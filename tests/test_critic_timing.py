"""Evaluation timing is nested, cumulative and independent of scoring outcomes."""
import json
from types import SimpleNamespace

import httpx
import pytest

from src.state.poster_state import ModelConfig, TimingMetrics
from src.workflow.runtime import save_timing_log
from utils import model_requests
from test_exploration_samples import runner, scientific, critic_with_scores


@pytest.mark.parametrize('agent_name', ['critic_content', 'critic_visual'])
@pytest.mark.parametrize('outcome', ['success', 'failure', 'retry', 'truncated'])
def test_physical_request_time_includes_failures_but_excludes_retry_sleep(
        tmp_path, monkeypatch, agent_name, outcome):
    clock = [0.0]
    monkeypatch.setattr(model_requests.time, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(model_requests.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    metrics = TimingMetrics()
    agent = SimpleNamespace(agent_name=agent_name, state={
        'output_dir': str(tmp_path), 'timing_metrics': metrics,
        'iteration_context': {'iteration': 3}}, request_policy={
        'max_transient_retries': 1, 'response_timeout_seconds': 900})
    calls = []

    def invoke(messages):
        calls.append(messages)
        clock[0] += 5
        if outcome == 'failure':
            raise httpx.ReadTimeout('offline')
        if outcome == 'retry' and len(calls) == 1:
            raise httpx.ConnectTimeout('offline')
        return SimpleNamespace(response_metadata={
            'finish_reason': 'length' if outcome == 'truncated' else 'stop'})

    model = SimpleNamespace(invoke=invoke)
    if outcome in {'failure', 'truncated'}:
        with pytest.raises(model_requests.SampleRequestFailure):
            model_requests.invoke(agent, model, [])
    else:
        model_requests.invoke(agent, model, [])
    expected = 10 if outcome == 'retry' else 5
    assert getattr(metrics, agent_name + '_request_time') == expected
    assert metrics.critic_time == 0  # Only the runner owns the enclosing timer.
    assert clock[0] == expected + (2 if outcome == 'retry' else 0)
    assert all(row['iteration'] == 3 for row in metrics.iteration_timings)
    rows = [json.loads(line) for line in (tmp_path / 'model_requests.jsonl').read_text().splitlines()]
    assert sum(row['event'] == 'request_start' for row in rows) == len(calls)


@pytest.mark.parametrize('failure', [False, True])
def test_runner_records_total_once_per_sample_even_on_evaluation_failure(tmp_path, monkeypatch, failure):
    import src.workflow.exploration_runner as runner_module
    clock = [0.0]
    monkeypatch.setattr(runner_module.time, 'perf_counter', lambda: clock[0])
    score = critic_with_scores([40, 90])

    def critic(state):
        clock[0] += 7
        if failure:
            raise RuntimeError('offline critic failure')
        return score(state)

    generator = runner(tmp_path, samples=2, critic=critic)
    result = generator.run(scientific(tmp_path), paper_ready=True)
    metrics = result['timing_metrics']
    assert metrics.critic_time == 14
    rows = [row for row in metrics.iteration_timings if row['component'] == 'critic']
    assert rows == [{'iteration': i, 'component': 'critic', 'elapsed_seconds': 7} for i in (1, 2)]
    assert [r['status'] for r in result['run_state']['results']] == [
        'evaluation_failed' if failure else 'scored'] * 2


def test_export_keeps_nested_request_times_out_of_stage_totals_and_history(tmp_path):
    metrics = TimingMetrics(pipeline_start=1, pipeline_end=101)
    for iteration in (1, 2):
        metrics.record_component('critic', 20, iteration)
        metrics.record_component('critic_content_request', 5, iteration)
        metrics.record_component('critic_visual_request', 12, iteration)
    metrics.record_component('joint_preparation', 40)
    metrics.record_component('source_balancer', 30)
    metrics.iteration_timings.clear()  # Totals survive bounded event pruning.
    # A previous process's journal must not inflate this execution's breakdown.
    (tmp_path / 'model_requests.jsonl').write_text(json.dumps({
        'event': 'request_finished', 'agent': 'critic_content', 'elapsed_seconds': 900}) + '\n')
    state = {'output_dir': str(tmp_path), 'timing_metrics': metrics,
        'text_model': ModelConfig('text', 'local_text'),
        'vision_model': ModelConfig('vision', 'local_vision'),
        'generation_route': 'optimization_family', 'joint_preparation': True,
        'editorial_version': 'poster_editorial_v1'}
    report = save_timing_log(state)
    components = report['component_timing']
    assert components['critic']['time_seconds'] == 40
    assert components['critic']['breakdown'] == {
        'content_model_requests_seconds': 10,
        'visual_model_requests_seconds': 24,
        'local_processing_and_retry_wait_seconds': 6}
    assert 'critic_content_request' not in components and 'critic_visual_request' not in components
    assert components['source_balancer']['timing_scope'] == 'included_in_joint_preparation'
    assert report['overall']['total_runtime_seconds'] == 100
    assert report['model_request_attempts']['finished'] == 1
