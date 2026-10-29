"""Unchanged Rubrics behavior stays shared; editorial exceptions are explicit."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from PIL import Image

from test_editorial_generation import state_for,install
from src.critic.base import CriticContext
from src.config.critic_config import load_critic_config
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_critic import make_critic,editorial_critic_config,EditorialEvaluator,EditorialVisualEvaluator,CONTENT_KEYS


def test_unchanged_critic_implementations_and_weight_matrix_are_reused():
    from src.critic.evaluators import ColumnBalanceEvaluator
    from src.critic.section_fit import SectionFitEvaluator
    from src.critic.layout_family import LayoutFamilyCriticEvaluator
    base=load_critic_config();config=editorial_critic_config(base)
    assert config['dimensions']==base['dimensions']
    assert config['dimension_sources']==base['dimension_sources']
    evaluators={e.name:e for e in make_critic(config).evaluators}
    for cls in (ColumnBalanceEvaluator,SectionFitEvaluator,LayoutFamilyCriticEvaluator):
        assert type(evaluators[cls.name]) is cls


@pytest.mark.parametrize('family',['classic_three_column','top_hero_bottom_grid','modular_editorial_mosaic'])
def test_shared_geometric_scoring_matches_previous_route_for_same_layout(tmp_path,family):
    from src.layout.editorial_layout import measure
    from src.agents.layout_agent import LayoutAgent
    from src.critic.evaluators import ColumnBalanceEvaluator
    from src.critic.section_fit import SectionFitEvaluator
    state=install(state_for(tmp_path,family));physical=measure(state,state['editorial_candidate'],state['editorial_zones'])
    state.update(design_layout=physical['layout'],layout_spec=physical['spec'])
    state['final_column_analysis']=LayoutAgent()._generate_column_analysis(physical['layout'],state)
    previous=deepcopy(state);previous.pop('editorial_version');previous['source_editorial_version']='source_editorial_v1'
    for cls in (ColumnBalanceEvaluator,SectionFitEvaluator):
        actual=cls().evaluate(CriticContext(state,state['critic_config']))
        expected=cls().evaluate(CriticContext(previous,previous['critic_config']))
        assert actual.scores==expected.scores
        assert actual.issues==expected.issues
        assert actual.metadata==expected.metadata


def test_adequacy_retains_previous_duplicate_and_underuse_penalties(tmp_path):
    from src.workflow.source_critic import adequacy_result
    state=install(state_for(tmp_path))
    modules=state['editorial_candidate']['modules']
    modules[0]['entries'][1]['text']=modules[0]['entries'][0]['text']
    state['section_fit_analysis']={'ideal_band':[.95,1],'sections':{
        m['module_id']:{'utilization':.8 if i==0 else 1} for i,m in enumerate(modules)}}
    context=CriticContext(state,state['critic_config'])
    current=EditorialEvaluator('content_adequacy').evaluate(context)
    previous=deepcopy(state);previous['source_candidate']=deepcopy(state['editorial_candidate'])
    for m in previous['source_candidate']['modules']:m['source_refs']=[]
    previous['source_verification_report']={'covered_obligation_ids':[]}
    expected=adequacy_result(CriticContext(previous,previous['critic_config']))
    assert current.scores==expected.scores=={'content_quality':69}
    assert current.metadata['underfilled_section_count']==expected.metadata['underfilled_section_count']==1


def test_palette_preserves_logo_to_figure_fallback_style_and_diagnostics(monkeypatch,tmp_path):
    from src.agents.color_agent import ColorAgent
    state=state_for(tmp_path);logo=tmp_path/'logo.png';figure=tmp_path/'figure.png'
    for path in (logo,figure):Image.new('RGB',(100,40),'blue').save(path)
    state.update(aff_logo_path=str(logo),images={'1':{'path':str(figure)}},
                 classified_visuals={'key_visual':'figure_1'},style_overrides={'palette_variant':'accessible'})
    calls=[]
    def request(st,kind,payload,*args,**kwargs):
        calls.append(payload)
        if payload['source']=='affiliation_logo':raise TimeoutError('offline logo unavailable')
        return {'theme_color':'#1256AB'}
    monkeypatch.setattr(pipeline,'request',request)
    expected=deepcopy(state)
    monkeypatch.setattr(ColorAgent,'_extract_theme_from_logo',lambda *args:'#1256AB')
    ColorAgent()(expected)
    pipeline.editorial_color_node(state)
    assert state['color_scheme']==expected['color_scheme']
    assert state['color_provenance']['variant']==expected['color_provenance']['variant']
    assert state['color_provenance']['source']=='key_visual'
    assert [p['source'] for p in calls]==['affiliation_logo','key_visual']
    assert 'Readability' in calls[0]['instructions']
    assert (Path(state['output_dir'])/'content/color_scheme.json').exists()


def test_palette_uses_configured_fallback_and_does_not_treat_tables_as_figures(monkeypatch,tmp_path):
    from src.agents.color_agent import ColorAgent
    state=state_for(tmp_path);image=tmp_path/'table.png';Image.new('RGB',(30,30),'red').save(image)
    state.update(tables={'1':{'path':str(image)}},classified_visuals={'key_visual':'table_1'})
    monkeypatch.setattr(pipeline,'request',lambda *a,**k:pytest.fail('Table must not replace key-figure color fallback'))
    pipeline.editorial_color_node(state)
    assert state['color_provenance']['theme_color']==ColorAgent().color_config['fallback_theme']
    assert state['color_provenance']['source']=='configured_fallback'


def test_visual_critic_retains_actionable_locations_and_positive_patterns(monkeypatch,tmp_path):
    import src.workflow.editorial_critic as critic
    from src.layout.editorial_layout import measure
    state=install(state_for(tmp_path));physical=measure(state,state['editorial_candidate'],state['editorial_zones'])
    state.update(design_layout=physical['layout'],layout_spec=physical['spec'],current_candidate={'png_path':'unused'})
    module=state['editorial_candidate']['modules'][0]
    def response(*args,**kwargs):
        return {'scores':{k:80 for k in ('readability','visual_hierarchy','visual_balance','aesthetics')},
            'submetrics':{},'issues':[{'severity':'warning','scope':'layout','location':{
                'section_id':module['module_id'],'zone_id':module['zone_id'],'element_id':'invented'},
                'observation':'Small gap','required_outcome':'Review gap','allowed_operations':['adjust_zone_budget'],
                'forbidden_operations':['invent_claim']}],
            'positive_patterns':[{'scope':'visual','observation':'Clear figure'}],'reason':'Offline fixture'}
    monkeypatch.setattr(critic,'request',response)
    verdict=EditorialVisualEvaluator().evaluate(CriticContext(state,state['critic_config']))
    assert verdict.passed and verdict.positive_patterns
    assert verdict.issues[0]['location']=={'section_id':module['module_id'],'zone_id':module['zone_id']}
    assert verdict.issues[0]['allowed_operations']==['adjust_zone_budget']
    assert verdict.issues[0]['evidence']['location_validation']=='invalid identifiers removed'


@pytest.mark.parametrize('fails',[False,True])
def test_editorial_requests_preserve_strict_schema_and_restore_model(monkeypatch,tmp_path,fails):
    import utils.langgraph_utils as language
    from src.workflow.editorial_requests import request,obj,STRING
    state=state_for(tmp_path);agents=[];bindings=[]
    class BaseModel:
        def bind(self,**kwargs):bindings.append(kwargs);return object()
    class Agent:
        def __init__(self,*a):
            self.model=BaseModel();self.original=self.model;self.request_policy=object();agents.append(self)
        def reset(self):pass
        def step(self,message):
            assert self.model is not self.original
            if fails:raise TimeoutError('offline failed request')
            return SimpleNamespace(content='{"title":"Valid"}',input_tokens=1,output_tokens=2)
    monkeypatch.setattr(language,'ChatOpenAI',BaseModel)
    monkeypatch.setattr(language,'LangGraphAgent',Agent)
    if fails:
        with pytest.raises(TimeoutError):request(state,'editorial_metadata',{},obj({'title':STRING}),directory='editorial/strict')
    else:
        assert request(state,'editorial_metadata',{},obj({'title':STRING}),directory='editorial/strict')=={'title':'Valid'}
    assert agents[0].model is agents[0].original
    binding=bindings[0]['response_format']
    assert binding['type']=='json_schema' and binding['json_schema']['strict'] is True
    assert binding['json_schema']['schema']==obj({'title':STRING})
