"""Actual placement, family-aware entry points, and exact safe assignment."""

from copy import deepcopy

import pytest

from src.config.critic_config import load_critic_config
from src.layout.design_content import ContentPriorities, apply_reading_flow, flow_conflicts
from src.layout.family_contract import FamilyContract
from src.layout.families import LayoutArchitect, FAMILIES, compile_layout
from src.layout.feasibility import _exact_refine_candidate, fit_family_layout, validate_compiled_layout
from src.layout.reading_flow import analyze_reading, reassign_reading
from test_family_design_policy import state_for
from test_layout_exploration import _MeasuredAgent, _board


def zone(zid, ids, *, x=0, y=0, role='support', capacity=2):
    return {'zone_id': zid, 'section_ids': ids, 'x': x, 'y': y,
            'width': .3, 'height': 1, 'role': role, 'capacity': capacity}


def priorities_for(roles):
    sections = [{'section_id': sid, 'claim_ids': [sid]} for sid in roles]
    state = {'narrative_plan': {'sections': [
        {'section_id': sid, 'narrative_role': role} for sid, role in roles.items()]}}
    return ContentPriorities(state, sections), {s['section_id']: s for s in sections}


def test_saved_i6_shape_detects_results_before_methods_with_shared_measurements():
    roles = {'p': 'insight', 'm': 'method', 'd': 'methods', 'r': 'results', 'a': 'evaluation'}
    priorities, selected = priorities_for(roles)
    spec = {'family_id': 'horizontal_narrative_bands', 'zones': [
        zone('b1', ['p']), zone('b2', ['r', 'a'], y=.2),
        zone('b3', ['d'], y=.5), zone('b4', ['m'], y=.7)],
        'reading_order': ['p', 'r', 'a', 'd', 'm']}
    assert flow_conflicts(spec, selected, priorities, FamilyContract(reading='bands')) == [('a', 'd')]
    report = analyze_reading(spec, FamilyContract(reading='bands'), priorities.planned)
    assert report['conflicts'] == [['a', 'd']]
    assert report['role_ranks'] == [1, 3, 3, 2, 2]


def test_saved_i7_shape_preserves_summary_but_checks_the_body():
    priorities, selected = priorities_for({'p': 'problem', 'd': 'insight', 'm': 'method',
        's': 'method', 'r': 'results', 'a': 'results', 'h': 'implications'})
    # Mirrored IDs deliberately disagree with their physical left/right names.
    spec = {'zones': [zone('hero', ['h'], role='hero'),
        zone('bottom_right', ['p', 'a'], y=.3),
        zone('bottom_middle', ['d', 's'], x=.3, y=.3),
        zone('bottom_left', ['m', 'r'], x=.6, y=.3)],
        'reading_order': ['h', 'p', 'a', 'd', 's', 'm', 'r']}
    contract = FamilyContract(reading='anchor_first', entry_roles=('implications',))
    assert flow_conflicts(spec, selected, priorities, contract) == [('a', 'd')]
    fixed, audit = reassign_reading(spec, selected, priorities, contract,
        fits=lambda zid, ids: True, pins={}, allowed=lambda sid, zid: True)
    assert audit['status'] == 'adopted'
    assert fixed['zones'][0]['section_ids'] == ['h']
    assert fixed['reading_order'] == ['h', 'p', 'd', 'm', 's', 'r', 'a']
    assert not flow_conflicts(fixed, selected, priorities, contract)
    assert spec['zones'][1]['section_ids'] == ['p', 'a']
    assert [{k:v for k,v in z.items() if k!='section_ids'} for z in fixed['zones']] == [
        {k:v for k,v in z.items() if k!='section_ids'} for z in spec['zones']]


@pytest.mark.parametrize('role', ['insight', ' Methods ', 'findings', 'implications', 'discussion'])
def test_shared_role_aliases_are_classified_without_false_final_stage(role):
    p, _ = priorities_for({'s': role})
    report = analyze_reading({'reading_order': ['s']}, FamilyContract(reading='columns'), p.planned)
    assert report['role_ranks'][0] is not None
    assert not report['unknown_role_section_ids']


def test_unknown_slots_stay_in_place_but_cannot_hide_a_reversal():
    p, selected = priorities_for({'r': 'results', 'u': 'new_role', 'm': 'method'})
    spec = {'zones': [zone('z', ['r', 'u', 'm'], capacity=3)], 'reading_order': ['r', 'u', 'm']}
    contract = FamilyContract(reading='columns')
    assert flow_conflicts(spec, selected, p, contract) == [('r', 'm')]
    apply_reading_flow(spec, selected, p, contract)
    assert spec['reading_order'] == ['m', 'u', 'r']
    assert analyze_reading(spec, contract, p.planned)['role_ranks'] == [2, None, 3]


@pytest.mark.parametrize('reading', ['parallel', 'matrix'])
def test_peer_branches_are_independent_but_local_order_is_checked(reading):
    p, selected = priorities_for({'p': 'problem', 'm': 'method', 'r': 'results'})
    contract = FamilyContract(reading=reading)
    spec = {'zones': [zone('a', ['r']), zone('b', ['p', 'm'], x=.5)]}
    assert not flow_conflicts(spec, selected, p, contract)
    spec['zones'][1]['section_ids'] = ['r', 'm']
    assert flow_conflicts(spec, selected, p, contract) == [('r', 'm')]


def test_metadata_only_order_cannot_conceal_physical_inversion():
    p, _ = priorities_for({'r': 'results', 'm': 'method'})
    spec = {'zones': [zone('left', ['r']), zone('right', ['m'], x=.5)], 'reading_order': ['m', 'r']}
    report = analyze_reading(spec, FamilyContract(reading='columns'), p.planned)
    assert report['actual_reading_order'] == ['r', 'm']
    assert report['declared_order_matches_positions'] is False
    assert report['conflicts'] == [['r', 'm']]


@pytest.mark.parametrize('reading', ['columns', 'bands', 'stages', 'anchor_first', 'spine'])
def test_future_contracts_share_capacity_pins_and_bounded_assignment(reading):
    p, selected = priorities_for({'p': 'problem', 'm': 'method', 'r': 'results'})
    spec = {'zones': [zone('a', ['r'], capacity=1), zone('b', ['p'], x=.3,y=.3,capacity=1),
                      zone('c', ['m'], x=.6,y=.6,capacity=1)]}
    contract = FamilyContract(reading=reading)
    fixed, audit = reassign_reading(spec, selected, p, contract,
        fits=lambda zid, ids: True, pins={}, allowed=lambda sid,zid: True)
    assert fixed['reading_order'] == ['p', 'm', 'r']
    assert audit['states'] <= 256
    for kwargs in ({'pins': {'r':'a'}}, {'fits': lambda zid,ids: zid!='c' or ids==['m']},
                   {'allowed': lambda sid,zid: sid!='r' or zid=='a'}, {'maximum_states':1}):
        settings = dict(fits=lambda zid,ids: True, pins={}, allowed=lambda sid,zid: True)
        fixed, audit = reassign_reading(spec, selected, p, contract, **{**settings, **kwargs})
        assert fixed is None
        assert spec['zones'][0]['section_ids'] == ['r']


@pytest.mark.parametrize('locked', [False, True])
def test_exact_order_failure_is_diagnostic_without_mutating_locked_topology(locked):
    board = {'spatial_content_plan': {'sections': deepcopy(_board()['spatial_content_plan']['sections'][1:3])}}
    state = state_for(board)
    spec = LayoutArchitect().build({**state, 'story_board': board}, 'classic_three_column',
        assignments_override={'left':['s2'], 'middle':[], 'right':['s1']})
    state['layout_revision_constraints'] = {'section_to_zone': {'s2':'left', 's1':'right'}}
    if locked:
        state['fit_locked'] = True
    original = deepcopy(spec)
    diagnostics = {}
    result = _exact_refine_candidate(_MeasuredAgent(), {'board':board, 'layout_spec':spec,
        'variant':{}, 'score':(1,1,1,'v'), 'candidate_content_selection':{}},
        deepcopy(board), state, {}, allow_changes=not locked, diagnostics=diagnostics)
    if locked:
        assert result['layout_spec'] == original
        assert result['content_quality_hints']['reading_conflicts'] == [['s2','s1']]
    else:
        assert result is None
        assert diagnostics['reason_code'] == 'READING_ORDER_UNRESOLVED'
        assert diagnostics['issues'] == [{'code':'LAYOUT_READING_ORDER_CONFLICT'}]
    assert spec == original


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f:f.family_id)
def test_all_families_fit_without_known_reading_conflicts(family):
    board = _board()
    state = state_for(board)
    if family.family_id == 'method_flow_spine':
        for section, role in zip(state['narrative_plan']['sections'],
                                 ['problem','method','method','results','conclusion','problem']):
            section['narrative_role'] = role
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    fitted, spec, report = fit_family_layout(_MeasuredAgent(), board, state, family.family_id, config=config)
    layout = compile_layout(_MeasuredAgent(), fitted, state, spec)
    assert validate_compiled_layout(layout, spec, state, poster_margin=1,
                                   title_height_fraction=.18)['passed']
    assert not report['content_quality_hints']['reading_conflicts']
    assert report['content_quality_hints']['reading_flow']['declared_order_matches_positions']
    assert report['max_physical_utilization'] <= 1


def test_legacy_replay_requires_explicit_policy_compatible_input():
    from src.layout.attempt_inputs import validate_replay_input
    from src.layout.reading_flow import READING_POLICY_VERSION
    data = {'family_contract': {'reading': 'columns'}}
    with pytest.raises(ValueError, match='reading policy differs'):
        validate_replay_input(data)
    from src.layout.editorial import EDITORIAL_POLICY_VERSION
    from src.layout.body_presentation import BODY_PRESENTATION_VERSION
    from src.layout.emphasis import EMPHASIS_POLICY_VERSION
    with pytest.raises(ValueError, match='editorial policy differs'):
        validate_replay_input({**data, 'reading_policy_version': READING_POLICY_VERSION})
    compatible = {**data, 'reading_policy_version': READING_POLICY_VERSION,
                  'editorial_policy_version': EDITORIAL_POLICY_VERSION,
                  'body_presentation_version': BODY_PRESENTATION_VERSION,
                  'emphasis_policy_version': EMPHASIS_POLICY_VERSION}
    with pytest.raises(ValueError, match='presentation policy differs'):
        validate_replay_input(compatible)
    from src.layout.presentation_policy import PRESENTATION_POLICY_VERSION
    validate_replay_input({**compatible, 'presentation_policy_version': PRESENTATION_POLICY_VERSION,
        'source_context_version': 'body_context_v1', 'selection_policy_version': 'editorial_selection_v1'})


def test_reading_only_fit_failure_keeps_its_reason_and_skips_content_models(monkeypatch):
    from src.layout import feasibility
    from src.layout.capacity_repair import CapacityActionPlanner
    def reject(*args, diagnostics=None, **kwargs):
        diagnostics.update(reason_code='READING_ORDER_UNRESOLVED',
                           issues=[{'code':'LAYOUT_READING_ORDER_CONFLICT'}])
        return None
    monkeypatch.setattr(feasibility, '_exact_refine_candidate', reject)
    board = _board()
    with pytest.raises(feasibility.LayoutFeasibilityError) as caught:
        fit_family_layout(_MeasuredAgent(), board, state_for(board), 'classic_three_column',
                          config={'explore_layout':{'max_geometry_candidates_per_family':2,
                                                   'max_adaptive_geometry_candidates':2}})
    report = caught.value.report
    assert report['reason_code'] == 'READING_ORDER_UNRESOLVED'
    assert report['failure_stage'] == 'reading_flow'
    assert report['failure_class'] == 'reading_assignment_limit'
    actions, reason = CapacityActionPlanner.plan_with_reason(
        {}, board, report, round_index=0, maximum_actions=2)
    assert actions == [] and reason == 'reading_order_unresolved'


def test_core_preference_cannot_displace_whitespace_of_better_ordered_fit(monkeypatch):
    from src.layout import feasibility
    original = feasibility._exact_refine_candidate
    ids = []
    def refine(*args, **kwargs):
        result = original(*args, **kwargs)
        if result is None:
            return None
        first = not ids
        ids.append(result['variant']['variant_id'])
        result['exact_score'] = 1.0 if first else .99
        result['content_quality_hints']['missing_core_roots'] = ['core'] if first else []
        result['composition_whitespace'] = {
            'unallocated_body_fraction': .02,
            'largest_empty_rectangle_fraction': .02 if first else .3,
            'largest_cross_zone_gap_inches': .3 if first else 4,
            'largest_within_zone_gap_inches': .3,
        }
        return result
    monkeypatch.setattr(feasibility, '_exact_refine_candidate', refine)
    board = _board()
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    _, spec, report = fit_family_layout(_MeasuredAgent(), board, state_for(board),
                                       'classic_three_column', config=config)
    guard = report['selection_whitespace_guard']
    assert len(ids) > 1
    assert spec['variant_id'] == ids[0]
    assert guard['reference_variant_id'] == ids[0]
    assert guard['nonregressing_candidate_count'] < guard['candidate_count']
    assert report['composition_whitespace']['largest_empty_rectangle_fraction'] == .02
