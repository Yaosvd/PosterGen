"""Writer-owned headings, one-line budgets and actual wrapped capacity geometry."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from test_editorial_generation import state_for, draft_for, plan_for, prose_for, capacity_reply
from test_editorial_field_repair import model
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_authoring import plan_schema, writer_schema, written_candidate
from src.workflow.editorial_contract import EditorialStructureError
from src.layout.authoring_geometry import assert_initial_frames
from src.layout.editorial_composition import initial_fit
from src.layout.editorial_layout import measure
from src.layout.families import LayoutFamilyRegistry
from src.layout.measurement_context import measurement_scope

LONG_TITLE = 'Experimental evaluation of prediction accuracy and computational efficiency across multiple resource constrained search benchmarks'


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No real model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


def test_title_ownership_is_closed_in_both_model_schemas(tmp_path):
    state = state_for(tmp_path); raw = draft_for(state); plan = plan_for(raw)
    zones = LayoutFamilyRegistry().get(state['sample_family']['family']).zones
    schema = plan_schema(pipeline.curator_schema(zones, []))
    Draft202012Validator(schema).validate(plan)
    assert all('title' not in m for m in plan['modules'])
    wrong = deepcopy(plan); wrong['modules'][0]['title'] = 'Early title'
    assert not Draft202012Validator(schema).is_valid(wrong)
    reply = prose_for(raw); reply['modules']['module_0']['title'] = 'New heading'
    Draft202012Validator(writer_schema(plan, pipeline.ENTRY)).validate(reply)
    actual = written_candidate(reply, plan, state, zones)
    assert actual['modules'][0]['title'] == 'New heading'
    for field in ('space_weight', 'zone_id', 'visual_ids', 'narrative_stage'):
        bad = deepcopy(reply); bad['modules']['module_0'][field] = raw['modules'][0][field]
        assert not Draft202012Validator(writer_schema(plan, pipeline.ENTRY)).is_valid(bad)
    del reply['modules']['module_0']['title']
    assert not Draft202012Validator(writer_schema(plan, pipeline.ENTRY)).is_valid(reply)


@pytest.mark.parametrize('title', [' ', 'x' * 161])
def test_invalid_title_maps_to_existing_writer_field_repair(tmp_path, title):
    state = state_for(tmp_path); raw = draft_for(state); reply = prose_for(raw)
    reply['modules']['module_0']['title'] = title
    with pytest.raises(EditorialStructureError) as error:
        written_candidate(reply, plan_for(raw), state, LayoutFamilyRegistry().get('classic_three_column').zones)
    assert error.value.paths == (('modules', 'module_0', 'title'),)


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_wrapped_writer_titles_recompute_all_family_frames_without_extra_call(monkeypatch, tmp_path, family):
    state = state_for(tmp_path, family)
    state['images'] = {'1': {'aspect': 2}, '2': {'aspect': 1}}
    raw = draft_for(state)
    raw['modules'][0]['visual_ids'] = ['figure_1', 'figure_2']
    for module in raw['modules']:
        module['title'] = LONG_TITLE
    original = deepcopy(state)
    calls = model(monkeypatch, [plan_for(raw), prose_for(raw)])
    pipeline.editorial_curator_node(state)
    pipeline.editorial_curator_node(original)
    assert len(calls) == 2
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'writer']
    assert state['editorial_candidate'] == original['editorial_candidate']
    budget = deepcopy(state['editorial_authoring_geometry'])
    assert budget['title_basis'] == 'single_line_reservation'
    assert len({r['title_and_gap_height'] for r in budget['frames']}) == 1
    assert all('title' not in m for m in state['editorial_plan']['modules'])
    writer_input = json.loads(calls[1].split('\nINPUT:\n')[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:')[0])
    assert all('title' not in m for m in writer_input['writing_tasks']['modules'])
    assert 'Untitled' not in json.dumps(writer_input)
    pipeline.editorial_color_node(state); pipeline.editorial_title_node(state)
    before_fit = deepcopy(state)
    result = initial_fit(state, fitter=measure)
    record = json.loads((Path(state['sample_preparation_dir'])/'editorial/composition.json').read_text())['payload']
    actual = record['authored_geometry']
    assert actual['title_basis'] == 'actual_title'
    assert actual['modules'] == budget['modules']
    assert_initial_frames(actual, result)
    assert state['editorial_authoring_geometry'] == budget
    for reserved, measured in zip(budget['frames'], actual['frames']):
        assert measured['module_frame'] == reserved['module_frame']
        assert measured['title_and_gap_height'] > reserved['title_and_gap_height']
        if not measured['visuals']:
            assert measured['body_frame']['height'] < reserved['body_frame']['height']
        # With images, shrinking/row selection can recover more space than the
        # extra title line consumes; the actual shared geometry remains authoritative.
    tasks = pipeline.capacity_payload(state, result)['capacity_tasks']['modules']
    for task, row in zip(tasks, actual['frames']):
        assert task['available_body_height_inches'] == pytest.approx(row['body_frame']['height'])
    assert initial_fit(before_fit, fitter=lambda *a: pytest.fail('Replayed search')) == result
    assert len(calls) == 2


def test_wrapped_title_survives_capacity_and_final_compilation(monkeypatch, tmp_path):
    state = state_for(tmp_path, 'central_evidence_band')
    raw = draft_for(state)
    raw['modules'][2]['title'] = LONG_TITLE
    raw['modules'][2]['entries'][0]['text'] *= 150
    replacement = deepcopy(raw['modules'][2])
    replacement['entries'][0]['text'] = state['raw_text']
    calls = model(monkeypatch, [plan_for(raw), prose_for(raw), capacity_reply([replacement])])
    pipeline.editorial_curator_node(state)
    pipeline.editorial_color_node(state); pipeline.editorial_title_node(state)
    pipeline.editorial_joint_node(state)
    pipeline.editorial_compile_node(state)
    assert len(calls) == 3
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'writer', 'capacity']
    assert state['editorial_candidate']['modules'][2]['title'] == LONG_TITLE
    assert state['editorial_candidate']['modules'][2]['entries'] == replacement['entries']
    assert [e['section_title'] for e in state['design_layout']
            if e['type'] == 'section_title' and e['section_id'] == 'module_2'] == [LONG_TITLE]
    request = json.loads(calls[2].split('\nINPUT:\n')[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:')[0])
    task = next(t for t in request['capacity_tasks']['modules'] if t['module_id'] == 'module_2')
    assert task['action'] == 'compress'
    assert task['available_body_height_inches'] != pytest.approx(
        state['editorial_authoring_geometry']['frames'][2]['body_frame']['height'])


def test_title_field_repair_changes_only_title_and_reuses_existing_allowance(monkeypatch, tmp_path):
    state = state_for(tmp_path); raw = draft_for(state); bad = prose_for(raw)
    bad['modules']['module_0']['title'] = ' '
    calls = model(monkeypatch, [plan_for(raw), bad, {'repairs': {'field_0': 'Shared method'}}])
    pipeline.editorial_curator_node(state)
    assert len(calls) == 3
    assert state['editorial_candidate']['modules'] == raw['modules']
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'writer']
    correction = json.loads((Path(state['sample_preparation_dir'])/'editorial/writer/repair_plan.json').read_text())['payload']
    assert correction['plan']['targets'][0]['path'] == ['modules', 'module_0', 'title']


def test_wrapped_writer_titles_reach_real_pptx_png_and_publication_recovery(monkeypatch, tmp_path):
    import test_editorial_generation as generation
    from pptx import Presentation
    original_draft = generation.draft_for
    def with_wrapped_titles(state):
        raw = original_draft(state)
        for module in raw['modules']:
            module['title'] = LONG_TITLE
        return raw
    monkeypatch.setattr(generation, 'draft_for', with_wrapped_titles)
    generation.test_default_runner_real_compile_render_critic_and_publication(
        monkeypatch, tmp_path, evaluation_failure=False, publication_crash=True,
        layout_defects=False, horizontal=False)
    posters = list(tmp_path.rglob('poster.pptx'))
    assert posters
    for path in posters:
        deck = Presentation(path)
        assert any(LONG_TITLE in shape.text for slide in deck.slides
                   for shape in slide.shapes if shape.has_text_frame)
        assert path.with_suffix('.png').is_file()
