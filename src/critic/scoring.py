"""Versioned discrete grades and independently verifiable score snapshots."""
from copy import deepcopy

from utils.persistence import digest

METHOD = 'model_grades_v1'
VERSION = 1
SCHEMA_VERSION = 10
CRITIC_SYSTEM_VERSION = '8.0.0'
RUBRIC_VERSION = 'academic_poster_editorial_v5_discrete'
DIMENSION_CRITERIA = {
    'scientific_integrity': ('scientific_integrity',),
    'content_quality': ('information_coverage', 'information_completeness', 'narrative_flow',
                        'information_depth', 'narrative_structure', 'information_layering',
                        'narrative_conciseness'),
    'layout_integrity': ('layout_robustness', 'layout_structure', 'element_alignment'),
    'readability': ('font_legibility', 'color_contrast'),
    'visual_hierarchy': ('reading_order_quality', 'primary_anchor', 'font_hierarchy', 'font_emphasis'),
    'visual_balance': ('whitespace_quality', 'compositional_balance'),
    'aesthetics': ('color_palette', 'visual_relevance', 'color_hierarchy', 'color_source'),
}
CONTENT_CRITERIA = frozenset(('information_layering', 'information_coverage', 'information_depth',
                            'information_completeness', 'narrative_structure', 'narrative_conciseness'))
IMPORTANT = frozenset(('scientific_integrity', 'information_coverage', 'information_completeness',
                      'narrative_flow', 'layout_robustness', 'layout_structure',
                      'reading_order_quality', 'whitespace_quality', 'visual_relevance'))
SOURCES = {name: ('grounding' if name == 'scientific_integrity' else
                 'information_narrative' if name in CONTENT_CRITERIA else 'visual')
           for names in DIMENSION_CRITERIA.values() for name in names}


def _canonical_snapshot():
    criteria = {}
    for dimension, names in DIMENSION_CRITERIA.items():
        for name in names:
            important = name in IMPORTANT
            criteria[name] = {'dimension': dimension, 'source': SOURCES[name],
                              'importance': 'important' if important else 'secondary',
                              'points': [0, 2, 4, 6] if important else [0, 1, 2, 3],
                              'target_grade': 3 if important else 2}
    maxima = {d: sum(criteria[k]['points'][-1] for k in names)
              for d, names in DIMENSION_CRITERIA.items()}
    targets = {d: sum(criteria[k]['points'][criteria[k]['target_grade']] for k in names)
               for d, names in DIMENSION_CRITERIA.items()}
    policy = {'method': METHOD, 'version': VERSION, 'criteria': criteria,
              'maximum_score': sum(maxima.values()), 'high_score_threshold': sum(targets.values()),
              'dimension_maxima': maxima, 'dimension_targets': targets}
    policy['digest'] = digest(policy)
    return policy


def validate_policy_snapshot(snapshot):
    """Accept only the declared immutable v1 contract, with a valid checksum."""
    if not isinstance(snapshot, dict):
        raise ValueError('Scoring policy snapshot must be an object')
    # Canonical JSON equality also rejects bools/floats impersonating integer fields.
    try:
        if digest(snapshot) != digest(_canonical_snapshot()):
            raise ValueError('Unknown, changed or invalid scoring policy snapshot')
    except (TypeError, OverflowError) as exc:
        raise ValueError('Invalid scoring policy snapshot') from exc
    return deepcopy(snapshot)


def policy_from_settings(settings, dimensions):
    """Build a frozen policy from the production config without importing its loader."""
    expected = _canonical_snapshot()
    if settings.get('method') != METHOD or type(settings.get('version')) is not int or settings['version'] != VERSION:
        raise ValueError('Unknown editorial scoring method/version')
    if (type(settings.get('schema_version')) is not int or settings['schema_version'] != SCHEMA_VERSION
            or settings.get('critic_system_version') != CRITIC_SYSTEM_VERSION
            or settings.get('rubric_version') != RUBRIC_VERSION):
        raise ValueError('Unknown editorial scoring schema/system/rubric version')
    if set(dimensions) != set(DIMENSION_CRITERIA):
        raise ValueError('Editorial scoring must define all seven dimensions')
    configured = settings.get('dimensions')
    if not isinstance(configured, dict) or set(configured) != set(DIMENSION_CRITERIA):
        raise ValueError('Editorial scoring must define all seven dimensions')
    for dimension, names in DIMENSION_CRITERIA.items():
        row = configured[dimension]
        if not isinstance(row, dict) or set(row) != {'submetrics'}:
            raise ValueError('Discrete dimensions contain submetrics, not percentage weights')
        leaves = row['submetrics']
        if not isinstance(leaves, dict) or set(leaves) != set(names):
            raise ValueError('Current Critic requires exactly its 23 model submetrics')
        for name in names:
            if leaves[name] != expected['criteria'][name]['importance']:
                raise ValueError('Criterion importance differs from scoring policy version 1: ' + name)
    return expected


def current_policy(config=None):
    """Return a fresh serializable snapshot; loading stays lazy to avoid cycles."""
    if config is None:
        from src.config.critic_config import load_critic_config
        config = load_critic_config()
    return policy_from_settings(config['editorial_scoring'], config['dimensions'])


def report_policy_metadata(policy=None):
    policy = validate_policy_snapshot(policy if policy is not None else current_policy())
    return {'scoring_method': policy['method'], 'scoring_policy': policy,
            'scoring_policy_digest': policy['digest'], 'score_maximum': policy['maximum_score'],
            'high_score_threshold': policy['high_score_threshold'], 'rubric_version': RUBRIC_VERSION}


def valid_grade_assessment(assessment):
    """Quality zero is valid; missing evidence, uncertainty, or score is not."""
    return (isinstance(assessment, dict)
            and assessment.get('assessment_status') in {'assessed', 'uncertain'}
            and type(assessment.get('score')) is int and 0 <= assessment['score'] <= 3
            and isinstance(assessment.get('reason'), str) and bool(assessment['reason'].strip())
            and isinstance(assessment.get('evidence'), list) and bool(assessment['evidence'])
            and (assessment['assessment_status'] != 'uncertain'
                 or isinstance(assessment.get('uncertainty'), str) and bool(assessment['uncertainty'].strip())))


def _same(value, expected):
    """Compare JSON types as well as values (True must never equal one)."""
    return digest(value) == digest(expected)


def complete_grade_report(report):
    """Fail closed when any score, source, policy, or duplicated metadata disagrees."""
    try:
        if not isinstance(report, dict) or report.get('evaluation_status') != 'complete':
            return False
        if (type(report.get('schema_version')) is not int or report['schema_version'] != SCHEMA_VERSION
                or report.get('critic_system_version') != CRITIC_SYSTEM_VERSION):
            return False
        policy = validate_policy_snapshot(report.get('scoring_policy'))
        meta = report_policy_metadata(policy)
        if any(not _same(report.get(k), v) for k, v in meta.items()):
            return False
        if not _same(report.get('assessment_stages'), {
                stage: {'stage': stage, 'status': 'complete'} for stage in ('content', 'visual')}):
            return False
        criteria = policy['criteria']
        assessments = report.get('submetric_assessments')
        if not isinstance(assessments, dict) or set(assessments) != set(criteria):
            return False
        grades, points = {}, {}
        for key, criterion in criteria.items():
            value = assessments[key]
            if not valid_grade_assessment(value) or value.get('evaluator') != criterion['source']:
                return False
            grade = value['score']
            points[key] = criterion['points'][grade]
            grades[key] = grade
            expected = {'grade': grade, 'points': points[key], 'maximum_score': criterion['points'][-1],
                        'importance': criterion['importance']}
            if any(not _same(value.get(k), v) for k, v in expected.items()):
                return False
        dimensions = {d: sum(points[k] for k in names) for d, names in DIMENSION_CRITERIA.items()}
        total = sum(points.values())
        presentation = total - points['scientific_integrity']
        expected = {**meta, 'submetric_grades': grades, 'submetric_scores': points,
                    'dimension_scores': dimensions, 'overall_score': total,
                    'presentation_quality_score': presentation,
                    'presentation_score_maximum': policy['maximum_score'] - policy['dimension_maxima']['scientific_integrity'],
                    'reference_passed': total >= policy['high_score_threshold'],
                    'required_dimensions_present': True, 'aggregation_policy': policy}
        if any(not _same(report.get(k), v) for k, v in expected.items()):
            return False
        nested = report.get('poster_evaluation')
        if not isinstance(nested, dict) or any(not _same(nested.get(k), v) for k, v in expected.items()):
            return False
        if not _same(nested.get('submetric_assessments'), assessments):
            return False
        sources = {row.get('evaluator'): row for row in report.get('evaluations', [])
                   if row.get('evaluator') in set(SOURCES.values())}
        if set(sources) != set(SOURCES.values()):
            return False
        if len([r for r in report['evaluations'] if r.get('evaluator') in sources]) != len(sources):
            return False
        for source, result in sources.items():
            expected_stage = 'visual' if source == 'visual' else 'content'
            if not _same(result.get('metadata', {}).get('assessment_stage'),
                         {'stage': expected_stage, 'status': 'complete'}):
                return False
            raw = result.get('metadata', {}).get('submetric_assessments', {})
            keys = {k for k, c in criteria.items() if c['source'] == source}
            if set(raw) != keys:
                return False
            for key in keys:
                expected_raw = {k: v for k, v in assessments[key].items()
                                if k not in {'evaluator', 'grade', 'points', 'maximum_score', 'importance'}}
                if not _same(raw[key], expected_raw):
                    return False
        missing = nested.get('missing_score_sources')
        if not _same(missing, {d: [] for d in DIMENSION_CRITERIA}):
            return False
        contributions = {d: [{'evaluator': criteria[k]['source'], 'submetric': k,
                               'grade': grades[k], 'score': points[k],
                               'maximum_score': criteria[k]['points'][-1]}
                              for k in names] for d, names in DIMENSION_CRITERIA.items()}
        return _same(nested.get('dimension_source_contributions'), contributions)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return False
