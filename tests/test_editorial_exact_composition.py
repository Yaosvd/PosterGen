"""Exact initial directions, actual aspect-derived candidates and readable images."""
from copy import deepcopy

import pytest

from test_editorial_generation import state_for, draft_for, install
from test_editorial_composition import hags_state
from src.agents.layout_agent import LayoutAgent
from src.layout import module_composition as composition
from src.layout.editorial_layout import measure
from src.layout.editorial_composition import initial_fit, HORIZONTAL, VERTICAL, assert_composition


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    from src.layout.measurement_context import measurement_scope
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected live model'))
    with measurement_scope():
        yield


def neds_state(tmp_path):
    state=state_for(tmp_path,'central_evidence_band')
    state['images']={'1':{'aspect':2.157556270096463,'caption':'Architecture'}}
    raw=draft_for(state)
    method=raw['modules'][2]
    method.update(title='NEDS Architecture',visual_ids=['figure_1'],presentation_style='plain')
    texts=[
        'Modality-specific tokenizers convert spike counts and continuous behaviors into 20ms temporal tokens, while discrete behaviors are replicated to match this resolution.',
        'Learnable modality, temporal (RoPE), and session embeddings are added to the tokens to provide context for the shared encoder.',
        'A shared encoder-only transformer processes the concatenated unified sequence, trained to predict masked tokens according to the selected masking scheme.',
        'Modality-specific linear decoders reconstruct the original data, using Poisson NLL for neural spikes, MSE for continuous behaviors, and Cross-Entropy for discrete behaviors.',
    ]
    method['entries']=[{'item_id':f'e{i}','text':text,'display_label':'','parent_item_id':''}
                       for i,text in enumerate(texts)]
    return install(state,raw)


def test_neds_regression_exact_initial_choice_fits_wrapped_original_prose(monkeypatch,tmp_path):
    state=neds_state(tmp_path)
    section=state['optimized_story_board']['spatial_content_plan']['sections'][2]
    agent=LayoutAgent()
    assert composition._adaptive_side_by_side_plan(agent,section,52,8.6428,state) is None
    monkeypatch.setattr(composition,'fast_body_height',lambda *a:pytest.fail('Coarse rejection before initial lock'))
    plan=composition.side_by_side_plan(agent,section,52,8.6428,state)
    assert plan['measurement']=='exact'
    assert plan['title_height']+plan['body_height']<8.6428
    assert plan['visuals'][0]['width']>12
    assert plan['visuals'][0]['height']>5.5
    elements=agent._create_section_elements(section,1,1,52,state,8.6428)
    text=next(e for e in elements if e['type']=='text')
    visual=next(e for e in elements if e['type']=='visual')
    assert visual['y']==text['y'] and visual['x']+visual['width']<text['x']
    assert max(e['y']+e['height'] for e in elements)-1<8.6428
    assert [p['text'] for p in text['editorial_paragraphs']]==section['text_content']
    assert text['height']>4  # Original long points wrap; no single-line restriction.


def test_candidates_have_distinct_actual_image_widths_and_use_only_four_exact_measurements(monkeypatch,tmp_path):
    state=neds_state(tmp_path); agent=LayoutAgent()
    section=state['optimized_story_board']['spatial_content_plan']['sections'][2]
    widths=[]; original=agent._measure_body_text
    def measured(text_content,column_width,*args,**kwargs):
        widths.append(column_width)
        return original(text_content,column_width,*args,**kwargs)
    monkeypatch.setattr(agent,'_measure_body_text',measured)
    plan=composition.side_by_side_plan(agent,section,52,8.6428,state)
    assert plan
    assert len(widths)==4 and len(set(widths))==4  # One vertical reference plus three real splits.
    assert widths[1]>widths[2]>widths[3]


@pytest.mark.parametrize('aspect',[.4,1,2,4,8])
def test_horizontal_choice_preserves_original_aspect_and_never_reduces_vertical_image_area(tmp_path,aspect):
    state=neds_state(tmp_path); state['images']['1']['aspect']=aspect
    section=state['optimized_story_board']['spatial_content_plan']['sections'][2]
    agent=LayoutAgent()
    plan=composition.side_by_side_plan(agent,section,52,12,state)
    if plan:
        visual=plan['visuals'][0]
        assert visual['width']/visual['height']==pytest.approx(aspect)
        vw,vh,_=agent._calculate_visual_height('figure_1',51.4,state,12)
        assert plan['visual_area']>=vw*vh-.001
        assert plan['title_height']+plan['body_height']<12


def test_exact_choice_does_not_buy_a_fit_by_shrinking_text_or_images(tmp_path):
    state=neds_state(tmp_path)
    section=deepcopy(state['optimized_story_board']['spatial_content_plan']['sections'][2])
    section['text_content']=['A long explanation requiring many wrapped lines. '*80]
    assert composition.side_by_side_plan(LayoutAgent(),section,52,4,state) is None
    assert state['styling_interfaces']['font_sizes']['body_text']==44


def test_precise_initial_direction_is_durable_and_locked_under_later_overflow(tmp_path):
    state=hags_state(tmp_path); first=initial_fit(state,fitter=measure)
    assert state['editorial_composition']['modules']['module_2']==HORIZONTAL
    candidate=deepcopy(state['editorial_candidate'])
    candidate['modules'][2]['entries'][0]['text']='A long explanation. '*100
    result=measure(state,candidate,state['editorial_zones'])
    assert next(m for m in result['report']['modules'] if m['module_id']=='module_2')['body_layout']==HORIZONTAL
    assert_composition(state,candidate,result['layout'],durable=True)
    assert first['layout']!=result['layout']


def test_narrow_module_keeps_vertical_and_legacy_does_not_use_new_exact_selector(monkeypatch,tmp_path):
    state=neds_state(tmp_path)
    section=state['optimized_story_board']['spatial_content_plan']['sections'][2]
    assert composition.side_by_side_plan(LayoutAgent(),section,12,22,state) is None
    state.pop('editorial_version')
    monkeypatch.setattr(composition,'_editorial_side_by_side_plan',lambda *a,**k:pytest.fail('Legacy behavior changed'))
    assert composition.side_by_side_plan(LayoutAgent(),section,52,8.6428,state) is None
