"""Coverage navigation is faithful input guidance, never a fabricated judgment."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import paper_material
from src.workflow.editorial_coverage import authoring_coverage, VERSION
from test_curator_schema import fake_model
from test_editorial_generation import state_for, draft_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))


def research_state(tmp_path, family='horizontal_narrative_bands'):
    state = state_for(tmp_path, family)
    sections = state['structured_sections']['paper_sections']
    for kind, content in (
        ('evaluation', 'On held-out task A, accuracy is 0.80 versus baseline 0.75 under setting X.'),
        ('discussion', 'The reported advantage is limited to setting X.'),
        ('other', 'A qualitative failure case illustrates the remaining limitation.'),
    ):
        section = deepcopy(sections[0])
        section.update(section_name=kind.title(), section_type=kind, content=content,
                       key_points=[content], contains_figures=[], contains_tables=[])
        sections.append(section)
    state['images'] = {'1': {'caption': 'Method diagram with panels (a) and (b)', 'aspect': 2}}
    state['tables'] = {'1': {'caption': 'Task A accuracy comparison under setting X', 'aspect': 2},
                       '2': {'caption': 'Additional observations', 'aspect': 1.5}}
    state['classified_visuals'] = {'key_visual': 'figure_1', 'method_workflow': ['figure_1'],
                                    'main_results': ['table_1'], 'supporting': ['table_2']}
    return state


def payload(message):
    return json.loads(message.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:', 1)[0])


def resolve(value, path):
    for key in path:
        value = value[key]
    return value


def test_index_keeps_every_source_and_exact_locations_without_copying_evidence(tmp_path):
    paper = paper_material(research_state(tmp_path)); before = deepcopy(paper)
    guide = authoring_coverage(paper)
    assert paper == before
    assert len(guide['sections']) == len(paper['structured_sections']['paper_sections'])
    assert [r['visual_id'] for r in guide['visuals']] == list(paper['visuals'])
    for row, section in zip(guide['sections'], paper['structured_sections']['paper_sections']):
        assert resolve({'paper': paper}, row['source_path']) is section
        assert row['section_type'] == section['section_type']
    for row in guide['visuals']:
        assert resolve({'paper': paper}, row['source_path']) is paper['visuals'][row['visual_id']]
    assert guide['review_for_findings'] == {
        'section_paths': [['paper', 'structured_sections', 'paper_sections', 1]],
        'visual_ids': ['table_1']}
    assert [r['visual_id'] for r in guide['visuals'] if r['required_key_visual']] == ['figure_1']
    # Full evidence appears only in paper, never as a lossy/duplicate summary.
    assert '0.80' not in json.dumps(guide)
    guide['sections'][0]['section_name'] = 'changed'
    guide['review_for_findings']['section_paths'][0][-1] = 99
    guide['visuals'][0]['reported_roles'].append('changed')
    assert paper == before
    assert guide['sections'][1]['source_path'][-1] == 1


@pytest.mark.parametrize('kind', ['method', 'other', 'evaluation'])
def test_theory_qualitative_and_misclassified_findings_are_not_deleted_or_certified(tmp_path, kind):
    paper = paper_material(state_for(tmp_path))
    section = paper['structured_sections']['paper_sections'][0]
    section.update(section_type=kind, section_name='Analysis',
                   content='Under assumption A, Theorem 1 establishes property B; no experiment is reported.')
    guide = authoring_coverage(paper)
    assert len(guide['sections']) == 1 and not guide['visuals']
    assert bool(guide['review_for_findings']['section_paths']) == (kind == 'evaluation')
    assert resolve({'paper': paper}, guide['sections'][0]['source_path'])['content'] == section['content']
    assert not {'empirical', 'no_results', 'coverage_passed', 'required_modules'} & guide.keys()


def test_roles_cannot_invent_assets_or_omit_unclassified_available_ones(tmp_path):
    paper = paper_material(research_state(tmp_path))
    paper['classified_visuals'] = {'key_visual': 'figure_1a',
        'main_results': ['figure_1a', 'table_1', 'table_1'], 'comparative_results': ['table_1']}
    guide = authoring_coverage(paper)
    assert [v['visual_id'] for v in guide['visuals']] == ['figure_1', 'table_1', 'table_2']
    assert guide['review_for_findings']['visual_ids'] == ['table_1']
    assert not any(v['required_key_visual'] for v in guide['visuals'])
    assert paper['classified_visuals']['key_visual'] == 'figure_1a'  # not silently repaired


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_all_families_receive_complete_index_and_matching_existing_budgets(monkeypatch,tmp_path,family):
    state = research_state(tmp_path, family); expected_paper = paper_material(state)
    raw = draft_for(state); raw['modules'][0]['visual_ids'] = ['figure_1']
    calls = fake_model(monkeypatch, [raw])
    pipeline.editorial_curator_node(state)
    sent = payload(calls[0])
    assert sent['research_coverage'] == authoring_coverage(expected_paper)
    assert sent['paper'] == expected_paper
    assert [z['zone_id'] for z in sent['body_budgets']['zones']] == [z['zone_id'] for z in sent['family']['zones']]
    for zone, budget in zip(sent['family']['zones'], sent['body_budgets']['zones']):
        assert [c['modules_in_zone'] for c in budget['allocation_cases']] == list(range(1, zone['capacity']+1))
    assert len(calls) == 1
    # Guidance does not impose a new semantic admission gate or a retry when
    # this deliberately method-only fixture fails to follow the writing advice.
    assert state['editorial_candidate']['modules'] == raw['modules']
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator']


def test_four_slot_findings_and_provenance_survive_real_request_and_replay(monkeypatch,tmp_path):
    state = research_state(tmp_path)
    raw = draft_for(state)
    raw['modules'][0]['visual_ids'] = ['figure_1']
    finding = raw['modules'][-1]
    finding.update(title='Reported Evidence', visual_ids=['table_1'])
    finding['entries'][0]['text'] = state['structured_sections']['paper_sections'][1]['content']
    finding['entries'][1]['text'] = state['structured_sections']['paper_sections'][2]['content']
    raw['reason'] = 'Method is in module_0; task A evidence and its scope are in module_3.'
    calls = fake_model(monkeypatch, [raw])
    original = deepcopy(state)
    pipeline.editorial_curator_node(state)
    pipeline.editorial_curator_node(original)
    assert len(calls) == 1
    assert original['editorial_candidate'] == state['editorial_candidate']
    assert state['editorial_candidate']['modules'][-1] == finding
    assert state['editorial_visual_selection']['owners']['module_3'] == ['table_1']
    root = Path(state['sample_preparation_dir'])/'editorial/curator'
    identity = json.loads((root/'identity.json').read_text())['payload']
    assert VERSION in identity['prompt']
    assert payload(identity['prompt']) == payload(calls[0])
    assert json.loads((root/'accepted.json').read_text())['payload']['value']['reason'] == raw['reason']
    assert len(original['editorial_budget']['charges']) == 1


def test_merge_replans_same_evidence_against_new_occupancy_without_extra_stage(monkeypatch,tmp_path):
    state = research_state(tmp_path, 'small_multiples_matrix')
    captured = []
    def respond(st, kind, value, schema, **kwargs):
        captured.append(deepcopy(value))
        raw = draft_for(st); raw['modules'] = raw['modules'][:4]
        raw['modules'][0]['visual_ids'] = ['figure_1']
        raw['modules'][-1]['visual_ids'] = ['table_1']
        if value['phase'] == 'merge':
            for module, zone in zip(raw['modules'], value['family']['zones']):
                module['zone_id'] = zone['zone_id']
        return raw
    monkeypatch.setattr(pipeline, 'request', respond)
    pipeline.editorial_curator_node(state)
    first, merged = captured
    assert first['research_coverage'] == merged['research_coverage']
    assert first['paper'] == merged['paper']
    assert len(first['body_budgets']['zones']) == 6
    assert len(merged['body_budgets']['zones']) == 4
    assert [z['zone_id'] for z in merged['body_budgets']['zones']] == [z['zone_id'] for z in merged['family']['zones']]
    assert merged['previous_draft'] is not None
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge']
