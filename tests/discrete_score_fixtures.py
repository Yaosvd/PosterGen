"""Offline model-grade inputs passed through the production report aggregator."""
from src.config.critic_config import load_critic_config
from src.critic.base import EvaluationResult
from src.critic.engine import PosterCritic
from src.critic.scoring import SOURCES
from src.workflow.poster_grouping import score_metadata


def grade_report(grade=2, **overrides):
    results = []
    for source in ('grounding', 'information_narrative', 'visual'):
        assessments = {name: {'score': overrides.get(name, grade),
                             'assessment_status': 'assessed', 'reason': 'Offline evidence',
                             'evidence': [{'observation': 'Offline fixture'}], 'uncertainty': ''}
                       for name, owner in SOURCES.items() if owner == source}
        results.append(EvaluationResult(source, 'offline', False, True, metadata={
            'submetric_assessments': assessments, 'assessment_stage': {
                'stage': 'visual' if source == 'visual' else 'content', 'status': 'complete'}}))
    return PosterCritic(load_critic_config(), evaluators=[])._build_report({}, results)


def scored_result(report, **fields):
    return {'status': 'scored', 'score': report['overall_score'], **score_metadata(report), **fields}
