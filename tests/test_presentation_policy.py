"""Independent module function, paper focus and actual natural traversal."""

from copy import deepcopy

import pytest

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.layout_family import LayoutFamilyCriticEvaluator
from src.layout.editorial import prepare_board, _organize, sections
from src.layout.families import FAMILIES, LayoutFamily, LayoutFamilyRegistry
from src.layout.family_contract import FamilyContract, ordered_zones
from src.layout.feasibility import fit_family_layout, generate_zone_variants, _fit_one_variant
from src.layout.presentation_policy import (
    ordered_plan, prepare_structure, structure_audit, contribution_roots,
    focus_allowed, is_auxiliary,
)
from src.layout.reading_flow import analyze_reading, planned_for_sections
from test_family_design_policy import state_for
from test_layout_exploration import _MeasuredAgent


def study():
    roles = ['problem', 'method', 'method', 'results', 'conclusion']
    rows = [
        ('p', 'Research Problem', [('p1', 'A supported research question.', 'goal')]),
        ('m', 'Search Method', [('m1', 'A hierarchical policy selects a region and then a parcel.', 'method')]),
        ('d', 'Data and Setup', [('d1', 'The dataset comprises 26700 parcels.', 'setup'),
                               ('d2', 'Testing spans a held out period.', 'setup')]),
        ('r', 'Main Results', [('r1', 'The policy improves the stated metric against the baseline.', 'result')]),
        ('c', 'Implications', [('c1', 'The results support more effective outreach.', 'interpretation')]),
    ]
    board = {'spatial_content_plan': {'sections': [
        {'section_id': sid, 'section_title': title, 'claim_ids': [c for c, _, _ in items],
         'text_content': [t for _, t, _ in items], 'core_claim_ids': [items[0][0]], 'visual_assets': []}
        for sid, title, items in rows]}}
    state = state_for(board)
    state['narrative_plan']['sections'] = [
        {'section_id': sid, 'narrative_role': role, 'importance': 1 if sid in {'m', 'r'} else 2,
         'required_evidence_ids': ['d1e'] if sid == 'd' else []}
        for (sid, _, _), role in zip(rows, roles)]
    raw = [{'section_id': sid, 'claim_layout': [{'claim_id': cid, 'kind': kind} for cid, _, kind in items]}
           for sid, _, items in rows]
    board = prepare_board(board, state, raw)
    for section in sections(board):
        _organize(section)
    return state, board


def spec_for(board, **owners):
    zones = [{'zone_id': zid, 'x': x, 'y': 0, 'width': .3, 'height': 1,
              'role': 'hero' if zid == 'center' else 'support', 'capacity': 4, 'section_ids': owners.get(zid, [])}
             for zid, x in [('left', 0), ('center', .35), ('right', .7)]]
    return {'family_id': 'central_hero_side_rails', 'zones': zones,
            'reading_order': [sid for z in zones for sid in z['section_ids']]}


def test_routine_data_is_attached_before_fit_with_all_science_and_sources_preserved():
    state, board = study()
    original = deepcopy((state, board))
    result, audit = prepare_structure(board, state, FAMILIES[0])
    assert [s['section_id'] for s in sections(result)] == ['p', 'm', 'r', 'c']
    method = next(s for s in sections(result) if s['section_id'] == 'm')
    assert set(method['claim_ids']) == {'m1', 'd1', 'd2'}
    assert method['editorial']['merged_section_ids'] == ['m', 'd']
    assert method['presentation']['supporting_claim_roots'] == ['d1', 'd2']
    assert method['presentation']['supporting_context_groups'][0]['preferred_roots'] == ['d1']
    assert not is_auxiliary(method, state)
    assert audit['merges'] == [{'section_id': 'd', 'into_section_id': 'm'}]
    assert (state, board) == original
    assert {t for s in sections(result) for t in s['text_content']} == {
        t for s in sections(board) for t in s['text_content']}


def test_dataset_contribution_can_stand_alone_and_be_focus_without_title_blacklist():
    state, board = study()
    claim = next(c for c in state['verified_claims']['claims'] if c['claim_id'] == 'd1')
    claim['text'] = 'We introduce a new benchmark dataset for geospatial search.'
    plan = next(s for s in state['narrative_plan']['sections'] if s['section_id'] == 'd')
    plan.update(central_subject=True, contribution_evidence_ids=['d1e'])
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    data['text_content'][0] = claim['text']
    assert contribution_roots(data, state) == {'d1'}
    assert not is_auxiliary(data, state)
    assert focus_allowed(data, state, FAMILIES[3].contract)
    result, audit = prepare_structure(board, state, FAMILIES[0])
    assert len(sections(result)) == 5 and not audit['merges']


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f: f.family_id)
def test_all_registered_contracts_share_auxiliary_preparation(family):
    state, board = study()
    result, audit = prepare_structure(board, state, family)
    assert audit['merges'] == [{'section_id': 'd', 'into_section_id': 'm'}]
    assert not audit['unresolved_section_ids']
    assert {c for s in sections(board) for c in s['claim_ids']} == {
        c for s in sections(result) for c in s['claim_ids']}


def test_dataset_mention_in_a_new_method_does_not_certify_a_dataset_contribution():
    state, board = study()
    claim = next(c for c in state['verified_claims']['claims'] if c['claim_id'] == 'd1')
    claim['text'] = 'The method introduces a spatial prior trained on the dataset.'
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    assert not contribution_roots(data, state)
    assert is_auxiliary(data, state)


def test_explicit_grounded_central_subject_metadata_works_without_novelty_words():
    state, board = study()
    plan = next(s for s in state['narrative_plan']['sections'] if s['section_id'] == 'd')
    plan['contribution_evidence_ids'] = ['d1e']
    plan['central_subject'] = True
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    assert contribution_roots(data, state) == {'d1'}
    assert not is_auxiliary(data, state)


def test_claim_variant_cannot_turn_supporting_data_into_primary_method_by_changing_display_owner():
    state, board = study()
    state['verified_content_bank'] = {'claims': [{'claim_id': 'v', 'root_claim_id': 'd1',
        'section_id': 'm', 'text': 'The dataset contains 26700 parcels.', 'verified': True}]}
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    data['claim_ids'] = ['v']
    assert not focus_allowed(data, state, FAMILIES[3].contract)


def test_trimming_a_merged_module_to_only_supporting_facts_is_not_a_valid_final_module():
    state, board = study()
    board, _ = prepare_structure(board, state, FAMILIES[0])
    method = next(s for s in sections(board) if s['section_id'] == 'm')
    method['claim_ids'] = ['d1']
    method['text_content'] = [next(c['text'] for c in state['verified_claims']['claims'] if c['claim_id'] == 'd1')]
    spec = spec_for(board, left=['p'], center=['m', 'r'], right=['c'])
    audit = structure_audit(board, spec, state, FAMILIES[3].contract)
    assert not audit['passed']
    assert any(i['code'] == 'MODULE_LOST_INDEPENDENT_FUNCTION' for i in audit['issues'])


def test_merging_cannot_dispose_of_all_useful_supporting_context_during_selection():
    from src.layout.feasibility import _content_options
    state, board = study()
    board, _ = prepare_structure(board, state, FAMILIES[0])
    method = next(s for s in sections(board) if s['section_id'] == 'm')
    options = _content_options(_MeasuredAgent(), method, zone_width=15, zone_height=25, state=state)
    assert options and all('d1' in x['section']['claim_ids'] for x in options)
    assert any(set(x['section']['claim_ids']) == {'m1', 'd1'} for x in options)
    method['claim_ids'] = ['m1']
    method['text_content'] = ['A hierarchical policy selects a region and then a parcel.']
    audit = structure_audit(board, spec_for(board, left=['p'], center=['m', 'r'], right=['c']), state, FAMILIES[3].contract)
    assert any(i['code'] == 'SUPPORTING_CONTEXT_LOST' for i in audit['issues'])


def test_supporting_context_allows_verified_root_variants_and_respects_explicit_exclusions():
    from src.layout.presentation_policy import supporting_contexts_preserved
    state, board = study()
    board, _ = prepare_structure(board, state, FAMILIES[0])
    method = next(s for s in sections(board) if s['section_id'] == 'm')
    state['verified_content_bank'] = {'claims': [{'claim_id': 'd_short', 'root_claim_id': 'd1',
        'section_id': 'm', 'text': 'Verified concise sample description.', 'verified': True}]}
    method['claim_ids'] = ['m1', 'd_short']
    assert supporting_contexts_preserved(method, state)
    method['claim_ids'] = ['m1']
    assert not supporting_contexts_preserved(method, state)
    state['content_selection'] = {'disabled_claim_ids': ['d1'], 'replacements': {'d1': 'd_short'}}
    assert not supporting_contexts_preserved(method, state)
    state['content_selection'] = {}
    state['content_recovery_policy'] = {'excluded_claim_roots': [['m', 'd1'], ['m', 'd2']]}
    assert supporting_contexts_preserved(method, state)
    state['content_recovery_policy'] = {}
    state['content_selection'] = {'disabled_claim_ids': ['d1', 'd2']}
    assert supporting_contexts_preserved(method, state)


def test_i10_background_in_center_is_rejected_and_natural_core_center_passes():
    state, board = study()
    board, _ = prepare_structure(board, state, FAMILIES[3])
    contract = FAMILIES[3].contract
    assert not contract.entry_roles
    bad = spec_for(board, left=['m', 'r'], center=['p'], right=['c'])
    audit = structure_audit(board, bad, state, contract)
    assert not audit['passed']
    assert any(i['code'] == 'HERO_NOT_PAPER_FOCUS' for i in audit['issues'])
    assert audit['reading_flow']['conflicts']
    good = spec_for(board, left=['p'], center=['m', 'r'], right=['c'])
    assert structure_audit(board, good, state, contract)['passed']


def test_whole_wide_region_may_include_conclusion_after_its_primary_method_and_result():
    state, board = study()
    board, _ = prepare_structure(board, state, FAMILIES[1])
    spec = spec_for(board, left=['p'], center=['m', 'r', 'c'])
    assert structure_audit(board, spec, state, FAMILIES[1].contract)['passed']


def test_result_first_requires_explicit_entry_contract_and_real_result_content():
    state, board = study()
    board, _ = prepare_structure(board, state, FAMILIES[0])
    spec = spec_for(board, left=['p', 'm'], center=['r'], right=['c'])
    contract = FamilyContract(reading='bands', entry_roles=('results',))
    spec['reading_order'] = ['r', 'p', 'm', 'c']
    assert structure_audit(board, spec, state, contract)['passed']
    spec['zones'][1]['section_ids'] = ['p']
    assert not structure_audit(board, spec, state, contract)['passed']


def test_future_column_entry_preserves_natural_body_traversal():
    zones = [{'zone_id': zid, 'x': x, 'y': y, 'role': role}
             for zid, x, y, role in [('right', .7, 0, 'support'), ('lower', 0, .5, 'support'),
                                     ('left', 0, 0, 'support'), ('hero', .35, 0, 'hero')]]
    contract = FamilyContract(reading='columns', entry_roles=('results',))
    assert [z['zone_id'] for z in ordered_zones(zones, contract)] == ['hero', 'left', 'lower', 'right']


def test_raw_source_order_overrides_generic_role_rank_and_abstract_preview():
    state, board = study()
    # This paper presents an evaluation before its theoretical explanation.
    state['evidence_bank'] = {'items': [
        {'evidence_id': 'abstract', 'source': {'section_id': 'abs', 'section_name': 'Abstract'}},
        {'evidence_id': 'intro1', 'source': {'section_id': 'intro', 'section_name': '1 Introduction'}},
        {'evidence_id': 'intro2', 'source': {'section_id': 'intro', 'section_name': '1 Introduction'}},
        {'evidence_id': 'method', 'source': {'section_id': 'body1', 'section_name': 'Method'}},
        {'evidence_id': 'result', 'source': {'section_id': 'body2', 'section_name': 'Evaluation'}},
        {'evidence_id': 'theory', 'source': {'section_id': 'body3', 'section_name': 'Theory'}}]}
    state['narrative_plan'] = {'sections': [
        {'section_id': 't', 'narrative_role': 'theory', 'evidence_ids': ['abstract', 'theory']},
        {'section_id': 'r', 'narrative_role': 'results', 'evidence_ids': ['intro1', 'intro2', 'result']},
        {'section_id': 'm', 'narrative_role': 'method', 'evidence_ids': ['method']}]}
    plan = ordered_plan(state)
    assert [s['section_id'] for s in sorted(plan.values(), key=lambda s: s['source_order'])] == ['m', 'r', 't']
    spec = {'zones': [{'zone_id': 'z', 'x': 0, 'y': 0, 'section_ids': ['m', 'r', 't']}],
            'reading_order': ['m', 'r', 't']}
    report = analyze_reading(spec, FamilyContract(), plan)
    assert report['ordering_basis'] == 'paper_body_sources' and not report['conflicts']
    spec['zones'][0]['section_ids'] = ['m', 't', 'r']
    assert analyze_reading(spec, FamilyContract(), plan)['conflicts'] == [['t', 'r']]


@pytest.mark.parametrize('flag', ['fixed_layout_topology', 'fit_locked'])
def test_locked_structure_is_observed_but_never_regrouped(flag):
    state, board = study()
    state[flag] = True
    result, audit = prepare_structure(board, state, FAMILIES[3])
    assert result == board and not audit['merges']
    spec = spec_for(board, left=['m', 'd', 'r'], center=['p'], right=['c'])
    assert not structure_audit(result, spec, state, FAMILIES[3].contract)['passed']


def test_bad_structure_is_a_critic_hard_gate_even_without_any_overflow():
    state, board = study()
    state.update(optimized_story_board=board, layout_spec=spec_for(board,
                 left=['m', 'd', 'r'], center=['p'], right=['c']))
    result = LayoutFamilyCriticEvaluator().evaluate(CriticContext(state=state, config=load_critic_config()))
    assert result.hard_gate and not result.passed
    assert any(i['issue_id'].startswith('PRESENTATION-') for i in result.issues)


@pytest.mark.parametrize('mode', ['explore', 'current_fixed', 'current_pinned'])
def test_internal_refit_retains_zone_ownership_in_every_mode(mode):
    state, board = study()
    board['spatial_content_plan']['sections'] = sections(board)[:1]
    state['iteration_context']['generation_purpose'] = 'explore'
    state['fit_locked'] = mode == 'current_fixed'
    state['layout_revision_constraints'] = {'section_to_zone': {'p': 'right'}, 'must_retain_claim_ids': ['p1']}
    family = FAMILIES[0]
    variant = generate_zone_variants(family, random_seed=1, maximum=1)[0]
    result = _fit_one_variant(_MeasuredAgent(), board, state, family, variant,
                              {'minimum_sections': 1, 'beam_width': 4}, {})
    assert result is not None
    assert next(z['zone_id'] for z in result['layout_spec']['zones'] if z['section_ids']) == 'right'
    assert sections(result['board'])[0]['claim_ids'] == ['p1']


def test_finding_entry_label_is_measured_once_even_for_a_long_scientific_title():
    state, board = study()
    section = next(s for s in sections(board) if s['section_id'] == 'r')
    section['editorial']['source_title'] = section['section_title'] = ' '.join(['Scientific'] * 14)
    section['editorial']['reading_entry'] = True
    _organize(section)
    first = section['section_title']
    _organize(section)
    assert section['section_title'] == first and first.count('Key finding: ') == 1
    section['editorial']['reading_entry'] = False
    _organize(section)
    assert not section['section_title'].startswith('Key finding: ')


def test_exact_compile_installs_only_the_adopted_entry_style():
    from src.layout.feasibility import _exact_refine_candidate
    from src.layout.families import LayoutArchitect
    state, board = study()
    family = next(f for f in FAMILIES if f.family_id == 'top_hero_bottom_grid')
    board, _ = prepare_structure(board, state, family)
    body = next(s for s in sections(board) if s['section_id'] == 'p')
    body['editorial']['reading_entry'] = True
    _organize(body)
    spec = LayoutArchitect().build({**state, 'story_board': board}, family.family_id,
        assignments_override={'top_hero': ['r'], 'bottom_left': ['p'],
                              'bottom_middle': ['m'], 'bottom_right': ['c']})
    result = _exact_refine_candidate(_MeasuredAgent(), {
        'board': deepcopy(board), 'layout_spec': spec, 'variant': {}, 'score': (1, 1, 1, 'v'),
        'candidate_content_selection': {}}, board, state, {'max_exact_refill_steps': 0}, allow_changes=True)
    assert result is not None
    for section in sections(result['board']):
        assert section['section_title'].startswith('Key finding: ') == (section['section_id'] == 'r')


def test_source_order_does_not_sort_unknown_modules_by_identifier_or_send_them_last():
    from src.layout.design_content import ContentPriorities, apply_reading_flow
    state, board = study()
    state['evidence_bank'] = {'items': [
        {'evidence_id': 'm1e', 'source': {'section_id': 'first', 'section_name': 'Method'}},
        {'evidence_id': 'r1e', 'source': {'section_id': 'last', 'section_name': 'Results'}}]}
    for s in state['narrative_plan']['sections']:
        s['evidence_ids'] = [s['section_id'] + '1e']
    unknown = {'section_id': 'zz_unknown', 'claim_ids': [], 'text_content': []}
    state['narrative_plan']['sections'].append({'section_id': 'zz_unknown', 'narrative_role': 'method'})
    chosen = {s['section_id']: s for s in sections(board)} | {'zz_unknown': unknown}
    priorities = ContentPriorities(state, list(chosen.values()))
    spec = {'zones': [{'zone_id': 'z', 'x': 0, 'y': 0,
                      'section_ids': ['r', 'zz_unknown', 'm']}],
            'reading_order': ['r', 'zz_unknown', 'm']}
    apply_reading_flow(spec, chosen, priorities, FamilyContract())
    assert spec['reading_order'] == ['m', 'zz_unknown', 'r']
    assert analyze_reading(spec, FamilyContract(), priorities.planned)['scope_status'] == 'partial'


def test_standalone_board_and_structure_remain_unchanged():
    state, board = study()
    state['generation_route'] = 'standalone_classic'
    result, audit = prepare_structure(board, state, FAMILIES[0])
    assert result == board and not audit['merges']
    assert structure_audit(board, {}, state, FAMILIES[0].contract)['status'] == 'not_applicable'


def test_structure_only_failure_keeps_diagnostics_and_never_spends_content_actions(monkeypatch):
    from src.layout import feasibility
    from src.layout.capacity_repair import CapacityActionPlanner
    def reject(*args, diagnostics=None, **kwargs):
        diagnostics.update(reason_code='PRESENTATION_STRUCTURE_UNRESOLVED',
                           issues=[{'code': 'AUXILIARY_MODULE_STANDALONE'}])
        return None
    monkeypatch.setattr(feasibility, '_exact_refine_candidate', reject)
    state, board = study()
    with pytest.raises(feasibility.LayoutFeasibilityError) as caught:
        fit_family_layout(_MeasuredAgent(), board, state, 'classic_three_column',
            config={'explore_layout': {'max_geometry_candidates_per_family': 2,
                                      'max_adaptive_geometry_candidates': 2}})
    report = caught.value.report
    assert report['reason_code'] == 'PRESENTATION_STRUCTURE_UNRESOLVED'
    assert report['failure_class'] == 'presentation_assignment_limit'
    actions, reason = CapacityActionPlanner.plan_with_reason({}, board, report, round_index=0, maximum_actions=2)
    assert actions == [] and reason == 'presentation_structure_unresolved'


def test_future_registered_family_uses_the_same_structure_focus_and_fit(monkeypatch):
    family = LayoutFamily('future_natural', 'Future', 'Future', FAMILIES[3].zones,
                          ('general',), contract=FamilyContract(allow_module_grouping=True))
    original = LayoutFamilyRegistry.__init__
    def register(self):
        original(self)
        self._families[family.family_id] = family
    monkeypatch.setattr(LayoutFamilyRegistry, '__init__', register)
    state, board = study()
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    fitted, spec, report = fit_family_layout(_MeasuredAgent(), board, state, family.family_id, config=config)
    assert 'd' not in [s['section_id'] for s in sections(fitted)]
    assert structure_audit(fitted, spec, state, family.contract)['passed']
    assert report['presentation_preparation']['merges']
