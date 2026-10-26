"""No-model regressions for request budgets and sample-local curation reuse."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from utils.model_requests import invoke, sample_policy, SampleRequestFailure
from utils.persistence import read_json, _atomic_json
from src.workflow.sample_curation import SampleCuration
from src.workflow.exploration_store import ExplorationStore
from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.run_control import RunControl
from src.layout.repair_budget import budget_usage
from test_exploration_samples import scientific, prepare_sample, render_sample, critic_with_scores


def test_sample_factory_disables_sdk_retries_and_leaves_classic_unchanged(monkeypatch,tmp_path):
    import utils.langgraph_utils as util
    from src.state.poster_state import ModelConfig
    monkeypatch.setenv('LOCAL_TEXT_BASE_URL','http://example.invalid/v1')
    captured=[]
    monkeypatch.setattr(util,'ChatOpenAI',lambda **kwargs:captured.append(kwargs) or object())
    state={'generation_route':'optimization_family','output_dir':str(tmp_path)}
    util.LangGraphAgent('system',ModelConfig('fake','local_text'),state,'grounded_curator')
    assert captured[-1]['max_retries']==0
    assert captured[-1]['request_timeout'].read==900 and captured[-1]['request_timeout'].connect==15
    util.LangGraphAgent('system',ModelConfig('fake','local_text'),{},'grounded_curator')
    assert captured[-1]['max_retries']==2 and captured[-1]['request_timeout']==500


@pytest.mark.parametrize('error,retry',[
    (httpx.ReadTimeout('private failure'),False),
    (httpx.ConnectTimeout('private failure'),True),
    (SimpleNamespace(status_code=429),True),
    (SimpleNamespace(status_code=401),False),
])
def test_only_known_transient_errors_retry_once_and_all_attempts_are_logged(tmp_path,monkeypatch,error,retry):
    import utils.model_requests as requests
    monkeypatch.setattr(requests.time,'sleep',lambda _:None)
    if not isinstance(error,Exception):
        failure=RuntimeError('private failure');failure.status_code=error.status_code;error=failure
    calls=[]
    def call(messages):
        calls.append(messages)
        if len(calls)==1:raise error
        return SimpleNamespace(content='{}',response_metadata={'finish_reason':'stop'},usage_metadata={'output_tokens':3})
    agent=SimpleNamespace(state={'output_dir':str(tmp_path)},agent_name='curator',request_policy=sample_policy({'generation_route':'optimization_family'}))
    if retry:invoke(agent,SimpleNamespace(invoke=call),[SimpleNamespace(content='private scientific prose')])
    else:
        with pytest.raises(SampleRequestFailure):invoke(agent,SimpleNamespace(invoke=call),[SimpleNamespace(content='private scientific prose')])
    assert len(calls)==(2 if retry else 1)
    log=(tmp_path/'model_requests.jsonl').read_text()
    assert 'private failure' not in log and 'private scientific prose' not in log
    events=[json.loads(s)['event'] for s in log.splitlines()]
    assert events==(['request_start','request_retry','request_start','request_finished'] if retry else ['request_start','request_failed'])


def test_truncated_response_never_becomes_a_curator_result(tmp_path):
    agent=SimpleNamespace(state={'output_dir':str(tmp_path)},agent_name='curator',request_policy=sample_policy({'generation_route':'optimization_family'}))
    model=SimpleNamespace(invoke=lambda _:SimpleNamespace(response_metadata={'finish_reason':'length'}))
    with pytest.raises(SampleRequestFailure,match='truncated'):invoke(agent,model,[])


def curated(state):
    state['story_board']={'spatial_content_plan':{'sections':[{
        'section_id':'display','claim_ids':['c1'],'text_content':['A verified observation.']}]},
        'editorial_selection':{'items':[{'claim_id':'c1','disposition':'required','reason':'core'}]}}
    return state
curated.__name__='grounded_curator_node'


def test_single_family_failure_never_retries_or_scores_previous_design(tmp_path):
    calls=[];families=[]
    def curate(state):calls.append(1);return curated(state)
    curate.__name__='grounded_curator_node'
    def design(state):
        assert state['story_board']['spatial_content_plan']['sections'][0]['section_id']=='display'
        assert not state.get('critic_report') and not (state.get('verified_content_bank') or {}).get('claims')
        families.append(state['iteration_context']['layout_family'])
        if len(families)<3:
            state.update(errors=['known fit'],layout_preflight_failed=True,layout_feasibility_report={'reason_code':'NO_FAST_FEASIBLE_VARIANT'})
            return state
        state['story_board']=None
        return render_sample(state)
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=1,random_seed=31,
        paper_nodes=[],preparation_nodes=[prepare_sample],design_nodes=[curate,design],critic=critic_with_scores([40]))
    # Disable layout model repair so the test isolates geometry-only family retries.
    runner.config['capacity_repair']['max_rounds_per_iteration']=0
    result=runner.run(scientific(tmp_path),paper_ready=True)
    assert calls==[1] and len(families)==1 and result['run_state']['rendered_samples']==0
    assert result['run_state']['results'][0]['status']=='fit_failed'


def test_shared_structure_failure_has_no_separate_recuration_pass(tmp_path):
    calls=[]
    def curate(state):
        repair = bool(state.get('curation_repair_context'))
        calls.append(repair)
        curated(state)
        state['story_board']['spatial_content_plan']['sections'][0]['editorial'] = {
            'module_purpose': 'primary' if repair else 'supporting'}
        return state
    curate.__name__='grounded_curator_node'
    def design(state):
        if state['curation_report']['revision']==0:
            state['capacity_repair_report']={'visual_restoration':[{'visual_id':'figure_1'}]}
            state.update(errors=['shared'],layout_preflight_failed=True,layout_feasibility_report={
                'reason_code':'PRESENTATION_STRUCTURE_UNRESOLVED','failure_scope':'shared_content',
                'failure_stage':'structure','trial_count':0})
            return state
        assert state['iteration_context']['visual_restore_remaining']==max(0, state['critic_config']['capacity_repair']['max_visual_restore_attempts_per_iteration']-1)
        state['story_board']=None;return render_sample(state)
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=1,
        paper_nodes=[],preparation_nodes=[prepare_sample],design_nodes=[curate,design],critic=critic_with_scores([40]))
    result=runner.run(scientific(tmp_path),paper_ready=True)
    assert calls==[False] and result['run_state']['rendered_samples']==0
    root=runner.storage.sample_path(runner.run_id,'sample_000001')
    assert budget_usage(root/'attempts/attempt_0002')==(0,0)
    assert not (root/'curation/curation_budget.json').exists()
    assert len(list((root/'curation').glob('board_*.json')))==1


def test_curation_checkpoint_survives_force_stop_and_rejects_corruption(tmp_path):
    control=RunControl();calls=[]
    def curate(state):
        calls.append(1);curated(state);control.request_stop(force=True);return state
    curate.__name__='grounded_curator_node'
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=1,control=control,
        paper_nodes=[],preparation_nodes=[prepare_sample],design_nodes=[curate])
    assert runner.run(scientific(tmp_path),paper_ready=True)['run_state']['status']=='PAUSED'
    def design(state):state['story_board']=None;return render_sample(state)
    resumed=PosterExplorationRunner(storage=runner.storage,run_id=runner.run_id,
        preparation_nodes=[prepare_sample],design_nodes=[curate,design],critic=critic_with_scores([60]))
    assert resumed.run(scientific(tmp_path))['run_state']['rendered_samples']==1 and calls==[1]
    p=runner.storage.sample_path(runner.run_id,'sample_000001')/'curation/board_00.json'
    data=read_json(p);data['digest']='invalid';_atomic_json(p,data)
    with pytest.raises(ValueError,match='digest'):
        SampleCuration(runner.storage,runner.run_id,'sample_000001').current({'sample_science_digest':'test'})


@pytest.mark.parametrize('change', ['drop_required', 'drop_condition', 'split_condition', 'drop_dependency'])
def test_revision_cannot_drop_required_content_or_split_existing_dependencies(tmp_path, change):
    store=ExplorationStore(tmp_path/'store');root=store.run_path('run_test');root.mkdir(parents=True)
    state=scientific(tmp_path);state['sample_science_digest']='test';state['iteration_context']={}
    state['verified_claims']['claims'].append({'claim_id':'c2','text':'Condition.','section_id':'s1','evidence_ids':['e1']})
    def initial(state):
        curated(state);s=state['story_board']['spatial_content_plan']['sections'][0]
        s['claim_ids'].append('c2');s['text_content'].append('Condition.')
        s['editorial']={'items':[{'claim_id':'c1','requires_claim_ids':['c2']}]}
        return state
    cache=SampleCuration(store,'run_test','sample_000001');cache.run(state,initial)
    baseline=deepcopy(state['story_board'])
    state['curation_repair_context']={'protected_claim_ids':['c1'],'base_board':baseline}
    def revised(state):
        state['story_board']=deepcopy(baseline)
        board=state['story_board'];section=board['spatial_content_plan']['sections'][0]
        if change=='drop_required':section['claim_ids'].remove('c1')
        if change=='drop_condition':section['claim_ids'].remove('c2')
        if change=='split_condition':
            section['claim_ids'].remove('c2')
            board['spatial_content_plan']['sections'].append({'section_id':'other','claim_ids':['c2']})
        if change=='drop_dependency':section['editorial']['items'][0]['requires_claim_ids']=[]
        return state
    cache.run(state,revised)
    assert state['curation_report']['status']=='repair_rejected'
    assert state['story_board']==baseline and cache.revision(state)==0


def test_different_samples_never_reuse_curator_boards_or_feedback(tmp_path):
    seen=[]
    def curate(state):
        assert not state.get('story_board') and not state.get('critic_report')
        seen.append(state['iteration_context']['sample_id'])
        curated(state)
        state['story_board']['spatial_content_plan']['sections'][0]['section_id']=seen[-1]
        return state
    curate.__name__='grounded_curator_node'
    def design(state):
        assert state['story_board']['spatial_content_plan']['sections'][0]['section_id']==state['iteration_context']['sample_id']
        state['story_board']=None
        return render_sample(state)
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=2,
        paper_nodes=[],preparation_nodes=[prepare_sample],design_nodes=[curate,design],critic=critic_with_scores([30,90]))
    result=runner.run(scientific(tmp_path),paper_ready=True)
    assert seen==['sample_000001','sample_000002'] and result['run_state']['rendered_samples']==2


def test_failed_task_is_final_and_new_design_cannot_reopen_it_on_resume(tmp_path):
    calls=[]
    def curate(state):
        assert not state.get('curation_repair_context')
        calls.append(False);return curated(state)
    curate.__name__='grounded_curator_node'
    def failing_design(state):
        state.update(errors=['known fit'],layout_preflight_failed=True,
            layout_feasibility_report={'reason_code':'PRESENTATION_STRUCTURE_UNRESOLVED',
                'failure_scope':'shared_content','failure_stage':'structure','trial_count':0})
        return state
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=1,
        paper_nodes=[],preparation_nodes=[prepare_sample],design_nodes=[curate,failing_design])
    first=runner.run(scientific(tmp_path),paper_ready=True)
    assert first['run_state']['status']=='COMPLETED' and first['run_state']['rendered_samples']==0
    resumed=PosterExplorationRunner(storage=runner.storage,run_id=runner.run_id,
        preparation_nodes=[prepare_sample],design_nodes=[lambda s:pytest.fail('Final task cannot regenerate')])
    result=resumed.run(scientific(tmp_path))
    assert result['run_state']['results']==first['run_state']['results'] and calls==[False]
    root=runner.storage.sample_path(runner.run_id,'sample_000001')
    assert not (root/'curation/curation_budget.json').exists()
