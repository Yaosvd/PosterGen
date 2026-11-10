"""Priority ownership, finite format repair, and space-first writing contracts."""
from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator

from test_editorial_generation import state_for, draft_for, plan_for, prose_for, install
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_authoring import (
    plan_schema, normalize_plan, content_guidance, writing_payload, written_candidate,
    setup_geometry_style, skeleton)
from src.workflow.editorial_contract import EditorialOutputError, EditorialStructureError
from src.workflow.editorial_format import repair_plan, apply_repair
from src.workflow.editorial_requests import wire_schema
from src.layout.authoring_geometry import prepare_geometry
from src.layout.families import LayoutFamilyRegistry
from src.layout.editorial_layout import measure
from src.workflow.editorial_writing import capacity_tasks
from src.layout.measurement_context import measurement_scope


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No real model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


def planned(tmp_path):
    state = state_for(tmp_path)
    raw = draft_for(state); plan = plan_for(raw)
    zones = list(LayoutFamilyRegistry().get(state['sample_family']['family']).zones)
    plan['modules'][0]['content_outline'][0]['required_conditions'] = ['Under the stated resource limit.']
    schema = plan_schema(pipeline.curator_schema(zones, []))
    return state, raw, plan, zones, schema


def test_structured_priorities_are_closed_and_preserve_condition_ownership(tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    before = deepcopy(plan)
    Draft202012Validator(schema).validate(plan)
    assert normalize_plan(plan, state, zones) == before
    wire = wire_schema(schema, 'local_text')
    assert (wire['properties']['modules']['items']['properties']['content_outline'] ==
            schema['properties']['modules']['items']['properties']['content_outline'])
    bad = deepcopy(plan); bad['modules'][0]['content_outline'] = ['Legacy free text']
    assert not Draft202012Validator(schema).is_valid(bad)
    bad = deepcopy(plan); bad['modules'][0]['content_outline'][0]['conditions_for_other_point'] = []
    assert not Draft202012Validator(schema).is_valid(bad)
    assert skeleton(plan)['modules'] == [{**m, 'entries': []} for m in raw['modules']]
    assert plan == before


def test_core_selection_is_not_bought_with_format_repair(monkeypatch, tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    for point in plan['modules'][0]['content_outline']:
        point['priority'] = 'optional'
    from types import SimpleNamespace
    import utils.langgraph_utils as language
    calls = []
    class Model:
        def __init__(self, *a): pass
        def reset(self): pass
        def step(self, prompt):
            calls.append(prompt)
            return SimpleNamespace(content=json.dumps(plan), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    with pytest.raises(EditorialOutputError, match='core content point'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge']
    from pathlib import Path
    assert not (Path(state['sample_preparation_dir'])/'editorial_format_correction.json').exists()


def test_duplicate_point_id_repairs_only_identifier_not_statement_or_conditions(tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    point = plan['modules'][0]['content_outline'][1]
    point['point_id'] = plan['modules'][0]['content_outline'][0]['point_id']
    with pytest.raises(EditorialStructureError) as error:
        normalize_plan(plan, state, zones)
    assert error.value.paths == (('modules', 0, 'content_outline', 1, 'point_id'),)
    scope = repair_plan(plan, schema, error.value.paths)
    fixed = apply_repair(plan, {'repairs': {'field_0': 'detail'}}, scope)
    expected = deepcopy(plan); expected['modules'][0]['content_outline'][1]['point_id'] = 'detail'
    assert fixed == expected
    assert normalize_plan(fixed, state, zones) == expected


@pytest.mark.parametrize('field', ['statement', 'required_conditions'])
def test_whitespace_content_is_not_valid_planning(tmp_path, field):
    state, raw, plan, zones, schema = planned(tmp_path)
    plan['modules'][0]['content_outline'][0][field] = ['   '] if field == 'required_conditions' else ' '
    with pytest.raises(EditorialStructureError):
        normalize_plan(plan, state, zones)


def test_guidance_follows_ids_after_reordering_and_does_not_transfer_deleted_plan(tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    first = content_guidance(plan, 'module_0')
    plan['modules'].reverse()
    assert content_guidance(plan, 'module_0') == first
    assert content_guidance(plan, 'new_merged_id') == {
        'source_module_id': 'new_merged_id', 'status': 'not_planned', 'content_outline': []}
    assert content_guidance(None, 'module_0')['status'] == 'not_planned'
    first['content_outline'][0]['required_conditions'].clear()
    assert content_guidance(plan, 'module_0')['content_outline'][0]['required_conditions']


def test_space_first_payload_has_one_reference_and_outline_and_full_paper(tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    setup_geometry_style(state, plan)
    geometry = prepare_geometry(state, skeleton(plan), zones)
    original = deepcopy((plan, geometry))
    payload = writing_payload(state, plan, geometry)
    assert list(payload)[:2] == ['phase', 'writing_tasks']
    assert list(payload).index('paper') > list(payload).index('writing_tasks')
    assert json.dumps(payload).count('"reference_words"') == len(plan['modules'])
    assert json.dumps(payload).count('"content_outline"') == len(plan['modules'])
    assert payload['paper'] == pipeline.paper_material(state)
    assert payload['writing_tasks']['font']['font_size_pt'] == geometry['calibration']['font_size_pt']
    for task, frame in zip(payload['writing_tasks']['modules'], geometry['frames']):
        assert task['body_frame'] == frame['body_frame']
        assert task['reference_words'] == frame['reference']['reference_words']
    assert (plan, geometry) == original
    geometry['frames'].pop()
    with pytest.raises(EditorialOutputError, match='every actual body frame'):
        writing_payload(state, plan, geometry)


def test_writer_does_not_truncate_or_rewrite_frozen_metadata(tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    prose = prose_for(raw)
    prose['modules']['module_0']['entries'][0]['text'] *= 40
    candidate = written_candidate(prose, plan, state, zones)
    assert candidate['modules'][0]['entries'] == prose['modules']['module_0']['entries']
    for m, source in zip(candidate['modules'], raw['modules']):
        assert {k:v for k,v in m.items() if k != 'entries'} == {k:v for k,v in source.items() if k != 'entries'}


def test_capacity_priorities_keep_actual_budget_and_match_by_module_id(tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    state = install(state, raw)
    result = measure(state, state['editorial_candidate'], zones)
    old = capacity_tasks(result)
    plan['modules'].reverse()
    tasks = capacity_tasks(result, plan)
    for task, baseline in zip(tasks['modules'], old['modules']):
        assert task['reference_words'] == baseline['reference_words']
        assert task['action'] == baseline['action']
        assert task['content_guidance'] == content_guidance(plan, task['module_id'])
    assert tasks['modules'][0]['content_guidance']['content_outline'][0]['required_conditions']


def test_priority_identifier_repair_uses_shared_request_allowance(monkeypatch, tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    plan['modules'][0]['content_outline'][1]['point_id'] = 'main'
    from types import SimpleNamespace
    import utils.langgraph_utils as language
    calls = []
    replies = iter([plan, {'repairs': {'field_0': 'support'}}, prose_for(raw)])
    class Model:
        def __init__(self, *a): pass
        def reset(self): pass
        def step(self, prompt):
            calls.append(prompt)
            return SimpleNamespace(content=json.dumps(next(replies)), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    pipeline.editorial_curator_node(state)
    assert len(calls) == 3
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'writer']
    points = state['editorial_plan']['modules'][0]['content_outline']
    assert points[1]['point_id'] == 'support'
    assert points[0]['required_conditions'] == ['Under the stated resource limit.']
    assert state['editorial_candidate']['modules'] == raw['modules']
    repair = json.loads(calls[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:\n')[1])
    assert list(repair['properties']['repairs']['properties']) == ['field_0']
    assert repair['properties']['repairs']['properties']['field_0']['type'] == 'string'


def test_capacity_request_orders_single_worklist_before_unchanged_source(tmp_path):
    state, raw, plan, zones, schema = planned(tmp_path)
    state = install(state, raw)
    from src.layout.editorial_composition import initial_fit
    result = initial_fit(state, fitter=measure)
    state['editorial_plan'] = plan
    before = deepcopy(plan)
    payload = pipeline.capacity_payload(state, result)
    assert list(payload)[:2] == ['phase', 'capacity_tasks']
    assert payload['paper'] == pipeline.paper_material(state)
    assert payload['whole_poster'] == state['editorial_candidate']
    assert json.dumps(payload).count('"reference_words"') == len(raw['modules'])
    assert json.dumps(payload).count('"content_outline"') == len(raw['modules'])
    assert 'geometry_trials' not in payload['measurements']
    assert plan == before
