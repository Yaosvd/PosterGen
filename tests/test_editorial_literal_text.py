"""Literal scientific symbols survive both compiled and styled freeze checks."""
from copy import deepcopy

import pytest

from test_editorial_generation import state_for, draft_for, install
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import assert_editorial_ready
from src.layout.editorial_layout import measure
from src.agents.font_agent import FontAgent


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    # Literal stars are scientific notation, not author-supplied style markup.
    text = (r'Weights w_i* ≥ w_j*; a*b*c; lone*; **literal**; \alpha; C:\work. '
            'The prediction is 97 percent.\nA second line keeps its symbols.')
    state = state_for(tmp_path, text=text)
    install(state, draft_for(state))
    pipeline.charge(state, 'curator', 'offline_literal_fixture')
    monkeypatch.setattr(pipeline, 'fit', lambda s, c, z: measure(s, c, z))
    monkeypatch.setattr(pipeline, 'edit', lambda *args: False)
    pipeline.editorial_joint_node(state)
    pipeline.editorial_compile_node(state)
    return state


def style(state):
    agent = object.__new__(FontAgent)
    agent.name = 'font_agent'
    keywords = {'section_keywords': {
        m['module_id']: {'bold': ['prediction'], 'italic': ['second'],
                         'bold_contrast': ['percent']}
        for m in state['editorial_candidate']['modules']}}
    state['styled_layout'] = agent._apply_styling(
        state['design_layout'], state['color_scheme'], keywords, state)


def test_full_freeze_checks_preserve_literals_and_real_styles(frozen):
    assert_editorial_ready(frozen, compiled=True)
    original = deepcopy(frozen['design_layout'])
    style(frozen)
    assert frozen['design_layout'] == original
    body = next(e['content'] for e in frozen['styled_layout'] if e.get('type') == 'text')
    assert r'w_i\*' in body and '**prediction**' in body
    assert '*second*' in body and '<color:' in body
    assert_editorial_ready(frozen, compiled=True)


@pytest.mark.parametrize('styled', [False, True])
def test_actual_content_and_ownership_mutations_still_fail(frozen, styled):
    if styled:
        style(frozen)
    key = 'styled_layout' if styled else 'design_layout'
    original = deepcopy(frozen[key])
    for mutation in ('star', 'number', 'inequality', 'title', 'ownership'):
        frozen[key] = deepcopy(original)
        body = next(e for e in frozen[key] if e.get('type') == 'text')
        if mutation == 'star':
            body['content'] = body['content'].replace(r'\*' if styled else '*', '', 1)
        elif mutation == 'number':
            body['content'] = body['content'].replace('97', '98')
        elif mutation == 'inequality':
            body['content'] = body['content'].replace('≥', '>')
        elif mutation == 'title':
            next(e for e in frozen[key] if e.get('type') == 'section_title')['section_title'] = 'Changed'
        else:
            body['section_id'] = 'unknown'
        with pytest.raises(ValueError):
            assert_editorial_ready(frozen, compiled=True)


def test_unescaped_scientific_stars_are_not_accepted_as_styled_text(frozen):
    # Layout provenance controls the grammar, not an asterisk heuristic.
    frozen['styled_layout'] = deepcopy(frozen['design_layout'])
    with pytest.raises(ValueError, match='Renderer-visible'):
        assert_editorial_ready(frozen, compiled=True)


def test_real_pptx_preserves_scientific_stars_alongside_emphasis(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from src.agents.renderer import Renderer
    original = 'Weights w* ≥ v*; literal *stars*; prediction 97.'
    agent = object.__new__(FontAgent)
    styled = agent._apply_keyword_highlighting(
        agent._escape_formatting_literals(original), {'bold': ['prediction']}, {})
    ppt = Presentation()
    slide = ppt.slides.add_slide(ppt.slide_layouts[6])
    paragraph = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(12), Inches(3)).text_frame.paragraphs[0]
    Renderer()._parse_and_add_runs(paragraph, styled, 'Arial', Pt(44), RGBColor(0, 0, 0))
    path = tmp_path/'literal-stars.pptx'
    ppt.save(path)
    reopened = Presentation(path).slides[0].shapes[0].text_frame.paragraphs[0]
    assert reopened.text == original
    assert any(run.text == 'prediction' and run.font.bold for run in reopened.runs)
