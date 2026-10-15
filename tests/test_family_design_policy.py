"""Shared family policy: extension, real geometry, grounded selection and budgets."""

from copy import deepcopy
import json

import pytest

from src.agents.grounded_curator import GroundedCurator
from src.config.critic_config import load_critic_config
from src.layout.attempt_inputs import save_layout_inputs, validate_replay_input
from src.layout.design_content import ContentPriorities, apply_reading_flow, flow_conflicts, candidate_quality_key
from src.layout.family_contract import FamilyContract, ordered_zones
from src.layout.families import FAMILIES, LayoutArchitect, LayoutFamily, LayoutFamilyRegistry, valid_family_topology
from src.layout.feasibility import fit_family_layout, generate_zone_variants, _exact_refine_candidate
from src.layout.repair_budget import available_rounds, budget_usage, charge_round, family_rounds_used
from test_layout_exploration import _MeasuredAgent, _board


def state_for(board):
    sections = board['spatial_content_plan']['sections']
    return {'poster_width': 54, 'poster_height': 36, 'generation_route': 'optimization_family',
            'images': {}, 'tables': {},
            'iteration_context': {'portfolio_mode': 'explore', 'random_seed': 7},
            'verified_claims': {'claims': [
                {'claim_id': c, 'text': t, 'section_id': s['section_id'], 'evidence_ids': [c+'e']}
                for s in sections for c, t in zip(s['claim_ids'], s['text_content'])]},
            'narrative_plan': {'sections': [
                {'section_id': s['section_id'], 'narrative_role': role, 'importance': 1,
                 'evidence_ids': [s['claim_ids'][0]+'e']}
                for s, role in zip(sections, ['problem', 'method', 'results', 'results', 'conclusion', 'supporting'])]}}


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f: f.family_id)
def test_all_families_use_contract_and_shared_fit(family):
    assert family.contract.geometry == family.family_id
    assert all(valid_family_topology(family, v['zones']) for v in
               generate_zone_variants(family, random_seed=4, maximum=60))
    board = _board()
    state = state_for(board)
    original = deepcopy(state)
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    fitted, spec, report = fit_family_layout(_MeasuredAgent(), board, state, family.family_id, config=config)
    assert report['family_contract'] == family.contract.to_dict()
    assert report['design_policy_version']
    assert valid_family_topology(family, spec['zones'])
    assert set(report['candidate_content_selection']['visible_claim_ids']).issubset(
        {c['claim_id'] for c in state['verified_claims']['claims']})
    assert state == original
    assert all(s['text_content'] for s in fitted['spatial_content_plan']['sections'])


def test_unseen_registered_family_uses_generic_geometry_and_full_solver(monkeypatch):
    family = LayoutFamily('new_peer_tracks', 'New tracks', 'Test extension',
                          tuple({**z, 'zone_id': 'track_'+str(i)} for i, z in enumerate(FAMILIES[2].zones)),
                          ('general',), contract=FamilyContract(reading='columns'))
    original_init = LayoutFamilyRegistry.__init__
    def init(self, families=None):
        original_init(self, (*FAMILIES, family) if families is None else families)
    monkeypatch.setattr(LayoutFamilyRegistry, '__init__', init)
    board = _board()
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    _, spec, report = fit_family_layout(_MeasuredAgent(), board, state_for(board), family.family_id, config=config)
    assert spec['family_id'] == family.family_id
    assert report['content_quality_hints']['metadata_is_not_scientific_proof']
    assert any(v['mutation_trace'] for v in generate_zone_variants(family, random_seed=2))


def test_classic_contract_never_splits_or_spans():
    family = FAMILIES[0]
    assert not family.contract.allow_split and not family.contract.allow_span
    assert all(len(v['zones']) == 3 for v in generate_zone_variants(family, random_seed=2, maximum=60))
    zones = deepcopy(list(family.zones))
    zones.append({**zones[0], 'zone_id': 'left__lower'})
    assert not valid_family_topology(family, zones)


def test_extension_generator_cannot_mutate_canonical_candidate():
    def generator(zones, *, random_seed):
        zones[0]['capacity'] = 1
        return [('custom', zones, ['custom_capacity'])]
    family = LayoutFamily('custom_tracks', 'Custom', 'Custom generator', FAMILIES[2].zones,
                          ('general',), geometry_generator=generator)
    variants = generate_zone_variants(family, random_seed=5, maximum=60)
    assert variants[0]['zones'][0]['capacity'] == 3
    assert any('custom_capacity' in v['mutation_trace'] for v in variants)
    assert FAMILIES[2].zones[0]['capacity'] == 3


def test_previously_exhausted_beam_finds_compact_three_column_solution():
    board = _board()
    state = state_for(board)
    state['poster_height'] = 8
    _, _, report = fit_family_layout(_MeasuredAgent(), board, state, 'classic_three_column',
                                    config={'explore_layout': {'minimum_sections': 5, 'beam_width': 4}})
    assert report['status'] == 'feasible'
    assert report['max_physical_utilization'] <= 1


def test_core_priority_survives_verified_same_root_compaction():
    source = {'section_id': 's', 'claim_ids': ['a', 'b', 'c'], 'core_claim_ids': ['a']}
    state = {'verified_claims': {'claims': [{'claim_id': x} for x in ['a', 'b', 'c']]},
             'verified_content_bank': {'claims': [{'claim_id': 'compact', 'root_claim_id': 'a', 'verified': True}]}}
    changed = {**source, 'claim_ids': ['compact', 'b', 'c']}
    priorities = ContentPriorities(state, [changed])
    result = priorities.summary([{**changed, 'claim_ids': ['compact']}])
    assert result['core_coverage'] == 1
    assert result['thin_section_ids'] == ['s']  # retaining core does not excuse other lost detail
    assert priorities.summary([{**changed, 'claim_ids': ['b']}])['thin_section_ids'] == ['s']
    assert not ContentPriorities(state, [{'section_id': 'one', 'claim_ids': ['a']}]).summary(
        [{'section_id': 'one', 'claim_ids': ['a']}])['thin_section_ids']


def test_alternative_problem_modules_do_not_require_two_role_placeholders():
    sections = [{'section_id': 'a', 'claim_ids': ['a']}, {'section_id': 'b', 'claim_ids': ['b']}]
    state = {'narrative_plan': {'sections': [
        {'section_id': 'a', 'narrative_role': 'problem'}, {'section_id': 'b', 'narrative_role': 'insight'}]}}
    assert ContentPriorities(state, sections).summary(sections[:1])['role_coverage'] == 1


def test_thin_and_missing_core_hints_survive_refit_and_respect_explicit_deletion():
    section = {'section_id': 's', 'claim_ids': ['b'], 'core_claim_ids': ['a'],
               'curated_claim_roots': ['a', 'b', 'c']}
    state = {'verified_claims': {'claims': [{'claim_id': c} for c in ['a', 'b', 'c']]}}
    hints = ContentPriorities(state, [section]).summary([section])
    assert hints['thin_section_ids'] == ['s'] and hints['missing_core_roots'] == ['a']
    state['revision_recovery_policy'] = {'excluded_claim_roots': [['s', 'a'], ['s', 'c']]}
    hints = ContentPriorities(state, [section]).summary([section])
    assert not hints['thin_section_ids'] and not hints['missing_core_roots']


def test_random_diversity_cannot_prefer_known_flow_or_core_loss():
    clear = {'content_quality_hints': {'missing_core_roots': [], 'reading_conflicts': [], 'thin_section_ids': []}}
    reversed_flow = {'content_quality_hints': {'reading_conflicts': [['a', 'b']]}}
    missing = {'content_quality_hints': {'missing_core_roots': ['core']}}
    assert candidate_quality_key(clear) > candidate_quality_key(reversed_flow) > candidate_quality_key(missing)


@pytest.mark.parametrize('locked', [False, True])
def test_reading_flow_changes_actual_stacking_unless_locked(locked):
    sections = [{'section_id': 'intro', 'claim_ids': ['a']}, {'section_id': 'result', 'claim_ids': ['b']}]
    state = {'narrative_plan': {'sections': [
        {'section_id': 'intro', 'narrative_role': 'problem'},
        {'section_id': 'result', 'narrative_role': 'results'}]}}
    spec = {'zones': [{'zone_id': 'column', 'x': 0, 'y': 0, 'section_ids': ['result', 'intro']}],
            'reading_order': ['result', 'intro']}
    priorities = ContentPriorities(state, sections)
    apply_reading_flow(spec, {s['section_id']: s for s in sections}, priorities,
                       FamilyContract(reading='columns'), locked=locked)
    assert spec['zones'][0]['section_ids'] == (['result', 'intro'] if locked else ['intro', 'result'])
    assert spec['reading_order'] == spec['zones'][0]['section_ids']


def test_anchor_and_parallel_reading_do_not_force_linear_abt():
    zones = [{'zone_id': 'support', 'x': 0, 'y': 0, 'role': 'support'},
             {'zone_id': 'hero', 'x': .5, 'y': 0, 'role': 'hero'},
             {'zone_id': 'end', 'x': 0, 'y': .8, 'role': 'conclusion'}]
    assert ordered_zones(zones, FamilyContract(reading='anchor_first'))[0]['zone_id'] == 'hero'
    assert ordered_zones(zones, FamilyContract(reading='parallel'))[-1]['zone_id'] == 'end'
    assert not flow_conflicts({'reading_order': ['r', 'p']},
                             {'r': {'section_id': 'r'}, 'p': {'section_id': 'p'}},
                             ContentPriorities({}, []), FamilyContract(reading='anchor_first'))


def test_unknown_role_does_not_hide_known_order_reversal():
    sections = [{'section_id': s, 'claim_ids': [s]} for s in ['r', 'u', 'm']]
    state = {'narrative_plan': {'sections': [
        {'section_id': 'r', 'narrative_role': 'results'},
        {'section_id': 'u', 'narrative_role': 'custom_role'},
        {'section_id': 'm', 'narrative_role': 'method'}]}}
    priorities = ContentPriorities(state, sections)
    assert flow_conflicts({'reading_order': ['r', 'u', 'm']},
                          {s['section_id']: s for s in sections}, priorities,
                          FamilyContract(reading='columns')) == [('r', 'm')]


def test_zero_height_claim_refill_is_not_discarded():
    class FlatAgent(_MeasuredAgent):
        @staticmethod
        def _calculate_precise_section_height(*_args):
            return 2.0
    source = {'spatial_content_plan': {'sections': [_board()['spatial_content_plan']['sections'][1]]}}
    board = deepcopy(source)
    board['spatial_content_plan']['sections'][0]['claim_ids'] = ['c1_0']
    board['spatial_content_plan']['sections'][0]['text_content'] = ['Grounded claim 1-0.']
    state = state_for(source)
    spec = LayoutArchitect().build({**state, 'story_board': board}, 'classic_three_column',
                                   assignments_override={'left': ['s1'], 'middle': [], 'right': []})
    candidate = {'board': board, 'layout_spec': spec, 'variant': {}, 'score': (1, 1, 1, 'v'),
                 'candidate_content_selection': {}}
    result = _exact_refine_candidate(FlatAgent(), candidate, source, state,
                                    {'max_exact_refill_steps': 24}, allow_changes=True)
    assert result is not None
    assert len(result['board']['spatial_content_plan']['sections'][0]['claim_ids']) == 4


def test_loop_titles_complete_and_core_ids_sanitized_classic_unchanged():
    curator = GroundedCurator()
    title = 'A complete title longer than five words'
    claims = {'a': {'text': 'Verified original.'}, 'b': {'text': 'Another verified original.'}}
    raw = {'spatial_content_plan': {'sections': [{'section_id': 's', 'section_title': title,
        'claim_ids': ['a', 'b'], 'core_claim_ids': ['bad', 'b', 'b']} ]}}
    loop = curator._materialize(raw, claims, {}, {}, family_mode=True)['spatial_content_plan']['sections'][0]
    classic = curator._materialize(raw, claims, {}, {}, family_mode=False)['spatial_content_plan']['sections'][0]
    assert loop['section_title'] == title and loop['core_claim_ids'] == ['b']
    assert classic['section_title'] == 'A complete title longer than'
    assert 'core_claim_ids' not in classic
    assert loop['text_content'] == [c['text'] for c in claims.values()]


def test_repair_budget_reserve_survives_new_attempt_and_process_resume(tmp_path):
    settings = {'max_rounds_per_iteration': 4, 'quality_reserved_rounds': 1}
    first = tmp_path / 'attempts' / 'first'; first.mkdir(parents=True)
    state = {'iteration_context': {'attempt_diagnostics_dir': str(first)}}
    for _ in range(3):
        assert charge_round(state, 'capacity', settings)
    assert not charge_round(state, 'capacity', settings)
    second = first.parent / 'second'; second.mkdir()
    resumed = {'iteration_context': {'attempt_diagnostics_dir': str(second)}}
    assert available_rounds(resumed, 'capacity', settings) == 0
    assert available_rounds(resumed, 'quality', settings) == 1
    assert charge_round(resumed, 'quality', settings)
    assert not charge_round(resumed, 'quality', settings)
    assert budget_usage(second) == (3, 1)


def test_corrupt_budget_fails_closed(tmp_path):
    directory = tmp_path / 'attempts' / 'first'; directory.mkdir(parents=True)
    (directory / 'model_repair_budget.json').write_text('{broken')
    with pytest.raises(ValueError):
        available_rounds({'iteration_context': {'attempt_diagnostics_dir': str(directory)}}, 'capacity', {})


def test_original_attempt_input_immutable_and_excludes_model_secrets(tmp_path):
    directory = tmp_path / 'attempt'; directory.mkdir()
    board = _board(); state = state_for(board)
    state.update({'text_model': {'api_key': 'must-not-copy'}, 'tokens': object()})
    state['iteration_context']['attempt_diagnostics_dir'] = str(directory)
    save_layout_inputs(state, board, FAMILIES[0])
    original = (directory / 'layout_input_snapshot.json').read_bytes()
    assert b'must-not-copy' not in original
    changed = deepcopy(board); changed['spatial_content_plan']['sections'].pop()
    save_layout_inputs(state, changed, FAMILIES[0])
    assert (directory / 'layout_input_snapshot.json').read_bytes() == original
    assert json.loads(original)['family_contract']['allow_split'] is False
    saved = json.loads(original)
    validate_replay_input(saved)
    saved['state']['poster_width'] = 999
    with pytest.raises(ValueError, match='digest mismatch'):
        validate_replay_input(saved)


def test_thin_section_is_repair_target_even_when_zone_is_dense():
    from src.layout.capacity_repair import CapacityActionPlanner, needs_feasible_repair
    board = {'spatial_content_plan': {'sections': [
        {'section_id': 'full', 'claim_ids': ['a']}, {'section_id': 'thin', 'claim_ids': ['b']} ]}}
    report = {'status': 'feasible', 'zone_utilization': {'z': .96}, 'exact_bottom_gaps': {'z': 0},
              'content_quality_hints': {'thin_section_ids': ['thin']},
              'selected_layout_spec': {'zones': [{'zone_id': 'z', 'section_ids': ['full', 'thin']}]}}
    assert needs_feasible_repair(report, {})
    actions, _ = CapacityActionPlanner.plan_with_reason({}, board, report, round_index=0, maximum_actions=2)
    assert actions[0]['section_id'] == 'thin'


def test_reserve_is_released_after_quality_call_without_refunding_calls(tmp_path):
    directory = tmp_path / 'attempts' / 'a'; directory.mkdir(parents=True)
    state = {'iteration_context': {'attempt_diagnostics_dir': str(directory)}}
    settings = {'max_rounds_per_iteration': 4, 'quality_reserved_rounds': 1}
    assert charge_round(state, 'quality', settings)
    assert available_rounds(state, 'capacity', settings) == 3
    assert charge_round(state, 'capacity', settings)
    assert budget_usage(directory) == (1, 1)


def test_family_budget_counts_both_phases_across_attempts(tmp_path):
    directory = tmp_path / 'attempts' / 'a'; directory.mkdir(parents=True)
    state = {'iteration_context': {'attempt_diagnostics_dir': str(directory), 'layout_family': 'family'}}
    assert charge_round(state, 'capacity', {'max_rounds_per_iteration': 4})
    assert charge_round(state, 'quality', {'max_rounds_per_iteration': 4})
    second = directory.parent / 'b'; second.mkdir()
    resumed = {'iteration_context': {'attempt_diagnostics_dir': str(second), 'layout_family': 'family'}}
    assert family_rounds_used(resumed, 'family') == 2
    assert family_rounds_used(resumed, 'other') == 0


def test_requested_reading_order_moves_real_zone_ownership():
    source = {'spatial_content_plan': {'sections': _board()['spatial_content_plan']['sections'][1:3]}}
    state = state_for(source)
    spec = LayoutArchitect().build({**state, 'story_board': source}, 'classic_three_column',
                                   assignments_override={'left': ['s1'], 'middle': ['s2'], 'right': []})
    state['iteration_context']['portfolio_mode'] = 'improve'
    state['layout_revision_constraints'] = {'reading_order': ['s2', 's1']}
    result = _exact_refine_candidate(_MeasuredAgent(), {
        'board': deepcopy(source), 'layout_spec': spec, 'variant': {}, 'score': (1, 1, 1, 'v'),
        'candidate_content_selection': {},
    }, source, state, {}, allow_changes=True)
    assert result['layout_spec']['zones'][0]['section_ids'] == ['s2']
    assert result['layout_spec']['reading_order'] == ['s2', 's1']
    assert result['content_quality_hints']['requested_reading_order_applied'] is True


def test_pinned_reading_request_cannot_claim_false_success():
    source = {'spatial_content_plan': {'sections': _board()['spatial_content_plan']['sections'][1:3]}}
    state = state_for(source)
    spec = LayoutArchitect().build({**state, 'story_board': source}, 'classic_three_column',
                                   assignments_override={'left': ['s1'], 'middle': ['s2'], 'right': []})
    state['layout_revision_constraints'] = {'reading_order': ['s2', 's1'], 'section_to_zone': {'s1': 'left'}}
    result = _exact_refine_candidate(_MeasuredAgent(), {
        'board': deepcopy(source), 'layout_spec': spec, 'variant': {}, 'score': (1, 1, 1, 'v'),
        'candidate_content_selection': {},
    }, source, state, {}, allow_changes=True)
    assert result['layout_spec']['reading_order'] == ['s1', 's2']
    assert result['content_quality_hints']['requested_reading_order_applied'] is False
