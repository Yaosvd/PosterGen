"""Approved nine-important / fourteen-secondary grade and archival contracts."""
from copy import deepcopy
import math

import pytest

from src.config.critic_config import load_critic_config, validate_editorial_scoring
from src.critic.base import EvaluationResult
from src.critic.engine import PosterCritic
from src.critic.scoring import (METHOD, IMPORTANT, SOURCES, current_policy,
    complete_grade_report, validate_policy_snapshot)


def make_report(grades=None):
    grades = grades or {key: 3 for key in SOURCES}
    results = [EvaluationResult(source, METHOD, False, True,
        metadata={'assessment_stage': {'stage': 'visual' if source == 'visual' else 'content', 'status': 'complete'},
                  'submetric_assessments': {key: {'score': grades[key],
            'assessment_status': 'assessed', 'reason': 'Offline evidence',
            'evidence': [{'observation': 'Offline fixture'}], 'uncertainty': ''}
            for key in SOURCES if SOURCES[key] == source}})
        for source in ('grounding', 'information_narrative', 'visual')]
    return PosterCritic(load_critic_config(), evaluators=[])._build_report({}, results)


@pytest.mark.parametrize('grade,total', [(0, 0), (1, 32), (2, 64), (3, 96)])
def test_all_grades_exact_totals_and_complete_report(grade, total):
    report = make_report(dict.fromkeys(SOURCES, grade))
    assert report['overall_score'] == total
    assert report['score_maximum'] == 96 and report['high_score_threshold'] == 82
    assert report['presentation_score_maximum'] == 90
    assert report['presentation_quality_score'] == total - grade * 2
    assert complete_grade_report(report)
    assert all(row['score'] == grade for row in report['submetric_assessments'].values())


def test_targets_and_compensation_have_no_hidden_gates():
    grades = {key: 3 if key in IMPORTANT else 2 for key in SOURCES}
    report = make_report(grades)
    assert report['overall_score'] == 82 and report['reference_passed']
    grades['font_legibility'] = 1
    report = make_report(grades)
    assert report['overall_score'] == 81 and not report['reference_passed']
    report = make_report({key: 0 if key == 'scientific_integrity' else 3 for key in SOURCES})
    assert report['overall_score'] == 90 and report['reference_passed']
    assert complete_grade_report(report)


@pytest.mark.parametrize('bad', [True, False, 1.0, 2.5, '3', -1, 4, 85, math.nan, math.inf, None])
def test_aggregation_rejects_invalid_grades_without_imputation(bad):
    grades = dict.fromkeys(SOURCES, 3)
    grades['scientific_integrity'] = bad
    report = make_report(grades)
    assert report['overall_score'] is None
    assert report['evaluation_status'] == 'failed'
    assert not report['reference_passed'] and not complete_grade_report(report)
    assert 'scientific_integrity' not in report['submetric_scores']


@pytest.mark.parametrize('field,value', [('maximum_score', 100), ('maximum_score', 96.0),
    ('high_score_threshold', 80), ('version', True), ('method', 'unknown'), ('digest', 'modified')])
def test_policy_snapshot_is_strict_and_versioned(field, value):
    policy = current_policy()
    policy[field] = value
    with pytest.raises(ValueError):
        validate_policy_snapshot(policy)


def test_policy_copy_and_all_configured_classifications():
    policy = current_policy()
    assert len(policy['criteria']) == 23
    assert sum(c['importance'] == 'important' for c in policy['criteria'].values()) == 9
    assert policy['dimension_maxima'] == {'scientific_integrity': 6, 'content_quality': 30,
        'layout_integrity': 15, 'readability': 6, 'visual_hierarchy': 15, 'visual_balance': 9, 'aesthetics': 15}
    policy['criteria'].clear()
    assert len(current_policy()['criteria']) == 23
    config = load_critic_config()
    assert 'quality_reference' not in config
    assert all('weight' not in row and 'minimum' not in row for row in config['dimensions'].values())
    config['editorial_scoring']['dimensions']['readability']['submetrics']['font_legibility'] = 'important'
    with pytest.raises(ValueError):
        validate_editorial_scoring(config['editorial_scoring'], config['dimensions'])


@pytest.mark.parametrize('mutation', ['score', 'float_total', 'maximum', 'threshold', 'source', 'grade',
    'points', 'dimension', 'nested_score', 'nested_policy', 'missing', 'extra', 'raw', 'duplicate_source',
    'missing_evidence', 'missing_contribution', 'method', 'schema_version', 'system_version'])
def test_report_verification_recomputes_all_sources_and_metadata(mutation):
    report = make_report()
    if mutation == 'score': report['overall_score'] = 95
    elif mutation == 'float_total': report['overall_score'] = 96.0
    elif mutation == 'maximum': report['score_maximum'] = 100
    elif mutation == 'threshold': report['high_score_threshold'] = 80
    elif mutation == 'source': report['submetric_assessments']['narrative_flow']['evaluator'] = 'information_narrative'
    elif mutation == 'grade': report['submetric_assessments']['narrative_flow']['grade'] = 2
    elif mutation == 'points': report['submetric_scores']['narrative_flow'] = 3
    elif mutation == 'dimension': report['dimension_scores']['readability'] = 12
    elif mutation == 'nested_score': report['poster_evaluation']['overall_score'] = 95
    elif mutation == 'nested_policy': report['poster_evaluation']['high_score_threshold'] = 80
    elif mutation == 'missing': del report['submetric_assessments']['narrative_flow']
    elif mutation == 'extra': report['submetric_assessments']['new_item'] = {}
    elif mutation == 'raw': report['evaluations'][0]['metadata']['submetric_assessments']['scientific_integrity']['score'] = 0
    elif mutation == 'duplicate_source': report['evaluations'].append(deepcopy(report['evaluations'][0]))
    elif mutation == 'missing_evidence': report['submetric_assessments']['scientific_integrity']['evidence'] = []
    elif mutation == 'missing_contribution': report['poster_evaluation']['dimension_source_contributions']['readability'].clear()
    elif mutation == 'schema_version': report['schema_version'] = 9
    elif mutation == 'system_version': report['critic_system_version'] = 'unknown'
    else: report['scoring_method'] = 'unknown'
    assert not complete_grade_report(report)


@pytest.mark.parametrize('status,score,uncertainty,complete', [
    ('uncertain', 2, 'Source extraction limits interpretation', True),
    ('uncertain', 2, '', False),
    ('unavailable', None, 'Missing source evidence', False),
    ('unavailable', 0, 'Missing source evidence', False),
    ('assessed', None, '', False),
])
def test_uncertainty_preserves_real_scores_and_unavailable_never_becomes_zero(status, score, uncertainty, complete):
    initial = make_report()
    results = []
    for entry in initial['evaluations']:
        raw = deepcopy(entry['metadata']['submetric_assessments'])
        if entry['evaluator'] == 'grounding':
            raw['scientific_integrity'].update(score=score, assessment_status=status, uncertainty=uncertainty)
        results.append(EvaluationResult(entry['evaluator'], METHOD, False, True,
                                       metadata={'submetric_assessments': raw,
                                                 'assessment_stage': deepcopy(entry['metadata']['assessment_stage'])}))
    report = PosterCritic(load_critic_config(), evaluators=[])._build_report({}, results)
    assert complete_grade_report(report) is complete
    assert (report['overall_score'] is not None) is complete


def test_physical_diagnostic_failure_does_not_reintroduce_quality_gate():
    initial = make_report()
    results = [EvaluationResult(entry['evaluator'], METHOD, False, True,
                metadata=entry['metadata']) for entry in initial['evaluations']]
    results.append(EvaluationResult('geometry', 'measurement_v1', True, False,
                                   metadata={'measurement': {'status': 'measured'}}))
    report = PosterCritic(load_critic_config(), evaluators=[])._build_report({}, results)
    assert report['hard_gate_passed'] is False
    assert report['overall_score'] == 96 and report['reference_passed'] is True
    assert complete_grade_report(report)


@pytest.mark.parametrize('mutation', ['missing_stages', 'stage_type', 'stage_failed', 'stage_missing_visual',
                                    'source_missing', 'source_type', 'source_failed', 'source_wrong_stage'])
def test_stage_receipts_must_match_complete_assessments(mutation):
    report = make_report()
    if mutation == 'missing_stages': del report['assessment_stages']
    elif mutation == 'stage_type': report['assessment_stages'] = []
    elif mutation == 'stage_failed': report['assessment_stages']['visual']['status'] = 'failed'
    elif mutation == 'stage_missing_visual': del report['assessment_stages']['visual']
    elif mutation == 'source_missing': del report['evaluations'][2]['metadata']['assessment_stage']
    elif mutation == 'source_type': report['evaluations'][2]['metadata']['assessment_stage'] = []
    elif mutation == 'source_failed': report['evaluations'][2]['metadata']['assessment_stage']['status'] = 'failed'
    else: report['evaluations'][2]['metadata']['assessment_stage']['stage'] = 'content'
    assert not complete_grade_report(report)


@pytest.mark.parametrize('progress', [None, [], {'stage': 'content', 'status': 'complete'},
    {'stage': 'visual', 'status': 'failed'}, {'stage': 'visual', 'status': 'skipped'},
    {'stage': 'visual', 'status': 'unknown'}])
def test_engine_never_reports_complete_without_complete_source_stage(progress):
    initial = make_report()
    results = []
    for entry in initial['evaluations']:
        metadata = deepcopy(entry['metadata'])
        if entry['evaluator'] == 'visual':
            metadata['assessment_stage'] = progress
        results.append(EvaluationResult(entry['evaluator'], METHOD, False, True, metadata=metadata))
    report = PosterCritic(load_critic_config(), evaluators=[])._build_report({}, results)
    assert report['overall_score'] is None and report['evaluation_status'] == 'failed'
    assert report['reference_passed'] is False and not complete_grade_report(report)
