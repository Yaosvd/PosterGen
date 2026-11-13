"""Above-prose image rows: strict gains, centering and compiled coordinates."""
from copy import deepcopy

import pytest

from src.agents.layout_agent import LayoutAgent
from src.layout import authoring_geometry as geometry
from src.layout.editorial_composition import VERTICAL
from src.layout.editorial_layout import measure
from src.layout.families import LayoutFamilyRegistry
from src.layout.measurement_context import measurement_scope
from src.workflow.editorial_authoring import skeleton
from src.workflow.editorial_contract import make_board
from test_editorial_generation import plan_for
from test_vertical_visual_caps import fixture


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


@pytest.mark.parametrize('offset,layout', [(-.01, 'horizontal_row'), (0, 'vertical_stack'),
                                          (.01, 'vertical_stack')])
def test_width_trigger_is_strictly_below_sixty_percent(tmp_path, offset, layout):
    # A=10, stack images are 2.85 high. The widest hits 60% of W=20.
    state, _, section = fixture(tmp_path, [(12+offset)/2.85, .5])
    result = geometry.vertical_visual_plan(LayoutAgent(), section, 20, 10, state)
    assert result['image_group_layout'] == layout
    assert result['image_group_decision']['attempted'] == (offset < 0)


@pytest.mark.parametrize('aspect', [4, 19.4/5.4])
def test_crowded_row_or_equal_size_keeps_stack(tmp_path, aspect):
    state, _, section = fixture(tmp_path, [aspect]*3)
    result = geometry.vertical_visual_plan(LayoutAgent(), section, 20, 10, state)
    decision = result['image_group_decision']
    assert decision['attempted']
    assert decision['uniform_scale'] <= 1+1e-9
    assert decision['reason'] == 'not_every_image_larger'
    assert result['visuals'] == geometry.vertical_visuals(LayoutAgent(), section, 20, 10, state)


def test_unequal_images_are_centered_inside_the_row_and_group(tmp_path):
    state, _, section = fixture(tmp_path, [.5, .7, 12])
    agent = LayoutAgent()
    stacked = geometry.vertical_visuals(agent, section, 30, 10, state)
    result = geometry.vertical_visual_plan(agent, section, 30, 10, state)
    assert result['image_group_layout'] == 'horizontal_row'
    rows = result['visuals']; group_height = result['visual_height']
    assert rows[2]['height'] < rows[0]['height']
    assert rows[2]['y'] > 0
    assert [r['y']+r['height']/2 for r in rows] == pytest.approx([group_height/2]*3)
    assert rows[0]['x'] == pytest.approx(30-rows[-1]['x']-rows[-1]['width'])
    assert rows[-1]['x']+rows[-1]['width'] == pytest.approx(30)  # width cap binds
    assert group_height < 4
    for before, after in zip(stacked, rows):
        assert before['visual_id'] == after['visual_id']
        assert after['width'] > before['width'] and after['height'] > before['height']
        assert after['width']/before['width'] == pytest.approx(result['image_group_decision']['uniform_scale'])
        assert after['width']/after['height'] == pytest.approx(before['width']/before['height'])
    for first, second in zip(rows, rows[1:]):
        assert second['x']-first['x']-first['width'] == pytest.approx(.3)
    assert result['image_group_decision']['row_body_height'] >= result['image_group_decision']['stack_body_height']


def test_real_poster_aspects_hit_height_cap_and_keep_side_margins_equal(tmp_path):
    state, _, section = fixture(tmp_path, [1137/229, 665/344])
    width, available = 35.657884, 11.57795321637427
    result = geometry.vertical_visual_plan(LayoutAgent(), section, width, available, state)
    decision = result['image_group_decision']; rows = result['visuals']
    assert result['image_group_layout'] == 'horizontal_row'
    assert decision['stack_width_fraction'] == pytest.approx(.4627540154885938)
    assert decision['uniform_scale'] == pytest.approx(1.3935129218949884)
    assert result['visual_height'] == pytest.approx(.4*available)
    assert decision['row_width']/width == pytest.approx(.9043396427687133)
    assert rows[0]['x'] > 0
    assert rows[0]['x'] == pytest.approx(width-rows[-1]['x']-rows[-1]['width'])
    assert decision['row_body_height']-decision['stack_body_height'] == pytest.approx(.2*available)


def test_body_space_guard_rejects_an_oversized_row(tmp_path, monkeypatch):
    state, _, section = fixture(tmp_path, [.1, .1])
    monkeypatch.setattr(geometry, 'VERTICAL_ROW_HEIGHT_FRACTION', .8)
    result = geometry.vertical_visual_plan(LayoutAgent(), section, 30, 10, state)
    assert result['image_group_layout'] == 'vertical_stack'
    assert result['image_group_decision']['reason'] == 'body_space_reduced_or_nonpositive'


def test_fixed_horizontal_gaps_cannot_create_negative_images(tmp_path):
    state, _, section = fixture(tmp_path, [.001]*3)
    result = geometry.vertical_visual_plan(LayoutAgent(), section, .3, 10, state)
    assert result['image_group_decision']['reason'] == 'row_gaps_exceed_width'
    assert all(r['width'] > 0 and r['height'] > 0 for r in result['visuals'])


def test_prewrite_fast_exact_and_resized_frames_use_the_same_group(tmp_path, monkeypatch):
    state, raw, _ = fixture(tmp_path, [.2, .3])
    zones = list(LayoutFamilyRegistry().get('classic_three_column').zones)
    planned = geometry.prepare_geometry(state, skeleton(plan_for(raw)), zones)
    frame = planned['frames'][0]
    assert frame['body_layout'] == VERTICAL
    assert frame['image_group_layout'] == 'horizontal_row'
    state['editorial_authoring_geometry'] = planned
    exact = measure(state, raw, zones)
    geometry.assert_initial_frames(planned, exact)
    tampered = deepcopy(exact)
    next(e for e in tampered['layout'] if e['type'] == 'visual')['y'] += .2
    with pytest.raises(ValueError, match='image positions'):
        geometry.assert_initial_frames(planned, tampered)
    import src.layout.module_composition as composition
    monkeypatch.setattr(composition, 'fast_body_height', lambda *a: 1.0)
    fast = measure(state, raw, zones, exact=False)
    assert fast['report']['modules'][0]['intrinsic_height'] == pytest.approx(
        1+frame['body_frame']['y']-frame['module_frame']['y'])
    section = exact['board']['spatial_content_plan']['sections'][0]
    agent = LayoutAgent()
    layouts = []
    for width, height in [(30, 12), (8, 60)]:
        box = geometry.dimensions(agent, section, width, height, state, VERTICAL)
        layouts.append(box['image_group_layout'])
        elements = agent._create_section_elements(section, 2, 3, width, state, height)
        images = [e for e in elements if e['type'] == 'visual']
        for actual, expected in zip(images, box['visuals']):
            assert actual['x'] == pytest.approx(2+box['padding']+expected['x'])
            assert actual['y'] == pytest.approx(3+box['title_height']+expected['y'])
            assert actual['width'] == pytest.approx(expected['width'])
            assert actual['height'] == pytest.approx(expected['height'])
        body = next(e for e in elements if e['type'] == 'text')
        assert body['y'] == pytest.approx(3+box['text_y'])
        assert max(e['y']+e['height'] for e in images)+.3 == pytest.approx(body['y'])
    assert layouts == ['horizontal_row', 'vertical_stack']


def test_compiler_uses_maximum_row_bottom_not_the_last_short_image(tmp_path):
    state, raw, _ = fixture(tmp_path, [.5, .7, 12])
    section = make_board(raw)['spatial_content_plan']['sections'][0]
    section['section_title'] = ''
    state['editorial_authoring_geometry'] = {'version': geometry.VERSION,
                                            'modules': {section['section_id']: VERTICAL}}
    agent = LayoutAgent()
    box = geometry.dimensions(agent, section, 30.6, 10, state, VERTICAL)
    assert box['image_group_layout'] == 'horizontal_row'
    elements = agent._create_section_elements(section, 2, 3, 30.6, state, 10)
    images = [e for e in elements if e['type'] == 'visual']
    assert images[-1]['y']+images[-1]['height'] < max(e['y']+e['height'] for e in images)
    body = next(e for e in elements if e['type'] == 'text')
    assert body['y'] == pytest.approx(max(e['y']+e['height'] for e in images)+.3)
    assert [e['y']+e['height']/2 for e in images] == pytest.approx([images[0]['y']+images[0]['height']/2]*3)
    # The actual PPTX writer must preserve the offset instead of aligning all
    # picture tops or re-fitting them independently.
    from PIL import Image
    from pptx import Presentation
    from src.agents.renderer import Renderer
    for index, size in enumerate([(100, 200), (140, 200), (1200, 100)]):
        path = tmp_path/f'visual_{index}.png'
        Image.new('RGB', size, color='white').save(path)
        state['tables'][str(index)]['path'] = str(path)
    state['styled_layout'] = elements
    output = tmp_path/'centered.pptx'
    renderer = Renderer()
    renderer.styling_interfaces = renderer._load_styling_interfaces(state)
    renderer._render_presentation(state, output)
    pictures = [s for s in Presentation(output).slides[0].shapes if hasattr(s, 'image')]
    assert len(pictures) == 3
    centers = [(p.top+p.height/2)/914400 for p in pictures]
    assert centers == pytest.approx([images[0]['y']+images[0]['height']/2]*3, abs=2/914400)
    for picture, expected in zip(pictures, images):
        assert picture.left/914400 == pytest.approx(expected['x'], abs=2/914400)
        assert picture.width/914400 == pytest.approx(expected['width'], abs=2/914400)


def test_height_feedback_recompiles_an_unequal_image_row_at_the_required_height(tmp_path):
    state, raw, _ = fixture(tmp_path, [.5, .7, 12])
    state.update(poster_width=100, poster_height=16)
    zones = list(LayoutFamilyRegistry().get('classic_three_column').zones)
    planned = geometry.prepare_geometry(state, skeleton(plan_for(raw)), zones)
    assert planned['frames'][0]['image_group_layout'] == 'horizontal_row'
    state['editorial_authoring_geometry'] = planned
    raw['modules'][0]['entries'][0]['text'] *= 24
    result = measure(state, raw, zones)
    metric = result['report']['modules'][0]
    assert metric['overage_inches'] > 0
    required = metric['minimum_intrinsic_height']
    section = result['board']['spatial_content_plan']['sections'][0]
    elements = LayoutAgent()._create_section_elements(section, 0, 0, metric['width_inches'], state, required)
    assert max(e['y']+e['height'] for e in elements) == pytest.approx(required, abs=.001)
