"""Single-family global writing, draft isolation and bounded science/space feedback."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from src.config.critic_config import load_critic_config
from src.layout.family_capacity import family_brief, plan_family_capacity
from src.layout.repair_budget import available_rounds, charge_round, sample_ledger
from src.workflow import joint_preparation as joint
from src.workflow.sample_modules import normalize_module_plan, finalize_modules, build_module_board
from src.workflow.sample_module_writing import write_joint_poster, normalize_joint_body
from utils.grounded_content import layout_claims, all_publishable_claims
from utils.persistence import read_json, digest
from test_sample_module_body import module_state, raw_plan, expression


@pytest.fixture(autouse=True)
def no_remote_models(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **kw: pytest.fail('CPU tests must not construct a remote model'))


def state_for(tmp_path, count=1):
    tmp_path.mkdir(parents=True, exist_ok=True)
    state = module_state(tmp_path)
    state.update(narrative_content={'meta':{'title':'Synthetic paper','authors':''}}, joint_preparation=True, sample_family={'family': 'four_column_modular'},
        paper_foundation_digest='paper', sample_edit_budget_dir=str(tmp_path/'sample'),
        sample_preparation_dir=str(tmp_path/'sample/preparation'),
        output_dir=str(tmp_path/'sample/preparation'), critic_config=load_critic_config(),
        iteration_context={'run_id':'run_test','sample_id':'sample_000001','random_seed':42,
            'generation_purpose':'explore','layout_family':'four_column_modular'})
    if count == 1:
        state['sample_module_plan'] = normalize_module_plan(raw_plan(), state)
        claim = expression(); claim.update(essential=False, verified=False)
        state['poster_claims'] = {'claims': [claim]}
    else:
        units, evidence, modules, claims = [], [], [], []
        for i in range(count):
            sid, eid, mid = f'u{i}', f'e{i}', f'display_{i+1:03d}'
            text = 'The grounded method predicts behavior from recorded neural signals under the measured experimental conditions.'
            units.append({'section_id':sid,'narrative_role':'results','importance':1,
                'evidence_ids':[eid],'required_evidence_ids':[eid]})
            evidence.append({'evidence_id':eid,'claim':text,'source_excerpt':text})
            modules.append({'module_id':mid,'title':f'Prediction {chr(65+i)}','writing_brief':'Explain the measured prediction.',
                'source_plan_unit_ids':[sid],'evidence_ids':[eid],'visual_ids':[]})
            claim = expression(text);claim.update(claim_id=f'c{i}',display_module_id=mid,section_id=sid,
                source_plan_unit_ids=[sid],evidence_ids=[eid],required_evidence_ids=[eid],
                essential=False,verified=False,discourse_kind='result')
            for key in ('support_map','covered_required_evidence_ids'): claim.pop(key)
            claims.append(claim)
        state['narrative_plan']={'sections':units}
        state['evidence_bank']={'items':evidence}
        state['sample_module_plan']=normalize_module_plan({'modules':modules},state)
        state['poster_claims']={'claims':claims}
    Path(state['output_dir']).mkdir(parents=True)
    joint.refresh_contexts(state['poster_claims']['claims'])
    plan_family_capacity(state)
    return state


def accept(state):
    claims = deepcopy(state['poster_claims']['claims'])
    for c in claims:
        c.update(verified=True,covered_required_evidence_ids=c['required_evidence_ids'],
            support_map=[{'quote':c['text'],'evidence_ids':c['evidence_ids'],'supported':True}])
    state['verified_claims']={'claims':claims};state['verification_passed']=True
    finalize_modules(state)
    return state


def fit_result(state):
    claims=state['poster_claims']['claims']
    view={**state,'draft_layout_mode':True}
    for c in claims:c['verified']=False
    board=build_module_board(view,claims,joint.draft_protection(view))
    return board, {'family_id':'four_column_modular','zones':[]}, {'content_quality_hints':{}}


def test_explicit_physical_view_never_enters_publishable_bank(tmp_path):
    state=state_for(tmp_path);state['draft_layout_mode']=True
    assert layout_claims(state) and not all_publishable_claims(state)
    assert not state.get('verified_claims') and not state.get('verification_passed')
    state['poster_claims']['claims'][0]['verified']=True
    with pytest.raises(ValueError,match='cannot claim'):layout_claims(state)


def test_draft_cannot_pass_publication_readiness(tmp_path):
    from src.workflow.generation_failure import require_rendered_candidate, GenerationFailure
    state=state_for(tmp_path);state['draft_layout_mode']=True
    with pytest.raises(GenerationFailure,match='unverified physical draft'):
        require_rendered_candidate(state,'candidate',tmp_path)


def test_space_brief_has_multiple_module_seats_and_no_false_fit_certificate(tmp_path):
    state=state_for(tmp_path,6)
    brief=family_brief(state)
    assert len(brief['zones'])==4 and sum(z['capacity'] for z in brief['zones']) >=6
    assert brief['certifies_feasible_layout'] is False
    targets=state['family_capacity']['modules']
    assert len(targets)==6 and any(sum(t['zone_id']==z['zone_id'] for t in targets)>1 for z in brief['zones'])
    assert all(m['space_target'] and m['soft_word_range'][0]>0 for m in state['sample_module_plan']['modules'])


def test_six_independent_modules_fit_real_four_column_geometry_without_verified_flags(tmp_path):
    state=state_for(tmp_path,6)
    result,failure=joint._fit(state,draft=True)
    assert result is not None, failure
    assert result[1]['family_id']=='four_column_modular'
    assert len(result[0]['spatial_content_plan']['sections'])==6
    assert any(len(z['section_ids'])>1 for z in result[1]['zones'])
    assert not all_publishable_claims(state)


class Agent:
    def __init__(self, value):self.value=value;self.calls=[]
    def reset(self):pass
    def step(self,prompt):
        self.calls.append(prompt)
        return SimpleNamespace(content=json.dumps(self.value),input_tokens=10,output_tokens=20)


def test_global_writer_calls_once_and_sees_every_module_space_and_neighbor(tmp_path):
    state=state_for(tmp_path,3)
    raw={'modules':[{'module_id':m['module_id'],'claims':[{'item_id':'a','text':state['evidence_bank']['items'][i]['source_excerpt'],
        'evidence_ids':[f'e{i}'],'essential':True,'kind':'result'}]} for i,m in enumerate(state['sample_module_plan']['modules'])]}
    agent=Agent(raw);write_joint_poster(state,agent)
    assert len(agent.calls)==1
    assert all(m['module_id'] in agent.calls[0] for m in state['sample_module_plan']['modules'])
    assert 'width_inches' in agent.calls[0] and 'four_column_modular' in agent.calls[0]
    assert all(c['essential_suggestion'] and not c['essential'] and c['verified'] is False for c in state['poster_claims']['claims'])
    # A stage replay reads the archived raw response without another model call.
    write_joint_poster(state,agent);assert len(agent.calls)==1


def test_required_evidence_protects_science_without_locking_every_suggested_paragraph(tmp_path):
    state=state_for(tmp_path);a=state['poster_claims']['claims'][0]
    b=deepcopy(a);b.update(claim_id='optional',essential=True,essential_suggestion=True,
        covered_required_evidence_ids=[],required_evidence_ids=[])
    state['poster_claims']['claims'].append(b)
    accept(state)
    protected=state['module_body_report']['required_claim_ids']
    assert a['claim_id'] in protected and 'optional' not in protected


def test_three_capacity_rounds_and_one_reserved_quality_survive_restart(tmp_path):
    state=state_for(tmp_path);settings=state['critic_config']['capacity_repair']
    for i in range(3):assert charge_round(state,'capacity',settings,kind=f'round{i}')
    assert available_rounds(deepcopy(state),'capacity',settings)==0
    assert not charge_round(state,'capacity',settings)
    assert charge_round(state,'quality',settings)
    assert available_rounds(state,'quality',settings)==0
    assert not charge_round(state,'quality',settings)
    assert len(sample_ledger(state)[1]['charges'])==4


@pytest.mark.parametrize('mutation',['digest','family','missing'])
def test_ledger_corruption_or_missing_history_fails_closed(tmp_path,mutation):
    state=state_for(tmp_path);charge_round(state,'capacity',state['critic_config']['capacity_repair'])
    path=sample_ledger(state)[0]
    if mutation=='digest':
        raw=read_json(path);raw['payload']['charges']=[];path.write_text(json.dumps(raw))
    elif mutation=='family':state['sample_family']['family']='classic_three_column'
    else:
        path.unlink();request=Path(state['output_dir'])/'joint/edits/a/request_00.json'
        request.parent.mkdir(parents=True);request.write_text('{}')
    with pytest.raises(ValueError):sample_ledger(state)


def revision(state,omit=False):
    claim=state['poster_claims']['claims'][0]
    row={'source_claim_id':claim['claim_id'],'text':claim['text'],'evidence_ids':claim['evidence_ids']}
    if omit:row={'source_claim_id':claim['claim_id'],'omit':True,'reason':'secondary'}
    return {'modules':[{'module_id':'display_001','claims':[row]}]}


def test_editorial_revision_retains_roots_and_explicit_preservation_contract(tmp_path):
    state=state_for(tmp_path);before=deepcopy(state['poster_claims']['claims'][0])
    claims,omitted=joint.normalize_editorial_revision(revision(state),state,['display_001'])
    assert not omitted and claims[0]['claim_id']==before['claim_id']
    assert claims[0]['source_plan_unit_ids']==before['source_plan_unit_ids']
    assert claims[0]['editorial_revision']['required_assertions']
    assert claims[0]['verified'] is False and 'support_map' not in claims[0]


def test_editorial_omission_cannot_remove_an_indispensable_expression(tmp_path):
    state=state_for(tmp_path)
    with pytest.raises(joint.JointContentFailure,match='protected'):
        joint.normalize_editorial_revision(revision(state,True),state,['display_001'])


def test_optional_omission_preserves_local_dependency_records(tmp_path):
    state=state_for(tmp_path);claim=state['poster_claims']['claims'][0]
    extra=deepcopy(claim);extra.update(claim_id='optional',evidence_ids=['e1'],required_evidence_ids=[],text=claim['text']+' Additional context.')
    state['poster_claims']['claims'].append(extra)
    raw=revision(state);raw['modules'][0]['claims'].append({'source_claim_id':'optional','omit':True,'reason':'redundant'})
    claims,omitted=joint.normalize_editorial_revision(raw,state,['display_001'])
    assert len(claims)==1 and omitted[0]['claim_id']=='optional'
    claim['requires_claim_ids']=['optional']
    with pytest.raises(joint.JointContentFailure,match='prerequisite'):
        joint.normalize_editorial_revision(raw,state,['display_001'])


@pytest.mark.parametrize('bad',['foreign','number','duplicate'])
def test_revision_cannot_add_foreign_numbers_evidence_or_duplicate_origins(tmp_path,bad):
    state=state_for(tmp_path);raw=revision(state)
    if bad=='foreign':raw['modules'][0]['claims'][0]['evidence_ids']=['foreign']
    if bad=='number':raw['modules'][0]['claims'][0]['text']='The model has 99999 neurons.'
    if bad=='duplicate':raw['modules'][0]['claims']*=2
    with pytest.raises(joint.JointContentFailure):joint.normalize_editorial_revision(raw,state,['display_001'])


def test_controller_remeasures_actual_verified_prose_before_freezing(monkeypatch,tmp_path):
    state=state_for(tmp_path);seen=[]
    def fit(current,*,draft):
        seen.append((draft,current['poster_claims']['claims'][0]['text']))
        return fit_result(current),None
    def verify(current):
        current['poster_claims']['claims'][0]['text']='The model predicts behavior from neural signals.'
        return accept(current)
    monkeypatch.setattr(joint,'_fit',fit);monkeypatch.setattr(joint,'sample_claim_verifier_node',verify)
    result=joint.joint_preparation_node(state)
    assert [draft for draft,_ in seen]==[True,False]
    assert seen[0][1]!=seen[1][1]
    assert result['joint_candidate']['status']=='verified_feasible' and not result['draft_layout_mode']
    saved=deepcopy(result['joint_candidate'])
    # Completed convergence is replayable with no more verification or fit calls.
    replay=state_for_existing(result)
    joint.joint_preparation_node(replay)
    assert len(seen)==2 and replay['joint_candidate']==saved


def state_for_existing(state):
    # The outer Writer checkpoint restores the original draft on a real restart.
    value=deepcopy(state)
    original=expression();original.update(essential=False,verified=False)
    value['poster_claims']={'claims':[original]};joint.refresh_contexts(value['poster_claims']['claims'])
    return value


def test_compile_rejects_mutated_science_before_any_new_search(monkeypatch,tmp_path):
    state=accept(state_for(tmp_path));state['joint_candidate']={'version':joint.VERSION,'status':'verified_feasible',
        'family_id':'four_column_modular','science_digest':joint.candidate_identity(state),
        'board':state['verified_module_board'],'layout_spec':{},'fit_report':{}}
    state['joint_candidate']['digest']=digest(state['joint_candidate'])
    state['verified_claims']['claims'][0]['text']='Changed after freeze'
    monkeypatch.setattr(joint,'fit_family_layout',lambda *a,**k:pytest.fail('No new search'))
    with pytest.raises(ValueError,match='coherent verified'):joint.compile_joint_layout_node(state)


def test_system_failures_are_fatal_but_model_truncation_is_sample_failure(tmp_path):
    from src.workflow.sample_errors import record_sample_error
    from utils.model_requests import SampleRequestFailure
    for error, fatal in [(KeyError('bug'),True),(OSError('disk'),True),
                         (SampleRequestFailure('request failed AuthenticationError'),True),
                         (SampleRequestFailure('model output truncated'),False)]:
        state=state_for(tmp_path/f'case{fatal}{type(error).__name__}')
        record_sample_error(state,error,'test')
        assert bool(state.get('fatal_generation_error')) is fatal


def test_unchanged_verified_expression_reuses_science_but_context_change_rechecks(monkeypatch,tmp_path):
    import src.agents.claim_verifier as verifier
    state=accept(state_for(tmp_path))
    calls=[]
    def verify(s):calls.append(s);return accept(s)
    monkeypatch.setattr(verifier,'claim_verifier_node',verify)
    joint.verify_selected_science(state)
    assert not calls
    state['poster_claims']['claims'][0]['module_context']['task']='A different interpretation task'
    joint.verify_selected_science(state)
    assert len(calls)==1


def test_scientific_feedback_uses_same_sample_edit_allowance(monkeypatch,tmp_path):
    state=state_for(tmp_path);calls=[]
    monkeypatch.setattr(joint,'_fit',lambda s,**kw:(fit_result(s),None))
    def verify(s):
        calls.append('verify')
        if calls.count('verify')==1:
            s.update(joint_verification_feedback={'display_001':{'missing_required_evidence_ids':['e2']}}, verification_passed=False)
            return s
        return accept(s)
    def edit(s,feedback,touched,phase):
        assert feedback['verification'] and phase=='capacity'
        assert charge_round(s,phase,s['critic_config']['capacity_repair'])
        calls.append('edit');return s
    monkeypatch.setattr(joint,'sample_claim_verifier_node',verify);monkeypatch.setattr(joint,'_edit',edit)
    joint.joint_preparation_node(state)
    assert calls==['verify','edit','verify']
    assert len(sample_ledger(state)[1]['charges'])==1 and state['joint_candidate']


def test_no_capacity_edits_after_three_failed_rounds(monkeypatch,tmp_path):
    state=state_for(tmp_path)
    monkeypatch.setattr(joint,'_fit',lambda s,**kw:(None,{'reason_code':'NO_FAST_FEASIBLE_VARIANT'}))
    def edit(s,feedback,touched,phase):
        if not charge_round(s,phase,s['critic_config']['capacity_repair']):raise joint.JointContentFailure('exhausted')
        return s
    monkeypatch.setattr(joint,'_edit',edit)
    joint.joint_preparation_node(state)
    assert len(sample_ledger(state)[1]['charges'])==3
    assert not state.get('joint_candidate') and state['sample_failure']['family_reselected'] is False


def test_edit_charge_precedes_physical_request_and_completed_response_replays(monkeypatch,tmp_path):
    import utils.langgraph_utils as language
    state=state_for(tmp_path);seen=[]
    raw=revision(state)
    class Editor(Agent):
        def __init__(self,*args):super().__init__(raw)
        def step(self,prompt):
            assert len(sample_ledger(state)[1]['charges'])==1
            seen.append(prompt);return super().step(prompt)
    monkeypatch.setattr(language,'LangGraphAgent',Editor)
    original=deepcopy(state)
    joint._edit(state,{'reason_code':'pressure'},{},'capacity')
    replay=joint._edit(original,{'reason_code':'pressure'},{},'capacity')
    assert len(seen)==1 and replay['poster_claims']==state['poster_claims']


def test_charged_edit_without_response_is_not_resubmitted(monkeypatch,tmp_path):
    import utils.langgraph_utils as language
    state=state_for(tmp_path)
    class Broken:
        def __init__(self,*args):pass
        def reset(self):pass
        def step(self,prompt):raise RuntimeError('interruption')
    monkeypatch.setattr(language,'LangGraphAgent',Broken)
    with pytest.raises(RuntimeError,match='interruption'):joint._edit(state,{}, {},'capacity')
    with pytest.raises(ValueError,match='no saved response'):joint._edit(state,{}, {},'capacity')
    assert len(sample_ledger(state)[1]['charges'])==1


def test_force_stop_does_not_freeze_unverified_draft(monkeypatch,tmp_path):
    state=state_for(tmp_path);state['_force_stop_requested']=lambda:True
    monkeypatch.setattr(joint,'_fit',lambda *a,**kw:pytest.fail('Stop before fitting'))
    joint.joint_preparation_node(state)
    assert state['_joint_interrupted'] and not state.get('joint_candidate')
    assert not (Path(state['output_dir'])/'joint/READY.json').exists()
    assert not state.get('errors')


@pytest.mark.parametrize('verdict',[None,False])
def test_selective_editorial_revision_requires_explicit_preservation(monkeypatch,tmp_path,verdict):
    import src.agents.claim_verifier as verifier
    state=state_for(tmp_path)
    claims,_=joint.normalize_editorial_revision(revision(state),state,['display_001'])
    state['poster_claims']={'claims':claims}
    result={'supported':True,'relationships_supported':True,'necessary_information_preserved':True,
        'coverage':[{'quote':claims[0]['text'],'evidence_ids':['e1','e2'],'supported':True}],
        'covered_required_evidence_ids':['e1','e2']}
    if verdict is not None:result['editorial_information_preserved']=verdict
    class Verifier(Agent):
        def __init__(self,*args):super().__init__(result)
    monkeypatch.setattr(verifier,'LangGraphAgent',Verifier)
    verifier.ClaimVerifier()(state)
    assert not state['verification_passed'] and not state['verified_claims']['claims']


def test_missing_frozen_family_after_curation_cannot_be_rechosen(tmp_path):
    from src.workflow.exploration_store import ExplorationStore
    store=ExplorationStore(tmp_path/'store');task={'sample_id':'sample_000001','number':1,'seed':2}
    marker=store.sample_path('run_test','sample_000001')/'preparation/content/module_planning/identity.json'
    marker.parent.mkdir(parents=True);marker.write_text('{}')
    with pytest.raises(ValueError,match='assignment is missing'):
        store.family_assignment('run_test',task,{}, {},lambda:pytest.fail('Cannot choose again'))


def test_family_is_frozen_after_planner_before_curator_and_not_changed_on_resume(tmp_path):
    from src.workflow.exploration_runner import PosterExplorationRunner
    from src.workflow.exploration_store import ExplorationStore
    from src.workflow.run_control import RunControl
    from test_exploration_samples import scientific, prepare_sample, render_sample, critic_with_scores
    control=RunControl();seen=[]
    def planner(s):
        prepare_sample(s)
        assert not s.get('sample_family')
        return s
    def curator(s):
        assert s['sample_family']['family']==s['iteration_context']['layout_family']
        assert s.get('sample_science_digest') is None
        seen.append(s['sample_family']['family']);control.request_stop(force=True);return s
    nodes=[planner,curator]
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=1,random_seed=42,
        paper_nodes=[],preparation_nodes=nodes,design_nodes=[render_sample],control=control,critic=critic_with_scores([30]))
    paused=runner.run(scientific(tmp_path),paper_ready=True)
    assert paused['run_state']['status']=='PAUSED' and len(seen)==1
    runner2=PosterExplorationRunner(storage=runner.storage,run_id=runner.run_id,paper_nodes=[],
        preparation_nodes=nodes,design_nodes=[render_sample],critic=critic_with_scores([30]))
    result=runner2.run(scientific(tmp_path))
    assert result['run_state']['rendered_samples']==1 and len(seen)==1
    assert result['run_state']['results'][0]['layout_family']==seen[0]


def test_neutral_closing_zone_accepts_real_findings_without_conclusion_module(tmp_path):
    from src.layout.feasibility import _active_zone_roles
    state=state_for(tmp_path,3)
    view={**state,'draft_layout_mode':True}
    board=build_module_board(view,view['poster_claims']['claims'],joint.draft_protection(view))
    roles=_active_zone_roles('framed_multicolumn',board['spatial_content_plan']['sections'],view)
    assert 'results' in roles['conclusion']
    state['sample_family']['family']='framed_multicolumn'
    assert 'results' in dict(family_brief(state)['contract']['conditional_roles'])['conclusion']
    assert not any('conclusion' in m['title'].lower() for m in state['sample_module_plan']['modules'])


def test_adopted_candidate_compiles_styles_and_keeps_every_render_version(monkeypatch,tmp_path):
    from PIL import Image
    from src.agents.renderer import Renderer
    from src.agents.font_agent import FontAgent
    from src.agents.color_agent import ColorAgent
    from src.agents.section_title_designer import SectionTitleDesigner
    from src.agents.layout_preflight import layout_preflight_node
    state=state_for(tmp_path,6)
    state['critic_config']['capacity_repair']['enabled']=False
    monkeypatch.setattr(joint,'sample_claim_verifier_node',accept)
    state=joint.joint_preparation_node(state)
    assert state.get('joint_candidate'),state.get('errors')
    joint.install_joint_candidate_node(state)
    # Color and keyword models are stubbed; actual style/compile/PPTX code runs.
    state['color_scheme']=ColorAgent()._add_contrast_color(ColorAgent()._generate_color_scheme('#1E3A8A'))
    SectionTitleDesigner()(state)
    joint.compile_joint_layout_node(state)
    assert not state['layout_preflight_failed'] and not state['errors']
    monkeypatch.setattr(FontAgent,'_identify_keywords',lambda *a:{'section_keywords':{}})
    FontAgent()(state);layout_preflight_node(state)
    assert not state['layout_preflight_failed'], state.get('layout_preflight_report')
    state['current_candidate']={'candidate_id':'owned','candidate_dir':state['output_dir']}
    def png(_self,pptx):
        target=pptx.with_suffix('.png');Image.new('RGB',(540,360),'white').save(target);return str(target)
    monkeypatch.setattr(Renderer,'_convert_to_png',png)
    frozen=deepcopy(state['joint_candidate'])
    Renderer()(state);first=Path(state['current_candidate']['pptx_path'])
    first_bytes=first.read_bytes()
    Renderer()(state);second=Path(state['current_candidate']['pptx_path'])
    assert not state['errors'] and first!=second and first.read_bytes()==first_bytes
    assert state['joint_candidate']==frozen
    for path in (first,second):
        assert {'template.json','template.png','template.pptx'} <= {p.name for p in path.parent.iterdir()}
    assert len(state['render_history'])==2 and state['render_history'][1]['parent_render_id']==state['render_history'][0]['render_id']


def test_editorial_revision_cannot_change_canonical_source_ownership(tmp_path):
    state=state_for(tmp_path)
    claim=state['poster_claims']['claims'][0]
    claim.update(source_plan_unit_ids=['u1'],section_id='u1',evidence_ids=['e1'],required_evidence_ids=['e1'],text='The model uses neural signals.')
    raw=revision(state)
    revised,_=joint.normalize_editorial_revision(raw,state,['display_001'])
    assert revised[0]['source_plan_unit_ids']==['u1'] and revised[0]['section_id']=='u1'
    raw['modules'][0]['claims'][0]['evidence_ids']=['e2']
    with pytest.raises(joint.JointContentFailure,match='different source unit'):
        joint.normalize_editorial_revision(raw,state,['display_001'])


def test_explicit_structure_merge_preserves_all_roots_sources_and_required_assertions(tmp_path):
    state=state_for(tmp_path,3)
    # Three module tasks, two compatible method uses and a separate result.
    for index in (0,1):state['narrative_plan']['sections'][index]['narrative_role']='method'
    source,owner=state['sample_module_plan']['modules'][:2]
    source['module_purpose']='supporting'
    state['poster_claims']['claims'][0]['discourse_kind']='setup'
    state['poster_claims']['claims'][1]['discourse_kind']='method'
    options=joint.structure_merge_options(state)
    assert (source['module_id'],owner['module_id']) in options
    before={c['claim_id']:deepcopy(c) for c in state['poster_claims']['claims']}
    targets=[source['module_id'],owner['module_id']]
    raw={'modules':[{'module_id':mid,'claims':[{'source_claim_id':c['claim_id'],'text':c['text'],'evidence_ids':c['evidence_ids']}
        for c in state['poster_claims']['claims'] if c['display_module_id']==mid]} for mid in targets]}
    raw['modules'][0]['merge_into_module_id']=owner['module_id']
    claims,_=joint.normalize_editorial_revision(raw,state,targets)
    assert {c['claim_id'] for c in claims}==set(before)
    assert all(c['source_plan_unit_ids']==before[c['claim_id']]['source_plan_unit_ids'] for c in claims)
    assert len(state['sample_module_plan']['modules'])==2
    combined=state['sample_module_plan']['modules'][0]
    assert set(combined['required_evidence_ids'])=={'e0','e1'}
    assert state['sample_module_plan']['structure_revisions'][0]['scientific_roots_merged'] is False


def test_quality_regression_restores_frozen_feasible_science_and_spends_one_round(monkeypatch,tmp_path):
    from src.layout import module_repair
    state=state_for(tmp_path);original=state['poster_claims']['claims'][0]['text']
    def fit(s,**kw):
        result=fit_result(s);result[2]['content_quality_hints']={'completion_targets':[{'section_id':'display_001'}]}
        return result,None
    def edit(s,feedback,touched,phase):
        assert phase=='quality' and charge_round(s,phase,s['critic_config']['capacity_repair'])
        s['poster_claims']['claims'][0]['text']='Changed quality candidate.'
        return s
    monkeypatch.setattr(joint,'_fit',fit);monkeypatch.setattr(joint,'_edit',edit)
    monkeypatch.setattr(joint,'sample_claim_verifier_node',accept)
    monkeypatch.setattr(module_repair,'space_preserved',lambda *a:False)
    result=joint.joint_preparation_node(state)
    assert result['verified_claims']['claims'][0]['text']==original
    assert sample_ledger(result)[1]['charges'][0]['phase']=='quality'
    assert result['joint_candidate']['status']=='verified_feasible'


def test_exhausted_preparation_correction_is_sample_failure_not_service_failure(tmp_path):
    from src.workflow.sample_errors import record_sample_error
    state=state_for(tmp_path)
    record_sample_error(state,ValueError('Shared preparation repair allowance is exhausted'),'preparation')
    assert state['sample_failure'] and not state.get('fatal_generation_error')


def test_undeclared_visible_citation_is_a_diagnosed_editorial_output_failure(tmp_path):
    state=state_for(tmp_path);raw=revision(state)
    # Use machine-style IDs in this test so marker normalization recognizes them.
    state['evidence_bank']['items'][0]['evidence_id']='ev_0001'
    state['evidence_bank']['items'][1]['evidence_id']='ev_0002'
    module=state['sample_module_plan']['modules'][0]
    module['available_evidence_ids']=['ev_0001','ev_0002']
    row=raw['modules'][0]['claims'][0];row['evidence_ids']=['ev_0001','ev_0002']
    row['text']+=' (ev_9999)'
    for unit,eid in zip(state['narrative_plan']['sections'],['ev_0001','ev_0002']):unit['evidence_ids']=[eid]
    with pytest.raises(joint.JointContentFailure,match='undeclared'):
        joint.normalize_editorial_revision(raw,state,['display_001'])
