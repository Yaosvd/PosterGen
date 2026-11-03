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
from src.workflow.editorial_critic import make_critic,editorial_critic_config,EditorialVisualEvaluator


@pytest.mark.parametrize('factory', ['direct', 'factory'])
def test_current_critic_uses_shared_measurements_without_rule_score_sources(factory):
    from src.workflow.editorial_critic import MeasurementEvaluator
    from src.critic.evaluators import ColumnBalanceEvaluator
    from src.critic.section_fit import SectionFitEvaluator
    from src.critic.layout_family import LayoutFamilyCriticEvaluator
    from src.critic.engine import PosterCritic
    base=load_critic_config();config=editorial_critic_config(base)
    assert [v['weight'] for v in config['dimensions'].values()]==[.25,.20,.20,.10,.15,.05,.05]
    assert set(config['submetric_sources'].values())=={'grounding','information_narrative','visual'}
    current=PosterCritic(base) if factory=='direct' else make_critic(config)
    assert type(current) is PosterCritic
    evaluators={e.name:e for e in current.evaluators}
    assert 'content_adequacy' not in evaluators
    for cls in (ColumnBalanceEvaluator,SectionFitEvaluator,LayoutFamilyCriticEvaluator):
        assert type(evaluators[cls.name]) is MeasurementEvaluator
        assert type(evaluators[cls.name].evaluator) is cls


@pytest.mark.parametrize('family',['classic_three_column','top_hero_bottom_grid','modular_editorial_mosaic'])
def test_shared_geometric_measurements_match_for_same_layout(tmp_path,family):
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
        assert actual.issues==expected.issues
        assert actual.metadata==expected.metadata


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
    from critic_fixtures import content_reply,visual_reply,finding
    from src.layout.editorial_layout import measure
    state=install(state_for(tmp_path));physical=measure(state,state['editorial_candidate'],state['editorial_zones'])
    png=tmp_path/'poster.png';Image.new('RGB',(40,40),'white').save(png)
    state.update(design_layout=physical['layout'],layout_spec=physical['spec'],current_candidate={'png_path':str(png)})
    monkeypatch.setattr(critic,'assert_editorial_ready',lambda *a,**k:None)
    module=state['editorial_candidate']['modules'][0]
    def response(st,kind,*args,**kwargs):
        if kind=='editorial_content_critic':return content_reply(st['editorial_candidate']['modules'])
        raw=visual_reply(st['editorial_candidate']['modules'])
        raw['issues']=[finding(module['module_id'],scope='layout',severity='warning')]
        raw['issues'][0]['location']['zone_id']=module['zone_id']
        raw['issues'][0]['allowed_operations']=['adjust_zone_budget']
        return raw
    monkeypatch.setattr(critic,'request',response)
    verdict=EditorialVisualEvaluator().evaluate(CriticContext(state,state['critic_config']))
    assert verdict.passed and verdict.positive_patterns and "scores" not in verdict.to_dict()
    assert verdict.issues[0]['location']=={'section_id':module['module_id'],'zone_id':module['zone_id']}
    assert verdict.issues[0]['allowed_operations']==['adjust_zone_budget']
    assert verdict.issues[0]['evidence']['source']=='model'


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
