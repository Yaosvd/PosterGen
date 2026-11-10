"""Positive small frames reach writing; impossible frames and frozen rules remain guarded."""
from copy import deepcopy
import json

import pytest

from src.agents.layout_agent import LayoutAgent
from src.layout import authoring_geometry as geometry
from src.layout.editorial_composition import HORIZONTAL, VERTICAL
from src.layout.editorial_layout import measure
from src.layout.measurement_context import measurement_scope
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_authoring import setup_geometry_style, skeleton
from test_curator_schema import fake_model
from test_editorial_generation import state_for, draft_for, plan_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No real model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


@pytest.mark.parametrize('mode', [VERTICAL, HORIZONTAL])
@pytest.mark.parametrize('width,height', [(1e-8, 1e-8), (3, .5), (6.11110, 2.14999)])
def test_positive_body_has_no_font_or_reference_line_minimum(mode, width, height):
    box = {'mode': mode, 'visuals': [], 'title_height': 1, 'visual_height': 0,
           'text_y': 1, 'text_width': width, 'text_height_available': height}
    assert geometry.problems(box) == []


@pytest.mark.parametrize('field,issue', [('text_width', 'invalid_body_width'),
                                       ('text_height_available', 'invalid_body_height')])
@pytest.mark.parametrize('value', [0, -.01, float('inf'), float('-inf'), float('nan')])
def test_nonpositive_or_nonfinite_dimensions_are_not_accepted(field, issue, value):
    box = {'mode': HORIZONTAL, 'visuals': [], 'title_height': 1, 'visual_height': 0,
           'text_y': 1, 'text_width': 10, 'text_height_available': 5}
    box[field] = value
    assert issue in geometry.problems(box)


def test_horizontal_fixed_stack_overflow_is_still_rejected():
    box = {'mode': HORIZONTAL, 'visuals': [{'height': 3}], 'title_height': 1,
           'visual_height': 3, 'text_y': 1, 'text_width': 10, 'text_height_available': 2}
    assert geometry.problems(box) == ['fixed_content_overflow']


@pytest.mark.parametrize('mode', [VERTICAL, HORIZONTAL])
def test_actual_remaining_geometry_is_not_enlarged_to_a_minimum(tmp_path, monkeypatch, mode):
    state = state_for(tmp_path)
    state['images'] = {'1': {'aspect': 2}}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['figure_1']
    plan = plan_for(raw); setup_geometry_style(state, plan)
    section = pipeline.make_board(skeleton(plan))['spatial_content_plan']['sections'][0]
    monkeypatch.setattr(geometry, 'title_cost', lambda *a: 1)
    box = geometry.dimensions(LayoutAgent(), section, 4, 2, state, mode)
    assert geometry.problems(box) == []
    assert box['text_height_available'] == pytest.approx(.3 if mode == VERTICAL else 1)
    assert box['text_width'] == pytest.approx(3.4 if mode == VERTICAL else 1.74)
    assert box['visuals'][0]['height'] == pytest.approx(.4 if mode == VERTICAL else .68)


@pytest.mark.parametrize('width,height', [(6, 36), (54, 12)])
def test_small_frames_reach_writer_and_replay_without_replanning(tmp_path, monkeypatch, width, height):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    state.update(poster_width=width, poster_height=height)
    raw = draft_for(state)
    for module in raw['modules']:
        module['title'] = 'Core'
    original = deepcopy(state)
    calls = fake_model(monkeypatch, [raw])
    pipeline.editorial_curator_node(state)
    receipt = state['editorial_authoring_geometry']
    assert receipt['version'] == 'editorial_authoring_geometry_v4'
    assert receipt['failures'] == []
    frames = receipt['frames']
    assert all(f['body_frame']['width'] > 0 and f['body_frame']['height'] > 0 for f in frames)
    if width == 6:
        assert all(f['body_frame']['width'] < 4 for f in frames)
    else:
        assert all(f['body_frame']['height'] < 2.15 for f in frames)
        assert all(f['reference']['reference_words'] == 0 for f in frames)
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'writer']
    instruction, packed = calls[1].split('\nINPUT:\n', 1)
    payload = json.JSONDecoder().raw_decode(packed)[0]
    assert 'not an instruction to return empty prose' in instruction
    assert [m['reference_words'] for m in payload['writing_tasks']['modules']] == [
        f['reference']['reference_words'] for f in frames]
    assert 'direction_decisions' not in payload['body_frames']
    assert state['editorial_candidate']['modules'] == raw['modules']
    pipeline.editorial_curator_node(original)
    assert len(calls) == 2
    assert original['editorial_authoring_geometry'] == receipt
    # Admission does not certify fit: actual writing is still measured against
    # the same small frames and preserves overflow instead of truncating prose.
    measured = measure(state, state['editorial_candidate'], receipt['zones'])
    geometry.assert_initial_frames(receipt, measured)
    assert measured['report']['total_overflow_inches'] > 0
