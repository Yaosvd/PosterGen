"""Preparation ownership, caching and provenance without external model calls."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.exploration_store import ExplorationStore
from src.workflow.run_control import RunControl
from utils.persistence import read_json, _atomic_json, digest
from test_exploration_samples import scientific, prepare_sample, render_sample, critic_with_scores


def make_runner(tmp_path, nodes, **kwargs):
    return PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'), paper_nodes=[],
        preparation_nodes=nodes, design_nodes=[render_sample], critic=critic_with_scores([40]*20),
        random_seed=31, **kwargs)


def test_sample_preparation_is_independent_and_failed_family_does_not_retry(tmp_path):
    preparations, seen = [], []
    def prepare(state):
        preparations.append(state['iteration_context']['sample_id'])
        prepare_sample(state)
        state['narrative_plan']['sample_marker'] = len(preparations)
        return state
    runner = make_runner(tmp_path, [prepare], samples=2)
    def design(state):
        seen.append((state['iteration_context']['sample_id'], state['sample_science_digest']))
        assert not state.get('critic_report')
        if len(seen) == 1:
            state.update(layout_preflight_failed=True, errors=['known fit failure'],
                         layout_feasibility_report={'reason_code':'ASSIGNMENT_EXHAUSTED'})
            return state
        return render_sample(state)
    runner.design_nodes = [design]
    result = runner.run(scientific(tmp_path), paper_ready=True)
    assert result['run_state']['rendered_samples'] == 1
    assert preparations == ['sample_000001', 'sample_000002']
    assert len(seen) == 2 and seen[0][1] != seen[1][1]
    paper = runner.storage.paper_foundation(runner.run_id)
    assert not set(paper) & {'narrative_plan','poster_claims','verified_claims','verification_passed'}
    assert set(paper['narrative_content']) == {'meta'}
    for row in result['run_state']['results']:
        assert row['dataset'] == 'rubrics_samples_v2'
        if not row['poster_id']:
            assert row['status'] == 'fit_failed' and row['retry_count'] == 0
            continue
        diagnostics = runner.storage.verify_poster(row['poster_id'])/'diagnostics'
        assert (diagnostics/'verified_claims.json').exists()
        assert read_json(diagnostics/'sample_science_digest.json') == row['sample_science_digest']


@pytest.mark.parametrize('stop_after', [1, 2, 3])
def test_force_stop_checkpoints_reuse_completed_science_stages(tmp_path, stop_after):
    control, calls = RunControl(), []
    def node1(state):
        calls.append(1);prepare_sample(state)
        if stop_after == 1: control.request_stop(force=True)
        return state
    def node2(state):
        calls.append(2)
        if stop_after == 2: control.request_stop(force=True)
        return state
    def node3(state):
        calls.append(3)
        if stop_after == 3: control.request_stop(force=True)
        return state
    nodes = [node1,node2,node3]
    runner = make_runner(tmp_path, nodes, samples=1, control=control)
    result = runner.run(scientific(tmp_path), paper_ready=True)
    assert result['run_state']['status'] == 'PAUSED'
    assert result['run_state']['finalized_samples'] == 0
    resumed = PosterExplorationRunner(storage=runner.storage, run_id=runner.run_id,
        paper_nodes=[], preparation_nodes=nodes, design_nodes=[render_sample], critic=critic_with_scores([60]))
    result = resumed.run(scientific(tmp_path))
    assert result['run_state']['rendered_samples'] == 1 and calls == [1,2,3]
    path = runner.storage.sample_path(runner.run_id, 'sample_000001')/'preparation'
    assert len(read_json(path/'model_work_ledger.json')['charges']) == 3


def test_failed_science_never_reaches_family_design_or_critic(tmp_path):
    def failed(state):
        state['errors'].append('No verified claims remain')
        state['sample_failure'] = {'kind': 'no_verified_science'}
        return state
    runner = make_runner(tmp_path, [failed], samples=3)
    runner.design_nodes = [lambda _:pytest.fail('No design before verification')]
    runner.critic = lambda _:pytest.fail('No scoring before verification')
    result = runner.run(scientific(tmp_path), paper_ready=True)
    assert result['run_state']['status'] == 'COMPLETED'
    assert len(result['run_state']['results']) == 3
    row = result['run_state']['results'][0]
    assert row['status'] == 'preparation_failed' and row['score'] is None
    root = runner.storage.sample_path(runner.run_id, row['sample_id'])
    assert (root/'preparation/failure.json').exists()
    assert not (root/'attempts').exists()
    assert not (root/'family_assignment.json').exists()


def test_preparation_cannot_rewrite_paper_evidence(tmp_path):
    def corrupt_paper(state):
        prepare_sample(state)
        state['evidence_bank']['items'][0]['source_excerpt'] = 'Changed source'
        return state
    runner = make_runner(tmp_path, [corrupt_paper], samples=1)
    original = scientific(tmp_path)
    expected = deepcopy(original['evidence_bank'])
    result = runner.run(original, paper_ready=True)
    assert result['run_state']['status'] == 'FAILED'
    assert runner.storage.paper_foundation(runner.run_id)['evidence_bank'] == expected
    root = runner.storage.sample_path(runner.run_id, 'sample_000001')
    assert 'immutable paper evidence' in str(read_json(root/'preparation/failure.json'))
    assert not (root/'preparation/READY.json').exists()


@pytest.mark.parametrize('target', ['READY.json', 'sample_science.json', 'stage_01.json', 'family_assignment.json'])
def test_corrupted_unfinished_science_or_family_checkpoint_is_rejected(tmp_path, target):
    control = RunControl()
    def stop(state):
        control.request_stop(force=True)
        return state
    runner = make_runner(tmp_path, [prepare_sample], samples=1, control=control)
    runner.design_nodes = [stop]
    runner.run(scientific(tmp_path), paper_ready=True)
    root = runner.storage.sample_path(runner.run_id, 'sample_000001')
    if target == 'stage_01.json':
        # Simulate interruption before publishing READY, not a finished preparation.
        (root/'preparation/READY.json').unlink()
    path = root/target if target=='family_assignment.json' else root/'preparation'/target
    payload = read_json(path);payload['digest']='corrupt';_atomic_json(path,payload)
    resumed = PosterExplorationRunner(storage=runner.storage, run_id=runner.run_id,
        preparation_nodes=[prepare_sample], design_nodes=[render_sample])
    with pytest.raises(ValueError, match='digest|mismatch'):
        resumed.run(scientific(tmp_path))


def test_completed_science_cannot_be_reused_under_another_sample_id(tmp_path):
    control = RunControl()
    def score(state):
        control.request_stop();return critic_with_scores([40])(state)
    runner = make_runner(tmp_path, [prepare_sample], samples=2, control=control)
    runner.critic=score
    runner.run(scientific(tmp_path), paper_ready=True)
    import shutil
    src = runner.storage.sample_path(runner.run_id,'sample_000001')/'preparation'
    dst = runner.storage.sample_path(runner.run_id,'sample_000002')/'preparation'
    shutil.copytree(src,dst)
    resumed = PosterExplorationRunner(storage=runner.storage,run_id=runner.run_id,
        preparation_nodes=[prepare_sample],design_nodes=[render_sample])
    with pytest.raises(ValueError,match='identity'):
        resumed.run(scientific(tmp_path))


def test_family_coverage_ignores_scores_and_remains_frozen_on_resume(tmp_path):
    assignments = []
    for score_value in (1,99):
        folder=tmp_path/str(score_value);folder.mkdir()
        control = RunControl()
        runner=make_runner(folder,[prepare_sample],samples=15,control=control)
        score = critic_with_scores([score_value]*15)
        def pause_after_first(state):
            control.request_stop()
            return score(state)
        runner.critic=pause_after_first if score_value == 99 else score
        result=runner.run(scientific(folder),paper_ready=True)
        if score_value == 99:
            assert result['run_state']['status'] == 'PAUSED'
            first_assignment = (runner.storage.sample_path(runner.run_id,'sample_000001')/
                                'family_assignment.json').read_bytes()
            runner = PosterExplorationRunner(storage=runner.storage,run_id=runner.run_id,
                preparation_nodes=[prepare_sample],design_nodes=[render_sample],
                critic=critic_with_scores([score_value]*14))
            result=runner.run(scientific(folder))
            assert (runner.storage.sample_path(runner.run_id,'sample_000001')/
                    'family_assignment.json').read_bytes() == first_assignment
        families=[row['layout_family'] for row in result['run_state']['results']]
        assert len(set(families)) == 15
        assignments.append(families)
    assert assignments[0] == assignments[1]


def test_family_profile_is_derived_from_current_sample_planner_before_writer(tmp_path, monkeypatch):
    import src.workflow.exploration_runner as workflow
    real_profile = workflow.build_planning_profile
    seen = []
    def prepare(state):
        prepare_sample(state)
        state['narrative_plan']['sections'][0]['narrative_role'] = 'results'
        return state
    def profile(state):
        assert state['narrative_plan'] and not state.get('sample_science_digest')
        seen.append(state['narrative_plan']['sections'][0]['narrative_role'])
        return real_profile(state)
    monkeypatch.setattr(workflow, 'build_planning_profile', profile)
    runner = make_runner(tmp_path, [prepare], samples=2)
    assert runner.run(scientific(tmp_path),paper_ready=True)['run_state']['rendered_samples'] == 2
    assert seen == ['results', 'results']


def test_legacy_run_is_readable_but_not_silently_upgraded(tmp_path):
    store=ExplorationStore(tmp_path/'store')
    root=store.run_path('run_old');root.mkdir(parents=True)
    manifest={'schema_version':1,'dataset':'rubrics_samples_v1'}
    _atomic_json(root/'manifest.json',manifest)
    result={'sample_id':'sample_000001','poster_id':None,'status':'fit_failed'}
    _atomic_json(root/'samples/sample_000001/FINALIZED.json',{
        'schema_version':1,'run_id':'run_old','result':result,'result_digest':digest(result)})
    assert store.results('run_old') == [result]
    before=(root/'manifest.json').read_bytes()
    with pytest.raises(ValueError,match='older preparation contract'):
        store.open_run({}, {}, run_id='run_old')
    assert (root/'manifest.json').read_bytes() == before


@pytest.mark.parametrize('route, expected_calls', [('optimization_family',0), ('standalone_classic',1)])
def test_parser_keeps_title_authors_and_classic_abt_only(tmp_path, monkeypatch, route, expected_calls):
    from src.agents.parser import Parser
    from src.agents.layout_agent import LayoutAgent
    agent=Parser.__new__(Parser);agent.name='parser'
    calls=[]
    monkeypatch.setattr(agent,'_extract_raw_text',lambda *a:('Original paper text',None))
    monkeypatch.setattr(agent,'_extract_assets',lambda *a:({},{}))
    monkeypatch.setattr(agent,'_cleanup_unused_assets',lambda *a:None)
    monkeypatch.setattr(agent,'_extract_title_authors',lambda *a:('Exact Paper Title','Exact Authors'))
    def abt(*a):
        calls.append(1);return {'and':'background','but':'problem','therefore':'result'},0,0
    monkeypatch.setattr(agent,'_generate_narrative_content',abt)
    monkeypatch.setattr(agent,'_classify_visual_assets',lambda *a:({},0,0))
    monkeypatch.setattr(agent,'_extract_structured_sections',lambda *a:{'paper_sections':[]})
    state=scientific(tmp_path);state['output_dir']=str(tmp_path/'parser');state['generation_route']=route
    result=agent(state)
    assert not result['errors'] and len(calls)==expected_calls
    assert result['narrative_content']['meta']=={'poster_title':'Exact Paper Title','authors':'Exact Authors'}
    title=LayoutAgent()._create_title_element(result,54,6)
    assert title['content']=='Exact Paper Title\nExact Authors'
    assert ('and' in result['narrative_content']) == bool(expected_calls)


def test_actual_planner_writer_verifier_chain_keeps_verified_source_and_per_sample_scope(tmp_path,monkeypatch):
    from src.agents import narrative_planner as planner, claim_writer as writer, claim_verifier as verifier
    seen=[]
    class Agent:
        def __init__(self,*args):self.name=args[-1]
        def reset(self):pass
        def step(self,prompt):
            seen.append(self.name)
            if self.name=='narrative_planner':
                value={'sections':[{'evidence_ids':['e1'],'title_intent':'Method','narrative_role':'method'}]}
            elif self.name=='claim_writer':
                value={'claims':[{'text':'A verified observation.','evidence_ids':['e1']}]}
            else:value={'supported':True}
            return SimpleNamespace(content=json.dumps(value),input_tokens=1,output_tokens=1)
    for module in (planner,writer,verifier):
        monkeypatch.setattr(module,'LangGraphAgent',Agent)
    runner=make_runner(tmp_path,[planner.narrative_planner_node,writer.claim_writer_node,verifier.claim_verifier_node],samples=2)
    def design(state):
        assert state['verification_passed']
        assert state['verified_claims']['claims'][0]['verified'] is True
        assert state['narrative_plan']['planning_contract']=='research_units_v1'
        return render_sample(state)
    runner.design_nodes=[design]
    result=runner.run(scientific(tmp_path),paper_ready=True)
    assert result['run_state']['rendered_samples']==2
    assert seen==['narrative_planner','claim_writer','claim_verifier']*2


def test_module_mapping_retains_multiple_plan_units_after_display_regrouping():
    from src.workflow.content_contracts import module_provenance
    from utils.module_content import module_context
    from src.layout.reading_flow import planned_for_sections
    state={'evidence_bank':{'items':[{'evidence_id':'e1','source':{'section_id':'paper-a'}},
                                  {'evidence_id':'e2','source':{'section_id':'paper-b'}}]},
           'narrative_plan':{'sections':[{'section_id':'plan-a','narrative_role':'method','evidence_ids':['e1']},
                                         {'section_id':'plan-b','narrative_role':'results','evidence_ids':['e2']}]},
           'verified_claims':{'claims':[{'claim_id':'c1','section_id':'plan-a','evidence_ids':['e1']},
                                         {'claim_id':'c2','section_id':'plan-b','evidence_ids':['e2']}]}}
    module={'section_id':'display-x','claim_ids':['c1','c2']}
    board={'spatial_content_plan':{'sections':[module]}}
    row=module_provenance(board,state)['modules'][0]
    assert row['plan_section_ids']==['plan-a','plan-b'] and row['paper_section_ids']==['paper-a','paper-b']
    assert set(module_context(state,board,'display-x')['evidence_ids'])=={'e1','e2'}
    assert planned_for_sections(state,[module])['display-x']['narrative_role']==''


@pytest.mark.parametrize('route, expected_reserve', [
    ('optimization_family', 'e2-reserve'), ('standalone_classic', 'unrelated')])
def test_display_id_collision_preserves_roots_and_classic_evidence_policy(route, expected_reserve):
    from src.critic.base import CriticContext
    from src.critic.section_fit import ContentAdequacyEvaluator
    from utils.module_content import module_context
    state = {
        'generation_route': route,
        'evidence_bank': {'items': [{'evidence_id': eid} for eid in ('e1','e2','e2-reserve','unrelated')]},
        'verified_claims': {'claims': [
            {'claim_id':'c1','section_id':'plan-a','text':'First finding.','evidence_ids':['e1']},
            {'claim_id':'c2','section_id':'plan-b','text':'Second finding.','evidence_ids':['e2']}]},
        'narrative_plan': {'sections': [
            {'section_id':'plan-a','evidence_ids':['e1']},
            {'section_id':'plan-b','evidence_ids':['e2','e2-reserve']},
            {'section_id':'display','evidence_ids':['unrelated']}]},
        'story_board': {'spatial_content_plan': {'sections': [
            {'section_id':'display','claim_ids':['c1'], 'curated_claim_roots':['c1','c2']}]}},
        'section_fit_analysis': {'sections': {'display': {'utilization': .5}}},
    }
    context = module_context(state,state['story_board'],'display')
    assert set(context['evidence_ids']) == {'e1','e2','e2-reserve'}
    result = ContentAdequacyEvaluator().evaluate(CriticContext(state,{}))
    unused = result.issues[0]['evidence']['candidate_evidence_ids']
    assert expected_reserve in unused
    assert ('unrelated' in unused) == (route == 'standalone_classic')
