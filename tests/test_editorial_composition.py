"""Initial directions survive measured edits, geometry changes and recovery."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from test_editorial_generation import state_for, draft_for, install
from src.agents.layout_agent import LayoutAgent
from src.layout.editorial_composition import (
    VERSION, HORIZONTAL, VERTICAL, initial_fit, assert_composition,
)
from src.layout.editorial_layout import measure
from src.layout.families import LayoutFamilyRegistry
from src.layout.module_composition import side_by_side_plan
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import assert_editorial_ready, EditorialInterrupted


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    from src.layout.measurement_context import measurement_scope
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected real model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


def hags_state(tmp_path, multiple=False):
    state = state_for(tmp_path, 'central_evidence_band')
    state['images'] = {'1': {'aspect': 2.836, 'caption': 'Hierarchical search architecture'}}
    state['classified_visuals'] = {'key_visual': 'figure_1', 'method_workflow': ['figure_1']}
    raw = draft_for(state)
    method = raw['modules'][2]
    method.update(title='HAGS Architecture', visual_ids=['figure_1'])
    method['entries'] = [
        {'item_id': 'hierarchy', 'text': 'Divides the city into regions, creating a two-level hierarchy: Level 1 selects a region, Level 2 selects a parcel within it.',
         'display_label': 'Two-Level Hierarchy', 'parent_item_id': ''},
        {'item_id': 'shared', 'text': 'Shares a single prediction module and Level-2 policy across all regions to reduce parameter count and improve generalization.',
         'display_label': 'Shared Parameters', 'parent_item_id': ''},
        {'item_id': 'training', 'text': 'Uses REINFORCE for both levels, with online BCE updates to the prediction module allowing test-time adaptation to new eviction data.',
         'display_label': 'Adaptive RL', 'parent_item_id': ''},
    ]
    if multiple:
        state['images']['2'] = {'aspect': 2, 'caption': 'Supporting method detail'}
        method['visual_ids'].append('figure_2')
    return install(state, raw)


def compressed(state):
    candidate = deepcopy(state['editorial_candidate'])
    candidate['modules'][2]['entries'] = [
        {'item_id': f'e{i}', 'text': text, 'display_label': label, 'parent_item_id': ''}
        for i, (label, text) in enumerate([
            ('Two-Level Hierarchy', 'Two-level hierarchy: Level 1 selects a region, Level 2 selects a parcel within it.'),
            ('Shared Parameters', 'Shared prediction module and Level-2 policy across regions reduce parameters and improve generalization.'),
            ('Adaptive RL', 'REINFORCE trains both levels; online BCE updates to the prediction module enable test-time adaptation.'),
            ('Policy Inputs', 'Level 1 uses aggregated region predictions; Level 2 uses region-specific parcel inputs.'),
            ('Loss Function', 'Loss: L_HAGS = L^h1_RL + L^h2_RL + λ L_BCE.'),
        ])]
    return candidate


def narrower_height(state):
    zones = deepcopy(state['editorial_zones'])
    for zone in zones:
        if zone['zone_id'] == 'central_evidence': zone['height'] = .285
        if zone['zone_id'].startswith('bottom_'): zone.update(y=.575, height=.425)
    return zones


def boxes(elements, mid='module_2'):
    return ([e for e in elements if e.get('section_id') == mid and e['type'] == 'visual'],
            next(e for e in elements if e.get('section_id') == mid and e['type'] == 'text'))


def test_hags_regression_keeps_horizontal_after_five_entry_edit_and_height_reduction(tmp_path):
    state = hags_state(tmp_path)
    assert state.get('editorial_composition') is None
    before = initial_fit(state, fitter=measure)
    assert state['editorial_composition']['modules'] == {'module_2': HORIZONTAL}
    candidate = compressed(state)
    zones = narrower_height(state)
    unlocked = deepcopy(state); unlocked.pop('editorial_composition')
    exact = measure(unlocked, candidate, zones)
    assert boxes(exact['layout'])[1]['y'] == boxes(exact['layout'])[0][0]['y']
    unlocked.pop('editorial_version')  # The explicitly older source route retains coarse selection.
    legacy = measure(unlocked, candidate, zones)
    images, text = boxes(legacy['layout'])
    assert text['y'] > images[0]['y']+images[0]['height']
    result = measure(state, candidate, zones)
    images, text = boxes(result['layout'])
    assert images[0]['y'] == pytest.approx(text['y'])
    assert images[0]['x']+images[0]['width'] < text['x']
    assert images[0]['width'] > boxes(legacy['layout'])[0][0]['width']*2
    metric = next(m for m in result['report']['modules'] if m['module_id'] == 'module_2')
    assert metric['intrinsic_height'] <= metric['allocated_height']+1e-6
    assert_composition(state, candidate, result['layout'], durable=True)
    fast = measure(state, candidate, zones, exact=False)
    assert next(m for m in fast['report']['modules'] if m['module_id'] == 'module_2')['body_layout'] == HORIZONTAL
    assert before['report']['modules'][2]['composition_locked']


def test_vertical_stays_vertical_when_wider_geometry_would_choose_horizontal(tmp_path):
    state = state_for(tmp_path)
    state['images'] = {'1': {'aspect': 2}}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['figure_1']
    install(state, raw); result = initial_fit(state, fitter=measure)
    assert state['editorial_composition']['modules'] == {'module_0': VERTICAL}
    section = result['board']['spatial_content_plan']['sections'][0]
    unlocked = deepcopy(state); unlocked.pop('editorial_composition')
    assert side_by_side_plan(LayoutAgent(), section, 52, 14, unlocked)
    elements = LayoutAgent()._create_section_elements(section, 1, 1, 52, state, 14)
    images, text = boxes(elements, 'module_0')
    assert text['y'] >= images[0]['y']+images[0]['height']
    assert_composition(state, layout=elements)


@pytest.mark.parametrize('width,height', [(12, 22), (52, 2), (7, 3)])
def test_horizontal_never_falls_back_when_aspect_or_capacity_changes(tmp_path, width, height):
    state = hags_state(tmp_path); result = initial_fit(state, fitter=measure)
    section = result['board']['spatial_content_plan']['sections'][2]
    section['text_content'] = ['Long mechanism explanation. '*20]
    elements = LayoutAgent()._create_section_elements(section, 1, 1, width, state, height)
    images, text = boxes(elements)
    assert images[0]['y'] == text['y'] and images[0]['x']+images[0]['width'] < text['x']
    assert all(e['width'] > 0 and e['height'] > 0 for e in elements)
    if height <= 3:
        assert max(e['y']+e['height'] for e in elements)-1 > height


def test_multiple_visuals_keep_their_left_stack_and_original_aspects(tmp_path):
    state = hags_state(tmp_path, multiple=True); result = initial_fit(state, fitter=measure)
    assert state['editorial_composition']['modules']['module_2'] == HORIZONTAL
    candidate = compressed(state)
    result = measure(state, candidate, narrower_height(state))
    images, text = boxes(result['layout'])
    assert [e['visual_id'] for e in images] == ['figure_1', 'figure_2']
    assert images[1]['y'] >= images[0]['y']+images[0]['height']
    assert all(e['x']+e['width'] < text['x'] for e in images)
    assert [e['width']/e['height'] for e in images] == pytest.approx([2.836, 2])


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_all_families_freeze_and_recompile_the_same_initial_direction(tmp_path, family):
    state = state_for(tmp_path, family)
    state['images'] = {'1': {'aspect': 2}}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['figure_1']
    install(state, raw); result = initial_fit(state, fitter=measure)
    after = measure(state, state['editorial_candidate'], result['spec']['zones'])
    assert result['layout'] == after['layout']
    assert_composition(state, layout=after['layout'], durable=True)


def test_initial_fit_receipt_replays_without_another_search(tmp_path):
    state = hags_state(tmp_path); original = deepcopy(state)
    first = initial_fit(state, fitter=measure)
    again = initial_fit(original, fitter=lambda *a: pytest.fail('Initial search repeated'))
    assert again == first and original['editorial_composition'] == state['editorial_composition']


@pytest.mark.parametrize('damage', ['missing', 'version', 'unknown_mode', 'dropped_owner', 'changed_mode', 'deleted_receipt'])
def test_missing_or_changed_lock_refuses_edit_before_request(monkeypatch, tmp_path, damage):
    state = hags_state(tmp_path); result = initial_fit(state, fitter=measure)
    if damage == 'missing': state.pop('editorial_composition')
    elif damage == 'version': state['editorial_composition']['version'] = 'old'
    elif damage == 'unknown_mode': state['editorial_composition']['modules']['module_2'] = 'automatic'
    elif damage == 'dropped_owner': state['editorial_composition']['modules'].clear()
    elif damage == 'changed_mode': state['editorial_composition']['modules']['module_2'] = VERTICAL
    else: (Path(state['sample_preparation_dir'])/'editorial/composition.json').unlink()
    monkeypatch.setattr(pipeline, 'request', lambda *a, **k: pytest.fail('Request after lost composition'))
    with pytest.raises((ValueError, FileNotFoundError)):
        pipeline.edit(state, result, 'capacity')


def test_missing_initial_receipt_after_a_charge_cannot_buy_new_selection(tmp_path):
    state = hags_state(tmp_path); pipeline.charge(state, 'capacity', 'interrupted')
    with pytest.raises(ValueError, match='receipt missing'):
        initial_fit(state, fitter=lambda *a: pytest.fail('Uncharged replacement selection'))


def test_corrupt_or_mismatched_initial_receipt_is_not_replaced(tmp_path):
    state = hags_state(tmp_path); original = deepcopy(state); initial_fit(state, fitter=measure)
    path = Path(state['sample_preparation_dir'])/'editorial/composition.json'
    data = json.loads(path.read_text()); data['payload']['result']['layout'][0]['x'] += 1
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='digest'):
        initial_fit(original, fitter=lambda *a: pytest.fail('Corrupt receipt triggered a search'))


@pytest.mark.parametrize('change', ['prose', 'geometry', 'style', 'sample'])
def test_initial_receipt_is_bound_to_actual_inputs(tmp_path, change):
    state = hags_state(tmp_path); original = deepcopy(state); initial_fit(state, fitter=measure)
    if change == 'prose': original['editorial_candidate']['modules'][2]['entries'][0]['text'] += ' Changed.'
    elif change == 'geometry': original['editorial_zones'][2]['height'] -= .01
    elif change == 'style': original['styling_interfaces']['font_sizes']['body_text'] += 1
    else: original['iteration_context']['sample_id'] = 'sample_000002'
    with pytest.raises(ValueError, match='identity'):
        initial_fit(original, fitter=lambda *a: pytest.fail('Changed inputs triggered a search'))


def test_actual_direction_is_checked_in_addition_to_metadata(tmp_path):
    state = hags_state(tmp_path); result = initial_fit(state, fitter=measure)
    images, text = boxes(result['layout']); text['y'] = images[0]['y']+images[0]['height']+.3
    with pytest.raises(ValueError, match='boxes'):
        assert_composition(state, layout=result['layout'])


@pytest.mark.parametrize('damage', ['missing', 'changed', 'changed_and_resigned'])
def test_ready_snapshot_binds_composition_and_its_original_receipt(monkeypatch, tmp_path, damage):
    from src.workflow.editorial_contract import snapshot_payload
    from utils.persistence import digest
    state = hags_state(tmp_path)
    pipeline.charge(state, 'curator', 'offline_fixture')
    monkeypatch.setattr(pipeline, 'fit', measure)
    monkeypatch.setattr(pipeline, 'edit', lambda *a: False)
    pipeline.editorial_joint_node(state); pipeline.editorial_compile_node(state)
    assert_editorial_ready(state, compiled=True)
    if damage == 'missing': state.pop('editorial_composition')
    else: state['editorial_composition']['modules']['module_2'] = VERTICAL
    if damage == 'changed_and_resigned':
        state['editorial_snapshot']['digest'] = digest(snapshot_payload(state))
    with pytest.raises(ValueError, match='snapshot|composition'):
        assert_editorial_ready(state, compiled=True)


def test_empty_lock_allows_text_only_module_addition_and_removal(tmp_path):
    state = install(state_for(tmp_path)); initial_fit(state, fitter=measure)
    assert state['editorial_composition']['modules'] == {}
    extra = deepcopy(state['editorial_candidate']['modules'][0]); extra['module_id'] = 'extra'
    patch = {'modules': [extra], 'remove_module_ids': [], 'module_order': [], 'narrative_flow': '', 'reason': 'Explain'}
    candidate = pipeline.merge_patch(state, patch)
    pipeline.install(state, candidate)
    patch.update(modules=[], remove_module_ids=['extra'])
    candidate = pipeline.merge_patch(state, patch)
    assert_composition(state, candidate)


@pytest.mark.parametrize('route,version', [('standalone_classic', 'poster_editorial_v1'),
                                         ('optimization_family', None), ('optimization_family', 'old')])
def test_legacy_routes_ignore_current_editorial_lock(tmp_path, route, version):
    state = hags_state(tmp_path); result = initial_fit(state, fitter=measure)
    section = result['board']['spatial_content_plan']['sections'][2]
    state.update(generation_route=route, editorial_version=version)
    state['editorial_composition']['modules']['module_2'] = VERTICAL
    plan = side_by_side_plan(LayoutAgent(), section, 52, 14, state)
    assert bool(plan) is (route == 'optimization_family')


def test_interrupted_capacity_response_replays_with_same_frozen_direction(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    state = hags_state(tmp_path); start = deepcopy(state); calls = []; searches = []
    def fitter(st, candidate, zones):
        searches.append(candidate['candidate_id'])
        return measure(st, candidate, zones)
    monkeypatch.setattr(pipeline, 'fit', fitter)
    class Model:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            data = json.loads(message.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])
            assert data['fixed_module_composition']['modules'] == {'module_2': HORIZONTAL}
            assert data['capacity_guidance']['modules'][2]['body_layout'] == HORIZONTAL
            calls.append(data)
            module = deepcopy(data['whole_poster']['modules'][2])
            module['entries'][0]['text'] += ' More mechanism detail.'
            value = {'modules': [module] if len(calls) == 1 else [], 'remove_module_ids': [],
                     'module_order': [], 'narrative_flow': '', 'reason': 'Measured edit'}
            return SimpleNamespace(content=json.dumps(value), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    edit = pipeline.edit
    def interrupt_after_response(*args):
        edit(*args)
        raise EditorialInterrupted()
    monkeypatch.setattr(pipeline, 'edit', interrupt_after_response)
    with pytest.raises(EditorialInterrupted): pipeline.editorial_joint_node(state)
    frozen = deepcopy(state['editorial_composition'])
    assert len(calls) == len(searches) == 1
    monkeypatch.setattr(pipeline, 'edit', edit)
    pipeline.editorial_joint_node(start)
    pipeline.editorial_compile_node(start)
    assert len(calls) == 3 and len(searches) == 4
    assert start['editorial_composition'] == frozen
    assert [c['phase'] for c in start['editorial_budget']['charges']] == ['capacity'] * 3
    assert_editorial_ready(start, compiled=True)


def test_real_pptx_png_and_renderfit_keep_hags_horizontal_after_capacity_edit(monkeypatch, tmp_path):
    import shutil
    from PIL import Image
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from src.agents.font_agent import FontAgent
    from src.agents.renderer import Renderer
    from src.agents.render_fit_audit import render_fit_audit_node
    import utils.langgraph_utils as language
    if not shutil.which('libreoffice'):
        pytest.skip('LibreOffice not installed')
    state = hags_state(tmp_path)
    image = tmp_path/'method.png'; Image.new('RGB', (850, 300), '#335577').save(image)
    state['images']['1']['path'] = str(image)
    calls = []
    def fitter(st, candidate, zones):
        return measure(st, candidate, narrower_height(st) if len(candidate['modules'][2]['entries']) == 5 else zones)
    monkeypatch.setattr(pipeline, 'fit', fitter)
    class Model:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            data = json.loads(message.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])
            calls.append(data)
            value = {'modules': [compressed(state)['modules'][2]] if len(calls) == 1 else [],
                     'remove_module_ids': [], 'module_order': [], 'narrative_flow': '', 'reason': 'Capacity edit'}
            return SimpleNamespace(content=json.dumps(value), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    monkeypatch.setattr(FontAgent, '_identify_keywords', lambda *a: {'section_keywords': {}})
    pipeline.editorial_joint_node(state); pipeline.editorial_compile_node(state)
    FontAgent()(state); Renderer()(state); render_fit_audit_node(state)
    assert not state['errors'], state['errors']
    assert len(calls) == 3 and state['editorial_composition']['modules'] == {'module_2': HORIZONTAL}
    assert_composition(state, layout=state['styled_layout'], durable=True)
    assert state['render_fit_report']['conclusive'], state['render_fit_report']
    assert state['render_fit_report']['status'] == 'passed'
    hags_match = next(row for row in state['render_fit_report']['matched_text_boxes']
                      if row['element_id'] == 'module_2_text')
    assert hags_match['matched_normalized_characters'] == hags_match['expected_normalized_characters'] == 405
    assert not [issue for issue in state['render_fit_report'].get('issues', []) if issue.get('section_id') == 'module_2']
    current = state['current_candidate']
    assert Path(current['png_path']).is_file()
    with Image.open(current['png_path']) as png:
        assert png.width > 1000 and png.height > 500
    prs = Presentation(current['pptx_path'])
    pictures = [s for s in prs.slides[0].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    body = next(s for s in prs.slides[0].shapes if s.has_text_frame and 'Two-level hierarchy:' in s.text)
    figure = next(s for s in pictures if s.width/s.height == pytest.approx(2.836, rel=.01))
    assert figure.left+figure.width < body.left and figure.top == body.top
    assert figure.width/914400 > 14
    assert_editorial_ready(state, compiled=True)
