"""Communication fixes must preserve science, family ownership and durable budgets."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from src.layout.family_capacity import family_brief, plan_family_capacity
from src.layout.families import LayoutFamilyRegistry
from src.layout.repair_budget import sample_ledger
from src.workflow import joint_preparation as joint
from src.workflow.sample_editorial import visual_context, quality_gain, prose_diagnostics
from src.workflow.sample_modules import normalize_module_plan
from utils.persistence import read_json
from test_joint_preparation import state_for, accept, fit_result, revision, Agent


@pytest.mark.parametrize('route', ['initial', 'revision', 'completion'])
@pytest.mark.parametrize('bounds', [('3', '17'), ('42', '70')])
def test_shared_percent_range_reaches_science_as_explicit_unverified_text(tmp_path, route, bounds):
    from src.workflow.sample_module_writing import normalize_body
    state = state_for(tmp_path)
    low, high = bounds
    for evidence in state['evidence_bank']['items']:
        evidence.update(claim=f'Improvement ranges from {low}% to {high}%.',
                        source_excerpt=f'Improvement ranges from {low}% to {high}%.')
    original_evidence = deepcopy(state['evidence_bank'])
    text = f'Improvement ranges from {low}–{high}%.'
    module = state['sample_module_plan']['modules'][0]
    item = {'item_id': 'range', 'text': text, 'evidence_ids': ['e1', 'e2']}
    if route == 'initial':
        claims = normalize_body({'claims': [item]}, module, state)
    else:
        raw = revision(state)
        if route == 'revision':
            raw['modules'][0]['claims'][0]['text'] = text
        else:
            raw['modules'][0]['additional_claims'] = [item]
        claims, _ = joint.normalize_editorial_revision(raw, state, ['display_001'], 'quality')
    claim = claims[-1]
    assert claim['text'] == f'Improvement ranges from {low}%–{high}%.'
    assert claim.get('verified') is not True and 'support_map' not in claim
    assert claim['display_normalizations'][-1]['kind'] == 'shared_percentage_range'
    assert state['evidence_bank'] == original_evidence


@pytest.mark.parametrize('text', ['Improvement is 999–17%.', 'Improvement is 3–999%.'])
@pytest.mark.parametrize('route', ['initial', 'revision', 'completion'])
def test_percentage_range_cannot_admit_an_unsupported_endpoint(tmp_path, text, route):
    from src.workflow.sample_module_writing import normalize_body
    state = state_for(tmp_path)
    for evidence in state['evidence_bank']['items']:
        evidence.update(claim='Improvement ranges from 3% to 17%.',
                        source_excerpt='Improvement ranges from 3% to 17%.')
    item = {'item_id': 'range', 'text': text, 'evidence_ids': ['e1', 'e2']}
    with pytest.raises(ValueError):
        if route == 'initial':
            normalize_body({'claims': [item]}, state['sample_module_plan']['modules'][0], state)
        else:
            raw = revision(state)
            if route == 'revision': raw['modules'][0]['claims'][0]['text'] = text
            else: raw['modules'][0]['additional_claims'] = [item]
            joint.normalize_editorial_revision(raw, state, ['display_001'], 'quality')


@pytest.mark.parametrize('text', ['3%–17%', '-3–17%', '−3–17%', '3-17%', 'x3–17%', '3–17 units'])
def test_percentage_normalization_preserves_explicit_units_and_ambiguous_math(text):
    from src.workflow.sample_module_writing import normalize_shared_percentage_ranges
    bank = {'e': {'claim': '3% to 17%'}}
    assert normalize_shared_percentage_ranges(text, ['e'], bank) == (text, [])


def six_roles(tmp_path):
    state = state_for(tmp_path, 6)
    state['sample_family']['family'] = state['iteration_context']['layout_family'] = 'central_hero_side_rails'
    for unit, role in zip(state['narrative_plan']['sections'], ['context', 'task_definition', 'method', 'evaluation', 'results', 'implications']):
        unit.update(narrative_role=role, presentation_function=role)
    state['images'] = {'1': {'caption': 'Method architecture', 'aspect': 2.84}}
    state['sample_module_plan']['modules'][2]['visual_ids'] = ['figure_1']
    return state


def test_capacity_does_not_give_implications_hero_budget_over_architecture(tmp_path):
    state = six_roles(tmp_path)
    plan_family_capacity(state)
    modules = state['sample_module_plan']['modules']
    assert modules[2]['space_target']['zone_id'] == 'central_hero'
    assert modules[5]['space_target']['zone_id'] != 'central_hero'
    assert modules[2]['soft_word_range'][1] > modules[5]['soft_word_range'][1]
    assert state['family_capacity']['assignment_status'] == 'provisional_range'
    assert not state['family_capacity']['assignment_is_binding']
    assert all(m['space_target']['candidate_zone_ids'] for m in modules)


def test_measured_assignment_replaces_provisional_hint_without_mutating_spec(tmp_path):
    state = six_roles(tmp_path)
    zones = deepcopy(family_brief(state)['zones'])
    for zone, ids in zip(zones, [['display_001', 'display_002'], ['display_003', 'display_004'], ['display_005', 'display_006']]):
        zone['section_ids'] = ids
    spec = {'family_id': 'central_hero_side_rails', 'zones': zones}
    saved = deepcopy(spec)
    plan_family_capacity(state, spec)
    assert spec == saved
    assert state['family_capacity']['assignment_status'] == 'measured_ownership'
    assert state['sample_module_plan']['modules'][2]['space_target']['zone_id'] == 'central_hero'


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_all_peer_families_get_explicit_uncertain_capacity_not_false_fit(tmp_path, family):
    state = state_for(tmp_path, 6)
    state['sample_family']['family'] = state['iteration_context']['layout_family'] = family
    plan_family_capacity(state)
    assert not state['family_capacity']['certifies_feasible_layout']
    assert len(state['family_capacity']['modules']) == 6
    assert all(m['space_target']['width_range_inches'] for m in state['sample_module_plan']['modules'])


def test_visual_context_contains_existing_roles_key_and_actual_footprint(tmp_path):
    from PIL import Image
    state = six_roles(tmp_path)
    path = tmp_path/'asset.png'; Image.new('RGB', (1000, 400)).save(path)
    state['images']['1']['path'] = str(path)
    state['classified_visuals'] = {'key_visual': 'figure_1', 'method_workflow': ['figure_1']}
    row = visual_context(state, family_brief(state))[0]
    assert row['key_visual'] and row['source_roles'] == ['method_workflow']
    assert len(row['family_footprints']) == 3
    assert all(r['effective_dpi'] > 0 for r in row['family_footprints'])


def test_visual_reserve_ownership_and_rationale_survive_plan_assembly(tmp_path):
    state = state_for(tmp_path)
    state['images'] = {'1': {}, '2': {}}
    module = deepcopy(state['sample_module_plan']['modules'][0])
    module.update(visual_ids=['figure_1'], reserve_visual_ids=['figure_2'],
                  visual_rationales={'figure_1': 'Mechanism', 'figure_2': 'Complementary evidence'},
                  research_question='How does it predict?', communication_goal='Explain the mechanism')
    plan = normalize_module_plan({'modules': [module]}, state)
    assert plan['modules'][0]['research_question'] == module['research_question']
    assert plan['visual_decisions']['figure_2']['decision'] == 'optional_same_module_probe'
    assert plan['visual_decisions']['figure_2']['module_id'] == module['module_id']
    module['reserve_visual_ids'] = ['figure_1']
    with pytest.raises(ValueError, match='duplicate_visual'):
        normalize_module_plan({'modules': [module]}, state)


def test_sparse_target_ranking_uses_gap_severity_instead_of_longest_module(tmp_path):
    state = state_for(tmp_path, 3)
    state['poster_claims']['claims'][0]['text'] *= 20
    feedback = {'completion_targets': [{'section_id': f'display_{i:03d}', 'bottom_gap': gap, 'utilization': .7}
                                        for i, gap in [(1, 1), (2, 6), (3, 3)]]}
    assert joint.edit_targets(state, feedback, {}) == ['display_002', 'display_003']


def completion_state(tmp_path):
    state = state_for(tmp_path)
    state['evidence_bank']['items'].append({'evidence_id': 'e3', 'claim': 'Neural inputs come from recorded signals.',
                                         'source_excerpt': 'Neural inputs come from recorded signals.'})
    state['narrative_plan']['sections'][0]['evidence_ids'].append('e3')
    state['sample_module_plan']['modules'][0]['available_evidence_ids'].append('e3')
    return state


def additional_revision(state):
    raw = revision(state)
    raw['modules'][0]['additional_claims'] = [{'item_id': 'explain', 'text': 'Neural inputs come from recorded signals.',
        'evidence_ids': ['e3'], 'kind': 'method', 'parent_source_claim_id': state['poster_claims']['claims'][0]['claim_id']}]
    return raw


def test_quality_completion_gets_new_root_with_exact_local_origins_and_dependency(tmp_path):
    state = completion_state(tmp_path)
    old = deepcopy(state['poster_claims']['claims'][0])
    claims, omitted = joint.normalize_editorial_revision(additional_revision(state), state, ['display_001'], 'quality')
    assert not omitted and claims[0]['claim_id'] == old['claim_id']
    assert claims[1]['claim_id'] != old['claim_id'] and claims[1]['source_plan_unit_ids'] == ['u1']
    assert claims[1]['parent_claim_id'] == old['claim_id']
    assert claims[1]['verified'] is False and 'support_map' not in claims[1]
    assert all(len(c['module_context']['items']) == 2 for c in claims)


@pytest.mark.parametrize('bad', ['foreign', 'numeric', 'parent', 'parent_type', 'capacity'])
def test_completion_cannot_bypass_scientific_scope_or_capacity_policy(tmp_path, bad):
    state = completion_state(tmp_path); raw = additional_revision(state)
    row = raw['modules'][0]['additional_claims'][0]
    if bad == 'foreign': row['evidence_ids'] = ['foreign']
    if bad == 'numeric': row['text'] = 'There are 999999 neurons.'
    if bad == 'parent': row['parent_source_claim_id'] = 'foreign'
    if bad == 'parent_type': row['parent_source_claim_id'] = ['not-an-id']
    with pytest.raises(joint.JointContentFailure):
        joint.normalize_editorial_revision(raw, state, ['display_001'], 'capacity' if bad == 'capacity' else 'quality')


def test_completion_is_charged_once_reverified_and_frozen_only_after_fit(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    state = completion_state(tmp_path)
    seen = []
    class Editor(Agent):
        def __init__(self, *args): super().__init__(additional_revision(state))
        def step(self, prompt):
            assert len(sample_ledger(state)[1]['charges']) == 1
            return super().step(prompt)
    def fit(current, *, draft):
        result = fit_result(current)
        result[2]['content_quality_hints'] = {'completion_targets': [
            {'section_id': 'display_001', 'bottom_gap': 4, 'utilization': .7}]}
        return result, None
    def verify(current):
        seen.append([c['claim_id'] for c in current['poster_claims']['claims']])
        return accept(current)
    monkeypatch.setattr(language, 'LangGraphAgent', Editor)
    monkeypatch.setattr(joint, '_fit', fit)
    monkeypatch.setattr(joint, 'sample_claim_verifier_node', verify)
    state = joint.joint_preparation_node(state)
    assert len(seen) == 2 and len(seen[0]) == 1 and len(seen[1]) == 2
    assert state['joint_candidate']['fit_report']['editorial_quality']['status'] == 'adopted'
    assert len(state['verified_claims']['claims']) == 2
    assert len(sample_ledger(state)[1]['charges']) == 1


def test_no_change_quality_trial_is_explicitly_rejected_and_baseline_preserved(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    def fit(current, *, draft):
        result = fit_result(current)
        result[2]['content_quality_hints'] = {'completion_targets': [
            {'section_id': 'display_001', 'bottom_gap': 4, 'utilization': .7}]}
        return result, None
    monkeypatch.setattr(joint, '_fit', fit)
    monkeypatch.setattr(joint, 'sample_claim_verifier_node', accept)
    monkeypatch.setattr(joint, '_edit', lambda s, *args: s)
    joint.joint_preparation_node(state)
    report = read_json(Path(state['output_dir'])/'joint/quality_report.json')
    assert report['status'] == 'rejected' and report['reason'] == 'no_measured_quality_gain'
    assert report['unresolved_targets'] == ['display_001']
    assert len(state['verified_claims']['claims']) == 1


def test_copy_diagnostics_are_not_a_scientific_or_plain_style_rejection(tmp_path):
    state = state_for(tmp_path)
    state['poster_claims']['claims'][0]['text'] = state['evidence_bank']['items'][0]['claim']
    report = prose_diagnostics(state)
    assert report['signals_are_not_semantic_verdicts']
    assert report['modules'][0]['copied_expressions'] == 1
    assert not report['modules'][0]['reasons']


def test_added_prose_still_passes_real_verifier_and_cannot_enter_bank_on_rejection(monkeypatch, tmp_path):
    import src.agents.claim_verifier as verifier
    from types import SimpleNamespace
    state = completion_state(tmp_path)
    claims, _ = joint.normalize_editorial_revision(additional_revision(state), state, ['display_001'], 'quality')
    state['poster_claims'] = {'claims': claims}
    checked = []
    class Verifier:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, prompt):
            claim = json.loads(prompt.split('CLAIM:\n', 1)[1].split('\n\nEVIDENCE:', 1)[0])
            checked.append(claim['claim_id'])
            supported = '_add_' not in claim['claim_id']
            result = {'supported': supported, 'relationships_supported': supported,
                'necessary_information_preserved': True, 'error_types': [], 'reason': 'Checked source', 'corrected_text': '',
                'coverage': [{'quote': claim['text'], 'evidence_ids': claim['evidence_ids'], 'supported': supported}],
                'covered_required_evidence_ids': claim.get('required_evidence_ids', []) if supported else []}
            if claim.get('editorial_revision'): result['editorial_information_preserved'] = True
            if claim.get('completion_origin'): result.update(completion_relevant=True, completion_non_redundant=True)
            return SimpleNamespace(content=json.dumps(result), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(verifier, 'LangGraphAgent', Verifier)
    monkeypatch.setattr(verifier, 'apply_agent_policy', lambda config, _: config)
    verifier.claim_verifier_node(state)
    assert claims[1]['claim_id'] in checked
    assert claims[1]['claim_id'] not in {c['claim_id'] for c in state['verified_claims']['claims']}


def test_extra_citation_without_supported_new_information_is_not_quality_gain(tmp_path):
    state = accept(completion_state(tmp_path))
    before = fit_result(deepcopy(state))
    trial = deepcopy(state)
    trial['verified_claims']['claims'][0]['evidence_ids'] = [*trial['verified_claims']['claims'][0]['evidence_ids'], 'e3']
    after = deepcopy(before)
    adopted, reason = quality_gain(state, before, trial, after, ['display_001'])
    assert not adopted and reason == 'no_measured_quality_gain'


def test_hierarchy_gain_counts_actual_safe_cues_not_unrendered_metadata(tmp_path):
    state = accept(state_for(tmp_path))
    before = fit_result(deepcopy(state)); after = deepcopy(before)
    section = after[0]['spatial_content_plan']['sections'][0]
    section['editorial'].update(active=True, body_style='rich', presentation_style='topics')
    section['editorial']['items'][0]['display_label'] = 'neural signals'
    assert quality_gain(state, before, state, after, ['display_001']) == (True, 'display_hierarchy_improved')
    section['editorial']['items'][0]['display_label'] = 'Unsupported improvement'
    assert quality_gain(state, before, state, after, ['display_001']) == (False, 'no_measured_quality_gain')


@pytest.mark.parametrize('verdict', [None, False, True])
def test_completion_requires_explicit_nonredundancy_in_existing_verifier(monkeypatch, tmp_path, verdict):
    import src.agents.claim_verifier as verifier
    from types import SimpleNamespace
    state = completion_state(tmp_path)
    claims, _ = joint.normalize_editorial_revision(additional_revision(state), state, ['display_001'], 'quality')
    state['poster_claims'] = {'claims': claims}
    class Verifier:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, prompt):
            claim = json.loads(prompt.split('CLAIM:\n', 1)[1].split('\n\nEVIDENCE:', 1)[0])
            result = {'supported': True, 'relationships_supported': True,
                'necessary_information_preserved': True, 'error_types': [], 'reason': 'Checked source', 'corrected_text': '',
                'coverage': [{'quote': claim['text'], 'evidence_ids': claim['evidence_ids'], 'supported': True}],
                'covered_required_evidence_ids': claim.get('required_evidence_ids', [])}
            if claim.get('editorial_revision'): result['editorial_information_preserved'] = True
            if verdict is not None and claim.get('completion_origin'):
                result.update(completion_relevant=verdict, completion_non_redundant=verdict)
            return SimpleNamespace(content=json.dumps(result), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(verifier, 'LangGraphAgent', Verifier)
    monkeypatch.setattr(verifier, 'apply_agent_policy', lambda config, _: config)
    verifier.claim_verifier_node(state)
    assert (claims[1]['claim_id'] in {c['claim_id'] for c in state['verified_claims']['claims']}) is (verdict is True)
