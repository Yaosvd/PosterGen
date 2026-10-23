"""Responsibility assembly, local patches and sample-wide editorial recovery."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_sample_module_body import module_state, raw_plan, expression, stub_models
from test_module_planning_interface import fake_agent, history
from src.agents.sample_module_planner import sample_module_planner_node
from src.agents.claim_writer import claim_writer_node
from src.workflow.sample_modules import normalize_module_plan, ModulePlanValidationError, sample_claim_verifier_node
from src.workflow.module_plan_patches import identify_modules, apply_module_patch
from src.workflow.module_planning_requests import ModulePlanningRequests
from utils.persistence import read_json


def test_declared_whole_unit_responsibility_fills_all_required_without_new_module(tmp_path):
    state = module_state(tmp_path);raw = raw_plan()
    row = raw['modules'][0]
    row.pop('source_plan_unit_ids');row.update(evidence_ids=['e1'], required_unit_ids=['u1', 'u2'])
    plan = normalize_module_plan(raw, state)
    assert len(plan['modules']) == 1
    assert plan['modules'][0]['evidence_ids'] == ['e1', 'e2']
    assert plan['modules'][0]['required_evidence_ids'] == ['e1', 'e2']
    assert any(n['code'] == 'declared_responsibility_materialized' for n in plan['source_normalizations'])


def test_same_origin_alone_does_not_assign_omitted_necessary_information(tmp_path):
    state = module_state(tmp_path)
    state['narrative_plan']['sections'][0].update(evidence_ids=['e1','e2'],required_evidence_ids=['e1','e2'])
    state['narrative_plan']['sections'].pop()
    raw=raw_plan();raw['modules'][0].update(evidence_ids=['e1'],source_plan_unit_ids=['u1'])
    with pytest.raises(ModulePlanValidationError) as exc:normalize_module_plan(raw,state)
    assert any(i['code']=='missing_indispensable_evidence' for i in exc.value.issues)


def test_support_bank_restores_context_without_making_it_mandatory(tmp_path):
    state=module_state(tmp_path)
    state['evidence_bank']['items'].append({'evidence_id':'e3','claim':'metric','source_excerpt':'metric'})
    state['narrative_plan']['sections'][0]['evidence_ids'].append('e3')
    plan=normalize_module_plan(raw_plan(),state)
    module=plan['modules'][0]
    assert module['support_evidence_ids']==['e3']
    assert set(module['available_evidence_ids'])=={'e1','e2','e3'}
    assert module['required_evidence_ids']==['e1','e2']


@pytest.mark.parametrize('field,value,code',[
    ('required_unit_ids',['unknown'],'invalid_required_unit_ids'),
    ('required_evidence_ids',['unknown'],'invalid_required_evidence_ids'),
    ('required_unit_ids','u1','invalid_required_unit_ids'),
    ('module_id','../bad','invalid_or_duplicate_module_id'),
])
def test_responsibilities_cannot_invent_science_or_paths(tmp_path,field,value,code):
    raw=raw_plan();raw['modules'][0][field]=value
    with pytest.raises(ModulePlanValidationError) as exc:normalize_module_plan(raw,module_state(tmp_path))
    assert any(i['code']==code for i in exc.value.issues)


def test_explicit_parts_can_split_a_unit_but_duplicate_responsibility_fails(tmp_path):
    state=module_state(tmp_path)
    state['narrative_plan']['sections'][0].update(evidence_ids=['e1','e2'],required_evidence_ids=['e1','e2'])
    state['narrative_plan']['sections'].pop()
    row=raw_plan()['modules'][0]
    raw={'modules':[dict(row,evidence_ids=[],source_plan_unit_ids=[],required_evidence_ids=['e1']),
                    dict(row,evidence_ids=[],source_plan_unit_ids=[],required_evidence_ids=['e2'])]}
    plan=normalize_module_plan(raw,state)
    assert [m['required_evidence_ids'] for m in plan['modules']]==[['e1'],['e2']]
    for row in raw['modules']:row['required_unit_ids']=['u1']
    with pytest.raises(ModulePlanValidationError) as exc:normalize_module_plan(raw,state)
    assert any(i['code']=='duplicate_required_responsibility' for i in exc.value.issues)


def test_patch_keeps_unaffected_modules_and_stable_ids():
    raw=raw_plan();raw['modules'].append(deepcopy(raw['modules'][0]))
    draft=identify_modules(raw)
    updated=apply_module_patch(draft,{'updates':[{'module_id':'display_001','set':{'required_unit_ids':['u1']}}]})
    assert updated['modules'][1]==draft['modules'][1] and updated['modules'][0]['module_id']=='display_001'
    assert 'required_unit_ids' not in draft['modules'][0]


@pytest.mark.parametrize('patch',[
    {'modules':[]}, {'updates':[{'module_id':'missing','set':{}}]},
    {'updates':[{'module_id':'display_001','set':{'module_id':'changed'}}]},
    {'module_order':[]}, {'add_modules':[{'module_id':'display_001'}]},
])
def test_invalid_patch_never_changes_the_base(patch):
    base=identify_modules(raw_plan());before=deepcopy(base)
    with pytest.raises(ModulePlanValidationError):apply_module_patch(base,patch)
    assert base==before


def test_one_allowance_is_shared_between_curation_and_body(tmp_path):
    state=module_state(tmp_path)
    class Agent:
        def reset(self):pass
        def step(self,p):
            from types import SimpleNamespace
            return SimpleNamespace(content='{}',input_tokens=1,output_tokens=1)
    a=ModulePlanningRequests(state,'a')
    a.request(1,Agent(),'repair a')
    b=ModulePlanningRequests(state,'b',directory='content/body',kind='module_body_correction',scope='display_001')
    with pytest.raises(ValueError,match='exhausted'):b.request(1,Agent(),'repair b')
    assert not (b.root/'request_01.json').exists()


def test_module_writer_replays_partial_work_without_second_model_call(monkeypatch,tmp_path):
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    calls=stub_models(monkeypatch)
    claim_writer_node(state)
    assert not state['errors']
    saved=deepcopy(state['poster_claims']);state['poster_claims']=None
    claim_writer_node(state)
    assert state['poster_claims']==saved
    assert [name for name,_ in calls]==['claim_writer']
    archive=Path(state['output_dir'])/'content/module_writing/display_001'
    assert (archive/'response_00.json').exists() and (archive/'body.json').exists()


def test_writer_receives_support_and_exact_obligations(monkeypatch,tmp_path):
    state=module_state(tmp_path)
    state['evidence_bank']['items'].append({'evidence_id':'e3','claim':'metric definition','source_excerpt':'metric definition'})
    state['narrative_plan']['sections'][0]['evidence_ids'].append('e3')
    state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    calls=stub_models(monkeypatch);claim_writer_node(state)
    prompt=calls[0][1]
    assert 'metric definition' in prompt and 'required_evidence_ids' in prompt
    assert state['poster_claims']['claims'][0]['source_plan_unit_ids']==['u1','u2']


def test_real_verifier_journal_reuses_exact_input_and_archives_raw(monkeypatch,tmp_path):
    import src.agents.claim_verifier as verifier
    state=module_state(tmp_path);state['poster_claims']={'claims':[expression()]}
    calls=stub_models(monkeypatch)
    verifier.claim_verifier_node(state);first=deepcopy(state['verified_claims'])
    verifier.claim_verifier_node(state)
    assert state['verified_claims']==first
    assert [name for name,_ in calls]==['claim_verifier']
    assert list((Path(state['output_dir'])/'content/module_verification').rglob('response_00.json'))


def test_missing_verified_information_gets_one_body_repair_and_full_reverification(monkeypatch,tmp_path):
    import src.agents.claim_writer as writer
    import src.agents.claim_verifier as verifier
    from types import SimpleNamespace
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    calls=[]
    class Agent:
        def __init__(self,*args):self.name=args[-1]
        def reset(self):pass
        def step(self,prompt):
            calls.append(self.name)
            if self.name=='claim_writer':
                if 'Correct only the affected' not in prompt:
                    result={'claims':[{'item_id':'a','text':'The model uses neural signals.','evidence_ids':['e1'],'essential':True}]}
                else:
                    result={'modules':[{'module_id':'display_001','claims':[{
                        'item_id':'a','text':expression()['text'],'evidence_ids':['e1','e2'],'essential':True,
                        'replaces_claim_ids':['pc_display_001_001']}]}]}
            else:
                claim=json.loads(prompt.split('CLAIM:\n',1)[1].split('\n\nEVIDENCE:',1)[0])
                result={'supported':True,'coverage':[{'quote':claim['text'],'evidence_ids':claim['evidence_ids'],'supported':True}],
                        'relationships_supported':True,'necessary_information_preserved':True,
                        'covered_required_evidence_ids':claim['required_evidence_ids']}
            return SimpleNamespace(content=json.dumps(result),input_tokens=1,output_tokens=1)
    for mod in (writer,verifier):monkeypatch.setattr(mod,'LangGraphAgent',Agent);monkeypatch.setattr(mod,'apply_agent_policy',lambda c,_:c)
    writer.claim_writer_node(state);sample_claim_verifier_node(state)
    assert not state['errors'] and state['verified_module_board']
    assert calls==['claim_writer','claim_verifier','claim_writer','claim_verifier']
    assert state['verified_claims']['claims'][0]['original_expression']=='The model uses neural signals.'
    budget=read_json(Path(state['output_dir'])/'preparation_repair_budget.json')['payload']
    assert budget['charge']['kind']=='module_body_correction'


def test_repair_cannot_remove_an_essential_old_expression(monkeypatch,tmp_path):
    import src.agents.claim_writer as writer
    from types import SimpleNamespace
    from src.workflow.sample_module_writing import repair_verified_modules
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    state['poster_claims']={'claims':[expression()]}
    class Agent:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,p):return SimpleNamespace(content=json.dumps({'modules':[{'module_id':'display_001','claims':[{
            'item_id':'a','text':'It predicts behavior.','evidence_ids':['e2'],'essential':True}]}]}),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(writer,'LangGraphAgent',Agent);monkeypatch.setattr(writer,'apply_agent_policy',lambda c,_:c)
    with pytest.raises(ValueError,match='lost or duplicated'):repair_verified_modules(state,{'display_001':{'missing':['e2']}})
    assert state['poster_claims']['claims'][0]['text']==expression()['text']


def test_partial_invalid_draft_does_not_allow_discarding_good_modules():
    raw=raw_plan();raw['modules'].append(None)
    draft=identify_modules(raw)
    with pytest.raises(ModulePlanValidationError):apply_module_patch(draft,{'replacement_modules':raw_plan()['modules']})
    fixed=apply_module_patch(draft,{'updates':[{'module_id':'display_002','set':raw_plan()['modules'][0]}]})
    assert fixed['modules'][0]==draft['modules'][0] and not fixed['modules'][1].get('_invalid_module')


def test_rewritten_body_needs_explicit_information_preservation(monkeypatch,tmp_path):
    import src.agents.claim_verifier as verifier
    from types import SimpleNamespace
    state=module_state(tmp_path);claim=expression();claim['original_expression']=claim['text']
    state['poster_claims']={'claims':[claim]}
    class Agent:
        def __init__(self,*args):pass
        def reset(self):pass
        def step(self,prompt):return SimpleNamespace(content=json.dumps({
            'supported':True,'coverage':[{'quote':claim['text'],'evidence_ids':['e1','e2'],'supported':True}],
            'relationships_supported':True,'necessary_information_preserved':False,
            'covered_required_evidence_ids':['e1','e2']}),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(verifier,'LangGraphAgent',Agent);monkeypatch.setattr(verifier,'apply_agent_policy',lambda c,_:c)
    verifier.claim_verifier_node(state)
    assert state['verified_claims']['claims']==[] and not state['verification_passed']


@pytest.mark.parametrize('verdict',[
    {'claim_id':'pc_1','text':'The model uses neural signals.'},
    {}, {'supported':'true'}, {'supported':0},
])
def test_verifier_non_verdict_is_format_failure_without_editorial_retry(monkeypatch,tmp_path,verdict):
    import src.agents.claim_verifier as verifier
    import src.workflow.sample_module_writing as writing
    from types import SimpleNamespace
    state=module_state(tmp_path);state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    second=dict(expression(),claim_id='pc_2',text='It predicts behavior.',evidence_ids=['e2'],
                required_evidence_ids=['e2'],essential=False)
    state['poster_claims']={'claims':[second,expression(),dict(second,claim_id='pc_after')]}
    calls=[];repairs=[]
    class Agent:
        def __init__(self,*args):pass
        def reset(self):pass
        def step(self,prompt):
            calls.append(prompt)
            claim=json.loads(prompt.split('CLAIM:\n',1)[1].split('\n\nEVIDENCE:',1)[0])
            result=verdict if claim['claim_id']!='pc_2' else {
                'supported':True,'coverage':[{'quote':claim['text'],'evidence_ids':['e2'],'supported':True}],
                'relationships_supported':True,'covered_required_evidence_ids':['e2']}
            return SimpleNamespace(content=json.dumps(result),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(verifier,'LangGraphAgent',Agent)
    monkeypatch.setattr(verifier,'apply_agent_policy',lambda c,_:c)
    monkeypatch.setattr(writing,'repair_verified_modules',lambda s,f:repairs.append(f) or s)
    sample_claim_verifier_node(state)
    assert len(calls)==2 and state['errors'] and not repairs
    assert state['verification_report']['details'][-1]['error_types']==['verification_failure']
    assert state['verification_report']['status']=='incomplete'
    assert state['verification_report']['summary']['not_checked_claim_ids']==['pc_after']
    assert state['verification_passed'] is False
    assert not (Path(state['output_dir'])/'preparation_repair_budget.json').exists()


def test_verification_context_keeps_exact_original_chunk_and_deduplicates(tmp_path):
    from src.workflow.sample_module_writing import verification_source_context
    state=module_state(tmp_path)
    text='The dataset is IBL. The model uses neural signals. It predicts behavior.'
    state['section_chunks']=[{'section_id':'paper_1','chunk_index':0,'section_name':'Data','content':text}]
    evidence=deepcopy(state['evidence_bank']['items'])
    for e in evidence:e['source']={'section_id':'paper_1','chunk_index':0}
    result=verification_source_context(state,evidence)
    assert result['unavailable_evidence_ids']==[]
    assert len(result['chunks'])==1
    assert result['chunks'][0]['content']==text
    assert result['chunks'][0]['evidence_ids']==['e1','e2']
    assert 'source_context' not in evidence[0]


@pytest.mark.parametrize('defect',['foreign_section','wrong_chunk','nonverbatim','ambiguous_chunk'])
def test_verification_context_never_guesses_a_source(tmp_path,defect):
    from src.workflow.sample_module_writing import verification_source_context
    state=module_state(tmp_path);evidence=deepcopy(state['evidence_bank']['items'][:1])
    row={'section_id':'paper_1','chunk_index':0,'content':evidence[0]['source_excerpt']}
    evidence[0]['source']={'section_id':'paper_1','chunk_index':0}
    state['section_chunks']=[row]
    if defect=='foreign_section':row['section_id']='paper_2'
    if defect=='wrong_chunk':row['chunk_index']=1
    if defect=='nonverbatim':row['content']='A different source.'
    if defect=='ambiguous_chunk':state['section_chunks'].append(deepcopy(row))
    result=verification_source_context(state,evidence)
    assert result=={'chunks':[],'unavailable_evidence_ids':['e1']}


def test_verifier_receives_context_on_initial_and_existing_correction_calls(monkeypatch,tmp_path):
    import src.agents.claim_verifier as verifier
    from types import SimpleNamespace
    state=module_state(tmp_path);claim=expression('The model uses neural signals. It predicts behavior.')
    state['poster_claims']={'claims':[claim]}
    state['section_chunks']=[{'section_id':'paper_1','chunk_index':0,'section_name':'Method',
                             'content':'We introduce the model. The model uses neural signals. It predicts behavior.'}]
    for e in state['evidence_bank']['items']:e['source']={'section_id':'paper_1','chunk_index':0}
    calls=[]
    class Agent:
        def __init__(self,*args):pass
        def reset(self):pass
        def step(self,prompt):
            calls.append(prompt)
            assert 'We introduce the model.' in prompt
            if len(calls)==1:
                result={'supported':False,'error_types':['unsupported_claim'],'corrected_text':claim['text']}
            else:
                result={'supported':True,'coverage':[{'quote':claim['text'],'evidence_ids':['e1','e2'],'supported':True}],
                        'relationships_supported':True,'necessary_information_preserved':True,
                        'covered_required_evidence_ids':['e1','e2']}
            return SimpleNamespace(content=json.dumps(result),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(verifier,'LangGraphAgent',Agent)
    monkeypatch.setattr(verifier,'apply_agent_policy',lambda c,_:c)
    verifier.claim_verifier_node(state)
    assert len(calls)==2 and not state['errors']
    assert state['verified_claims']['claims'][0]['repaired'] is True


def test_supported_clause_commas_are_normalized_with_original_verdict_preserved():
    from src.workflow.sample_module_writing import normalize_verifier_coverage
    from src.workflow.sample_modules import support_coverage
    text='NEDS uses neural signals, and predicts behavior.'
    result={'supported':True,'relationships_supported':True,'coverage':[
        {'quote':'NEDS uses neural signals','evidence_ids':['e1'],'supported':True},
        {'quote':'and predicts behavior.','evidence_ids':['e2'],'supported':True}]}
    before=deepcopy(result)
    assert not support_coverage(text,result['coverage'],['e1','e2'])
    normalized,notes=normalize_verifier_coverage(text,result)
    assert notes and result==before
    assert support_coverage(text,normalized['coverage'],['e1','e2'])


@pytest.mark.parametrize('text,quotes',[
    ('x > y',['x','y']),
    ('It is not effective.',['It is','effective.']),
    ('The count is 1, 000 neurons were recorded.',
     ['The count is 1','000 neurons were recorded.']),
    ('f(x, y)',['f(x','y)']),
    ('The sample used 83 animals, its result is 1.',
     ['The sample used','animals, its result is 1.']),
])
def test_coverage_format_normalization_cannot_fill_science(text,quotes):
    from src.workflow.sample_module_writing import normalize_verifier_coverage
    from src.workflow.sample_modules import support_coverage
    result={'supported':True,'relationships_supported':True,'coverage':[
        {'quote':q,'evidence_ids':['e1'],'supported':True} for q in quotes]}
    normalized,notes=normalize_verifier_coverage(text,result)
    assert normalized==result and not notes
    assert not support_coverage(text,normalized['coverage'],['e1'])


def test_negative_verdict_is_never_repaired_by_coverage_normalization():
    from src.workflow.sample_module_writing import normalize_verifier_coverage
    result={'supported':False,'relationships_supported':True,'coverage':[
        {'quote':'NEDS uses neural signals','evidence_ids':['e1'],'supported':True},
        {'quote':'and predicts behavior.','evidence_ids':['e2'],'supported':True}]}
    normalized,notes=normalize_verifier_coverage('NEDS uses neural signals, and predicts behavior.',result)
    assert normalized==result and not notes


@pytest.mark.parametrize('text,source,expected,changed',[
    ('Neural signals (ev_0001, ev_0002) were measured in 83 mice.',
     'Neural signals were measured in 83 mice.',
     'Neural signals were measured in 83 mice.',True),
    ('The cohort (83 mice, 5 regions) remains fixed.',
     '83 mice, 5 regions','The cohort (83 mice, 5 regions) remains fixed.',False),
    ('The gene (ev_0001) is measured.',
     'The gene ev_0001 is measured.','The gene (ev_0001) is measured.',False),
    ('Neural(ev_0001)signals remain.',
     'Neural signals remain.','Neural signals remain.',True),
])
def test_internal_annotations_do_not_remove_scientific_parentheses(text,source,expected,changed):
    from src.workflow.sample_module_writing import clean_internal_evidence_markers
    evidence={e:{'source_excerpt':source} for e in ['ev_0001','ev_0002']}
    result,notes=clean_internal_evidence_markers(text,list(evidence),evidence)
    assert result==expected and bool(notes)==changed


def test_internal_annotation_cannot_hide_undeclared_evidence():
    from src.workflow.sample_module_writing import clean_internal_evidence_markers
    with pytest.raises(ValueError,match='undeclared'):
        clean_internal_evidence_markers('A result (ev_0002).',['ev_0001'],{'ev_0001':{'source_excerpt':'A result.'}})


def test_writer_gets_original_context_for_qualifications(monkeypatch,tmp_path):
    state=module_state(tmp_path)
    state['section_chunks']=[{'section_id':'paper_1','chunk_index':0,
        'content':'We define the research model. The model uses neural signals. It predicts behavior.'}]
    for e in state['evidence_bank']['items']:e['source']={'section_id':'paper_1','chunk_index':0}
    state['sample_module_plan']=normalize_module_plan(raw_plan(),state)
    calls=stub_models(monkeypatch);claim_writer_node(state)
    assert not state['errors'] and 'We define the research model.' in calls[0][1]


def test_missing_preservation_verdict_is_saved_but_not_assumed_true(tmp_path):
    from src.workflow.sample_module_writing import verifier_response
    from types import SimpleNamespace
    state=module_state(tmp_path)
    class Agent:
        def reset(self):pass
        def step(self,prompt):return SimpleNamespace(content=json.dumps({'supported':True}),input_tokens=1,output_tokens=1)
    with pytest.raises(ValueError,match='necessary_information_preserved'):
        verifier_response(state,Agent(),'correction','pc_test',claim={
            'text':'It predicts behavior.','original_expression':'It predicts behavior effectively.'})
    assert list((Path(state['output_dir'])/'content/module_verification').rglob('parsed_00.json'))
    assert not (Path(state['output_dir'])/'preparation_repair_budget.json').exists()
