"""Finite source loop, every family, actual rendering and final visual protocol."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from PIL import Image

from test_source_editorial import (source_state, verdict_for, accept, reading_review,
                                  no_remote_models, Agent)
from src.workflow import source_preparation as preparation
from src.workflow.source_editorial import make_board, install_candidate, normalize_candidate
from src.workflow.source_document import SourceOutputError
from src.workflow.source_reading import reading_context, draft_preview
from src.workflow.source_verification import assert_verified, assert_compiled_text
from src.layout.families import LayoutFamilyRegistry, compile_layout, valid_family_topology
from src.layout.feasibility import fit_family_layout, validate_compiled_layout
from src.layout.measurement_context import measurement_scope
from src.layout.repair_budget import sample_ledger
from utils.persistence import read_json, digest


@pytest.mark.parametrize('family',LayoutFamilyRegistry().ids())
def test_source_modules_use_all_fifteen_family_contracts(tmp_path,family):
    from test_layout_exploration import _MeasuredAgent
    count=min(6,sum(z['capacity'] for z in LayoutFamilyRegistry().get(family).zones))
    state=source_state(tmp_path,family=family,count=count)
    roles=['method','results','results','problem','conclusion','supporting']
    if family == 'method_flow_spine':
        roles=['method','method','results','problem','conclusion','supporting']
    raw={'modules':deepcopy(state['source_candidate']['modules'])}
    for i,m in enumerate(raw['modules']): m['narrative_role']=roles[i]
    install_candidate(state,normalize_candidate(raw,state));state['draft_layout_mode']=True
    board=make_board(state)
    config=deepcopy(state['critic_config']);config['explore_layout'].update(
        max_geometry_candidates_per_family=2,max_adaptive_geometry_candidates=2,max_exact_candidates=2,minimum_sections=1)
    result=fit_family_layout(_MeasuredAgent(),board,state,family,config=config)
    assert valid_family_topology(LayoutFamilyRegistry().get(family),result[1]['zones'])
    assert {s['section_id'] for s in result[0]['spatial_content_plan']['sections']}=={
        m['module_id'] for m in state['source_candidate']['modules']}
    assert not result[2]['content_quality_hints']['reading_conflicts']
    assert result[2]['content_quality_hints']['reading_flow']['policy_version']=='visual_natural_reading_v1'


def fake_fit(state, *, draft, physical_baseline=None):
    view=deepcopy(state);view['draft_layout_mode']=draft
    if draft:
        for c in view['poster_claims']['claims']: c['verified']=False
    return (make_board(view),{'family_id':state['sample_family']['family'],'zones':[]},
            {'content_quality_hints':{},'zone_utilization':{'zone':.9},'exact_bottom_gaps':{'zone':1.0}}),None


def fake_preview(state,result):
    root=Path(state['output_dir']);root.mkdir(parents=True,exist_ok=True)
    image=root/'fake_draft.png';Image.new('RGB',(20,20),'white').save(image)
    return {'png':str(image),'reading_context':reading_context(state,result[0],result[1],[],image,
        state['source_candidate']['candidate_id'])}


class NoopBalancer(Agent):
    def __init__(self): self.calls=[]
    def step(self,message):
        self.calls.append(message)
        data=json.loads(message)
        text=data[0]['text'] if isinstance(data,list) else message
        payload=json.loads(text.split('\nINPUT:\n',1)[1].split('\nCURRENT EDIT TASK (execute on the visible poster, not the paper):',1)[0].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
        review=reading_review(payload['reading_input'])
        if not payload['reading_input']['has_actual_image']:
            review.update(status='incomplete',primary_routes=[])
        response={'modules':payload['whole_candidate']['modules'], 'remove_module_ids':[], 'module_order':[],
            'lineage':[],'reason':'No change needed.','layout_requests':payload['previous_layout_requests']}
        if payload['reading_input']['has_actual_image']:
            response['reading_review']={k:v for k,v in review.items() if k not in payload['reading_input']['binding']}
        return SimpleNamespace(content=json.dumps(response),input_tokens=5,output_tokens=5)


def test_joint_quality_review_uses_one_existing_charge_and_ready_replays(monkeypatch,tmp_path):
    import src.workflow.source_verification as science
    state=source_state(tmp_path)
    monkeypatch.setattr(science,'request',lambda st,kind,data,schema,**kw:verdict_for(data['module'],st))
    monkeypatch.setattr(preparation,'_fit',fake_fit)
    monkeypatch.setattr(preparation,'draft_preview',fake_preview)
    agent=NoopBalancer();monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    initial=deepcopy(state)
    state=preparation.source_joint_preparation_node(state)
    assert not state['errors'] and assert_verified(state,state['joint_candidate']['board'])
    assert len(agent.calls)==1
    ledger=sample_ledger(state)[1]
    assert [c['phase'] for c in ledger['charges']]==['quality']
    assert state['source_reading_review']['status']=='clear'
    assert state['source_reading_review']['final_image_assessed'] is False
    assert not state['source_quality_report']['targets']['old_modules']
    replay=preparation.source_joint_preparation_node(initial)
    assert len(agent.calls)==1 and replay['joint_candidate']==state['joint_candidate']
    state['sample_edit_budget_dir']=str(tmp_path/'foreign_sample')
    with pytest.raises(ValueError,match='freeze identity'):
        preparation.install_source_candidate_node(state)


def test_quality_edit_stales_image_review_and_affects_only_two_neighbors(monkeypatch,tmp_path):
    state=source_state(tmp_path)
    result=fake_fit(state,draft=True)[0]
    monkeypatch.setattr(preparation,'draft_preview',fake_preview)
    class Balancer(NoopBalancer):
        def step(self,message):
            raw=super().step(message)
            value=json.loads(raw.content)
            first=value['modules'][0]
            first['entries'][0]['text']='The shared policy learns a common representation across agents.'
            value['lineage']=[{'new_module_id':first['module_id'],'old_module_ids':[first['module_id']]}]
            value['reason']='Clarify the actual shared mechanism.'
            raw.content=json.dumps(value);return raw
    agent=Balancer();monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    before=deepcopy(state['source_candidate'])
    state,changed=preparation.edit_candidate(state,{},'quality',result)
    assert changed and state['source_reading_review']['applies_to_reviewed_draft_candidate'] is False
    assert state['source_candidate']['modules'][1:]==before['modules'][1:]
    assert not state['verification_passed'] and not state.get('verified_claims')
    # A second logical quality call cannot add a free edit or judge.
    with pytest.raises(SourceOutputError,match='allowance exhausted'):
        preparation.edit_candidate(state,{'another':'review'},'quality',fake_fit(state,draft=True)[0])
    assert len(agent.calls)==1


def test_scientific_rejection_does_not_free_retry_or_publish(monkeypatch,tmp_path):
    import src.workflow.source_verification as science
    state=source_state(tmp_path)
    def reject(st,kind,data,schema,**kw):
        result=verdict_for(data['module'],st);result['status']='contradicted'
        result['reason']='Comparison direction is reversed.';return result
    monkeypatch.setattr(science,'request',reject)
    monkeypatch.setattr(preparation,'_fit',fake_fit)
    monkeypatch.setattr(preparation,'draft_preview',fake_preview)
    agent=NoopBalancer();monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    result=preparation.source_joint_preparation_node(state)
    assert result['errors'] and not result['verification_passed'] and not result.get('joint_candidate')
    assert len(agent.calls)==1 and sample_ledger(state)[1]['charges'][0]['phase']=='capacity'
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()
    progress=list(Path(state['sample_preparation_dir']).glob('source/verification/*/progress.json'))
    assert progress and read_json(progress[0])['payload']['status']=='rejected'


def test_actual_draft_preview_isolated_and_editable_then_final_text_bound(monkeypatch,tmp_path):
    from src.agents.layout_agent import LayoutAgent
    from src.agents.font_agent import FontAgent
    from src.agents.color_agent import ColorAgent
    from src.agents.section_title_designer import SectionTitleDesigner
    from pptx import Presentation
    state=source_state(tmp_path,family='classic_three_column',count=3)
    state['critic_config']['explore_layout'].update(max_geometry_candidates_per_family=1,
        max_adaptive_geometry_candidates=1,max_exact_candidates=1)
    state['critic_config']['composition_refinement']['enabled']=False
    with measurement_scope(state['critic_config'].get('layout_performance')):
        state['draft_layout_mode']=True
        result,failure=preparation._fit(state,draft=True)
        assert failure is None,failure
        record=draft_preview(state,result)
    assert Path(record['png']).is_file() and Path(record['pptx']).is_file()
    assert record['status']=='draft_not_publishable' and not state.get('current_candidate')
    assert not state.get('verified_claims') and record==draft_preview(state,result)
    deck=Presentation(record['pptx']);assert len(deck.slides)==1
    visible=' '.join(s.text for s in deck.slides[0].shapes if s.has_text_frame)
    assert 'level-2' in visible and 'Shared learning A' in visible
    # Use the exact same compiler and deterministic font styling on actual proof.
    accept(state,monkeypatch);state['draft_layout_mode']=False
    state['optimized_story_board']=result[0];state['story_board']=result[0];state['layout_spec']=result[1]
    color=ColorAgent();state['color_scheme']=color._add_contrast_color(color._generate_color_scheme('#1E3A8A'))
    state['section_title_design']=SectionTitleDesigner()._generate_colorblock_design(result[0],state['color_scheme'])
    state=LayoutAgent()(state,mode='final')
    font=FontAgent();state['styled_layout']=font._apply_styling(state['design_layout'],state['color_scheme'],{'section_keywords':{}},state)
    assert assert_compiled_text(state)
    next(e for e in state['styled_layout'] if e['type']=='text')['content']+=' invented'
    with pytest.raises(ValueError,match='compiled scientific text'):assert_compiled_text(state)


def test_final_visual_uses_one_existing_call_and_actual_image_bindings(monkeypatch,tmp_path):
    from src.workflow.source_critic import final_visual_payload
    from src.critic.visual import VisualCriticEvaluator
    from src.critic.base import CriticContext
    import utils.langgraph_utils as language
    state=accept(source_state(tmp_path),monkeypatch)
    board=make_board(state);state['story_board']=board;state['optimized_story_board']=board
    state['layout_spec']={'zones':[]};state['styled_layout']=[]
    image=tmp_path/'actual_final.png';Image.new('RGB',(20,20),'white').save(image)
    state['current_candidate']={'candidate_id':'actual_final'}
    evaluator=VisualCriticEvaluator();calls=[]
    class Visual(Agent):
        def step(self,message):
            calls.append(message)
            prompt=json.loads(message)[0]['text']
            data=json.loads(prompt.split('Use the COMPLETE schema below (including reading_review); empty location strings mean unknown.\n',1)[1].split('\nCURRENT EDIT TASK (execute on the visible poster, not the paper):',1)[0].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
            assert all('text' in m and 'bbox_inches' in m for m in data['modules'])
            assert 'reading_order' not in data and 'source_order' not in data
            raw={'scores':{k:80 for k in evaluator._DIMENSIONS},'submetrics':{k:80 for k in evaluator._SUBMETRICS},
                 'issues':[],'positive_patterns':[],'reading_review':{k:v for k,v in reading_review(data).items() if k not in data['binding']}}
            return SimpleNamespace(content=json.dumps(raw),input_tokens=5,output_tokens=5)
    monkeypatch.setattr(language,'LangGraphAgent',lambda *a,**kw:Visual())
    raw,context=final_visual_payload(evaluator,CriticContext(state,state['critic_config']),image)
    assert len(calls)==1 and raw['reading_review']['status']=='clear'
    assert state['source_final_reading_review']['candidate_id']=='actual_final'
    assert state['source_final_reading_review']['image_digest']==context['binding']['image_digest']
    assert state['tokens'].input_vision==5


def test_default_source_runner_reaches_real_pptx_png_and_all_score_publication(monkeypatch,tmp_path):
    """Offline model transcripts, real fitter/compiler/font/render/critic/store boundaries."""
    from src.state.poster_state import create_state
    from src.workflow.exploration_runner import PosterExplorationRunner
    from src.workflow.exploration_store import ExplorationStore
    from src.workflow.source_document import source_document_node
    from src.workflow.source_critic import CONTENT_KEYS
    from src.critic.visual import VisualCriticEvaluator
    from src.agents.font_agent import FontAgent
    import src.workflow.source_editorial as editorial
    import src.critic.visual as visual
    import utils.langgraph_utils as language
    prototype=source_state(tmp_path/'prototype',family='classic_three_column',count=3)
    source_visual=tmp_path/'source_diagram.png'
    Image.new('RGB',(800,360),'navy').save(source_visual)
    assets={'1':{'path':str(source_visual),'aspect':800/360,'caption':'Shared learning architecture'}}
    prototype['source_candidate']['modules'][0]['visual_ids']=['figure_1']
    pdf=tmp_path/'paper.pdf'
    import pymupdf
    from utils.source_pdf import transcribe_regions
    with pymupdf.open() as document:
        page=document.new_page()
        assert page.insert_textbox(page.rect+ (20,20,-20,-20), prototype['raw_text'],fontsize=9)>0
        page.insert_image(pymupdf.Rect(20,500,570,748),filename=str(source_visual))
        document.save(pdf)
    with pymupdf.open(pdf) as document:
        pages=[{'page_index':0,'bbox':list(document[0].rect),'regions':[
            {'region_id':str(i),'kind':'Text','bbox':list(b[:4]),
             'heading_level':None,'marker_text':b[4]} for i,b in enumerate(document[0].get_text('blocks')) if b[6]==0]}]
    canonical,audit=transcribe_regions(pdf,pages,prototype['raw_text'])
    assert not audit['issues']

    original=create_state(str(pdf),text_model='local-text',vision_model='local-vision',width=54,height=36,poster_name='source_integration')
    def paper_node(state):
        state.update(raw_text=canonical,source_extraction_report=audit,section_chunks=[],images=deepcopy(assets),tables={},
                     classified_visuals={'method_workflow':['figure_1']},
                     narrative_content=prototype['narrative_content'])
        return state
    calls=[]
    evaluator=VisualCriticEvaluator()
    class Model:
        def __init__(self,system,config,state,name):self.state=state;self.agent_name=name
        def reset(self):pass
        def step(self,message):
            calls.append(self.agent_name)
            try:parts=json.loads(message)
            except ValueError:parts=None
            text=parts[0]['text'] if isinstance(parts,list) else message
            prefix=text.split('\nCURRENT EDIT TASK (execute on the visible poster, not the paper):',1)[0].split('\nCURRENT WRITING TASK:',1)[0].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0]
            if self.agent_name.startswith('source_'):
                data=json.loads(prefix.split('\nINPUT:\n',1)[1])
            if self.agent_name=='source_narrative':value=deepcopy(prototype['source_narrative_plan'])
            elif self.agent_name=='source_curator':value={'modules':deepcopy(prototype['source_candidate']['modules'])}
            elif self.agent_name=='source_verifier':value=verdict_for(data['module'],self.state)
            elif self.agent_name=='source_balancer':value={'modules':[], 'remove_module_ids':[], 'module_order':[],
                'reading_review':{k:v for k,v in reading_review(data['reading_input']).items() if k not in data['reading_input']['binding']},'lineage':[],'reason':'Clear compact explanation.',
                'layout_requests':data['previous_layout_requests']}
            elif self.agent_name=='critic_visual':
                data=json.loads(prefix.split('Use the COMPLETE schema below (including reading_review); empty location strings mean unknown.\n',1)[1])
                value={'scores':{k:20 for k in evaluator._DIMENSIONS},'submetrics':{k:20 for k in evaluator._SUBMETRICS},
                    'issues':[],'positive_patterns':[],'reading_review':{k:v for k,v in reading_review(data).items() if k not in data['binding']}}
            elif self.agent_name=='critic_content':value={'scores':{k:20 for k in CONTENT_KEYS},'reason':'Synthetic fixture quality only.'}
            else:raise AssertionError('Unexpected model stage '+self.agent_name)
            if self.agent_name.startswith('source_'):
                from src.workflow.source_document import paragraph_hints
                value=paragraph_hints(value,self.state['source_document'])
            return SimpleNamespace(content=json.dumps(value),input_tokens=9,output_tokens=4)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    monkeypatch.setattr(visual,'LangGraphAgent',Model)
    monkeypatch.setattr(editorial,'agent_for',lambda state,kind,vision=False:Model('',None,state,kind))
    monkeypatch.setattr(FontAgent,'_identify_keywords',lambda *a:{'section_keywords':{}})
    monkeypatch.setattr(LayoutFamilyRegistry,'choose_with_report',lambda self,*a,**kw:(
        'classic_three_column',{'enabled_families':self.ids(),'test_policy':'offline_fixed_family'}))
    store=ExplorationStore(tmp_path/'independent_store')
    config=deepcopy(original['critic_config']) if original.get('critic_config') else __import__('src.config.critic_config',fromlist=['load_critic_config']).load_critic_config()
    config['explore_layout'].update(max_geometry_candidates_per_family=1,max_adaptive_geometry_candidates=1,max_exact_candidates=1)
    config['composition_refinement']['enabled']=False
    # The retired source route is now an explicit diagnostic interface.
    from src.workflow.source_editorial import source_narrative_node,source_curator_node
    from src.workflow.source_preparation import source_joint_preparation_node,install_source_candidate_node,compile_source_layout_node
    from src.agents.color_agent import color_agent_node
    from src.agents.section_title_designer import section_title_designer_node
    from src.agents.font_agent import font_agent_node
    from src.agents.layout_preflight import layout_preflight_node
    from src.agents.renderer import renderer_node
    from src.agents.render_fit_audit import render_fit_audit_node
    runner=PosterExplorationRunner(config=config,storage=store,paper_nodes=[paper_node,source_document_node],
        preparation_nodes=[source_narrative_node,source_curator_node,source_joint_preparation_node],
        design_nodes=[install_source_candidate_node,color_agent_node,section_title_designer_node,
                      compile_source_layout_node,font_agent_node,layout_preflight_node,renderer_node,render_fit_audit_node],
        samples=1,random_seed=42)
    result=runner.run(original)
    assert result['run_state']['status']=='COMPLETED',result.get('errors')
    records=store.results(runner.run_id)
    assert len(records)==1 and records[0]['poster_id'],records
    bundle=store.verify_poster(records[0]['poster_id'])
    assert (bundle/'poster.png').is_file() and (bundle/'poster.pptx').is_file()
    assert (bundle/'template.png').is_file() and (bundle/'template.pptx').is_file()
    frozen=read_json(bundle/'diagnostics/joint_candidate.json')
    assert 'figure_1' in {v['visual_id'] for s in frozen['board']['spatial_content_plan']['sections'] for v in s['visual_assets']}
    assert records[0]['grouping']=='unclassified'
    assert calls.count('source_narrative')==calls.count('source_curator')==calls.count('source_balancer')==1
    assert calls.count('source_verifier')==3 and calls.count('critic_visual')==1
    assert calls.count('critic_content')==1 and not any('evidence' in name for name in calls)
    paper=store.paper_foundation(runner.run_id, 'sample_000001')
    assert 'evidence_bank' not in paper and paper['source_document']
    saved=read_json(bundle/'diagnostics/source_final_reading_review.json')
    assert saved['status']=='clear' and saved['candidate_id']==records[0]['candidate_id']
    report=read_json(bundle/'evaluation.json')
    assert report['rubric_version']=='academic_poster_source_editorial_v1'
    assert report['critic_system_version']=='5.0.0'
    assert records[0]['score'] is not None and records[0]['score']<78
    assert not report['reference_passed'] and not report['hard_gate_passed']


def test_invalid_verdict_does_not_unlock_capacity_prose_retry(monkeypatch,tmp_path):
    import src.workflow.source_verification as science
    from src.workflow.source_document import SourceProtocolError
    state=source_state(tmp_path)
    def malformed(*args,**kwargs):raise SourceProtocolError('Missing supported verdict after bounded recovery')
    monkeypatch.setattr(science,'request',malformed)
    monkeypatch.setattr(preparation,'_fit',fake_fit)
    monkeypatch.setattr(preparation,'edit_candidate',lambda *a,**kw:pytest.fail('Protocol failures cannot spend prose edits'))
    result=preparation.source_joint_preparation_node(state)
    assert result['errors'] and not result['verification_passed']
    assert not sample_ledger(state)[1]['charges']
