"""Lossless final-Critic input views; no model or tokenizer service is needed."""
from copy import deepcopy

import pytest

from src.workflow.editorial_contract import paper_material
from src.workflow.editorial_critic import _paper_evidence, _render_diagnostics, measurement_evidence


@pytest.fixture
def state():
    return {
        'raw_text': 'The complete paper: geometry_trials is a scientific field name.\n',
        'structured_sections': {'paper_sections': [{'content': 'Organized source material.'}]},
        'narrative_content': {'meta': {'poster_title': 'Full paper title'}},
        'classified_visuals': {'key_visual': 'figure_1'},
        'images': {'1': {'path': '/unused/original.png', 'caption': 'Complete figure caption.'}},
        'editorial_fit': {
            'passed': False, 'status': 'layout_defects', 'completion_reason': 'no_useful_edit',
            'modules': [{'module_id': 'm6', 'overage_inches': 4.381427082666663}],
            'preflight': {'passed': False, 'issues': [{'code': 'PREFLIGHT_POSTER_BOUNDS'}]},
            'composition_whitespace': {'visible_bounds_source': 'mixed_rendered_glyphs_and_planned_children'},
            'geometry_trials': [{'exact_report': {'search_debug': 'Not final evidence.'}}],
        },
        'layout_preflight_report': {'passed': False, 'issues': [{'element_id': 'm6_text'}]},
        'render_fit_report': {'status': 'partial', 'conclusive': False, 'issue_count': 0,
                              'matched_text_count': 11, 'expected_text_count': 12,
                              'unmatched_text_ids': ['m6_text'], 'issues': []},
        'critic_measurement_evidence': {
            'geometry': {'status': 'measured', 'findings': [{'element_id': 'm6_text'}]},
            'visual_assets': {'status': 'unavailable', 'reason': 'Source asset could not be decoded.'},
        },
        'styled_layout': [{'id': 'm6_text', 'content': 'Exact **visible** target.\nSecond line.',
                           'x': 35.202127999999995, 'height': 6.799999999999999}],
        'color_scheme': {'text': '#000000'},
        'color_provenance': {'source': 'affiliation_logo'},
    }


@pytest.mark.parametrize('proofread,identical', [
    ('The uncorrected frst result.\n', True),
    ('The corrected first result.\n', False),
    ('The uncorrected frst result.', False),
])
def test_original_and_advisory_text_are_preserved_exactly(state, proofread, identical):
    state.update(marker_raw_text='The uncorrected frst result.\n', raw_text=proofread,
                 source_extraction_report={'version': 'marker_spelling_review_v1',
                     'status': 'corrected', 'edits': [{'original': 'frst', 'replacement': 'first'}],
                     'rejected_edits': [], 'uncertain': ['A formula needs review.'],
                     'warnings': ['Advisory only.']})
    before = deepcopy(state)
    full = paper_material(state, original=True)
    sent = _paper_evidence(state)
    if identical:
        assert 'proofread_text' not in sent
        assert sent.pop('proofread_text_ref') == 'original_text'
        sent['proofread_text'] = sent['original_text']
    else:
        assert 'proofread_text_ref' not in sent
        assert sent['proofread_text'] == proofread
    assert sent == full  # Resolving the reference restores every original evidence field.
    assert state == before


@pytest.mark.parametrize('marker', [None, ''])
def test_missing_marker_text_keeps_the_existing_full_source_fallback(state, marker):
    state['marker_raw_text'] = marker
    sent = _paper_evidence(state)
    assert sent['original_text'] == state['raw_text']
    if 'proofread_text_ref' in sent:
        assert sent.pop('proofread_text_ref') == 'original_text'
        sent['proofread_text'] = sent['original_text']
    assert sent == paper_material(state, original=True)


def test_final_evidence_remains_complete_while_search_history_stays_local(state):
    before = deepcopy(state)
    sent = _render_diagnostics(state)
    expected = deepcopy(state['editorial_fit'])
    del expected['geometry_trials']
    assert sent['editorial_fit'] == expected
    assert sent['layout_preflight_report'] == state['layout_preflight_report']
    assert sent['render_fit_report'] == state['render_fit_report']
    assert not sent['render_fit_report']['conclusive']
    assert sent['render_fit_report']['unmatched_text_ids'] == ['m6_text']
    measured = measurement_evidence(state)
    assert 'render_diagnostics' not in measured
    assert measured == {
        'measurements': state['critic_measurement_evidence'],
        'authored_elements': state['styled_layout'],
        'color_scheme': state['color_scheme'], 'color_provenance': state['color_provenance'],
    }
    sent['editorial_fit']['modules'].clear()
    measured['authored_elements'].clear()
    assert state == before  # Persisted fit/search reports and rendered content must not be rewritten.


@pytest.mark.parametrize('status', [None, 'unavailable', 'partial'])
def test_absent_or_inconclusive_diagnostics_never_become_success(state, status):
    state['editorial_fit'] = None
    state['render_fit_report'] = None if status is None else {'status': status, 'conclusive': False}
    sent = _render_diagnostics(state)
    assert sent['editorial_fit'] is None
    assert sent['render_fit_report'] == state['render_fit_report']
    assert sent['layout_preflight_report']['passed'] is False
