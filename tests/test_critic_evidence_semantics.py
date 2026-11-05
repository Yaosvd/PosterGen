"""Final evidence semantics against exported artifacts, without any model calls."""
from copy import deepcopy
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches

from src.workflow.critic_evidence import (applied_colors, diagnostic_provenance,
    geometry_view, measurement_view, annotate_gaps)
from src.workflow.editorial_critic import _paper_evidence
from utils.persistence import file_hash


@pytest.fixture
def artifact(tmp_path):
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Inches(54), Inches(36)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    panel = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1), Inches(10), Inches(52), Inches(6))
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor.from_string('E6EAEF')
    panel.line.fill.background()
    layout = []
    for identity, kind, module, y, height in [('poster_title', 'title', '', 1, 4),
            ('m2_text', 'text', 'm2', 14, 3), ('m3_title', 'section_title', 'm3', 17, 1)]:
        shape = slide.shapes.add_textbox(Inches(1.5), Inches(y), Inches(50), Inches(height))
        paragraph = shape.text_frame.paragraphs[0]
        paragraph.text = identity
        paragraph.font.color.rgb = RGBColor(0, 0, 0)
        layout.append({'id': identity, 'type': kind, 'section_id': module,
            'x': 1.5, 'y': y, 'width': 50, 'height': height, 'font_color': '#00FF00'})
    path = tmp_path / 'final.pptx'
    presentation.save(path)
    state = {'design_layout': layout, 'current_candidate': {'pptx_path': str(path)},
             'color_scheme': {'theme': '#8E6F3E', 'text_on_theme': '#FFFFFF', 'mono_light': '#EFEBE6'}}
    return state, presentation, path


def test_final_artifact_resolves_black_title_white_canvas_despite_candidate_palette(artifact):
    state, _, path = artifact
    before, original = deepcopy(state), file_hash(path)
    evidence = applied_colors(state)
    title = next(r for r in evidence['text_elements'] if r['element_id'] == 'poster_title')
    assert evidence['source'] == 'exported_pptx_styles'
    assert evidence['canvas_color'] == '#FFFFFF'
    assert title['foreground_colors'] == ['#000000']  # Artifact beats misleading layout color too.
    assert title['background_colors'] == ['#FFFFFF']
    assert title['style_contrast_pairs'] == [{'foreground': '#000000', 'background': '#FFFFFF', 'ratio': 21}]
    assert evidence['pixel_visibility'] == 'not_verified'
    assert state == before and file_hash(path) == original


def test_partial_panel_fill_keeps_both_backgrounds_without_claiming_per_glyph_pairs(artifact):
    state, _, _ = artifact
    body = next(r for r in applied_colors(state)['text_elements'] if r['element_id'] == 'm2_text')
    assert body['background_colors'] == ['#E6EAEF', '#FFFFFF']
    assert 'not per-glyph' in body['coverage']


def test_actual_nonwhite_canvas_and_white_ink_are_read_from_artifact(artifact):
    state, presentation, path = artifact
    slide = presentation.slides[0]
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string('8E6F3E')
    slide.shapes[1].text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
    presentation.save(path)
    evidence = applied_colors(state)
    assert evidence['canvas_color'] == '#8E6F3E'
    title = evidence['text_elements'][0]
    assert title['foreground_colors'] == ['#FFFFFF']
    assert title['style_contrast_pairs'][0]['ratio'] == pytest.approx(4.673)


@pytest.mark.parametrize('fault', ['missing', 'corrupt', 'ambiguous', 'inherited_ink', 'gradient'])
def test_unavailable_or_unsupported_styles_never_fall_back_to_candidate_palette(artifact, fault):
    state, presentation, path = artifact
    slide = presentation.slides[0]
    if fault == 'missing':path.unlink()
    elif fault == 'corrupt':path.write_bytes(b'not a presentation')
    elif fault == 'ambiguous':
        slide.shapes.add_textbox(Inches(1.5), Inches(1), Inches(50), Inches(4)).text = 'Duplicate'
        presentation.save(path)
    elif fault == 'inherited_ink':
        paragraph = slide.shapes[1].text_frame.paragraphs[0]
        paragraph._p.pPr.remove(paragraph._p.pPr.defRPr)
        presentation.save(path)
    else:
        slide.background.fill.gradient()
        presentation.save(path)
    evidence = applied_colors(state)
    assert evidence['status'] in {'unavailable', 'partial'}
    assert not any(p['foreground'] == '#00FF00' for r in evidence['text_elements'] for p in r['style_contrast_pairs'])
    if fault == 'gradient':assert evidence['canvas_color'] is None


def test_geometry_denominator_is_smaller_title_box_not_body_or_occluded_characters():
    layout = [{'type': 'text', 'section_id': 'm2', 'id': 'm2_text', 'x': 1, 'y': 10, 'width': 50, 'height': 4},
              {'type': 'section_title', 'section_id': 'm3', 'x': 1, 'y': 13.8, 'width': 50, 'height': 1}]
    raw = {'status': 'measured', 'findings': [{'issue_id': 'GEOMETRY-OVERLAP-1-2',
        'location': {'element_ids': ['m2_text', 'm3']},
        'evidence': {'overlap_area_inches_squared': 10, 'overlap_ratio': .2}}]}
    before = deepcopy(raw)
    view = geometry_view(raw, layout)['findings'][0]['evidence']
    assert view['ratio_denominator']['element_ids'] == ['m3_title']
    assert view['ratio_denominator']['area_square_inches'] == 50
    assert view['fraction_of_each_box'] == {'m2_text': .05, 'm3_title': .2}
    assert view['glyph_occlusion'] == 'not_established'
    assert view['element_boxes'][1]['element_type'] == 'section_title'
    assert raw == before


def test_ambiguous_geometry_identity_does_not_invent_denominator():
    layout = [{'type': 'section_title', 'section_id': 'm3', 'x': 0, 'y': 0, 'width': 1, 'height': 1},
              {'type': 'text', 'section_id': 'm3', 'x': 0, 'y': 0, 'width': 2, 'height': 2}]
    raw = {'findings': [{'issue_id': 'GEOMETRY-OVERLAP-0-1', 'location': {'element_ids': ['m3', 'm3']}}]}
    view = geometry_view(raw, layout)['findings'][0]['evidence']
    assert view['ratio_denominator']['status'] == 'unresolved'
    assert 'fraction_of_each_box' not in view


def test_unmatched_text_marks_specific_gap_as_fallback_not_a_glyph_clearance(artifact):
    state, _, _ = artifact
    state['render_fit_report'] = {'status': 'partial', 'conclusive': False,
        'unmatched_text_ids': ['m2_text'], 'matched_text_boxes': [{'element_id': 'm3_title'}], 'issues': []}
    before = deepcopy(state)
    provenance = diagnostic_provenance(state)
    assert provenance['text_bounds']['m2_text']['bounds_basis'] == 'planned_box_fallback'
    assert provenance['text_bounds']['m3_title']['bounds_basis'] == 'rendered_glyph_bounds'
    gap = {'after_section_id': 'm2', 'before_section_id': 'm3', 'gap_inches': .0787}
    annotate_gaps(gap, provenance)
    assert gap['measurement_basis'] == 'includes_planned_text_fallback'
    assert gap['unmatched_text_ids'] == ['m2_text'] and gap['gap_inches'] == .0787
    assert provenance['render_fit_conclusive'] is False and state == before


def test_candidate_contrast_is_separated_from_applied_colors_and_raw_reports_retained(artifact):
    state, _, _ = artifact
    state['critic_measurement_evidence'] = {'color_quality': {'status': 'measured',
        'metadata': {'contrast_ratios': {'text_on_theme_on_theme': 4.673}}, 'findings': [{
            'issue_id': 'COLOR-CONTRAST-INSUFFICIENT', 'evidence': {'failed_pairs': ['legacy']}}]}}
    before = deepcopy(state)
    view = measurement_view(state)
    assert 'color_scheme' not in view
    assert view['candidate_palette']['role'] == 'design_candidates_not_rendered_facts'
    metadata = view['measurements']['color_quality']['metadata']
    assert 'contrast_ratios' not in metadata
    assert metadata['candidate_or_layout_contrast_ratios']['text_on_theme_on_theme'] == 4.673
    assert view['measurements']['color_quality']['findings'][0]['evidence']['rendered_use_verified'] is False
    assert view['applied_colors']['text_elements'][0]['foreground_colors'] == ['#000000']
    assert state == before


def test_original_equation_remains_primary_over_conflicting_auxiliary_summary():
    original = 'Eq. 19: MLP(Pool(IFFT(Pad_N(Phi[k])))). Pad_N acts on the DFT.'
    state = {'raw_text': original, 'marker_raw_text': original,
        'structured_sections': {'paper_sections': [{'content': 'IFFT then pad (incorrect auxiliary summary)'}]},
        'narrative_content': {}, 'classified_visuals': {}, 'images': {}, 'tables': {}}
    before = deepcopy(state)
    paper = _paper_evidence(state)
    assert paper['original_text'] == original
    assert paper['source_priority']['primary'] == ['original_text']
    assert 'structured_sections' in paper['source_priority']['advisory']
    assert paper['structured_sections'] == state['structured_sections']  # No silent summary rewrite.
    assert state == before
