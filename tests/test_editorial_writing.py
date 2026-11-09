"""Writing structure, measured edits and real editable math delivery, offline."""
from copy import deepcopy
from types import SimpleNamespace
import json
import shutil
import subprocess

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from test_editorial_generation import state_for, draft_for, install
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import make_board, normalize_candidate
from src.workflow.editorial_writing import capacity_guidance, observed_edit, record_measured_edit
from src.layout.body_presentation import paragraphs, paragraph_text
from src.layout.editorial_layout import measure
from src.layout.editorial_text import formula_plan
from src.layout.families import LayoutFamilyRegistry
from src.agents.font_agent import FontAgent
from src.agents.layout_agent import LayoutAgent
from src.agents.renderer import Renderer


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected real model'))


def entries():
    return [
        {'item_id': 'encode', 'text': 'Encode the available features.', 'display_label': '', 'parent_item_id': ''},
        {'item_id': 'detail', 'text': 'Predictions assign probability p_i to each item; queries cost $1.',
         'display_label': '', 'parent_item_id': 'encode'},
        {'item_id': 'query', 'text': 'Query an item and observe its outcome.', 'display_label': '', 'parent_item_id': ''},
        {'item_id': 'loss', 'text': 'The loss is ε(α) = α/2.',
         'display_label': 'Training', 'parent_item_id': 'query'},
        {'item_id': 'update', 'text': 'Update predictions before the next query.', 'display_label': '', 'parent_item_id': ''},
    ]


def section_for(state, style='topics'):
    raw = draft_for(state)
    raw['modules'][0].update(entries=entries(), presentation_style=style)
    candidate = normalize_candidate(raw, state, LayoutFamilyRegistry().get(state['sample_family']['family']).zones)
    return make_board(candidate)['spatial_content_plan']['sections'][0]


@pytest.mark.parametrize('style,prefixes', [
    ('topics', ['• ', '◦ ', '• ', '◦ ', '• ']),
    ('plain', ['• ', '◦ ', '• ', '◦ ', '• ']),
    ('steps', ['1) ', '◦ ', '2) ', '◦ ', '3) ']),
])
def test_authored_parents_survive_inline_math_and_step_support(tmp_path, style, prefixes):
    state = state_for(tmp_path)
    section = section_for(state, style)
    description = paragraphs(section)
    assert [p['prefix'] for p in description] == prefixes
    assert [p['text'] for p in description] == [e['text'] for e in entries()]
    assert [p['indent_inches'] for p in description] == [0, .30, 0, .30, 0]
    assert [p['label'] for p in description] == (['', '', '', 'Training', ''] if style == 'topics' else [''] * 5)


@pytest.mark.parametrize('style', ['topics', 'steps'])
def test_legacy_formula_and_step_presentation_remains_unchanged(tmp_path, style):
    section = section_for(state_for(tmp_path), style)
    section.pop('editorial_version')
    description = paragraphs(section)
    assert [p['prefix'] for p in description] == ([f'{i}) ' for i in range(1, 6)] if style == 'steps' else ['• '] * 5)


def test_legacy_empty_entries_do_not_renumber_later_steps(tmp_path):
    section = section_for(state_for(tmp_path), 'steps')
    section.pop('editorial_version')
    section['text_content'][1] = ''
    assert [p['prefix'] for p in paragraphs(section)] == ['1) ', '3) ', '4) ', '5) ']


@pytest.mark.parametrize('usage,action', [(.8999, 'expand'), (.9, 'keep'), (.9775, 'keep'), (1, 'keep'), (1.0001, 'compress')])
def test_capacity_guidance_uses_actual_ratio_boundaries(usage, action):
    row = {'module_id': 'm', 'utilization': usage, 'current_words': 32, 'suggested_words': 31}
    original = deepcopy(row)
    result = capacity_guidance({'modules': [row]})
    assert result['modules'][0]['suggested_action'] == action
    assert result['modules'][0]['utilization_percent'] == round(usage * 100, 4)
    assert row == original


def test_observed_diff_tracks_actual_deletions_rewrites_and_hierarchy(tmp_path):
    state = install(state_for(tmp_path))
    before = state['editorial_candidate']
    after = deepcopy(before)
    module = after['modules'][0]
    module['entries'].pop()
    module['entries'][0]['text'] = 'A revised explanation.'
    module['entries'][0]['display_label'] = ''
    module['presentation_style'] = 'plain'
    diff = observed_edit(before, after)
    assert diff['changed'] and len(diff['changed_modules']) == 1
    assert diff['changed_modules'][0]['removed_entry_ids'] == ['support']
    assert diff['changed_modules'][0]['rewritten_entry_ids'] == ['main']
    assert diff['changed_modules'][0]['presentation_changed_entry_ids'] == ['main']
    assert observed_edit(before, before)['changed'] is False
    assert len(before['modules'][0]['entries']) == 2


def test_false_deletion_reason_is_recorded_as_noop_without_another_request(monkeypatch, tmp_path):
    state = install(state_for(tmp_path))
    from src.layout.editorial_composition import initial_fit
    result = initial_fit(state, fitter=measure)
    calls = []
    def response(st, kind, payload, schema, **kwargs):
        calls.append(payload)
        assert 'modules' not in payload['measurements']
        assert len(payload['capacity_tasks']['modules']) == len(payload['whole_poster']['modules'])
        assert schema == pipeline.PATCH
        return {'modules': deepcopy(payload['whole_poster']['modules']), 'remove_module_ids': [],
                'module_order': [], 'narrative_flow': '', 'reason': 'Deleted the support entry.'}
    monkeypatch.setattr(pipeline, 'request', response)
    assert pipeline.edit(state, result, 'capacity') is False
    assert len(calls) == 1
    history = state['editorial_history'][-1]
    assert history['observed_edit']['changed'] is False
    assert not history['observed_edit']['changed_modules']
    assert history['measurements_before'] == history['measurements_after']
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['capacity']


def test_next_measurement_is_attached_only_to_matching_candidate(tmp_path):
    state = install(state_for(tmp_path)); candidate = state['editorial_candidate']
    history = [{'to': 'different'}]
    record_measured_edit(history, candidate, {'modules': []})
    assert 'measurements_after' not in history[-1]
    history[-1]['to'] = candidate['candidate_id']
    report = measure(state, candidate, state['editorial_zones'])['report']
    record_measured_edit(history, candidate, report)
    assert history[-1]['measurements_after'] == capacity_guidance(report)


def test_formulas_preserve_literal_stars_backslashes_and_styled_prefix():
    from utils.text_formatting import tokenize_styling
    text = '• A literal *symbol* and a backslash \\ are scientific text.\n◦ Training: ε(α) = α/2.'
    raw = formula_plan(text, 16, 'Arial', 44)
    assert raw['blocks'][0]['text'] == text.split('\n')[0]
    styled_text = FontAgent._escape_formatting_literals(text).replace('Training:', '**Training:**')
    styled = formula_plan(styled_text, 16, 'Arial', 44, styled=True)
    assert styled['height'] == pytest.approx(raw['height'])
    prefix = next(b for b in styled['blocks'] if b.get('formula_prefix'))
    assert any(s['bold'] and s['text'] == 'Training:' for s in tokenize_styling(prefix['text']))
    assert ''.join(s['text'] for s in tokenize_styling(styled['blocks'][0]['text'])) == text.split('\n')[0]


def test_measurement_after_single_edit_records_the_frozen_candidate(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    state = install(state_for(tmp_path))
    monkeypatch.setattr(pipeline, 'fit', lambda s, c, z: measure(s, c, z))
    calls = []
    class Model:
        def __init__(self, *args):
            pass
        def reset(self):
            pass
        def step(self, message):
            payload = json.loads(message.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])
            calls.append(payload)
            module = deepcopy(payload['whole_poster']['modules'][0])
            module['entries'][0]['text'] += ' Additional mechanism.'
            value = {'modules': [module], 'remove_module_ids': [], 'module_order': [],
                     'narrative_flow': '', 'reason': 'Clarified the mechanism.'}
            return SimpleNamespace(content=json.dumps(value), input_tokens=2, output_tokens=2)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    pipeline.editorial_joint_node(state)
    history = state['editorial_history']
    assert len(calls) == len(history) == 1
    assert state['editorial_fit']['completion_reason'] == 'repair_limit_reached'
    assert all(h['observed_edit']['changed'] for h in history)
    assert all('measurements_after' in h for h in history)
    assert history[-1]['to'] == state['editorial_candidate']['candidate_id']
    assert history[-1]['measurements_after'] == capacity_guidance(state['editorial_fit'])
    assert pipeline.LIMITS == {'curator': 1, 'merge': 1, 'writer': 1, 'capacity': 1}


def test_single_global_patch_compresses_overflow_and_expands_other_modules(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    from src.workflow.editorial_contract import assert_editorial_ready
    state = state_for(tmp_path)
    raw = draft_for(state)
    raw['modules'][0]['entries'][0]['text'] = 'The model updates predictions after each observation. ' * 150
    install(state, raw)
    before = deepcopy(state['editorial_candidate'])
    calls, fits = [], []
    def fitter(st, candidate, zones):
        result = measure(st, candidate, zones)
        fits.append(result)
        return result
    monkeypatch.setattr(pipeline, 'fit', fitter)
    class Model:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            payload = json.loads(message.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])
            calls.append(payload)
            assert len(calls) == 1, 'No second capacity request is allowed'
            modules = deepcopy(payload['whole_poster']['modules'])
            assert [m['module_id'] for m in payload['capacity_tasks']['modules']] == [m['module_id'] for m in modules]
            assert [m['action'] for m in payload['capacity_tasks']['modules']] == ['compress', 'expand', 'expand']
            assert all('reference_words' in task for task in payload['capacity_tasks']['modules'])
            modules[0]['entries'][0]['text'] = 'The model updates predictions after each observation.'
            for module in modules[1:]:
                module['entries'][0]['text'] += ' Observations guide subsequent resource allocation.'
            value = {'modules': modules, 'remove_module_ids': [], 'module_order': [],
                     'narrative_flow': '', 'reason': 'Compress the first module and expand the other modules.'}
            return SimpleNamespace(content=json.dumps(value), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    pipeline.editorial_joint_node(state)
    assert len(calls) == len(state['editorial_budget']['charges']) == 1
    assert len(fits) == 2  # Initial measurement and measurement of the complete patch.
    after = state['editorial_candidate']
    assert len(after['modules'][0]['entries'][0]['text']) < len(before['modules'][0]['entries'][0]['text'])
    assert all(len(a['entries'][0]['text']) > len(b['entries'][0]['text'])
               for a, b in zip(after['modules'][1:], before['modules'][1:]))
    assert fits[0]['report']['modules'][0]['overage_inches'] > fits[1]['report']['modules'][0]['overage_inches']
    assert state['editorial_history'][0]['measurements_after'] == capacity_guidance(state['editorial_fit'])
    assert state['editorial_fit']['completion_reason'] == 'repair_limit_reached'
    pipeline.editorial_compile_node(state)
    assert_editorial_ready(state, compiled=True)


def test_initial_target_met_skips_capacity_request(monkeypatch, tmp_path):
    state = install(state_for(tmp_path))
    pipeline.charge(state, 'curator', 'offline-initial-draft')
    def fitted_report(st, candidate, zones):
        result = measure(st, candidate, zones)
        # Simulate a consistent physical target to isolate zero-call termination.
        for row in result['report']['modules']:
            row.update(utilization=.95, overage_inches=0, missing_height_inches=0)
        result['report'].update(passed=True, all_modules_90_percent=True)
        return result
    monkeypatch.setattr(pipeline, 'fit', fitted_report)
    monkeypatch.setattr(pipeline, 'request', lambda *a, **k: pytest.fail('Already fitting poster requested an edit'))
    pipeline.editorial_joint_node(state)
    assert state['editorial_fit']['completion_reason'] == 'target_met'
    assert not state.get('editorial_history')
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator']


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_all_families_compile_authored_hierarchy_with_math(tmp_path, family):
    state = state_for(tmp_path, family)
    raw = draft_for(state)
    # Keep these small enough for every canonical region; the display formula
    # integration below checks the independent, taller equation path.
    raw['modules'][0]['entries'] = entries()[:2]
    raw['modules'][0]['presentation_style'] = 'steps'
    install(state, raw)
    before = deepcopy(state['editorial_candidate'])
    result = measure(state, before, state['editorial_zones'])
    assert result['report']['passed'], result['report']
    body = next(e for e in result['layout'] if e.get('id') == 'module_0_text')
    assert body['content'].split('\n')[1].startswith('◦ ')
    assert body['editorial_version'] == 'poster_editorial_v1'
    assert state['editorial_candidate'] == before


@pytest.mark.parametrize('style', ['topics', 'steps'])
def test_formula_plan_and_real_editable_pptx_png_preserve_support(tmp_path, style):
    import pymupdf
    from src.layout.measurement_context import measurement_scope
    state = state_for(tmp_path)
    section = section_for(state, style)
    description = paragraphs(section)
    raw_text = '\n'.join(paragraph_text(p) for p in description)
    element = {'id': 'module_0_text', 'content': raw_text, 'editorial_body': True,
               'editorial_version': 'poster_editorial_v1', 'editorial_paragraphs': description,
               'font_family': 'Arial', 'font_size': 44, 'font_color': '#000000', 'line_spacing': 1.0}
    plain = formula_plan(raw_text, 16, 'Arial', 44, description=description)
    FontAgent()._apply_content_styling(element, {'text': '#000000', 'contrast': '#005577'},
        {'module_0': {'bold': ['probability'], 'bold_contrast': [], 'italic': []}})
    styled = formula_plan(element['content'], 16, 'Arial', 44, description=description, styled=True)
    assert styled['height'] == pytest.approx(plain['height'])
    with measurement_scope({'enabled': True}):
        cached = formula_plan(element['content'], 16, 'Arial', 44, description=description, styled=True)
    assert cached['height'] == pytest.approx(plain['height'])
    metrics = LayoutAgent()._measure_body_text(raw_text.split('\n'), 16.6, state,
        editorial=True, presentation=description)
    assert metrics['height'] >= styled['height']
    prs = Presentation(); prs.slide_width = Inches(18); prs.slide_height = Inches(14)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    renderer = Renderer(); renderer.styling_interfaces = FontAgent().get_styling_interfaces()
    renderer._add_enhanced_text(slide, element['content'], Inches(1), Inches(1), Inches(16),
                                Inches(metrics['height']), element)
    pptx = tmp_path / 'hierarchy.pptx'; prs.save(pptx)
    reopened = Presentation(pptx)
    shapes = reopened.slides[0].shapes
    pictures = [s for s in shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pictures) == 1 and pictures[0]._element.nvPicPr.cNvPr.get('descr') == 'ε(α) = α/2.'
    ps = [p for s in shapes if s.has_text_frame for p in s.text_frame.paragraphs]
    assert sum(p.text.startswith('◦ ') for p in ps) == 2
    for p in ps:
        if p.text.startswith('◦ '):
            assert p.level == 1 and p._p.get_or_add_pPr().get('marL') == str(Inches(.30))
    assert any(r.font.bold and 'probability' in r.text for p in ps for r in p.runs)
    if style == 'topics':
        assert any(r.font.bold and 'Training:' in r.text for p in ps for r in p.runs)
    assert max(s.top + s.height for s in shapes) <= Inches(1 + metrics['height'] + .001)
    if not shutil.which('libreoffice'):
        pytest.skip('LibreOffice not installed; editable PPTX checks completed')
    subprocess.run([shutil.which('libreoffice'), f'-env:UserInstallation={(tmp_path / "profile").as_uri()}',
        '--headless', '--convert-to', 'pdf:impress_pdf_Export', '--outdir', str(tmp_path), str(pptx)],
        capture_output=True, check=True, timeout=60)
    with pymupdf.open(pptx.with_suffix('.pdf')) as doc:
        text = doc[0].get_text()
        assert 'Encode the available features.' in text
        assert 'Update predictions before the next query.' in text
        doc[0].get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(tmp_path / 'hierarchy.png')
    assert (tmp_path / 'hierarchy.png').stat().st_size > 1000
