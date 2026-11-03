"""Retained source preparation diagnostics; the retired source Critic is unavailable."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from PIL import Image

from test_source_editorial import source_state, verdict_for, accept, reading_review, Agent
from src.workflow import source_preparation as preparation
from src.workflow.source_editorial import make_board, install_candidate, normalize_candidate
from src.workflow.source_document import SourceOutputError
from src.workflow.source_reading import reading_context, draft_preview
from src.workflow.source_verification import assert_verified, assert_compiled_text
from src.layout.families import LayoutFamilyRegistry, valid_family_topology
from src.layout.feasibility import fit_family_layout
from src.layout.measurement_context import measurement_scope
from src.layout.repair_budget import sample_ledger
from utils.persistence import read_json


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


def test_source_diagnostic_helpers_require_explicit_critic(tmp_path):
    from src.workflow.exploration_runner import PosterExplorationRunner
    from src.workflow.exploration_store import ExplorationStore
    with pytest.raises(ValueError, match='Retired source Critic'):
        PosterExplorationRunner(storage=ExplorationStore(tmp_path / 'store'),
            paper_nodes=[], preparation_nodes=[preparation.source_joint_preparation_node], design_nodes=[])
    supplied = lambda state: state
    runner = PosterExplorationRunner(storage=ExplorationStore(tmp_path / 'explicit-store'),
        paper_nodes=[], preparation_nodes=[preparation.source_joint_preparation_node], design_nodes=[],
        critic=supplied)
    assert runner.critic is supplied and runner.source_default
