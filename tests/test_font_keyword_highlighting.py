"""Overlapping model-selected highlights must preserve renderer-visible prose."""
from copy import deepcopy

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from src.agents.font_agent import FontAgent
from src.agents.renderer import Renderer
from utils.text_formatting import tokenize_styling

COLORS = {'text': '#000000', 'contrast': '#133d7f'}


def plain(text):
    return '\n'.join(''.join(run['text'] for run in tokenize_styling(line))
                     for line in text.split('\n'))


def highlight(text, keywords):
    return FontAgent()._apply_keyword_highlighting(
        FontAgent._escape_formatting_literals(text), keywords, COLORS)


def test_bold_phrase_and_italic_subword_do_not_create_nested_markup():
    text = highlight('anti-aliasing', {'bold': ['anti-aliasing'], 'italic': ['alias']})
    assert text == '**anti-aliasing**'
    assert plain(text) == 'anti-aliasing'
    assert tokenize_styling(text)[0]['bold']


@pytest.mark.parametrize('text,keywords', [
    ('Anti-Aliasing', {'bold': ['anti-aliasing'], 'italic': ['ALIAS']}),
    ('MODEL', {'bold_contrast': ['model'], 'bold': ['MODEL'], 'italic': ['Model']}),
    ('anti-alias filter', {'bold': ['anti-alias filter'], 'italic': ['alias']}),
    ('scale equivariance error', {'bold': ['scale equivariance'], 'italic': ['equivariance error']}),
    ('resources', {'bold': ['resources'], 'italic': ['source']}),
    ('literal *star* and \\path; anti-aliasing', {'bold': ['anti-aliasing'], 'italic': ['alias', 'star']}),
    ('λ_i ≤ 0.9889; anti-aliasing', {'bold': ['0.9889', 'anti-aliasing'], 'italic': ['alias']}),
    ('first\nsecond', {'bold': ['first\nsecond']}),
    ('first\nsecond', {'bold_contrast': ['first\nsecond']}),
    ('first\nsecond', {'italic': ['first\nsecond']}),
])
def test_overlaps_case_math_escapes_and_unsupported_multiline_keywords_keep_text(text, keywords):
    before = deepcopy(keywords)
    assert plain(highlight(text, keywords)) == text
    assert keywords == before


def test_disjoint_highlights_are_not_suppressed_by_an_earlier_color():
    styled = highlight('Fourier layers reduce aliasing.',
        {'bold_contrast': ['Fourier'], 'bold': ['layers'], 'italic': ['aliasing']})
    spans = tokenize_styling(styled)
    assert plain(styled) == 'Fourier layers reduce aliasing.'
    assert any(s['text'] == 'Fourier' and s['color'] == '#133d7f' for s in spans)
    assert any(s['text'] == 'layers' and s['bold'] for s in spans)
    assert any(s['text'] == 'aliasing' and s['italic'] for s in spans)


def test_overlapping_phrase_keeps_its_style_and_later_independent_occurrence_can_be_italic():
    styled = highlight('anti-alias filter; alias is a separate word.',
                       {'bold': ['anti-alias filter'], 'italic': ['alias']})
    assert plain(styled) == 'anti-alias filter; alias is a separate word.'
    assert any(s['text'] == 'anti-alias filter' and s['bold'] for s in tokenize_styling(styled))
    assert any(s['text'] == 'alias' and s['italic'] for s in tokenize_styling(styled))


@pytest.mark.parametrize('content', ['**MODEL**', '*MODEL*', '<color:#112233>MODEL</color>'])
def test_existing_style_and_original_case_remain_intact(content):
    agent = FontAgent()
    assert agent._highlight_keyword_in_content(content, 'model', lambda s: '*' + s + '*') == content


def test_word_match_is_not_applied_to_an_earlier_nonword_occurrence():
    styled = highlight('models differ from a model.', {'bold': ['model']})
    assert styled == 'models differ from a **model**.'


def test_described_editorial_paragraphs_keep_labels_and_literals():
    text = 'Ignore anti-aliasing and keep literal * markers.'
    paragraph = {'text': text, 'label': 'Root cause', 'prefix': '• ', 'indent_inches': 0}
    element = {'id': 'm1_text', 'type': 'text', 'editorial_body': True,
        'editorial_paragraphs': [paragraph], 'content': '• Root cause: ' + text}
    original = deepcopy(element)
    FontAgent()._apply_content_styling(element, COLORS,
        {'m1': {'bold': ['anti-aliasing'], 'italic': ['alias']}})
    assert plain(element['content']) == original['content']
    assert element['editorial_paragraphs'] == original['editorial_paragraphs']
    assert '**Root cause:**' in element['content']


def test_real_renderer_writes_original_characters_and_safe_styles_to_pptx(tmp_path):
    original = 'Anti-aliasing prevents alias effects.'
    styled = highlight(original, {'bold': ['Anti-aliasing'], 'italic': ['alias']})
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    paragraph = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(12), Inches(3)).text_frame.paragraphs[0]
    Renderer()._parse_and_add_runs(paragraph, styled, 'Arial', Pt(44), RGBColor(0, 0, 0))
    path = tmp_path / 'overlapping-highlights.pptx'
    presentation.save(path)
    reopened = Presentation(path).slides[0].shapes[0].text_frame.paragraphs[0]
    assert reopened.text == original
    assert any(r.text == 'Anti-aliasing' and r.font.bold for r in reopened.runs)
    assert any(r.text == 'alias' and r.font.italic for r in reopened.runs)
