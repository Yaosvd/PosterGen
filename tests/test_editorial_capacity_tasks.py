"""Capacity input de-duplication and honest one-round outcome diagnostics."""
from copy import deepcopy

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
    module['entries'][1]['parent_item_id'] = 'renamed'
    module['entries'][0]['text'] = '  ' + module['entries'][0]['text'].replace(' ', '  ') + '\n'
    after['narrative_flow'] = 'Claimed compression.'
    assert not any(row['prose_changed'] for row in prose_changes(before, after))
    module['entries'].pop()
    assert prose_changes(before, after)[0]['prose_changed']


@pytest.mark.parametrize('reference,available,fixed', [(0, 1, 0), (10, -1, 0), (10, 1, 2)])
def test_impossible_body_budget_does_not_demand_empty_or_text_only_solution(monkeypatch, reference, available, fixed):
    import src.layout.editorial_body_budget as budgets
    monkeypatch.setattr(budgets, 'measured_body_budgets', lambda _: {'modules': [{
        'module_id': 'm', 'current_words': 100, 'reference_words': reference,
        'available_body_height_inches': available, 'fixed_content_overflow_inches': fixed}]})
    task = capacity_tasks({'report': report(2)})['modules'][0]
    assert task['action'] == 'compress'
    assert 'Coordinate legal space' in task['rewrite_instruction']
    assert 'Do not return empty prose' in task['rewrite_instruction']
    assert 'about 0 words' not in task['rewrite_instruction']


def test_prose_diff_uses_rendered_label_visibility(tmp_path):
    before = install(state_for(tmp_path))['editorial_candidate']
    before['modules'][0]['presentation_style'] = 'plain'
    after = deepcopy(before)
    after['modules'][0]['entries'][0]['display_label'] = 'Invisible label'
    assert not prose_changes(before, after)[0]['prose_changed']
    before['modules'][0]['presentation_style'] = 'topics'
    after['modules'][0]['presentation_style'] = 'topics'
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
