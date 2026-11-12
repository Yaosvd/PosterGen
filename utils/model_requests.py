"""Observable, bounded sample requests. Classic retains its legacy policy."""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx


class SampleRequestFailure(RuntimeError):
    pass


def sample_policy(state):
    if (state or {}).get('generation_route') != 'optimization_family':
        return None
    settings = ((state.get('critic_config') or {}).get('sample_execution') or {})
    seconds = settings.get('response_timeout_seconds', 900)
    retries = settings.get('max_transient_retries', 1)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 60 <= seconds <= 1800:
        raise ValueError('Sample response timeout must be between 60 and 1800 seconds')
    if type(retries) is not int or not 0 <= retries <= 1:
        raise ValueError('Sample transient retries must be 0 or 1')
    return {'response_timeout_seconds': seconds, 'max_transient_retries': retries}


def factory_settings(policy):
    return {'request_timeout': policy['response_timeout_seconds'],
            'max_retries': 0}


def _retryable(exc):
    # A read timeout may leave generation running remotely; never duplicate it.
    chain, seen = exc, set()
    while chain is not None and id(chain) not in seen:
        seen.add(id(chain))
        if isinstance(chain, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
            return False
        chain = chain.__cause__ or chain.__context__
    # ConnectTimeout is safe only when identified explicitly by its cause.
    chain = exc
    seen = set()
    while chain is not None and id(chain) not in seen:
        seen.add(id(chain))
        if isinstance(chain, (httpx.ConnectError, httpx.ConnectTimeout)):
            return True
        chain = chain.__cause__
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)) or type(exc).__name__ == 'APITimeoutError':
        return False
    return getattr(exc, 'status_code', None) in {429, 500, 502, 503, 504}



def _length_completion(error):
    """Return only the actual SDK completion, never reconstruct missing output."""
    from openai import LengthFinishReasonError
    current, seen = error, set()
    while isinstance(current, Exception) and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, LengthFinishReasonError):
            return current.completion.model_dump(mode='json')
        current = current.__cause__ or current.__context__
    return None


def _save_truncation(agent, request_id, attempt, messages, *, completion=None, response=None):
    """Diagnostic only. This receipt cannot become an accepted editorial result."""
    from utils.persistence import _atomic_json, digest
    if completion is not None:
        usage = completion.get('usage') or {}
        output = {'sdk_completion': completion}
        input_tokens, output_tokens = usage.get('prompt_tokens'), usage.get('completion_tokens')
    else:
        usage = getattr(response, 'usage_metadata', None) or {}
        output = {'message_content': getattr(response, 'content', None),
                  'response_metadata': getattr(response, 'response_metadata', None),
                  'usage_metadata': usage}
        input_tokens, output_tokens = usage.get('input_tokens'), usage.get('output_tokens')
    payload = {'version': 1, 'diagnostic_only': True, 'request_id': request_id,
               'attempt': attempt, 'agent': agent.agent_name,
               'messages_digest': digest([{'type': getattr(m, 'type', None), 'content': m.content}
                                          for m in messages]),
               'requested_max_tokens': getattr(getattr(agent, 'config', None), 'max_tokens', None),
               **output}
    relative = Path('request_diagnostics') / f'{request_id}_{attempt:02d}_length.json'
    _atomic_json(Path(agent.state['output_dir']) / relative,
                 {'payload': payload, 'digest': digest(payload)})
    return {'diagnostic_path': str(relative), 'input_tokens': input_tokens, 'output_tokens': output_tokens}


def invoke(agent, model, messages):
    policy = agent.request_policy
    request_id = uuid.uuid4().hex
    root = Path(agent.state['output_dir'])
    root.mkdir(parents=True, exist_ok=True)
    context = agent.state.get('iteration_context') or {}
    def event(kind, **details):
        row = {'event': kind, 'request_id': request_id, 'agent': agent.agent_name,
               'time': datetime.now(timezone.utc).isoformat(),
               'sample_id': context.get('sample_id'), 'attempt_id': context.get('attempt_id'), **details}
        with (root/'model_requests.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
        from utils.src.logging_utils import emit_progress
        if not emit_progress({'type': 'model_request', **row}):
            print(f"Model request | {agent.agent_name} | {kind} | "
                  f"attempt {details.get('attempt')} | {details.get('elapsed_seconds', 0):.1f}s", flush=True)
    for index in range(1 + policy['max_transient_retries']):
        from utils.concurrency import slot, settings
        managed = settings() is not None
        if managed:
            event('request_queued', attempt=index+1)
        with slot('model') as queue_seconds:
            if managed:
                event('request_admitted', attempt=index+1, queue_seconds=round(queue_seconds, 3))
            started = time.perf_counter()
            event('request_start', attempt=index+1, timeout_seconds=policy['response_timeout_seconds'],
                  input_characters=sum(len(str(m.content)) for m in messages))
            try:
                request_started = time.perf_counter()
                try:
                    response = model.invoke(messages)
                finally:
                    metrics = agent.state.get('timing_metrics')
                    if (agent.agent_name in {'critic_content', 'critic_visual'}
                            and metrics is not None and hasattr(metrics, 'record_component')):
                        metrics.record_component(agent.agent_name + '_request',
                            time.perf_counter() - request_started, context.get('iteration', 0))
            except Exception as exc:
                completion = _length_completion(exc)
                details = ({'finish_reason': 'length', **_save_truncation(
                    agent, request_id, index+1, messages, completion=completion)}
                    if completion is not None else {})
                again = completion is None and index < policy['max_transient_retries'] and _retryable(exc)
                event('request_retry' if again else 'request_failed', attempt=index+1,
                      elapsed_seconds=round(time.perf_counter()-started, 3), error_type=type(exc).__name__, **details)
                if not again:
                    raise SampleRequestFailure(f'{agent.agent_name}: model request failed ({type(exc).__name__}); see model_requests.jsonl') from exc
                time.sleep(2)
                continue
        metadata = getattr(response, 'response_metadata', {}) or {}
        usage = getattr(response, 'usage_metadata', {}) or {}
        raw_finish = metadata.get('finish_reason')
        finish = str(raw_finish) if raw_finish is not None else None
        truncated = finish and finish.lower().split('.')[-1] in {'length', 'max_tokens'}
        diagnostic = _save_truncation(agent, request_id, index+1, messages, response=response) if truncated else {}
        event('request_finished', attempt=index+1, elapsed_seconds=round(time.perf_counter()-started, 3),
              finish_reason=finish, input_tokens=usage.get('input_tokens'), output_tokens=usage.get('output_tokens'),
              **({'diagnostic_path': diagnostic['diagnostic_path']} if diagnostic else {}))
        if truncated:
            raise SampleRequestFailure(f'{agent.agent_name}: model output truncated; see model_requests.jsonl')
        return response


def summarize(root):
    """Physical attempts, separately from the legacy logical API-call counts."""
    counts = {'started': 0, 'finished': 0, 'failed': 0, 'retries': 0, 'truncated': 0}
    keys = {'request_start': 'started', 'request_finished': 'finished',
            'request_failed': 'failed', 'request_retry': 'retries'}
    for path in Path(root).rglob('model_requests.jsonl'):
        for line in path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['event'] in keys:
                counts[keys[row['event']]] += 1
            if str(row.get('finish_reason')).lower().split('.')[-1] in {'length', 'max_tokens'}:
                counts['truncated'] += 1
    return counts
