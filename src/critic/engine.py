"""Versioned poster evaluation; reference thresholds never control storage."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext, CriticEvaluator, EvaluationResult, issue
from src.critic.scoring import current_policy, report_policy_metadata, valid_grade_assessment, validate_policy_snapshot
from src.state.poster_state import PosterState
from utils.src.logging_utils import log_agent_info, log_agent_success, log_agent_warning


class PosterCritic:
    """Run independent evaluators, aggregate scores, and build one report."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        evaluators: Optional[Iterable[CriticEvaluator]] = None,
    ) -> None:
        self.name = "critic"
        from src.workflow.editorial_critic import editorial_critic_config, current_evaluators
        self.config = editorial_critic_config(config if config is not None else load_critic_config())
        if evaluators is None:
            evaluators = current_evaluators()
        self.evaluators: List[CriticEvaluator] = list(evaluators)

    def register_evaluator(self, evaluator: CriticEvaluator) -> None:
        """Add or replace an evaluator without changing the aggregator."""

        self.evaluators = [
            current
            for current in self.evaluators
            if current.name != evaluator.name
        ]
        self.evaluators.append(evaluator)

    def __call__(self, state: PosterState) -> PosterState:
        from src.workflow.editorial_critic import assessment_failure
        log_agent_info(self.name, "evaluating rendered poster candidate")
        policy = current_policy(self.config)
        if state.get('scoring_policy') is not None:
            frozen = validate_policy_snapshot(state['scoring_policy'])
            if frozen != policy:
                raise ValueError('Frozen sample scoring policy differs from the evaluator configuration')
        state['scoring_policy'] = policy
        context = CriticContext(state=state, config=self.config)
        results: List[EvaluationResult] = []
        # Rebuild reports from this image/input. Durable request journals, not
        # stale in-memory verdicts, own replay without additional model calls.
        for key in ('critic_measurement_evidence', 'critic_request_identities',
                    '_editorial_content_evaluation', '_editorial_content_input_digest',
                    '_editorial_content_error', '_editorial_visual_evaluation'):
            state.pop(key, None)

        evaluators = self.evaluators
        for evaluator in evaluators:
            settings = self.config["evaluators"].get(evaluator.name, {})
            if not settings.get("enabled", True):
                continue
            stage = {'grounding': 'content', 'information_narrative': 'content',
                     'visual': 'visual'}.get(evaluator.name)
            blocked = state.get('_editorial_content_error')
            content = state.get('_editorial_content_evaluation')
            if stage == 'visual' and content and any(
                    a['score'] is None for a in content['assessments'].values()):
                blocked = 'Required content assessment unavailable'
            if stage and blocked:
                results.append(EvaluationResult(evaluator.name, str(settings.get('version', 'unknown')),
                    bool(settings.get('hard_gate', False)), False,
                    metadata={'assessment_stage': {'stage': stage, 'status': 'skipped',
                              'blocked_by': 'content', 'reason': str(blocked)}}))
                continue
            try:
                results.append(evaluator.evaluate(context))
            except Exception as exc:
                hard_gate = bool(settings.get("hard_gate", False))
                results.append(EvaluationResult(
                    evaluator=evaluator.name,
                    version=str(settings.get("version", "unknown")),
                    hard_gate=hard_gate,
                    passed=not hard_gate,
                    issues=[issue(
                        f"EVALUATOR-{evaluator.name.upper()}-FAILED",
                        severity="critical" if hard_gate else "warning",
                        scope="critic",
                        observation=f"Evaluator {evaluator.name} failed: {exc}",
                        required_outcome="Fix or retry the failed evaluator",
                        allowed_operations=["retry_critic"],
                    )],
                    metadata={'assessment_stage': assessment_failure(exc, stage)} if stage else {},
                ))

        report = self._build_report(state, results)
        if state.get('editorial_version') == 'poster_editorial_v1':
            report['factual_consistency_status'] = state.get('editorial_factual_status', 'unavailable')
            if report['evaluation_status'] != 'complete':
                report['overall_score'] = None
                report['poster_evaluation']['overall_score'] = None
                report['reference_passed'] = False
                report['poster_evaluation']['reference_passed'] = False
        state["critic_report"] = report
        history = state.setdefault("critic_history", [])
        history.append({
            "candidate_id": report["candidate_id"],
            "iteration": report["iteration"],
            "decision": report["decision"],
            "overall_score": report["overall_score"],
            "rejection_summary": report["rejection_summary"],
        })
        history_limit = 50
        if len(history) > history_limit:
            del history[:-history_limit]
        state["current_agent"] = self.name
        self._save_report(state, report)

        if report["reference_passed"]:
            log_agent_success(
                self.name,
                f"sample meets the reference policy ({report['overall_score']:.1f})",
            )
        else:
            log_agent_warning(
                self.name,
                f"sample evaluated ({report['overall_score']}): "
                f"{report['rejection_summary']}",
            )
        return state

    def _build_report(
        self,
        state: PosterState,
        results: List[EvaluationResult],
    ) -> Dict[str, Any]:
        result_by_name = {result.evaluator: result for result in results}
        all_issues: List[Dict[str, Any]] = []
        positives: List[Dict[str, Any]] = []
        evaluator_versions: Dict[str, str] = {}

        for result in results:
            evaluator_versions[result.evaluator] = result.version
            all_issues.extend(result.issues)
            positives.extend(result.positive_patterns)
        policy = current_policy(self.config)
        configured_dimensions = self.config["dimensions"]
        dimension_scores: Dict[str, int] = {}
        source_contributions: Dict[str, List[Dict[str, Any]]] = {}
        missing_score_sources: Dict[str, List[str]] = {}
        for dimension in configured_dimensions:
            contributions = []
            missing = []
            for leaf, criterion in policy['criteria'].items():
                if criterion['dimension'] != dimension:
                    continue
                source = criterion['source']
                result = result_by_name.get(source)
                assessment = ((result.metadata.get('submetric_assessments') or {}).get(leaf)
                              if result else None)
                if not valid_grade_assessment(assessment):
                    missing.append(leaf)
                    continue
                grade = assessment['score']
                contributions.append({'evaluator': source, 'submetric': leaf, 'grade': grade,
                                      'score': criterion['points'][grade],
                                      'maximum_score': criterion['points'][-1]})
            source_contributions[dimension] = contributions
            missing_score_sources[dimension] = missing
            # Incomplete dimensions remain absent: never impute or renormalize.
            if not missing:
                dimension_scores[dimension] = sum(c['score'] for c in contributions)
        overall_score = None if any(missing_score_sources.values()) else sum(dimension_scores.values())
        hard_gate_passed = all(result.passed for result in results if result.hard_gate)
        required_dimensions_present = all(dimension in dimension_scores for dimension in configured_dimensions)
        # Diagnostic failures and individual grades do not impose hidden score gates.
        archive_eligible = overall_score is not None and overall_score >= policy['high_score_threshold']

        unresolved_serious = [item for item in all_issues
                              if str(item.get('severity', '')).lower() in {'critical', 'major'}]

        presentation_quality_score = (None if overall_score is None else
            sum(score for name, score in dimension_scores.items() if name != 'scientific_integrity'))
        presentation_score_maximum = policy['maximum_score'] - policy['dimension_maxima']['scientific_integrity']

        severity_rank = {"critical": 0, "major": 1, "minor": 2, "warning": 3}
        all_issues.sort(key=lambda item: severity_rank.get(item.get("severity"), 4))
        stages = {}
        stage_rank = {'complete': 0, 'skipped': 1, 'failed': 2}
        model_sources = set(self.config['submetric_sources'].values())
        for source in sorted(model_sources):
            result = result_by_name.get(source)
            expected_stage = 'visual' if source == 'visual' else 'content'
            progress = result.metadata.get('assessment_stage') if result else None
            if (not isinstance(progress, dict) or progress.get('stage') != expected_stage
                    or progress.get('status') not in stage_rank
                    or (progress.get('status') == 'complete' and
                        progress != {'stage': expected_stage, 'status': 'complete'})):
                progress = {'stage': expected_stage, 'status': 'failed',
                            'error_kind': 'response_validation', 'error_type': 'InvalidAssessmentStage',
                            'reason': 'Required assessment stage is missing or inconsistent: ' + source,
                            'field_paths': [['evaluations', source, 'metadata', 'assessment_stage']]}
            else:
                progress = deepcopy(progress)
                if progress['status'] == 'failed':
                    progress.setdefault('error_kind', 'response_validation')
                    progress.setdefault('reason', 'Model assessment did not complete')
                elif progress['status'] == 'skipped':
                    progress.setdefault('blocked_by', 'content')
                    progress.setdefault('reason', 'Required model assessment was skipped')
            if stage_rank[progress['status']] > stage_rank.get(
                    stages.get(expected_stage, {}).get('status'), -1):
                stages[expected_stage] = progress
        required_stages_complete = all(p['status'] == 'complete' for p in stages.values())
        if not required_stages_complete:
            overall_score = presentation_quality_score = None
            archive_eligible = False
        failures = [p for p in stages.values() if p['status'] == 'failed']
        failure_summary = [p['stage'] + ' assessment failed [' + p['error_kind'] + ']: ' + p['reason']
                           for p in failures]
        failure_summary.extend(p['stage'] + ' assessment not run: blocked by ' + p['blocked_by'] +
                               (': ' + p['reason'] if not failures else '')
                               for p in stages.values() if p['status'] == 'skipped')
        summary_parts = [
            item.get("observation", "")
            for item in all_issues[:3]
            if item.get("observation")
        ]
        rejection_summary = "" if archive_eligible else (
            "; ".join(failure_summary or summary_parts)
            if failure_summary or summary_parts
            else "Candidate did not meet the configured quality thresholds"
        )

        candidate = state.get("current_candidate") or {}
        iteration_context = state.get("iteration_context") or {}
        assessments = {}
        for leaf, criterion in policy['criteria'].items():
            source = criterion['source']
            result = result_by_name.get(source)
            assessment = ((result.metadata.get('submetric_assessments') or {}).get(leaf)
                          if result else None)
            if assessment is not None:
                value = {'evaluator': source, **deepcopy(assessment),
                         'grade': assessment.get('score'),
                         'points': criterion['points'][assessment['score']] if valid_grade_assessment(assessment) else None,
                         'maximum_score': criterion['points'][-1], 'importance': criterion['importance']}
                assessments[leaf] = value
        submetric_scores = {k: v['points'] for k, v in assessments.items() if valid_grade_assessment(v)}
        submetric_grades = {k: v['grade'] for k, v in assessments.items() if valid_grade_assessment(v)}
        policy_metadata = report_policy_metadata(policy)
        poster_evaluation = {
            "overall_score": overall_score,
            "presentation_quality_score": presentation_quality_score,
            "presentation_score_maximum": presentation_score_maximum,
            "dimension_scores": dimension_scores,
            "submetric_scores": submetric_scores,
            "submetric_grades": submetric_grades,
            "dimension_source_contributions": source_contributions,
            "missing_score_sources": missing_score_sources,
            "hard_gate_passed": hard_gate_passed,
            "required_dimensions_present": required_dimensions_present,
            "reference_passed": archive_eligible,
            "unresolved_serious_issue_count": len(unresolved_serious),
        }
        report = {
            "schema_version": self.config['schema_version'],
            "critic_system_version": self.config["critic_system_version"],
            "rubric_version": self.config["rubric_version"],
            "evaluation_status": "failed" if (any(
                str(item.get('issue_id', '')).endswith('-FAILED') and
                str(item.get('issue_id', '')).startswith('EVALUATOR-') for item in all_issues)
                or any(missing_score_sources.values()) or not required_dimensions_present
                or not required_stages_complete) else "complete",
            "evaluator_versions": evaluator_versions,
            "candidate_id": candidate.get("candidate_id", "unknown"),
            "iteration": int(iteration_context.get("iteration", 0)),
            "strategy": iteration_context.get("strategy", "single_pass"),
            "layout_family": (
                (state.get("layout_spec") or {}).get("family_id")
                or iteration_context.get("layout_family")
            ),
            "decision": "evaluated",
            "reference_passed": archive_eligible,
            "hard_gate_passed": hard_gate_passed,
            "presentation_quality_score": presentation_quality_score,
            "presentation_score_maximum": presentation_score_maximum,
            "required_dimensions_present": required_dimensions_present,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "submetric_scores": submetric_scores,
            "submetric_grades": submetric_grades,
            "poster_evaluation": poster_evaluation,
            "issues": all_issues,
            "positive_patterns": positives,
            "rejection_summary": rejection_summary,
            "evaluations": [result.to_dict() for result in results],
        }
        content = state.get('_editorial_content_evaluation') or {}
        visual = state.get('_editorial_visual_evaluation') or {}
        details = {
            'scoring_method': self.config['scoring_method'],
            'submetric_assessments': assessments,
            'aggregation_policy': deepcopy(policy),
            **policy_metadata,
            'content_dependencies': deepcopy(content.get('content_dependencies')),
            'reading_review': deepcopy(visual.get('reading_review')),
            'measurement_evidence': deepcopy(state.get('critic_measurement_evidence') or {}),
            'request_identities': deepcopy(state.get('critic_request_identities') or {}),
            'assessment_stages': stages,
            'review_notes': [dict(source=source, **deepcopy(note)) for source, raw in
                             (('content', content), ('visual', visual))
                             for note in raw.get('review_notes', [])],
            'artifact_identity': {
                'task_input_digest': state.get('task_input_digest'),
                'paper_foundation_digest': state.get('paper_foundation_digest'),
                'editorial_snapshot': deepcopy(state.get('editorial_snapshot'))},
            'quality_reference_calibration': 'discrete_threshold_not_yet_calibrated_on_live_samples',
        }
        report.update(details)
        poster_evaluation.update({k: details[k] for k in
            ('scoring_method', 'submetric_assessments', 'aggregation_policy')})
        poster_evaluation.update(deepcopy(policy_metadata))
        return report

    @staticmethod
    def _save_report(state: PosterState, report: Dict[str, Any]) -> None:
        paths = [Path(state["output_dir"]) / "content" / "critic_report.json"]
        candidate_dir = (state.get("current_candidate") or {}).get("candidate_dir")
        if candidate_dir:
            paths.append(Path(candidate_dir) / "critic_report.json")
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )


def critic_node(state: PosterState) -> PosterState:
    return PosterCritic()(state)
