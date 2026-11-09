"""Wide-band eligibility, measured benefit, and immutable 40% image allocation."""
from copy import deepcopy

import pytest

from src.layout import authoring_geometry as geometry
from src.layout.editorial_composition import HORIZONTAL, VERTICAL
from src.layout.editorial_layout import family_brief, measure
from src.layout.families import LayoutFamilyRegistry
from src.layout.measurement_context import measurement_scope
from src.agents.layout_agent import LayoutAgent
from src.workflow.editorial_authoring import setup_geometry_style, skeleton
from test_editorial_generation import state_for, draft_for, plan_for


@pytest.mark.parametrize('width,height,eligible', [
    (26, 8, True), (25.999, 8, False), (30, 10, True),
    (30, 10.001, False), (52, 20, False), (52, 10, True),
])
def test_half_of_effective_board_and_aspect_three_are_both_required(width, height, eligible):
    assert geometry.horizontal_candidate_eligible(width, height, 52) is eligible


def box(widths, body_height):
    return {'mode': None, 'text_width': 11, 'text_height_available': body_height,
            'text_y': 1, 'title_height': 1, 'padding': .3,
            'visual_height': sum(widths)/100 + .3*(len(widths)-1),
            'visuals': [{'visual_id': str(i), 'width': w, 'height': w/100}
                        for i, w in enumerate(widths)]}


@pytest.mark.parametrize('ratios,vheight,hheight,mode,reason', [
    ([1.3], 10, 9, HORIZONTAL, 'larger_images_with_body_capacity'),
    ([1.299], 10, 9, VERTICAL, 'vertical_preferred_no_clear_gain'),
    ([1.3], 10, 8, VERTICAL, 'vertical_preferred_no_clear_gain'),
    ([1.3, 1.1], 10, 9, HORIZONTAL, 'larger_images_with_body_capacity'),
    ([1.5, .99], 10, 9, VERTICAL, 'horizontal_shrinks_image'),
    ([1.1], 10, 10, VERTICAL, 'vertical_preferred_no_clear_gain'),
    ([1.0], 1, 9, HORIZONTAL, 'horizontal_restores_body_space'),
    ([.99], 1, 9, VERTICAL, 'horizontal_shrinks_image'),
    ([1.3], 10, 1, VERTICAL, 'horizontal_infeasible'),
    ([1.3], 1, 1, VERTICAL, 'horizontal_infeasible'),
])
def test_benefit_requires_capacity_and_individual_image_preservation(
        monkeypatch, ratios, vheight, hheight, mode, reason):
    # Controlled candidate geometry; real reference calculator gives 100 vs90
    # words for ten vs nine lines. No actual-prose or model output is involved.
    boxes = {VERTICAL: box([10]*len(ratios), vheight),
             HORIZONTAL: box([10*r for r in ratios], hheight)}
    for key, value in boxes.items():
        value['mode'] = key
    monkeypatch.setattr(geometry, 'dimensions', lambda *args: deepcopy(boxes[args[-1]]))
    density = {'font_size_pt': 72, 'body_reserve_inches': 0, 'line_height_inches': 1,
               'reference_word_width_inches': 1, 'word_safety_factor': 1}
    selected, decision = geometry.select_direction(None, {'visual_assets': [1]}, 30, 10, 52, {}, density)
    assert selected['mode'] == mode
    assert decision['reason'] == reason
    if vheight == 10 and hheight == 9:
        assert decision['body_capacity_retention'] == .9


def test_narrow_module_cannot_bypass_gate_when_vertical_is_infeasible(monkeypatch):
    calls = []
    def dimension(*args):
        calls.append(args[-1])
        value = box([10], 1); value['mode'] = VERTICAL
        return value
    monkeypatch.setattr(geometry, 'dimensions', dimension)
    selected, decision = geometry.select_direction(None, {'visual_assets': [1]}, 25, 8, 52, {},
        {'font_size_pt': 72, 'body_reserve_inches': 0, 'line_height_inches': 1,
         'reference_word_width_inches': 1, 'word_safety_factor': 1})
    assert calls == [VERTICAL]
    assert selected['mode'] == VERTICAL
    assert decision['candidates'][VERTICAL]['issues']
    assert decision['reason'] == 'outside_horizontal_band'


def test_central_band_only_and_compilation_preserves_40_percent(tmp_path):
    state = state_for(tmp_path, 'central_evidence_band')
    raw = draft_for(state)
    state['images'] = {str(i): {'aspect': 3.24} for i in range(len(raw['modules']))}
    for i, module in enumerate(raw['modules']):
        module['visual_ids'] = [f'figure_{i}']
    plan = plan_for(raw); setup_geometry_style(state, plan)
    zones = list(LayoutFamilyRegistry().get('central_evidence_band').zones)
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        result = geometry.prepare_geometry(state, skeleton(plan), zones)
        assert not result['failures']
        modes = [f['body_layout'] for f in result['frames']]
        assert modes == [VERTICAL, VERTICAL, HORIZONTAL, VERTICAL, VERTICAL, VERTICAL]
        assert result['direction_policy']['minimum_board_width_fraction'] == .50
        assert result['image_width_fraction'] == .40
        state['editorial_authoring_geometry'] = result
        measured = measure(state, raw, zones)
        geometry.assert_initial_frames(result, measured)
        section = measured['board']['spatial_content_plan']['sections'][2]
        from src.layout.module_composition import side_by_side_plan
        # After selection the direction stays locked, even below aspect3/50%.
        for width, height in [(52, 10), (26, 8), (15, 14), (50, 3)]:
            horizontal = side_by_side_plan(LayoutAgent(), section, width, height, state)
            assert horizontal is not None
            assert all(r['width'] <= .40*(width-.6)+1e-9 for r in horizontal['visuals'])
    brief = family_brief(state, zones)
    assert [z['horizontal_image_text_possible'] for z in brief['zones']] == [False, False, True, False, False, False]


def test_wider_image_candidate_is_not_permission_to_exceed_40_percent(tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    state['images'] = {'1': {'aspect': 10}, '2': {'aspect': .5}}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['figure_1', 'figure_2']
    plan = plan_for(raw); setup_geometry_style(state, plan)
    from src.workflow.editorial_contract import make_board
    section = make_board(skeleton(plan))['spatial_content_plan']['sections'][0]
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        selected, decision = geometry.select_direction(LayoutAgent(), section, 52, 10, 52,
                                                       state, geometry._density(LayoutAgent(), state))
    horizontal = decision['candidates'][HORIZONTAL]
    assert all(r['width'] <= .4*(52-.6) for r in horizontal['visuals'])
    assert decision['reason'] == 'horizontal_shrinks_image'
    assert selected['mode'] == VERTICAL
