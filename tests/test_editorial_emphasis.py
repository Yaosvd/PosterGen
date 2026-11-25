"""Core selection, owner-local palettes and actual editable slide backgrounds."""
from copy import deepcopy
from test_editorial_generation import capacity_reply
from pathlib import Path

import pytest
from src.workflow.editorial_contract import EditorialOutputError
from PIL import Image
from pptx import Presentation
from pptx.enum.dml import MSO_FILL

from test_editorial_generation import state_for, draft_for
from src.agents.renderer import Renderer
from src.layout.editorial_layout import measure
from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import normalize_candidate, EditorialStructureError
from src.workflow.editorial_emphasis import assert_emphasis


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected live model'))


def setup(state, raw):
    zones = list(LayoutFamilyRegistry().get(state['sample_family']['family']).zones)
    state['editorial_zones'] = zones
    pipeline.install(state, normalize_candidate(raw, state, zones))
    state['editorial_visual_selection'] = pipeline.visual_selection(state['editorial_candidate'], state)
    return state


def image(state, tmp_path, number, color):
    path = tmp_path/f'figure_{number}.png'
    Image.new('RGB', (800, 400), color).save(path)
    state['images'][str(number)] = {'path': str(path), 'aspect': 2, 'caption': 'Method detail'}
    return str(path)


@pytest.mark.parametrize('core', [[], ['module_0'], ['module_2']])
def test_only_explicit_core_modules_receive_actual_backgrounds_even_when_all_important(tmp_path, core):
    state = state_for(tmp_path)
    raw = draft_for(state); raw['core_module_ids'] = core
    for module in raw['modules']: module['importance'] = 1
    setup(state, raw); pipeline.editorial_color_node(state)
    result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    assert_emphasis(state, layout=result['layout'], durable=True)
    slide = Presentation().slides.add_slide(Presentation().slide_layouts[6])
    renderer = Renderer()
    for container in (e for e in result['layout'] if e['type'] == 'section_container'):
        renderer._render_section_container(slide, container, state)
        assert (slide.shapes[-1].fill.type == MSO_FILL.SOLID) == (container['section_id'] in core)
    assert all(s['importance_level'] == 1 for s in result['board']['spatial_content_plan']['sections'])


@pytest.mark.parametrize('core', [['module_0', 'module_1'], ['module_0', 'module_1', 'module_2'],
    ['module_0', 'module_0'], ['unknown'], [1], None])
def test_invalid_core_selection_does_not_silently_pick_or_truncate_modules(tmp_path, core):
    state = state_for(tmp_path); raw = draft_for(state); raw['core_module_ids'] = core
    with pytest.raises(EditorialStructureError) as rejected:
        setup(state, raw)
    assert rejected.value.paths == (('core_module_ids',),)


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_single_core_module_works_in_every_family(tmp_path, family):
    state = state_for(tmp_path, family); raw = draft_for(state)
    core = raw['modules'][-1]['module_id']
    raw['core_module_ids'] = [core]
    setup(state, raw); pipeline.editorial_color_node(state)
    result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    assert [e['section_id'] for e in result['layout'] if e['type'] == 'section_container'
            and e.get('emphasis_background')] == [core]


@pytest.mark.parametrize('core', [[], ['module_0'], ['module_1']], ids=['none', 'text', 'image'])
def test_palette_requests_use_only_the_selected_cores_source(monkeypatch, tmp_path, core):
    state = state_for(tmp_path)
    first = image(state, tmp_path, 1, '#1C7448')
    second = image(state, tmp_path, 2, '#B05020')
    other = image(state, tmp_path, 3, '#442277')
    logo = tmp_path/'logo.png'; Image.new('RGB', (40, 40), '#224466').save(logo)
    state.update(aff_logo_path=str(logo), classified_visuals={'key_visual':'figure_1'})
    raw = draft_for(state); raw['core_module_ids'] = core
    raw['modules'][1]['visual_ids'] = ['figure_2', 'figure_1']
    raw['modules'][2]['visual_ids'] = ['figure_3']
    setup(state, raw)
    calls = []
    def extract(st, kind, payload, schema, **kwargs):
        calls.append((payload['source'], kwargs['images']))
        return {'extracted_color':'#224466'} if payload['source']=='affiliation_logo' else {'theme_color':'#1C7448'}
    monkeypatch.setattr(pipeline, 'request', extract)
    pipeline.editorial_color_node(state)
    panels = state['editorial_emphasis']['panels']
    assert list(panels) == core
    expected_calls = [('affiliation_logo', [str(logo)])]
    if core == ['module_0']:
        assert panels['module_0']['source'] == 'global_palette'
        assert panels['module_0']['theme_color'] == state['color_scheme']['theme']
    if core == ['module_1']:
        expected_calls.append(('core_module_1', [first]))
        assert panels['module_1']['visual_id'] == 'figure_1'
        assert panels['module_1']['theme_color'] == '#1C7448'
        assert panels['module_1']['theme_color'] != state['color_scheme']['theme']
    assert calls == expected_calls
    assert all(second not in str(c) and other not in str(c) for c in calls)


def test_single_image_core_extracts_its_first_local_visual_once_and_replays(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    first = image(state, tmp_path, 1, '#1C7448')
    image(state, tmp_path, 2, '#B05020')
    raw = draft_for(state); raw['core_module_ids'] = ['module_1']
    raw['modules'][1]['visual_ids'] = ['figure_1', 'figure_2']
    setup(state, raw)
    calls = []
    def extract(st, kind, payload, schema, **kwargs):
        calls.append(kwargs['images'][0])
        return {'theme_color':'#1C7448'}
    monkeypatch.setattr(pipeline, 'request', extract)
    pipeline.editorial_color_node(state)
    assert calls == [first]
    before = deepcopy(state['editorial_emphasis'])
    pipeline.editorial_color_node(state)
    assert calls == [first] and state['editorial_emphasis'] == before
    assert_emphasis(state, durable=True)


@pytest.mark.parametrize('failure', ['monochrome', 'timeout'])
def test_unavailable_image_accent_keeps_core_transparent_without_borrowing_global(monkeypatch, tmp_path, failure):
    state = state_for(tmp_path); image(state, tmp_path, 1, 'white')
    raw = draft_for(state); raw['core_module_ids'] = ['module_0']; raw['modules'][0]['visual_ids']=['figure_1']
    setup(state, raw)
    def extract(*args, **kwargs):
        if failure=='timeout': raise TimeoutError('Offline')
        return {'theme_color':None}
    monkeypatch.setattr(pipeline, 'request', extract)
    pipeline.editorial_color_node(state)
    panel = state['editorial_emphasis']['panels']['module_0']
    assert panel['resolved'] is None and panel['theme_color'] is None
    assert panel['resolution']['status']=='unavailable'
    assert state['optimized_story_board']['spatial_content_plan']['sections'][0]['editorial']['emphasis_disabled']
    assert state['editorial_candidate']['core_module_ids'] == ['module_0']
    result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    container = next(e for e in result['layout'] if e['type'] == 'section_container'
                     and e['section_id'] == 'module_0')
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    Renderer()._render_section_container(slide, container, state)
    assert slide.shapes[-1].fill.type == MSO_FILL.BACKGROUND


def test_patch_cannot_expand_core_selection_by_changing_importance(tmp_path):
    state = state_for(tmp_path); raw = draft_for(state); raw['core_module_ids']=['module_0']
    setup(state, raw); pipeline.editorial_color_node(state)
    changed = deepcopy(state['editorial_candidate']['modules'][1]); changed['importance']=1
    core = deepcopy(state['editorial_candidate']['modules'][0]); core['importance']=3
    with pytest.raises(EditorialOutputError):
        pipeline.merge_patch(state, {'modules':[changed,core], 'reason':'Change importance'})
    changed['entries'][0]['text'] += ' More explanation.'
    candidate = pipeline.merge_patch(state, capacity_reply([changed, core]))
    assert candidate['modules'][0]['importance'] == state['editorial_candidate']['modules'][0]['importance']
    pipeline.install(state, candidate)
    result = measure(state, candidate, state['editorial_zones'])
    assert [e['section_id'] for e in result['layout'] if e.get('emphasis_background')]==['module_0']
    assert_emphasis(state, candidate, durable=True)
    from src.critic.base import CriticContext
    from src.critic.quality import ColorQualityEvaluator
    state['design_layout']=result['layout']
    verdict=ColorQualityEvaluator().evaluate(CriticContext(state,state['critic_config']))
    assert set(verdict.metadata['panel_canvas_contrasts'])=={'module_module_0'}


@pytest.mark.parametrize('damage', ['missing', 'selection', 'source', 'color', 'receipt', 'compiled'])
def test_changed_or_lost_panel_palette_is_rejected(tmp_path, damage):
    state = state_for(tmp_path); raw = draft_for(state); raw['core_module_ids']=['module_0']
    setup(state, raw); pipeline.editorial_color_node(state)
    layout = None
    if damage=='missing': state.pop('editorial_emphasis')
    elif damage=='selection': state['editorial_candidate']['core_module_ids']=['module_1']
    elif damage=='source': state['editorial_emphasis']['panels']['module_0']['source']='module_visual'
    elif damage=='color': state['editorial_emphasis']['panels']['module_0']['resolved']['background']='#000000'
    elif damage=='receipt': (Path(state['sample_preparation_dir'])/'editorial/emphasis.json').unlink()
    else:
        layout = measure(state, state['editorial_candidate'], state['editorial_zones'])['layout']
        next(e for e in layout if e['type']=='section_container')['emphasis_background']='#000000'
    with pytest.raises((ValueError, FileNotFoundError)):
        assert_emphasis(state, durable=True, layout=layout)


def test_legacy_renderer_retains_importance_background(tmp_path):
    state=state_for(tmp_path); state.pop('editorial_version')
    state['color_scheme']={'mono_light':'#e6eaef'}
    slide=Presentation().slides.add_slide(Presentation().slide_layouts[6])
    Renderer()._render_section_container(slide, {'x':1,'y':1,'width':10,'height':5,'importance_level':1}, state)
    assert slide.shapes[0].fill.type==MSO_FILL.SOLID


def test_real_request_receipts_replay_without_calls_and_missing_response_refuses_delivery(monkeypatch,tmp_path):
    import json
    from types import SimpleNamespace
    import utils.langgraph_utils as language
    state=state_for(tmp_path); image(state,tmp_path,1,'#1C7448')
    raw=draft_for(state); raw['core_module_ids']=['module_0']; raw['modules'][0]['visual_ids']=['figure_1']
    setup(state,raw)
    calls=[]
    class Model:
        def __init__(self,*args):pass
        def reset(self):pass
        def step(self,message):
            parts=json.loads(message); assert len(parts)==2 and parts[1]['type']=='image_url'
            assert 'ONLY this module-owned image' in parts[0]['text']
            calls.append(message)
            return SimpleNamespace(content=json.dumps({'theme_color':'#1C7448'}),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    pipeline.editorial_color_node(state); pipeline.editorial_color_node(state)
    assert len(calls)==1
    root=Path(state['sample_preparation_dir'])/'editorial/palette/core_module_0'
    (root/'response_00.json').unlink()
    with pytest.raises(ValueError,match='receipts'):
        assert_emphasis(state,durable=True)


def test_changed_source_image_cannot_reuse_the_frozen_palette(monkeypatch,tmp_path):
    state=state_for(tmp_path); path=image(state,tmp_path,1,'#1C7448')
    raw=draft_for(state); raw['core_module_ids']=['module_0']; raw['modules'][0]['visual_ids']=['figure_1']
    setup(state,raw)
    monkeypatch.setattr(pipeline,'request',lambda *a,**k:{'theme_color':'#1C7448'})
    pipeline.editorial_color_node(state)
    Image.new('RGB',(800,400),'red').save(path)
    with pytest.raises(ValueError,match='resources or palette'):
        assert_emphasis(state,durable=True)
