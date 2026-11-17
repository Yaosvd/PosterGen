"""Storage classification only; never changes scores or generation decisions."""
import math

VERSION = 'poster_score_groups_v2'
# Historical percentage reports retain their original threshold. New reports use
# their frozen scoring policy, never this compatibility constant.
THRESHOLD = 80
GROUPS = ('high_score', 'low_score', 'evaluation_failed')


def valid_score(value, maximum=100):
    return type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value)



def _legacy_percentage_report(report):
    """Missing method is legacy only when no new-contract marker is present."""
    if report.get('scoring_method') not in (None, '', 'model_submetrics_v1'):
        return False
    if any(report.get(key) is not None for key in
           ('scoring_policy', 'scoring_policy_digest', 'score_maximum', 'high_score_threshold', 'submetric_grades')):
        return False
    if type(report.get('schema_version')) is int and report['schema_version'] >= 10:
        return False
    return not str(report.get('rubric_version', '')).endswith('_discrete')

def complete_score(report):
    """Use completion evidence, not a surviving numeric score from a partial review."""
    if not isinstance(report, dict):
        return False
    from src.critic.scoring import METHOD, complete_grade_report
    method = report.get('scoring_method')
    if method == METHOD:
        return complete_grade_report(report)
    if not _legacy_percentage_report(report):
        return False
    if report.get('evaluation_status') != 'complete':
        return False
    if not valid_score(report.get('overall_score')):
        return False
    if report.get('required_dimensions_present') is False:
        return False
    stages = report.get('assessment_stages')
    if stages is not None and (not isinstance(stages, dict) or any(
            not isinstance(stages.get(stage), dict) or stages[stage].get('status') != 'complete'
            for stage in ('content', 'visual'))):
        return False
    if report.get('scoring_method') == 'model_submetrics_v1':
        # Follow the report's frozen rubric, not today's potentially different weights.
        policy = report.get('aggregation_policy') or {}
        if not isinstance(policy, dict):
            return False
        dimensions = policy.get('dimensions') or {}
        if not isinstance(dimensions, dict) or not dimensions or stages is None:
            return False
        scores = report.get('dimension_scores') or {}
        leaves = report.get('submetric_scores') or {}
        assessments = report.get('submetric_assessments') or {}
        if not all(isinstance(value, dict) for value in (scores, leaves, assessments)):
            return False
        for name, dimension in dimensions.items():
            if not valid_score(scores.get(name)) or not isinstance(dimension, dict):
                return False
            expected = dimension.get('submetrics')
            if not isinstance(expected, dict) or not expected:
                return False
            for leaf in expected:
                assessment = assessments.get(leaf)
                if (not valid_score(leaves.get(leaf)) or not isinstance(assessment, dict)
                        or assessment.get('assessment_status') not in {'assessed', 'uncertain'}
                        or not valid_score(assessment.get('score'))):
                    return False
    return True


def score_metadata(report):
    """Describe a report's scale without rewriting or inferring from its score."""
    from src.critic.scoring import METHOD, RUBRIC_VERSION, validate_policy_snapshot
    report = report if isinstance(report, dict) else {}
    method = report.get('scoring_method')
    if method == METHOD:
        try:
            policy = validate_policy_snapshot(report.get('scoring_policy'))
        except (ValueError, TypeError, KeyError):
            policy = None
        return {'scoring_method': method,
                'rubric_version': RUBRIC_VERSION if policy else None,
                'scoring_policy_digest': policy['digest'] if policy else None,
                'score_maximum': policy['maximum_score'] if policy else None,
                'high_score_threshold': policy['high_score_threshold'] if policy else None}
    legacy = _legacy_percentage_report(report)
    return {'scoring_method': method or ('legacy_percentage' if legacy else 'unknown'),
            'rubric_version': report.get('rubric_version'), 'scoring_policy_digest': None,
            'score_maximum': 100 if legacy else None,
            'high_score_threshold': THRESHOLD if legacy else None}


def poster_group(result, report):
    if (not isinstance(result, dict) or result.get('status') != 'scored' or not complete_score(report)
            or not valid_score(result.get('score'), score_metadata(report)['score_maximum'])
            or result['score'] != report['overall_score']):
        return 'evaluation_failed'
    metadata = score_metadata(report)
    from src.critic.scoring import METHOD
    if report.get('scoring_method') == METHOD:
        keys = ('scoring_method', 'rubric_version', 'scoring_policy_digest',
                'score_maximum', 'high_score_threshold')
        if type(result.get('score')) is not int or any(
                type(result.get(key)) is not type(metadata[key]) or result.get(key) != metadata[key]
                for key in keys):
            return 'evaluation_failed'
    return 'high_score' if result['score'] >= metadata['high_score_threshold'] else 'low_score'


def grouping_policy(report=None):
    if report is None:
        from src.critic.scoring import METHOD, current_policy
        report = {'scoring_method': METHOD, 'scoring_policy': current_policy()}
    metadata = score_metadata(report)
    return {'version': VERSION if metadata['scoring_method'] == 'model_grades_v1' else 'poster_score_groups_v1',
            'threshold': metadata['high_score_threshold'], 'maximum_score': metadata['score_maximum'],
            'scoring_method': metadata['scoring_method'], 'scoring_policy_digest': metadata['scoring_policy_digest'],
            'high_score_inclusive': True, 'groups': list(GROUPS)}
