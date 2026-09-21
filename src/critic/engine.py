"""Versioned evaluator orchestration and archive decision policy."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext, CriticEvaluator, EvaluationResult, issue
from src.critic.evaluators import DEFAULT_DETERMINISTIC_EVALUATORS
from src.critic.layout_family import LayoutFamilyCriticEvaluator
from src.critic.visual import VisualCriticEvaluator
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
        self.config = config or load_critic_config()
        if evaluators is None:
            evaluators = [factory() for factory in DEFAULT_DETERMINISTIC_EVALUATORS]
            evaluators.append(LayoutFamilyCriticEvaluator())
            if self.config["evaluators"].get("visual", {}).get("enabled", True):
                evaluators.append(VisualCriticEvaluator())
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

        for evaluator in self.evaluators:
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
                    scores={},
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
        state["critic_report"] = report
        history = state.setdefault("critic_history", [])
        history.append({
            "candidate_id": report["candidate_id"],
            "iteration": report["iteration"],
            "decision": report["decision"],
            "overall_score": report["overall_score"],
            "rejection_summary": report["rejection_summary"],
        })
        history_limit = max(
            1,
            int(self.config.get("loop", {}).get("in_memory_history_limit", 50)),
        )
        if len(history) > history_limit:
            del history[:-history_limit]
        state["current_agent"] = self.name
        self._save_report(state, report)

        if report["archive_eligible"]:
            log_agent_success(
                self.name,
                f"candidate qualifies for archive ({report['overall_score']:.1f})",
            )
        else:
            log_agent_warning(
                self.name,
                f"candidate rejected ({report['overall_score']:.1f}): "
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
        submetric_values: Dict[str, List[float]] = defaultdict(list)

        for result in results:
            evaluator_versions[result.evaluator] = result.version
            all_issues.extend(result.issues)
            positives.extend(result.positive_patterns)
            for name, value in (result.metadata.get("submetrics") or {}).items():
                try:
                    submetric_values[str(name)].append(float(value))
                except (TypeError, ValueError):
                    continue

        configured_dimensions = self.config["dimensions"]
        configured_sources = self.config.get("dimension_sources", {})
        dimension_scores: Dict[str, float] = {}
        source_contributions: Dict[str, List[Dict[str, Any]]] = {}
        missing_score_sources: Dict[str, List[str]] = {}
        for dimension in configured_dimensions:
            source_weights = configured_sources.get(dimension, {})
            contributions: List[Dict[str, Any]] = []
            if source_weights:
                missing: List[str] = []
                configured_weight = 0.0
                for evaluator_name, raw_weight in source_weights.items():
                    weight = max(0.0, float(raw_weight))
                    if weight <= 0:
                        continue
                    configured_weight += weight
                    result = result_by_name.get(evaluator_name)
                    if result is None or dimension not in result.scores:
                        missing.append(evaluator_name)
                        continue
                    contributions.append({
                        "evaluator": evaluator_name,
                        "score": float(result.scores[dimension]),
                        "weight": weight,
                    })
                missing_score_sources[dimension] = missing
            else:
                for result in results:
                    if dimension in result.scores:
                        contributions.append({
                            "evaluator": result.evaluator,
                            "score": float(result.scores[dimension]),
                            "weight": 1.0,
                        })
            source_contributions[dimension] = contributions
            total_source_weight = (
                configured_weight
                if source_weights
                else sum(item["weight"] for item in contributions)
            )
            if total_source_weight:
                # Missing configured sources contribute zero rather than causing
                # the remaining sources to be silently renormalized upward.
                dimension_scores[dimension] = round(
                    sum(item["score"] * item["weight"] for item in contributions)
                    / total_source_weight,
                    2,
                )

        weighted_total = 0.0
        active_weight = 0.0
        for dimension, score in dimension_scores.items():
            weight = float(configured_dimensions[dimension].get("weight", 0.0))
            weighted_total += score * weight
            active_weight += weight
        overall_score = round(weighted_total / active_weight if active_weight else 0.0, 2)

        hard_gate_passed = all(result.passed for result in results if result.hard_gate)
        archive_policy = self.config["archive_policy"]
        dimension_minimums_passed = all(
            dimension_scores.get(dimension, 0.0) >= float(settings.get("minimum", 0.0))
            for dimension, settings in configured_dimensions.items()
        )
        required_dimensions_present = all(
            dimension in dimension_scores for dimension in configured_dimensions
        )
        archive_eligible = (
            overall_score >= float(archive_policy.get("minimum_overall_score", 0.0))
            and (hard_gate_passed or not archive_policy.get("require_all_hard_gates", True))
            and (
                dimension_minimums_passed
                or not archive_policy.get("require_dimension_minimums", True)
            )
            and required_dimensions_present
        )

        section_fit = state.get("section_fit_analysis") or {}
        template_policy = self.config.get("templates", {})
        template_minimums = template_policy.get("dimension_minimums", {})
        template_dimensions_passed = all(
            dimension_scores.get(dimension, 0.0) >= float(minimum)
            for dimension, minimum in template_minimums.items()
        )
        unresolved_serious = [
            item for item in all_issues
            if str(item.get("severity", "")).lower() in {"critical", "major"}
        ]
        template_eligible = (
            archive_eligible
            and overall_score >= float(template_policy.get("minimum_overall_score", 85.0))
            and template_dimensions_passed
            and (
                not template_policy.get("require_ideal_section_fit", True)
                or (
                    bool(section_fit.get("all_sections_ideal"))
                    and bool(section_fit.get("gaps_acceptable"))
                )
            )
            and (
                not template_policy.get("require_no_major_issues", True)
                or not unresolved_serious
            )
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
        submetric_scores = {
            name: round(sum(values) / len(values), 2)
            for name, values in submetric_values.items()
            if values
        }
        poster_evaluation = {
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "submetric_scores": submetric_scores,
            "dimension_source_contributions": source_contributions,
            "missing_score_sources": missing_score_sources,
            "hard_gate_passed": hard_gate_passed,
            "required_dimensions_present": required_dimensions_present,
            "dimension_minimums_passed": dimension_minimums_passed,
            "archive_eligible": archive_eligible,
            "template_eligible": template_eligible,
            "unresolved_serious_issue_count": len(unresolved_serious),
        }
        return {
            "schema_version": 3,
            "critic_system_version": self.config["critic_system_version"],
            "rubric_version": self.config["rubric_version"],
            "evaluator_versions": evaluator_versions,
            "candidate_id": candidate.get("candidate_id", "unknown"),
            "iteration": int(iteration_context.get("iteration", 0)),
            "strategy": iteration_context.get("strategy", "single_pass"),
            "portfolio_mode": iteration_context.get("portfolio_mode"),
            "lineage_id": iteration_context.get("lineage_id"),
            "parent_lineage_id": iteration_context.get("parent_lineage_id"),
            "layout_family": (
                (state.get("layout_spec") or {}).get("family_id")
                or iteration_context.get("layout_family")
            ),
            "template_validation": iteration_context.get("portfolio_mode") == "validate",
            "decision": "archive" if archive_eligible else "discard",
            "archive_eligible": archive_eligible,
            "hard_gate_passed": hard_gate_passed,
            "template_eligible": template_eligible,
            "required_dimensions_present": required_dimensions_present,
            "dimension_minimums_passed": dimension_minimums_passed,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "submetric_scores": submetric_scores,
            "poster_evaluation": poster_evaluation,
            "task_evaluation": {
                "status": "not_applicable",
                "reason": "Task-grounded evaluation is reserved for future task-specific rubrics",
                "scores": {},
            },
            "issues": all_issues,
            "positive_patterns": positives,
            "rejection_summary": rejection_summary,
            "evaluations": [result.to_dict() for result in results],
        }

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


critic = PosterCritic()


def critic_node(state: PosterState) -> PosterState:
    return critic(state)
