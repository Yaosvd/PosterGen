"""Shared allocated backgrounds and measured transfers across all families."""
from copy import deepcopy

import pytest
from pptx import Presentation
from pptx.util import Inches

from test_editorial_generation import state_for, draft_for, install
from test_editorial_exact_composition import neds_state
from test_editorial_finalization import freeze
from src.agents.layout_agent import LayoutAgent
from src.agents.renderer import Renderer
from src.layout.editorial_frames import frame_box, assert_frames
from src.layout.editorial_layout import measure, boundary_candidates, fit
from src.layout.editorial_space import shared_cuts, _contacts_preserved
from src.layout.families import LayoutFamilyRegistry, valid_family_topology
from src.layout.region_merges import merge_candidates
from src.workflow.editorial_contract import geometry_digest, assert_editorial_ready


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    from src.layout.measurement_context import measurement_scope
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected live model'))
    with measurement_scope():
        yield


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_allocated_frames_never_overlap_even_when_real_contents_overflow(tmp_path, family):
    state = state_for(tmp_path, family)
    raw = draft_for(state); raw['core_module_ids'] = [m['module_id'] for m in raw['modules'][:2]]
    raw['modules'][0]['entries'][0]['text'] = 'An explanation.\n'*90
    # Also exercise multiple modules sharing one region and its internal gutter.
    zone = next(z for z in LayoutFamilyRegistry().get(family).zones if z['capacity'] >= 2) if any(
        z['capacity'] >= 2 for z in LayoutFamilyRegistry().get(family).zones) else None
    if zone:
        extra = deepcopy(next(m for m in raw['modules'] if m['zone_id'] == zone['zone_id']))
        extra.update(module_id='extra', space_weight=2)
        raw['modules'].append(extra)
    install(state, raw)
    result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    assert_frames(state, state['editorial_candidate'], result['spec'], result['layout'])
    assert not result['report']['passed']
    first = next(e for e in result['layout'] if e['type'] == 'section_container')
    assert first['height'] > frame_box(first)['height']
    assert result['report']['modules'][0]['utilization'] > 1
    assert result['report']['total_overflow_inches'] > 0
    assert result['report']['total_underfill_inches'] > 0  # Paint is not content occupancy.
    presentation = Presentation(); slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    for container in (e for e in result['layout'] if e['type'] == 'section_container'):
        Renderer()._render_section_container(slide, container, state)
        shape = slide.shapes[-1]; box = frame_box(container)
        assert shape.top == Inches(box['y']) and shape.height == Inches(box['height'])
        assert not shape.shadow.inherit
        assert shape._element.xpath('./p:style/a:effectRef')[0].get('idx') == '0'
    # Reopen the actual editable shape geometry, including explicit empty effects.
    path = tmp_path/'frames.pptx'; presentation.save(path)
    assert not Presentation(path).slides[0].shapes[0].shadow.inherit


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_all_family_transfers_preserve_gutters_metadata_and_budget(tmp_path, family):
    state = install(state_for(tmp_path, family))
    zones = state['editorial_zones']; candidate = state['editorial_candidate']
    baseline = measure(state, candidate, zones)
    # Deliberate measured mixed pressure, including spanning neighbors. Geometry
    # proposals are tested independently of fonts; exact fit remains authoritative.
    for i, row in enumerate(baseline['report']['modules']):
        row['intrinsic_height'] = row['allocated_height']*(1.18 if i == 0 else .65)
        row['minimum_intrinsic_height'] = row['intrinsic_height']
    options = boundary_candidates(state, candidate, zones, baseline, maximum=100)
    assert 0 < len(options) <= 12
    cuts = shared_cuts(zones)
    original = {z['zone_id']: z for z in zones}
    for trial in options:
        assert valid_family_topology(LayoutFamilyRegistry().get(family), trial)
        assert _contacts_preserved(trial, cuts)
        for z in trial:
            assert {k:v for k,v in z.items() if k not in {'x','y','width','height'}} == {
                k:v for k,v in original[z['zone_id']].items() if k not in {'x','y','width','height'}}
    assert len(boundary_candidates(state, candidate, zones, baseline, maximum=1)) == 1


def test_coupled_shared_cuts_redistribute_a_band_to_both_neighbors(tmp_path):
    state = install(state_for(tmp_path, 'central_evidence_band'))
    baseline = measure(state, state['editorial_candidate'], state['editorial_zones'])
    for row in baseline['report']['modules']:
        factor = .5 if row['zone_id'] == 'central_evidence' else 1.1
        row['intrinsic_height'] = row['minimum_intrinsic_height'] = row['allocated_height']*factor
    options = boundary_candidates(state, state['editorial_candidate'], state['editorial_zones'], baseline)
    base = {z['zone_id']:z for z in state['editorial_zones']}
    coupled = [trial for trial in options if all(
        z['height'] > base[z['zone_id']]['height'] for z in trial if z['zone_id'] != 'central_evidence')]
    assert coupled, 'Independent one-cut proposals cannot satisfy both adjacent rows together'
    trial = {z['zone_id']:z for z in coupled[0]}
    assert trial['central_evidence']['y'] > base['central_evidence']['y']
    assert trial['central_evidence']['height'] < base['central_evidence']['height']
    assert len({z['y'] for key,z in trial.items() if key.startswith('bottom_')}) == 1


def test_joint_cuts_cannot_spend_a_donors_readable_space_twice(tmp_path):
    from src.layout.editorial_space import _needs
    state = install(state_for(tmp_path, 'central_evidence_band'))
    baseline = measure(state, state['editorial_candidate'], state['editorial_zones'])
    for row in baseline['report']['modules']:
        factor = .9 if row['zone_id'] == 'central_evidence' else 1.3
        row['intrinsic_height'] = row['minimum_intrinsic_height'] = row['allocated_height']*factor
    needed = _needs(state, state['editorial_candidate'], state['editorial_zones'], baseline)
    options = boundary_candidates(state, state['editorial_candidate'], state['editorial_zones'], baseline)
    assert options
    for trial in options:
        donor = next(z for z in trial if z['zone_id'] == 'central_evidence')
        assert donor['height'] >= needed['central_evidence']['height']-1e-6


@pytest.mark.parametrize('family', [fid for fid in LayoutFamilyRegistry().ids()
    if merge_candidates(LayoutFamilyRegistry().get(fid), LayoutFamilyRegistry().get(fid).zones)])
def test_shared_allocator_respects_legal_merged_region_provenance(tmp_path, family):
    from src.workflow.editorial_contract import normalize_candidate
    from src.workflow import editorial_pipeline as pipeline
    state = state_for(tmp_path, family)
    registered = LayoutFamilyRegistry().get(family)
    merges = merge_candidates(registered, registered.zones)
    zones = merges[0][1]
    raw = draft_for(state)
    removed = set(z['zone_id'] for z in registered.zones)-set(z['zone_id'] for z in zones)
    raw['modules'] = [m for m in raw['modules'] if m['zone_id'] not in removed]
    state['editorial_zones'] = zones
    pipeline.install(state, normalize_candidate(raw, state, zones))
    pipeline.editorial_color_node(state); pipeline.editorial_title_node(state)
    baseline = measure(state, state['editorial_candidate'], zones)
    for i, row in enumerate(baseline['report']['modules']):
        row['intrinsic_height'] = row['minimum_intrinsic_height'] = row['allocated_height']*(1.1 if i==0 else .6)
    options = boundary_candidates(state, state['editorial_candidate'], zones, baseline)
    assert options
    for trial in options:
        assert valid_family_topology(registered, trial)
        assert {z['zone_id']: z.get('merged_from') for z in trial} == {
            z['zone_id']: z.get('merged_from') for z in zones}
        result = measure(state, state['editorial_candidate'], trial)
        assert_frames(state, state['editorial_candidate'], result['spec'], result['layout'])


def test_exact_image_row_uses_full_height_and_exposes_safe_donation(tmp_path):
    state = neds_state(tmp_path); agent = LayoutAgent()
    section = state['optimized_story_board']['spatial_content_plan']['sections'][2]
    from src.layout.module_composition import side_by_side_plan
    plan = side_by_side_plan(agent, section, 52, 8.6428, state)
    assert plan['title_height']+plan['body_height'] == pytest.approx(8.6428)
    assert plan['minimum_height'] < 8.6428
    children = agent._create_section_elements(section, 1, 1, 52, state, 8.6428)
    assert max(e['y']+e['height'] for e in children)-1 == pytest.approx(8.6428)
    assert next(e for e in children if e['type']=='visual')['height'] > 6.9


def test_vertical_pressure_accounts_for_images_growing_with_the_region(tmp_path):
    state = neds_state(tmp_path)
    # Force a vertical module with enough text to overflow its height-capped image.
    candidate = deepcopy(state['editorial_candidate'])
    candidate['modules'][0]['visual_ids'] = ['figure_1']
    candidate['modules'][2]['visual_ids'] = []
    candidate['modules'][0]['entries'][0]['text'] = 'A long explanation of the result. '*45
    result = measure(state, candidate, state['editorial_zones'])
    metric = result['report']['modules'][0]
    assert metric['body_layout'] == 'image_above_text'
    assert metric['minimum_intrinsic_height'] > metric['intrinsic_height']


@pytest.mark.parametrize('damage', ['missing','nan','negative','position','height'])
def test_background_frame_cannot_escape_frozen_geometry(monkeypatch, tmp_path, damage):
    state = freeze(monkeypatch, tmp_path)
    assert_editorial_ready(state, compiled=True)
    layout = state['design_layout']
    box = next(e for e in layout if e['type']=='section_container')
    original_digest = geometry_digest(layout)
    if damage == 'missing': box.pop('module_frame')
    elif damage == 'nan': box['module_frame']['height'] = float('nan')
    elif damage == 'negative': box['module_frame']['width'] = -1
    elif damage == 'position': box['module_frame']['y'] -= .5
    else: box['module_frame']['height'] += 1
    with pytest.raises(ValueError, match='frame|geometry'):
        assert_editorial_ready(state, compiled=True)
    if damage in {'position','height','missing'}:
        assert geometry_digest(layout) != original_digest


def test_global_search_still_has_at_most_twelve_fast_and_four_exact_trials(tmp_path):
    state = neds_state(tmp_path)
    result = fit(state, state['editorial_candidate'], state['editorial_zones'])
    trials = result['report']['geometry_trials']
    assert len([t for t in trials if 'fast_report' in t]) <= 12
    assert len([t for t in trials if 'exact_report' in t]) <= 4
