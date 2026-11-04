"""Physical text budgets and bounded, factual capacity feedback; no inference."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import math

import pytest

from test_editorial_generation import state_for, install
from test_editorial_exact_composition import neds_state
from src.layout.editorial_layout import measure, text_budget, suggested_words
from src.layout.editorial_composition import initial_fit
from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import EditorialOutputError
from src.workflow.editorial_writing import (capacity_guidance, module_tasks, observed_edit,
    record_measured_edit, last_edit_feedback)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected live inference'))


def budget(mode='image_above_text', allocation=12):
    parallel = mode == 'image_left_text_right'
    text_y = 2 if parallel or mode == 'text_only' else 8
    children = [{'type': 'section_title', 'y': 1, 'height': .8},
        {'type': 'text', 'y': text_y, 'width': 8 if parallel else 16,
         'height': 6, 'font_size': 44, 'font_family': 'Arial', 'body_layout': mode}]
    if mode != 'text_only':
        children.append({'type': 'visual', 'y': 2, 'height': 5})
    return text_budget(children, module_y=1, allocated_height=allocation,
                       module_width=17, geometry_fingerprint='geometry')


@pytest.mark.parametrize('mode,available,width', [
    ('image_above_text', 5, 16), ('image_left_text_right', 11, 8), ('text_only', 11, 16)])
def test_budget_uses_actual_text_origin_and_lane(mode, available, width):
    result = budget(mode)
    assert result['status'] == 'measured'
    assert result['available_text_height_inches'] == available
    assert result['text_width_inches'] == width
    assert result['current_text_height_inches'] == 6
    assert result['spacing_height_inches'] == pytest.approx(.2 if mode != 'image_above_text' else 1.2)
    assert suggested_words(60, result) == round(60 * .95 * available / 6)


def test_no_space_and_parallel_visual_pressure_are_not_fake_word_targets():
    result = budget(allocation=6)
    assert result['status'] == 'no_text_space' and result['layout_pressure']
    assert result['available_text_height_inches'] == -1
    assert suggested_words(60, result) is None
    parallel = budget('image_left_text_right', allocation=4)
    assert parallel['status'] == 'measured' and parallel['layout_pressure']
    tiny = {**budget(), 'available_text_height_inches': .00001}
    assert suggested_words(1, tiny) is None


@pytest.mark.parametrize('children', [[], [{'type': 'text'}],
    [{'type': 'text'}, {'type': 'text'}],
    [{'type': 'text', 'y': 2, 'width': 8, 'height': math.nan, 'font_size': 44}]])
def test_unreliable_text_measurement_is_explicitly_unavailable(children):
    result = text_budget(children, module_y=1, allocated_height=12,
                         module_width=17, geometry_fingerprint='g')
    assert result['status'] == 'unavailable' and result['reason']
    assert suggested_words(60, result) is None


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_fifteen_families_bind_budget_to_real_compiled_text_and_frame(tmp_path, family):
    state = install(state_for(tmp_path, family))
    candidate = deepcopy(state['editorial_candidate'])
    result = measure(state, candidate, state['editorial_zones'])
    assert result['report']['candidate_id'] == candidate['candidate_id']
    for row in result['report']['modules']:
        frame = next(e['module_frame'] for e in result['layout']
                     if e.get('section_id') == row['module_id'] and e['type'] == 'section_container')
        text = next(e for e in result['layout'] if e.get('id') == row['module_id'] + '_text')
        value = row['text_budget']
        assert value['geometry_fingerprint'] == result['spec']['geometry_fingerprint']
        assert value['available_text_height_inches'] == pytest.approx(frame['y'] + frame['height'] - text['y'])
        assert value['text_width_inches'] == text['width']
        assert value['current_text_height_inches'] == text['height']
    assert candidate == state['editorial_candidate']


def test_real_parallel_layout_uses_shared_height_not_stacked_visual_cost(tmp_path):
    state = neds_state(tmp_path)
    result = initial_fit(state, fitter=measure)
    row = next(r for r in result['report']['modules'] if r['module_id'] == 'module_2')
    value = row['text_budget']
    assert value['body_layout'] == 'image_left_text_right'
    assert value['visual_height_inches'] > 5
    assert value['available_text_height_inches'] >= value['visual_height_inches'] - 1e-6
    assert value['available_text_height_inches'] == pytest.approx(
        row['allocated_height'] - value['before_text_height_inches'])


def report(words=43, height=6.8, overflow=4.38, geometry='g'):
    return {'version': 'editorial_fit_v2', 'candidate_id': 'candidate',
        'geometry_fingerprint': geometry, 'passed': overflow <= .01,
        'all_modules_90_percent': overflow <= .01, 'total_overflow_inches': overflow,
        'preflight': {'passed': overflow <= .01, 'issues': []},
        'geometry_trials': [{'local_history': 'retained'}],
        'modules': [{'module_id': 'm', 'zone_id': 'z', 'current_words': words,
            'utilization': (11.5881 + overflow) / 11.5881, 'allocated_height': 11.5881,
            'width_inches': 16, 'overage_inches': overflow,
            'text_budget': {'status': 'measured', 'current_text_height_inches': height,
                'available_text_height_inches': 2.4186, 'text_width_inches': 15.4}}]}


def feedback(tmp_path, before, after, change=None):
    state = install(state_for(tmp_path))
    candidate = state['editorial_candidate']
    # Keep authentic candidate-derived changes, use a small explicit measurement
    # to isolate physical improvement from mere reduction in word count.
    first = deepcopy(candidate)
    if change:
        change(candidate['modules'][0])
    before = deepcopy(before); after = deepcopy(after)
    for value in (before, after):
        value['candidate_id'] = candidate['candidate_id']
        value['modules'][0]['module_id'] = 'module_0'
    record = {'from': first['candidate_id'], 'to': candidate['candidate_id'],
        'changed': first != candidate, 'reason': 'Claimed successful compression.',
        'observed_edit': observed_edit(first, candidate), 'requested_tasks': module_tasks(before),
        'measurements_before': capacity_guidance(before)}
    state['editorial_history'] = [record]
    record_measured_edit(state['editorial_history'], candidate, after)
    return state, after, last_edit_feedback(state, after)


@pytest.mark.parametrize('words,height,overflow,directions', [
    (43, 6.8, 4.38, ('unchanged', 'unchanged', 'unchanged')),
    (30, 7.1, 4.7, ('reduced', 'increased', 'increased')),
    (43, 4.2, 1.8, ('unchanged', 'reduced', 'reduced')),
    (39, 6.2, 3.8, ('reduced', 'reduced', 'reduced')),
    (50, 7.2, 4.8, ('increased', 'increased', 'increased'))])
def test_feedback_distinguishes_word_changes_from_actual_physical_result(tmp_path, words, height, overflow, directions):
    _, _, value = feedback(tmp_path, report(), report(words, height, overflow),
        lambda m: m.update(presentation_style='plain'))
    row = value['modules'][0]
    assert tuple(row[k] for k in ('word_change', 'text_height_change', 'overflow_change')) == directions
    assert row['entry_text_changed'] is False  # Presentation change alone is not compression.
    assert not value['target_met']
    assert row['current_measurement_ref']['module_id'] == 'module_0'
    assert 'after' not in row and 'preflight_after' not in value
    assert 'reason' not in value


def test_feedback_tracks_new_overflow_and_rejects_stale_geometry_or_candidate(tmp_path):
    state, after, value = feedback(tmp_path, report(30, 2, 0), report(60, 7, 4))
    assert value['new_overflow_module_ids'] == ['module_0']
    assert value['modules'][0]['requested_action'] == 'keep'
    with pytest.raises(ValueError, match='matching'):
        last_edit_feedback(state, {**after, 'geometry_fingerprint': 'other'})
    with pytest.raises(ValueError, match='different candidate'):
        record_measured_edit(state['editorial_history'], state['editorial_candidate'], {**after, 'candidate_id': 'other'})
    state['editorial_candidate']['candidate_id'] = 'other'
    with pytest.raises(ValueError, match='matching'):
        last_edit_feedback(state, after)


def test_guidance_retains_final_defects_but_search_history_stays_local():
    source = report(); source['preflight']['issues'] = [{'element_id': 'm_text', 'code': 'OUT_OF_BOUNDS'}]
    original = deepcopy(source)
    guidance = capacity_guidance(source)
    assert guidance['preflight'] == source['preflight'] and 'geometry_trials' not in guidance
    assert guidance['version'] == 'editorial_capacity_guidance_v2'
    assert source == original
    source['modules'][0]['text_budget']['layout_pressure'] = True
    assert module_tasks(source)[0]['action'] == 'adjust_layout'


def test_noop_then_real_edits_use_three_distinct_charges_and_replay_without_calls(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    state = install(state_for(tmp_path)); original = deepcopy(state)
    monkeypatch.setattr(pipeline, 'fit', lambda s, c, z: measure(s, c, z))
    calls = []
    class Model:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            payload = json.loads(message.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])
            calls.append(payload)
            modules = []
            if len(calls) > 1:
                module = deepcopy(payload['whole_poster']['modules'][0])
                module['entries'][0]['text'] += ' Additional mechanism.'
                modules = [module]
            return SimpleNamespace(content=json.dumps({'modules': modules, 'remove_module_ids': [],
                'module_order': [], 'narrative_flow': '', 'reason': 'Compressed the content.'}),
                input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    pipeline.editorial_joint_node(state)
    assert len(calls) == len(state['editorial_history']) == 3
    assert [p['capacity_round'] for p in calls] == [1, 2, 3]
    assert calls[0]['last_edit_feedback'] is None
    assert calls[1]['last_edit_feedback']['candidate_changed'] is False
    assert calls[1]['last_edit_feedback']['modules'][0]['word_change'] == 'unchanged'
    assert calls[2]['last_edit_feedback']['candidate_changed'] is True
    assert len({c['key'] for c in state['editorial_budget']['charges']}) == 3
    assert state['editorial_fit']['completion_reason'] == 'repair_limit_reached'
    pipeline.editorial_joint_node(original)  # Resume from pre-stage checkpoint.
    assert len(calls) == 3
    assert original['editorial_history'] == state['editorial_history']
    assert original['editorial_candidate'] == state['editorial_candidate']
    assert not (Path(state['sample_preparation_dir']) / 'editorial_format_correction.json').exists()
    with pytest.raises(EditorialOutputError, match='exhausted'):
        pipeline.edit(state, measure(state, state['editorial_candidate'], state['editorial_zones']), 'capacity')
    assert len(calls) == 3


@pytest.mark.parametrize('stop', ['target_met', 'no_useful_edit'])
def test_stop_conditions_do_not_purchase_an_unneeded_edit(monkeypatch, tmp_path, stop):
    state = install(state_for(tmp_path))
    pipeline.charge(state, 'curator', 'offline_fixture')
    def fitted(s, c, z):
        result = measure(s, c, z)
        if stop == 'target_met':
            result['report'].update(passed=True, all_modules_90_percent=True)
        return result
    monkeypatch.setattr(pipeline, 'fit', fitted)
    if stop == 'no_useful_edit':
        monkeypatch.setattr(pipeline, 'module_tasks', lambda report: [{'action': 'keep'}])
    monkeypatch.setattr(pipeline, 'edit', lambda *a: pytest.fail('No actionable edit should be charged'))
    pipeline.editorial_joint_node(state)
    assert state['editorial_fit']['completion_reason'] == stop
    assert not state.get('editorial_history')
    assert all(c['phase'] != 'capacity' for c in state['editorial_budget']['charges'])


def test_narrative_only_change_is_distinct_from_entry_compression(tmp_path):
    state = install(state_for(tmp_path)); before = deepcopy(state['editorial_candidate'])
    after = deepcopy(before); after['narrative_flow'] += ' A clearer route.'
    value = observed_edit(before, after)
    assert value['changed'] and value['narrative_changed']
    assert not value['changed_modules']


def test_fast_geometry_estimate_cannot_certify_text_budget(tmp_path):
    state = install(state_for(tmp_path))
    result = measure(state, state['editorial_candidate'], state['editorial_zones'], exact=False)
    assert all(r['text_budget']['status'] == 'unavailable' and r['suggested_words'] is None
               for r in result['report']['modules'])


def test_changed_module_allocation_counts_even_when_zone_fingerprint_is_unchanged(tmp_path):
    before, after = report(), report()
    after['modules'][0]['allocated_height'] += 1
    _, _, value = feedback(tmp_path, before, after)
    assert value['geometry_changed']
    pair = value['modules'][0]['measurement_pairs']['allocated_height']
    assert pair['after'] == pair['before'] + 1


def test_first_request_also_rejects_missing_or_wrong_candidate_measurement(tmp_path):
    state = install(state_for(tmp_path))
    for value in ({}, {'candidate_id': 'different'}):
        with pytest.raises(ValueError, match='matching candidate measurement'):
            last_edit_feedback(state, value)
