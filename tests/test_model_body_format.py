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
from src.workflow.editorial_contract import normalize_candidate, make_board, preserves_step_numbers
from src.workflow.editorial_body_format import capacity_issues, report as format_report
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
    candidate = normalize_candidate(raw, state, LayoutFamilyRegistry().get('classic_three_column').zones)
    assert any('consecutively' in i['message'] for i in format_report(candidate)['issues'])
    assert candidate['modules'][0]['entries'] == raw['modules'][0]['entries']


def test_structured_steps_are_renumbered_after_deletion_and_support_keeps_its_indent(tmp_path):
    state = state_for(tmp_path)
    raw = draft_for(state)
    module = raw['modules'][0]
    module.update(presentation_style='steps', entries=[
        {'item_id': eid, 'text': text, 'parent_item_id': parent, 'display_label': ''}
        for eid, text, parent in [('a', 'Collect samples.', ''), ('s', '1.5× scaling.', 'a'),
                                  ('b', 'Remove noise.', ''), ('c', 'Report results.', '')]])
    def displayed():
        candidate = normalize_candidate(raw, state, LayoutFamilyRegistry().get('classic_three_column').zones)
        assert format_report(candidate)['status'] == 'ok'
        return section_paragraphs(make_board(candidate)['spatial_content_plan']['sections'][0])
    assert [p['prefix'] for p in displayed()] == ['1) ', '◦ ', '2) ', '3) ']
    del module['entries'][2]
    revised = displayed()
    assert [paragraph_text(p) for p in revised] == ['1) Collect samples.', '◦ 1.5× scaling.', '2) Report results.']
    assert revised[1]['indent_inches'] == .30


def test_step_marker_detection_and_partial_numbering_share_one_display(tmp_path):
    state = state_for(tmp_path)
    raw = draft_for(state)
    module = raw['modules'][0]
    texts = ['Collect.', 'See Step 2 in the appendix.', '2. Normalize.', '(3) Rank.',
             '• **Step 4:** Verify.', '5) Step 5: Finish.', '步骤6：检查。', 'Report.']
    module.update(presentation_style='steps', entries=[
        {'item_id': f'e{i}', 'parent_item_id': 'e0' if i == 1 else '', 'display_label': '', 'text': line}
        for i, line in enumerate(texts)])
    candidate = normalize_candidate(raw, state, LayoutFamilyRegistry().get('classic_three_column').zones)
    def lines(board):
        return [paragraph_text(p) for p in section_paragraphs(board['spatial_content_plan']['sections'][0])]
    assert lines(make_board(candidate)) == [
        '1) Collect.', '◦ See Step 2 in the appendix.', '2) Normalize.', '3) Rank.',
        '4) Verify.', '5) Finish.', '6) 检查。', '7) Report.']
    v65 = make_board(candidate, preserve_step_numbers=True)
    assert preserves_step_numbers(v65) is True
    assert lines(v65) == [
        '1) Collect.', '◦ See Step 2 in the appendix.', '2. Normalize.', '(3) Rank.',
        'Step 4: Verify.', 'Step 5: Finish.', '步骤6：检查。', '7) Report.']
    # An unnumbered first step and a support item must not make a valid '2.' a gap.
    assert format_report(candidate)['status'] == 'ok'
    archived = make_board(candidate, preserve_step_numbers=False)
    assert preserves_step_numbers(archived) is False
    assert lines(archived)[2:4] == ['2) Normalize.', '3) (3) Rank.']
    assert format_report(candidate, preserve_step_numbers=False)['status'] == 'format_defects'
    module['presentation_style'] = 'plain'
    assert lines(make_board(raw))[2] == '• 2. Normalize.'


@pytest.mark.parametrize('raw, expected', [
    ('1) Step 1: Measure.', ('Step 1: ', 1, 'Measure.')),
    ('Step 1: 1. Measure.', ('Step 1: ', 1, 'Measure.')),
    ('1) 2) Measure.', ('1) ', 1, 'Measure.')),
    ('Step 1: (1) + (3) equals four.', ('Step 1: ', 1, '(1) + (3) equals four.')),
    ('Step 1: (2) gives the error bound.', ('Step 1: ', 1, '(2) gives the error bound.')),
    ('**Step 2**: Compare.', ('Step 2: ', 2, 'Compare.')),
    ('Step 1:\nCollect.', ('Step 1:\n', 1, 'Collect.')),
    ('Step 1\nCollect.', ('Step 1\n', 1, 'Collect.')),
    ('2)', ('2)', 2, '')),
])
def test_step_marker_preserves_one_label_and_scientific_body(raw, expected):
    from src.layout.body_presentation import split_step_marker
    assert split_step_marker(raw) == expected


def test_invalid_numbers_are_replaced_after_failed_repair(tmp_path):
    raw = draft_for(state_for(tmp_path))
    raw['modules'][0].update(presentation_style='steps', entries=[
        {'item_id': f'e{i}', 'parent_item_id': '', 'display_label': '', 'text': line}
        for i, line in enumerate(['Step 3: Measure.', 'Analyze.', '5. Summarize.', 'Report.'])])
    section = make_board(raw)['spatial_content_plan']['sections'][0]
    assert [paragraph_text(p) for p in section_paragraphs(section)] == [
        '1) Measure.', '2) Analyze.', '3) Summarize.', '4) Report.']


@pytest.mark.parametrize('prefixes,keep', [
    (['1. ', '2. ', '3. '], True),
    (['(1) ', '(2) ', '(3) '], True),
    (['Step 01: ', 'Step 02:  ', 'Step 03: '], True),
    (['第1步：', '第2步：', '第3步：'], True),
    (['Step 1\n', 'Step 2\n', 'Step 3\n'], True),
    (['', '', ''], False),
    (['', 'Step 2: ', 'Step 3: '], False),
    (['Step 1: ', '', 'Step 3: '], False),
    (['Step 1: ', 'Step 2: ', ''], False),
    (['1. ', '2) ', '3. '], False),
    (['Step 1: ', 'Step 3: ', 'Step 4: '], False),
    (['Step 1: ', 'Step 2: ', 'Step 2: '], False),
    (['Step 2: ', 'Step 1: ', 'Step 3: '], False),
    (['Step 1: ', 'Step 2: 2. ', 'Step 3: '], False),
    (['01. ', '2. ', '03. '], False),
])
def test_each_steps_module_decides_independently(tmp_path, prefixes, keep):
    raw = draft_for(state_for(tmp_path))
    bodies = ['1.5× speedup.', 'Step 2 improves recall.', '(2) + (3) equals five.']
    original = ['Step 1: ', 'Step 2: ', 'Step 3: ']
    for module, markers in zip(raw['modules'], [original, prefixes]):
        entries = [{'item_id': f'e{i}', 'text': marker + body, 'parent_item_id': '', 'display_label': ''}
                   for i, (marker, body) in enumerate(zip(markers, bodies))]
        entries.insert(1, {'item_id': 'support', 'text': '92% recall.', 'parent_item_id': 'e0', 'display_label': ''})
        module.update(presentation_style='steps', entries=entries)

    board = make_board(raw)
    sections = board['spatial_content_plan']['sections']
    expected = prefixes if keep else ['1) ', '2) ', '3) ']
    for section, markers in zip(sections, [original, expected]):
        rows = section_paragraphs(section)
        assert [paragraph_text(row) for row in rows] == [
            markers[0] + bodies[0], '◦ 92% recall.', markers[1] + bodies[1], markers[2] + bodies[2]]
        assert rows[1]['indent_inches'] == .30


@pytest.mark.parametrize('text', ['1.5× speedup.', '2024. Results were published.', '92% recall.',
                                  'Step 2 improves recall.', 'Step 1.5 is a parameter.',
                                  '(2) + (3) equals five.', '−2.4 difference.'])
def test_scientific_prose_is_not_a_step_marker(text):
    from src.layout.body_presentation import split_step_marker
    assert split_step_marker(text) == ('', None, text)


def test_stray_model_numbering_gets_plain_prose_repair_once(monkeypatch, tmp_path):
    from src.workflow import editorial_pipeline as pipeline
    from src.workflow.editorial_requests import request
    from test_editorial_generation import capacity_reply
    from test_editorial_field_repair import model
    state = state_for(tmp_path); raw = draft_for(state)
    raw['modules'][0].update(presentation_style='steps', entries=[
        {'item_id': 'collect', 'parent_item_id': '', 'display_label': '', 'text': '1) Collect pairs at 92% precision with 2% recall.'},
        {'item_id': 'evaluate', 'parent_item_id': '', 'display_label': '', 'text': '2) Evaluate 196 comments.'},
        {'item_id': 'limit', 'parent_item_id': '', 'display_label': '', 'text': '3) Retain the annotation condition.'}])
    install(state, raw)
    changed = deepcopy(state['editorial_candidate']['modules'][0])
    changed['entries'].pop(1)
    patch = capacity_reply([changed])
    calls = model(monkeypatch, [patch, {'repairs': {'field_0': 'Retain the annotation condition.'}}])
    diagnostics = lambda p: capacity_issues(p, state['editorial_candidate'])
    repaired = request(state, 'editorial_balancer', {}, pipeline.PATCH,
        directory='editorial/numbering', validator=lambda p: pipeline.merge_patch(state, p),
        format_diagnostics=diagnostics)
    assert len(calls) == 2
    assert repaired['modules'][0]['entries'][0] == changed['entries'][0]
    assert repaired['modules'][0]['entries'][1]['text'] == 'Retain the annotation condition.'
    assert 'Remove hand-written list markers' in diagnostics(patch)[0]['message']
    assert request(state, 'editorial_balancer', {}, pipeline.PATCH,
        directory='editorial/numbering', validator=lambda p: pipeline.merge_patch(state, p),
        format_diagnostics=diagnostics) == repaired
    assert len(calls) == 2  # Durable replay cannot purchase another format request.


def test_font_agent_skips_keyword_call_and_preserves_authored_emphasis(monkeypatch, tmp_path):
    from src.workflow import editorial_pipeline as pipeline
    from src.layout.editorial_layout import measure
    state = state_for(tmp_path)
    archived = draft_for(state)
    for module in archived['modules']:
        module['entries'] = [{'item_id': 'main', 'text': '• **Core mechanism:** A result.'},
                             {'item_id': 'support', 'text': '  ◦ A supporting explanation.'}]
    install(state, archived)
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
