"""Optional grounded cues, joint panel/ink colors and bounded prose variants."""

from copy import deepcopy

import pytest
from pptx import Presentation
from pptx.util import Inches

from src.agents.content_optimizer import GroundedContentOptimizer
from src.agents.color_agent import ColorAgent
from src.agents.font_agent import FontAgent
from src.agents.layout_agent import LayoutAgent
from src.agents.renderer import Renderer
from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.quality import ColorQualityEvaluator, _contrast
from src.layout.body_presentation import extract_label, paragraphs, wording_issues
from src.layout.editorial import _organize, prepare_board, presentation_lines, presentation_line_count
from src.layout.emphasis import resolve_emphasis
from src.layout.measurement_context import measurement_scope
from test_content_optimizer import _base_state
from test_poster_editorial import example, sections


def topic_board():
    state, board = example()
    raw = [{'section_id': 's', 'presentation_style': 'topics', 'claim_layout': [
        {'claim_id': 'r', 'kind': 'result', 'display_label': 'uniform costs', 'requires_claim_ids': ['c']},
        {'claim_id': 'c', 'kind': 'setup', 'display_label': 'random selections'}]}]
    board = prepare_board(board, state, raw)
    _organize(sections(board)[0])
    return state, board


@pytest.mark.parametrize('value', ['Novel guarantee', 'Causal effect', 'significant improvement',
                                 'foreign words', '**recall**', 'recall: 99%', {'text': 'recall'}])
def test_unsupported_or_assertive_cues_are_removed(value):
    assert extract_label(value, 'No significant improvement or causal effect is guaranteed for recall.') == ''


def test_labels_are_local_optional_extracts_not_role_names():
    state, board = topic_board()
    section = sections(board)[0]
    assert presentation_lines(section)[0].startswith('• random selections: ')
    assert presentation_lines(section)[1].startswith('• uniform costs: ')
    assert 'Finding:' not in '\n'.join(presentation_lines(section))
    # Classification does not force a cue even for a wrong old role hint.
    section['editorial']['presentation_style'] = 'plain'
    section['editorial']['items'][0]['kind'] = 'definition'
    assert all('Definition:' not in line for line in presentation_lines(section))
    assert not extract_label('HAGS', 'HAGS improves recall.')
    assert not extract_label('recall', 'HAGS improves recall.', 'Recall')
    assert state['verified_claims']['claims'][0]['text'] in section['text_content']


@pytest.mark.parametrize('bad_style', [[], {}, True, 'unverified_prose'])
def test_malformed_presentation_fields_fall_back_without_inserting_prose(bad_style):
    state, board = example()
    result = prepare_board(board, state, [{'section_id': 's', 'presentation_style': bad_style,
        'claim_layout': [{'claim_id': 'r', 'kind': [], 'display_label': {'body': 'new prose'}, 'step_index': True}]}])
    section = sections(result)[0]
    _organize(section)
    assert section['editorial']['presentation_style'] == 'plain'
    assert set(section['text_content']) == set(sections(board)[0]['text_content'])
    assert 'new prose' not in '\n'.join(presentation_lines(section))


def test_replacement_subset_and_merger_revalidate_local_cues():
    state, board = topic_board()
    section = sections(board)[0]
    state['verified_content_bank'] = {'claims': [{'claim_id': 'v', 'root_claim_id': 'r',
        'text': 'HAGS improves recall compared with the baseline.', 'verified': True}]}
    section['claim_ids'][1] = 'v'
    section['text_content'][1] = state['verified_content_bank']['claims'][0]['text']
    replaced = sections(prepare_board(board, state))[0]
    assert 'uniform costs:' not in '\n'.join(presentation_lines(replaced))
    # A foreign module's label cannot survive simply because its ID is reused.
    replaced['editorial']['items'][0]['display_label'] = 'unrelated dataset'
    assert 'unrelated dataset' not in '\n'.join(presentation_lines(replaced))


def test_real_step_indices_preserve_order_and_incomplete_sequence_is_plain():
    state, board = example()
    board = prepare_board(board, state, [{'section_id': 's', 'presentation_style': 'steps',
        'claim_layout': [{'claim_id': 'r', 'step_index': 2}, {'claim_id': 'c', 'step_index': 1}]}])
    section = sections(board)[0]
    _organize(section)
    assert section['claim_ids'] == ['c', 'r']
    assert presentation_lines(section)[0].startswith('1) ')
    assert presentation_lines(section)[1].startswith('2) ')
    section['claim_ids'] = ['r']
    section['text_content'] = [section['text_content'][1]]
    assert presentation_lines(section)[0].startswith('• ')


def test_legacy_locked_description_keeps_historical_labels():
    state, board = example()
    section = sections(prepare_board(board, state))[0]
    section['editorial'].update(version='poster_editorial_v3', active=True)
    assert presentation_lines(section)[0].startswith('• Finding: ')


def test_dynamic_cues_share_measurement_markup_and_actual_pptx_runs(tmp_path):
    state, board = topic_board()
    section = sections(board)[0]
    description = paragraphs(section)
    text = '\n'.join(presentation_lines(section))
    with measurement_scope({'enabled': False}):
        cold = presentation_line_count(text, 8, 'Arial', 44, description)
    with measurement_scope({'enabled': True}) as ctx:
        assert presentation_line_count(text, 8, 'Arial', 44, description) == cold
        assert presentation_line_count(text, 8, 'Arial', 44, description) == cold
        before = ctx.report('completed')['caches']['line']['computed']
        different = deepcopy(description)
        different[0]['label'] = ''
        presentation_line_count(text, 8, 'Arial', 44, different)
        assert ctx.report('completed')['caches']['line']['computed'] > before
    element = {'id': 's_text', 'content': text, 'editorial_body': True,
               'editorial_paragraphs': description}
    FontAgent()._apply_content_styling(element, state['color_scheme'], {
        's': {'bold_contrast': ['HAGS'], 'bold': ['recall'], 'italic': []}})
    assert '**uniform costs:**' in element['content']
    assert '<color:' in element['content']
    from utils.text_formatting import editable_text_parts
    assert '\n'.join(editable_text_parts(element['content'])[0]) == text
    pptx = Presentation()
    pptx.slide_width, pptx.slide_height = Inches(20), Inches(20)
    slide = pptx.slides.add_slide(pptx.slide_layouts[6])
    renderer = Renderer()
    renderer.styling_interfaces = {'font_sizes': {'body_text': 44}}
    renderer._add_enhanced_textbox(slide, element['content'], Inches(1), Inches(1),
                                 Inches(16), Inches(14), 'Arial', 44, '#000000', 1, editorial=True)
    path = tmp_path / 'cues.pptx'
    pptx.save(path)
    saved = Presentation(path).slides[0].shapes[0]
    assert saved.text == text
    assert any(run.font.bold and 'uniform costs:' in run.text for p in saved.text_frame.paragraphs for run in p.runs)


@pytest.mark.parametrize('theme,light,accent', [
    ('#8A1515', '#efe6e6', '#137f7f'), ('#15468a', '#e6eaef', '#7f6513'),
    ('#268a15', '#e7efe6', '#79137f'), ('#808080', '#eeeeee', '#777777')])
def test_joint_colors_visible_accessible_and_deterministic(theme, light, accent):
    palette = {'theme': theme, 'mono_light': light, 'text': '#000000', 'contrast': accent}
    original = deepcopy(palette)
    resolved, report = resolve_emphasis(palette)
    assert report['status'] == 'resolved'
    assert _contrast(resolved['background'], '#ffffff') >= 1.12
    for ink in (resolved['text_color'], resolved['accent_color']):
        assert _contrast(ink, '#ffffff') >= 4.5
        assert _contrast(ink, resolved['background']) >= 4.5
    assert (resolved, report) == resolve_emphasis(palette)
    assert palette == original
    if theme == '#8A1515':
        assert resolved['background'] == light
        assert resolved['accent_color'] != accent


def test_invalid_palette_and_impossible_threshold_have_explicit_fallback():
    assert resolve_emphasis({'mono_light': '#gggggg'})[0] is None
    palette = {'mono_light': '#eeeeee', 'text': '#000000', 'contrast': '#777777'}
    resolved, report = resolve_emphasis(palette, {'evaluators': {'color_quality': {'minimum_contrast_ratio': 21}}})
    assert resolved is None and report['reason'] == 'no_visible_accessible_pair'


@pytest.mark.parametrize('route,locked', [('optimization_family', False), ('optimization_family', True),
                                         ('standalone_classic', False)])
def test_color_agent_joint_palette_respects_route_and_strict_locks(tmp_path, route, locked):
    agent = ColorAgent()
    agent._extract_theme_from_visuals = lambda _: '#8A1515'
    agent._save_color_scheme = lambda _: None
    state = {'generation_route': route, 'output_dir': str(tmp_path), 'errors': [],
             'iteration_context': {'generation_purpose': 'explore'}, 'fit_locked': locked}
    agent(state)
    assert not state['errors']
    assert ('emphasis_resolution' in state['color_provenance']) == (route == 'optimization_family' and not locked)
    if route == 'optimization_family' and not locked:
        assert _contrast(state['color_scheme']['contrast'], state['color_scheme']['mono_light']) >= 4.5


def test_unresolvable_emphasis_does_not_render_a_stale_unsafe_panel():
    from src.layout.editorial import _emphasize
    state, board = topic_board()
    state['critic_config'] = {'evaluators': {'color_quality': {'minimum_contrast_ratio': 21}}}
    section = sections(board)[0]
    section.update(importance_level=1)
    section['editorial'].update(background='#eeeeee', accent_color='#ffffff')
    _emphasize(board, state, {'zones': []})
    assert section['editorial']['emphasis_disabled']
    assert 'background' not in section['editorial']
    pptx = Presentation()
    slide = pptx.slides.add_slide(pptx.slide_layouts[6])
    Renderer()._render_section_container(slide, {'x': 0, 'y': 0, 'width': 5, 'height': 5,
        'importance_level': 1, 'emphasis_disabled': True}, state)
    from pptx.enum.dml import MSO_FILL_TYPE
    assert slide.shapes[0].fill.type == MSO_FILL_TYPE.BACKGROUND


def test_color_critic_checks_actual_overridden_ink_and_reports_faint_panel():
    state, board = topic_board()
    section = sections(board)[0]
    state.update(optimized_story_board=board)
    state['color_scheme'].update(theme='#8A1515', mono_dark='#562222', text_on_theme='#ffffff')
    state['styled_layout'] = [
        {'type': 'section_container', 'section_id': 's', 'importance_level': 1, 'emphasis_background': '#efe6e6'},
        {'type': 'text', 'section_id': 's', 'editorial_body': True, 'font_color': '#000000',
         'content': '• <color:#ffffff>HAGS</color> improves recall.'}]
    evaluation = ColorQualityEvaluator().evaluate(CriticContext(state=state, config=load_critic_config()))
    assert not evaluation.passed
    assert any(i['issue_id'] == 'COLOR-CONTRAST-INSUFFICIENT' for i in evaluation.issues)
    # A dense module's flat-body fallback must remain covered too.
    state['styled_layout'][1].pop('editorial_body')
    evaluation = ColorQualityEvaluator().evaluate(CriticContext(state=state, config=load_critic_config()))
    assert not evaluation.passed
    state['styled_layout'][1]['content'] = '• HAGS improves recall.'
    state['styled_layout'][0]['emphasis_background'] = '#fbf9f9'
    evaluation = ColorQualityEvaluator().evaluate(CriticContext(state=state, config=load_critic_config()))
    assert evaluation.passed
    assert any(i['issue_id'] == 'COLOR-EMPHASIS-FAINT' for i in evaluation.issues)


@pytest.mark.parametrize('block', ['meaning', 'style', 'grounding', 'disabled', 'excluded', 'foreign', 'planner'])
def test_style_variants_fail_closed_and_do_not_publish_banks(tmp_path, block):
    state = _base_state(tmp_path)
    original = deepcopy(state['verified_claims'])
    optimizer = GroundedContentOptimizer()
    optimizer._verify_candidate = lambda _s, c, _b: ({**c, 'verified': True}, {}) if block != 'grounding' else (None, {})
    def model(_state, prompt, _payload):
        if prompt == optimizer.prompt:
            return {'candidates': [{'text': 'The method and result remain directly explained in this research poster.',
                                    'evidence_ids': ['e1']}]}
        return {'grounded': True, 'meaning_preserved': block != 'meaning', 'style_improved': block != 'style'}
    optimizer._model_json = model
    if block == 'disabled':
        state['content_selection']['disabled_claim_ids'] = ['c1']
    if block == 'excluded':
        state['content_recovery_policy'] = {'excluded_claim_roots': [['results', 'c1']]}
    action = {'operation': 'create_style_variant', 'section_id': 'results', 'claim_id': 'c2' if block == 'foreign' else 'c1'}
    board = deepcopy(state['story_board'])
    if block == 'planner':
        state['revision_plan'] = {'content_actions': [action]}
        optimizer(state, save=False)
    else:
        optimizer(state, board_override=board, actions_override=[action], save=False)
    assert state['verified_content_bank']['claims'] == []
    assert state['story_board'] == board and state['verified_claims'] == original


def test_style_variant_may_be_longer_but_compaction_still_must_shorten(tmp_path):
    state = _base_state(tmp_path)
    base = deepcopy(state)
    original = deepcopy(state['verified_claims'])
    optimizer = GroundedContentOptimizer()
    replacement = 'The method and result are explained directly while retaining every necessary condition.'
    assert len(replacement) > len(original['claims'][0]['text'])
    optimizer._model_json = lambda _s, prompt, _: ({'candidates': [{'text': replacement, 'evidence_ids': ['e1']}]}
        if prompt == optimizer.prompt else {'grounded': True, 'meaning_preserved': True, 'style_improved': True})
    optimizer._verify_candidate = lambda _s, c, _b: ({**c, 'verified': True}, {})
    action = {'operation': 'create_style_variant', 'section_id': 'results', 'claim_id': 'c1'}
    optimizer(state, board_override=state['story_board'], actions_override=[action], save=False)
    assert state['content_revision']['accepted_actions']
    assert state['verified_claims'] == original
    variant = state['verified_content_bank']['claims'][0]
    assert variant['root_claim_id'] == 'c1' and variant['variant_kind'] == 'poster_prose'
    assert sections(state['story_board'])[0]['text_content'] == [replacement]
    action['operation'] = 'create_compact_variant'
    optimizer(base, board_override=base['story_board'], actions_override=[action], save=False)
    assert not base['verified_content_bank']['claims']


def test_existing_prose_variant_is_reverified_without_regeneration_or_bank_mutation(tmp_path):
    state = _base_state(tmp_path)
    variant = {'claim_id': 'v', 'root_claim_id': 'c1', 'text': 'The method explains the result.',
               'evidence_ids': ['e1'], 'verified': True, 'variant_kind': 'poster_prose'}
    state['verified_content_bank']['claims'] = [deepcopy(variant)]
    optimizer = GroundedContentOptimizer()
    seen = []
    optimizer._verify_candidate = lambda _s, c, _b: (seen.append(c['claim_id']) or c, {})
    def audit(_s, prompt, _):
        assert prompt == optimizer.editorial_prompt
        return {'grounded': True, 'meaning_preserved': True, 'style_improved': True}
    optimizer._model_json = audit
    optimizer(state, board_override=state['story_board'], actions_override=[{
        'operation': 'create_style_variant', 'section_id': 'results', 'claim_id': 'c1'}], save=False)
    assert seen == ['v']
    assert state['verified_content_bank']['claims'] == [variant]
    assert sections(state['story_board'])[0]['claim_ids'] == ['v']


def test_wording_hints_do_not_treat_attributed_related_work_as_automatic_rewrite():
    assert wording_issues('The authors propose a method.') == ['review_voice']
    assert wording_issues('The paper presents a method.') == ['review_voice']
    assert wording_issues('It is important to note that the model uses a policy.') == ['indirect_opening']
    assert not wording_issues('Smith et al. introduced the baseline used in this comparison.')
