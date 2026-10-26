"""Module prose, exact support, provenance and bounded recovery without models."""
from copy import deepcopy
from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from src.workflow.sample_modules import (
    BODY_VERSION, finalize_modules, normalize_module_plan, source_units, support_coverage,
    sample_claim_verifier_node,
)
from src.workflow.sample_curation import SampleCuration, diagnostic_pressure
from src.workflow.exploration_store import ExplorationStore
from src.layout.repair_budget import budget_usage
from src.layout.families import FAMILIES
from utils.persistence import read_json
from test_exploration_samples import scientific, render_sample, critic_with_scores


def module_state(tmp_path):
    state = scientific(tmp_path)
    state.update(errors=[], generation_route='optimization_family', images={}, tables={},
                 output_dir=str(tmp_path/'work'), verified_claims=None, verification_passed=False)
    state['evidence_bank'] = {'items': [
        {'evidence_id': 'e1', 'claim': 'The model uses neural signals.',
         'source_excerpt': 'The model uses neural signals.', 'claim_type': 'method'},
        {'evidence_id': 'e2', 'claim': 'It predicts behavior.',
         'source_excerpt': 'It predicts behavior.', 'claim_type': 'result'},
    ]}
    state['narrative_plan'] = {'narrative_summary': 'Explain neural modeling.', 'sections': [
        {'section_id': 'u1', 'title_intent': 'Neural method', 'narrative_role': 'method',
         'evidence_ids': ['e1'], 'required_evidence_ids': ['e1'], 'importance': 1},
        {'section_id': 'u2', 'title_intent': 'Behavior prediction', 'narrative_role': 'results',
         'evidence_ids': ['e2'], 'required_evidence_ids': ['e2'], 'importance': 1},
    ]}
    return state


def raw_plan():
    return {'modules': [{'title': 'Neural Modeling', 'writing_brief': 'Explain mechanism, then prediction.',
                         'source_plan_unit_ids': ['u1', 'u2'], 'evidence_ids': ['e1', 'e2'], 'visual_ids': []}]}


def expression(text='The model uses neural signals. It predicts behavior.'):
    return {'claim_id': 'pc_0001', 'text': text, 'evidence_ids': ['e1', 'e2'],
            'body_contract': BODY_VERSION, 'source_plan_unit_ids': ['u1', 'u2'],
            'required_evidence_ids': ['e1', 'e2'], 'covered_required_evidence_ids': ['e1', 'e2'],
            'section_id': '', 'display_module_id': 'display_001', 'essential': True,
            'requires_claim_ids': [], 'support_map': [
                {'quote': text, 'evidence_ids': ['e1', 'e2'], 'supported': True}]}


@pytest.mark.parametrize('rows', [None, [],
    [{'quote': 'The model uses neural signals.', 'evidence_ids': ['e1'], 'supported': True}],
    [{'quote': 'The model uses neural signals. It predicts behavior.', 'evidence_ids': ['foreign'], 'supported': True}],
    [{'quote': 'The model uses neural signals. It predicts behavior.', 'evidence_ids': ['e1'], 'supported': False}],
])
def test_partial_support_or_foreign_evidence_cannot_approve_whole_expression(rows):
    assert not support_coverage(expression()['text'], rows, ['e1', 'e2'])


def test_multiple_spans_cover_all_visible_words():
    rows = [{'quote': 'The model uses neural signals.', 'evidence_ids': ['e1'], 'supported': True},
            {'quote': 'It predicts behavior.', 'evidence_ids': ['e2'], 'supported': True}]
    assert support_coverage(expression()['text'], rows, ['e1', 'e2'])
    assert not support_coverage('The model does not use neural signals.',
        [{'quote': 'The model', 'evidence_ids': ['e1'], 'supported': True},
         {'quote': 'use neural signals.', 'evidence_ids': ['e1'], 'supported': True}], ['e1'])


@pytest.mark.parametrize('text',['Value -5.', 'Score ≤ 5.', 'A / B.'])
def test_meaningful_math_symbols_cannot_fall_outside_support_spans(text):
    rows=[{'quote':part,'evidence_ids':['e1'],'supported':True}
          for part in text.replace('-',' ').replace('≤',' ').replace('/',' ').split()]
    assert not support_coverage(text,rows,['e1'])


@pytest.mark.parametrize('mutation', ['missing_required', 'foreign_source', 'foreign_evidence', 'duplicate_visual'])
def test_invalid_plan_fails_instead_of_auto_creating_recovery_modules(tmp_path, mutation):
    state = module_state(tmp_path); raw = raw_plan()
    if mutation == 'missing_required': raw['modules'][0]['evidence_ids'] = ['e1']
    if mutation == 'foreign_source': raw['modules'][0]['source_plan_unit_ids'] = ['other']
    if mutation == 'foreign_evidence': raw['modules'][0]['evidence_ids'].append('other')
    if mutation == 'duplicate_visual':
        state['images'] = {'1': {}}
        raw['modules'][0]['visual_ids'] = ['figure_1', 'figure_1']
    with pytest.raises(ValueError): normalize_module_plan(raw, state)


def test_multisource_prose_retains_original_units_through_layout_and_retrieval(tmp_path):
    from src.layout.presentation_policy import section_sources, prepare_structure
    from src.layout.families import FAMILIES
    from utils.module_content import module_context
    state = module_state(tmp_path)
    state['sample_module_plan'] = normalize_module_plan(raw_plan(), state)
    claim = expression(); state['poster_claims'] = {'claims': [claim]}
    state['verified_claims'] = {'claims': [claim]}
    finalize_modules(state)
    board = state['verified_module_board'];section = board['spatial_content_plan']['sections'][0]
    assert section['claim_ids'] == ['pc_0001'] and section['text_content'] == [claim['text']]
    assert section_sources(section, state) == ['u1', 'u2']
    # A colliding display ID cannot inject some unrelated scientific unit.
    state['narrative_plan']['sections'].append({'section_id':'display_001','evidence_ids':['foreign']})
    assert set(module_context(state, board, 'display_001')['evidence_ids']) == {'e1','e2'}
    for family in FAMILIES:
        prepared, report = prepare_structure(board, state, family)
        assert [(s['section_id'], s['claim_ids'], s['text_content']) for s in prepared['spatial_content_plan']['sections']] == [
            (s['section_id'], s['claim_ids'], s['text_content']) for s in board['spatial_content_plan']['sections']]
        assert not report['merges'] and report['reason'] == 'verified_module_prose_ownership'


@pytest.mark.parametrize('failure', ['essential_rejected','evidence_lost','dependency_lost','empty_module'])
def test_preparation_cannot_freeze_incomplete_module_science(tmp_path, failure):
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    claim=expression();state['poster_claims']={'claims':[deepcopy(claim)]}
    state['verified_claims']={'claims':[claim]}
    if failure=='essential_rejected':state['verified_claims']['claims']=[]
    if failure=='evidence_lost':claim['support_map'][0]['evidence_ids']=['e1']
    if failure=='dependency_lost':claim['requires_claim_ids']=['rejected']
    if failure=='empty_module':claim['display_module_id']='elsewhere'
    with pytest.raises(ValueError):finalize_modules(state)


def test_necessary_evidence_protects_one_expression_not_all_shared_citations(tmp_path):
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    a=expression();a['essential']=False
    b=deepcopy(a);b.update(claim_id='pc_0002',text='The model uses neural signals and predicts behavior.')
    b['support_map']=[{'quote':b['text'],'evidence_ids':['e1','e2'],'supported':True}]
    state['poster_claims']=state['verified_claims']={'claims':[a,b]}
    finalize_modules(state)
    decisions=state['verified_module_board']['editorial_selection']['items']
    assert sum(i['disposition']=='required' for i in decisions)==1


def test_citing_required_source_does_not_prove_its_necessary_assertion_was_expressed(tmp_path):
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    claim=expression();claim['covered_required_evidence_ids']=['e1']
    state['poster_claims']=state['verified_claims']={'claims':[claim]}
    with pytest.raises(ValueError,match='indispensable'):finalize_modules(state)


def test_new_module_install_keeps_existing_optional_key_visual_recovery_without_model_call(monkeypatch,tmp_path):
    import src.agents.grounded_curator as module
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    claim=expression();state['poster_claims']=state['verified_claims']={'claims':[claim]}
    finalize_modules(state)
    original=deepcopy(state['verified_module_board'])
    state.update(images={'1':{'aspect':2.0}},classified_visuals={'key_visual':'figure_1','method_workflow':['figure_1']})
    monkeypatch.setattr(module,'LangGraphAgent',lambda *args:pytest.fail('No extra initial Curator request'))
    module.GroundedCurator()(state)
    assert not state['errors'] and state['verified_module_board']==original
    assert state['visual_curation_report']['key_seed_status']=='seeded_as_optional_candidate'
    assert state['story_board']['spatial_content_plan']['sections'][0]['visual_assets']==[{'visual_id':'figure_1'}]


def test_written_auxiliary_module_routes_to_shared_structure_repair_before_family_search(tmp_path):
    from src.agents.layout_agent import LayoutAgent
    from src.layout.feasibility import fit_family_layout,LayoutFeasibilityError
    state=module_state(tmp_path);raw=raw_plan();raw['modules'][0]['module_purpose']='supporting'
    state['sample_module_plan']=normalize_module_plan(raw,state)
    claim=expression();claim['discourse_kind']='setup'
    state['poster_claims']=state['verified_claims']={'claims':[claim]}
    finalize_modules(state);state['styling_interfaces']={}
    with pytest.raises(LayoutFeasibilityError) as error:
        fit_family_layout(LayoutAgent(),state['verified_module_board'],state,'classic_three_column')
    report=error.value.report
    assert report['reason_code']=='PRESENTATION_STRUCTURE_UNRESOLVED'
    assert report['failure_scope']=='shared_content' and report['trial_count']==0
    assert report['presentation_preparation']['unresolved_section_ids']==['display_001']


def test_conditions_first_writing_does_not_hide_the_result_from_core_preferences(tmp_path):
    from src.layout.presentation_policy import prepare_structure
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    claims=[]
    for i in range(4):
        c=expression();c.update(claim_id=f'pc_{i}',text=f'Context statement {i}.',
            discourse_kind='result' if i==3 else 'setup',
            source_plan_unit_ids=['u2'] if i==3 else ['u1'],section_id='u2' if i==3 else 'u1')
        claims.append(c)
    state['poster_claims']=state['verified_claims']={'claims':claims};finalize_modules(state)
    section=state['verified_module_board']['spatial_content_plan']['sections'][0]
    assert section['claim_ids']==['pc_0','pc_1','pc_2','pc_3'] and 'pc_3' in section['core_claim_ids']
    _,report=prepare_structure(state['verified_module_board'],state,FAMILIES[0])
    assert not report['unresolved_section_ids']


def test_pressure_summary_includes_overloaded_module_instead_of_duplicate_small_misses():
    small={'section_id':'small','zone_id':'z','estimated_used_in':4.2,'zone_limit_in':4.1}
    large={'section_id':'large','zone_id':'z','estimated_used_in':45,'zone_limit_in':28}
    rows=diagnostic_pressure({'repair_pressure_candidates':[small]*8,'height_pressure_samples':[large]})
    assert rows==[large,small]


def test_title_only_revision_is_rejected_without_spending_layout_rounds(tmp_path):
    from test_sample_execution import curated
    store=ExplorationStore(tmp_path/'store');store.run_path('run_test').mkdir(parents=True)
    state=scientific(tmp_path);state['sample_science_digest']='science'
    state['iteration_context']={'attempt_diagnostics_dir':str(store.sample_path('run_test','sample_000001')/'attempts/attempt_0001')}
    cache=SampleCuration(store,'run_test','sample_000001');cache.run(state,curated)
    state['layout_feasibility_report']={'failure_scope':'shared_content','reason_code':'PRESENTATION_STRUCTURE_UNRESOLVED','failure_stage':'structure'}
    (store.sample_path('run_test','sample_000001')/'attempts/attempt_0001').mkdir(parents=True)
    state['curation_repair_context']=cache.repair_context(state)
    assert state['curation_repair_context'] is not None
    def rename(s):
        curated(s);s['story_board']['spatial_content_plan']['sections'][0]['section_title']='A new title';return s
    cache.run(state,rename)
    assert state['curation_report']['reason']=='no_material_structure_change'
    assert cache.revision(state)==0 and cache.repair_context(state) is None
    attempts=store.sample_path('run_test','sample_000001')/'attempts';attempts.mkdir(exist_ok=True)
    assert budget_usage(attempts/'attempt_0001')==(0,0)


def test_normal_height_failure_never_charges_curator(tmp_path):
    from test_sample_execution import curated
    store=ExplorationStore(tmp_path/'store');store.run_path('run_test').mkdir(parents=True)
    state=scientific(tmp_path);state['sample_science_digest']='science'
    cache=SampleCuration(store,'run_test','sample_000001');cache.run(state,curated)
    state['layout_feasibility_report']={'reason_code':'NO_FAST_FEASIBLE_VARIANT'}
    assert cache.repair_context(state) is None
    assert not (cache.root/'curation_budget.json').exists()


def stub_models(monkeypatch):
    import src.agents.sample_module_planner as planner
    import src.agents.claim_writer as writer
    import src.agents.claim_verifier as verifier
    calls=[]
    class Agent:
        def __init__(self,*args):self.name=args[-1]
        def reset(self):pass
        def step(self,prompt):
            calls.append((self.name,prompt))
            if self.name=='grounded_curator':result=raw_plan()
            elif self.name=='claim_writer':result={'claims':[{'item_id':'a','text':expression()['text'],
                'evidence_ids':['e1','e2'],'essential':True,'kind':'method'}]}
            else:
                claim=json.loads(prompt.split('CLAIM:\n',1)[1].split('\n\nEVIDENCE:',1)[0])
                result={'supported':True,'coverage':[{'quote':claim['text'],
                    'evidence_ids':claim['evidence_ids'],'supported':True}], 'relationships_supported':True,
                    'covered_required_evidence_ids':claim.get('required_evidence_ids', [])}
            return SimpleNamespace(content=json.dumps(result),input_tokens=1,output_tokens=1)
    for mod in [planner,writer,verifier]:
        monkeypatch.setattr(mod,'LangGraphAgent',Agent)
        monkeypatch.setattr(mod,'apply_agent_policy',lambda c,_:c)
    return calls


def test_legacy_module_interfaces_remain_valid_with_single_family_sample_policy(monkeypatch,tmp_path):
    from src.agents.sample_module_planner import sample_module_planner_node
    from src.agents.claim_writer import claim_writer_node
    from src.agents.grounded_curator import grounded_curator_node
    from src.workflow.exploration_runner import PosterExplorationRunner
    calls=stub_models(monkeypatch);state=module_state(tmp_path);plan=deepcopy(state['narrative_plan']);seen=[]
    def scientific_plan(s):s['narrative_plan']=deepcopy(plan);return s
    def design(s):
        assert s['verified_module_board'] and s['module_body_report']['verified_items']==1
        assert s['story_board']['spatial_content_plan']['sections'][0]['text_content']==[expression()['text']]
        seen.append(s['sample_science_digest'])
        if len(seen)==1:
            s.update(errors=['known fit'],layout_preflight_failed=True,layout_feasibility_report={'reason_code':'NO_FAST_FEASIBLE_VARIANT'})
            return s
        s['story_board']=None;return render_sample(s)
    generator=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=2,random_seed=31,
        paper_nodes=[],preparation_nodes=[scientific_plan,sample_module_planner_node,claim_writer_node,sample_claim_verifier_node],
        design_nodes=[grounded_curator_node,design],critic=critic_with_scores([30,90]))
    result=generator.run(state,paper_ready=True)
    assert result['run_state']['rendered_samples']==1
    assert [name for name,_ in calls]==['grounded_curator','claim_writer','claim_verifier']*2
    assert len(seen)==2 and seen[0]!=seen[1]
    for row in result['run_state']['results']:
        if not row['poster_id']:continue
        path=generator.storage.verify_poster(row['poster_id'])/'diagnostics'
        assert read_json(path/'sample_module_plan.json')['version']==BODY_VERSION


def test_actual_verifier_rejects_partial_body_verdict(monkeypatch,tmp_path):
    import src.agents.claim_verifier as verifier
    class Agent:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,p):return SimpleNamespace(content=json.dumps({'supported':True,'relationships_supported':True,
            'coverage':[{'quote':'The model uses neural signals.','evidence_ids':['e1'],'supported':True}]}),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(verifier,'LangGraphAgent',Agent)
    monkeypatch.setattr(verifier,'apply_agent_policy',lambda c,_:c)
    state=module_state(tmp_path);state['poster_claims']={'claims':[expression()]}
    verifier.ClaimVerifier()(state)
    assert state['verified_claims']['claims']==[] and not state['verification_passed']


def test_new_body_correction_requires_fresh_coverage_and_information_preservation(monkeypatch,tmp_path):
    import src.agents.claim_verifier as verifier
    original=expression(); corrected='The model uses neural signals and predicts behavior.'
    responses=iter([{'supported':False,'corrected_text':corrected,'error_types':['scope_overclaim']},
        {'supported':True,'coverage':[{'quote':corrected,'evidence_ids':['e1','e2'],'supported':True}],
         'relationships_supported':True,'necessary_information_preserved':False}])
    class Agent:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,p):return SimpleNamespace(content=json.dumps(next(responses)),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(verifier,'LangGraphAgent',Agent)
    monkeypatch.setattr(verifier,'apply_agent_policy',lambda c,_:c)
    state=module_state(tmp_path);state['poster_claims']={'claims':[original]}
    verifier.ClaimVerifier()(state)
    assert state['verified_claims']['claims']==[]
    assert state['verification_report']['details'][0]['error_types']==['corrected_text_not_verified']


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f:f.family_id)
def test_module_body_ownership_reaches_all_family_search_and_compile(family):
    from test_family_design_policy import state_for
    from test_layout_exploration import _board, _MeasuredAgent
    from src.config.critic_config import load_critic_config
    from src.layout.feasibility import fit_family_layout
    from src.layout.families import valid_family_topology
    from src.workflow.content_contracts import module_provenance
    board=_board();state=state_for(board)
    mapping={s['section_id']:f'display_{i}' for i,s in enumerate(board['spatial_content_plan']['sections'])}
    for c in state['verified_claims']['claims']:
        c.update(body_contract=BODY_VERSION,source_plan_unit_ids=[c['section_id']],verified=True)
    for s in board['spatial_content_plan']['sections']:s['section_id']=mapping[s['section_id']]
    state.update(sample_module_plan={'version':BODY_VERSION},verified_module_board=deepcopy(board),story_board=deepcopy(board))
    config=load_critic_config();config['composition_refinement']['enabled']=False
    fitted,spec,report=fit_family_layout(_MeasuredAgent(),board,state,family.family_id,config=config)
    assert report['status']=='feasible' and valid_family_topology(family,spec['zones'])
    assert report['presentation_preparation']['reason']=='verified_module_prose_ownership'
    provenance=module_provenance(fitted,state)
    assert all(m['plan_section_ids'] and not any(s.startswith('display_') for s in m['plan_section_ids'])
               for m in provenance['modules'])


@pytest.mark.parametrize('stop_after',[1,2,3,4])
def test_each_new_preparation_checkpoint_resumes_without_repeating_model_calls(monkeypatch,tmp_path,stop_after):
    from functools import wraps
    from src.agents.sample_module_planner import sample_module_planner_node
    from src.agents.claim_writer import claim_writer_node
    from src.agents.grounded_curator import grounded_curator_node
    from src.workflow.exploration_runner import PosterExplorationRunner
    from src.workflow.run_control import RunControl
    calls=stub_models(monkeypatch);state=module_state(tmp_path);plan=deepcopy(state['narrative_plan'])
    control=RunControl()
    def research(s):s['narrative_plan']=deepcopy(plan);return s
    def wrap(node,index):
        @wraps(node)
        def run(s):
            result=node(s)
            if index==stop_after:control.request_stop(force=True)
            return result
        return run
    nodes=[wrap(n,i) for i,n in enumerate([research,sample_module_planner_node,claim_writer_node,sample_claim_verifier_node],1)]
    def design(s):s['story_board']=None;return render_sample(s)
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),samples=1,control=control,
        paper_nodes=[],preparation_nodes=nodes,design_nodes=[grounded_curator_node,design])
    assert runner.run(state,paper_ready=True)['run_state']['status']=='PAUSED'
    resumed=PosterExplorationRunner(storage=runner.storage,run_id=runner.run_id,paper_nodes=[],
        preparation_nodes=nodes,design_nodes=[grounded_curator_node,design],critic=critic_with_scores([40]))
    assert resumed.run(state)['run_state']['rendered_samples']==1
    assert [name for name,_ in calls]==['grounded_curator','claim_writer','claim_verifier']


@pytest.mark.parametrize('second_rewrite',[False,True])
def test_final_context_refresh_is_targeted_and_cannot_loop(monkeypatch,tmp_path,second_rewrite):
    import src.agents.claim_verifier as verifier
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    original=expression();original['module_context']={'items':[{'claim_id':original['claim_id'],'text':original['text']}]}
    state['poster_claims']={'claims':[deepcopy(original)]};calls=[]
    changed='The model uses neural signals and predicts behavior.'
    def verify(s):
        calls.append(deepcopy(s['poster_claims']))
        claim=deepcopy(s['poster_claims']['claims'][0])
        if len(calls)==1:claim['text']=changed
        else:
            assert claim['module_context']['items']==[{'claim_id':claim['claim_id'],'text':changed}]
            if second_rewrite:claim['text']='A further changed expression.'
        claim['support_map']=[{'quote':claim['text'],'evidence_ids':['e1','e2'],'supported':True}]
        s.update(verified_claims={'claims':[claim]},verification_passed=True,verification_report={'summary':{}})
        return s
    monkeypatch.setattr(verifier,'claim_verifier_node',verify)
    sample_claim_verifier_node(state)
    assert len(calls)==2
    if second_rewrite:
        assert not state['verification_passed'] and state['errors'] and not state.get('verified_module_board')
    else:
        assert not state['errors'] and state['verified_module_board']
        assert read_json(Path(state['output_dir'])/'content/verified_claims.json')==state['verified_claims']


def test_sample_color_is_reused_only_with_matching_science_and_valid_digest(tmp_path):
    from test_sample_execution import curated
    store=ExplorationStore(tmp_path/'store');store.run_path('run_test').mkdir(parents=True)
    state=scientific(tmp_path);state['sample_science_digest']='science';calls=[]
    cache=SampleCuration(store,'run_test','sample_000001');cache.run(state,curated)
    def color(s):calls.append(1);s['color_scheme']={'text':'#000000'};return s
    cache.run_color(state,color);state['color_scheme']=None
    cache.run_color(state,color)
    assert calls==[1] and state['color_scheme']=={'text':'#000000'}
    state['sample_science_digest']='different sample science'
    with pytest.raises(ValueError,match='identity'):cache.run_color(state,color)
