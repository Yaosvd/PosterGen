"""Editing preserves scientific text, prerequisites, geometry and rollback identity."""

from copy import deepcopy
import json

import pytest
from pptx import Presentation
from pptx.util import Inches

from src.agents.font_agent import FontAgent
from src.agents.grounded_curator import GroundedCurator
from src.agents.layout_agent import LayoutAgent
from src.agents.renderer import Renderer
from src.config.critic_config import load_critic_config
from src.layout.editorial import (
    EDITORIAL_POLICY_VERSION, EditorialFitResult, choose_title, dependencies_met,
    polish_wording, prepare_board, presentation_lines, refine_editorial,
    remember_baseline, sections, source_for_fit,
)
from src.layout.families import FAMILIES, LayoutFamily, LayoutFamilyRegistry
from src.layout.family_contract import FamilyContract
from src.layout.feasibility import _content_options, fit_family_layout
from src.layout.repair_budget import budget_usage
from test_family_design_policy import state_for
from test_layout_exploration import _board, _MeasuredAgent


def example():
    board = {'spatial_content_plan': {'sections': [
        {'section_id': 's', 'section_title': 'Performance Evaluation: HAGS vs. Baselines',
         'claim_ids': ['r', 'c'], 'text_content': [
             'HAGS improves recall by 3% under uniform costs compared with the baseline.',
             'The evaluation uses 16000 properties, averaged over four random selections.'],
         'core_claim_ids': ['r'], 'visual_assets': []}]}}
    state = {'generation_route': 'optimization_family', 'iteration_context': {'generation_purpose': 'explore', 'attempt_id': 'a'},
             'narrative_plan': {'sections': [{'section_id': 's', 'narrative_role': 'results', 'importance': 1}]},
             'verified_claims': {'claims': [
                 {'claim_id': cid, 'section_id': 's', 'text': text, 'verified': True,
                  'claim_type': 'comparative' if cid == 'r' else 'descriptive', 'evidence_ids': [cid + 'e']}
                 for cid, text in zip(['r', 'c'], sections(board)[0]['text_content'])]},
             'color_scheme': {'text': '#000000', 'contrast': '#006060', 'mono_light': '#F5EEEE'},
             'errors': []}
    return state, board


def candidate(board):
    return {'board': deepcopy(board), 'layout_spec': {'family_id': 'classic_three_column',
        'zones': [{'zone_id': 'z', 'x': 0, 'y': 0, 'width': 1, 'height': 1, 'capacity': 4,
                   'section_ids': [s['section_id'] for s in sections(board)]}],
        'reading_order': [s['section_id'] for s in sections(board)]},
        'exact_utilization': {'z': .95}, 'exact_bottom_gaps': {'z': .3},
        'composition_whitespace': {'largest_empty_rectangle_fraction': .04},
        'candidate_content_selection': {}}


def identity_refine(_agent, trial, _sources, _state, _settings, **kwargs):
    return trial


def test_internal_order_labels_and_exact_science_are_separate():
    state, board = example()
    original = deepcopy((state, board))
    result, audit = refine_editorial(None, candidate(board), board, state, FAMILIES[0], {}, identity_refine)
    section = sections(result['board'])[0]
    assert section['claim_ids'] == ['c', 'r']
    assert set(section['text_content']) == set(sections(board)[0]['text_content'])
    assert presentation_lines(section)[0].startswith('• The evaluation uses 16000')
    assert presentation_lines(section)[1].startswith('• HAGS improves recall by 3%')
    assert section['section_title'] == 'HAGS vs. Baselines'
    assert section['importance_level'] == 1
    assert audit['status'] == 'applied'
    assert (state, board) == original


def test_takeaway_first_is_supported_without_erasing_required_context():
    state, board = example()
    board = prepare_board(board, state, [{'section_id': 's', 'narrative_style': 'takeaway_first'}])
    result, _ = refine_editorial(None, candidate(board), board, state, FAMILIES[0], {}, identity_refine)
    assert sections(result['board'])[0]['claim_ids'] == ['r', 'c']
    assert len(sections(result['board'])[0]['text_content']) == 2


def test_visible_source_refill_respects_root_exclusions_and_other_modules():
    state, board = example()
    section = sections(board)[0]
    section['curated_claim_roots'] = ['r', 'c']
    section.update(claim_ids=['r'], text_content=[section['text_content'][0]])
    filled = source_for_fit(board, board, state)
    assert set(sections(filled)[0]['claim_ids']) == {'r', 'c'}
    state['content_recovery_policy'] = {'excluded_claim_roots': [['s', 'c']]}
    protected = source_for_fit(board, board, state)
    assert sections(protected)[0]['claim_ids'] == ['r']


def test_mixed_label_measurement_is_identical_with_and_without_cache():
    from src.layout.editorial import presentation_line_count
    from src.layout.measurement_context import measurement_scope
    text = '• Evaluation setup: The evaluation uses 16000 properties.\n◦ A necessary supporting detail.'
    with measurement_scope({'enabled': False}):
        cold = presentation_line_count(text, 9.5, 'Arial', 44)
    with measurement_scope({'enabled': True}) as context:
        assert presentation_line_count(text, 9.5, 'Arial', 44) == cold
        assert presentation_line_count(text, 9.5, 'Arial', 44) == cold
        assert context.report('completed')['caches']['line']['hits'] >= 1


def test_dependency_cannot_be_lost_by_subsetting_or_verified_replacement():
    state, board = example()
    raw = [{'section_id': 's', 'claim_layout': [
        {'claim_id': 'r', 'kind': 'result', 'requires_claim_ids': ['c']},
        {'claim_id': 'c', 'kind': 'setup'}]}]
    board = prepare_board(board, state, raw)
    claims = {c['claim_id']: c for c in state['verified_claims']['claims']}
    section = deepcopy(sections(board)[0])
    section.update(claim_ids=['r'], text_content=[section['text_content'][0]])
    assert not dependencies_met(section, claims)
    # Refreshing final visible metadata must not erase an omitted prerequisite.
    refreshed = prepare_board({'spatial_content_plan': {'sections': [section]}}, state)
    assert not dependencies_met(sections(refreshed)[0], claims)
    claims['short'] = {'claim_id': 'short', 'root_claim_id': 'c'}
    section['claim_ids'].append('short')
    assert dependencies_met(section, claims)
    options = _content_options(LayoutAgent(), sections(board)[0], zone_width=16, zone_height=28, state=state)
    assert not any(o['section']['claim_ids'] == ['r'] for o in options)


def test_unknown_foreign_and_cyclic_hints_cannot_invent_relationships():
    state, board = example()
    raw = [{'section_id': 's', 'claim_layout': [
        {'claim_id': 'r', 'kind': 'causal_proof', 'requires_claim_ids': ['foreign', {'bad': 1}]},
        {'claim_id': 'c', 'kind': 'setup', 'parent_claim_id': 'foreign'}],
        'title_candidates': ['Causal proof of 99% success', 'HAGS vs. Baselines']}]
    section = sections(prepare_board(board, state, raw))[0]
    assert all(not h['requires_claim_ids'] and h['parent_claim_id'] is None for h in section['editorial']['items'])
    assert choose_title(section) == 'HAGS vs. Baselines'
    raw[0]['claim_layout'] = [{'claim_id': 'r', 'requires_claim_ids': ['c']},
                             {'claim_id': 'c', 'requires_claim_ids': ['r']}]
    cyclic = sections(prepare_board(board, state, raw))[0]
    assert all(h['parent_claim_id'] is None for h in cyclic['editorial']['items'])
    cyclic['claim_ids'] = ['r']
    assert not dependencies_met(cyclic, {c['claim_id']: c for c in state['verified_claims']['claims']})


def test_nested_support_measured_and_rendered_with_same_indent():
    state, board = example()
    board = prepare_board(board, state, [{'section_id': 's', 'claim_layout': [
        {'claim_id': 'c', 'kind': 'setup', 'display_label': 'properties'},
        {'claim_id': 'r', 'kind': 'result', 'parent_claim_id': 'c'}], 'presentation_style': 'topics'}])
    section = sections(board)[0]
    section['editorial']['active'] = True
    section['claim_ids'].reverse()
    section['text_content'].reverse()
    lines = presentation_lines(section)
    assert lines[1].startswith('◦ ')
    agent = LayoutAgent()
    plain = agent._measure_body_text(lines, 16, state)
    edited = agent._measure_body_text(lines, 16, state, editorial=True)
    assert edited['height'] >= plain['height']
    renderer = Renderer()
    renderer.styling_interfaces = {'font_sizes': {'body_text': 44}}
    slide = Presentation().slides.add_slide(Presentation().slide_layouts[6])
    renderer._add_enhanced_textbox(slide, '\n'.join(lines), Inches(1), Inches(1), Inches(16), Inches(10),
                                 'Arial', 44, '#000000', 1.0, editorial=True)
    p = slide.shapes[-1].text_frame.paragraphs[1]
    assert p.level == 1 and p._p.get_or_add_pPr().get('marL') == str(Inches(.30))
    from src.layout.body_presentation import paragraphs
    element = {'content': '\n'.join(lines), 'editorial_body': True, 'id': 's_text',
               'editorial_paragraphs': paragraphs(section)}
    FontAgent()._apply_content_styling(element, state['color_scheme'], {})
    assert '**properties:**' in element['content']


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f: f.family_id)
def test_all_registered_contracts_allow_shared_editorial_without_geometry_exception(family):
    state, board = example()
    assert family.contract.allow_module_grouping
    original = candidate(board)
    result, audit = refine_editorial(None, original, board, state, family, {}, identity_refine)
    assert audit['status'] == 'applied'
    assert result['layout_spec'] == original['layout_spec']
    assert sections(result['board'])[0]['claim_ids'] == ['c', 'r']


def test_extension_styling_works_but_grouping_requires_opt_in():
    state, board = example()
    family = LayoutFamily('new', 'New', 'New', FAMILIES[0].zones, ('general',), contract=FamilyContract(reading='columns', allow_module_grouping=False))
    _, audit = refine_editorial(None, candidate(board), board, state, family, {}, identity_refine)
    assert audit['status'] == 'applied'
    assert not family.contract.allow_module_grouping


def test_new_presentation_keeps_each_important_research_phase():
    from src.layout.editorial import _organize
    from src.layout.design_content import ContentPriorities
    board = _board()
    state = state_for(board)
    board = prepare_board(board, state)
    for section in sections(board):
        section['core_claim_ids'] = [section['claim_ids'][-1]]
        _organize(section)
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    fitted, _, report = fit_family_layout(_MeasuredAgent(), board, state, 'classic_three_column', config=config)
    priorities = ContentPriorities(state, sections(board))
    assert not priorities.missing_important(sections(fitted))
    assert not report['content_quality_hints']['missing_important_role_groups']
    # A short, verified conclusion can be retained without forcing a large module.
    assert any('c4_3' in s['claim_ids'] for s in sections(fitted))


def test_late_core_claim_has_a_compact_prerequisite_complete_option():
    state, board = example()
    section = sections(board)[0]
    section['core_claim_ids'] = ['c']
    options = _content_options(LayoutAgent(), section, zone_width=16, zone_height=28, state=state)
    assert any(o['section']['claim_ids'] == ['c'] for o in options)


def test_thin_module_merges_preserve_sources_claims_and_zone_occupancy():
    state, board = example()
    extra = deepcopy(sections(board)[0])
    extra.update(section_id='other', section_title='Additional Results', claim_ids=['x'],
                 text_content=['A separate supported result.'], core_claim_ids=['x'])
    sections(board).append(extra)
    state['verified_claims']['claims'].append({'claim_id': 'x', 'section_id': 'other', 'text': extra['text_content'][0]})
    state['narrative_plan']['sections'].append({'section_id': 'other', 'narrative_role': 'results'})
    result, audit = refine_editorial(None, candidate(board), board, state, FAMILIES[0], {}, identity_refine)
    assert len(sections(result['board'])) == 1
    assert set(sections(result['board'])[0]['claim_ids']) == {'c', 'r', 'x'}
    assert sections(result['board'])[0]['editorial']['merged_section_ids'] == ['s', 'other']
    assert result['layout_spec']['zones'][0]['section_ids'] == ['s']
    assert audit['trials'][0]['merge']['zone_id'] == 'z'
    source = source_for_fit(board, result['board'], state, include_omitted_modules=True)
    assert len(sections(source)) == 1 and set(sections(source)[0]['claim_ids']) == {'c', 'r', 'x'}


@pytest.mark.parametrize('failure', ['space', 'content', 'compile'])
def test_failed_edit_retains_exact_original_candidate(failure):
    state, board = example()
    baseline = candidate(board)
    def reject(*args, **kwargs):
        trial = deepcopy(args[1])
        if failure == 'compile':
            return None
        if failure == 'space':
            trial['exact_utilization']['z'] = .2
        else:
            sections(trial['board'])[0]['claim_ids'].pop()
        return trial
    result, audit = refine_editorial(None, baseline, board, state, FAMILIES[0], {}, reject)
    assert result is baseline and audit['status'] == 'skipped'
    assert len(audit['trials']) <= 2


@pytest.mark.parametrize('flag', ['fit_locked', 'fixed_layout_topology', 'standalone'])
def test_locked_and_standalone_paths_remain_unchanged(flag):
    state, board = example()
    if flag == 'standalone':
        state['generation_route'] = 'standalone_classic'
    else:
        state[flag] = True
    baseline = candidate(board)
    def forbidden(*args, **kwargs):
        pytest.fail('A locked candidate must not enter editorial refitting')
    result, _ = refine_editorial(None, baseline, board, state, FAMILIES[0], {}, forbidden)
    assert result is baseline


@pytest.mark.parametrize('mode', ['fallback', 'topology', 'validate'])
def test_locked_content_options_preserve_existing_title_and_internal_order(mode):
    state, board = example()
    board = prepare_board(board, state)
    section = sections(board)[0]
    section['editorial']['active'] = True
    section['section_title'] = 'Pinned Heading'
    if mode == 'fallback':
        state['fit_locked'] = True
    elif mode == 'topology':
        state['fixed_layout_topology'] = True
    else:
        state['fit_locked'] = True
    options = _content_options(LayoutAgent(), section, zone_width=16, zone_height=28, state=state)
    full = next(o['section'] for o in options if set(o['section']['claim_ids']) == {'r', 'c'})
    assert full['section_title'] == 'Pinned Heading'
    assert full['claim_ids'] == ['r', 'c']


@pytest.mark.parametrize('fallback_flag', [False, True])
def test_locked_exact_measurement_preserves_existing_editorial_title(fallback_flag):
    from src.layout.families import LayoutArchitect
    from src.layout.feasibility import _exact_refine_candidate
    board = _board()
    state = state_for(board)
    board = prepare_board(board, state)
    for section in sections(board):
        section['editorial']['active'] = True
        section['section_title'] = 'Pinned Heading'
    spec = LayoutArchitect().build({**state, 'story_board': board}, 'classic_three_column')
    state['fit_locked'] = fallback_flag
    result = _exact_refine_candidate(_MeasuredAgent(), {'board': board, 'layout_spec': spec,
        'variant': {}, 'score': (1, 1, 1, 'v'), 'candidate_content_selection': {}},
        deepcopy(board), state, {}, allow_changes=False)
    assert result is not None
    assert all(s['section_title'] == 'Pinned Heading' for s in sections(result['board']))


def test_short_title_tracks_reduced_actual_content_without_cutting_words():
    state, board = example()
    section = sections(board)[0]
    section.update(section_title='Multi-Modal Data Integration and Experimental Setup',
                   claim_ids=['c'], text_content=['The dataset comprises 26700 parcels.'])
    section = sections(prepare_board(board, state))[0]
    assert choose_title(section) == 'Dataset'
    section['section_title'] = 'Hierarchical Reinforcement Learning for Scalable Search'
    section['editorial']['source_title'] = section['section_title']
    section['editorial']['items'] = []
    assert choose_title(section) == 'Hierarchical Reinforcement Learning'


def test_curator_omissions_stay_with_original_source_instead_of_shortest_module():
    index = {'a': {'claim_id': 'a', 'section_id': 'source_a', 'text': 'First fact.'},
             'b': {'claim_id': 'b', 'section_id': 'source_a', 'text': 'Necessary detail.'},
             'x': {'claim_id': 'x', 'section_id': 'source_x', 'text': 'Another topic.'}}
    raw = {'spatial_content_plan': {'sections': [
        {'section_id': 'a', 'claim_ids': ['a']}, {'section_id': 'x', 'claim_ids': ['x']}]}}
    raw['editorial_selection'] = {'items': [{'claim_id': 'b', 'disposition': 'required', 'reason': 'condition'}]}
    result = GroundedCurator()._materialize(raw, index, {}, {}, family_mode=True)
    assert sections(result)[0]['claim_ids'] == ['a', 'b']
    assert sections(result)[1]['claim_ids'] == ['x']


@pytest.mark.parametrize('route', ['optimization_family', 'standalone_classic'])
def test_real_curator_entry_prepares_loop_presentation_without_rewriting_claims(monkeypatch, tmp_path, route):
    from types import SimpleNamespace
    import src.agents.grounded_curator as curator
    state, board = example()
    original = deepcopy(state['verified_claims'])
    raw = deepcopy(board)
    sections(raw)[0].update(text_content=['UNVERIFIED REPLACEMENT'],
                            title_candidates=['HAGS vs. Baselines'])
    response = SimpleNamespace(content=json.dumps(raw), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(curator, 'apply_agent_policy', lambda config, _: config)
    monkeypatch.setattr(curator, 'LangGraphAgent', lambda *args: SimpleNamespace(
        reset=lambda: None, step=lambda _: response))
    state.update(generation_route=route, text_model={}, output_dir=str(tmp_path),
                 tokens=SimpleNamespace(add_text=lambda *_: None))
    GroundedCurator()(state)
    assert not state['errors'] and state['verified_claims'] == original
    section = sections(state['story_board'])[0]
    assert 'UNVERIFIED REPLACEMENT' not in section['text_content']
    if route == 'optimization_family':
        assert section['editorial']['active']
        assert section['claim_ids'] == ['c', 'r']
        assert section['section_title'] == 'HAGS vs. Baselines'
    else:
        assert not section.get('editorial')
        assert section['claim_ids'] == ['r', 'c']


def test_runtime_baseline_is_not_in_report_or_scientific_snapshot():
    board = _board()
    state = state_for(board)
    state['iteration_context']['attempt_id'] = 'a'
    original = deepcopy(state)
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    result = fit_family_layout(_MeasuredAgent(), board, state, 'classic_three_column', config=config)
    assert state == original and isinstance(result, EditorialFitResult)
    assert '_editorial_baseline' not in json.dumps(result[2])
    remember_baseline(state, result)
    assert state['_quality_repair_baseline']['attempt_id'] == 'a'
    from src.workflow.exploration_store import PAPER_FIELDS, DIAGNOSTIC_FIELDS
    assert '_quality_repair_baseline' not in PAPER_FIELDS
    assert '_quality_repair_baseline' not in DIAGNOSTIC_FIELDS


def test_legacy_wording_call_is_charged_before_optimizer_and_not_published_on_failure(tmp_path):
    state, board = example()
    sections(board)[0]['text_content'][0] = 'The authors propose HAGS for the task.'
    state.update(story_board=deepcopy(board), text_model={'provider': 'mock'}, critic_config={
        'capacity_repair': {'max_rounds_per_iteration': 4, 'max_rounds_per_family': 2}})
    directory = tmp_path / 'attempts' / 'one'
    directory.mkdir(parents=True)
    state['iteration_context'].update(layout_family='classic_three_column', attempt_diagnostics_dir=str(directory))
    def rejected(trial, **kwargs):
        assert budget_usage(directory) == (0, 1)
        assert kwargs['board_override'] is board
        trial['verified_content_bank'] = {'claims': [{'claim_id': 'unverified'}]}
        trial['content_revision'] = {'accepted_actions': []}
        return trial
    current = (board, {}, {})
    assert polish_wording(None, state, current, 'classic_three_column', optimizer=rejected) is current
    assert not state.get('verified_content_bank')
    assert state['capacity_repair_report']['editorial_wording']['reason'] == 'no_verified_edit'


def test_wording_refit_never_borrows_another_rounds_same_id_board(monkeypatch):
    import src.layout.feasibility as feasibility
    state, board = example()
    sections(board)[0]['text_content'][0] = 'The authors propose HAGS for the task.'
    state.update(text_model={'provider': 'mock'}, critic_config={'capacity_repair': {
        'max_rounds_per_iteration': 4, 'max_rounds_per_family': 2}},
        story_board={'spatial_content_plan': {'sections': [{
            'section_id': 's', 'claim_ids': ['foreign'], 'text_content': ['FOREIGN BOARD'], 'visual_assets': []}]}})
    base = candidate(board)
    report = {'zone_utilization': {'z': .95}, 'exact_bottom_gaps': {'z': .3},
              'composition_whitespace': {'largest_empty_rectangle_fraction': .04}}
    def verified(trial, **kwargs):
        changed = deepcopy(kwargs['board_override'])
        sections(changed)[0]['claim_ids'][0] = 'v'
        sections(changed)[0]['text_content'][0] = 'HAGS addresses the task.'
        trial.update(story_board=changed, content_revision={'accepted_actions': [{'claim_id': 'r'}]},
                     verified_content_bank={'claims': [{'claim_id': 'v', 'root_claim_id': 'r',
                                                       'text': 'HAGS addresses the task.', 'verified': True}]})
        return trial
    def exact(_agent, source, trial, *_args, **_kwargs):
        assert 'FOREIGN BOARD' not in json.dumps(source)
        assert 'foreign' not in {c for s in sections(source) for c in s['claim_ids']}
        return source, base['layout_spec'], deepcopy(report)
    monkeypatch.setattr(feasibility, 'fit_family_layout', exact)
    result = polish_wording(None, state, (board, base['layout_spec'], report), 'classic_three_column', optimizer=verified)
    assert result[0] != board
    assert sections(result[0])[0]['claim_ids'] == ['v', 'c']
    assert state['capacity_repair_report']['editorial_wording']['status'] == 'applied'


def test_actual_background_preserves_visible_tint_and_resolves_accessible_ink():
    from src.critic.quality import _contrast, ColorQualityEvaluator
    from src.critic.base import CriticContext
    state, board = example()
    state['color_scheme'].update(theme='#8C1D18', mono_dark='#592523', text_on_theme='#FFFFFF',
                                 mono_light='#efe6e6', contrast='#137a7f')
    result, audit = refine_editorial(None, candidate(board), board, state, FAMILIES[0], {}, identity_refine)
    section = sections(result['board'])[0]
    background = section['editorial']['background']
    assert background == '#efe6e6'
    assert _contrast(section['editorial']['accent_color'], background) >= 4.5
    assert _contrast(background, '#ffffff') >= 1.12
    state['optimized_story_board'] = result['board']
    context = CriticContext(state=state, config=load_critic_config())
    evaluation = ColorQualityEvaluator().evaluate(context)
    assert not any(i['issue_id'] == 'COLOR-CONTRAST-INSUFFICIENT' for i in evaluation.issues)


def test_presentation_title_recovers_when_useful_content_is_restored():
    state, board = example()
    section = sections(board)[0]
    section['section_title'] = 'Performance Evaluation: HAGS vs. Baselines'
    board = prepare_board(board, state)
    section = sections(board)[0]
    section['editorial']['active'] = True
    section.update(claim_ids=['c'], text_content=[section['text_content'][1]])
    assert choose_title(section) in ('Evaluation Setup', 'HAGS vs. Baselines')
    section['claim_ids'].append('r')
    section['text_content'].append(state['verified_claims']['claims'][0]['text'])
    assert choose_title(section) == 'HAGS vs. Baselines'


def test_restored_method_broadens_dataset_title_using_mixed_case_source():
    state, board = example()
    section = sections(board)[0]
    section.update(section_title='Multi-Modal Data Integration and Experimental Setup',
                   claim_ids=['c'], text_content=['The dataset comprises 26700 parcels.'])
    board = prepare_board(board, state)
    section = sections(board)[0]
    section['section_title'] = choose_title(section)
    assert section['section_title'] == 'Dataset'
    section['claim_ids'].append('method')
    section['text_content'].append('The method uses multi-modal representation learning to combine visual data and tabular features.')
    section['editorial']['items'].append({'claim_id': 'method', 'kind': '',
                                         'requires_claim_ids': [], 'parent_claim_id': None})
    # Setup is valid vocabulary from the original mixed-case title even when
    # it is absent from the retained sentences. A stale narrow title is unsafe.
    assert choose_title(section) == 'Multi-Modal Data & Setup'


def test_title_candidates_can_use_uppercase_names_from_verified_body():
    state, board = example()
    sections(board)[0]['section_title'] = 'Performance Evaluation'
    board = prepare_board(board, state, [{'section_id': 's', 'title_candidates': ['HAGS']}])
    assert choose_title(sections(board)[0]) == 'HAGS'
