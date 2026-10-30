"""Curator owns final visuals; capacity editing never supplements or drops them."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_editorial_generation import state_for, draft_for, install
from src.agents.visual_classification import normalize_visual_classification
from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import (
    EditorialOutputError, EditorialStructureError, normalize_candidate, assert_visual_selection,
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected real model connection'))


def with_visuals(state):
    state['images'] = {'1': {'caption': 'Proposed method architecture', 'aspect': 2},
                       '2': {'caption': 'Primary experimental results', 'aspect': 2},
                       '3': {'caption': 'Ablation comparison', 'aspect': 2}}
    state['classified_visuals'] = {'key_visual': 'figure_1', 'method_workflow': ['figure_1'],
                                   'main_results': ['figure_2'], 'comparative_results': ['figure_3']}
    raw = draft_for(state)
    raw['modules'][-1]['visual_ids'] = ['figure_1', 'figure_2']
    return raw


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_key_required_once_but_not_in_a_fixed_region(tmp_path, family):
    state = state_for(tmp_path, family)
    raw = with_visuals(state)
    zones = LayoutFamilyRegistry().get(family).zones
    candidate = normalize_candidate(raw, state, zones)
    assert candidate['modules'][-1]['visual_ids'] == ['figure_1', 'figure_2']
    raw['modules'][-1]['visual_ids'].remove('figure_1')
    with pytest.raises(EditorialOutputError, match='visibly use'):
        normalize_candidate(raw, state, zones)
    raw['modules'][-1]['visual_ids'].append('figure_1')
    raw['modules'][0]['visual_ids'] = ['figure_1']
    with pytest.raises(EditorialStructureError, match='multiple owners'):
        normalize_candidate(raw, state, zones)


def test_null_key_keeps_result_selection_optional_and_invalid_key_is_not_ignored(tmp_path):
    state = state_for(tmp_path)
    raw = with_visuals(state)
    state['classified_visuals']['key_visual'] = None
    raw['modules'][-1]['visual_ids'] = ['figure_2']
    zones = LayoutFamilyRegistry().get('classic_three_column').zones
    assert normalize_candidate(raw, state, zones)['modules'][-1]['visual_ids'] == ['figure_2']
    state['classified_visuals']['key_visual'] = 'figure_missing'
    with pytest.raises(ValueError, match='actual paper asset'):
        normalize_candidate(raw, state, zones)


@pytest.mark.parametrize('change', ['add', 'drop_optional', 'drop_key', 'replace', 'transfer', 'reorder', 'rename_owner'])
def test_capacity_patch_cannot_change_final_visual_decisions(tmp_path, change):
    state = state_for(tmp_path)
    install(state, with_visuals(state))
    modules = deepcopy(state['editorial_candidate']['modules'])
    owner = modules[-1]
    removed = []
    if change == 'add': owner['visual_ids'].append('figure_3')
    elif change == 'drop_optional': owner['visual_ids'].remove('figure_2')
    elif change == 'drop_key': owner['visual_ids'].remove('figure_1')
    elif change == 'replace': owner['visual_ids'][1] = 'figure_3'
    elif change == 'transfer':
        owner['visual_ids'].remove('figure_2'); modules[0]['visual_ids'] = ['figure_2']
    elif change == 'reorder': owner['visual_ids'].reverse()
    elif change == 'rename_owner':
        removed = [owner['module_id']]; owner['module_id'] = 'new_owner'
    patch = {'modules': modules, 'remove_module_ids': removed, 'module_order': [],
             'narrative_flow': '', 'reason': 'Measured capacity edit'}
    before = deepcopy(state['editorial_candidate'])
    with pytest.raises(EditorialOutputError, match='visual selection|visibly use'):
        pipeline.merge_patch(state, patch)
    assert state['editorial_candidate'] == before


def test_fixed_visuals_still_allow_prose_space_and_module_placement_edits(tmp_path):
    state = state_for(tmp_path)
    install(state, with_visuals(state))
    modules = deepcopy(state['editorial_candidate']['modules'])
    modules[-1]['entries'][0]['text'] += ' More mechanism explanation.'
    modules[-1]['space_weight'] = 3
    modules[0]['zone_id'], modules[-1]['zone_id'] = modules[-1]['zone_id'], modules[0]['zone_id']
    extra = deepcopy(modules[0]); extra['module_id'] = 'extra_explanation'
    modules.append(extra)
    result = pipeline.merge_patch(state, {'modules': modules, 'remove_module_ids': [],
        'module_order': [], 'narrative_flow': 'New grouping, same visual owners.', 'reason': 'Useful expansion'})
    assert len(result['modules']) == 4
    assert result['modules'][2]['space_weight'] == 3
    assert_visual_selection(result, state)


def test_merge_adaptation_finalizes_visuals_only_after_joint_rewriting(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'small_multiples_matrix')
    raw = with_visuals(state)
    raw['modules'] = raw['modules'][:4]
    raw['modules'][0]['visual_ids'] = ['figure_1']
    calls = []
    def response(st, kind, payload, *args, **kwargs):
        calls.append(payload['phase'])
        result = deepcopy(raw)
        if payload['phase'] == 'merge':
            assert not st.get('editorial_visual_selection')
            for module, zone in zip(result['modules'], payload['family']['zones']):
                module['zone_id'] = zone['zone_id']
            result['modules'][0]['visual_ids'] = []
            result['modules'][-1]['visual_ids'] = ['figure_1', 'figure_2']
        return result
    monkeypatch.setattr(pipeline, 'request', response)
    pipeline.editorial_curator_node(state)
    assert calls == ['curator', 'merge']
    assert state['editorial_visual_selection']['owners'] == {'module_3': ['figure_1', 'figure_2']}


def test_missing_key_stops_without_supplementation_or_extra_curator_calls(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    state = state_for(tmp_path)
    raw = with_visuals(state); raw['modules'][-1]['visual_ids'] = ['figure_2']
    calls = []
    class Model:
        def __init__(self, system, config, current, name): assert name == 'source_curator'
        def reset(self): pass
        def step(self, message):
            calls.append(message)
            return SimpleNamespace(content=json.dumps(raw), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    with pytest.raises(EditorialOutputError, match='visibly use'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 1
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator']
    assert not (Path(state['sample_preparation_dir']) / 'editorial_format_correction.json').exists()


def test_retired_probe_schema_and_budget_cannot_be_reactivated(tmp_path):
    state = state_for(tmp_path)
    assert not hasattr(pipeline, 'restore_visuals') and 'visual' not in pipeline.LIMITS
    assert 'reserve_visual_ids' not in pipeline.MODULE['properties']
    with pytest.raises(ValueError, match='Unsupported'):
        pipeline.charge(state, 'visual', 'old_probe')
    raw = draft_for(state); raw['modules'][0]['reserve_visual_ids'] = []
    with pytest.raises(EditorialStructureError, match='Reserve visuals'):
        normalize_candidate(raw, state, LayoutFamilyRegistry().get('classic_three_column').zones)


@pytest.mark.parametrize('caption,expected', [('Main accuracy results', None),
    ('Baseline ablation comparison', None), ('Supplementary explanation', None),
    ('Proposed method architecture', 'figure_1')])
def test_invalid_key_fallback_never_forces_a_result_or_support_figure(caption, expected):
    visuals = [{'id': 'figure_1', 'caption': caption}]
    value, audit = normalize_visual_classification({'key_visual': 'unknown'}, visuals,
                                                  source='model', method_key=True)
    assert value['key_visual'] == expected
    assert audit['key_selection_policy'] == 'core_method_visual_v1'
    legacy, _ = normalize_visual_classification(None, visuals, source='caption_fallback')
    assert legacy['key_visual'] == 'figure_1'


def test_ambiguous_methods_and_explicit_null_are_not_forced():
    visuals = [{'id': f'figure_{i}', 'caption': 'Method architecture'} for i in (1, 2)]
    value, _ = normalize_visual_classification({'key_visual': 'bad'}, visuals, source='model', method_key=True)
    assert value['key_visual'] is None
    value, _ = normalize_visual_classification({'key_visual': None}, visuals[:1], source='model', method_key=True)
    assert value['key_visual'] is None


def test_lone_table_does_not_become_a_mandatory_method_key():
    value, _ = normalize_visual_classification({'key_visual': 'bad'},
        [{'id': 'table_1', 'caption': 'Method performance comparison'}], source='model', method_key=True)
    assert value['key_visual'] is None and value['comparative_results'] == ['table_1']


def test_empty_visual_selection_also_prevents_late_insertion(tmp_path):
    state = install(state_for(tmp_path))
    state['images'] = {'1': {'caption': 'Optional result'}}
    module = deepcopy(state['editorial_candidate']['modules'][0]); module['visual_ids'] = ['figure_1']
    with pytest.raises(EditorialOutputError, match='visual selection'):
        pipeline.merge_patch(state, {'modules': [module], 'remove_module_ids': [],
            'module_order': [], 'narrative_flow': '', 'reason': 'Try to fill whitespace'})


def test_parser_uses_method_policy_and_replays_without_extra_requests(monkeypatch, tmp_path):
    from src.workflow.editorial_parser import classify
    import utils.langgraph_utils as language
    state = state_for(tmp_path)
    calls = []
    class Model:
        def __init__(self, system, config, current, name): assert name == 'parser'
        def reset(self): pass
        def step(self, message):
            calls.append(message)
            assert 'core research innovation' in message and state['raw_text'] in message
            value = {'key_visual': 'figure_missing', 'method_workflow': ['figure_1'],
                     'problem_illustration': [], 'main_results': ['figure_2'],
                     'comparative_results': [], 'supporting': []}
            return SimpleNamespace(content=json.dumps(value), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    figures = {'1': {'caption': 'Proposed architecture'}, '2': {'caption': 'Accuracy results'}}
    value = classify(state, figures, {}, state['raw_text'])
    assert value['key_visual'] == 'figure_1'
    assert state['visual_classification_report']['input_modality'] == 'original_text_captions_and_aspect'
    assert classify(state, figures, {}, state['raw_text']) == value and len(calls) == 1
    calls.clear()
    assert classify(state, {}, {}, state['raw_text'])['key_visual'] is None and not calls


def test_lost_visual_freeze_refuses_capacity_edit_before_request(monkeypatch, tmp_path):
    state = install(state_for(tmp_path))
    state.pop('editorial_visual_selection')
    monkeypatch.setattr(pipeline, 'request', lambda *a, **k: pytest.fail('No request after lost selection'))
    with pytest.raises(EditorialOutputError, match='missing'):
        pipeline.edit(state, None, 'capacity')
