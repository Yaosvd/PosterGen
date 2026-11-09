"""Space budgets must follow real frames and remain advisory/offline."""
from copy import deepcopy
import json

import pytest

from src.agents.layout_agent import LayoutAgent
from src.layout.editorial_body_budget import authoring_body_budgets, measured_body_budgets
from src.layout.editorial_layout import measure
from src.layout.families import LayoutFamilyRegistry
from src.layout.measurement_context import measurement_scope
from src.workflow import editorial_pipeline as pipeline
from test_editorial_generation import state_for, draft_for, install
from test_curator_schema import fake_model


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_initial_cases_cover_all_actual_regions_without_mutation(tmp_path, family):
    state = state_for(tmp_path, family)
    zones = LayoutFamilyRegistry().get(family).zones
    before = deepcopy(state)
    result = authoring_body_budgets(state, zones)
    assert state == before
    assert [r['zone_id'] for r in result['zones']] == [z['zone_id'] for z in zones]
    for row, zone in zip(result['zones'], zones):
        cases = row['allocation_cases']
        assert len(cases) == zone['capacity']
        for case in cases:
            count = case['modules_in_zone']
            available = row['height_inches'] - result['inter_module_gap_inches'] * (count - 1)
            assert case['allocated_module_height_inches'] == pytest.approx(available / count, abs=.0001)
            assert case['stacked_conservative_by_visual_count'][0]['reference_words'] >= 0
        assert cases[-1]['allocated_module_height_inches'] <= cases[0]['allocated_module_height_inches']
    json.dumps(result, allow_nan=False)


def test_larger_font_and_more_visuals_reduce_initial_prose_allowance(tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    state['images'] = {'1': {'aspect': 1.5}, '2': {'aspect': 2.0}}
    zones = LayoutFamilyRegistry().get(state['sample_family']['family']).zones
    result = authoring_body_budgets(state, zones)
    first = result['zones'][0]['allocation_cases'][0]
    stacked = first['stacked_conservative_by_visual_count']
    assert stacked[0]['reference_words'] > stacked[1]['reference_words'] >= stacked[2]['reference_words']
    assert stacked[2]['available_body_height_inches'] == pytest.approx(
        first['allocated_module_height_inches'] - first['title_and_gap_reserve_inches']
        - sum(first['stacked_visual_cost_inches'].values()), abs=.0002)
    assert first['single_visual_horizontal_reference']['figure_1']['reference_words'] > 0
    state['styling_interfaces'] = {'font_sizes': {'body_text': 60, 'section_title': 80}}
    larger = authoring_body_budgets(state, zones)['zones'][0]['allocation_cases'][0]
    assert larger['stacked_conservative_by_visual_count'][0]['reference_words'] < stacked[0]['reference_words']


def test_initial_measurement_cache_does_not_change_guidance(tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    state['images'] = {'1': {'aspect': 2}}
    zones = LayoutFamilyRegistry().get(state['sample_family']['family']).zones
    cached = authoring_body_budgets(state, zones)
    state['critic_config']['layout_performance'] = {'enabled': False, 'verbose_measurements': False}
    assert authoring_body_budgets(state, zones) == cached


def test_curator_persists_budget_and_replays_without_another_call(tmp_path, monkeypatch):
    state = state_for(tmp_path, 'horizontal_narrative_bands')
    calls = fake_model(monkeypatch, [draft_for(state)])
    pipeline.editorial_curator_node(state)
    first = deepcopy(state['editorial_candidate'])
    pipeline.editorial_curator_node(state)
    payload = json.loads(calls[1].split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])
    assert payload['body_frames']['version'] == 'editorial_authoring_geometry_v1'
    assert len(calls) == len(state['editorial_budget']['charges']) == 2
    assert state['editorial_candidate'] == first
    identity = json.loads((__import__('pathlib').Path(state['sample_preparation_dir']) /
                           'editorial/writer/identity.json').read_text())['payload']
    assert 'editorial_authoring_geometry_v1' in identity['prompt']


def test_body_budget_uses_remaining_text_space_not_image_utilization():
    # Regression for the observed 237-word body with only ~1.066in remaining.
    result = {'report': {'modules': [{'module_id': 'm', 'current_words': 237,
                'body_layout': 'image_above_text', 'suggested_words': 66}]},
        'layout': [
            {'type': 'section_container', 'section_id': 'm',
             'module_frame': {'x': 0, 'y': 5, 'width': 20, 'height': 10.8732}},
            {'type': 'visual', 'section_id': 'm', 'y': 9, 'height': 5.5},
            {'type': 'text', 'section_id': 'm', 'y': 14.807253, 'height': 27.333333, 'width': 19.4}]}
    before = deepcopy(result)
    row = measured_body_budgets(result)['modules'][0]
    assert row['available_body_height_inches'] == pytest.approx(1.065947)
    assert row['reference_words'] == 8
    assert row['body_overflow_inches'] == pytest.approx(26.267386)
    assert result == before
    result['layout'][-1]['y'] = 17
    assert measured_body_budgets(result)['modules'][0]['reference_words'] == 0


@pytest.mark.parametrize('visual_count', [0, 1, 2])
def test_real_compiled_body_space_follows_text_box_and_weighted_frames(tmp_path, visual_count):
    state = state_for(tmp_path)
    state['images'] = {str(i): {'aspect': 1.5} for i in range(1, visual_count + 1)}
    raw = draft_for(state)
    raw['modules'][0]['visual_ids'] = [f'figure_{i}' for i in range(1, visual_count + 1)]
    # Put two modules in one zone with unequal weights; the helper must read
    # the real allocation, not the equal-share initial reference.
    raw['modules'].append(deepcopy(raw['modules'][0]))
    raw['modules'][-1].update(module_id='extra', space_weight=3, visual_ids=[])
    install(state, raw)
    with measurement_scope():
        result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    rows = measured_body_budgets(result)['modules']
    for row in rows:
        body = next(e for e in result['layout'] if e.get('type') == 'text' and e['section_id'] == row['module_id'])
        container = next(e for e in result['layout'] if e.get('type') == 'section_container' and e['section_id'] == row['module_id'])
        frame = container['module_frame']
        assert row['available_body_height_inches'] == pytest.approx(frame['y'] + frame['height'] - body['y'])
        assert row['text_box_width_inches'] == body['width']
    assert rows[-1]['available_body_height_inches'] > rows[0]['available_body_height_inches']


def test_horizontal_images_do_not_get_subtracted_from_body_height(tmp_path):
    state = state_for(tmp_path, 'horizontal_narrative_bands', 'A short mechanism explains the result.')
    state['images'] = {'1': {'aspect': 2}}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['figure_1']
    install(state, raw)
    with measurement_scope():
        result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    row = measured_body_budgets(result)['modules'][0]
    assert row['body_layout'] == 'image_left_text_right'
    assert row['text_box_width_inches'] < 51.4
    title = next(e for e in result['layout'] if e.get('type') == 'section_title' and e['section_id'] == row['module_id'])
    assert row['available_body_height_inches'] == pytest.approx(
        result['report']['modules'][0]['allocated_height'] - title['height']
        - LayoutAgent().config['layout']['title_to_content_spacing'])
