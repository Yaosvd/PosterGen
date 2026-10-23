from copy import deepcopy
from types import SimpleNamespace
import json

import pytest

from src.agents.content_optimizer import GroundedContentOptimizer
from src.layout import module_compaction as mc
from src.layout.capacity_repair import CapacityActionPlanner
from utils.grounded_content import claim_root_id
from src.workflow.module_planning_requests import ModulePlanningRequests
from src.layout import capacity_repair as cr
from src.layout.feasibility import LayoutFeasibilityError


@pytest.fixture
def state(tmp_path):
    claims = []
    for index, text in enumerate([
        'Under the original experimental conditions, the method predicts the measured behavior accurately.',
        'The measured improvement applies to the original held-out population and comparison baseline.',
    ], 1):
        claims.append({'claim_id': f'c{index}', 'text': text, 'verified': True,
                       'evidence_ids': [f'ev_000{index}'], 'body_contract': 'sample_body_v2',
                       'display_module_id': 'display_001', 'section_id': '',
                       'source_plan_unit_ids': ['u1', 'u2'], 'essential': True,
                       'required_evidence_ids': [f'ev_000{index}'],
                       'covered_required_evidence_ids': [f'ev_000{index}'],
                       'requires_claim_ids': ['c1'] if index == 2 else [],
                       'parent_claim_id': 'c1' if index == 2 else None,
                       'module_context': {'items': []}})
    return {'output_dir': str(tmp_path), 'generation_route': 'optimization_family',
            'text_model': {}, 'iteration_context': {'iteration': 1},
            'sample_module_plan': {'modules': [{'module_id': 'display_001'}]},
            'verified_claims': {'claims': claims}, 'verified_content_bank': {'claims': []},
            'supplemental_evidence_bank': {'items': []}, 'critic_config': {},
            'evidence_bank': {'items': [{'evidence_id': f'ev_000{i}', 'source_excerpt': c['text']}
                                        for i, c in enumerate(claims, 1)]},
            'story_board': {'spatial_content_plan': {'sections': [{
                'section_id': 'display_001', 'section_title': 'Grounded result',
                'claim_ids': ['c1', 'c2'], 'core_claim_ids': ['c1'],
                'text_content': [c['text'] for c in claims], 'visual_assets': [],
                'claim_layout': [{'claim_id': 'c2', 'requires_claim_ids': ['c1'], 'parent_claim_id': 'c1'}]}]}}}


def draft():
    return {'claims': [
        {'source_claim_id': 'c1', 'text': 'The method predicts measured behavior under the original conditions.', 'evidence_ids': ['ev_0001']},
        {'source_claim_id': 'c2', 'text': 'Improvement holds for the original held-out population and baseline.', 'evidence_ids': ['ev_0002']}]}


def verified(c):
    return {**deepcopy(c), 'verified': True, 'covered_required_evidence_ids': c['required_evidence_ids'],
            'support_map': [{'quote': c['text'], 'supported': True, 'evidence_ids': c['evidence_ids']}]}


def install(monkeypatch, proposal=None):
    monkeypatch.setattr(mc, '_request', lambda _s, _j, name, _p:
                        deepcopy(draft() if proposal is None else proposal) if name == 'draft'
                        else {'grounded': True, 'meaning_preserved': True})
    optimizer = GroundedContentOptimizer()
    optimizer._verify_candidate = lambda _s, c, _b: (verified(c), {})
    return optimizer


def run(optimizer, state):
    return optimizer(state, board_override=deepcopy(state['story_board']), actions_override=[
        {'operation': 'create_compact_module', 'section_id': 'display_001'}], save=False)


def test_atomic_batch_preserves_roots_order_origins_and_dependencies(state, monkeypatch):
    optimizer = install(monkeypatch)
    original = deepcopy(state['verified_claims'])
    result = run(optimizer, state)
    variants = result['verified_content_bank']['claims']
    assert [claim_root_id(c) for c in variants] == ['c1', 'c2']
    assert all(c['section_id'] == '' and c['source_plan_unit_ids'] == ['u1', 'u2'] for c in variants)
    assert variants[1]['requires_claim_ids'] == [variants[0]['claim_id']]
    assert variants[1]['original_dependency_records']['requires_claim_ids'] == ['c1']
    assert result['verified_claims'] == original
    section = result['story_board']['spatial_content_plan']['sections'][0]
    assert section['claim_ids'] == [c['claim_id'] for c in variants]
    assert section['core_claim_ids'] == [variants[0]['claim_id']]
    assert section['claim_layout'][0]['requires_claim_ids'] == [variants[0]['claim_id']]
    assert len(result['content_revision']['accepted_actions']) == 1
    assert not (mc.Path(state['output_dir'])/'preparation_repair_budget.json').exists()


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'reorder', 'foreign', 'citation', 'number', 'expansion', 'no_gain', 'empty'])
def test_invalid_batch_never_partially_publishes(state, monkeypatch, defect):
    proposal = draft()
    if defect == 'missing': proposal['claims'].pop()
    if defect == 'duplicate': proposal['claims'][1]['source_claim_id'] = 'c1'
    if defect == 'reorder': proposal['claims'].reverse()
    if defect == 'foreign': proposal['claims'][1]['source_claim_id'] = 'foreign'
    if defect == 'citation': proposal['claims'][1]['evidence_ids'] = ['ev_0001']
    if defect == 'number': proposal['claims'][1]['text'] = 'The method improves by 999%.'
    if defect == 'expansion': proposal['claims'][1]['text'] = 'longer ' * 100
    if defect == 'no_gain':
        for row, c in zip(proposal['claims'], state['verified_claims']['claims']): row['text'] = c['text']
    if defect == 'empty': proposal['claims'] = []
    optimizer = install(monkeypatch, proposal)
    before = deepcopy(state['story_board'])
    result = run(optimizer, state)
    assert result['story_board'] == before
    assert result['verified_content_bank']['claims'] == []
    assert result['content_revision']['accepted_actions'] == []


@pytest.mark.parametrize('where', ['science', 'coverage', 'unsupported_map', 'negative_support', 'foreign_support_id', 'preservation'])
def test_one_bad_item_rolls_back_entire_batch(state, monkeypatch, where):
    optimizer = install(monkeypatch)
    if where == 'science':
        optimizer._verify_candidate = lambda _s, c, _b: ((None, {}) if c['root_claim_id'] == 'c2' else (verified(c), {}))
    if where == 'coverage':
        optimizer._verify_candidate = lambda _s, c, _b: ({**verified(c), 'covered_required_evidence_ids': []}, {})
    if where == 'unsupported_map':
        optimizer._verify_candidate = lambda _s, c, _b: ({**verified(c), 'support_map': []}, {})
    if where == 'negative_support':
        optimizer._verify_candidate = lambda _s, c, _b: ({**verified(c), 'support_map': [
            {'quote': c['text'], 'supported': False, 'evidence_ids': c['evidence_ids']}]}, {})
    if where == 'foreign_support_id':
        optimizer._verify_candidate = lambda _s, c, _b: ({**verified(c), 'support_map': [
            {'quote': c['text'], 'supported': True, 'evidence_ids': ['foreign_evidence']}]}, {})
    if where == 'preservation':
        monkeypatch.setattr(mc, '_request', lambda _s, _j, name, _p: draft() if name == 'draft'
                            else {'grounded': True, 'meaning_preserved': False})
    before = deepcopy(state['story_board'])
    result = run(optimizer, state)
    assert result['story_board'] == before
    assert result['verified_content_bank']['claims'] == []


def test_citation_alone_does_not_create_new_coverage_responsibility(state, monkeypatch):
    state['verified_claims']['claims'][0]['covered_required_evidence_ids'] = []
    optimizer = install(monkeypatch)
    def verify(_s, c, _b):
        return {**verified(c), 'covered_required_evidence_ids':
                [] if c['root_claim_id'] == 'c1' else ['ev_0002']}, {}
    optimizer._verify_candidate = verify
    result = run(optimizer, state)
    assert len(result['verified_content_bank']['claims']) == 2
    assert result['verified_content_bank']['claims'][0]['covered_required_evidence_ids'] == []


def test_compound_expression_receives_all_original_evidence_without_six_item_truncation(state, monkeypatch):
    source = state['verified_claims']['claims'][0]
    for i in range(3, 9):
        eid = f'ev_000{i}'
        source['evidence_ids'].append(eid)
        state['evidence_bank']['items'].append({'evidence_id': eid, 'source_excerpt': source['text']})
    proposal = draft()
    proposal['claims'][0]['evidence_ids'] = source['evidence_ids']
    optimizer = install(monkeypatch)
    def request(_s, _j, name, prompt):
        if name == 'draft':
            assert 'ev_0008' in prompt
            return proposal
        return {'grounded': True, 'meaning_preserved': True}
    monkeypatch.setattr(mc, '_request', request)
    result = run(optimizer, state)
    assert result['verified_content_bank']['claims'][0]['evidence_ids'] == source['evidence_ids']


def test_wrong_verified_identity_rejects_batch(state, monkeypatch):
    optimizer = install(monkeypatch)
    optimizer._verify_candidate = lambda _s, c, _b: ({**verified(c), 'claim_id': 'foreign'}, {})
    assert run(optimizer, state)['verified_content_bank']['claims'] == []


@pytest.mark.parametrize('second_rewrite', [False, True])
def test_semantic_correction_gets_one_final_context_check(state, monkeypatch, second_rewrite):
    optimizer = install(monkeypatch)
    calls = []
    def verify(_s, c, _b):
        calls.append(deepcopy(c))
        result = verified(c)
        if len(calls) == 1: result['text'] = 'Behavior is predicted under the original conditions.'
        if len(calls) == 3 and second_rewrite: result['text'] = 'Another rewrite.'
        result['support_map'][0]['quote'] = result['text']
        return result, {}
    optimizer._verify_candidate = verify
    result = run(optimizer, state)
    if second_rewrite:
        assert result['verified_content_bank']['claims'] == []
        assert len(calls) == 3
    else:
        assert len(calls) == 4
        assert calls[2]['module_context']['items'][0]['text'] == 'Behavior is predicted under the original conditions.'
        assert len(result['verified_content_bank']['claims']) == 2


def test_final_context_recheck_cannot_lose_required_supported_coverage(state, monkeypatch):
    optimizer = install(monkeypatch)
    calls = []
    def verify(_s, c, _b):
        calls.append(c['claim_id'])
        result = verified(c)
        if len(calls) == 1:
            result['text'] = 'Behavior is predicted under the original conditions.'
            result['support_map'][0]['quote'] = result['text']
        if len(calls) == 3: result['support_map'] = []
        return result, {}
    optimizer._verify_candidate = verify
    result = run(optimizer, state)
    assert len(calls) == 3
    assert result['verified_content_bank']['claims'] == []
    assert result['content_revision']['accepted_actions'] == []


@pytest.mark.parametrize('route', ['standalone_classic', 'no_sample', 'locked', 'fixed_topology', 'too_many', 'cross_owner'])
def test_no_new_action_for_classic_or_ineligible_module(state, monkeypatch, route):
    optimizer = install(monkeypatch)
    if route == 'standalone_classic': state['generation_route'] = route
    if route == 'no_sample': state.pop('sample_module_plan')
    if route == 'locked': state['fit_locked'] = True
    if route == 'fixed_topology': state['fixed_layout_topology'] = {'zones': [{'zone_id': 'fixed'}]}
    if route == 'too_many': state['story_board']['spatial_content_plan']['sections'][0]['claim_ids'] *= 5
    if route == 'cross_owner': state['verified_claims']['claims'][1]['display_module_id'] = 'another_module'
    monkeypatch.setattr(mc, '_request', lambda *_: pytest.fail('No model work permitted'))
    assert run(optimizer, state)['content_revision']['accepted_actions'] == []


def test_planner_addresses_full_load_instead_of_tiny_early_miss(state):
    section = state['story_board']['spatial_content_plan']['sections'][0]
    # Small fixture needs sufficient content to qualify as a complete-load target.
    for c in state['verified_claims']['claims']: c['text'] += ' original supporting explanation' * 10
    section['text_content'] = [c['text'] for c in state['verified_claims']['claims']]
    report = {'status': 'infeasible', 'reason_code': 'NO_FAST_FEASIBLE_VARIANT',
              'observed_blockers': {'estimated_height': 1}, 'repair_pressure_candidates': [
                  {'section_id': 'not_this_module', 'estimated_used_in': 10.01, 'zone_limit_in': 10}]}
    actions, reason = CapacityActionPlanner.plan_with_reason(state, state['story_board'], report, round_index=0, maximum_actions=1)
    assert reason == 'module_load_actions_ready'
    assert actions[0]['section_id'] == 'display_001'
    assert actions[0]['operation'] == 'create_compact_module'
    report['observed_blockers'] = {'required_claim': 1}
    assert mc.plan_module_actions(state, state['story_board'], report, {c['claim_id']: c for c in state['verified_claims']['claims']}, 1) == []


def test_exact_local_probe_is_not_layout_admission(state):
    after = deepcopy(state['story_board'])
    after['spatial_content_plan']['sections'][0]['text_content'] = ['short']
    state.update(poster_width=54, poster_height=36)
    agent = SimpleNamespace(poster_margin=1, title_height_fraction=.18,
        _calculate_precise_section_height=lambda section, w, s, h: sum(len(t) for t in section['text_content'])/w)
    result = mc.measure_module_progress(agent, state, state, state['story_board'], after, 'classic_three_column',
             [{'operation': 'create_compact_module', 'section_id': 'display_001'}])
    assert result['improved'] is True
    assert result['certifies_feasible_layout'] is False
    assert all(row['reduction_inches'] > 0 for row in result['measurements'])


def test_display_dependency_hints_follow_variants_before_exact_probes(state, monkeypatch):
    section = state['story_board']['spatial_content_plan']['sections'][0]
    section['editorial'] = {'version': 'poster_editorial_v4', 'active': True,
        'module_prose_order': True, 'items': [{'claim_id': 'c1', 'requires_claim_ids': []},
            {'claim_id': 'c2', 'requires_claim_ids': ['c1'], 'parent_claim_id': 'c1'}]}
    result = run(install(monkeypatch), state)
    target = result['story_board']['spatial_content_plan']['sections'][0]
    variants = target['claim_ids']
    assert target['editorial']['items'][1]['claim_id'] == variants[1]
    assert target['editorial']['items'][1]['parent_claim_id'] == variants[0]
    from src.layout.body_presentation import paragraphs
    assert paragraphs(target)[1]['indent_inches'] == .30


@pytest.mark.parametrize('operation', ['create_compact_variant', 'create_style_variant'])
@pytest.mark.parametrize('covered', [False, True])
def test_single_expression_fallback_keeps_same_scientific_protection(state, monkeypatch, operation, covered):
    optimizer = GroundedContentOptimizer()
    source = state['verified_claims']['claims'][0]
    optimizer._create_candidate = lambda *_: ({'claim_id': 'v1', 'text': 'Behavior is predicted under the original conditions.',
                                               'evidence_ids': ['ev_0001']}, None)
    def verify(_s, c, _b):
        assert c['original_expression'] == source['text']
        result = verified(c)
        if not covered: result['support_map'] = []
        return result, {}
    optimizer._verify_candidate = verify
    optimizer._editorial_guard = lambda *_a, **_k: True
    result = optimizer(state, board_override=deepcopy(state['story_board']), actions_override=[
        {'operation': operation, 'section_id': 'display_001', 'claim_id': 'c1'}], save=False)
    assert len(result['content_revision']['accepted_actions']) == int(covered)
    assert result['story_board']['spatial_content_plan']['sections'][0]['claim_ids'][0] == ('v1' if covered else 'c1')


@pytest.mark.parametrize('covered', [False, True])
def test_reusing_variant_cannot_bypass_required_coverage(state, covered):
    optimizer = GroundedContentOptimizer()
    source = state['verified_claims']['claims'][0]
    variant = verified(source)
    variant.update(claim_id='v1', root_claim_id='c1', text='Behavior is predicted under the original conditions.')
    state['verified_content_bank']['claims'] = [variant]
    def verify(_s, c, _b):
        assert c['original_expression'] == source['text']
        result = verified(c)
        if not covered: result['support_map'] = []
        return result, {}
    optimizer._verify_candidate = verify
    result = optimizer(state, board_override=deepcopy(state['story_board']), actions_override=[
        {'operation': 'use_claim_variant', 'section_id': 'display_001', 'claim_id': 'c1', 'variant_id': 'v1'}], save=False)
    assert len(result['content_revision']['accepted_actions']) == int(covered)


@pytest.mark.parametrize('sample_body', [False, True])
def test_single_expression_prompt_uses_full_evidence_only_for_sample_body(state, sample_body):
    source = state['verified_claims']['claims'][0]
    if not sample_body: source.pop('body_contract')
    for i in range(3, 10):
        eid = f'ev_000{i}'
        source['evidence_ids'].append(eid)
        state['evidence_bank']['items'].append({'evidence_id': eid, 'source_excerpt': source['text']})
    optimizer = GroundedContentOptimizer()
    def model(_s, _p, payload):
        assert len(payload['evidence']) == (8 if sample_body else 6)
        return {'candidates': []}
    optimizer._model_json = model
    optimizer._create_candidate(state, state['story_board'], {'operation': 'create_compact_variant',
        'section_id': 'display_001', 'claim_id': 'c1'}, {c['claim_id']: c for c in state['verified_claims']['claims']}, {'items': []})


def test_new_request_archives_raw_and_replays_without_preparation_charge(state, monkeypatch):
    class Agent:
        calls = 0
        def __init__(self, *_): pass
        def reset(self): pass
        def step(self, _):
            Agent.calls += 1
            return SimpleNamespace(content='{"claims":[]}', input_tokens=1, output_tokens=1)
    state['tokens'] = SimpleNamespace(add_text=lambda *_: None)
    monkeypatch.setattr(mc, 'LangGraphAgent', Agent)
    monkeypatch.setattr(mc, 'apply_agent_policy', lambda *_: {})
    journal = ModulePlanningRequests(state, 'outer', directory='content/compaction_test')
    assert mc._request(state, journal, 'draft', 'test prompt') == {'claims': []}
    assert mc._request(state, journal, 'draft', 'test prompt') == {'claims': []}
    assert Agent.calls == 1
    assert journal.root.joinpath('draft/response_00.json').exists()
    journal.root.joinpath('draft/response_00.json').unlink()
    with pytest.raises(ValueError, match='no saved response'):
        mc._request(state, journal, 'draft', 'test prompt')
    assert Agent.calls == 1


@pytest.mark.parametrize('physical_gain', [False, True])
def test_module_action_spends_original_budget_before_work_and_requires_measured_progress(state, monkeypatch, physical_gain):
    attempt = mc.Path(state['output_dir'])/'attempts/attempt_0001'
    attempt.mkdir(parents=True)
    state['iteration_context'].update(attempt_diagnostics_dir=str(attempt), attempt_id='attempt_0001')
    state.update(tokens=object(), text_model={'model': 'test'})
    state['critic_config']['capacity_repair'] = {'max_rounds_per_iteration': 4,
        'quality_reserved_rounds': 1, 'max_rounds_per_family': 2,
        'require_progress_for_second_round': True}
    original = deepcopy(state['story_board'])
    actions = [{'operation': 'create_compact_module', 'section_id': 'display_001'}]
    monkeypatch.setattr(cr.CapacityActionPlanner, 'plan_with_reason', lambda *_a, **_k: (actions, 'ready'))
    calls = []
    def optimize(trial, *, board_override, actions_override, save):
        charges = json.loads((attempt/'model_repair_budget.json').read_text())['charges']
        assert len(charges) == len(calls)+1
        calls.append(deepcopy(charges))
        trial['story_board'] = deepcopy(board_override)
        trial['content_revision'] = {'accepted_actions': actions, 'module_compactions': [{'status': 'verified_pending_exact_fit'}]}
        return trial
    monkeypatch.setattr(cr, 'content_optimizer', optimize)
    monkeypatch.setattr(mc, 'measure_module_progress', lambda *_a, **_k:
                        {'improved': physical_gain, 'certifies_feasible_layout': False})
    report = {'status': 'infeasible', 'reason_code': 'NO_FAST_FEASIBLE_VARIANT',
              'repair_pressure_candidates': [{'placed_section_count': 1, 'estimated_used_in': 11, 'zone_limit_in': 10}]}
    def fail(*_a, **_k): raise LayoutFeasibilityError('still infeasible', deepcopy(report))
    monkeypatch.setattr(cr, 'fit_family_layout', fail)
    result, audit = cr.repair_family_fit(object(), state, state['story_board'], 'classic_three_column', initial_report=report)
    assert result is None
    assert len(calls) == (2 if physical_gain else 1)
    assert state['story_board'] == original
    assert state['verified_content_bank']['claims'] == []
    assert len(json.loads((attempt/'model_repair_budget.json').read_text())['charges']) == len(calls)
    # Abandoning/restarting does not refund the family limit or consume quality reserve.
    assert cr.available_rounds(state, 'capacity', state['critic_config']['capacity_repair']) == 3-len(calls)
