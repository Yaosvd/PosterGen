"""Core problem/method functions survive supporting settings and shared failures."""

from copy import deepcopy

import pytest

from src.layout.editorial import prepare_board, sections
from src.layout.families import FAMILIES, LayoutFamily
from src.layout.family_contract import FamilyContract
from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError
from src.layout.presentation_policy import (
    PRESENTATION_POLICY_VERSION, auxiliary_assessment, is_auxiliary, prepare_structure,
)
from src.workflow.loop_progress import format_event
from test_layout_exploration import _MeasuredAgent
from test_presentation_policy import study
from test_generation_failure import make_loop, read
from test_campaign_resume import _state, _render_candidate, _AlwaysAcceptCritic


def task_board(setup_count=5):
    state, board = study()
    task = sections(board)[0]
    ids = ['q' + str(i) for i in range(8)]
    texts = ['The task discovers locations with a target attribute.',
             'Each location has an initially unknown binary target label.',
             'The objective is to discover targets within a resource budget.']
    texts.extend('Supported task constraint ' + str(i) + '.' for i in range(5))
    kinds = ['definition', 'definition', 'goal'] + ['setup'] * 5
    if setup_count == 4:
        kinds[3] = 'definition'
    elif setup_count == 6:
        kinds[1] = 'setup'
    task.update(claim_ids=ids, text_content=texts, core_claim_ids=ids[:3])
    state['verified_claims']['claims'] = [c for c in state['verified_claims']['claims'] if c['section_id'] != 'p'] + [
        {'claim_id': cid, 'section_id': 'p', 'text': text, 'evidence_ids': [cid + 'e']}
        for cid, text in zip(ids, texts)]
    state['narrative_plan']['sections'][0].update(narrative_role='insight', evidence_ids=[c + 'e' for c in ids])
    board = prepare_board(board, state, [{'section_id': 'p', 'module_purpose': 'primary',
        'claim_layout': [{'claim_id': cid, 'kind': kind} for cid, kind in zip(ids, kinds)]}])
    return state, board


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f: f.family_id)
@pytest.mark.parametrize('setup_count', [4, 5, 6])
def test_core_problem_definition_survives_setup_ratio_for_all_families(family, setup_count):
    state, board = task_board(setup_count)
    original = deepcopy((state, board))
    result, report = prepare_structure(board, state, family)
    task = next(s for s in sections(result) if s['section_id'] == 'p')
    assert task['claim_ids'] == sections(board)[0]['claim_ids']
    assert task['text_content'] == sections(board)[0]['text_content']
    assert not report['unresolved_section_ids']
    assert report['classifications']['p']['reason'] == 'source_supported_independent_core'
    assert report['merges'] == [{'section_id': 'd', 'into_section_id': 'm'}]
    assert (state, board) == original


def test_future_family_inherits_problem_function_protection():
    family = LayoutFamily('future', 'Future', 'Future', FAMILIES[0].zones, ('general',),
                          contract=FamilyContract(allow_module_grouping=True, reading='columns'))
    state, board = task_board()
    assert not prepare_structure(board, state, family)[1]['unresolved_section_ids']


def test_core_method_is_not_erased_by_a_majority_of_settings():
    state, board = task_board()
    state['narrative_plan']['sections'][0]['narrative_role'] = 'method'
    task = sections(board)[0]
    task['editorial']['items'][0]['kind'] = 'method'
    assert not is_auxiliary(task, state)


def test_primary_label_and_foreign_core_ids_do_not_exempt_routine_data():
    state, board = study()
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    data['editorial']['module_purpose'] = 'primary'
    data['core_claim_ids'] = ['p1', 'm1', 'd1']
    assert is_auxiliary(data, state)
    result, report = prepare_structure(board, state, FAMILIES[0])
    assert report['merges'] == [{'section_id': 'd', 'into_section_id': 'm'}]
    assert 'd' not in {s['section_id'] for s in sections(result)}


def test_a_complete_task_definition_survives_a_wrong_supporting_purpose_hint():
    state, board = task_board()
    sections(board)[0]['editorial']['module_purpose'] = 'supporting'
    assert not is_auxiliary(sections(board)[0], state)


def test_same_root_variants_keep_original_source_function_and_cannot_borrow_an_owner():
    state, board = task_board()
    task = sections(board)[0]
    state['verified_content_bank'] = {'claims': [{'claim_id': 'v', 'root_claim_id': 'q0',
        'section_id': 'd', 'text': task['text_content'][0], 'verified': True}]}
    task['claim_ids'][0] = 'v'
    refreshed = prepare_board(board, state)
    assert not is_auxiliary(sections(refreshed)[0], state)


def test_old_auxiliary_stamp_is_recomputed_but_strict_locks_remain_exact():
    state, board = task_board()
    sections(board)[0]['presentation'] = {'version': 'paper_presentation_v2', 'original_auxiliary': True}
    result, report = prepare_structure(board, state, FAMILIES[0])
    assert not report['unresolved_section_ids']
    assert not sections(result)[0]['presentation']['original_auxiliary']
    assert sections(result)[0]['presentation']['version'] == PRESENTATION_POLICY_VERSION
    state['improve_safe_fallback'] = True
    assert prepare_structure(board, state, FAMILIES[0])[0] == board


@pytest.mark.parametrize('constraint', ['none', 'pinned', 'grouping_disabled'])
def test_only_pregeometry_unrestricted_ownership_failure_has_shared_scope(monkeypatch, constraint):
    import src.layout.feasibility as solver
    state, board = study()
    # Genuine unresolved source, not a reason to silently guess a method owner.
    state['narrative_plan']['sections'][2]['narrative_role'] = 'supporting'
    family = FAMILIES[0]
    if constraint == 'pinned':
        state['layout_revision_constraints'] = {'section_to_zone': {'d': 'left'}}
    elif constraint == 'grouping_disabled':
        family = LayoutFamily('closed', 'Closed', 'Closed', FAMILIES[0].zones, ('general',),
                              contract=FamilyContract(allow_module_grouping=False))
        original = solver.LayoutFamilyRegistry
        monkeypatch.setattr(solver, 'LayoutFamilyRegistry', lambda: original((FAMILIES[0], family)))
    monkeypatch.setattr(solver, 'generate_zone_variants', lambda *a, **k: pytest.fail('No geometry should be searched'))
    with pytest.raises(LayoutFeasibilityError) as caught:
        fit_family_layout(_MeasuredAgent(), board, state, family.family_id)
    report = caught.value.report
    assert report['trial_count'] == 0 and report['reason_code'] == 'PRESENTATION_STRUCTURE_UNRESOLVED'
    assert report['failure_scope'] == ('shared_content' if constraint == 'none' else 'family_constraints')


def fail_structure(state, *, scope='shared_content', code='PRESENTATION_STRUCTURE_UNRESOLVED', trials=0):
    state.update(layout_preflight_failed=True,
        layout_feasibility_report={'status': 'infeasible', 'reason_code': code,
            'failure_stage': 'structure', 'failure_scope': scope, 'trial_count': trials,
            'presentation_preparation': {'unresolved_section_ids': ['d']}},
        layout_preflight_report={'passed': False, 'status': 'not_run', 'issues': []})
    state['errors'].append('Supporting modules require a compatible display owner')
    return state


@pytest.mark.parametrize('stop', [False, True])
def test_shared_failure_stops_once_without_poisoning_families_or_spending_budget(tmp_path, stop):
    calls = []
    def node(state):
        calls.append(state['iteration_context']['layout_family'])
        if stop:
            loop.control.request_stop()
        return fail_structure(state)
    def no_critic(_):
        pytest.fail('Unresolved content cannot reach Critic')
    loop = make_loop(tmp_path, node, no_critic, batch_mode='explore')
    result = loop.run(_state(tmp_path / 'run'), foundation_ready=True)
    summary = result['loop_state']
    assert len(calls) == 1
    assert summary['status'] == ('PAUSED' if stop else 'FAILED_REQUIRES_USER')
    if not stop:
        assert summary['stop_reason'] == 'shared_presentation_structure_unresolved'
    assert summary['batch']['completed_iterations'] == 0
    assert summary['accepted_count'] == summary['rejected_count'] == summary['template_count'] == 0
    assert not summary['portfolio_state']['lineages']
    root = loop.storage.root / 'campaigns' / summary['campaign_id']
    statuses = list(root.glob('iterations/*/attempts/*/status.json'))
    assert len(statuses) == 1
    assert read(statuses[0])['reason'] == 'shared_presentation_structure_unresolved'
    assert not list(root.glob('iterations/*/COMPLETED.json'))
    assert not list(root.glob('iterations/*/attempts/*/attempt_failure_report.json'))
    assert not list(root.glob('iterations/*/attempts/*/model_repair_budget.json'))
    selection = read(statuses[0].parent / 'family_selection_report.json')
    assert not selection['excluded_families']
    assert not (loop.storage.root / 'design_memory/rejection_memory.jsonl').exists()


@pytest.mark.parametrize('scope,code,trials', [
    ('family_constraints', 'PRESENTATION_STRUCTURE_UNRESOLVED', 0),
    ('shared_content', 'READING_ORDER_UNRESOLVED', 0),
    ('shared_content', 'PRESENTATION_STRUCTURE_UNRESOLVED', 1)])
def test_family_or_reading_or_exact_failure_still_retries_normally(tmp_path, scope, code, trials):
    calls = []
    def node(state):
        calls.append(state['iteration_context']['layout_family'])
        if len(calls) == 1:
            return fail_structure(state, scope=scope, code=code, trials=trials)
        state['layout_preflight_failed'] = False
        return _render_candidate(state)
    loop = make_loop(tmp_path, node, _AlwaysAcceptCritic(), batch_mode='explore')
    loop.batch_iterations = 1
    result = loop.run(_state(tmp_path / 'run'), foundation_ready=True)
    assert result['loop_state']['status'] == 'COMPLETED'
    assert len(calls) == 2 and calls[0] != calls[1]
    assert result['loop_state']['batch']['completed_iterations'] == 1


def test_shared_structure_terminal_event_explains_scope_and_budget():
    text = format_event({'type': 'shared_structure_failed', 'iteration': 12, 'unresolved_section_ids': ['d']})
    assert 'Shared content structure' in text and 'no family excluded' in text
    assert 'Batch budget not consumed' in text
