"""Internal column gaps must drive one edit without weakening physical fit."""
from copy import deepcopy
import socket

import pytest

from src.workflow.editorial_writing import (
    capacity_tasks, capacity_guidance, writing_assessment, record_capacity_result)
from src.layout.editorial_body_budget import measured_body_budgets
from src.layout.editorial_composition import HORIZONTAL, VERTICAL


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a: pytest.fail('Offline test attempted network'))


def result_for(body_height=3.8666666667, available=6.3527755733, font_size=44, mode=HORIZONTAL):
    allocated = available + 1
    used = max(body_height, available) + 1
    return {'report': {'passed': used <= allocated, 'all_modules_90_percent': used <= allocated,
        'total_overflow_inches': max(0, used-allocated), 'total_underfill_inches': 0,
        'modules': [{'module_id': 'm', 'body_layout': mode, 'utilization': used/allocated,
                     'allocated_height': allocated, 'intrinsic_height': used,
                     'overage_inches': max(0, used-allocated), 'missing_height_inches': 0,
                     'current_words': 48}]},
        'layout': [{'type': 'section_container', 'section_id': 'm',
                    'module_frame': {'y': 0, 'height': allocated}},
                   {'type': 'visual', 'section_id': 'm', 'y': 1, 'height': available},
                   {'type': 'text', 'section_id': 'm', 'y': 1, 'height': body_height,
                    'width': 10, 'font_size': font_size}]}


def test_image_full_body_short_has_one_reference_and_does_not_mutate_geometry():
    result = result_for(); before = deepcopy(result)
    tasks = capacity_tasks(result)
    task = tasks['modules'][0]
    assert task['action'] == 'expand' and task['requires_prose_rewrite']
    assert task['action_reason'] == 'horizontal_body_underfill'
    assert task['current_words'] == 48 and task['reference_words'] == 70
    assert task['body_utilization'] == pytest.approx(.60865784)
    assert 'suggested_words' not in task
    assert result == before
    fit = writing_assessment(result)
    assert fit['needs_edit'] and not fit['target_met']
    result['report']['writing_fit'] = fit
    assert capacity_guidance(result['report'])['modules'][0]['suggested_action'] == task['action']


@pytest.mark.parametrize('height,available,action,reason', [
    (8.99, 10, 'expand', 'horizontal_body_underfill'),
    (9, 10, 'keep', 'horizontal_body_target_met'),
    (9.5, 10, 'keep', 'horizontal_body_target_met'),
    (10.1, 10, 'compress', 'physical_overflow'),
    (1.6, 2, 'keep', 'below_one_line_exemption'),
])
def test_threshold_and_one_line_exception(height, available, action, reason):
    task = capacity_tasks(result_for(height, available))['modules'][0]
    assert (task['action'], task['action_reason']) == (action, reason)
    if reason == 'below_one_line_exemption':
        assert task['body_utilization'] < .9


def test_actual_font_size_controls_the_one_line_exception():
    assert capacity_tasks(result_for(1, 2, font_size=44))['modules'][0]['action'] == 'expand'
    assert capacity_tasks(result_for(1, 2, font_size=72))['modules'][0]['action'] == 'keep'


@pytest.mark.parametrize('mode', [VERTICAL, None])
def test_other_layout_actions_keep_their_original_module_rule(mode):
    result = result_for(mode=mode)
    assert capacity_tasks(result)['modules'][0]['action'] == 'keep'
    result['report']['modules'][0]['utilization'] = .8
    assert capacity_tasks(result)['modules'][0]['action'] == 'expand'


@pytest.mark.parametrize('damage', ['missing_body', 'missing_frame', 'zero_height', 'nan', 'missing_size', 'no_space'])
def test_missing_measurement_never_certifies_fit_or_blindly_expands(damage):
    result = result_for()
    if damage == 'missing_body': result['layout'].pop()
    elif damage == 'missing_frame': result['layout'][0].pop('module_frame')
    elif damage == 'zero_height': result['layout'][-1]['height'] = 0
    elif damage == 'nan': result['layout'][-1]['height'] = float('nan')
    elif damage == 'missing_size': result['layout'][-1].pop('font_size')
    else: result['layout'][-1]['y'] = 20
    assessment = writing_assessment(result)
    assert not assessment['target_met']
    assert assessment['modules'][0]['body_measurement_status'] == 'unknown'
    assert capacity_tasks(result)['modules'][0]['action'] != 'expand'


def test_fixed_content_overflow_takes_priority_over_body_underfill():
    result = result_for(); result['layout'][1]['height'] += 1
    task = capacity_tasks(result)['modules'][0]
    assert task['action'] == 'compress'
    assert 'shorter body alone' in task['rewrite_instruction']


@pytest.mark.parametrize('after_height,changed,outcome', [
    (3, False, 'rewrite_not_executed'),
    (5, True, 'improved_underfill_remaining'),
    (2, True, 'rewrite_did_not_reduce_underfill'),
    (9, True, 'target_met'),
    (11, True, 'introduced_overflow'),
])
def test_outcomes_use_body_measurements_even_with_full_image(after_height, changed, outcome):
    before = result_for(3, 10)
    before['report']['writing_fit'] = writing_assessment(before)
    history = [{'phase': 'capacity', 'measurements_before': capacity_guidance(before['report']),
                'prose_changes': [{'module_id': 'm', 'prose_changed': changed}]}]
    after = result_for(after_height, 10)
    after['report']['writing_fit'] = writing_assessment(after)
    record_capacity_result(history, {'candidate_id': 'after'}, after['report'])
    assert history[0]['capacity_result']['modules'][0]['outcome'] == outcome
    assert (history[0]['capacity_result']['status'] == 'target_met') == (outcome == 'target_met')


def test_stale_attached_assessment_is_recomputed():
    result = result_for(3, 10)
    result['report']['writing_fit'] = writing_assessment(result)
    result['layout'][-1]['height'] = 9.5
    assert not writing_assessment(result)['needs_edit']


def test_local_writing_policy_is_not_sent_to_critic(monkeypatch):
    import src.workflow.editorial_critic as critic
    monkeypatch.setattr(critic, 'diagnostic_provenance', lambda s: {})
    monkeypatch.setattr(critic, 'annotate_gaps', lambda *a: None)
    state = {'editorial_fit': {'passed': True, 'writing_fit': writing_assessment(result_for()),
                              'geometry_trials': ['local']}}
    original = deepcopy(state)
    assert critic._render_diagnostics(state)['editorial_fit'] == {'passed': True}
    assert state == original


@pytest.mark.parametrize('body_ratio,expected_calls,physical_passed', [(.6, 1, True), (.95, 0, True), (.95, 1, False)])
def test_full_modules_do_not_skip_body_task_and_noop_is_only_one_call(tmp_path, monkeypatch, body_ratio, expected_calls, physical_passed):
    from test_editorial_generation import state_for, install
    from src.workflow import editorial_pipeline as pipeline
    from src.layout.editorial_layout import measure
    state = install(state_for(tmp_path))
    pipeline.charge(state, 'curator', 'offline-initial-draft')
    calls = []
    def fitted(st, candidate, zones):
        result = measure(st, candidate, zones)
        # Isolate stopping logic: measured full image beside shorter text.
        for row in result['report']['modules']:
            row.update(utilization=1, overage_inches=0, missing_height_inches=0,
                       body_layout=HORIZONTAL)
            body = next(e for e in result['layout'] if e.get('section_id') == row['module_id'] and e['type'] == 'text')
            frame = next(e['module_frame'] for e in result['layout'] if e.get('section_id') == row['module_id'] and e['type'] == 'section_container')
            body['height'] = body_ratio * (frame['y'] + frame['height'] - body['y'])
        result['report'].update(passed=physical_passed, all_modules_90_percent=True, total_overflow_inches=0)
        return result
    monkeypatch.setattr(pipeline, 'fit', fitted)
    def response(st, kind, payload, schema, **kwargs):
        calls.append(payload)
        assert all(t['action'] == ('expand' if body_ratio < .9 else 'keep') for t in payload['capacity_tasks']['modules'])
        return {'modules': [], 'remove_module_ids': [], 'module_order': [], 'narrative_flow': '', 'reason': 'No useful addition.'}
    import json
    from types import SimpleNamespace
    import utils.langgraph_utils as language
    class Model:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            payload = json.loads(message.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])
            return SimpleNamespace(content=json.dumps(response(state, None, payload, None)), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    pipeline.editorial_joint_node(state)
    assert len(calls) == expected_calls
    assert state['editorial_fit']['writing_fit']['target_met'] == (expected_calls == 0)
    if expected_calls:
        assert state['editorial_fit']['completion_reason'] == 'no_useful_edit'
        assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'capacity']
        assert all(r['outcome'] == ('rewrite_not_executed' if body_ratio < .9 else 'target_met')
                   for r in state['editorial_history'][0]['capacity_result']['modules'])
