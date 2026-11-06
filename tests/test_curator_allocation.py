"""Every family and merged geometry obeys region quotas with one bounded repair."""
from copy import deepcopy
from itertools import product
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.layout.families import LayoutFamilyRegistry
from src.layout.region_merges import merge_candidates
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import EditorialOutputError, normalize_candidate
from src.workflow.editorial_requests import wire_schema
from test_curator_schema import fake_model
from test_curator_visual_repair import repair_context, journal
from test_editorial_generation import state_for, draft_for


REGISTRY = LayoutFamilyRegistry()
GEOMETRIES = [(f.family_id, 'base', list(f.zones)) for f in (REGISTRY.get(k) for k in REGISTRY.ids())]
GEOMETRIES += [(key, name, zones) for key in REGISTRY.ids()
               for name, zones, _ in merge_candidates(REGISTRY.get(key), REGISTRY.get(key).zones)]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))


def full_draft(state, zones):
    raw = draft_for(state)
    template = raw['modules'][0]
    raw['modules'] = []
    for zone in zones:
        for _ in range(zone['capacity']):
            m = deepcopy(template)
            m.update(module_id=f"m{len(raw['modules'])}", zone_id=zone['zone_id'])
            raw['modules'].append(m)
    raw['core_module_ids'] = [raw['modules'][0]['module_id']]
    return raw


def overfull_draft(state, zones):
    expected = full_draft(state, zones)
    raw = deepcopy(expected)
    # Move the last region's last module into the first region, keeping total legal.
    raw['modules'][-1]['zone_id'] = zones[0]['zone_id']
    raw['narrative_flow'] = 'Incorrect old positions.'
    return raw, expected


def redistribution_wire(raw, expected, source_zone):
    eligible = [i for i, m in enumerate(raw['modules']) if m['zone_id'] == source_zone]
    slots = {f'field_{j}': expected['modules'][i]['zone_id'] for j, i in enumerate(eligible)}
    slots[f'field_{len(eligible)}'] = expected['narrative_flow']
    return {'repairs': slots}


@pytest.mark.parametrize('family_id,label,zones', GEOMETRIES,
                         ids=[f'{f}/{n}' for f, n, _ in GEOMETRIES])
def test_all_base_and_merged_geometries_enforce_local_counts_and_bounded_repair(
        monkeypatch, tmp_path, family_id, label, zones):
    state = state_for(tmp_path, family_id)
    raw, expected = overfull_draft(state, zones)
    schema = pipeline.curator_schema(zones, [])
    validator = Draft202012Validator(schema)
    Draft202012Validator.check_schema(schema)
    assert validator.is_valid(expected)
    errors = list(validator.iter_errors(raw))
    assert [e.validator for e in errors] == ['maxContains']
    # Local servers keep the previous supported grammar, plus quota descriptions.
    remote = wire_schema(schema, 'local_text')
    assert 'allOf' not in remote['properties']['modules']
    assert Draft202012Validator(remote).is_valid(raw)
    assert wire_schema(schema, 'openai') == schema
    calls = fake_model(monkeypatch, [raw, redistribution_wire(raw, expected, zones[0]['zone_id'])])
    result = pipeline._curate(state, zones, 'curator' if label == 'base' else 'merge')
    assert result['modules'] == expected['modules']
    assert result['core_module_ids'] == expected['core_module_ids']
    assert result['narrative_flow'] == expected['narrative_flow']
    context = repair_context(calls[1])
    assert context['allocation']['minimum_moves'] == 1
    assert [(z['zone_id'], z['capacity']) for z in context['allocation']['regions']] == [
        (z['zone_id'], z['capacity']) for z in zones]
    assert len(calls) == 2
    # Replay cannot spend another repair, including before candidate installation.
    assert pipeline._curate(state, zones, 'curator' if label == 'base' else 'merge') == result
    assert len(calls) == 2
    assert len(state['editorial_budget']['charges']) == 1


@pytest.mark.parametrize('family_id', REGISTRY.ids())
def test_schema_all_legal_occupancy_combinations_keep_meaningful_deficits(tmp_path, family_id):
    state = state_for(tmp_path, family_id)
    zones = REGISTRY.get(family_id).zones
    raw = full_draft(state, zones)
    validator = Draft202012Validator(pipeline.curator_schema(zones, []))
    for counts in product(*(range(z['capacity']+1) for z in zones)):
        if not sum(counts):
            continue
        chosen = []
        for z, count in zip(zones, counts):
            chosen += [m for m in raw['modules'] if m['zone_id'] == z['zone_id']][:count]
        candidate = {**raw, 'modules': chosen, 'core_module_ids': []}
        # Schema imposes only upper bounds; independent validator owns minimum use.
        assert validator.is_valid(candidate)
        assert validator.is_valid({**candidate, 'modules': list(reversed(chosen))})


def test_position_repair_preserves_science_assets_core_order_and_ineligible_modules(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'asymmetric_two_column')
    state['images'] = {'1': {'caption': 'Method', 'aspect': 2}, '2': {'caption': 'Result', 'aspect': 1}}
    state['classified_visuals'] = {'key_visual': 'figure_1'}
    zones = REGISTRY.get('asymmetric_two_column').zones
    raw, expected = overfull_draft(state, zones)
    for value in (raw, expected):
        value['modules'][0]['visual_ids'] = ['figure_1']
        value['modules'][-1]['visual_ids'] = ['figure_2']
    calls = fake_model(monkeypatch, [raw, redistribution_wire(raw, expected, zones[0]['zone_id'])])
    pipeline.editorial_curator_node(state)
    assert journal(state, 'accepted.json')['value'] == expected
    plan = journal(state, 'repair_plan.json')['plan']
    assert [t['path'] for t in plan['targets']] == [
        ['modules', 0, 'zone_id'], ['modules', 1, 'zone_id'], ['modules', 3, 'zone_id'], ['narrative_flow']]
    assert all('visual_ids' not in t['path'] and 'entries' not in t['path'] for t in plan['targets'])
    assert state['editorial_visual_selection']['owners'] == {'m0': ['figure_1'], 'm3': ['figure_2']}
    assert len(calls) == 2


@pytest.mark.parametrize('failure', ['unchanged', 'foreign', 'extra_prose', 'extra_modules', 'missing_flow'])
def test_invalid_repairs_stop_and_replay_never_buys_another_call(monkeypatch, tmp_path, failure):
    state = state_for(tmp_path, 'asymmetric_two_column')
    zones = REGISTRY.get('asymmetric_two_column').zones
    raw, expected = overfull_draft(state, zones)
    wire = redistribution_wire(raw, expected, zones[0]['zone_id'])
    if failure == 'unchanged': wire['repairs']['field_2'] = zones[0]['zone_id']
    if failure == 'foreign': wire['repairs']['field_2'] = 'fake_zone'
    if failure == 'extra_prose': wire['repairs']['entries'] = [{'text': 'New unsupported result'}]
    if failure == 'extra_modules': wire['modules'] = expected['modules']
    if failure == 'missing_flow': del wire['repairs']['field_3']
    calls = fake_model(monkeypatch, [raw, wire])
    for _ in range(2):
        with pytest.raises(EditorialOutputError):
            pipeline.editorial_curator_node(state)
    assert len(calls) == 2
    assert not (Path(state['sample_preparation_dir'])/'editorial/curator/accepted.json').exists()
    assert not state.get('editorial_visual_selection')


def test_empty_region_only_repair_opens_surplus_sources_and_flow(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    raw = draft_for(state)
    raw['modules'][2]['zone_id'] = 'left'  # left2/middle1/right0: no upper-bound error.
    expected = draft_for(state)
    calls = fake_model(monkeypatch, [raw, {'repairs': {
        'field_0': 'left', 'field_1': 'right', 'field_2': expected['narrative_flow']}}])
    pipeline.editorial_curator_node(state)
    assert state['editorial_candidate']['modules'] == expected['modules']
    assert repair_context(calls[1])['allocation']['minimum_moves'] == 1
    assert [t['path'] for t in journal(state, 'repair_plan.json')['plan']['targets']] == [
        ['modules', 0, 'zone_id'], ['modules', 2, 'zone_id'], ['narrative_flow']]


def test_legal_but_unnecessary_extra_moves_rejected(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    raw = full_draft(state, REGISTRY.get('classic_three_column').zones)
    raw['modules'] = raw['modules'][:4]
    raw['modules'][2]['zone_id'] = 'left'  # 3/1/0, only one move to right needed.
    # 1/2/1 is legal but moves two modules instead of the necessary one.
    calls = fake_model(monkeypatch, [raw, {'repairs': {
        'field_0': 'left', 'field_1': 'middle', 'field_2': 'right', 'field_3': 'New path.'}}])
    with pytest.raises(EditorialOutputError, match='exactly the necessary'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2


def test_allocation_with_other_schema_errors_never_opens_whole_modules(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'asymmetric_two_column')
    raw, _ = overfull_draft(state, REGISTRY.get('asymmetric_two_column').zones)
    raw['modules'][0]['entries'] = []
    calls = fake_model(monkeypatch, [raw])
    with pytest.raises(EditorialOutputError, match='refusing whole-module'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 1
    assert not (Path(state['sample_preparation_dir'])/'editorial/curator/repair_plan.json').exists()


def test_shared_repair_already_spent_is_not_refunded(monkeypatch, tmp_path):
    from src.workflow.editorial_requests import request, obj, STRING
    state = state_for(tmp_path, 'asymmetric_two_column')
    raw, expected = overfull_draft(state, REGISTRY.get('asymmetric_two_column').zones)
    calls = fake_model(monkeypatch, [{'name': 1}, {'repairs': {'field_0': 'fixed'}}, raw])
    request(state, 'editorial_metadata', {}, obj({'name': STRING}), directory='other/metadata')
    with pytest.raises(EditorialOutputError, match='Shared editorial format correction exhausted'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 3


def test_allocation_repair_consumes_shared_allowance_for_later_requests(monkeypatch, tmp_path):
    from src.workflow.editorial_requests import request, obj, STRING
    state = state_for(tmp_path, 'asymmetric_two_column')
    zones = REGISTRY.get('asymmetric_two_column').zones
    raw, expected = overfull_draft(state, zones)
    calls = fake_model(monkeypatch, [raw, redistribution_wire(raw, expected, zones[0]['zone_id']), {'name': 1}])
    pipeline.editorial_curator_node(state)
    with pytest.raises(EditorialOutputError, match='Shared editorial format correction exhausted'):
        request(state, 'editorial_metadata', {}, obj({'name': STRING}), directory='editorial/later')
    assert len(calls) == 3


def test_joint_occupancy_not_independent_field_enums_decides_repair(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    raw = draft_for(state)
    for m in raw['modules']: m['zone_id'] = 'foreign'
    # All slots individually accept left, but the resulting joint assignment does not.
    calls = fake_model(monkeypatch, [raw, {'repairs': {
        'field_0': 'left', 'field_1': 'left', 'field_2': 'left', 'field_3': 'Invalid.'}}])
    with pytest.raises(EditorialOutputError, match='finite format allowance'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2


def test_merge_uses_remaining_shared_repair_on_actual_geometry(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'small_multiples_matrix')
    initial = draft_for(state)
    initial['modules'] = initial['modules'][:4]
    from src.layout.editorial_layout import family_brief
    captured = []
    import utils.langgraph_utils as language
    from types import SimpleNamespace

    class Model:
        def __init__(self, *a): pass
        def reset(self): pass
        def step(self, message):
            captured.append(message)
            if len(captured) == 1: value = initial
            elif len(captured) == 2:
                payload = json.loads(message.split('\nINPUT:\n')[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:')[0])
                zs = payload['family']['zones']
                value = deepcopy(initial)
                for m, z in zip(value['modules'], zs): m['zone_id'] = z['zone_id']
                # Put a second module in a capacity-one region.
                target = next(z['zone_id'] for z in zs if z['capacity'] == 1)
                donor = next(m for m in value['modules'] if m['zone_id'] != target)
                donor['zone_id'] = target
                self.expected = deepcopy(initial)
                for m, z in zip(self.expected['modules'], zs): m['zone_id'] = z['zone_id']
                self.raw = value
            else:
                context = repair_context(message)
                movable = context['allocation']['movable_module_indices']
                fields = {f'field_{j}': self.expected['modules'][i]['zone_id'] for j, i in enumerate(movable)}
                fields[f'field_{len(movable)}'] = self.expected['narrative_flow']
                value = {'repairs': fields}
            return SimpleNamespace(content=json.dumps(value), input_tokens=1, output_tokens=1)

    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    pipeline.editorial_curator_node(state)
    assert len(captured) == 3
    actual = repair_context(captured[2])['family']
    assert actual == family_brief(state, state['editorial_zones'])
    assert len(actual['zones']) == 4
    assert any(z.get('merged_from') for z in state['editorial_zones'])
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge']


def test_only_known_zone_counter_clauses_are_projected_without_mutating_data():
    from src.workflow.editorial_allocation import zone_count_constraint
    counter = zone_count_constraint({'zone_id': 'a', 'capacity': 2})
    other = {'contains': {'type': 'string'}, 'minContains': 0, 'maxContains': 2}
    schema = {'allOf': [counter, other], 'enum': [{'allOf': [counter]}],
              'properties': {'maxContains': {'type': 'integer'}}}
    before = deepcopy(schema)
    projected = wire_schema(schema, 'local_text')
    assert projected == {**schema, 'allOf': [other]}
    assert schema == before


@pytest.mark.parametrize('family_id', REGISTRY.ids())
def test_total_overflow_is_fatal_for_every_family(monkeypatch, tmp_path, family_id):
    state = state_for(tmp_path, family_id)
    raw = full_draft(state, REGISTRY.get(family_id).zones)
    extra = deepcopy(raw['modules'][0]); extra['module_id'] = 'extra'
    raw['modules'].append(extra)
    calls = fake_model(monkeypatch, [raw])
    with pytest.raises(EditorialOutputError, match='module count must be'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 1
    assert not (Path(state['sample_preparation_dir'])/'editorial_format_correction.json').exists()


def test_multiple_overfull_regions_repaired_jointly_with_minimum_moves(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'four_column_modular')
    zones = REGISTRY.get('four_column_modular').zones
    raw = full_draft(state, zones)
    expected = deepcopy(raw)
    raw['modules'][-1]['zone_id'] = zones[0]['zone_id']
    raw['modules'][-2]['zone_id'] = zones[1]['zone_id']
    # Counts 3/3/2/0 require exactly two moves; either overloaded region can donate.
    movable = [0, 1, 2, 3, 6, 7]
    fields = {f'field_{j}': expected['modules'][i]['zone_id'] for j, i in enumerate(movable)}
    fields['field_6'] = expected['narrative_flow']
    calls = fake_model(monkeypatch, [raw, {'repairs': fields}])
    pipeline.editorial_curator_node(state)
    assert state['editorial_candidate']['modules'] == expected['modules']
    assert repair_context(calls[1])['allocation']['minimum_moves'] == 2


def test_deficit_and_final_balancer_validation_do_not_acquire_new_repair_semantics(tmp_path):
    state = state_for(tmp_path, 'small_multiples_matrix')
    zones = REGISTRY.get('small_multiples_matrix').zones
    raw = draft_for(state); raw['modules'] = raw['modules'][:2]
    assert len(normalize_candidate(raw, state, zones, allow_underfull=True)['modules']) == 2
    with pytest.raises(EditorialOutputError, match='meaningful modules cannot occupy'):
        normalize_candidate(raw, state, zones)
    raw, _ = overfull_draft(state, zones)
    with pytest.raises(EditorialOutputError, match='allocation exceeds region capacity') as exc:
        normalize_candidate(raw, state, zones)
    assert type(exc.value) is EditorialOutputError


def test_position_repair_recovers_after_response_before_acceptance(monkeypatch, tmp_path):
    import src.workflow.editorial_requests as requests
    state = state_for(tmp_path, 'asymmetric_two_column')
    zones = REGISTRY.get('asymmetric_two_column').zones
    raw, expected = overfull_draft(state, zones)
    calls = fake_model(monkeypatch, [raw, redistribution_wire(raw, expected, zones[0]['zone_id'])])
    original_save = requests.save
    def stop(path, value):
        if Path(path).name == 'accepted.json': raise KeyboardInterrupt('receipt boundary')
        original_save(path, value)
    monkeypatch.setattr(requests, 'save', stop)
    with pytest.raises(KeyboardInterrupt): pipeline.editorial_curator_node(state)
    monkeypatch.setattr(requests, 'save', original_save)
    pipeline.editorial_curator_node(state)
    assert state['editorial_candidate']['modules'] == expected['modules']
    assert len(calls) == 2 and len(state['editorial_budget']['charges']) == 1


def test_missing_charged_repair_response_is_not_resubmitted(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'asymmetric_two_column')
    zones = REGISTRY.get('asymmetric_two_column').zones
    raw, expected = overfull_draft(state, zones)
    calls = fake_model(monkeypatch, [raw, redistribution_wire(raw, expected, zones[0]['zone_id'])])
    pipeline.editorial_curator_node(state)
    root = Path(state['sample_preparation_dir'])/'editorial/curator'
    (root/'response_01.json').unlink()
    with pytest.raises(ValueError, match='response missing; refusing resubmission'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2
