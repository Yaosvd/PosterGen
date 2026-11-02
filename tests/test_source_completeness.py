"""Incomplete drafts use bounded content edits; formatting never invents science."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from test_source_editorial import source_state, Agent, verdict_for, reading_review, no_remote_models, accept
from test_source_editorial_integration import fake_fit, fake_preview
from src.workflow import source_editorial as editorial
from src.workflow import source_preparation as preparation
from src.workflow import source_verification as science
from src.workflow.source_document import SourceOutputError, SourceProtocolError, paragraph_hints, bind_paragraph_refs
from src.workflow.source_requests import SourceRequests, object_schema, BOOL
from src.layout.families import LayoutFamilyRegistry
from src.layout.repair_budget import sample_ledger
from utils.persistence import read_json, digest


def incomplete_state(tmp_path, family='four_column_modular', count=4):
    state = source_state(tmp_path, count=count, family=family)
    unit = state['source_document']['units'][0]
    refs = bind_paragraph_refs({'source_refs': [{'source_id':unit['source_id'],
        'paragraph_ids':[unit['paragraphs'][2]['paragraph_id']]}]}, state['source_document'])['source_refs']
    state['source_narrative_plan']['obligations'].append({'obligation_id':'evaluation',
        'meaning':'Explain the evaluation population and reported improvement.',
        'rationale':'The reader needs actual evaluation conditions.', 'source_refs':refs})
    return state


class CompletionBalancer:
    def __init__(self, *, add=2, keep_missing=False, no_op=False):
        self.calls = []; self.add = add; self.keep_missing = keep_missing; self.no_op = no_op

    def reset(self):
        pass

    def step(self, message):
        self.calls.append(message)
        text = json.loads(message)[0]['text'] if message.lstrip().startswith('[') else message
        data = json.loads(text.split('\nINPUT:\n',1)[1].split('\nCURRENT EDIT TASK (execute on the visible poster, not the paper):',1)[0].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
        review = reading_review(data['reading_input'])
        if not data['reading_input']['has_actual_image']:
            review.update(status='incomplete',primary_routes=[])
        modules = deepcopy(data['whole_candidate']['modules'])
        links = []
        missing = data['feedback'].get('missing_indispensable_meanings')
        if missing and not self.no_op:
            for i in range(self.add):
                module = deepcopy(modules[0])
                module.update(module_id=f'added_{len(self.calls)}_{i}',title='Evaluation conditions',
                    narrative_role='evaluation',source_refs=missing[0]['source_refs'],
                    obligation_ids=[] if self.keep_missing else [missing[0]['obligation_id']],
                    visual_ids=[],reserve_visual_ids=[])
                module['entries'] = [{**deepcopy(module['entries'][0]),
                    'text':'The evaluation uses 16000 properties and a 3% to 17% improvement in the reported test setting.',
                    'source_refs':missing[0]['source_refs'],'display_label':'','step_index':0}]
                modules.append(module)
                links.append({'new_module_id':module['module_id'],'old_module_ids':[]})
        return SimpleNamespace(content=json.dumps({'modules':modules[len(data['whole_candidate']['modules']):], 'remove_module_ids':[], 'module_order':[],
            'lineage':links,'reason':'Explain the missing original evaluation conditions.',
            'layout_requests':data['previous_layout_requests'],
            **({'reading_review':{k:v for k,v in review.items() if k not in data['reading_input']['binding']}} if data['reading_input']['has_actual_image'] else {})}),
            input_tokens=5,output_tokens=5)


def offline_preparation(monkeypatch, agent):
    monkeypatch.setattr(preparation,'_fit',fake_fit)
    monkeypatch.setattr(preparation,'draft_preview',fake_preview)
    monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    monkeypatch.setattr(science,'request',lambda st,kind,data,schema,**kw:verdict_for(data['module'],st))


def test_missing_meaning_and_bad_topics_are_not_a_format_retry(tmp_path, monkeypatch):
    state = incomplete_state(tmp_path)
    raw = paragraph_hints({'modules':state['source_candidate']['modules']},state['source_document'])
    raw['modules'][1]['presentation_style']='topics'
    raw['modules'][1]['entries'][0]['display_label']='New independent heading'
    before = deepcopy(raw)
    agent = Agent(json.dumps(raw)); monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    editorial.source_curator_node(state)
    assert len(agent.calls)==1 and raw==before
    assert len(state['source_candidate']['modules'])==4 and not state['verification_passed']
    audit = read_json(Path(state['sample_preparation_dir'])/'source/curator/normalization.json')
    assert audit['missing_obligations'][0]['obligation_id']=='evaluation'
    assert audit['changes'][0]['reason']=='invalid_optional_topics_cue'
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()
    with pytest.raises(SourceOutputError,match='unassigned'):
        editorial.normalize_candidate({'modules':state['source_candidate']['modules']},state)
    with pytest.raises(SourceOutputError,match='assigned visible support'):
        science.verify_candidate(state,state['source_candidate'])


@pytest.mark.parametrize('family',LayoutFamilyRegistry().ids())
def test_content_completion_can_add_two_modules_without_freezing_initial_count(tmp_path, monkeypatch, family):
    initial_count=min(4,sum(z['capacity'] for z in LayoutFamilyRegistry().get(family).zones)-2)
    state = incomplete_state(tmp_path,family,count=initial_count)
    before = deepcopy(state['source_candidate'])
    agent = CompletionBalancer(); offline_preparation(monkeypatch,agent)
    state, result = preparation.converge(state)
    assert len(agent.calls)==1 and len(state['source_candidate']['modules'])==initial_count+2
    assert state['source_candidate']['modules'][:initial_count]==before['modules']
    assert [c['phase'] for c in sample_ledger(state)[1]['charges']]==['capacity']
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()
    assert state['source_reading_review']['status']=='incomplete'
    assert science.assert_verified(state,result[0])
    assert state['source_candidate_lineage'][0]['old_modules']==[]
    assert len(state['source_candidate_lineage'][0]['new_modules'])==2


def test_combined_structural_diagnostics_preserve_missing_content_for_charged_edit(tmp_path, monkeypatch):
    state = incomplete_state(tmp_path)
    raw = paragraph_hints({'modules':state['source_candidate']['modules']},state['source_document'])
    raw['modules'][1]['presentation_style']='topics'
    raw['modules'][1]['entries'][0]['display_label']='Independent heading'
    bad = deepcopy(raw)
    bad['modules'][0]['entries'][0]['parent_item_id']='missing'
    bad['modules'][2]['title']=''
    agent = Agent(json.dumps(bad),json.dumps(raw))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    editorial.source_curator_node(state)
    root = Path(state['sample_preparation_dir'])
    error = read_json(root/'source/curator/validation_00.json')['payload']['error']
    assert 'parent_item_id' in error and 'title' in error and 'evaluation' in error
    assert len(agent.calls)==2 and len(editorial.missing_obligations(state['source_candidate'],state))==1
    content_agent=CompletionBalancer();offline_preparation(monkeypatch,content_agent)
    state,_ = preparation.converge(state)
    assert len(content_agent.calls)==1 and len(sample_ledger(state)[1]['charges'])==1
    assert not editorial.missing_obligations(state['source_candidate'],state)


def test_format_repair_cannot_add_missing_explanation_or_modules(tmp_path, monkeypatch):
    state = incomplete_state(tmp_path)
    raw = paragraph_hints({'modules':state['source_candidate']['modules']},state['source_document'])
    bad = deepcopy(raw);bad['modules'][0]['entries'][0]['parent_item_id']='missing'
    changed = deepcopy(raw);new=deepcopy(changed['modules'][0]);new['module_id']='extra'
    new['obligation_ids']=['evaluation'];changed['modules'].append(new)
    agent=Agent(json.dumps(bad),json.dumps(changed))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    with pytest.raises(SourceProtocolError,match='no remaining'):
        editorial.source_curator_node(state)
    assert len(agent.calls)==2 and not sample_ledger(state)[1]['charges']


@pytest.mark.parametrize('mode',['too_many_modules','no_op','budget_exhausted','still_missing'])
def test_content_completion_is_bounded_and_cannot_hide_missing_meaning(tmp_path, monkeypatch, mode):
    state=incomplete_state(tmp_path)
    agent=CompletionBalancer(add=3 if mode=='too_many_modules' else 1,
        no_op=mode=='no_op',keep_missing=mode=='still_missing')
    offline_preparation(monkeypatch,agent)
    if mode=='budget_exhausted':
        from src.layout.repair_budget import charge_round
        for i in range(3):assert charge_round(state,'capacity',{},kind=f'prior_{i}')
    with pytest.raises(SourceOutputError):preparation.converge(state)
    assert len(agent.calls)==(0 if mode=='budget_exhausted' else 3 if mode=='still_missing' else 1)
    assert not state['verification_passed']
    assert len(sample_ledger(state)[1]['charges'])<=3


def test_content_decision_does_not_consume_format_recovery(tmp_path):
    state=source_state(tmp_path)
    agent=Agent('{"supported":true}')
    def reject(value):raise SourceOutputError('A scientific comparator is unsupported')
    with pytest.raises(SourceOutputError,match='comparator'):
        SourceRequests(state,'source/semantic','task',object_schema({'supported':BOOL})).call(agent,reject)
    assert len(agent.calls)==1
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()


def test_missing_mapping_is_not_semantic_approval(tmp_path, monkeypatch):
    state=incomplete_state(tmp_path)
    # Metadata alone can claim completion; the existing semantic judge must still reject it.
    raw={'modules':deepcopy(state['source_candidate']['modules'])}
    raw['modules'][0]['obligation_ids'].append('evaluation')
    candidate=editorial.normalize_candidate(raw,state)
    def reject(st,kind,data,schema,**kw):
        verdict=verdict_for(data['module'],st)
        for row in verdict['obligations']:
            if row['obligation_id']=='evaluation':row['fully_expressed']=False
        return verdict
    monkeypatch.setattr(science,'request',reject)
    with pytest.raises(SourceOutputError,match='indispensable meaning'):
        science.verify_candidate(state,candidate)


def test_completed_joint_candidate_replays_without_extra_content_or_quality_calls(tmp_path, monkeypatch):
    state=incomplete_state(tmp_path)
    initial=deepcopy(state)
    agent=CompletionBalancer();offline_preparation(monkeypatch,agent)
    result=preparation.source_joint_preparation_node(state)
    assert not result['errors'] and result['joint_candidate']['status']=='verified_feasible'
    assert len(agent.calls)==2  # one completion, one existing no-op quality opportunity
    assert [r['phase'] for r in sample_ledger(result)[1]['charges']]==['capacity','quality']
    replay=preparation.source_joint_preparation_node(initial)
    assert replay['joint_candidate']==result['joint_candidate'] and len(agent.calls)==2


def test_interrupted_completion_cannot_reset_charge_or_resubmit(tmp_path, monkeypatch):
    state=incomplete_state(tmp_path)
    class Interrupted(CompletionBalancer):
        def step(self,message):
            self.calls.append(message)
            raise KeyboardInterrupt('after durable request charge')
    agent=Interrupted();offline_preparation(monkeypatch,agent)
    with pytest.raises(KeyboardInterrupt):preparation.converge(state)
    assert len(sample_ledger(state)[1]['charges'])==1
    with pytest.raises(ValueError,match='charged but missing response'):
        preparation.converge(state)
    assert len(agent.calls)==1 and len(sample_ledger(state)[1]['charges'])==1


def test_optional_key_visual_offer_does_not_reject_an_incomplete_draft(tmp_path):
    from PIL import Image
    from src.workflow.source_document import build_document
    from src.workflow.source_visuals import offer_key_reserve
    state=incomplete_state(tmp_path)
    image=tmp_path/'source.png';Image.new('RGB',(20,20),'white').save(image)
    state['images']={'1':{'path':str(image),'caption':'Shared mechanism'}}
    state['classified_visuals']={'key_visual':'figure_1','method_workflow':['figure_1']}
    state['source_document']=build_document(state)
    candidate=offer_key_reserve(state['source_candidate'],state,allow_missing=True)
    assert any('figure_1' in m['reserve_visual_ids'] for m in candidate['modules'])
    assert editorial.missing_obligations(candidate,state) and not state['verification_passed']


def test_wrong_comparator_is_a_scientific_rejection_even_with_matching_quantities(tmp_path, monkeypatch):
    state=source_state(tmp_path,count=1)
    unit=state['source_document']['units'][0]
    refs=bind_paragraph_refs({'source_refs':[{'source_id':unit['source_id'],
        'paragraph_ids':[unit['paragraphs'][2]['paragraph_id']]}]},state['source_document'])['source_refs']
    candidate=deepcopy(state['source_candidate']);module=candidate['modules'][0]
    module['source_refs']=refs
    module['entries'][0].update(text='The best baseline was evaluated on 16000 properties.',source_refs=refs)
    candidate=editorial.normalize_candidate({'modules':candidate['modules']},state)
    module=candidate['modules'][0]
    assert science.numeric_support(module['entries'][0]['text'],refs)
    verdict=verdict_for(module,state)
    verdict.update(status='contradicted',relationships_supported=False,
        reason='Matching population size does not identify the best baseline.')
    agent=Agent(json.dumps(paragraph_hints(verdict,state['source_document'])))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    with pytest.raises(SourceOutputError,match='best baseline'):
        science.verify_candidate(state,candidate)
    assert len(agent.calls)==1 and 'COMPARATOR CHECK' in agent.calls[0]
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()


@pytest.mark.parametrize('damage',['remove_assignment','false_coverage_summary'])
def test_publication_rechecks_complete_meaning_even_with_rehashed_receipts(tmp_path, monkeypatch, damage):
    state=accept(source_state(tmp_path),monkeypatch)
    report=deepcopy(state['source_verification_report']);report.pop('digest')
    if damage=='remove_assignment':
        for module in state['source_candidate']['modules']:module['obligation_ids']=[]
        for row in report['results']:row['verdict']['obligations']=[]
        report['candidate_digest']=digest(state['source_candidate'])
    report['covered_obligation_ids']=[]
    report['digest']=digest(report)
    state['source_verification_report']=report
    for claim in state['verified_claims']['claims']:claim['source_verification_digest']=report['digest']
    with pytest.raises(ValueError,match='Incomplete indispensable meaning'):
        science.assert_verified(state)
