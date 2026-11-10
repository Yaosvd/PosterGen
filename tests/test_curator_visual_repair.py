"""Real asset identifiers and single-owner recovery within one field repair."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import EditorialOutputError
from test_curator_schema import fake_model
from test_editorial_generation import state_for, draft_for, plan_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))


def visual_draft(tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    state['images'] = {'1': {'caption': 'Problem illustration', 'aspect': 2},
                       '2': {'caption': 'Method: panels (a) and (b)', 'aspect': 2}}
    state['tables'] = {'1': {'caption': 'Experimental comparison', 'aspect': 2}}
    state['classified_visuals'] = {'key_visual': 'figure_2'}
    raw = draft_for(state)
    raw['modules'][0]['visual_ids'] = ['figure_1']
    raw['modules'][1]['visual_ids'] = ['figure_2']
    raw['modules'][2]['visual_ids'] = ['figure_2']
    return state, raw


def repair_context(prompt):
    return json.JSONDecoder().raw_decode(prompt.split('REPAIR CONTEXT:\n', 1)[1])[0]


def journal(state, name):
    path = Path(state['sample_preparation_dir']) / 'editorial/curator' / name
    return json.loads(path.read_text())['payload']


@pytest.mark.parametrize('invalid', [['figure_2a'], ['figure_2b'], ['table_2'], ['figure_1', 'figure_1']])
def test_authoring_schema_rejects_nonexistent_assets_and_local_duplicates(tmp_path, invalid):
    state, raw = visual_draft(tmp_path)
    schema = pipeline.curator_schema(LayoutFamilyRegistry().get('horizontal_narrative_bands').zones,
                                     pipeline.asset_index(state))
    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema).is_valid(raw)  # Cross-module ownership remains semantic.
    raw['modules'][1]['visual_ids'] = invalid
    assert not Draft202012Validator(schema).is_valid(raw)


def test_duplicate_figure_repair_has_catalog_and_preserves_every_other_field(monkeypatch, tmp_path):
    state, raw = visual_draft(tmp_path)
    bindings = []
    wire = {'repairs': {'field_0': [], 'field_1': ['figure_2']}}
    calls = fake_model(monkeypatch, [raw, wire], bindings)
    pipeline.editorial_curator_node(state)
    expected = deepcopy(raw)
    expected['modules'][1]['visual_ids'] = []
    assert state['editorial_candidate']['modules'] == expected['modules']
    assert state['editorial_candidate']['narrative_flow'] == raw['narrative_flow']
    assert journal(state, 'accepted.json')['value'] == plan_for(expected)
    context = repair_context(calls[1])
    assert context['available_visual_ids'] == ['figure_1', 'figure_2', 'table_1']
    assert context['key_visual'] == 'figure_2'
    assert context['current_ownership'] == [
        {'module_index': i, 'module_id': m['module_id'], 'visual_ids': m['visual_ids']}
        for i, m in enumerate(raw['modules'])]
    assert 'subpanel' in ' '.join(context['rules']) and 'exactly one module' in ' '.join(context['rules'])
    plan = journal(state, 'repair_plan.json')['plan']
    assert [t['path'] for t in plan['targets']] == [
        ['modules', 1, 'visual_ids'], ['modules', 2, 'visual_ids']]
    slots = bindings[1]['response_format']['json_schema']['schema']['properties']['repairs']['properties']
    for field, slot in slots.items():
        local_slot = plan['schema']['properties']['repairs']['properties'][field]
        assert local_slot['uniqueItems'] is True
        assert slot == {k: v for k, v in local_slot.items() if k != 'uniqueItems'}
        assert slot['items']['enum'] == context['available_visual_ids']
    assert len(calls) == 3 and len(state['editorial_budget']['charges']) == 2
    assert (Path(state['sample_preparation_dir']) / 'editorial_format_correction.json').exists()
    # The charge and original repair prompt stay reproducible after selection freezes.
    pipeline.editorial_curator_node(state)
    assert len(calls) == 3


@pytest.mark.parametrize('bad_wire,error', [
    ({'repairs': {'field_0': [], 'field_1': ['figure_2', 'figure_2']}}, 'Invalid field repair response'),
    ({'repairs': {'field_0': ['figure_2a'], 'field_1': ['figure_2b']}}, 'Invalid field repair response'),
    ({'repairs': {'field_0': ['figure_2'], 'field_1': ['figure_2']}}, 'finite format allowance'),
    ({'repairs': {'field_0': ['figure_1'], 'field_1': ['figure_2']}}, 'finite format allowance'),
    ({'repairs': {'field_0': [], 'field_1': ['figure_2']}, 'modules': []}, 'Invalid field repair response'),
])
def test_bad_repair_never_buys_another_call_or_changes_locked_siblings(monkeypatch, tmp_path, bad_wire, error):
    state, raw = visual_draft(tmp_path)
    calls = fake_model(monkeypatch, [raw, bad_wire])
    for _ in range(2):
        with pytest.raises(EditorialOutputError, match=error):
            pipeline.editorial_curator_node(state)
    assert len(calls) == 2
    assert 'editorial_visual_selection' not in state
    assert journal(state, 'response_00.json')['content'] == json.dumps(plan_for(raw))


@pytest.mark.parametrize('assets', [False, True])
@pytest.mark.parametrize('bad_ids', [['figure_2a'], ['figure_1', 'figure_1']])
def test_invalid_selection_repairs_whole_array_so_it_can_be_empty(monkeypatch, tmp_path, assets, bad_ids):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    if assets:
        state['images'] = {'1': {'caption': 'Optional visual', 'aspect': 2}}
    raw = draft_for(state)
    raw['modules'][1]['visual_ids'] = bad_ids
    calls = fake_model(monkeypatch, [raw, {'repairs': {'field_0': []}}])
    pipeline.editorial_curator_node(state)
    assert len(calls) == 3
    assert state['editorial_candidate']['modules'][1]['visual_ids'] == []
    targets = journal(state, 'repair_plan.json')['plan']['targets']
    assert targets == [{'path': ['modules', 1, 'visual_ids'], 'action': 'replace', 'field': 'field_0'}]
    schema = journal(state, 'identity.json')['schema']
    Draft202012Validator.check_schema(schema)
    if not assets:
        assert schema['properties']['modules']['items']['properties']['visual_ids']['maxItems'] == 0
        assert repair_context(calls[1])['available_visual_ids'] == []


@pytest.mark.parametrize('wrong_type', ['root', 'modules'])
def test_visual_context_survives_wrong_type_initial_draft(monkeypatch, tmp_path, wrong_type):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    expected = draft_for(state)
    raw = None if wrong_type == 'root' else {**deepcopy(expected), 'modules': None}
    replacement = expected if wrong_type == 'root' else expected['modules']
    calls = fake_model(monkeypatch, [raw, {'repairs': {'field_0': replacement}}])
    pipeline.editorial_curator_node(state)
    assert state['editorial_candidate']['modules'] == expected['modules']
    assert len(calls) == 3 and repair_context(calls[1])['current_ownership'] == []
