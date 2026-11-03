"""Versioned poster evaluation; reference thresholds never control storage."""

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext, CriticEvaluator, EvaluationResult, issue
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
        log_agent_info(self.name, "evaluating rendered poster candidate")
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
        configured_dimensions = self.config["dimensions"]
        dimension_scores: Dict[str, float] = {}
        source_contributions: Dict[str, List[Dict[str, Any]]] = {}
        missing_score_sources: Dict[str, List[str]] = {}
        for dimension in configured_dimensions:
            contributions = []
            missing = []
            weights = self.config['editorial_scoring']['dimensions'][dimension]['submetrics']
            for leaf, weight in weights.items():
                source = self.config['submetric_sources'][leaf]
                result = result_by_name.get(source)
                assessment = ((result.metadata.get('submetric_assessments') or {}).get(leaf)
                              if result else None)
                value = assessment.get('score') if assessment else None
                if (not assessment or assessment.get('assessment_status') not in {'assessed', 'uncertain'}
                        or type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100):
                    missing.append(leaf)
                    continue
                contributions.append({'evaluator': source, 'submetric': leaf,
                                      'score': value, 'weight': weight})
            source_contributions[dimension] = contributions
            missing_score_sources[dimension] = missing
            # Incomplete dimensions remain absent: never impute or renormalize.
            if not missing:
                dimension_scores[dimension] = round(sum(c['score'] * c['weight'] for c in contributions), 2)
        weighted_total = 0.0
        active_weight = 0.0
        for dimension, score in dimension_scores.items():
            weight = float(configured_dimensions[dimension].get("weight", 0.0))
            weighted_total += score * weight
            active_weight += weight
        overall_score = round(weighted_total / active_weight if active_weight else 0.0, 2)
        if any(missing_score_sources.values()):
            overall_score = None

        hard_gate_passed = all(result.passed for result in results if result.hard_gate)
        archive_policy = self.config["quality_reference"]
        dimension_minimums_passed = all(
            dimension_scores.get(dimension, 0.0) >= float(settings.get("minimum", 0.0))
            for dimension, settings in configured_dimensions.items()
        )
        required_dimensions_present = all(
            dimension in dimension_scores for dimension in configured_dimensions
        )
        archive_eligible = (
            overall_score is not None
            and overall_score >= float(archive_policy.get("minimum_overall_score", 0.0))
            and (hard_gate_passed or not archive_policy.get("require_all_hard_gates", True))
            and (
                dimension_minimums_passed
                or not archive_policy.get("require_dimension_minimums", True)
            )
            and required_dimensions_present
        )

        unresolved_serious = [item for item in all_issues
                              if str(item.get('severity', '')).lower() in {'critical', 'major'}]

        # Scientific integrity remains a hard quality requirement; this separate
        # view makes presentation quality auditable without changing admission.
        presentation_dimensions = {
            name: score for name, score in dimension_scores.items()
            if name != "scientific_integrity"
        }
        presentation_weight = sum(
            float(configured_dimensions[name].get("weight", 0.0))
            for name in presentation_dimensions
        )
        presentation_quality_score = round(
            sum(score * float(configured_dimensions[name].get("weight", 0.0))
                for name, score in presentation_dimensions.items()) / presentation_weight
            if presentation_weight else 0.0, 2
        )

        severity_rank = {"critical": 0, "major": 1, "minor": 2, "warning": 3}
        all_issues.sort(key=lambda item: severity_rank.get(item.get("severity"), 4))
        summary_parts = [
            item.get("observation", "")
            for item in all_issues[:3]
            if item.get("observation")
        ]
        rejection_summary = "" if archive_eligible else (
            "; ".join(summary_parts)
            if summary_parts
            else "Candidate did not meet the configured quality thresholds"
        )

        candidate = state.get("current_candidate") or {}
        iteration_context = state.get("iteration_context") or {}
        assessments = {}
        for leaf, source in self.config['submetric_sources'].items():
            result = result_by_name.get(source)
            assessment = ((result.metadata.get('submetric_assessments') or {}).get(leaf)
                          if result else None)
            if assessment is not None:
                assessments[leaf] = {'evaluator': source, **deepcopy(assessment)}
        # Only the declared model source owns each public quality score.
        submetric_scores = {k: v['score'] for k, v in assessments.items()
                            if v.get('assessment_status') in {'assessed', 'uncertain'}
                            and type(v.get('score')) in (int, float)
                            and math.isfinite(v['score']) and 0 <= v['score'] <= 100}
        if overall_score is None:
            presentation_quality_score = None
        poster_evaluation = {
            "overall_score": overall_score,
            "presentation_quality_score": presentation_quality_score,
            "dimension_scores": dimension_scores,
            "submetric_scores": submetric_scores,
            "dimension_source_contributions": source_contributions,
            "missing_score_sources": missing_score_sources,
            "hard_gate_passed": hard_gate_passed,
            "required_dimensions_present": required_dimensions_present,
            "dimension_minimums_passed": dimension_minimums_passed,
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
                or any(missing_score_sources.values()) or not required_dimensions_present) else "complete",
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
            "required_dimensions_present": required_dimensions_present,
            "dimension_minimums_passed": dimension_minimums_passed,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "submetric_scores": submetric_scores,
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
            'aggregation_policy': {'dimensions': deepcopy(self.config['editorial_scoring']['dimensions']),
                                   'submetric_sources': deepcopy(self.config['submetric_sources']),
                                   'rounding': 'dimension_then_overall_2_decimal_places'},
            'content_dependencies': deepcopy(content.get('content_dependencies')),
            'reading_review': deepcopy(visual.get('reading_review')),
            'measurement_evidence': deepcopy(state.get('critic_measurement_evidence') or {}),
            'request_identities': deepcopy(state.get('critic_request_identities') or {}),
            'artifact_identity': {
                'task_input_digest': state.get('task_input_digest'),
                'paper_foundation_digest': state.get('paper_foundation_digest'),
                'editorial_snapshot': deepcopy(state.get('editorial_snapshot'))},
            'quality_reference_calibration': 'legacy_reference_not_calibrated_for_model_submetrics',
        }
        report.update(details)
        poster_evaluation.update({k: details[k] for k in
            ('scoring_method', 'submetric_assessments', 'aggregation_policy')})
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
