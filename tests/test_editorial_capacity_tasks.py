"""Capacity input de-duplication and honest one-round outcome diagnostics."""
from copy import deepcopy
from math import nextafter

import pytest

from test_editorial_generation import state_for, install
from src.layout.editorial_layout import measure
from src.layout.editorial_body_budget import measured_body_budgets
from src.workflow.editorial_writing import (
    capacity_guidance, capacity_measurements, capacity_tasks, prose_changes, record_capacity_result)


def test_tasks_use_body_space_once_and_leave_full_measurement_untouched(tmp_path):
    state = install(state_for(tmp_path))
    result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    result['report']['geometry_trials'] = [{'intermediate_report': deepcopy(result['report'])}]
    original = deepcopy(result)
    tasks = capacity_tasks(result)
    final = capacity_measurements(result['report'])
    assert 'geometry_trials' not in final and 'modules' not in final
    assert final['total_overflow_inches'] == result['report']['total_overflow_inches']
    for task, budget in zip(tasks['modules'], measured_body_budgets(result)['modules']):
        assert task['reference_words'] == budget['reference_words']
        assert task['available_body_height_inches'] == budget['available_body_height_inches']
        assert 'suggested_words' not in task
    tasks['modules'][0]['reference_words'] = -1
    assert result == original


def test_visible_prose_diff_ignores_ids_reasons_and_whitespace(tmp_path):
    before = install(state_for(tmp_path))['editorial_candidate']
    after = deepcopy(before)
    module = after['modules'][0]
    module['entries'][0]['item_id'] = 'renamed'
    module['entries'][0]['text'] = '  ' + module['entries'][0]['text'].replace(' ', '  ') + '\n'
    after['narrative_flow'] = 'Claimed compression.'
    assert not any(row['prose_changed'] for row in prose_changes(before, after))
    module['entries'].pop()
    assert prose_changes(before, after)[0]['prose_changed']


@pytest.mark.parametrize('reference,available,fixed', [(None, 1, 0), (-1, 1, 0), (0, 1, 0), (10, -1, 0), (10, 1, 2)])
def test_impossible_body_budget_does_not_demand_empty_or_text_only_solution(monkeypatch, reference, available, fixed):
    import src.layout.editorial_body_budget as budgets
    monkeypatch.setattr(budgets, 'measured_body_budgets', lambda _: {'modules': [{
        'module_id': 'm', 'current_words': 100, 'reference_words': reference,
        'available_body_height_inches': available, 'fixed_content_overflow_inches': fixed}]})
    task = capacity_tasks({'report': report(2)})['modules'][0]
    assert task['action'] == 'compress'
    assert 'legal geometry coordination belongs to the program' in task['rewrite_instruction']
    assert 'Do not return empty prose' in task['rewrite_instruction']
    assert '0-0 words' not in task['rewrite_instruction']
    assert 'Include this module with its complete body candidate' in task['rewrite_instruction']


def test_prose_diff_ignores_markers_and_bold_but_preserves_label_words(tmp_path):
    before = install(state_for(tmp_path))['editorial_candidate']
    after = deepcopy(before)
    entry = after['modules'][0]['entries'][0]
    entry['text'] = entry['text'].replace('• ', '1) ').replace('**', '')
    assert not prose_changes(before, after)[0]['prose_changed']
    entry['text'] = entry['text'].replace('Core mechanism:', 'Different mechanism:')
    assert prose_changes(before, after)[0]['prose_changed']


def report(usage):
    return {'passed': usage <= 1, 'all_modules_90_percent': usage >= .9,
            'total_overflow_inches': max(0, usage - 1) * 10,
            'total_underfill_inches': max(0, .9 - usage) * 10,
            'modules': [{'module_id': 'm', 'utilization': usage,
                         'overage_inches': max(0, usage - 1) * 10,
                         'missing_height_inches': max(0, .9 - usage) * 10}]}


@pytest.mark.parametrize('before,after,changed,outcome', [
    (2, 2, False, 'rewrite_not_executed'),
    (2, 2.1, True, 'rewrite_did_not_reduce_overflow'),
    (2, 1.1, True, 'improved_overflow_remaining'),
    (2, .95, True, 'target_met'),
    (2, .7, True, 'underfill_remaining'),
    (.6, .6, False, 'rewrite_not_executed'),
    (.6, .5, True, 'rewrite_did_not_reduce_underfill'),
    (.6, .8, True, 'improved_underfill_remaining'),
    (.6, 1.1, True, 'introduced_overflow'),
    (.95, .95, False, 'target_met'),
    (.95, 1.1, True, 'introduced_overflow'),
])
def test_result_distinguishes_real_rewrite_from_measured_success(before, after, changed, outcome):
    history = [{'phase': 'capacity', 'to': 'edited', 'reason': 'Everything fits perfectly!',
                'prose_changes': [{'module_id': 'm', 'prose_changed': changed,
                                   'words_before': 100, 'words_after': 80 if changed else 100}],
                'measurements_before': capacity_guidance(report(before))}]
    record_capacity_result(history, {'candidate_id': 'edited'}, report(after))
    result = history[0]['capacity_result']
    assert result['modules'][0]['outcome'] == outcome
    assert result['modules'][0]['prose_changed'] is changed
    assert result['science_verified'] is False
    assert (result['status'] == 'layout_defects_remain') == (after > 1)


def test_final_cpu_height_transfer_is_not_reported_as_prose_compression():
    history = [{'phase': 'capacity', 'to': 'edited',
                'prose_changes': [{'module_id': 'm', 'prose_changed': False,
                                   'words_before': 100, 'words_after': 100}],
                'measurements_before': capacity_guidance(report(2))},
               {'phase': 'height_allocation', 'from': 'edited', 'to': 'coordinated'}]
    record_capacity_result(history, {'candidate_id': 'coordinated'}, report(.95))
    result = history[0]['capacity_result']
    assert result['candidate_id'] == 'coordinated'
    assert result['modules'][0]['outcome'] == 'target_met'
    assert not result['modules'][0]['prose_changed']
    assert 'capacity_result' not in history[1]


def test_no_capacity_request_has_no_invented_result():
    history = []
    record_capacity_result(history, {'candidate_id': 'initial'}, report(.95))
    assert history == []


@pytest.mark.parametrize('fixed_excess,expected', [
    (-.01, 0.0),
    (0.0, 0.0),
    (3.552713678800501e-15, 0.0),
    (nextafter(1e-7, 0), 0.0),
    (1e-7, 0.0),
    (nextafter(1e-7, float('inf')), nextafter(1e-7, float('inf'))),
    (1e-5, 1e-5),
    (.25, .25),
])
def test_fixed_content_tolerance_reaches_model_task_without_hiding_body_overflow(fixed_excess, expected):
    # A frame ending at zero makes the tolerance boundary exactly representable.
    # Prose genuinely overflows regardless of the fixed-content boundary case.
    result = {'report': report(2), 'layout': [
        {'type': 'section_container', 'section_id': 'm',
         'module_frame': {'y': -4, 'height': 4}},
        {'type': 'visual', 'section_id': 'm',
         'y': 0 if fixed_excess > 0 else fixed_excess - 1,
         'height': fixed_excess if fixed_excess > 0 else 1},
        {'type': 'text', 'section_id': 'm', 'y': -3,
         'height': 6, 'width': 10, 'font_size': 44},
    ]}
    result['report']['modules'][0].update(current_words=100, body_layout='image_left_text_right')
    original = deepcopy(result)
    budget = measured_body_budgets(result)['modules'][0]
    task = capacity_tasks(result)['modules'][0]
    assert budget['fixed_content_overflow_inches'] == expected
    assert task['fixed_content_overflow_inches'] == expected
    assert task['body_overflow_inches'] == 3
    assert task['available_body_height_inches'] == 3
    assert task['reference_words'] == 45
    assert task['action'] == 'compress'
    if expected == 0:
        assert '43-47 words TOTAL' in task['rewrite_instruction']
        assert 'legal geometry coordination belongs to the program' not in task['rewrite_instruction']
    else:
        assert 'legal geometry coordination belongs to the program' in task['rewrite_instruction']
    assert result == original


def test_ec17_touching_image_stack_gets_197_to_126_word_compression():
    # Saved ec17 MNIST geometry; do not depend on local historical run files.
    result = {'report': report(1.3555244903881918), 'layout': [
        {'type': 'section_container', 'section_id': 'm',
         'module_frame': {'y': 14.508200000000002, 'height': 10.8732}},
        {'type': 'section_title', 'section_id': 'm',
         'y': 14.508200000000002, 'height': 1.038888888888889},
        {'type': 'visual', 'section_id': 'm',
         'y': 15.847088888888893, 'height': 4.68591014805048},
        {'type': 'visual', 'section_id': 'm',
         'y': 20.832999036939373, 'height': 4.548400963060632},
        {'type': 'text', 'section_id': 'm', 'y': 15.847088888888893,
         'height': 13.399999999999999, 'width': 35.9339255387947, 'font_size': 44},
    ]}
    result['report']['modules'][0].update(current_words=197, body_layout='image_left_text_right')
    original = deepcopy(result)
    task = capacity_tasks(result)['modules'][0]
    assert task['fixed_content_overflow_inches'] == 0
    assert task['reference_words'] == 126
    assert task['body_overflow_inches'] == pytest.approx(3.8656888888888883)
    assert task['action'] == 'compress'
    assert 'current 197-word body' in task['rewrite_instruction']
    assert '120-132 words TOTAL' in task['rewrite_instruction']
    assert 'legal geometry coordination belongs to the program' not in task['rewrite_instruction']
    assert result == original


@pytest.mark.parametrize('usage,action', [(2, 'compress'), (.5, 'expand')])
@pytest.mark.parametrize('reference,lower,upper', [
    (1, 1, 1), (19, 19, 19), (20, 19, 21), (21, 20, 22),
    (103, 98, 108), (126, 120, 132), (191, 182, 200),
])
def test_capacity_word_interval_is_rounded_inward_without_changing_task(
        monkeypatch, usage, action, reference, lower, upper):
    import src.layout.editorial_body_budget as budgets
    row = {'module_id': 'm', 'current_words': 103, 'reference_words': reference,
           'available_body_height_inches': 10, 'fixed_content_overflow_inches': 0}
    original = deepcopy(row)
    monkeypatch.setattr(budgets, 'measured_body_budgets', lambda _: {'modules': [row]})
    task = capacity_tasks({'report': report(usage)})['modules'][0]
    assert task['action'] == action and task['requires_prose_rewrite']
    assert task['reference_words'] == reference and task['current_words'] == 103
    assert f'{lower}-{upper} words TOTAL' in task['rewrite_instruction']
    assert task['available_body_height_inches'] == 10
    assert row == original
    if action == 'compress':
        assert 'strictly fewer than 103 words' in task['rewrite_instruction']
    # At reference=current=103, expansion has room above the former 103-word cap.
    if action == 'expand' and reference == 103:
        assert upper > task['current_words']


@pytest.mark.parametrize('reference', [None, 0, -1])
def test_expansion_without_reliable_reference_does_not_invent_word_range(monkeypatch, reference):
    import src.layout.editorial_body_budget as budgets
    monkeypatch.setattr(budgets, 'measured_body_budgets', lambda _: {'modules': [{
        'module_id': 'm', 'current_words': 10, 'reference_words': reference,
        'available_body_height_inches': 10, 'fixed_content_overflow_inches': 0}]})
    task = capacity_tasks({'report': report(.5)})['modules'][0]
    assert task['action'] == 'expand'
    instruction = task['rewrite_instruction']
    assert 'No reliable positive reference_words allowance' in instruction
    assert 'COMPLETE expanded entries' in instruction
    assert 'None' not in instruction and '0-0 words' not in instruction
    assert 'words TOTAL' not in instruction
    assert task['reference_words'] is reference
