"""Actual request guidance must agree with sizing, without speculative heights."""
from copy import deepcopy
import json

import pytest

from src.agents.layout_agent import LayoutAgent
from src.layout import authoring_geometry as geometry
from src.layout.editorial_composition import initial_fit
from src.layout.editorial_layout import family_brief, measure
from src.layout.families import LayoutFamilyRegistry
from src.layout.measurement_context import measurement_scope
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_authoring import setup_geometry_style, skeleton
from src.workflow.editorial_contract import make_board, paper_material
from test_curator_schema import fake_model
from test_editorial_generation import state_for, draft_for, plan_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No real model'))
    with measurement_scope({'enabled': True, 'reuse_wrapping': True}):
        yield


def assert_rules(rules):
    assert rules['preserve_aspect_ratio'] is True
    assert rules['space_weight_applies_to'] == 'whole_module_height'
    vertical = rules['vertical']
    assert vertical['height_basis'] == 'module_height_minus_actual_title_and_title_to_content_gap'
    assert vertical['maximum_individual_height_fraction'] == .4
    assert vertical['maximum_multi_image_group_height_fraction'] == .5
    assert vertical['group_includes_inter_image_gaps'] is True
    assert vertical['final_gap_before_prose_is_additional'] is True
    assert vertical['group_shrink'] == 'uniform_image_scaling_with_fixed_gaps'
    assert vertical['width_limit'] == 'module_inner_width'
    horizontal = rules['horizontal']
    assert horizontal['image_width_basis'] == 'module_inner_width'
    assert horizontal['maximum_image_width_fraction'] == .4
    assert horizontal['stack_height_basis'] == vertical['height_basis']
    assert horizontal['stack_includes_inter_image_gaps'] is True
    direction = rules['direction']
    assert direction['default'] == geometry.VERTICAL
    assert direction['selected_by'] == 'program_before_writer'
    assert direction['minimum_board_width_fraction'] == .5
    assert direction['minimum_module_aspect'] == 3
    assert direction['minimum_image_linear_gain'] == 1.3
    assert direction['minimum_body_capacity_retention'] == .9
    assert direction['requires_each_image_not_smaller_than_vertical'] is True
    assert direction['alternative_benefit'] == 'restore_infeasible_vertical_body_space'
    assert direction['frozen_during_later_fitting'] is True


def assert_no_old_guidance(family):
    text = json.dumps(family)
    for field in ('visual_full_width_heights_inches', 'visual_heights_inches',
                  'vertical_max_module_height_fraction'):
        assert field not in text
    assert '30%' not in text
    assert_rules(family['image_rules'])


@pytest.mark.parametrize('family_id', LayoutFamilyRegistry().ids())
def test_family_guidance_keeps_real_regions_without_measuring_assets(tmp_path, monkeypatch, family_id):
    state = state_for(tmp_path, family_id)
    state['tables'] = {'1': {'aspect': .001, 'caption': 'A tall results table.'},
                       '2': {'caption': 'Aspect unavailable.'}}
    zones = deepcopy(list(LayoutFamilyRegistry().get(family_id).zones))
    original = deepcopy(zones)
    monkeypatch.setattr(LayoutAgent, '_calculate_visual_height',
                        lambda *a, **k: pytest.fail('No guessed image dimensions in planning'))
    family = family_brief(state, zones)
    assert_no_old_guidance(family)
    agent = LayoutAgent()
    width = state['poster_width']-2*agent.poster_margin
    height = (state['poster_height']-2*agent.poster_margin)*(1-agent.title_height_fraction)
    for actual, zone in zip(family['zones'], zones):
        assert {k: actual[k] for k in zone} == zone
        assert actual['width_inches'] == pytest.approx(width*zone['width'])
        assert actual['height_inches'] == pytest.approx(height*zone['height'])
        assert actual['horizontal_image_text_possible'] == geometry.horizontal_candidate_eligible(
            actual['width_inches'], actual['height_inches']/zone['capacity'], width)
    assert zones == original
    # Asset metadata stays in one paper catalog; missing aspect is not invented.
    visuals = paper_material(state)['visuals']
    assert visuals['table_1'] == state['tables']['1']
    assert visuals['table_2'] == state['tables']['2']


@pytest.mark.parametrize('constant,path,value', [
    ('VERTICAL_IMAGE_HEIGHT_FRACTION', ('vertical', 'maximum_individual_height_fraction'), .37),
    ('VERTICAL_GROUP_HEIGHT_FRACTION', ('vertical', 'maximum_multi_image_group_height_fraction'), .47),
    ('IMAGE_WIDTH_FRACTION', ('horizontal', 'maximum_image_width_fraction'), .39),
    ('MIN_HORIZONTAL_BOARD_WIDTH_FRACTION', ('direction', 'minimum_board_width_fraction'), .55),
    ('MIN_HORIZONTAL_ASPECT', ('direction', 'minimum_module_aspect'), 3.5),
    ('MIN_IMAGE_LINEAR_GAIN', ('direction', 'minimum_image_linear_gain'), 1.4),
    ('MIN_BODY_CAPACITY_RETENTION', ('direction', 'minimum_body_capacity_retention'), .92),
])
def test_request_rules_follow_live_geometry_constants(tmp_path, monkeypatch, constant, path, value):
    monkeypatch.setattr(geometry, constant, value)
    state = state_for(tmp_path)
    rules = family_brief(state, LayoutFamilyRegistry().get('classic_three_column').zones)['image_rules']
    assert rules[path[0]][path[1]] == value
    rules[path[0]][path[1]] = -1
    assert geometry.image_rules()[path[0]][path[1]] == value


@pytest.mark.parametrize('replan', [False, True])
def test_serialized_curator_replan_writer_and_capacity_requests(monkeypatch, tmp_path, replan):
    state = state_for(tmp_path)
    state['tables'] = {'1': {'aspect': 2, 'caption': 'Measured results, gain 30%.'},
                       '2': {'aspect': 1, 'caption': 'Comparison conditions.'}}
    raw = draft_for(state)
    raw['modules'][0]['visual_ids'] = ['table_1', 'table_2']
    bad = deepcopy(raw); bad['modules'][0]['title'] = 'A\n'*60
    patch = {'modules': [], 'remove_module_ids': [], 'module_order': [], 'narrative_flow': '',
             'reason': 'Offline unchanged capacity patch.'}
    original = deepcopy(state)
    paper = paper_material(state)
    calls = fake_model(monkeypatch, ([bad, raw] if replan else [raw])+[patch])
    pipeline.editorial_curator_node(state)
    pipeline.editorial_curator_node(original)
    assert original['editorial_authoring_geometry'] == state['editorial_authoring_geometry']
    assert len(calls) == (3 if replan else 2)  # replay does not buy a new call
    pipeline.editorial_color_node(state)
    pipeline.editorial_title_node(state)
    measured = initial_fit(state, fitter=measure)
    geometry.assert_initial_frames(state['editorial_authoring_geometry'], measured)
    before_direction = deepcopy(state['editorial_composition'])
    pipeline.edit(state, measured, 'capacity')
    assert state['editorial_composition'] == before_direction
    phases = []
    for message in calls:
        instruction, packed = message.split('\nINPUT:\n', 1)
        payload = json.JSONDecoder().raw_decode(packed)[0]
        phase = payload['phase']; phases.append(phase)
        if phase in ('curator', 'merge', 'capacity'):
            assert_no_old_guidance(payload['family'])
            assert 'image_rules' not in payload  # only family.image_rules is authoritative
            assert message.count('"image_rules":') == 1
            assert '30%' not in instruction
            assert 'family.image_rules' in instruction
            assert payload['paper'] == paper
        if phase == 'merge':
            assert payload['geometry_feedback']['failures']
        if phase == 'capacity':
            assert payload['fixed_module_composition'] == before_direction
            assert payload['capacity_tasks']['modules']
            assert 'before prose writing' in instruction
        if phase == 'writer':
            assert 'family' not in payload
            assert payload['body_frames']['frames']
            assert payload['body_frames']['version'] == geometry.VERSION
            assert payload['writing_tasks']['modules']
    expected = ['curator']+(['merge'] if replan else [])+['writer', 'capacity']
    assert phases == expected
    assert [r['phase'] for r in state['editorial_budget']['charges']] == expected


def test_numeric_rules_and_real_caps_share_the_same_title_free_basis(tmp_path):
    state = state_for(tmp_path)
    state['tables'] = {'1': {'aspect': 1}, '2': {'aspect': 2}}
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['table_1', 'table_2']
    plan = plan_for(raw); setup_geometry_style(state, plan)
    section = make_board(skeleton(plan))['spatial_content_plan']['sections'][0]
    rules = geometry.image_rules(); agent = LayoutAgent()
    vertical = geometry.dimensions(agent, section, 20, 12, state, geometry.VERTICAL)
    available = 12-vertical['title_height']
    assert vertical['visual_height'] == pytest.approx(available*rules['vertical']['maximum_multi_image_group_height_fraction'])
    assert all(r['height'] <= available*rules['vertical']['maximum_individual_height_fraction']
               for r in vertical['visuals'])
    horizontal = geometry.dimensions(agent, section, 20, 12, state, geometry.HORIZONTAL)
    assert all(r['width'] <= (20-2*horizontal['padding'])*rules['horizontal']['maximum_image_width_fraction']
               for r in horizontal['visuals'])
