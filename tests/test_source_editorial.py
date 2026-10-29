"""Source-driven whole-poster writing, direct proof and image reading boundaries."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from PIL import Image

from src.state.poster_state import ModelConfig, TokenUsage
from src.config.critic_config import load_critic_config
from src.workflow.source_document import (VERSION, SourceOutputError, build_document,
    validate_document, validate_refs, source_material)
from src.workflow.source_editorial import (normalize_candidate, install_candidate, make_board,
    validate_revision, family_material, source_curator_node, source_narrative_node)
from src.workflow.source_requests import SourceRequests, object_schema, BOOL
from src.workflow.source_verification import (targets_for, check_module_verdict, verify_candidate,
                                             assert_verified, numeric_support)
from src.workflow.source_reading import reading_context, check_reading_review
from src.workflow import source_preparation as preparation
from src.workflow.content_contracts import paper_fields, science_ready
from utils.persistence import digest, read_json
from src.workflow.source_document import paragraph_hints


@pytest.fixture(autouse=True)
def no_remote_models(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **kw: pytest.fail('Offline tests must never contact models'))


def source_state(tmp_path, count=4, family='four_column_modular'):
    tmp_path.mkdir(parents=True, exist_ok=True)
    raw = ('# Paper\n\nThe measured method predicts behavior from neural signals under the recorded conditions. '
           '\n\nA shared policy at level-2 learns a common representation across agents.\n\n'
           'The evaluation uses 16000 properties and a 3% to 17% improvement in the reported test setting.\n\n'
           '# Findings\n\nThe original comparison measures accuracy on held-out data, without proving causality.')
    state = {'source_editorial_version': VERSION, 'generation_route': 'optimization_family',
        'raw_text': raw, 'section_chunks': [], 'images': {}, 'tables': {}, 'classified_visuals': {},
        'poster_width': 54, 'poster_height': 36, 'poster_name': 'source_test',
        'narrative_content': {'meta': {'poster_title': 'Synthetic paper', 'authors': ''}},
        'logo_path': '', 'aff_logo_path': '', 'url': '', 'joint_preparation': True,
        'paper_foundation_digest': 'paper', 'source_layout_requests': {'section_to_zone': [], 'variant_id': ''},
        'sample_family': {'family': family}, 'sample_edit_budget_dir': str(tmp_path/'sample'),
        'sample_preparation_dir': str(tmp_path/'sample/preparation'),
        'output_dir': str(tmp_path/'sample/preparation'), 'critic_config': load_critic_config(),
        'iteration_context': {'run_id':'run_source', 'sample_id':'sample_000001', 'iteration':1,
            'random_seed':42,'layout_family':family,'generation_purpose':'explore'},
        'text_model': ModelConfig('fake','local_text'), 'vision_model': ModelConfig('fake','local_vision'),
        'tokens': TokenUsage(), 'errors': [], 'styling_interfaces': {}}
    Path(state['output_dir']).mkdir(parents=True,exist_ok=True)
    state['source_document'] = build_document(state)
    ref = {'source_id': state['source_document']['units'][0]['source_id'],
           'paragraph_ids':[state['source_document']['units'][0]['paragraphs'][1]['paragraph_id']],
           'quote': 'A shared policy at level-2 learns a common representation across agents.'}
    state['source_narrative_plan'] = {'reader_question':'How does shared learning work?',
        'research_story':'Explain a common representation and its measured evaluation.',
        'sections':[{'section_id':'research_method','narrative_role':'method','title_intent':'Shared learning', 'source_refs':[ref]}],
        'obligations':[{'obligation_id':'core','meaning':'The method learns a shared representation.',
                        'rationale':'Core mechanism','source_refs':[ref]}]}
    modules = []
    for i in range(count):
        modules.append({'module_id':f'module_{i}', 'title':f'Shared learning {chr(65+i)}',
            'narrative_role':'results' if i%2 else 'method', 'importance':1 if i%2 else 2,
            'module_purpose':'primary','presentation_style':'plain','reader_question':'How does it work?',
            'communication_goal':'Explain the shared mechanism','source_refs':[ref],
            'obligation_ids':['core'] if i==0 else [],
            'entries':[{'item_id':'idea','text':ref['quote'],'kind':'method','source_refs':[ref],
                        'parent_item_id':'','display_label':'','step_index':0}],
            'visual_ids':[],'reserve_visual_ids':[],'visual_rationale':''})
    install_candidate(state, normalize_candidate({'modules': modules},state))
    return state


def verdict_for(module, state):
    refs = deepcopy(module['source_refs'])
    return {'status':'supported','reason':'Original mechanism supports this explanation.',
        'module_function_supported':True,'relationships_supported':True,'necessary_information_preserved':True,
        'editorial_information_preserved':True,'additions_relevant':True,'additions_nonredundant':True,
        'coverage':[{'target_id':key,'quote':text,'supported':True,'source_refs':refs}
                    for key,text in targets_for(module).items()],
        'obligations':[{'obligation_id':oid,'fully_expressed':True,'meaning_source_supported':True,
                        'target_ids':[module['module_id']+':idea'],'source_refs':refs}
                       for oid in module['obligation_ids']]}


def accept(state, monkeypatch, previous=None):
    import src.workflow.source_verification as science
    monkeypatch.setattr(science, 'request', lambda st, kind, data, schema, **kw: verdict_for(data['module'],st))
    proof = verify_candidate(state, state['source_candidate'], previous=previous)
    install_candidate(state,state['source_candidate'],verified=proof)
    return state


def reading_review(context, routes=None, status='clear'):
    ids = [m['module_id'] for m in context['modules']]
    return {**context['binding'], 'status':status, 'primary_routes': routes if routes is not None else [ids],
        'acceptable_alternatives':[], 'shared_module_ids':[], 'issues':[], 'reason':'Observed grouping gives a clear route.'}


class Agent:
    def __init__(self, *responses): self.responses=iter(responses);self.calls=[]
    def reset(self): pass
    def step(self,prompt):
        self.calls.append(prompt)
        value=next(self.responses)
        if isinstance(value,BaseException): raise value
        return SimpleNamespace(content=value,input_tokens=7,output_tokens=3)


def test_default_chain_has_no_builder_writer_or_old_joint():
    from src.workflow.exploration_runner import default_nodes
    paper, prepare, design=default_nodes()
    assert [n.__name__ for n in paper]==['parser_node']
    assert [n.__name__ for n in prepare]==['editorial_curator_node','editorial_color_node','editorial_title_node','editorial_joint_node']
    assert design[0].__name__=='editorial_compile_node'
    assert not any('evidence' in n.__name__ for stage in (paper,prepare,design) for n in stage)


def test_paper_material_has_no_evidence_permissions_and_retains_whole_source(tmp_path):
    state=source_state(tmp_path)
    fields=paper_fields(state)
    assert 'evidence_bank' not in fields and 'academic_entities' not in fields
    material=source_material(state)
    assert any('level-2' in u['text'] for u in material['units'])
    assert any('without proving causality' in u['text'] for u in material['units'])
    assert len(state['source_document']['units'])>=2
    assert validate_document(fields['source_document'])
    changed=deepcopy(fields['source_document']);changed['units'][0]['text']='Invented'
    with pytest.raises(ValueError,match='digest'):validate_document(changed)
    with pytest.raises(SourceOutputError,match='nonexact'):
        validate_refs([{'source_id':'missing','quote':'fake'}],state['source_document'])


def test_curator_one_whole_call_sees_unrestricted_original_mechanism(monkeypatch,tmp_path):
    import src.workflow.source_editorial as editorial
    state=source_state(tmp_path,count=5)
    calls=[]
    def ask(st,kind,payload,schema,**kw):
        calls.append((kind,payload))
        return {'modules':deepcopy(state['source_candidate']['modules'])}
    monkeypatch.setattr(editorial,'request',ask)
    source_curator_node(state)
    assert len(calls)==1 and calls[0][0]=='source_curator'
    assert len(state['source_candidate']['modules'])==5
    assert any('shared policy' in u['text'] for u in calls[0][1]['source']['units'])
    assert all('evidence_ids' not in c for c in state['poster_claims']['claims'])
    assert not state.get('verification_passed')


def test_direct_source_synthesis_outside_any_old_bank_is_publishable(monkeypatch,tmp_path):
    state=accept(source_state(tmp_path),monkeypatch)
    state['draft_layout_mode']=False
    assert 'evidence_bank' not in state
    assert assert_verified(state,make_board(state))
    assert state['verified_claims']['claims'][0]['text'].startswith('A shared policy')
    assert state['verified_claims']['claims'][0]['source_verification_digest']


@pytest.mark.parametrize('damage',['wrong_quote','missing_slice','unsupported','relationship','module_function','preservation','obligation','fabricated_source'])
def test_scientific_partial_or_negative_verdict_cannot_publish(tmp_path,damage):
    state=source_state(tmp_path);module=state['source_candidate']['modules'][0]
    verdict=verdict_for(module,state)
    if damage=='wrong_quote':verdict['coverage'][0]['quote']='not in candidate'
    elif damage=='missing_slice':verdict['coverage'].pop()
    elif damage=='unsupported':verdict['status']='unsupported'
    elif damage=='relationship':verdict['relationships_supported']=False
    elif damage=='module_function':verdict['module_function_supported']=False
    elif damage=='preservation':verdict['editorial_information_preserved']=False
    elif damage=='obligation':verdict['obligations'][0]['fully_expressed']=False
    elif damage=='fabricated_source':verdict['coverage'][0]['source_refs'][0]['quote']='fake excerpt'
    targets={k:v for m in state['source_candidate']['modules'] for k,v in targets_for(m).items()}
    with pytest.raises(SourceOutputError):
        check_module_verdict(module,verdict,state['source_document'],targets,{'core':{}})


def test_quantities_are_local_but_level_identifier_is_not_measurement():
    assert numeric_support('level-2 policy',[{'quote':'A common policy learns a representation.'}])
    assert numeric_support('3–17%',[{'quote':'3% to 17%'}])
    assert numeric_support('3% to 17%',[{'quote':'3–17%'}])
    assert not numeric_support('3% to 18%',[{'quote':'3–17%'}])
    assert not numeric_support('16000 properties',[{'quote':'An evaluation on 100 properties.'}])
    assert not numeric_support('-17%',[{'quote':'17% improvement'}])


@pytest.mark.parametrize('damage',['title','body','context','source','proof','claim_flag','module_missing'])
def test_final_snapshot_rejects_changed_or_forged_versions(monkeypatch,tmp_path,damage):
    state=accept(source_state(tmp_path),monkeypatch)
    board=make_board(state)
    if damage=='title':board['spatial_content_plan']['sections'][0]['section_title']='Unverified conclusion'
    elif damage=='body':board['spatial_content_plan']['sections'][0]['text_content'][0]='Unsupported improvement'
    elif damage=='context':state['source_candidate']['modules'][0]['entries'].append(deepcopy(state['source_candidate']['modules'][0]['entries'][0]))
    elif damage=='source':state['source_document']['units'][0]['text']='Changed original'
    elif damage=='proof':state['source_verification_report']['results'][0]['verdict']['status']='unsupported'
    elif damage=='claim_flag':state['verified_claims']['claims'][0]['verified']=False
    elif damage=='module_missing':board['spatial_content_plan']['sections'].pop()
    with pytest.raises((ValueError,SourceOutputError)):assert_verified(state,board)


def test_dynamic_split_merge_preserves_meaning_without_fixed_roots(tmp_path):
    state=source_state(tmp_path,count=3)
    before=deepcopy(state['source_candidate'])
    raw={'modules':deepcopy(before['modules'])}
    first,second=raw['modules'][:2]
    second['entries'][0]['item_id']='second_idea'
    first['entries'].extend(second['entries']);raw['modules'].remove(second)
    merged=normalize_candidate(raw,state)
    audit=validate_revision(before,merged,[{'new_module_id':first['module_id'],
        'old_module_ids':[first['module_id'],second['module_id']]}],'Combine explanations; preserve necessary meaning.')
    assert len(audit['old_modules'])==2 and len(audit['new_modules'])==1
    assert len(merged['modules'])==2 and merged['modules'][1]==before['modules'][2]
    with pytest.raises(SourceOutputError,match='two affected'):
        changed=deepcopy(before)
        for module in changed['modules']: module['title']+=' changed'
        validate_revision(before,changed,[],'Rewrite everything')


def test_requests_replay_without_rebilling_and_missing_response_refuses(tmp_path):
    state=source_state(tmp_path);schema=object_schema({'supported':BOOL})
    journal=SourceRequests(state,'source/unit','task',schema)
    agent=Agent('{"supported":true}')
    assert journal.call(agent)['supported'] is True
    assert len(agent.calls)==1 and state['tokens'].input_text==7
    assert journal.call(agent)['supported'] is True
    assert len(agent.calls)==1 and state['tokens'].input_text==7
    (journal.root/'response_00.json').unlink()
    with pytest.raises(ValueError,match='charged but'):journal.call(agent)


def test_schema_recovery_shared_across_stages_and_not_for_negative_science(tmp_path):
    state=source_state(tmp_path);schema=object_schema({'supported':BOOL})
    first=SourceRequests(state,'source/unit_a','task A',schema)
    agent=Agent('{"claim":"echo"}','{"supported":false}')
    assert first.call(agent)['supported'] is False and len(agent.calls)==2
    assert (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()
    second=SourceRequests(state,'source/unit_b','task B',schema)
    next_agent=Agent('{"supported":"true"}')
    with pytest.raises(SourceOutputError,match='exhausted'):second.call(next_agent)
    assert len(next_agent.calls)==1


def test_force_stop_does_not_issue_request(tmp_path):
    from src.workflow.source_document import SourceInterrupted
    state=source_state(tmp_path);state['_force_stop_requested']=lambda:True
    journal=SourceRequests(state,'source/stop','task',object_schema({'supported':BOOL}))
    agent=Agent('{"supported":true}')
    with pytest.raises(SourceInterrupted):journal.call(agent)
    assert not agent.calls and not (journal.root/'request_00.json').exists()


@pytest.mark.parametrize('routes',[[['module_0','module_1','module_2','module_3']],
    [['module_0','module_2','module_1','module_3']],
    [['module_0','module_1'],['module_2','module_3']]])
def test_model_may_choose_column_row_or_parallel_routes(tmp_path,routes):
    state=source_state(tmp_path)
    image=tmp_path/'preview.png';Image.new('RGB',(20,20),'white').save(image)
    context=reading_context(state,make_board({**state,'draft_layout_mode':True}),{'zones':[]},[],image,'draft')
    review=reading_review(context,routes)
    assert check_reading_review(review,context)==review


def test_shared_branch_entry_and_convergence_are_valid(tmp_path):
    state=source_state(tmp_path)
    image=tmp_path/'preview.png';Image.new('RGB',(20,20),'white').save(image)
    context=reading_context(state,make_board({**state,'draft_layout_mode':True}),{'zones':[]},[],image,'draft')
    review=reading_review(context,[['module_0','module_1','module_3'],['module_0','module_2','module_3']])
    review['shared_module_ids']=['module_0','module_3']
    assert check_reading_review(review,context)
    review['shared_module_ids']=[]
    with pytest.raises(SourceOutputError,match='sharing'):check_reading_review(review,context)


@pytest.mark.parametrize('damage',['foreign','missing','duplicate','image','no_image'])
def test_invalid_reading_protocol_never_becomes_clear(tmp_path,damage):
    state=source_state(tmp_path)
    image=tmp_path/'preview.png';Image.new('RGB',(20,20),'white').save(image)
    context=reading_context(state,make_board({**state,'draft_layout_mode':True}),{'zones':[]},[],image,'draft')
    review=reading_review(context)
    if damage=='foreign':review['primary_routes'][0][0]='unknown'
    elif damage=='missing':review['primary_routes'][0].pop()
    elif damage=='duplicate':review['primary_routes'][0].append('module_0')
    elif damage=='image':review['image_digest']='another image'
    elif damage=='no_image':context['has_actual_image']=False
    with pytest.raises(SourceOutputError):check_reading_review(review,context)


def test_old_source_and_role_order_do_not_reorder_or_reject_source_modules(tmp_path):
    from src.layout.design_content import ContentPriorities,apply_reading_flow,flow_conflicts
    from src.layout.reading_flow import reassign_reading
    from src.layout.families import LayoutFamilyRegistry
    state=source_state(tmp_path);state['draft_layout_mode']=True
    board=make_board(state);state['story_board']=board
    sections=board['spatial_content_plan']['sections']
    priorities=ContentPriorities(state,sections)
    family=LayoutFamilyRegistry().get('classic_three_column')
    spec={'zones':[{'zone_id':'left','x':0,'y':0,'section_ids':['module_3','module_0']}],
          'reading_order':['module_0','module_3']}
    original=deepcopy(spec)
    selected={s['section_id']:s for s in sections}
    apply_reading_flow(spec,selected,priorities,family.contract)
    assert spec==original and not flow_conflicts(spec,selected,priorities,family.contract)
    changed,audit=reassign_reading(spec,selected,priorities,family.contract,
        fits=lambda *a:pytest.fail('No old reading search'),pins={},allowed=lambda *a:True)
    assert changed is None and audit['states']==0


def test_physical_source_fit_keeps_dynamic_modules_and_exact_text(tmp_path):
    state=source_state(tmp_path,count=5)
    state['draft_layout_mode']=True
    result,failure=preparation._fit(state,draft=True)
    assert failure is None, failure
    assert len(result[0]['spatial_content_plan']['sections'])==5
    assert {s['section_title'] for s in result[0]['spatial_content_plan']['sections']}=={
        m['title'] for m in state['source_candidate']['modules']}
    assert not state.get('verified_claims')


def test_original_excerpt_locations_map_normalized_whitespace_to_actual_paragraphs(tmp_path):
    from src.workflow.source_document import locate_refs
    state=source_state(tmp_path)
    ref=state['source_candidate']['modules'][0]['source_refs'][0]
    located=locate_refs([ref],state['source_document'])[0]
    unit=next(u for u in state['source_document']['units'] if u['source_id']==ref['source_id'])
    span=located['matches'][0]
    assert unit['text'][span['start']:span['end']]==ref['quote']
    assert span['paragraph_ids'] and located['location_status']=='located'


def test_format_recovery_cannot_rewrite_valid_neighbor_modules(tmp_path):
    from src.workflow.source_editorial import CANDIDATE_SCHEMA
    from src.workflow.source_document import SourceProtocolError
    state=source_state(tmp_path)
    raw={'modules':deepcopy(state['source_candidate']['modules'])}
    raw['modules'][0].pop('reader_question')
    recovered={'modules':deepcopy(state['source_candidate']['modules'])}
    recovered['modules'][1]['entries'][0]['text']='A different neighboring explanation.'
    journal=SourceRequests(state,'source/neighbor_format','task',CANDIDATE_SCHEMA)
    agent=Agent(json.dumps(paragraph_hints(raw,state['source_document'])),json.dumps(paragraph_hints(recovered,state['source_document'])))
    with pytest.raises(SourceProtocolError,match='no remaining'):
        journal.call(agent)
    assert len(agent.calls)==2
    assert (journal.root/'validation_01.json').exists()


def test_protocol_validator_uses_shared_recovery_but_false_support_does_not(tmp_path):
    from src.workflow.source_verification import VERDICT_SCHEMA,validate_verdict_protocol
    state=source_state(tmp_path);module=state['source_candidate']['modules'][0]
    good=verdict_for(module,state);bad=deepcopy(good);bad['coverage'].pop()
    targets={key:value for m in state['source_candidate']['modules'] for key,value in targets_for(m).items()}
    validator=lambda v:validate_verdict_protocol(module,v,state['source_document'],targets)
    journal=SourceRequests(state,'source/partial_proof','task',VERDICT_SCHEMA)
    agent=Agent(json.dumps(paragraph_hints(bad,state['source_document'])),json.dumps(paragraph_hints(good,state['source_document'])))
    assert journal.call(agent,validator)['status']=='supported' and len(agent.calls)==2
    negative=deepcopy(good);negative['status']='unsupported';negative['coverage']=[]
    other=SourceRequests(state,'source/scientific_negative','negative task',VERDICT_SCHEMA)
    next_agent=Agent(json.dumps(paragraph_hints(negative,state['source_document'])))
    assert other.call(next_agent,validator)['status']=='unsupported' and len(next_agent.calls)==1


def test_charged_but_missing_format_request_is_not_resubmitted(tmp_path,monkeypatch):
    state=source_state(tmp_path);schema=object_schema({'supported':BOOL})
    journal=SourceRequests(state,'source/interrupted_correction','task',schema)
    agent=Agent('{"claim":"echo"}')
    original=journal._correction
    def interrupted(prompt):
        original(prompt)
        raise KeyboardInterrupt('after shared correction charge')
    monkeypatch.setattr(journal,'_correction',interrupted)
    with pytest.raises(KeyboardInterrupt):journal.call(agent)
    monkeypatch.setattr(journal,'_correction',original)
    with pytest.raises(ValueError,match='Format correction charged'):
        journal.call(Agent('{"supported":true}'))
