"""Terminal behavior without real model/GPU calls or timer sleeps."""
from contextlib import redirect_stdout
import io
import json
from types import SimpleNamespace

import httpx
import pytest
from rich.console import Console

from src.workflow import sample_progress as progress
from src.workflow.runtime import tee_console_output
from utils import model_requests
from utils.src.logging_utils import emit_progress, log_agent_info, log_agent_warning, progress_operation


def test_compact_output_keeps_details_and_traceback_in_log(tmp_path):
    terminal = io.StringIO()
    path = tmp_path / 'run.log'
    with redirect_stdout(terminal), tee_console_output(path), progress.SampleProgressReporter(path) as reporter:
        reporter.emit({'type': 'task_inputs', 'iteration': 1, 'planned_samples': 3})
        reporter.emit({'type': 'stage_start', 'stage': 'renderer'})
        log_agent_info('renderer', 'rendering text element [m1]')
        print('third-party verbose output')
        reporter.emit({'type': 'layout_detail', 'label': 'exact_candidate started', 'variant': 'trial1'})
        log_agent_warning('renderer', 'missing image [figure_1]')
        reporter.write_traceback('Traceback: original failure')
    visible, full = terminal.getvalue(), path.read_text()
    assert '[   Renderer   ]' in visible and '[样本 1/3]' in visible
    assert 'missing image [figure_1]' in visible and '完整异常堆栈' in visible
    for detail in ('rendering text element [m1]', 'third-party verbose output',
                   'exact_candidate started', 'Traceback: original failure'):
        assert detail not in visible and detail in full
    assert not reporter._thread.is_alive()
    assert emit_progress({'type': 'test'}) is False


def test_verbose_includes_source_location_and_raw_output(tmp_path):
    terminal = io.StringIO()
    path = tmp_path / 'run.log'
    with redirect_stdout(terminal), tee_console_output(path), progress.SampleProgressReporter(path, verbose=True):
        log_agent_info('renderer', 'rendering [m1]')
        print('raw diagnostics')
    assert 'tests/test_sample_progress.py:' in terminal.getvalue()
    assert 'rendering [m1]' in terminal.getvalue() and 'raw diagnostics' in terminal.getvalue()
    assert terminal.getvalue() == path.read_text()


def test_heartbeat_tracks_request_and_clears_completed_stage(tmp_path, monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(progress.time, 'perf_counter', lambda: clock[0])
    terminal = io.StringIO()
    with progress.SampleProgressReporter(tmp_path/'log', terminal=terminal) as reporter:
        reporter.emit({'type': 'task_inputs', 'iteration': 2, 'planned_samples': 3})
        reporter.emit({'type': 'stage_start', 'stage': 'critic'})
        with progress_operation('editorial_content_critic'):
            clock[0] += 3
            reporter.emit({'type': 'model_request', 'event': 'request_start', 'agent': 'critic_content', 'attempt': 1})
            clock[0] += 17
            reporter.heartbeat()
            text = terminal.getvalue()
            assert '阶段    20.0s' in text and '已等待 17.0s' in text
            assert '评价科学内容与模块依赖（模型请求 1）' in text
            reporter.emit({'type': 'model_request', 'event': 'request_finished', 'agent': 'critic_content',
                           'attempt': 1, 'elapsed_seconds': 17, 'finish_reason': 'stop'})
        reporter.emit({'type': 'stage_done', 'stage': 'critic', 'elapsed': 20})
        before = terminal.getvalue()
        clock[0] += 100
        reporter.heartbeat()
        assert terminal.getvalue() == before
        reporter.emit({'type': 'stage_start', 'stage': 'publish'})
        clock[0] += 2
        reporter.heartbeat()
        assert '阶段     2.0s' in terminal.getvalue()
        assert '保存样本' in terminal.getvalue()


@pytest.mark.parametrize('outcome', ['success', 'retry', 'failure', 'truncated', 'validation'])
def test_real_request_events_preserve_transport_and_validation_semantics(tmp_path, monkeypatch, outcome):
    clock = [0.0]
    monkeypatch.setattr(model_requests.time, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(model_requests.time, 'sleep', lambda n: clock.__setitem__(0, clock[0]+n))
    output = io.StringIO()
    calls = []
    agent = SimpleNamespace(agent_name='critic_content', state={'output_dir': str(tmp_path)},
                            request_policy={'max_transient_retries': 1, 'response_timeout_seconds': 900})
    response = SimpleNamespace(response_metadata={'finish_reason': 'length' if outcome == 'truncated' else 'stop'},
                               usage_metadata={'input_tokens': 10, 'output_tokens': 5})
    def invoke(messages):
        calls.append(messages)
        clock[0] += 5
        if outcome == 'failure':
            raise httpx.ReadTimeout('offline failure')
        if outcome == 'retry' and len(calls) == 1:
            raise httpx.ConnectTimeout('offline retry')
        return response
    with progress.SampleProgressReporter(tmp_path/'log', terminal=output) as reporter:
        reporter.emit({'type': 'stage_start', 'stage': 'critic'})
        def run():
            with progress_operation('editorial_content_critic'):
                result = model_requests.invoke(agent, SimpleNamespace(invoke=invoke), [SimpleNamespace(content='unchanged input')])
                if outcome == 'validation':
                    raise ValueError('invalid module reference')
                return result
        if outcome in {'failure', 'truncated', 'validation'}:
            with pytest.raises((model_requests.SampleRequestFailure, ValueError)):
                run()
            assert '响应校验完成' not in output.getvalue()
            assert '失败' in output.getvalue()
        else:
            assert run() is response
            assert '响应校验完成' in output.getvalue()
        assert reporter._request is None and reporter._operation is None
    assert len(calls) == (2 if outcome == 'retry' else 1)
    assert [[m.content for m in row] for row in calls] == [['unchanged input']] * len(calls)
    rows = [json.loads(line) for line in (tmp_path/'model_requests.jsonl').read_text().splitlines()]
    assert sum(r['event'] == 'request_start' for r in rows) == len(calls)
    if outcome == 'retry':
        assert '重试等待（2s）' in output.getvalue() and '尝试 2' in output.getvalue()
    if outcome == 'truncated':
        assert '输出截断' in output.getvalue()


@pytest.mark.parametrize('group', ['high_score', 'low_score', 'evaluation_failed'])
def test_saved_group_and_failed_evaluation_are_truthful(tmp_path, group):
    output = io.StringIO()
    reporter = progress.SampleProgressReporter(tmp_path/'log', terminal=output)
    reporter.emit({'type': 'stage_start', 'stage': 'critic'})
    if group == 'evaluation_failed':
        reporter.emit({'type': 'stage_done', 'stage': 'critic', 'elapsed': 12, 'outcome': 'evaluation_failed'})
        assert '评分失败/不完整' in output.getvalue()
    directory = str(tmp_path / '海报 storage' / group / 'p1')
    reporter.emit({'type': 'sample_saved', 'poster_directory': directory, 'result': {'sample_id': 's1', 'poster_id': 'p1',
                   'status': 'evaluation_failed' if group == 'evaluation_failed' else 'scored',
                   'score': None if group == 'evaluation_failed' else 90, 'grouping': group}})
    assert group in output.getvalue() and 'unclassified' not in output.getvalue()
    assert 's1 saved' in output.getvalue()
    assert f'保存位置：{directory}' in output.getvalue()


def test_no_render_is_recorded_without_claiming_poster_saved():
    text = progress.format_event({'type': 'sample_saved', 'poster_directory': '/must-not-display', 'result': {
        'sample_id': 's1', 'poster_id': None, 'status': 'generation_failed', 'score': None}})
    assert 'no poster exported' in text and 'saved' not in text
    assert '保存位置' not in text and '/must-not-display' not in text


def test_color_terminal_and_plain_log(tmp_path):
    terminal = io.StringIO()
    path = tmp_path/'run.log'
    with redirect_stdout(terminal), tee_console_output(path) as _:
        reporter = progress.SampleProgressReporter(path)
        reporter.console = Console(file=reporter.terminal, force_terminal=True, color_system='standard')
        reporter.emit({'type': 'stage_start', 'stage': 'parser'})
    assert '\x1b[' in terminal.getvalue()
    assert '\x1b[' not in path.read_text()
    assert '[    Parser    ]' in path.read_text()


def test_observer_is_context_local_and_restores_on_exception(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with pytest.raises(RuntimeError):
        with progress.SampleProgressReporter(tmp_path/'log', terminal=io.StringIO()):
            with ThreadPoolExecutor() as executor:
                assert executor.submit(emit_progress, {'type': 'test'}).result() is False
            raise RuntimeError('exit path')
    assert emit_progress({'type': 'test'}) is False


def test_runner_emits_critic_outcome_before_saving_each_sample(tmp_path):
    from test_exploration_samples import runner, scientific
    def failed_critic(state):
        raise RuntimeError('offline evaluation failure')
    gen = runner(tmp_path, samples=2, critic=failed_critic)
    events = []
    gen.status_callback = lambda payload: events.append(payload.get('progress_event', {}))
    result = gen.run(scientific(tmp_path), paper_ready=True)
    assert result['run_state']['rendered_samples'] == 2
    for number in (1, 2):
        per_sample = [e for e in events if e.get('iteration') == number]
        start = next(i for i,e in enumerate(per_sample) if e.get('type') == 'stage_start' and e.get('stage') == 'critic')
        end = next(i for i,e in enumerate(per_sample) if e.get('type') == 'stage_done' and e.get('stage') == 'critic')
        saved = next(i for i,e in enumerate(per_sample) if e.get('type') == 'sample_saved')
        assert start < end < saved
        assert per_sample[end]['outcome'] == 'evaluation_failed'
        assert per_sample[saved]['result']['grouping'] == 'evaluation_failed'
        assert per_sample[start]['planned_samples'] == 2
        saved_event = per_sample[saved]
        directory = gen.storage.verify_poster(saved_event['result']['poster_id'])
        assert saved_event['poster_directory'] == str(directory.resolve())
        assert (directory / 'poster.png').is_file() and (directory / 'poster.pptx').is_file()


@pytest.mark.parametrize('evaluation_failure', [False, True])
def test_compact_reporter_with_real_offline_pptx_png_pipeline(tmp_path, monkeypatch, evaluation_failure):
    from src.workflow.exploration_runner import PosterExplorationRunner
    from test_editorial_generation import test_default_runner_real_compile_render_critic_and_publication
    original = PosterExplorationRunner.__init__
    output = io.StringIO()
    path = tmp_path/'terminal.log'
    with redirect_stdout(output), tee_console_output(path), progress.SampleProgressReporter(path) as reporter:
        def constructor(self, **kwargs):
            original(self, progress_reporter=reporter, **kwargs)
        monkeypatch.setattr(PosterExplorationRunner, '__init__', constructor)
        test_default_runner_real_compile_render_critic_and_publication(
            monkeypatch, tmp_path/'fixture', evaluation_failure, False, not evaluation_failure, False)
    visible, full = output.getvalue(), path.read_text()
    assert '[   Renderer   ]' in visible and '[    Critic    ]' in visible and '[     Save     ]' in visible
    assert 'rendering section title' not in visible and 'rendering section title' in full
    if evaluation_failure:
        assert '评分失败/不完整' in visible and 'evaluation_failed' in visible
    else:
        assert '完成（存在布局缺陷）' in visible and 'low_score' in visible
    assert '响应校验完成' in visible
    posters = list((tmp_path/'fixture'/'store'/'posters').glob('*/*/*/poster.png'))
    assert len(posters) == 1
    assert f'保存位置：{posters[0].parent.resolve()}' in visible
    assert f'保存位置：{posters[0].parent.resolve()}' in full
    assert not reporter._thread.is_alive()
