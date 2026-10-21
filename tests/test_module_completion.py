"""Module completion preserves scientific ownership, space and finite budgets."""

from copy import deepcopy

import pytest

from src.agents.content_optimizer import GroundedContentOptimizer
from src.layout.design_content import ContentPriorities
from src.layout.families import FAMILIES
from src.layout.feasibility import LayoutFeasibilityError
from src.layout.module_repair import complete_modules, content_preserved, repair_targets, space_preserved
from utils.module_content import module_context, existing_module_candidates
import src.layout.module_repair as module


def fixture():
    sections, claims, evidence = [], [], []
    for i in range(3):
        sid = f'm{i}'
        for j in range(2):
            cid = f'c{i}{j}'
            claims.append({'claim_id': cid, 'section_id': f'plan{i}', 'verified': True,
                           'text': f'Independent supported detail {i} {j}.', 'evidence_ids': [cid + 'e']})
            evidence.append({'evidence_id': cid + 'e', 'source_excerpt': f'Detail {i} {j}',
                             'source': {'section_id': f'paper{i}'}})
        sections.append({'section_id': sid, 'section_title': f'Module {i}',
                         'claim_ids': [f'c{i}0'], 'curated_claim_roots': [f'c{i}0', f'c{i}1'],
                         'text_content': [claims[-2]['text']], 'visual_assets': []})
    board = {'spatial_content_plan': {'sections': sections}}
    state = {'story_board': deepcopy(board), 'generation_route': 'optimization_family',
             'verified_claims': {'claims': claims}, 'evidence_bank': {'items': evidence},
             'verified_content_bank': {'claims': []}, 'supplemental_evidence_bank': {'items': []},
             'iteration_context': {'generation_purpose': 'explore', 'layout_family': 'test', 'attempt_id': 'a'},
             'content_selection': {}, 'errors': []}
    spec = {'zones': [{'zone_id': 'z', 'section_ids': ['m0', 'm1', 'm2']}],
            'reading_order': ['m0', 'm1', 'm2']}
    report = report_for(state, board)
    return state, (board, spec, report)


def report_for(state, board):
    return {'status': 'feasible', 'zone_utilization': {'z': .96}, 'exact_bottom_gaps': {'z': .1},
            'worst_zone_utilization': .96,
            'composition_whitespace': {'unallocated_body_fraction': .03, 'largest_empty_rectangle_fraction': .04},
            'content_quality_hints': ContentPriorities(state, board['spatial_content_plan']['sections']).summary(board['spatial_content_plan']['sections'])}


def audit():
    return {'status': 'skipped', 'rounds_attempted': 0, 'rounds': [], 'skip_reason': None}


def test_regrouped_module_recovers_source_without_another_board():
    state, current = fixture()
    state['story_board'] = {'spatial_content_plan': {'sections': [{'section_id': 'foreign'}]}}
    context = module_context(state, current[0], 'm0')
    assert context['source_section_ids'] == ['paper0']
    assert context['evidence_ids'] == ['c00e', 'c01e']
    assert [c['claim_id'] for c in existing_module_candidates(state, current[0], 'm0')] == ['c01']
    assert module_context(state, current[0], 'foreign')['status'] == 'missing_module'


def test_explicit_exclusions_and_visible_root_variants_are_not_restored():
    state, current = fixture()
    state['content_recovery_policy'] = {'excluded_claim_roots': [['m0', 'c01']]}
    assert not existing_module_candidates(state, current[0], 'm0')
    assert 'c01e' not in module_context(state, current[0], 'm0')['evidence_ids']
    state['content_recovery_policy'] = {}
    state['verified_content_bank']['claims'] = [{'claim_id': 'v', 'root_claim_id': 'c01',
        'verified': True, 'text': 'Short verified variant', 'evidence_ids': ['c01e']}]
    current[0]['spatial_content_plan']['sections'][1]['claim_ids'].append('v')
    assert not existing_module_candidates(state, current[0], 'm0')


def test_consecutive_short_modules_are_all_targets_but_single_visual_module_is_not():
    state, (board, spec, report) = fixture()
    report['content_quality_hints'] = {}
    targets = repair_targets(board, {**report, 'selected_layout_spec': spec}, {})
    assert [x['section_id'] for x in targets] == ['m0', 'm1', 'm2']
    for s in board['spatial_content_plan']['sections']:
        s['visual_assets'] = [{'visual_id': 'figure_1'}]
    assert not repair_targets(board, {**report, 'selected_layout_spec': spec}, {})


@pytest.mark.parametrize('family', [f.family_id for f in FAMILIES] + ['future_family'])
def test_same_zone_modules_restore_without_height_gain_or_model_round(monkeypatch, family):
    state, current = fixture()
    before = deepcopy(state['verified_claims'])
    def fit(_agent, board, trial, family_id, *, fixed_zones, **_):
        assert family_id == family
        assert fixed_zones == current[1]['zones']
        assert trial['layout_revision_constraints']['section_to_zone'] == {'m0': 'z', 'm1': 'z', 'm2': 'z'}
        return deepcopy(board), deepcopy(current[1]), report_for(trial, board)
    monkeypatch.setattr(module, 'fit_family_layout', fit)
    result, log = complete_modules(object(), state, current, family, {}, audit(), 0)
    assert all(len(s['claim_ids']) == 2 for s in result[0]['spatial_content_plan']['sections'])
    assert log['status'] == 'applied' and log['rounds_attempted'] == 0
    assert not log['unresolved_section_ids']
    assert state['verified_claims'] == before
    assert result[2]['zone_utilization'] == current[2]['zone_utilization']
    assert state['_quality_repair_baseline']['result'] == current


@pytest.mark.parametrize('failure', ['overflow', 'space', 'drop', 'move'])
def test_failed_trials_preserve_board_banks_and_baseline(monkeypatch, failure):
    state, current = fixture()
    original = deepcopy(state)
    def fit(_agent, board, trial, _family, **_):
        if failure == 'overflow':
            raise LayoutFeasibilityError('overflow', {})
        report = report_for(trial, board)
        if failure == 'space':
            report['composition_whitespace']['largest_empty_rectangle_fraction'] = .3
        elif failure == 'drop':
            board['spatial_content_plan']['sections'].pop()
        elif failure == 'move':
            board['spatial_content_plan']['sections'][1]['claim_ids'].extend(board['spatial_content_plan']['sections'][0]['claim_ids'])
            board['spatial_content_plan']['sections'][0]['claim_ids'] = []
        return board, current[1], report
    monkeypatch.setattr(module, 'fit_family_layout', fit)
    result, log = complete_modules(object(), state, current, 'test', {}, audit(), 0)
    assert result == current and state == original
    assert log['unresolved_section_ids'] == ['m0', 'm1', 'm2']
    if failure in {'drop', 'move'}:
        rejected = [a for a in log['module_attempts'] if a['status'] == 'content_or_ownership_regression']
        assert rejected and all(a['violations'] for a in rejected)


def test_space_checks_cumulative_and_each_zone_regression():
    before = {'zone_utilization': {'a': .96, 'b': .96}, 'exact_bottom_gaps': {'a': .1, 'b': .1}}
    first = deepcopy(before)
    first['zone_utilization']['a'] = .956
    second = deepcopy(first)
    second['zone_utilization']['a'] = .952
    assert space_preserved(before, first) and space_preserved(first, second)
    assert not space_preserved(before, second)
    first['exact_bottom_gaps']['b'] = .2
    assert not space_preserved(before, first)


def test_budget_queue_reaches_third_module_and_records_unresolved(monkeypatch):
    state, current = fixture()
    state.update(text_model=object(), tokens=object())
    for s in current[0]['spatial_content_plan']['sections']:
        s.pop('curated_claim_roots')
    # Remove recoverable originals so the queue needs model work.
    state['verified_claims']['claims'] = [c for c in state['verified_claims']['claims'] if c['claim_id'].endswith('0')]
    current = (current[0], current[1], report_for(state, current[0]))
    seen = []
    def fail(trial, *, actions_override, **_):
        seen.extend(actions_override)
        trial['content_revision'] = {'accepted_actions': [], 'rejected_actions': []}
        return trial
    monkeypatch.setattr(module, 'content_optimizer', fail)
    _, log = complete_modules(object(), state, current, 'test', {}, audit(), 2)
    assert [a['section_id'] for a in seen[:3]] == ['m0', 'm1', 'm2']
    assert len(seen) == 4 and log['rounds_attempted'] == 2
    assert seen[-1]['search_source'] is True
    assert log['unresolved_section_ids'] == ['m0', 'm1', 'm2']


def test_used_evidence_can_support_additional_verified_information(monkeypatch):
    state, current = fixture()
    optimizer = GroundedContentOptimizer()
    payloads = []
    def model(_state, _prompt, payload):
        payloads.append(payload)
        return {'candidates': [{'text': 'Another supported condition.', 'evidence_ids': ['c00e']}]}
    monkeypatch.setattr(optimizer, '_model_json', model)
    candidate, extra = optimizer._create_candidate(state, current[0],
        {'operation': 'add_claim_from_evidence', 'section_id': 'm0'},
        {c['claim_id']: c for c in state['verified_claims']['claims']}, {'items': []})
    assert candidate['evidence_ids'] == ['c00e'] and extra is None
    assert payloads[0]['current_section_claims']


def test_forced_source_search_works_even_when_existing_evidence_is_available(monkeypatch):
    state, current = fixture()
    optimizer = GroundedContentOptimizer()
    extra = {'evidence_id': 'source_new', 'source_excerpt': 'Source detail'}
    monkeypatch.setattr(optimizer, '_extract_supplemental_evidence', lambda *a: extra)
    monkeypatch.setattr(optimizer, '_model_json', lambda *a: {'candidates': [
        {'text': 'Source detail', 'evidence_ids': ['source_new']}]})
    candidate, found = optimizer._create_candidate(state, current[0],
        {'operation': 'add_claim_from_evidence', 'section_id': 'm0', 'search_source': True},
        {c['claim_id']: c for c in state['verified_claims']['claims']}, {'items': []})
    assert found == extra and candidate['evidence_ids'] == ['source_new']


def test_omitted_original_can_be_restored_as_verified_compact_variant(monkeypatch):
    state, current = fixture()
    state['output_dir'] = '/tmp/unused-module-test'
    optimizer = GroundedContentOptimizer()
    monkeypatch.setattr(optimizer, '_create_candidate', lambda *a: (
        {'claim_id': 'compact', 'section_id': 'm0', 'text': 'Detail.', 'evidence_ids': ['c01e']}, None))
    monkeypatch.setattr(optimizer, '_verify_candidate', lambda s, c, b: ({**c, 'verified': True}, {}))
    monkeypatch.setattr(optimizer, '_editorial_guard', lambda *a, **k: True)
    result = optimizer(state, board_override=current[0], actions_override=[{
        'operation': 'create_compact_variant', 'section_id': 'm0', 'claim_id': 'c01', 'restore_omitted': True}], save=False)
    assert result['story_board']['spatial_content_plan']['sections'][0]['claim_ids'] == ['c00', 'compact']
    assert result['verified_content_bank']['claims'][0]['root_claim_id'] == 'c01'
    assert content_preserved(current[0], result['story_board'], result)


@pytest.mark.parametrize('status', ['failed', 'partial', 'unavailable'])
def test_runner_rolls_back_completion_once_and_rechecks_final_pipeline(monkeypatch, status):
    from src.workflow.exploration_runner import PosterExplorationRunner
    import src.layout.module_recovery as recovery
    # Exercise the actual runner boundary without a model, renderer or Campaign.
    owner = object.__new__(PosterExplorationRunner)
    owner.runtime = {}
    owner.control = type('Control', (), {'force_stop_requested': False, 'stop_requested': False})()
    owner._progress = lambda *a, **k: None
    owner._record_timing = lambda *a, **k: None
    seen = []
    def layout_preflight_node(state):
        seen.append('preflight')
        return state
    def render_fit_audit_node(state):
        seen.append('render')
        state['render_fit_report'] = {'status': status if state.get('_quality_repair_baseline') else 'passed'}
        return state
    def rollback(state):
        seen.append('rollback')
        state.pop('_quality_repair_baseline')
        return True
    monkeypatch.setattr(recovery, 'rollback_completion', rollback)
    result = owner._run_nodes({'errors': [], '_quality_repair_baseline': {'attempt_id': 'a', 'result': ({}, {}, {})}},
                             [layout_preflight_node, render_fit_audit_node], stage='design')
    assert seen == ['preflight', 'render', 'rollback', 'preflight', 'render']
    assert result['render_fit_report']['status'] == 'passed'


def test_rollback_restores_banks_board_reports_and_candidate_identity(tmp_path, monkeypatch):
    from src.layout.module_recovery import rollback_completion
    from src.layout.module_repair import CONTENT_FIELDS
    from src.agents.layout_agent import LayoutAgent
    from src.agents.font_agent import FontAgent
    state, current = fixture()
    state['output_dir'] = str(tmp_path)
    saved = {k: deepcopy(state.get(k)) for k in CONTENT_FIELDS}
    state['_quality_repair_baseline'] = {'fields': saved, 'result': deepcopy(current), 'attempt_id': 'a'}
    state['verified_content_bank']['claims'] = [{'claim_id': 'uncommitted'}]
    state['errors'] = ['rendered overflow']
    state['layout_preflight_failed'] = True
    state['render_fit_report'] = {'status': 'failed', 'issues': [{'code': 'OVERFLOW'}]}
    state['current_candidate'] = {'candidate_id': 'same', 'candidate_dir': str(tmp_path), 'status': 'rendered'}
    state['capacity_repair_report'] = {'module_outcomes': [{'section_id': 'm0', 'status': 'resolved'}]}
    def compile(_self, s, mode):
        s['design_layout'] = [{'type': 'text', 'text': 'original'}]
        return s
    monkeypatch.setattr(LayoutAgent, '__call__', compile)
    monkeypatch.setattr(FontAgent, '_apply_styling', lambda _self, layout, *a: deepcopy(layout))
    result = rollback_completion(state)
    assert result and not state['errors'] and not state['verified_content_bank']['claims']
    assert state['optimized_story_board'] == current[0] and state['layout_spec'] == current[1]
    assert state['current_candidate']['candidate_id'] == 'same'
    assert state['current_candidate']['status'] != 'rendered'
    assert state['capacity_repair_report']['completion_rollback']['render_fit']['status'] == 'failed'
    assert state['capacity_repair_report']['unresolved_section_ids'] == ['m0']
    assert not rollback_completion(state)


@pytest.mark.parametrize('family', ['classic_three_column', 'four_column_modular'])
def test_real_solver_completion_keeps_exact_preflight_and_geometry(family):
    from test_layout_exploration import _MeasuredAgent, _board
    from test_family_design_policy import state_for
    from src.config.critic_config import load_critic_config
    from src.layout.feasibility import fit_family_layout
    board = _board()
    state = state_for(board)
    state['evidence_bank'] = {'items': [
        {'evidence_id': c['claim_id'] + 'e', 'source_excerpt': c['text']}
        for c in state['verified_claims']['claims']]}
    for section in board['spatial_content_plan']['sections']:
        section['curated_claim_roots'] = list(section['claim_ids'])
        section['claim_ids'] = section['claim_ids'][:1]
        section['text_content'] = section['text_content'][:1]
    state['story_board'] = board
    state['iteration_context']['layout_family'] = family
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    state['critic_config'] = config
    agent = _MeasuredAgent()
    baseline = fit_family_layout(agent, board, state, family, config=config)
    result, log = complete_modules(agent, state, baseline, family, config['capacity_repair'], audit(), 0)
    from src.layout.families import compile_layout
    from src.layout.feasibility import validate_compiled_layout
    layout = compile_layout(agent, result[0], state, result[1])
    assert validate_compiled_layout(layout, result[1], state, poster_margin=agent.poster_margin,
                                    title_height_fraction=agent.title_height_fraction)['passed']
    assert space_preserved(baseline[2], result[2])
    assert content_preserved(baseline[0], result[0], state)
    assert log['rounds_attempted'] == 0
    assert result[1]['family_id'] == family


def test_disabled_claim_and_scoped_evidence_are_not_bypassed():
    state, current = fixture()
    state['content_selection'] = {'disabled_claim_ids': ['c01']}
    assert not existing_module_candidates(state, current[0], 'm0')
    state['content_selection'] = {}
    assert not existing_module_candidates(state, current[0], 'm0', evidence_ids=['c00e'])
    assert existing_module_candidates(state, current[0], 'm0', evidence_ids=['c01e'])


def test_compact_restoration_cannot_duplicate_a_root_visible_in_another_module(monkeypatch):
    state, current = fixture()
    state['verified_content_bank']['claims'] = [{'claim_id': 'already_compact',
        'root_claim_id': 'c01', 'verified': True, 'text': 'Already visible.', 'evidence_ids': ['c01e']}]
    current[0]['spatial_content_plan']['sections'][1]['claim_ids'].append('already_compact')
    optimizer = GroundedContentOptimizer()
    monkeypatch.setattr(optimizer, '_create_candidate', lambda *a: pytest.fail('No model call for visible root'))
    result = optimizer(state, board_override=current[0], actions_override=[{
        'operation': 'create_compact_variant', 'section_id': 'm0', 'claim_id': 'c01', 'restore_omitted': True}], save=False)
    assert not result['content_revision']['accepted_actions']
    assert 'omitted original root' in result['content_revision']['rejected_actions'][0]['reason']
