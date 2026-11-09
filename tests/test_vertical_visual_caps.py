"""Title-free vertical caps shared by authoring, search and exact compilation."""
from copy import deepcopy
import math

import pytest

from src.agents.layout_agent import LayoutAgent
from src.layout import authoring_geometry as geometry
from src.layout.editorial_composition import VERTICAL
from src.layout.editorial_layout import measure, family_brief
from src.layout.families import LayoutFamilyRegistry
from src.layout.measurement_context import measurement_scope
from src.workflow.editorial_authoring import setup_geometry_style, skeleton
from src.workflow.editorial_contract import make_board
from test_editorial_generation import state_for, draft_for, plan_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


def fixture(tmp_path, aspects, family='classic_three_column'):
    state = state_for(tmp_path, family)
    state['tables'] = {str(i): {'aspect': a} for i, a in enumerate(aspects)}
    raw = draft_for(state)
    raw['modules'][0]['visual_ids'] = [f'table_{i}' for i in range(len(aspects))]
    plan = plan_for(raw)
    setup_geometry_style(state, plan)
    section = make_board(skeleton(plan))['spatial_content_plan']['sections'][0]
    return state, raw, section


@pytest.mark.parametrize('title_cost', [0, 2, 4])
@pytest.mark.parametrize('aspects', [[1], [100], [1, 2], [1, 100], [100, 100], [.5, 2, 100]])
def test_vertical_caps_and_common_scale_include_only_internal_gaps(tmp_path, monkeypatch, title_cost, aspects):
    state, _, section = fixture(tmp_path, aspects)
    monkeypatch.setattr(geometry, 'title_cost', lambda *a: title_cost)
    box = geometry.dimensions(LayoutAgent(), section, 20, 10, state, VERTICAL)
    rows = box['visuals']; inner = 20-2*box['padding']; available = 10-title_cost
    assert [r['visual_id'] for r in rows] == [f'table_{i}' for i in range(len(aspects))]
    assert [r['width']/r['height'] for r in rows] == pytest.approx(aspects)
    assert all(0 < r['height'] <= .4*available+1e-9 and r['width'] <= inner for r in rows)
    if len(rows) > 1:
        assert box['visual_height'] <= .5*available+1e-9
    for first, second in zip(rows, rows[1:]):
        assert second['y']-first['y']-first['height'] == pytest.approx(.3)
    assert all(r['x'] == pytest.approx((inner-r['width'])/2) for r in rows)
    assert all(r['scale'] == pytest.approx(r['width']/inner) for r in rows)
    assert box['text_height_available'] == pytest.approx(available-box['visual_height']-.3)
    # Every asset receives the same additional group shrink, even when a wide
    # table is width-limited and a tall one is individually height-limited.
    initial = [min(inner/a, .4*available) for a in aspects]
    ratios = [r['height']/h for r, h in zip(rows, initial)]
    assert ratios == pytest.approx([ratios[0]]*len(rows))
    if sum(initial)+.3*(len(rows)-1) <= .5*available or len(rows) == 1:
        assert ratios == pytest.approx([1]*len(rows))
    else:
        assert box['visual_height'] == pytest.approx(.5*available)


def test_actual_multiline_title_and_gap_are_deducted(tmp_path):
    state, _, section = fixture(tmp_path, [1])
    section['section_title'] = 'A title\nwith two lines'
    agent = LayoutAgent()
    titles = agent._create_section_title_design(section, 0, 0, 20, state)
    title = max(e['y']+e['height'] for e in titles)
    gap = agent.config['layout']['title_to_content_spacing']
    box = geometry.dimensions(agent, section, 20, 10, state, VERTICAL)
    assert box['title_height'] == pytest.approx(title+gap)
    assert box['visuals'][0]['height'] == pytest.approx(.4*(10-title-gap))


def test_planner_footprints_do_not_present_old_thirty_percent_sizes_as_final(tmp_path):
    state, _, _ = fixture(tmp_path, [1, 2])
    zones = deepcopy(list(LayoutFamilyRegistry().get('classic_three_column').zones))
    brief = family_brief(state, zones)
    for zone in brief['zones']:
        assert 'visual_heights_inches' not in zone
        inner = zone['width_inches']-.6
        assert zone['visual_full_width_heights_inches'] == pytest.approx({'table_0': inner, 'table_1': inner/2})
    assert 'each image is at most 40%' in brief['instructions']
    assert 'internal gaps are at most 50%' in brief['instructions']


def test_tiny_positive_group_room_is_not_rounded_up_past_the_cap(tmp_path, monkeypatch):
    state, _, section = fixture(tmp_path, [1, 2])
    monkeypatch.setattr(geometry, 'title_cost', lambda *a: 9.39)
    box = geometry.dimensions(LayoutAgent(), section, 20, 10, state, VERTICAL)
    assert box['visual_height'] == pytest.approx(.305)
    assert sum(r['height'] for r in box['visuals']) == pytest.approx(.005)
    issues = geometry.problems(box, {'font_size_pt': 44, 'body_reserve_inches': .6, 'line_height_inches': .76})
    assert 'vertical_visual_height_limit_exceeded' not in issues
    assert 'body_height_below_two_reference_lines' in issues


@pytest.mark.parametrize('title_cost,count', [(10, 1), (11, 2), (9, 4), (9.4, 2)])
def test_impossible_title_or_fixed_gaps_still_fail_without_zero_images(tmp_path, monkeypatch, title_cost, count):
    state, _, section = fixture(tmp_path, [1]*count)
    monkeypatch.setattr(geometry, 'title_cost', lambda *a: title_cost)
    box = geometry.dimensions(LayoutAgent(), section, 20, 10, state, VERTICAL)
    assert all(math.isfinite(r[k]) and r[k] > 0 for r in box['visuals'] for k in ('width', 'height'))
    issues = geometry.problems(box, {'font_size_pt': 44, 'body_reserve_inches': .6, 'line_height_inches': .76})
    assert 'vertical_visual_height_limit_exceeded' in issues
    assert 'body_height_below_two_reference_lines' in issues


@pytest.mark.parametrize('family', ['classic_three_column', 'method_flow_spine', 'central_evidence_band'])
def test_prewrite_exact_fast_and_resized_module_use_same_vertical_stack(tmp_path, monkeypatch, family):
    state, raw, _ = fixture(tmp_path, [1.2, 3.24, 20], family)
    zones = deepcopy(list(LayoutFamilyRegistry().get(family).zones))
    planned = geometry.prepare_geometry(state, skeleton(plan_for(raw)), zones)
    assert not planned['failures']
    assert planned['frames'][0]['body_layout'] == VERTICAL
    state['editorial_authoring_geometry'] = planned
    baseline = measure(state, raw, zones)
    geometry.assert_initial_frames(planned, baseline)
    assert planned['vertical_image_policy']['maximum_group_height_fraction'] == .5
    assert planned['direction_decisions']['module_0']['vertical_height_capped_visual_ids']
    # Freeze directions, then vary both dimensions as later layout search does.
    state['editorial_composition'] = {'version': 'editorial_module_composition_v1',
                                     'modules': planned['modules']}
    section = baseline['board']['spatial_content_plan']['sections'][0]
    agent = LayoutAgent()
    for width, height in [(15, 12), (12, 8), (20, 16)]:
        box = geometry.dimensions(agent, section, width, height, state, VERTICAL)
        elements = agent._create_section_elements(section, 2, 3, width, state, height)
        visuals = [e for e in elements if e['type'] == 'visual']
        for actual, expected in zip(visuals, box['visuals']):
            assert actual['width'] == pytest.approx(expected['width'])
            assert actual['height'] == pytest.approx(expected['height'])
            assert actual['y'] == pytest.approx(3+box['title_height']+expected['y'])
        text = next(e for e in elements if e['type'] == 'text')
        assert text['y'] == pytest.approx(3+box['text_y'])
    # Fast ranking must add the SAME fixed stack to its approximate body.
    state.pop('editorial_composition')
    import src.layout.module_composition as composition
    monkeypatch.setattr(composition, 'fast_body_height', lambda *a: 1.0)
    fast = measure(state, raw, zones, exact=False)
    frame = planned['frames'][0]
    assert fast['report']['modules'][0]['intrinsic_height'] == pytest.approx(
        1+frame['body_frame']['y']-frame['module_frame']['y'])


def test_minimum_height_feedback_uses_group_cap_at_the_new_height(tmp_path):
    state, raw, _ = fixture(tmp_path, [1, 1])
    zones = deepcopy(list(LayoutFamilyRegistry().get('classic_three_column').zones))
    planned = geometry.prepare_geometry(state, skeleton(plan_for(raw)), zones)
    state['editorial_authoring_geometry'] = planned
    raw['modules'][0]['entries'][0]['text'] *= 12
    result = measure(state, raw, zones)
    metric = result['report']['modules'][0]
    assert metric['overage_inches'] > 0
    required = metric['minimum_intrinsic_height']
    section = result['board']['spatial_content_plan']['sections'][0]
    elements = LayoutAgent()._create_section_elements(section, 0, 0, metric['width_inches'], state, required)
    assert max(e['y']+e['height'] for e in elements) == pytest.approx(required, abs=.001)
