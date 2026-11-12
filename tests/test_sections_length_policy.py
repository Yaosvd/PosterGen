"""Section-only output policy and non-accepting truncation evidence."""
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import LengthFinishReasonError
from openai.types.chat import ChatCompletion

from src.state.poster_state import ModelConfig, create_state
from src.workflow.editorial_requests import request, obj, STRING
from utils.model_requests import invoke, sample_policy, SampleRequestFailure, summarize
from utils.persistence import digest
import utils.langgraph_utils as language


@pytest.mark.parametrize('kind,limit', [
    ('editorial_sections', 32768), ('editorial_metadata', 12000),
    ('editorial_abt', 12000), ('editorial_visuals', 12000),
    ('editorial_proofreading', 12000), ('editorial_curator', 12000),
    ('editorial_writer', 12000), ('editorial_content_critic', 12000),
    ('editorial_visual_critic', 12000),
])
def test_phase_policy_reaches_actual_structured_sdk_body(tmp_path, monkeypatch, kind, limit):
    bodies = []
    def respond(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json={
            'id': 'offline', 'object': 'chat.completion', 'created': 0, 'model': 'offline',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': '{"result":"ok"}'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})
    constructor = language.ChatOpenAI
    monkeypatch.setenv('LOCAL_TEXT_BASE_URL', 'http://offline.invalid/v1')
    monkeypatch.setenv('LOCAL_TEXT_API_KEY', 'EMPTY')
    state = create_state(str(tmp_path/'paper.pdf'), text_model='local-text', vision_model='local-vision')
    state.update(output_dir=str(tmp_path), generation_route='optimization_family', raw_text='source')
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        # Preserve the actual SDK type check and wire serialization.
        monkeypatch.setattr(language, 'create_model', lambda config, **kwargs: constructor(
            model=config.model_name, base_url='http://offline.invalid/v1', api_key='EMPTY',
            http_client=client, temperature=config.temperature, max_tokens=config.max_tokens,
            max_retries=0, extra_body={'chat_template_kwargs': {'enable_thinking': config.enable_thinking}}))
        assert request(state, kind, {'original_text': 'source'}, obj({'result': STRING}),
                       directory='request', correction=False) == {'result': 'ok'}
    assert len(bodies) == 1
    assert bodies[0]['max_completion_tokens'] == limit
    assert bodies[0]['chat_template_kwargs']['enable_thinking'] is False
    assert bodies[0]['response_format']['type'] == 'json_schema'
    if kind in {'editorial_sections','editorial_metadata','editorial_abt','editorial_visuals','editorial_proofreading'}:
        assert bodies[0]['temperature'] == 0


def agent_at(tmp_path):
    return SimpleNamespace(state={'output_dir': str(tmp_path)}, agent_name='parser_sections',
                           config=ModelConfig('offline', 'local_text', max_tokens=32768),
                           request_policy=sample_policy({'generation_route': 'optimization_family'}))


@pytest.mark.parametrize('usage', [None, {'prompt_tokens': 20, 'completion_tokens': 32768, 'total_tokens': 32788}])
def test_sdk_length_is_saved_exactly_without_retry_or_acceptance(tmp_path, usage):
    completion = ChatCompletion(id='actual-offline-receipt', object='chat.completion', created=0, model='offline',
        choices=[{'index': 0, 'finish_reason': 'length',
                  'message': {'role': 'assistant', 'content': '{"paper_sections":['}}], usage=usage)
    calls = []
    def call(messages):
        calls.append(messages)
        try:
            raise LengthFinishReasonError(completion=completion)
        except Exception as exc:
            raise RuntimeError('wrapped') from exc
    with pytest.raises(SampleRequestFailure):
        invoke(agent_at(tmp_path), SimpleNamespace(invoke=call), [SimpleNamespace(content='private source')])
    assert len(calls) == 1
    rows = [json.loads(x) for x in (tmp_path/'model_requests.jsonl').read_text().splitlines()]
    assert rows[-1]['finish_reason'] == 'length'
    assert rows[-1]['output_tokens'] == (32768 if usage else None)
    receipt = json.loads((tmp_path/rows[-1]['diagnostic_path']).read_text())
    assert receipt['digest'] == digest(receipt['payload'])
    assert receipt['payload']['sdk_completion'] == completion.model_dump(mode='json')
    assert receipt['payload']['diagnostic_only'] is True
    assert receipt['payload']['requested_max_tokens'] == 32768
    assert 'private source' not in (tmp_path/'model_requests.jsonl').read_text()
    assert summarize(tmp_path)['truncated'] == 1
    assert not list(tmp_path.rglob('accepted.json'))


def test_timeout_does_not_invent_provider_response(tmp_path):
    def fail(_): raise httpx.ReadTimeout('no returned response')
    with pytest.raises(SampleRequestFailure):
        invoke(agent_at(tmp_path), SimpleNamespace(invoke=fail), [])
    assert not (tmp_path/'request_diagnostics').exists()


def test_non_sdk_length_receipt_also_remains_diagnostic(tmp_path):
    response = SimpleNamespace(content='unfinished', response_metadata={'finish_reason': 'length'},
                               usage_metadata={'output_tokens': 32768})
    with pytest.raises(SampleRequestFailure):
        invoke(agent_at(tmp_path), SimpleNamespace(invoke=lambda _: response), [])
    receipt = json.loads(next((tmp_path/'request_diagnostics').glob('*.json')).read_text())['payload']
    assert receipt['message_content'] == 'unfinished' and 'sdk_completion' not in receipt


def test_length_diagnostic_cannot_buy_editorial_repair_or_resume_call(tmp_path, monkeypatch):
    calls = []
    class Agent:
        def __init__(self, system, config, state, name):
            self.state, self.config, self.agent_name = state, config, name
            self.request_policy = sample_policy(state)
        def reset(self): pass
        def step(self, message):
            def fail(messages):
                calls.append(messages)
                completion = ChatCompletion(id='offline', object='chat.completion', created=0, model='offline',
                    choices=[{'index':0, 'finish_reason':'length',
                              'message':{'role':'assistant','content':'{"result":'}}],
                    usage={'prompt_tokens':20,'completion_tokens':32768,'total_tokens':32788})
                raise LengthFinishReasonError(completion=completion)
            return invoke(self, SimpleNamespace(invoke=fail), [SimpleNamespace(content=message)])
    monkeypatch.setattr(language, 'LangGraphAgent', Agent)
    state = create_state(str(tmp_path/'paper.pdf'), text_model='local-text', vision_model='local-vision')
    state.update(output_dir=str(tmp_path), generation_route='optimization_family', raw_text='source')
    args = (state, 'editorial_sections', {'original_text':'source'}, obj({'result':STRING}))
    with pytest.raises(SampleRequestFailure):
        request(*args, directory='sections')
    assert (tmp_path/'sections/failure_00.json').exists()
    assert not (tmp_path/'sections/response_00.json').exists()
    assert not (tmp_path/'sections/accepted.json').exists()
    assert not (tmp_path/'sections/request_01.json').exists()
    with pytest.raises(ValueError, match='charged but response missing'):
        request(*args, directory='sections')
    assert len(calls) == 1
