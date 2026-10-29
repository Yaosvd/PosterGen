"""Small offline checks for measured image-left/text-right module composition."""
from copy import deepcopy
import shutil
import subprocess

from PIL import Image
from pptx import Presentation
import pytest

from src.agents.layout_agent import LayoutAgent
from src.agents.renderer import Renderer
from src.layout.feasibility import _estimate_section_height, validate_intra_section_layout
from src.layout.module_composition import side_by_side_plan


def sample():
    section = {'section_id': 'method', 'layout_zone_id': 'band', 'section_title': 'Search Method',
        'text_content': ['The search policy selects a region, then selects a parcel within that region. '
                         'A shared prediction module updates risk estimates after each observation. '
                         'The remaining budget determines which locations can be queried next.'],
        'visual_assets': [{'visual_id': 'figure_1'}]}
    state = {'generation_route': 'optimization_family', 'styling_interfaces': {},
             'images': {'1': {'aspect': 2.0}}, 'tables': {},
             'section_title_design': {'section_title_design': {
                 'section_applications': [{'section_id': 'method'}]}}}
    return section, state


def test_wide_module_uses_same_row_and_fast_estimate_covers_exact_height():
    agent = LayoutAgent()
    section, state = sample()
    before = deepcopy(section)
    elements = agent._create_section_elements(section, 1, 2, 36, state, 10)
    visual = next(e for e in elements if e['type'] == 'visual')
    text = next(e for e in elements if e['type'] == 'text')
    assert visual['y'] == pytest.approx(text['y'])
    assert visual['x'] + visual['width'] + .29 <= text['x']
    assert visual['width'] / visual['height'] == pytest.approx(2.0)
    assert text['x'] + text['width'] <= 37
    assert text['content'] == section['text_content'][0]
    exact = max(e['y'] + e['height'] for e in elements) - 2
    parts = {}
    estimate = _estimate_section_height(agent, section, zone_width=36, zone_height=10,
                                       state=state, components=parts)
    assert exact <= estimate <= 10
    assert parts['body_layout'] == 'image_left_text_right'
    container = {'type': 'section_container', 'section_id': 'method', 'zone_id': 'band',
                 'x': 1, 'y': 2, 'width': 36, 'height': exact}
    assert not validate_intra_section_layout([container, *elements])
    assert section == before


@pytest.mark.parametrize('width,height,route', [
    (12, 22, 'optimization_family'), (36, 10, 'standalone_classic'),
    (7, 3, 'optimization_family'),
])
def test_unsuitable_or_classic_module_keeps_vertical_flow(width, height, route):
    section, state = sample()
    state['generation_route'] = route
    agent = LayoutAgent()
    assert side_by_side_plan(agent, section, width, height, state) is None
    elements = agent._create_section_elements(section, 1, 1, width, state, height)
    visual = next(e for e in elements if e['type'] == 'visual')
    text = next(e for e in elements if e['type'] == 'text')
    assert text['y'] >= visual['y'] + visual['height']


@pytest.mark.parametrize('missing', ['text_content', 'visual_assets'])
def test_single_medium_does_not_create_a_second_column(missing):
    section, state = sample()
    section[missing] = []
    assert side_by_side_plan(LayoutAgent(), section, 36, 10, state) is None


def test_multiple_images_keep_order_on_left():
    section, state = sample()
    section['visual_assets'].append({'visual_id': 'figure_2'})
    state['images']['2'] = {'aspect': 3.0}
    elements = LayoutAgent()._create_section_elements(section, 1, 1, 36, state, 12)
    images = [e for e in elements if e['type'] == 'visual']
    text = next(e for e in elements if e['type'] == 'text')
    assert [v['visual_id'] for v in images] == ['figure_1', 'figure_2']
    assert images[1]['y'] >= images[0]['y'] + images[0]['height']
    assert all(v['x'] + v['width'] < text['x'] for v in images)
    assert text['y'] == images[0]['y']


def test_real_editable_pptx_and_rendered_text_fit(tmp_path):
    if not shutil.which('libreoffice'):
        pytest.skip('LibreOffice not installed')
    import pymupdf
    from src.layout.render_fit import evaluate_rendered_boxes
    section, state = sample()
    image_path = tmp_path / 'figure.png'
    Image.new('RGB', (1000, 500), '#4f83b5').save(image_path)
    state['images']['1']['path'] = str(image_path)
    agent = LayoutAgent()
    elements = agent._create_section_elements(section, 1, 1, 36, state, 10)
    presentation = Presentation()
    from pptx.util import Inches
    presentation.slide_width, presentation.slide_height = Inches(38), Inches(12)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    renderer = Renderer()
    from src.agents.font_agent import FontAgent
    renderer.styling_interfaces = FontAgent().get_styling_interfaces()
    for element in elements:
        renderer._render_element(slide, element, state, None)
    pptx = tmp_path / 'horizontal.pptx'
    presentation.save(pptx)
    reopened = Presentation(pptx)
    assert len(reopened.slides[0].shapes) == 4  # accent, editable title, image, editable body
    assert any(s.has_text_frame and section['text_content'][0] in s.text for s in reopened.slides[0].shapes)
    subprocess.run([shutil.which('libreoffice'),
        f'-env:UserInstallation={(tmp_path / "lo-profile").as_uri()}', '--headless',
        '--convert-to', 'pdf:impress_pdf_Export', '--outdir', str(tmp_path), str(pptx)],
        capture_output=True, check=True, timeout=60)
    with pymupdf.open(pptx.with_suffix('.pdf')) as doc:
        report = evaluate_rendered_boxes(elements, doc[0].get_text('blocks'),
                                        poster_width=38, poster_height=12)
        assert report['status'] == 'passed', report
