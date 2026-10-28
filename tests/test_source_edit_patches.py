"""Measured content edits work without images and retain strict publication bounds."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from test_source_editorial import source_state, no_remote_models, Agent
from src.workflow.source_edits import merge_patch, edit_schema, bound_reading
from src.workflow.source_editorial import family_material, install_candidate, normalize_candidate, source_curator_node
from src.workflow.source_document import SourceOutputError, SourceProtocolError, paragraph_hints
from src.workflow.source_space import writing_space, editorial_space
from src.workflow import source_preparation as preparation
from src.workflow.source_requests import SourceRequests
from src.layout.families import LayoutFamilyRegistry
from src.layout.repair_budget import sample_ledger


def patch(state, modules=()):
    return {'modules':deepcopy(list(modules)),'remove_module_ids':[],'module_order':[],
        'lineage':[],'reason':'Compress optional repetition, preserving the shared mechanism.',
        'layout_requests':deepcopy(state['source_layout_requests'])}


def test_curator_receives_compact_current_task_after_complete_original_source(tmp_path,monkeypatch):
    import src.workflow.source_editorial as editorial
    state=source_state(tmp_path,count=4)
    raw=paragraph_hints({'modules':deepcopy(state['source_candidate']['modules'])},state['source_document'])
    agent=Agent(json.dumps(raw))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    editorial.source_curator_node(state)
    assert len(agent.calls)==1
    prefix,tail=agent.calls[0].split('\nCURRENT WRITING TASK:\n',1)
    assert 'without proving causality' in prefix and 'shared policy' in prefix
    payload=json.loads(prefix.split('\nINPUT:\n',1)[1])
    assert len(payload['source']['units'])==len(state['source_document']['units'])
    task=json.loads(tail.split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
    assert task['necessary_meanings']==[{'obligation_id':o['obligation_id'],'meaning':o['meaning']}
                                       for o in state['source_narrative_plan']['obligations']]
    assert {v['variant_id'] for v in task['physical_options']}=={
        v['variant_id'] for v in state['family_capacity']['variants']}
    assert task['body_font_points']>0 and not task['pins_geometry'] and not task['certifies_feasible_layout']
    assert state['source_layout_requests']=={'section_to_zone':[],'variant_id':''}


def test_inplace_provenance_is_program_owned_and_neighbors_are_not_echoed(tmp_path):
    state=source_state(tmp_path)
    before=deepcopy(state['source_candidate'])
    module=deepcopy(before['modules'][0])
    module['entries'][0]['text']='A shared policy learns a common representation across agents.'
    raw=patch(state,[module])
    # Observed redundant identity records for unchanged modules are harmless.
    raw['lineage']=[{'new_module_id':m['module_id'],'old_module_ids':[m['module_id']]}
                    for m in before['modules'][1:]]
    candidate,revision=merge_patch(raw,state)
    assert candidate['modules'][1:]==before['modules'][1:]
    assert revision['lineage']==[{'new_module_id':'module_0','old_module_ids':['module_0']}]
    assert state['source_candidate']==before


def test_split_merge_retains_explicit_transfer_and_never_changes_other_neighbors(tmp_path):
    state=source_state(tmp_path,count=3);before=deepcopy(state['source_candidate'])
    module=deepcopy(before['modules'][0])
    module['entries'].append({**deepcopy(before['modules'][1]['entries'][0]),'item_id':'other'})
    raw=patch(state,[module]);raw['remove_module_ids']=['module_1']
    raw['lineage']=[{'new_module_id':'module_0','old_module_ids':['module_0','module_1']}]
    after,audit=merge_patch(raw,state)
    assert after['modules'][1]==before['modules'][2]
    assert audit['old_modules']==['module_0','module_1'] and audit['deleted_modules']==['module_1']
    raw['lineage'][0]['old_module_ids'].append('module_2')
    with pytest.raises(SourceOutputError,match='lineage'):merge_patch(raw,state)


def test_excessive_content_change_is_not_a_free_format_retry(tmp_path):
    state=source_state(tmp_path)
    rows=deepcopy(state['source_candidate']['modules'][:3])
    for m in rows:m['entries'][0]['text']='A shared policy learns a common representation.'
    raw=patch(state,rows)
    journal=SourceRequests(state,'source/excess_patch','edit',edit_schema(False))
    agent=Agent(json.dumps(paragraph_hints(raw,state['source_document'])))
    with pytest.raises(SourceOutputError,match='two affected'):
        journal.call(agent,lambda value:merge_patch(value,state))
    assert len(agent.calls)==1
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()


@pytest.mark.parametrize('family',LayoutFamilyRegistry().ids())
def test_space_brief_prices_real_variants_without_fixed_module_counts(tmp_path,family):
    state=source_state(tmp_path,count=4,family=family)
    brief=family_material(state);plan=writing_space(state,brief)
    assert len(plan['variants'])==len(brief['variants'])
    assert not plan['certifies_feasible_layout']
    for variant in plan['variants']:
        assert all(z['width_inches']>0 and z['height_inches']>0 for z in variant['zones'])
    measured=editorial_space(state,brief)
    assert not measured['assignment_is_binding'] and not measured['certifies_feasible_layout']
    assert {r['module_id'] for r in measured['modules']}=={m['module_id'] for m in state['source_candidate']['modules']}


def test_capacity_call_actually_edits_prose_without_a_reading_image(tmp_path,monkeypatch):
    state=source_state(tmp_path,count=4)
    raw={'modules':deepcopy(state['source_candidate']['modules'])}
    raw['modules'][0]['entries'][0]['text']='A shared policy learns a common representation across agents. '*30
    install_candidate(state,normalize_candidate(raw,state))
    before=deepcopy(state['source_candidate'])
    class CapacityAgent:
        calls=[]
        def reset(self):pass
        def step(self,message):
            self.calls.append(message)
            data=json.loads(message.split('\nINPUT:\n',1)[1].split('\nCURRENT EDIT TASK (execute on the visible poster, not the paper):',1)[0].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
            assert not data['reading_input']['has_actual_image']
            assert data['editing_space']['suggested_target_module_ids'][0]=='module_0'
            pressure=next(r for r in data['editing_space']['modules'] if r['module_id']=='module_0')
            assert pressure['overage_inches']>0 and pressure['suggested_body_words']<pressure['current_words']
            module=deepcopy(data['whole_candidate']['modules'][0])
            module['entries'][0]['text']='A shared policy learns a common representation across agents.'
            value=patch(state,[module])
            schema=json.loads(message.split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[1])
            assert 'reading_review' not in schema['properties'] and 'candidate' not in schema['properties']
            return SimpleNamespace(content=json.dumps(value),input_tokens=5,output_tokens=5)
    agent=CapacityAgent();monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    state,changed=preparation.edit_candidate(state,{'reason_code':'NO_FAST_FEASIBLE_VARIANT'},'capacity')
    assert changed and len(agent.calls)==1
    assert state['source_candidate']['modules'][1:]==before['modules'][1:]
    assert state['source_reading_review']['status']=='incomplete'
    assert not state['verification_passed'] and len(sample_ledger(state)[1]['charges'])==1
    replay=deepcopy(state);install_candidate(replay,before)
    preparation.edit_candidate(replay,{'reason_code':'NO_FAST_FEASIBLE_VARIANT'},'capacity')
    assert len(agent.calls)==1 and len(sample_ledger(state)[1]['charges'])==1


def test_visual_hashes_are_bound_by_program_and_old_clear_review_is_not_final(tmp_path):
    from test_source_editorial_integration import fake_preview,fake_fit
    state=source_state(tmp_path)
    context=fake_preview(state,fake_fit(state,draft=True)[0])['reading_context']
    schema=edit_schema(True)
    assert 'image_digest' not in schema['properties']['reading_review']['properties']
    raw={'reading_review':{'status':'clear','primary_routes':[[m['module_id'] for m in state['source_candidate']['modules']]],
        'acceptable_alternatives':[],'shared_module_ids':[],'issues':[],'reason':'Actual image assessed.'}}
    review=bound_reading(raw,context)
    assert all(review[k]==v for k,v in context['binding'].items())
    from src.workflow.source_reading import check_reading_review
    assert check_reading_review(review,context)


def test_patch_format_recovery_cannot_rewrite_other_patch_content(tmp_path):
    state=source_state(tmp_path)
    good=paragraph_hints(patch(state,state['source_candidate']['modules'][:2]),state['source_document'])
    bad=deepcopy(good);bad['modules'][0]['entries'][0]['parent_item_id']='unknown'
    changed=deepcopy(good);changed['modules'][1]['entries'][0]['text']='A different scientific assertion.'
    journal=SourceRequests(state,'source/patch_format','edit',edit_schema(False))
    agent=Agent(json.dumps(bad),json.dumps(changed))
    with pytest.raises(SourceProtocolError,match='no remaining'):
        journal.call(agent,lambda value:merge_patch(value,state))
    assert len(agent.calls)==2


def test_required_capacity_action_is_not_a_free_format_recovery(tmp_path,monkeypatch):
    state=source_state(tmp_path)
    raw=patch(state)
    raw['reason']='No-op: a source paragraph already explains the missing meaning.'
    agent=Agent(json.dumps(raw))
    monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    with pytest.raises(SourceOutputError,match='empty patch'):
        preparation.edit_candidate(state,{'missing_indispensable_meanings':[
            {'obligation_id':'core','meaning':'Explain learning and search.'}]},'capacity')
    assert len(agent.calls)==1 and len(sample_ledger(state)[1]['charges'])==1
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()
    prompt=agent.calls[0]
    task=json.loads(prompt.split('\nCURRENT EDIT TASK (execute on the visible poster, not the paper):\n',1)[1]
        .split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
    assert task['must_return_action'] and task['missing_meaning_ids']==['core']
    assert task['current_visible_targets'][0]['entries'][0]['text'] in prompt
    schema=json.loads(prompt.split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[1])
    assert schema['properties']['modules']['minItems']==1
    assert 'minItems' not in edit_schema(False,'quality')['properties']['modules']


def test_writing_edit_measurements_use_the_actual_fitter_safety_factor(tmp_path):
    from src.agents.layout_agent import LayoutAgent
    from src.layout.feasibility import _estimate_section_height
    from src.workflow.source_editorial import make_board
    state=source_state(tmp_path,count=4)
    state['critic_config']['explore_layout']['fast_measurement_safety_factor']=1.3
    plan=editorial_space(state,family_material(state))
    assert plan['measurement_safety_factor']==1.3
    assert writing_space(state,family_material(state))['measurement_safety_factor']==1.3
    agent=LayoutAgent();view={**state,'draft_layout_mode':True}
    sections={s['section_id']:s for s in make_board(view)['spatial_content_plan']['sections']}
    for row in plan['modules']:
        expected=_estimate_section_height(agent,sections[row['module_id']],zone_width=row['width_inches'],
            zone_height=row['zone_limit_inches'],state=view)
        assert row['module_used_inches']==pytest.approx(expected,abs=.005)


def test_actual_failed_fit_targets_survive_a_provisional_all_clear(tmp_path):
    from src.workflow.source_edits import edit_task
    state=source_state(tmp_path)
    feedback={'reason_code':'NO_FAST_FEASIBLE_VARIANT','pressure':[
        {'section_id':'module_0','estimated_used_in':31.886,'zone_limit_in':18.68},
        {'section_id':'module_0','estimated_used_in':19.403,'zone_limit_in':18.68}]}
    task=edit_task(state,feedback,'capacity',{'suggested_target_module_ids':[],'modules':[]})
    assert task['actual_fit_failed'] and task['must_return_action']
    target=task['current_visible_targets'][0]
    assert target['module_id']=='module_0'
    assert target['observed_failed_fit_pressure']['estimated_used_in']==19.403
    assert target['suggested_body_words']<target['current_words']
    assert 'authoritative' in task['instruction']


def test_capacity_edit_cannot_pin_a_provisional_geometry_variant(tmp_path):
    from jsonschema import Draft202012Validator
    state=source_state(tmp_path)
    raw=paragraph_hints(patch(state,state['source_candidate']['modules'][:1]),state['source_document'])
    raw['layout_requests']['variant_id']=family_material(state)['variants'][0]['variant_id']
    errors=list(Draft202012Validator(edit_schema(False,'capacity')).iter_errors(raw))
    assert any(list(e.absolute_path)==['layout_requests','variant_id'] for e in errors)
    raw['layout_requests']['variant_id']=''
    assert not list(Draft202012Validator(edit_schema(False,'capacity')).iter_errors(raw))


def test_verified_final_refit_keeps_string_visual_ids_and_actual_geometry(tmp_path,monkeypatch):
    from PIL import Image
    from src.workflow.source_document import build_document
    from test_source_editorial import accept
    from src.workflow.source_verification import assert_verified
    state=source_state(tmp_path,count=4)
    state['critic_config']['explore_layout'].update(max_geometry_candidates_per_family=2,
        max_adaptive_geometry_candidates=2,max_exact_candidates=2)
    state['critic_config']['composition_refinement']['enabled']=False
    image=tmp_path/'original_figure.png';Image.new('RGB',(800,360),'navy').save(image)
    state['images']={'1':{'path':str(image),'aspect':800/360,'caption':'Shared learning'}}
    state['source_document']=build_document(state)
    raw={'modules':deepcopy(state['source_candidate']['modules'])}
    raw['modules'][0]['visual_ids']=['figure_1']
    install_candidate(state,normalize_candidate(raw,state))
    draft,failure=preparation._fit(state,draft=True)
    assert failure is None
    state=preparation.align_selected_visuals(state,draft)
    assert any(m['visual_ids'] for m in state['source_candidate']['modules'])
    accept(state,monkeypatch)
    final,failure=preparation._fit(state,draft=False,physical_baseline=draft)
    assert failure is None and assert_verified(state,final[0])
    def geometry_and_owners(spec):
        return {z['zone_id']:([z[k] for k in ('x','y','width','height')],set(z.get('section_ids',[])))
                for z in spec['zones']}
    assert geometry_and_owners(final[1])==geometry_and_owners(draft[1])
    assert {v['visual_id'] for s in final[0]['spatial_content_plan']['sections'] for v in s['visual_assets']}=={'figure_1'}
