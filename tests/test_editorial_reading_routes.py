"""Fixed physical routes and nonblocking stage-count/order diagnostics."""
from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest
from jsonschema import Draft202012Validator

from src.layout.families import FAMILIES, LayoutFamilyRegistry
from src.layout.family_contract import ordered_zones
from src.layout.editorial_reading import STAGES, region_order, reading_report
from src.layout.editorial_layout import layout_spec, family_brief
from src.layout.region_merges import merge_candidates, valid_region_membership
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import EditorialOutputError, normalize_candidate
from test_editorial_generation import state_for, draft_for, plan_for, prose_for, install, capacity_reply
from test_editorial_field_repair import model


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('No network'))


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f:f.family_id)
def test_all_routes_variants_and_merges_cover_every_region_once(family):
    geometries = [family.zones]
    if family.geometry_generator:
        geometries += [v[1] for v in family.geometry_generator(family.zones, random_seed=42)]
    for zones in geometries:
        variants = [zones] + [v[1] for v in merge_candidates(family, zones)]
        for actual in variants:
            assert valid_region_membership(family, actual)
            route = region_order(family, actual)
            assert len(route) == len(actual) == len(set(route))
            assert route == [z['zone_id'] for z in ordered_zones(actual, family.contract)]
            ranks = {zid:i for i,zid in enumerate(family.contract.reading_route)}
            expanded = []
            for zid in route:
                zone = next(z for z in actual if z['zone_id'] == zid)
                members = sorted(zone.get('merged_from') or [zid], key=ranks.get)
                expanded += members
            assert expanded == list(family.contract.reading_route)


def test_fixed_mixed_paths_are_not_generic_xy_sorting(tmp_path):
    expected = {
        'method_flow_spine': ['left_top','left_bottom','flow_spine','right_top','right_bottom'],
        'narrative_evidence_grid': ['narrative_rail','evidence_1_1','evidence_1_2','evidence_2_1','evidence_2_2','conclusion'],
        'central_evidence_band': ['top_left','top_right','central_evidence','bottom_left','bottom_middle','bottom_right'],
    }
    for name, ids in expected.items():
        state = state_for(tmp_path/name, name)
        family = LayoutFamilyRegistry().get(name)
        assert family_brief(state, family.zones)['reading_route']['region_order'] == ids
    family = LayoutFamilyRegistry().get('modular_editorial_mosaic')
    brief = family_brief(state_for(tmp_path/'mosaic',family.family_id),family.zones)
    assert brief['reading_route']['region_order'] == [
        'lead', 'upper_right', 'middle_right', 'lower_left', 'lower_middle', 'lower_right']
    assert brief['reading_route']['region_labels']['lead'] == 'lead'
    assert not family.contract.entry_roles and not family.contract.conditional_roles


def wrong_order(state):
    raw = draft_for(state)
    for m,stage in zip(raw['modules'], ['background','method','results','method','method','results']):
        m['narrative_stage'] = stage
    raw['modules'][2], raw['modules'][3] = raw['modules'][3], raw['modules'][2]
    return raw


def test_ec17_style_jump_is_recorded_without_sorting_the_candidate(tmp_path):
    state = state_for(tmp_path,'central_evidence_band'); raw = wrong_order(state)
    family = LayoutFamilyRegistry().get('central_evidence_band')
    before = deepcopy(raw)
    candidate = normalize_candidate(raw,state,family.zones)
    spec = layout_spec(state,candidate,family.zones)
    report = spec['reading_route']
    assert spec['reading_order'] == [f'module_{i}' for i in range(6)]
    assert report['declared_module_order'] == ['module_0','module_1','module_3','module_2','module_4','module_5']
    assert {i['code'] for i in report['issues']} == {'array_route_mismatch','stage_regression'}
    assert candidate['modules'] == raw['modules'] == before['modules']
    assert report['scientific_content_verified'] is False


def test_order_error_reaches_writer_without_replan_format_charge_or_retry(monkeypatch,tmp_path):
    state=state_for(tmp_path,'central_evidence_band'); original=deepcopy(state);raw=wrong_order(state)
    calls=model(monkeypatch,[plan_for(raw),prose_for(raw)])
    pipeline.editorial_curator_node(state)
    pipeline.editorial_curator_node(original)
    assert len(calls)==2
    assert [x['phase'] for x in state['editorial_budget']['charges']]==['curator','writer']
    assert state['editorial_candidate']['modules']==raw['modules']
    root=Path(state['sample_preparation_dir'])/'editorial'
    record=json.loads((root/'curator/reading_order.json').read_text())['payload']
    assert record['reading']['status']=='issues_recorded'
    assert not (root/'merge').exists()
    assert not (root.parent/'editorial_format_correction.json').exists()
    payload=json.loads(calls[1].split('\nINPUT:\n')[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:')[0])
    assert payload['reading_route']['issues']==record['reading']['issues']


@pytest.mark.parametrize('stage,count,maximum', [
    ('background',2,2), ('background',3,2), ('results',3,3), ('results',4,3)])
def test_stage_counts_reach_writer_and_replay_without_extra_requests(monkeypatch,tmp_path,stage,count,maximum):
    state=state_for(tmp_path,'central_evidence_band');raw=draft_for(state)
    for m in raw['modules'][:count]:m['narrative_stage']=stage
    original=deepcopy(state)
    calls=model(monkeypatch,[plan_for(raw),prose_for(raw)])
    pipeline.editorial_curator_node(state)
    pipeline.editorial_curator_node(original)
    assert len(calls)==2
    assert state['editorial_candidate']['modules']==raw['modules']==original['editorial_candidate']['modules']
    assert [c['phase'] for c in state['editorial_budget']['charges']]==['curator','writer']
    root=Path(state['sample_preparation_dir'])/'editorial'
    report=json.loads((root/'curator/reading_order.json').read_text())['payload']['reading']
    issues=[i for i in report['issues'] if i['code']=='narrative_stage_count_exceeded']
    assert issues==([{'code':'narrative_stage_count_exceeded','stage':stage,'actual':count,
                     'maximum':maximum,'module_ids':[m['module_id'] for m in raw['modules'][:count]],
                     'generation_blocking':False}] if count>maximum else [])
    assert not (root/'curator/invalid_00.json').exists()
    assert not (root/'merge').exists() and not (root.parent/'editorial_format_correction.json').exists()
    inputs=[json.loads(c.split('\nINPUT:\n')[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:')[0]) for c in calls]
    assert inputs[1]['reading_route']==report
    route=inputs[0]['family']['reading_route']
    assert route['suggested_modules']=={'background':[1,2],'results':[1,2,3]}
    assert route['maximum_modules_by_stage']=={'background':2,'results':3}
    from utils.langgraph_utils import load_prompt
    template=load_prompt('config/prompts/editorial_curator.txt')
    assert calls[0].startswith(template+'\nINPUT:\n')
    assert 'In the existing reason field, briefly justify why each background and results module' in calls[0]


def test_both_stage_limits_are_recorded_without_changing_modules(tmp_path):
    state=state_for(tmp_path,'four_column_modular');raw=draft_for(state)
    family=LayoutFamilyRegistry().get('four_column_modular')
    for i in range(3):
        extra=deepcopy(raw['modules'][i]);extra['module_id']=f'extra_{i}'
        raw['modules'].append(extra)
    for i,m in enumerate(raw['modules']):m['narrative_stage']='background' if i<3 else 'results'
    before=deepcopy(raw)
    candidate=normalize_candidate(raw,state,family.zones)
    report=reading_report(family,family.zones,candidate['modules'])
    issues=[i for i in report['issues'] if i['code']=='narrative_stage_count_exceeded']
    assert [(i['stage'],i['actual'],i['maximum']) for i in issues]==[('background',3,2),('results',4,3)]
    assert all(i['generation_blocking'] is False for i in issues)
    assert candidate['modules']==raw['modules']==before['modules']
    assert report['status']=='issues_recorded' and report['scientific_content_verified'] is False


@pytest.mark.parametrize('damage',['stage','region','visual','capacity'])
def test_count_advisory_does_not_relax_other_admission_rules(tmp_path,damage):
    state=state_for(tmp_path);raw=draft_for(state)
    for m in raw['modules']:m['narrative_stage']='background'
    if damage=='stage':raw['modules'][0]['narrative_stage']='unknown'
    elif damage=='region':raw['modules'][0]['zone_id']='missing'
    elif damage=='visual':raw['modules'][0]['visual_ids']=['figure_missing']
    else:raw['modules']*=3
    with pytest.raises(EditorialOutputError):
        normalize_candidate(raw,state,LayoutFamilyRegistry().get('classic_three_column').zones)


def test_stages_can_share_regions_and_need_not_have_mandatory_counts(tmp_path):
    state=state_for(tmp_path);family=LayoutFamilyRegistry().get('classic_three_column')
    raw=draft_for(state)
    extra=deepcopy(raw['modules'][0]);extra['module_id']='background';extra['narrative_stage']='background'
    raw['modules'].insert(0,extra)
    raw['modules'][-1]['narrative_stage']='results'
    candidate=normalize_candidate(raw,state,family.zones)
    report=reading_report(family,family.zones,candidate['modules'])
    assert not report['issues']
    assert report['stage_counts']=={'background':1,'method':2,'results':1}
    normalize_candidate(draft_for(state),state,family.zones)  # no fabricated stage quota


@pytest.mark.parametrize('field', ['title','zone_id','narrative_stage','importance','space_weight',
                                   'presentation_style','visual_ids','reader_question'])
def test_capacity_schema_and_receiver_reject_every_metadata_field(tmp_path,field):
    state=install(state_for(tmp_path));before=deepcopy(state['editorial_candidate'])
    raw=capacity_reply([before['modules'][0]])
    raw['modules'][0][field]=before['modules'][0][field]
    assert not Draft202012Validator(pipeline.PATCH).is_valid(raw)
    with pytest.raises(EditorialOutputError,match='only module entries'):
        pipeline.merge_patch(state,raw)
    assert state['editorial_candidate']==before


def test_sparse_capacity_wire_order_does_not_reorder_poster(tmp_path):
    state=install(state_for(tmp_path));before=deepcopy(state['editorial_candidate'])
    changes=deepcopy(before['modules']);changes.reverse()
    for m in changes:m['entries'][0]['text']+=' Useful local explanation.'
    raw=capacity_reply(changes)
    assert Draft202012Validator(pipeline.PATCH).is_valid(raw)
    result=pipeline.merge_patch(state,raw)
    assert [m['module_id'] for m in result['modules']]==[m['module_id'] for m in before['modules']]
    for old,new in zip(before['modules'],result['modules']):
        assert {k:v for k,v in old.items() if k!='entries'}=={k:v for k,v in new.items() if k!='entries'}
    assert result['narrative_flow']==before['narrative_flow']


def test_actual_geometry_route_conflict_is_visible_but_nonblocking(tmp_path):
    state=state_for(tmp_path);family=LayoutFamilyRegistry().get('classic_three_column')
    zones=deepcopy(list(family.zones));zones[0]['x'],zones[2]['x']=zones[2]['x'],zones[0]['x']
    report=layout_spec(state,normalize_candidate(draft_for(state),state,zones),zones)['reading_route']
    assert any(i['code']=='geometry_route_conflict' for i in report['issues'])
    assert report['order_errors']=='record_only_no_retry_or_reordering'


@pytest.mark.parametrize('count_defect',[False,True])
def test_frozen_route_cannot_be_tampered_with_even_if_snapshot_is_resigned(monkeypatch,tmp_path,count_defect):
    from src.layout.editorial_layout import measure
    from src.workflow.editorial_contract import assert_editorial_ready, snapshot_payload
    from utils.persistence import digest
    state=state_for(tmp_path);raw=draft_for(state)
    if count_defect:
        for m in raw['modules']:m['narrative_stage']='background'
    install(state,raw)
    pipeline.charge(state,'curator','offline_fixture')
    monkeypatch.setattr(pipeline,'fit',measure)
    monkeypatch.setattr(pipeline,'edit',lambda *a:False)
    pipeline.editorial_joint_node(state)
    pipeline.editorial_compile_node(state)
    assert_editorial_ready(state,compiled=True)
    if count_defect:
        assert state['layout_spec']['reading_route']['issues'][0]['code']=='narrative_stage_count_exceeded'
        state['layout_spec']['reading_route']['issues']=[]
    else:state['layout_spec']['reading_route']['region_order'].reverse()
    state['editorial_snapshot']['digest']=digest(snapshot_payload(state))
    with pytest.raises(ValueError,match='reading-route diagnostic'):
        assert_editorial_ready(state,compiled=True)
