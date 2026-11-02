"""Full-paper mixed layouts use the same selection, fitting and export contracts."""

from copy import deepcopy

import pytest

from src.config.critic_config import load_critic_config
from src.layout.families import LayoutArchitect, LayoutFamilyRegistry, valid_family_topology
from src.layout.family_contract import ordered_zones
from src.layout.family_selection import make_family_selection_policy
from src.layout.feasibility import generate_zone_variants, validate_compiled_layout
from src.layout.paper_profile import build_paper_profile
from src.layout.reading_flow import analyze_reading


NEW_FAMILIES = ('framed_multicolumn', 'narrative_evidence_grid', 'central_evidence_band')


def test_all_fifteen_share_one_enabled_pool_and_neutral_coverage_cycle():
    registry = LayoutFamilyRegistry()
    config = load_critic_config()
    assert len(registry.ids()) == 15
    assert set(config['layout_families']['enabled']) == set(registry.ids())
    assert config['explore_layout']['max_family_attempts_per_iteration'] == 15
    profile = build_paper_profile({})
    policy = make_family_selection_policy(config['layout_families'], registry.ids())
    policy['semantic_bonus_max'] = 0
    counts = {}
    for number in range(15):
        family_id, report = registry.choose_with_report(profile, counts, random_seed=number, policy=policy)
        assert family_id not in counts
        assert set(report['enabled_families']) == set(registry.ids())
        assert all(item['weight'] == 1 for item in report['semantic_scores'].values())
        counts[family_id] = 1
    assert set(counts) == set(registry.ids())


@pytest.mark.parametrize('family_id', NEW_FAMILIES)
def test_new_families_have_bounded_variants_without_mutating_the_registration(family_id):
    family = LayoutFamilyRegistry().get(family_id)
    before = deepcopy(family.to_dict())
    variants = generate_zone_variants(family, random_seed=7, maximum=120)
    assert len(variants) > 4
    assert all(valid_family_topology(family, variant['zones']) for variant in variants)
    assert family.to_dict() == before
    assert len({variant['geometry_fingerprint'] for variant in variants}) == len(variants)
    assert variants == generate_zone_variants(family, random_seed=7, maximum=120)
    assert any(any(trace.startswith(('resize_frame', 'resize_narrative', 'resize_central'))
                   for trace in variant['mutation_trace']) for variant in variants)


def test_framed_body_supports_two_and_three_columns_with_full_width_bookends():
    family = LayoutFamilyRegistry().get('framed_multicolumn')
    counts = set()
    for variant in generate_zone_variants(family, random_seed=1, maximum=2000):
        zones = variant['zones']
        counts.add(sum(zone['zone_id'].startswith('body_') for zone in zones))
        assert zones[0]['zone_id'] == 'overview' and zones[0]['width'] == 1
        assert zones[-1]['zone_id'] == 'conclusion' and zones[-1]['width'] == 1
    assert counts == {2, 3}


def test_column_splits_finish_before_the_next_column_and_final_conclusion():
    family = LayoutFamilyRegistry().get('framed_multicolumn')
    zones = deepcopy(list(family.zones))
    left = zones[1]
    original_height = left['height']
    left['height'] = (original_height - .02) / 2
    zones.append({**left, 'zone_id': 'body_left__lower',
                  'y': left['y'] + left['height'] + .02})
    shuffled = list(reversed(zones))
    assert not valid_family_topology(family, shuffled)
    assert [zone['zone_id'] for zone in ordered_zones(shuffled, family.contract)] == [
        'overview', 'body_left', 'body_left__lower', 'body_middle', 'body_right', 'conclusion']
    mirrored = [{**zone, 'x': round(1 - zone['x'] - zone['width'], 6)} for zone in shuffled]
    assert [zone['zone_id'] for zone in ordered_zones(mirrored, family.contract)] == [
        'overview', 'body_right', 'body_middle', 'body_left', 'body_left__lower', 'conclusion']


def test_evidence_grid_keeps_the_narrative_first_and_shared_conclusion_last():
    family = LayoutFamilyRegistry().get('narrative_evidence_grid')
    ordered = ordered_zones(list(reversed(family.zones)), family.contract)
    assert [zone['zone_id'] for zone in ordered] == [
        'narrative_rail', 'evidence_1_1', 'evidence_2_1', 'evidence_1_2', 'evidence_2_2', 'conclusion']


def test_middle_hero_has_no_result_first_exemption_and_source_order_is_checked():
    family = LayoutFamilyRegistry().get('central_evidence_band')
    zones = deepcopy(list(family.zones))
    for zone in zones:
        zone['section_ids'] = [zone['zone_id']]
    spec = {'family_id': family.family_id, 'zones': zones,
            'reading_order': [zone['zone_id'] for zone in zones]}
    plan = {zone['zone_id']: {'narrative_role': 'results',
             'source_order_provenance': 'evidence_source', 'source_order': index}
            for index, zone in enumerate(zones)}
    assert not family.contract.entry_roles
    audit = analyze_reading(spec, family.contract, plan)
    assert audit['actual_reading_order'] == spec['reading_order']
    assert not audit['source_order_conflicts']
    plan['central_evidence']['source_order'] = -1
    assert analyze_reading(spec, family.contract, plan)['source_order_conflicts']


@pytest.mark.parametrize('family_id', NEW_FAMILIES)
def test_new_families_compile_and_pass_the_actual_layout_preflight(family_id):
    from test_family_design_policy import state_for
    from test_layout_exploration import _board, _MeasuredAgent
    from src.layout.feasibility import fit_family_layout
    from src.layout.families import compile_layout
    board = _board()
    state = state_for(board)
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    fitted, spec, report = fit_family_layout(_MeasuredAgent(), board, state, family_id, config=config)
    assert report['status'] == 'feasible'
    layout = compile_layout(_MeasuredAgent(), fitted, state, spec)
    assert validate_compiled_layout(layout, spec, state, poster_margin=1, title_height_fraction=.18)['passed']
    assert set(spec['reading_order']) == {section['section_id'] for section in fitted['spatial_content_plan']['sections']}
    assert all(section['text_content'] for section in fitted['spatial_content_plan']['sections'])


@pytest.mark.parametrize('family_id', NEW_FAMILIES)
def test_architect_uses_the_same_traversal_for_pinned_local_refits(family_id):
    family = LayoutFamilyRegistry().get(family_id)
    board = {'spatial_content_plan': {'sections': [
        {'section_id': f's{i}', 'claim_ids': [f'c{i}']}
        for i in range(min(6, sum(z['capacity'] for z in family.zones)))]}}
    state = {'story_board': board, 'fixed_layout_topology': {
        'family_id': family_id, 'zones': list(reversed(deepcopy(family.zones)))}}
    spec = LayoutArchitect().build(state, family_id)
    assert spec['zones'] == ordered_zones(spec['zones'], family.contract)
    assert spec['reading_order'] == [sid for zone in spec['zones'] for sid in zone['section_ids']]
