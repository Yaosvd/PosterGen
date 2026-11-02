"""User-defined capacities, finite region merges and no added whitespace."""
from copy import deepcopy
from dataclasses import replace

import pytest

from src.layout.families import LayoutArchitect, LayoutFamilyRegistry, valid_family_topology
from src.layout.feasibility import generate_zone_variants, validate_compiled_layout
from src.layout.region_merges import merge_candidates
from src.layout.whitespace import measure_composition_whitespace, no_added_whitespace


CAPACITIES = ['222', '22', '2222', '222', '1111', '1111', '11211', '221',
              '111111', '111111', '2222', '111111', '11111', '211111', '111111']


@pytest.mark.parametrize('family,expected', zip(LayoutFamilyRegistry().all(), CAPACITIES),
                         ids=LayoutFamilyRegistry().ids())
def test_every_family_and_size_variant_obeys_user_capacities(family, expected):
    assert ''.join(str(z['capacity']) for z in family.zones) == expected
    assert family.contract.allow_split is False
    variants = generate_zone_variants(family, random_seed=20261028, maximum=2000)
    assert variants == generate_zone_variants(family, random_seed=20261028, maximum=2000)
    originals = {z['zone_id']: z for z in family.zones}
    assert any(v['mutation_trace'] for v in variants)  # size changes remain available
    for variant in variants:
        assert valid_family_topology(family, variant['zones'])
        assert not any('__lower' in z['zone_id'] for z in variant['zones'])
        assert 'split_zone' not in variant['mutation_trace']
        merged = [z for z in variant['zones'] if z.get('merged_from')]
        assert len(merged) <= 2
        assert variant['mutation_trace'].count('span_adjacent_zones') == len(merged)
        for z in variant['zones']:
            assert z['capacity'] == (2 if z.get('merged_from') else originals[z['zone_id']]['capacity'])


def test_horizontal_vertical_and_two_disjoint_merges_are_generated():
    family = LayoutFamilyRegistry().get('small_multiples_matrix')
    options = merge_candidates(family, family.zones)
    assert any('horizontal' in trace for _, _, trace in options)
    assert any('vertical' in trace for _, _, trace in options)
    assert any(trace.count('span_adjacent_zones') == 2 for _, _, trace in options)
    for _, zones, _ in options:
        members = [m for z in zones for m in z.get('merged_from', [z['zone_id']])]
        assert len(members) == len(set(members)) == len(family.zones)
        assert valid_family_topology(family, zones)
        # A second invocation must not extend an already merged pair.
        assert merge_candidates(family, zones) == []


def test_gaps_alignment_roles_and_protections_are_authoritative():
    family = LayoutFamilyRegistry().get('small_multiples_matrix')
    pair = deepcopy(list(family.zones[:2]))
    assert merge_candidates(family, pair)
    pair[1]['y'] += .01
    assert not merge_candidates(family, pair)
    pair = deepcopy(list(family.zones[:2]));pair[1]['x'] += .1
    assert not merge_candidates(family, pair)
    for field, value in [('capacity', 2), ('role', 'hero'), ('role', 'conclusion')]:
        pair = deepcopy(list(family.zones[:2]));pair[0][field] = value
        assert not merge_candidates(family, pair)
    family = replace(family, contract=replace(family.contract, protected_spans=('cell_1_1',)))
    assert not any('cell_1_1' in trace for _, _, trace in merge_candidates(family, family.zones))


def test_forged_third_merge_recursion_missing_region_and_capacity_inflation_reject():
    family = LayoutFamilyRegistry().get('small_multiples_matrix')
    zones = deepcopy(list(family.zones))
    for col in range(3):
        a, b = zones[col], zones[col+3]
        a.update(height=1., capacity=2, merged_from=[a['zone_id'], b['zone_id']])
    assert not valid_family_topology(family, zones[:3])
    for members in [['cell_1_1','cell_1_2','cell_1_3'], ['cell_1_1', ['cell_1_2']],
                    ['cell_1_1','cell_2_3']]:
        zones = deepcopy(list(family.zones));zones[0].update(capacity=2, merged_from=members)
        assert not valid_family_topology(family, zones)
    zones = deepcopy(list(family.zones));zones[0]['capacity'] = 2
    assert not valid_family_topology(family, zones)
    assert not valid_family_topology(family, list(family.zones)[1:])
    zones = deepcopy(list(family.zones));zones[0]['zone_id'] += '__lower'
    assert not valid_family_topology(family, zones)


def test_architect_and_preflight_reject_too_many_modules_in_a_region():
    family = LayoutFamilyRegistry().get('top_hero_bottom_grid')
    state = {'story_board': {'spatial_content_plan': {'sections': [
        {'section_id': str(i)} for i in range(5)]}}}
    with pytest.raises(ValueError, match='capacity'):
        LayoutArchitect().build(state, family.family_id)
    zones = deepcopy(list(family.zones));zones[0]['section_ids'] = ['a', 'b']
    report = validate_compiled_layout([], {'family_id': family.family_id, 'zones': zones},
        {'generation_route':'optimization_family', 'poster_width':54, 'poster_height':36},
        poster_margin=1, title_height_fraction=.18)
    assert any(i['code']=='PREFLIGHT_ZONE_CAPACITY' for i in report['issues'])


def test_small_whitespace_regressions_no_longer_hide_in_old_tolerance():
    before = {'empty_body_fraction': .3, 'largest_empty_rectangle_fraction': .1,
              'unallocated_body_fraction': .04, 'largest_cross_zone_gap_inches': 1.,
              'mean_terminal_bottom_gap_inches': 2.}
    assert no_added_whitespace(before, before)
    for key in before:
        after = {**before, key: before[key] + .005}
        assert not no_added_whitespace(before, after)
    assert not no_added_whitespace(before, {**before, 'empty_body_fraction': float('nan')})


def test_total_empty_area_is_measured_even_when_largest_hole_stays_the_same():
    zones = [{'zone_id':'left','x':0,'y':0,'width':1,'height':1}]
    layout = [{'type':'section_container','section_id':'a','zone_id':'left',
               'x':1,'y':1,'width':2,'height':4}]
    args = dict(poster_width=6,poster_height=6,poster_margin=1,title_height_fraction=0)
    before = measure_composition_whitespace({'zones':zones},layout,**args)
    assert before['empty_body_fraction'] == .5
    layout[0]['width'] = 1.9
    after = measure_composition_whitespace({'zones':zones},layout,**args)
    assert after['empty_body_fraction'] > before['empty_body_fraction']
    assert not no_added_whitespace(before, after)


def test_two_vertical_merges_survive_real_compile_and_preflight():
    from src.layout.families import compile_layout
    from test_layout_exploration import _MeasuredAgent
    family = LayoutFamilyRegistry().get('small_multiples_matrix')
    name,zones,trace = next(c for c in merge_candidates(family, family.zones)
                           if c[2].count('vertical') == 2)
    sections = [{'section_id':f's{i}', 'section_title':'Explanation',
                 'claim_ids':[f'c{i}'], 'text_content':['Original supported explanation.'],
                 'visual_assets':[]} for i in range(6)]
    assignment,remaining = {},list(sections)
    for zone in zones:
        assignment[zone['zone_id']] = [s['section_id'] for s in remaining[:zone['capacity']]]
        remaining = remaining[zone['capacity']:]
    assert not remaining
    board={'spatial_content_plan':{'sections':sections}}
    state={'story_board':board,'poster_width':54,'poster_height':36,
           'generation_route':'optimization_family'}
    spec=LayoutArchitect().build(state,family.family_id,zones_override=zones,
        assignments_override=assignment,variant_metadata={'mutation_trace':trace})
    layout=compile_layout(_MeasuredAgent(),board,state,spec)
    report=validate_compiled_layout(layout,spec,state)
    assert report['passed'],report
    assert [z['merged_from'] for z in spec['zones'] if z.get('merged_from')]


def test_geometry_refinement_rejects_a_higher_score_with_more_whitespace(monkeypatch):
    from types import SimpleNamespace
    from src.layout import composition_refinement as module
    from src.layout import families
    from src.layout.feasibility import _fingerprint
    monkeypatch.setattr(families, 'valid_family_topology', lambda *_:True)
    monkeypatch.setattr(module, 'boundary_options', lambda candidate,*a,**kw:
        [(1,[{**candidate['layout_spec']['zones'][0],'width':.9}],'a','b')])
    baseline={'layout_spec':{'family_id':'small_multiples_matrix','zones':[{'zone_id':'a','width':1}]},
        'variant':{},'candidate_content_selection':{'visible_claim_ids':['c'],'visible_visual_ids':['v']},
        'composition_whitespace':{'empty_body_fraction':.2},'exact_score':0}
    def exact(_agent,trial,*a,**kw):
        trial['exact_score']=100
        trial['composition_whitespace']['empty_body_fraction'] += .001
        return trial
    result,audit=module.refine_composition(SimpleNamespace(poster_margin=1,title_height_fraction=.18),
        baseline,{}, {'poster_height':36},{},exact,_fingerprint)
    assert result is baseline
    assert audit['trials'][0]['status']=='no_safe_gain'
