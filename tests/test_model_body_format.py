"""Model-authored formatting: no double decoration, shared measurement/rendering."""
from copy import deepcopy

import pytest
from pptx import Presentation
from pptx.util import Inches

from utils.model_body import FORMAT, encode_line, formatting_errors, paragraphs, visible
from utils.text_formatting import tokenize_styling
from src.layout.body_presentation import paragraphs as section_paragraphs, paragraph_text
from src.layout.editorial import presentation_line_count
from src.layout.editorial_text import formula_plan
from src.workflow.editorial_contract import normalize_candidate, make_board, EditorialStructureError
from src.layout.families import LayoutFamilyRegistry
from src.agents.font_agent import FontAgent
from src.agents.renderer import Renderer
from test_editorial_generation import state_for, draft_for, install


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected live model'))


@pytest.mark.parametrize('source,plain,bold', [
    ('1) **Prediction:** w_i* ≥ w_j*; a*b*c; lone*.', '1) Prediction: w_i* ≥ w_j*; a*b*c; lone*.', ['Prediction:']),
    ('**w* ≥ v***', 'w* ≥ v*', ['w* ≥ v*']),
    (r'$x**2$; $$**x**$$; \(w*\); \[**a**\]; **Result**', r'$x**2$; $$**x**$$; \(w*\); \[**a**\]; Result', ['Result']),
    (r'x**2; C:\work; \alpha; *literal*; **unclosed', r'x**2; C:\work; \alpha; *literal*; **unclosed', []),
    ('<color:#ff0000>literal</color>', '<color:#ff0000>literal</color>', []),
])
def test_limited_bold_grammar_preserves_scientific_symbols(source, plain, bold):
    runs = tokenize_styling(encode_line(source))
    assert ''.join(r['text'] for r in runs) == plain == visible(source)
    assert [r['text'] for r in runs if r['bold']] == bold
    assert not any(r['italic'] or r['color'] for r in runs)


@pytest.mark.parametrize('text,style,reason', [
    ('1) 1. Collect drafts.', 'steps', 'Repeated list marker'),
    ('**1)** 1. Collect drafts.', 'steps', 'Repeated list marker'),
    ('• • Findings.', 'topics', 'Repeated list marker'),
    ('1) First.\n3) Third.', 'steps', 'consecutively'),
    ('1. First.\n1. Duplicate.', 'steps', 'consecutively'),
    ('  ◦ Orphan support.', 'topics', 'follow a main'),
])
def test_invalid_explicit_format_is_diagnosed_without_mutating_text(text, style, reason):
    entries = [{'item_id': 'e', 'text': text}]; original = deepcopy(entries)
    assert any(reason in error for _, error in formatting_errors(entries, style))
    assert entries == original


def test_real_numbers_and_nested_step_numbers_are_not_duplicate_markers():
    entries = [{'item_id': 'e', 'text':
        '1) 1.5× speedup; −0.2 difference.\n  ◦ 92% precision; recall 2%.\n  1) Local detail.\n2. 3.9K examples.'}]
    assert formatting_errors(entries, 'steps') == []


def test_authored_numbering_never_gets_a_second_program_number(tmp_path):
    state = state_for(tmp_path); raw = draft_for(state)
    lines = [
        '1. Collect CS paper drafts, reviews, and revisions from OpenReview; extract paragraph-level edits.',
        '2. Match comment-edit pairs at 92% precision; recall is low (2% on hand-labeled data).',
        "3. Expert-annotate a gold test set of 196 comments (Cohen's κ = 0.8).",
    ]
    raw['modules'][0].update(presentation_style='steps',
        entries=[{'item_id': f'e{i}', 'text': line} for i, line in enumerate(lines)])
    candidate = normalize_candidate(raw, state, LayoutFamilyRegistry().get('classic_three_column').zones)
    section = make_board(candidate)['spatial_content_plan']['sections'][0]
    assert section['body_format'] == FORMAT
    assert [paragraph_text(p) for p in section_paragraphs(section)] == lines
    raw['modules'][0]['entries'].pop(1)
    with pytest.raises(EditorialStructureError, match='consecutively'):
        normalize_candidate(raw, state, LayoutFamilyRegistry().get('classic_three_column').zones)


def test_capacity_deletion_requires_authored_renumbering_with_one_shared_repair(monkeypatch, tmp_path):
    from src.workflow import editorial_pipeline as pipeline
    from src.workflow.editorial_requests import request
    from test_editorial_generation import capacity_reply
    from test_editorial_field_repair import model
    state = state_for(tmp_path); raw = draft_for(state)
    raw['modules'][0].update(presentation_style='steps', entries=[
        {'item_id': 'collect', 'text': '1) Collect pairs at 92% precision with 2% recall.'},
        {'item_id': 'evaluate', 'text': '2) Evaluate 196 comments.'},
        {'item_id': 'limit', 'text': '3) Retain the annotation condition.'}])
    install(state, raw)
    changed = deepcopy(state['editorial_candidate']['modules'][0])
    changed['entries'].pop(1)
    patch = capacity_reply([changed])
    calls = model(monkeypatch, [patch, {'repairs': {'field_0': '2) Retain the annotation condition.'}}])
    repaired = request(state, 'editorial_balancer', {}, pipeline.PATCH,
        directory='editorial/numbering', validator=lambda p: pipeline.merge_patch(state, p))
    assert len(calls) == 2
    assert repaired['modules'][0]['entries'][0] == changed['entries'][0]
    assert repaired['modules'][0]['entries'][1]['text'] == '2) Retain the annotation condition.'
    assert request(state, 'editorial_balancer', {}, pipeline.PATCH,
        directory='editorial/numbering', validator=lambda p: pipeline.merge_patch(state, p)) == repaired
    assert len(calls) == 2  # Durable replay cannot purchase another format request.


def test_font_agent_skips_keyword_call_and_preserves_authored_emphasis(monkeypatch, tmp_path):
    from src.workflow import editorial_pipeline as pipeline
    from src.layout.editorial_layout import measure
    state = install(state_for(tmp_path))
    pipeline.charge(state, 'curator', 'offline_authored_format')
    monkeypatch.setattr(pipeline, 'fit', lambda s, c, z: measure(s, c, z))
    monkeypatch.setattr(pipeline, 'edit', lambda *a: False)
    pipeline.editorial_joint_node(state); pipeline.editorial_compile_node(state)
    monkeypatch.setattr(FontAgent, '_identify_keywords', lambda *a: pytest.fail('Extra keyword request'))
    before = [e['content'] for e in state['design_layout'] if e.get('type') == 'text']
    FontAgent()(state)
    assert not state['errors']
    assert state['keywords'] == {'section_keywords': {}}
    assert [e['content'] for e in state['styled_layout'] if e.get('type') == 'text'] == before
    from src.workflow.editorial_contract import assert_editorial_ready
    assert_editorial_ready(state, compiled=True)
    body = next(e for e in state['styled_layout'] if e.get('type') == 'text')
    body['editorial_paragraphs'] = deepcopy(body['editorial_paragraphs'])
    body['editorial_paragraphs'][1]['indent_inches'] = 0
    with pytest.raises(ValueError, match='body formatting'):
        assert_editorial_ready(state, compiled=True)


def test_bold_and_indentation_are_measured_and_cached_consistently():
    from src.layout.measurement_context import measurement_scope
    cases = ['WW WW WW WW WW WW', '**WW WW WW WW WW WW**', '    **WW WW WW WW WW WW**']
    def count(text):
        rows = paragraphs(text)
        return presentation_line_count('\n'.join(p['text'] for p in rows), 3.0, 'Arial', 44, rows)
    plain, bold, nested = [count(text) for text in cases]
    assert nested > bold >= plain
    with measurement_scope({'enabled': True}):
        assert [count(text) for text in cases] == [plain, bold, nested]
        assert [count(text) for text in cases] == [plain, bold, nested]


def test_formula_blocks_retain_original_indent_even_for_repeated_visible_lines():
    source = 'Same text.\n  Same text.\n  ◦ **Training:** ε(α) = α/2.\nSame text.'
    rows = paragraphs(source)
    plan = formula_plan('\n'.join(p['text'] for p in rows), 16, 'Arial', 44,
                        description=rows, styled=True)
    first, prefix, formula, last = plan['blocks']
    assert [p['indent_inches'] for p in first['paragraphs']] == [0, .30]
    assert prefix['paragraphs'][0]['indent_inches'] == formula['indent_inches'] == .30
    assert last['paragraphs'][0]['indent_inches'] == 0


def test_real_editable_pptx_has_authored_markers_bold_and_exact_indentation(tmp_path):
    source = '1) **Encode:** w_i* ≥ w_j*.\n  ◦ Keep the condition.\n2) Observe 3.9K items.\n    Further explanation.'
    rows = paragraphs(source)
    presentation = Presentation(); presentation.slide_width = Inches(18)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    renderer = Renderer(); renderer.styling_interfaces = FontAgent().get_styling_interfaces()
    renderer._add_enhanced_textbox(slide, '\n'.join(p['text'] for p in rows),
        Inches(1), Inches(1), Inches(16), Inches(6), 'Arial', 44, '#000000', 1,
        editorial=True, description=rows)
    path = tmp_path/'model-body.pptx'; presentation.save(path)
    frame = Presentation(path).slides[0].shapes[0].text_frame
    texts = [p.text for p in frame.paragraphs]
    assert texts == ['1) Encode: wi* ≥ wj*.', '◦ Keep the condition.', '2) Observe 3.9K items.', 'Further explanation.']
    assert any(r.text == 'Encode:' and r.font.bold for r in frame.paragraphs[0].runs)
    for paragraph, inset in zip(frame.paragraphs, [0, .30, 0, .60]):
        props = paragraph._p.get_or_add_pPr()
        assert props.get('marL') == str(Inches(inset))
        assert props.find('{http://schemas.openxmlformats.org/drawingml/2006/main}buNone') is not None
        assert not paragraph._p.xpath('.//a:buAutoNum')
