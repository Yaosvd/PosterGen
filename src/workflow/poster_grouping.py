"""Storage classification only; never changes scores or generation decisions."""
import math

VERSION = 'poster_score_groups_v1'
THRESHOLD = 80
GROUPS = ('high_score', 'low_score', 'evaluation_failed')


def valid_score(value):
    return type(value) in (int, float) and 0 <= value <= 100 and math.isfinite(value)


def complete_score(report):
    """Use completion evidence, not a surviving numeric score from a partial review."""
    if not isinstance(report, dict) or report.get('evaluation_status') != 'complete':
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


def poster_group(result, report):
    if (result.get('status') != 'scored' or not complete_score(report)
            or not valid_score(result.get('score')) or result['score'] != report['overall_score']):
        return 'evaluation_failed'
    return 'high_score' if result['score'] >= THRESHOLD else 'low_score'


def grouping_policy():
    return {'version': VERSION, 'threshold': THRESHOLD, 'high_score_inclusive': True,
            'groups': list(GROUPS)}
