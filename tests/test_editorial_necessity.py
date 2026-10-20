"""Necessity, conditional context and bounded selection review are shared."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from src.config.critic_config import load_critic_config
from src.layout.editorial import sections, prepare_board
from src.layout.editorial_selection import (
    sanitize_selection, selection_audit, required_roots, contexts_met,
)
from src.layout.selection_review import apply_review, review_selection
from src.layout.repair_budget import budget_usage, purpose_used, available_rounds
from src.layout.families import FAMILIES, LayoutFamily, LayoutFamilyRegistry
from src.layout.family_contract import FamilyContract
from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError
from src.layout.presentation_policy import prepare_structure, supporting_contexts_preserved
from test_layout_exploration import _board, _MeasuredAgent
from test_family_design_policy import state_for


def fixture(tmp_path=None, invalid=True):
    board = _board()
    for section in sections(board):
        section['visual_assets'] = []
        section['core_claim_ids'] = section['claim_ids'][:1]
    state = state_for(board)
    bank = {c['claim_id']: c for c in state['verified_claims']['claims']}
    board['editorial_selection'] = sanitize_selection({'items': [
        {'claim_id': c, 'disposition': 'required', 'reason': 'useful' if invalid and i else 'core'}
        for s in sections(board) for i, c in enumerate(s['claim_ids'])]}, bank)
    state.update(story_board=board, critic_config=load_critic_config(), text_model={'fake': True},
                 tokens=SimpleNamespace(add_text=lambda *_: None), errors=[])
    if tmp_path:
        directory = tmp_path / 'attempts' / 'one'
        directory.mkdir(parents=True)
        state['iteration_context'].update(attempt_diagnostics_dir=str(directory), attempt_id='one',
                                           layout_family=FAMILIES[0].family_id)
    return state, board


def decisions(board):
    return {'status': 'resolved', 'items': [
        {'claim_id': c, 'disposition': 'required' if i == 0 else 'optional',
         'reason': 'core' if i == 0 else 'secondary', 'retained_anchor_claim_ids': [s['claim_ids'][0]]}
        for s in sections(board) for i, c in enumerate(s['claim_ids'])]}


def test_useful_does_not_silently_become_optional_or_pass_admission():
    state, board = fixture()
    audit = selection_audit(board, state)
    assert not audit['passed']
    assert audit['required_root_count'] == 24
    with pytest.raises(LayoutFeasibilityError) as caught:
        fit_family_layout(_MeasuredAgent(), board, state, FAMILIES[0].family_id)
    assert caught.value.report['reason_code'] == 'EDITORIAL_SELECTION_UNRESOLVED'
    assert caught.value.report['failure_scope'] == 'shared_content'
    assert caught.value.report['trial_count'] == 0


def test_optional_dependencies_do_not_permanently_promote_their_context():
    claims = {c: {'claim_id': c} for c in ('main', 'extra', 'setting')}
    contract = sanitize_selection({'items': [{'claim_id': 'main', 'disposition': 'required', 'reason': 'core'}]},
        claims, visible=claims, dependencies=[('extra', 'setting')])
    assert next(i for i in contract['items'] if i['claim_id'] == 'setting')['disposition'] == 'optional'
    state = {'verified_claims': {'claims': list(claims.values())}}
    board = {'editorial_selection': contract, 'spatial_content_plan': {'sections': [{'claim_ids': ['main']}]}}
    assert contexts_met(board, state)
    board['spatial_content_plan']['sections'][0]['claim_ids'].append('extra')
    assert not contexts_met(board, state)
    board['spatial_content_plan']['sections'][0]['claim_ids'].append('setting')
    assert contexts_met(board, state)


def test_scoped_condition_tracks_selected_claim_and_verified_variants():
    claims = {c: {'claim_id': c} for c in ('main', 'extra', 'setting')}
    raw = {'items': [{'claim_id': 'main', 'disposition': 'required', 'reason': 'core'},
                     {'claim_id': 'setting', 'disposition': 'required', 'reason': 'condition',
                      'required_for_claim_ids': ['extra']}]}
    contract = sanitize_selection(raw, claims)
    state = {'verified_claims': {'claims': list(claims.values())}}
    board = {'editorial_selection': contract, 'spatial_content_plan': {'sections': [{'claim_ids': ['main']}]}}
    assert required_roots(board, state) == {'main'}
    assert contexts_met(board, state)
    board['spatial_content_plan']['sections'][0]['claim_ids'] += ['setting']
    assert not contexts_met(board, state)  # No orphan condition as filler.
    board['spatial_content_plan']['sections'][0]['claim_ids'] += ['extra']
    assert contexts_met(board, state)
    state['verified_content_bank'] = {'claims': [{'claim_id': 'cv', 'root_claim_id': 'setting', 'verified': True}]}
    board['spatial_content_plan']['sections'][0]['claim_ids'] = ['main', 'extra', 'cv']
    assert contexts_met(board, state)
    raw['items'].append({'claim_id': 'extra', 'disposition': 'required', 'reason': 'core'})
    board['editorial_selection'] = sanitize_selection(raw, claims)
    assert required_roots(board, state) == {'main', 'extra', 'setting'}


def test_genuinely_all_required_short_board_is_allowed_without_review():
    state, board = fixture(invalid=False)
    assert selection_audit(board, state)['passed']
    worker = SimpleNamespace(_model_json=lambda *_: pytest.fail('No review before measured failure'))
    result, audit = review_selection(state, board, FAMILIES[0].family_id, optimizer=worker)
    assert result == board and audit['status'] == 'not_needed'


@pytest.mark.parametrize('bad', ['foreign', 'duplicate', 'prose', 'no_anchor', 'bad_reason', 'all_optional', 'unresolved'])
def test_review_rejects_unsafe_metadata_and_never_mutates_science(bad):
    state, board = fixture()
    original = deepcopy((state['verified_claims'], board))
    raw = decisions(board)
    if bad == 'foreign': raw['items'][0]['claim_id'] = 'foreign'
    elif bad == 'duplicate': raw['items'][0]['claim_id'] = raw['items'][1]['claim_id']
    elif bad == 'prose': raw['items'] = [{'text': 'invented body'}]
    elif bad == 'no_anchor': raw['items'][1]['retained_anchor_claim_ids'] = []
    elif bad == 'bad_reason': raw['items'][0]['reason'] = ['core']
    elif bad == 'all_optional':
        for item in raw['items']: item.update(disposition='optional', reason='secondary')
    else: raw['status'] = 'unresolved'
    assert apply_review(board, state, raw)[0] is None
    assert (state['verified_claims'], board) == original


def test_planner_and_pinned_information_cannot_be_demoted():
    state, board = fixture()
    state['narrative_plan']['sections'][0]['required_evidence_ids'] = ['c0_1e']
    assert apply_review(board, state, decisions(board))[1] == 'hard_requirement_changed'
    state['narrative_plan']['sections'][0]['required_evidence_ids'] = []
    state['layout_revision_constraints'] = {'must_retain_claim_ids': ['c0_1']}
    assert apply_review(board, state, decisions(board))[1] == 'hard_requirement_changed'


def test_review_is_one_durable_capacity_charge_with_quality_reserve(tmp_path):
    state, board = fixture(tmp_path)
    original = deepcopy(board)
    calls = []
    worker = SimpleNamespace(_model_json=lambda st, prompt, payload: calls.append(payload) or decisions(board))
    reviewed, report = review_selection(state, board, FAMILIES[0].family_id, optimizer=worker)
    assert report['status'] == 'resolved' and len(calls) == 1
    assert board == original
    assert sorted((c, t) for s in sections(reviewed) for c, t in zip(s['claim_ids'], s['text_content'])) == sorted(
        (c, t) for s in sections(original) for c, t in zip(s['claim_ids'], s['text_content']))
    assert [v for s in sections(reviewed) for v in s['visual_assets']] == [
        v for s in sections(original) for v in s['visual_assets']]
    assert len(required_roots(reviewed, state)) == 6
    assert budget_usage(state['iteration_context']['attempt_diagnostics_dir']) == (1, 0)
    assert available_rounds(state, 'capacity', state['critic_config']['capacity_repair']) == 2
    assert available_rounds(state, 'quality', state['critic_config']['capacity_repair']) == 3
    # New attempt/process: durable ledger prevents another review, but does
    # not transfer the failed attempt's selection or prose into this board.
    directory = tmp_path / 'attempts' / 'two'; directory.mkdir()
    state['iteration_context'] = {'attempt_diagnostics_dir': str(directory), 'layout_family': FAMILIES[1].family_id}
    assert purpose_used(state, 'selection_review')
    _, report = review_selection(state, board, FAMILIES[1].family_id, optimizer=worker)
    assert report['status'] == 'unresolved' and len(calls) == 1
    assert board == original


@pytest.mark.parametrize('lock', ['validate', 'fallback', 'disabled', 'no_model'])
def test_locks_and_disabled_modes_never_rewrite_selection(lock):
    state, board = fixture()
    if lock == 'validate': state['iteration_context']['portfolio_mode'] = 'validate'
    elif lock == 'fallback': state['improve_safe_fallback'] = True
    elif lock == 'disabled': state['critic_config']['content_optimization']['enabled'] = False
    else: state['text_model'] = None
    worker = SimpleNamespace(_model_json=lambda *_: pytest.fail('Must not call a model'))
    assert review_selection(state, board, FAMILIES[0].family_id, optimizer=worker)[0] == board


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f: f.family_id)
def test_reviewed_selection_fits_all_families_without_science_changes(family):
    state, board = fixture()
    board = prepare_board(board, state)
    reviewed, reason = apply_review(board, state, decisions(board))
    assert reason == 'resolved'
    config = load_critic_config(); config['composition_refinement']['enabled'] = False
    fitted, _, report = fit_family_layout(_MeasuredAgent(), reviewed, state, family.family_id, config=config)
    assert report['status'] == 'feasible'
    assert required_roots(reviewed, state).issubset({c for s in sections(fitted) for c in s['claim_ids']})


def test_merged_support_requirements_are_recomputed_after_review():
    from test_presentation_policy import study
    state, board = study()
    claims = {c['claim_id']: c for c in state['verified_claims']['claims']}
    for section in state['narrative_plan']['sections']: section['required_evidence_ids'] = []
    board['editorial_selection'] = sanitize_selection({'items': [
        {'claim_id': c, 'disposition': 'required', 'reason': 'core'} for c in claims]}, claims)
    merged, _ = prepare_structure(board, state, FAMILIES[0])
    for item in merged['editorial_selection']['items']:
        if item['claim_id'] in ('d1', 'd2'): item.update(disposition='optional', reason='useful')
    updated, _ = prepare_structure(merged, state, FAMILIES[0])
    method = next(s for s in sections(updated) if s['section_id'] == 'm')
    method['claim_ids'] = [c for c in method['claim_ids'] if c not in ('d1', 'd2')]
    assert supporting_contexts_preserved(method, state)


def test_future_family_gets_same_necessity_guard(monkeypatch):
    family = LayoutFamily('future_necessity', 'Future', 'Future', FAMILIES[0].zones, ('general',),
                          contract=FamilyContract(reading='columns', allow_module_grouping=True))
    original = LayoutFamilyRegistry.__init__
    monkeypatch.setattr(LayoutFamilyRegistry, '__init__', lambda self, families=None:
                        original(self, (*FAMILIES, family) if families is None else families))
    state, board = fixture()
    with pytest.raises(LayoutFeasibilityError) as caught:
        fit_family_layout(_MeasuredAgent(), board, state, family.family_id)
    assert caught.value.report['reason_code'] == 'EDITORIAL_SELECTION_UNRESOLVED'


@pytest.mark.parametrize('stop', [False, True])
def test_unresolved_selection_stops_once_without_batch_or_rejection_accounting(tmp_path, stop):
    from test_generation_failure import make_loop
    from test_campaign_resume import _state
    calls = []
    def node(state):
        calls.append(state['iteration_context']['attempt_id'])
        if stop:
            loop.control.request_stop()
        state.update(layout_preflight_failed=True, errors=['selection unresolved'],
            layout_feasibility_report={'status': 'infeasible', 'failure_scope': 'shared_content',
                'reason_code': 'EDITORIAL_SELECTION_UNRESOLVED', 'failure_stage': 'selection', 'trial_count': 0})
        return state
    loop = make_loop(tmp_path, node, lambda _: pytest.fail('Must not reach Critic'), batch_mode='explore')
    result = loop.run(_state(tmp_path / 'run'), foundation_ready=True)['loop_state']
    assert len(calls) == 1
    assert result['status'] == ('PAUSED' if stop else 'FAILED_REQUIRES_USER')
    if not stop:
        assert result['stop_reason'] == 'shared_editorial_selection_unresolved'
    assert result['batch']['completed_iterations'] == 0
    assert result['accepted_count'] == result['rejected_count'] == result['template_count'] == 0
    root = loop.storage.root / 'campaigns' / result['campaign_id']
    assert not list(root.glob('iterations/*/COMPLETED.json'))
    assert not (loop.storage.root / 'design_memory/rejection_memory.jsonl').exists()


def test_selection_review_preserves_current_visual_contract(tmp_path):
    from test_critical_visuals import sample
    state, board = sample(tmp_path)
    claims = {c['claim_id']: c for c in state['verified_claims']['claims']}
    board['editorial_selection'] = sanitize_selection({'items': [
        {'claim_id': c, 'disposition': 'required', 'reason': 'core'} for c in claims]}, claims)
    board['visual_requirements'] = deepcopy(state['visual_requirements'])
    raw = {'status': 'resolved', 'items': deepcopy(board['editorial_selection']['items'])}
    reviewed, reason = apply_review(board, state, raw)
    assert reason == 'resolved'
    assert reviewed['visual_requirements'] == board['visual_requirements']
    assert [v for s in sections(reviewed) for v in s['visual_assets']] == [v for s in sections(board) for v in s['visual_assets']]


def test_planner_floor_cannot_be_made_conditional_by_curator():
    claims = {c: {'claim_id': c} for c in ('main', 'extra', 'condition')}
    raw = {'items': [{'claim_id': 'condition', 'disposition': 'required', 'reason': 'condition',
                      'required_for_claim_ids': ['extra']}]}
    contract = sanitize_selection(raw, claims, required={'condition'})
    board = {'editorial_selection': contract, 'spatial_content_plan': {'sections': [{'claim_ids': ['main']}]}}
    state = {'verified_claims': {'claims': list(claims.values())}}
    assert 'condition' in required_roots(board, state)
    assert not next(i for i in contract['items'] if i['claim_id'] == 'condition').get('required_for_claim_ids')


def test_measured_review_keeps_normal_feasible_quality_followup(monkeypatch, tmp_path):
    import src.agents.layout_with_balancer as module
    from src.agents.layout_agent import LayoutAgent
    from src.layout.families import compile_layout
    state, board = fixture(invalid=False)
    state['output_dir'] = str(tmp_path / 'output')
    state['critic_config']['composition_refinement']['enabled'] = False
    state['critic_config']['capacity_repair']['enabled'] = False
    # Fit a real guarded result first; inject only the initial capacity miss
    # and review response to exercise orchestration without a model call.
    result = fit_family_layout(_MeasuredAgent(), board, state, FAMILIES[0].family_id, config=state['critic_config'])
    count = []
    def fit(*args, **kwargs):
        count.append(1)
        if len(count) == 1:
            raise LayoutFeasibilityError('height pressure', {'status': 'infeasible', 'reason_code': 'NO_FAST_FEASIBLE_VARIANT'})
        return result
    reviewed, _ = apply_review(prepare_board(board, state), state, decisions(board))
    def review(st, original, family, **kwargs):
        return (reviewed, {'status': 'resolved'}) if kwargs.get('measured_failure') else (original, {'status': 'not_needed'})
    followups = []
    def repair(agent, st, source, family, **kwargs):
        followups.append(kwargs)
        return kwargs['initial_result'], {'status': 'not_needed', 'rounds_attempted': 0}
    monkeypatch.setattr(module, 'fit_family_layout', fit)
    monkeypatch.setattr('src.layout.selection_review.review_selection', review)
    monkeypatch.setattr(module, '_audited_capacity_repair', repair)
    monkeypatch.setattr(module, 'needs_feasible_repair', lambda *_: True)
    monkeypatch.setattr('src.layout.editorial.polish_wording', lambda a, st, current, f: current)
    class Compiler(_MeasuredAgent):
        def __call__(self, st, mode):
            st['design_layout'] = compile_layout(self, st['optimized_story_board'], st, st['layout_spec'])
            return st
    agent = module.LayoutWithBalancerAgent()
    agent.layout_agent = Compiler()
    agent._run_family_constraint_engine(state, FAMILIES[0].family_id)
    assert len(count) == 2 and len(followups) == 1
    assert followups[0]['previous_report']['budget_phase'] == 'capacity'
    assert state['layout_feasibility_report']['compiled_preflight']['passed']


def test_same_root_bank_reserve_cannot_erase_required_or_omitted_information():
    from src.layout.editorial_selection import root_allowed
    claims = {'main': {'claim_id': 'main'}, 'variant': {'claim_id': 'variant', 'root_claim_id': 'main'}}
    state = {'verified_claims': {'claims': list(claims.values())}}
    board = {'editorial_selection': sanitize_selection({'items': [
        {'claim_id': 'main', 'disposition': 'required', 'reason': 'core'}]}, claims)}
    assert required_roots(board, state) == {'main'}
    board['editorial_selection'] = sanitize_selection({'items': [
        {'claim_id': 'main', 'disposition': 'omit', 'reason': 'redundant'}]}, claims)
    assert not root_allowed(board, state, claims['variant'])


def test_review_of_visible_variant_updates_root_metadata_without_changing_bank():
    state, board = fixture()
    source = deepcopy(state['verified_claims']['claims'][1])
    source.update(claim_id='short_variant', root_claim_id='c0_1', verified=True)
    state['verified_content_bank'] = {'claims': [source]}
    board['spatial_content_plan']['sections'][0]['claim_ids'][1] = 'short_variant'
    original_bank = deepcopy(state['verified_content_bank'])
    reviewed, reason = apply_review(board, state, decisions(board))
    assert reason == 'resolved'
    assert 'c0_1' not in required_roots(reviewed, state)
    assert 'c0_0' in required_roots(reviewed, state)
    assert state['verified_content_bank'] == original_bank


def test_locked_legacy_vocabulary_keeps_required_information_gate():
    from src.layout.presentation_policy import structure_audit
    state, board = fixture()
    board = prepare_board(board, state)
    board['editorial_selection']['version'] = 'editorial_selection_v1'
    state['iteration_context']['portfolio_mode'] = 'validate'
    audit = structure_audit(board, {}, state, FAMILIES[0].contract)
    assert 'SELECTION_REQUIRED_REASON_UNSUPPORTED' not in {i['code'] for i in audit['issues']}
    sections(board)[0]['claim_ids'].pop()
    sections(board)[0]['text_content'].pop()
    audit = structure_audit(board, {}, state, FAMILIES[0].contract)
    assert 'REQUIRED_INFORMATION_LOST' in {i['code'] for i in audit['issues']}


@pytest.mark.parametrize('prior', ['required', 'omit'])
def test_visible_variant_cannot_bypass_root_anchor_or_omission(prior):
    state, board = fixture()
    source = deepcopy(state['verified_claims']['claims'][1])
    source.update(claim_id='variant', root_claim_id='c0_1', verified=True)
    state['verified_content_bank'] = {'claims': [source]}
    sections(board)[0]['claim_ids'][1] = 'variant'
    old = next(i for i in board['editorial_selection']['items'] if i['claim_id'] == 'c0_1')
    old.update(disposition=prior, reason='core' if prior == 'required' else 'redundant')
    raw = decisions(board)
    next(i for i in raw['items'] if i['claim_id'] == 'variant')['retained_anchor_claim_ids'] = []
    assert apply_review(board, state, raw)[1] == ('explicit_omission_protected' if prior == 'omit' else 'demotion_anchor_unresolved')


def test_loop_content_disable_override_prevents_necessity_model_call():
    state, board = fixture()
    state['loop_config'] = {'content_optimization': {'enabled': False}}
    worker = SimpleNamespace(_model_json=lambda *_: pytest.fail('Loop override must disable this action'))
    unchanged, report = review_selection(state, board, FAMILIES[0].family_id, optimizer=worker)
    assert unchanged == board and report['reason'] == 'disabled'


def test_measured_review_budget_skip_is_recorded_as_skip(monkeypatch, tmp_path):
    import src.agents.layout_with_balancer as module
    state, board = fixture(invalid=False)
    state['output_dir'] = str(tmp_path)
    monkeypatch.setattr(module, 'fit_family_layout', lambda *a, **k: (_ for _ in ()).throw(
        LayoutFeasibilityError('capacity', {'status': 'infeasible', 'reason_code': 'NO_FAST_FEASIBLE_VARIANT'})))
    def review(*args, **kwargs):
        return board, {'status': 'skipped', 'reason': 'repair_budget_exhausted', 'model_rounds': 0} if kwargs else {'status': 'not_needed', 'model_rounds': 0}
    monkeypatch.setattr('src.layout.selection_review.review_selection', review)
    monkeypatch.setattr(module, '_audited_capacity_repair', lambda *a, **k: (None, {'rounds_attempted': 0}))
    module.LayoutWithBalancerAgent()._run_family_constraint_engine(state, FAMILIES[0].family_id)
    assert state['selection_review_report']['reason'] == 'repair_budget_exhausted'


@pytest.mark.parametrize('include_extra', [False, True])
def test_curator_recovers_only_context_of_selected_findings(include_extra):
    from src.agents.grounded_curator import GroundedCurator
    claims = {c: {'claim_id': c, 'text': c, 'section_id': 'research' if c != 'setting' else 'setup'}
              for c in ('main', 'extra', 'setting')}
    ids = ['main', 'extra'] if include_extra else ['main']
    raw = {'spatial_content_plan': {'sections': [{'section_id': 'research', 'claim_ids': ids}]},
           'editorial_selection': {'items': [
               {'claim_id': 'main', 'disposition': 'required', 'reason': 'core'},
               {'claim_id': 'extra', 'disposition': 'optional', 'reason': 'useful'},
               {'claim_id': 'setting', 'disposition': 'required', 'reason': 'condition',
                'required_for_claim_ids': ['extra']}]}}
    board = GroundedCurator()._materialize(raw, claims, {}, {}, family_mode=True)
    visible = {c for s in sections(board) for c in s['claim_ids']}
    assert ('setting' in visible) == include_extra
    assert contexts_met(board, {'verified_claims': {'claims': list(claims.values())}})
