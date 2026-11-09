"""Plan/geometry/write integration, finite recovery, and real frame equivalence."""
from copy import deepcopy
from pathlib import Path
import json

import pytest
from jsonschema import Draft202012Validator

from test_editorial_generation import state_for, draft_for, plan_for, prose_for
from test_curator_schema import fake_model
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_authoring import (setup_geometry_style, skeleton, writer_schema,
    written_candidate, persist_geometry)
from src.workflow.editorial_contract import EditorialOutputError, EditorialStructureError
from src.layout.authoring_geometry import prepare_geometry, assert_initial_frames, dimensions, problems
from src.layout.editorial_layout import measure
from src.layout.editorial_composition import HORIZONTAL, VERTICAL, initial_fit
from src.layout.families import LayoutFamilyRegistry
from src.layout.measurement_context import measurement_scope
from src.agents.layout_agent import LayoutAgent


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No real model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


def geometry_for(state, draft):
    plan = plan_for(draft)
    setup_geometry_style(state, plan)
    zones = deepcopy(list(LayoutFamilyRegistry().get(state['sample_family']['family']).zones))
    return prepare_geometry(state, skeleton(plan), zones), zones


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_all_family_actual_body_frames_equal_prewrite_frames(tmp_path, family):
    state = state_for(tmp_path, family)
    state['images'] = {'1': {'aspect': 2}}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['figure_1']
    geometry, zones = geometry_for(state, raw)
    assert not geometry['failures']
    state['editorial_authoring_geometry'] = geometry
    candidate = written_candidate(prose_for(raw), plan_for(raw), state, zones)
    result = measure(state, candidate, zones)
    assert_initial_frames(geometry, result)
    # A very long body never chooses a different image size, direction or frame.
    candidate['modules'][0]['entries'][0]['text'] *= 20
    long = measure(state, candidate, zones)
    assert_initial_frames(geometry, long)
    assert long['report']['total_overflow_inches'] > result['report']['total_overflow_inches']


@pytest.mark.parametrize('aspects', [[2], [.5], [2, 1], [.5, .8, 3]])
def test_horizontal_40_percent_cap_stack_aspect_and_return_unused_width(tmp_path, aspects):
    state = state_for(tmp_path, 'central_evidence_band')
    state['images'] = {str(i): {'aspect': a} for i, a in enumerate(aspects)}
    raw = draft_for(state); raw['modules'][2]['visual_ids'] = [f'figure_{i}' for i in range(len(aspects))]
    plan = plan_for(raw); setup_geometry_style(state, plan)
    section = pipeline.make_board(skeleton(plan))['spatial_content_plan']['sections'][2]
    agent = LayoutAgent()
    box = dimensions(agent, section, 20, 10, state, HORIZONTAL)
    inner = 20-2*box['padding']
    assert all(v['width'] <= .4*inner+1e-9 for v in box['visuals'])
    assert box['visual_height'] <= box['content_height']+1e-9
    assert [v['width']/v['height'] for v in box['visuals']] == pytest.approx(aspects)
    gap = max(.3, agent.config['layout']['element_spacing'])
    assert box['text_width'] == pytest.approx(inner-box['visuals'][0]['width']-gap)
    assert box['text_height_available'] == pytest.approx(box['content_height'])
    for first, second in zip(box['visuals'], box['visuals'][1:]):
        assert second['y']-first['y']-first['height'] == pytest.approx(agent.config['layout']['visual_spacing']['below_visual'])
    if aspects == [.5]:
        assert box['visuals'][0]['width'] < .4*inner
        assert box['text_width'] > .6*inner-gap


def test_total_weight_allocation_accounts_for_gap_and_not_just_body(tmp_path):
    state = state_for(tmp_path)
    raw = draft_for(state)
    extra = deepcopy(raw['modules'][0]); extra['module_id'] = 'extra'
    raw['modules'][0]['space_weight'] = 2
    extra['space_weight'] = 1
    raw['modules'].insert(1, extra)
    geometry, zones = geometry_for(state, raw)
    a, b = geometry['frames'][:2]
    assert a['module_frame']['height']/b['module_frame']['height'] == pytest.approx(2)
    assert a['body_frame']['height']/b['body_frame']['height'] != pytest.approx(2)
    state['editorial_authoring_geometry'] = geometry
    candidate = written_candidate(prose_for(raw), plan_for(raw), state, zones)
    assert_initial_frames(geometry, measure(state, candidate, zones))


def test_plan_then_writer_schemas_receipts_and_replay(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'central_evidence_band'); original = deepcopy(state)
    raw = draft_for(state)
    calls = fake_model(monkeypatch, [raw])
    pipeline.editorial_curator_node(state)
    pipeline.editorial_curator_node(original)
    assert len(calls) == 2
    assert original['editorial_candidate'] == state['editorial_candidate']
    assert original['editorial_authoring_geometry'] == state['editorial_authoring_geometry']
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'writer']
    first_schema = json.loads(calls[0].split('\nCOMPLETE OUTPUT JSON SCHEMA:\n')[1])
    props = first_schema['properties']['modules']['items']['properties']
    assert 'entries' not in props and 'content_outline' in props
    payload = json.loads(calls[1].split('\nINPUT:\n')[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:')[0])
    frames = deepcopy(state['editorial_authoring_geometry'])
    for frame in frames['frames']:
        frame.pop('reference')
    assert payload['body_frames'] == frames
    assert 'body_budgets' not in calls[0]
    assert payload['writing_tasks']['modules'][0]['content_guidance']['content_outline']


def test_writer_can_only_change_prose_and_maps_entry_format_paths(tmp_path):
    state = state_for(tmp_path)
    raw = draft_for(state); plan = plan_for(raw)
    schema = writer_schema(plan, pipeline.ENTRY)
    reply = prose_for(raw)
    assert Draft202012Validator(schema).is_valid(reply)
    reply['modules']['module_0']['title'] = 'Changed'
    assert not Draft202012Validator(schema).is_valid(reply)
    del reply['modules']['module_0']['title']
    reply['modules']['module_0']['entries'][1]['parent_item_id'] = 'missing'
    zones = LayoutFamilyRegistry().get('classic_three_column').zones
    with pytest.raises(EditorialStructureError) as error:
        written_candidate(reply, plan, state, zones)
    assert error.value.paths == (('modules', 'module_0', 'entries', 1, 'parent_item_id'),)


def test_impossible_fixed_content_gets_one_replan_and_never_calls_writer(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    state['images'] = {str(i): {'aspect': .5} for i in range(5)}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = [f'figure_{i}' for i in range(5)]
    calls = fake_model(monkeypatch, [raw, raw])
    with pytest.raises(EditorialOutputError, match='infeasible after one adjustment'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge']
    assert (Path(state['sample_preparation_dir'])/'editorial/failed_geometry.json').is_file()
    assert not (Path(state['sample_preparation_dir'])/'editorial/writer').exists()


def test_geometric_replan_can_reallocate_before_writer(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    state['images'] = {str(i): {'aspect': .5} for i in range(5)}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = [f'figure_{i}' for i in range(5)]
    fixed = deepcopy(raw); fixed['modules'][0]['visual_ids'] = ['figure_0']
    calls = fake_model(monkeypatch, [raw, fixed])
    pipeline.editorial_curator_node(state)
    assert len(calls) == 3
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge', 'writer']
    assert not state['editorial_authoring_geometry']['failures']


def test_first_measurement_is_saved_before_geometry_search(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'central_evidence_band')
    raw = draft_for(state)
    fake_model(monkeypatch, [raw]); pipeline.editorial_curator_node(state)
    pipeline.editorial_color_node(state); pipeline.editorial_title_node(state)
    result = initial_fit(state, fitter=measure)
    receipt = json.loads((Path(state['sample_preparation_dir'])/'editorial/composition.json').read_text())['payload']
    assert_initial_frames(state['editorial_authoring_geometry'], receipt['authored_baseline'])
    assert result['layout'] == receipt['authored_baseline']['layout']
    changed = deepcopy(state['editorial_authoring_geometry']); changed['frames'][0]['body_frame']['width'] += 1
    with pytest.raises(ValueError, match='body frame'):
        assert_initial_frames(changed, result)


def test_deleted_geometry_after_writer_charge_cannot_regenerate(monkeypatch, tmp_path):
    state = state_for(tmp_path); original = deepcopy(state)
    calls = fake_model(monkeypatch, [draft_for(state)])
    pipeline.editorial_curator_node(state)
    (Path(state['sample_preparation_dir'])/'editorial/authoring_geometry.json').unlink()
    with pytest.raises(ValueError, match='missing after writer charge'):
        pipeline.editorial_curator_node(original)
    assert len(calls) == 2


@pytest.mark.parametrize('planner_repair', [False, True])
def test_writer_field_repair_uses_the_single_shared_allowance(monkeypatch, tmp_path, planner_repair):
    import utils.langgraph_utils as language
    from types import SimpleNamespace
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    raw = draft_for(state); planned = plan_for(raw)
    invalid_prose = prose_for(raw)
    invalid_prose['modules']['module_0']['entries'][1]['parent_item_id'] = 'missing'
    if planner_repair:
        bad_plan = deepcopy(planned); bad_plan['modules'][0]['zone_id'] = 'unknown'
        replies = [bad_plan, {'repairs': {'field_0': 'band_1'}}, invalid_prose]
    else:
        replies = [planned, invalid_prose, {'repairs': {'field_0': 'main'}}]
    responses = iter(replies); calls = []
    class Model:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            calls.append(message)
            return SimpleNamespace(content=json.dumps(next(responses)), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    if planner_repair:
        with pytest.raises(EditorialOutputError, match='Shared editorial format correction exhausted'):
            pipeline.editorial_curator_node(state)
        assert not (Path(state['sample_preparation_dir'])/'editorial/writer/request_01.json').exists()
    else:
        pipeline.editorial_curator_node(state)
        assert state['editorial_candidate']['modules'] == raw['modules']
        repair = json.loads((Path(state['sample_preparation_dir'])/'editorial/writer/repair_plan.json').read_text())['payload']
        assert repair['plan']['targets'][0]['path'] == ['modules', 'module_0', 'entries', 1, 'parent_item_id']
    assert len(calls) == 3
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'writer']


def test_merged_geometry_cannot_buy_another_replan(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'small_multiples_matrix')
    state['images'] = {str(i): {'aspect': .01} for i in range(7)}
    raw = draft_for(state); raw['modules'] = raw['modules'][:4]
    raw['modules'][0]['visual_ids'] = [f'figure_{i}' for i in range(7)]
    calls = []
    def response(st, kind, payload, schema, **kwargs):
        calls.append(payload['phase'])
        result = plan_for(raw)
        if payload['phase'] == 'merge':
            for module, zone in zip(result['modules'], payload['family']['zones']):
                module['zone_id'] = zone['zone_id']
            # Ensure no available title-free body even after horizontal fallback.
            result['modules'][0]['title'] = 'A\n' * 60
        return result
    monkeypatch.setattr(pipeline, 'request', response)
    with pytest.raises(EditorialOutputError, match='infeasible after one adjustment'):
        pipeline.editorial_curator_node(state)
    assert calls == ['curator', 'merge']


def test_missing_authoring_state_does_not_enable_legacy_layout_after_writer(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    fake_model(monkeypatch, [draft_for(state)]); pipeline.editorial_curator_node(state)
    state.pop('editorial_authoring_geometry')
    with pytest.raises(ValueError, match='missing from a written sample'):
        initial_fit(state, fitter=lambda *a: pytest.fail('Legacy selection after lost authoring geometry'))


@pytest.mark.parametrize('family', ['classic_three_column', 'central_evidence_band'])
def test_multi_image_actual_compilation_matches_frames_and_survives_resize(tmp_path, family):
    state = state_for(tmp_path, family)
    state['images'] = {'1': {'aspect': 2.5}, '2': {'aspect': 1.5}}
    raw = draft_for(state); index = 2 if family == 'central_evidence_band' else 0
    raw['modules'][index]['visual_ids'] = ['figure_1', 'figure_2']
    geometry, zones = geometry_for(state, raw)
    assert not geometry['failures']
    state['editorial_authoring_geometry'] = geometry
    candidate = written_candidate(prose_for(raw), plan_for(raw), state, zones)
    result = measure(state, candidate, zones)
    assert_initial_frames(geometry, result)
    mode = geometry['frames'][index]['body_layout']
    assert mode == (HORIZONTAL if family == 'central_evidence_band' else VERTICAL)
    if mode == HORIZONTAL:
        section = result['board']['spatial_content_plan']['sections'][index]
        from src.layout.module_composition import side_by_side_plan
        for w, h in [(30, 8), (15, 14), (50, 3)]:
            rendered = side_by_side_plan(LayoutAgent(), section, w, h, state)
            assert rendered is not None
            assert max(v['width'] for v in rendered['visuals']) <= .4*(w-.6)+1e-9


def test_geometry_receipt_tampering_is_not_bypassed_by_a_new_snapshot(monkeypatch, tmp_path):
    from src.workflow.editorial_authoring import assert_authoring_receipt
    state = state_for(tmp_path)
    fake_model(monkeypatch, [draft_for(state)]); pipeline.editorial_curator_node(state)
    state['editorial_authoring_geometry']['frames'][0]['body_frame']['width'] += .25
    with pytest.raises(ValueError, match='differs from its original receipt'):
        assert_authoring_receipt(state)
