"""Family constraints in authoring requests, without expanding repair budgets."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import EditorialOutputError, module_limits
from src.workflow.editorial_requests import STRING, STRINGS
from test_editorial_generation import state_for, draft_for, plan_for, prose_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))


def fake_model(monkeypatch, values, bindings=None):
    import utils.langgraph_utils as language
    calls = []
    replies = iter(values)
    last_draft = None

    class Base:
        def bind(self, **kwargs):
            if bindings is not None:
                bindings.append(kwargs)
            return object()

    class Model:
        def __init__(self, *a):
            self.model = Base()
            self.request_policy = object()

        def reset(self):
            pass

        def step(self, message):
            nonlocal last_draft
            calls.append(message)
            if '"phase": "writer"' in message and 'FORMAT CORRECTION:' not in message:
                value = prose_for(last_draft)
            else:
                value = next(replies)
                if 'You are planning an academic poster BEFORE' in message and isinstance(value, dict) and isinstance(value.get('modules'), list) and value['modules']:
                    last_draft = deepcopy(value)
                    value = plan_for(value)
                if 'content_outline' in message and isinstance(value, dict):
                    for field, replacement in value.get('repairs', {}).items():
                        if isinstance(replacement, dict) and isinstance(replacement.get('modules'), list):
                            last_draft = deepcopy(replacement)
                            value['repairs'][field] = plan_for(replacement)
                        elif isinstance(replacement, list) and replacement and isinstance(replacement[0], dict) and 'entries' in replacement[0]:
                            last_draft = {'modules': deepcopy(replacement)}
                            value['repairs'][field] = plan_for(last_draft)['modules']
            return SimpleNamespace(content=json.dumps(value), input_tokens=2, output_tokens=1)

    monkeypatch.setattr(language, 'ChatOpenAI', Base)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    return calls


@pytest.mark.parametrize('family_id', LayoutFamilyRegistry().ids())
def test_every_family_schema_accepts_legal_drafts_and_rejects_foreign_zones(tmp_path, family_id):
    state = state_for(tmp_path, family_id)
    zones = LayoutFamilyRegistry().get(family_id).zones
    schema = pipeline.curator_schema(zones, pipeline.asset_index(state))
    validator = Draft202012Validator(schema)
    raw = draft_for(state)
    assert validator.is_valid(raw)
    assert schema['properties']['modules']['maxItems'] == module_limits(zones)[1]
    assert schema['properties']['modules']['items']['properties']['zone_id']['enum'] == [z['zone_id'] for z in zones]
    # Meaningful underfull initial drafts must still reach same-family merging.
    raw['modules'] = raw['modules'][:1]
    assert validator.is_valid(raw)
    raw['modules'][0]['zone_id'] = 'invented_region'
    assert any(e.validator == 'enum' for e in validator.iter_errors(raw))


def test_schema_isolation_across_families_and_shared_string_nodes():
    before = deepcopy((pipeline.CANDIDATE, pipeline.MODULE, pipeline.PATCH, STRING, STRINGS))
    registry = LayoutFamilyRegistry()
    first = pipeline.curator_schema(registry.get('horizontal_narrative_bands').zones, ['figure_1'])
    second = pipeline.curator_schema(registry.get('small_multiples_matrix').zones, ['table_1'])
    first['properties']['modules']['items']['properties']['zone_id']['enum'].append('not_global')
    assert 'not_global' not in second['properties']['modules']['items']['properties']['zone_id']['enum']
    first['properties']['modules']['items']['properties']['visual_ids']['items']['enum'].append('foreign')
    assert second['properties']['modules']['items']['properties']['visual_ids']['items']['enum'] == ['table_1']
    assert (pipeline.CANDIDATE, pipeline.MODULE, pipeline.PATCH, STRING, STRINGS) == before


def test_actual_request_binds_compatible_schema_and_persists_full_validation(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    bindings = []
    calls = fake_model(monkeypatch, [draft_for(state)], bindings)
    pipeline.editorial_curator_node(state)
    root = Path(state['sample_preparation_dir']) / 'editorial/curator'
    identity = json.loads((root / 'identity.json').read_text())['payload']
    from src.workflow.editorial_authoring import plan_schema
    expected = plan_schema(pipeline.curator_schema(state['editorial_zones'], pipeline.asset_index(state)))
    assert identity['schema'] == expected
    wire = deepcopy(expected)
    del wire['properties']['modules']['items']['properties']['visual_ids']['uniqueItems']
    assert bindings[0]['response_format']['json_schema']['schema'] == wire
    assert expected['properties']['modules']['items']['properties']['visual_ids']['uniqueItems'] is True
    assert bindings[0]['response_format']['json_schema']['strict'] is True
    prompt_schema = json.loads(calls[0].split('\nCOMPLETE OUTPUT JSON SCHEMA:\n')[1])
    assert prompt_schema == expected
    assert len(calls) == 2
    assert [e['phase'] for e in state['editorial_budget']['charges']] == ['curator', 'writer']


def test_seven_band_incident_is_rejected_without_whole_array_repair_or_replay_call(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    raw = draft_for(state)
    for i in range(4, 7):
        module = deepcopy(raw['modules'][0])
        module.update(module_id=f'module_{i}', zone_id=f'band_{i + 1}')
        raw['modules'].append(module)
    schema = pipeline.curator_schema(LayoutFamilyRegistry().get('horizontal_narrative_bands').zones,
                                     pipeline.asset_index(state))
    errors = list(Draft202012Validator(schema).iter_errors(raw))
    assert sum(e.validator == 'maxItems' for e in errors) == 1
    assert sum(e.validator == 'enum' for e in errors) == 3
    calls = fake_model(monkeypatch, [raw])
    for _ in range(2):
        with pytest.raises(EditorialOutputError, match='module count must be in 1..4'):
            pipeline.editorial_curator_node(state)
    root = Path(state['sample_preparation_dir']) / 'editorial/curator'
    assert len(calls) == 1
    assert len(state['editorial_budget']['charges']) == 1
    assert not (root / 'request_01.json').exists()
    assert not (root / 'accepted.json').exists()
    assert not (root / 'repair_plan.json').exists()
    assert not (root.parent.parent / 'editorial_format_correction.json').exists()


def test_unknown_zone_repair_changes_only_that_identifier(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    raw = draft_for(state)
    original = deepcopy(raw)
    raw['modules'][2]['zone_id'] = 'band_7'
    bindings = []
    calls = fake_model(monkeypatch, [raw, {'repairs': {'field_0': 'band_3'}}], bindings)
    pipeline.editorial_curator_node(state)
    assert len(calls) == 3
    assert state['editorial_candidate']['modules'] == original['modules']
    root = Path(state['sample_preparation_dir']) / 'editorial/curator'
    plan = json.loads((root / 'repair_plan.json').read_text())['payload']['plan']
    assert plan['targets'] == [{'path': ['modules', 2, 'zone_id'], 'action': 'replace', 'field': 'field_0'}]
    slot = bindings[1]['response_format']['json_schema']['schema']['properties']['repairs']['properties']['field_0']
    assert slot == {'type': 'string', 'enum': ['band_1', 'band_2', 'band_3', 'band_4']}


def test_merge_request_rebuilds_schema_from_the_actual_merged_zones(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'small_multiples_matrix')
    state['images'] = {'1': {'caption': 'Method with two panels', 'aspect': 2}}
    state['classified_visuals'] = {'key_visual': 'figure_1'}
    initial = draft_for(state)
    initial['modules'] = initial['modules'][:4]
    initial['modules'][0]['visual_ids'] = ['figure_1']
    captured = []

    def respond(st, kind, payload, schema, **kwargs):
        if payload['phase'] == 'writer':
            return prose_for(initial)
        captured.append((deepcopy(payload['family']), deepcopy(schema)))
        raw = deepcopy(initial)
        if payload['phase'] == 'merge':
            for module, zone in zip(raw['modules'], payload['family']['zones']):
                module['zone_id'] = zone['zone_id']
        raw = plan_for(raw)
        assert Draft202012Validator(schema).is_valid(raw)
        return raw

    monkeypatch.setattr(pipeline, 'request', respond)
    pipeline.editorial_curator_node(state)
    assert len(captured) == 2
    for family, schema in captured:
        assert schema['properties']['modules']['maxItems'] == family['maximum_modules']
        assert schema['properties']['modules']['items']['properties']['zone_id']['enum'] == [z['zone_id'] for z in family['zones']]
        assert schema['properties']['modules']['items']['properties']['visual_ids']['items']['enum'] == ['figure_1']
    assert captured[0][1] != captured[1][1]
    assert [e['phase'] for e in state['editorial_budget']['charges']] == ['curator', 'merge', 'writer']


@pytest.mark.parametrize('provider', ['local_text', 'local_vision', 'openai'])
def test_wire_schema_preserves_data_names_and_local_constraints(provider):
    from src.workflow.editorial_requests import wire_schema

    array = {'type': 'array', 'uniqueItems': True, 'maxItems': 2,
             'items': {'type': 'string', 'enum': ['figure_1', 'figure_2']}}
    schema = {
        'type': 'object', 'required': ['uniqueItems'], 'additionalProperties': False,
        'properties': {'uniqueItems': deepcopy(array)},
        '$defs': {'uniqueItems': deepcopy(array)},
        'allOf': [{'properties': {'visual_ids': deepcopy(array)}}],
        'examples': [{'uniqueItems': True}],
        'const': {'uniqueItems': True},
        'enum': [{'uniqueItems': True}],
    }
    before = deepcopy(schema)
    expected = deepcopy(schema)
    if provider.startswith('local_'):
        del expected['properties']['uniqueItems']['uniqueItems']
        del expected['$defs']['uniqueItems']['uniqueItems']
        del expected['allOf'][0]['properties']['visual_ids']['uniqueItems']
    actual = wire_schema(schema, provider)
    assert actual == expected
    assert schema == before
    actual['properties']['uniqueItems']['items']['enum'].append('not_an_asset')
    assert schema == before


@pytest.mark.parametrize('keyword', ['items', 'additionalProperties', 'contains', 'not',
                                      'if', 'then', 'else', 'unevaluatedItems'])
def test_wire_schema_visits_nested_schema_positions(keyword):
    from src.workflow.editorial_requests import wire_schema

    schema = {keyword: {'type': 'array', 'uniqueItems': True, 'items': {'type': 'string'}}}
    expected = {keyword: {'type': 'array', 'items': {'type': 'string'}}}
    assert wire_schema(schema, 'local_text') == expected
    assert wire_schema(False, 'local_text') is False
