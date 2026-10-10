"""Persistent multi-lineage portfolio scheduling for poster optimization."""

from __future__ import annotations

import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from src.layout.families import LayoutFamilyRegistry


PORTFOLIO_SCHEMA_VERSION = 5
LINEAGE_SCHEMA_VERSION = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_NONREPAIRABLE_EVALUATORS = {"render_artifacts", "grounding"}
_NONREPAIRABLE_SCOPES = {
    "artifact", "critic", "grounding", "renderer", "scientific_integrity",
}


def promising_rank_key(rank: Any) -> tuple:
    """Return a deterministic higher-is-better key for one promising rank."""

    payload = rank if isinstance(rank, dict) else {}
    return (
        -int(payload.get("repairable_hard_gate_failures", 10**6)),
        -int(payload.get("critical_issue_count", 10**6)),
        -int(payload.get("major_issue_count", 10**6)),
        float(payload.get("overall_score", -1.0)),
        float(payload.get("presentation_quality_score", -1.0)),
        int(payload.get("iteration", -1)),
    )


def assess_promising_candidate(
    report: Dict[str, Any],
    *,
    preflight_passed: Optional[bool] = None,
) -> Dict[str, Any]:
    """Classify a rejected rendered poster as a safe editable working base."""

    reasons = []
    if (report.get("revision_admission") or {}).get("passed") is False:
        reasons.append("revision_safety_rejected")
    if bool(report.get("archive_eligible")):
        reasons.append("poster_already_accepted")
    poster_evaluation = report.get("poster_evaluation") or {}
    if poster_evaluation.get("evaluated") is False:
        reasons.append("poster_not_evaluated")
    if preflight_passed is False:
        reasons.append("layout_preflight_failed")
    try:
        score = float(report["overall_score"])
    except (KeyError, TypeError, ValueError):
        score = -1.0
        reasons.append("missing_numeric_score")

    evaluations = [
        item for item in (report.get("evaluations") or [])
        if isinstance(item, dict)
    ]
    failed_hard_gates = [
        str(item.get("evaluator") or "unknown")
        for item in evaluations
        if bool(item.get("hard_gate")) and not bool(item.get("passed"))
    ]
    nonrepairable_failures = sorted(
        set(failed_hard_gates).intersection(_NONREPAIRABLE_EVALUATORS)
    )
    if nonrepairable_failures:
        reasons.append(
            "nonrepairable_hard_gate:" + ",".join(nonrepairable_failures)
        )
    if not evaluations and report.get("hard_gate_passed") is False:
        reasons.append("unverified_hard_gate_failure")

    dimensions = report.get("dimension_scores") or {}
    if (
        "scientific_integrity" in dimensions
        and float(dimensions.get("scientific_integrity") or 0.0) < 100.0
    ):
        reasons.append("scientific_integrity_below_required")
    issues = [
        item for item in (report.get("issues") or [])
        if isinstance(item, dict)
    ]
    unsafe_scopes = sorted({
        str(item.get("scope") or "").lower()
        for item in issues
        if str(item.get("scope") or "").lower() in _NONREPAIRABLE_SCOPES
        and str(item.get("severity") or "").lower() in {"critical", "major"}
    })
    if unsafe_scopes:
        reasons.append("nonrepairable_issue_scope:" + ",".join(unsafe_scopes))

    critical_count = sum(
        str(item.get("severity") or "").lower() == "critical"
        for item in issues
    )
    major_count = sum(
        str(item.get("severity") or "").lower() == "major"
        for item in issues
    )
    presentation_score = report.get("presentation_quality_score")
    try:
        presentation_score = float(presentation_score)
    except (TypeError, ValueError):
        presentation_score = score
    rank = {
        "schema_version": 1,
        "repairable_hard_gate_failures": len(failed_hard_gates),
        "critical_issue_count": critical_count,
        "major_issue_count": major_count,
        "overall_score": score,
        "presentation_quality_score": presentation_score,
        "iteration": int(report.get("iteration", 0) or 0),
    }
    return {
        "schema_version": 1,
        "eligible": not reasons,
        "reasons": reasons,
        "failed_hard_gates": failed_hard_gates,
        "rank": rank,
    }


def new_portfolio_state() -> Dict[str, Any]:
    return {
        "schema_version": PORTFOLIO_SCHEMA_VERSION,
        "lineages": {},
        "mixed_mode_counts": {"explore": 0, "improve": 0, "validate": 0},
        "mode_counts": {
            "explore": 0,
            "improve": 0,
            "validate": 0,
        },
        "family_counts": {},
        "family_exploration_debt": {},
        "recent_lineage_ids": [],
        "validation_history": [],
        "updated_at": _utc_now(),
    }


class PortfolioScheduler:
    """Select mixed design work or an explicitly requested pure mode.

    Selection is based on rolling deficits rather than resetting quotas at a
    Batch boundary.  This is the mechanism that lets every Batch inherit all
    prior exploration debt and prevents a successful family from monopolizing
    later runs. Strict validation is deliberately absent from mixed scheduling.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        random_seed: int,
        registry: Optional[LayoutFamilyRegistry] = None,
    ) -> None:
        self.config = config
        self.random_seed = int(random_seed)
        self.registry = registry or LayoutFamilyRegistry()

    def normalize(self, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        state = deepcopy(raw) if isinstance(raw, dict) else new_portfolio_state()
        legacy_mutate_count = max(
            int((state.get("mode_counts") or {}).get("mutate", 0)),
            int((state.get("mixed_mode_counts") or {}).get("mutate", 0)),
        )
        legacy_mutate_lineages = [
            str(lineage_id)
            for lineage_id, lineage in (state.get("lineages") or {}).items()
            if str((lineage or {}).get("origin")) == "mutate"
        ]
        if legacy_mutate_count or legacy_mutate_lineages:
            raise ValueError(
                "Cannot migrate Portfolio with executed mutate history; "
                "preserve it with a compatible historical release"
            )
        state["schema_version"] = PORTFOLIO_SCHEMA_VERSION
        state.setdefault("lineages", {})
        state.setdefault("mode_counts", {})
        state.setdefault("mixed_mode_counts", dict(state["mode_counts"]))
        state["mode_counts"].pop("mutate", None)
        state["mixed_mode_counts"].pop("mutate", None)
        for mode in ("explore", "improve", "validate"):
            state["mode_counts"].setdefault(mode, 0)
            state["mixed_mode_counts"].setdefault(mode, 0)
        state.setdefault("family_counts", {})
        state.setdefault("family_exploration_debt", {})
        state.setdefault("recent_lineage_ids", [])
        state.setdefault("validation_history", [])
        for lineage in state["lineages"].values():
            if not isinstance(lineage, dict):
                continue
            legacy_references = lineage.pop("template_ids", [])
            lineage["schema_version"] = LINEAGE_SCHEMA_VERSION
            lineage["referenced_template_ids"] = sorted(set(
                str(item) for item in (
                    list(lineage.get("referenced_template_ids") or [])
                    + list(legacy_references or [])
                ) if item
            ))
            produced = list(lineage.get("produced_template_ids") or [])
            if lineage.get("distilled_template_id"):
                produced.append(lineage["distilled_template_id"])
            lineage["produced_template_ids"] = sorted(set(
                str(item) for item in produced if item
            ))
            lineage.setdefault("latest_feedback", {})
            lineage.setdefault("recent_revision_attempts", [])
            lineage.setdefault("best_promising_score", -1.0)
            lineage.setdefault("best_promising_candidate_id", None)
            lineage.setdefault("best_promising_rank", {})
            lineage.setdefault("best_promising_updated_at", None)
        current_rubric = str(self.config.get("rubric_version", "unknown"))
        stored_rubric = state.get("rubric_version")
        if stored_rubric != current_rubric:
            for lineage in state["lineages"].values():
                history = lineage.setdefault("best_by_rubric", {})
                if lineage.get("best_candidate_id") or lineage.get("best_accepted_candidate_id"):
                    history[str(stored_rubric or "legacy_unknown")] = {
                        "best_score": lineage.get("best_score", -1.0),
                        "best_candidate_id": lineage.get("best_candidate_id"),
                        "best_accepted_score": lineage.get("best_accepted_score", -1.0),
                        "best_accepted_candidate_id": lineage.get("best_accepted_candidate_id"),
                        "best_promising_score": lineage.get("best_promising_score", -1.0),
                        "best_promising_candidate_id": lineage.get("best_promising_candidate_id"),
                        "best_promising_rank": deepcopy(lineage.get("best_promising_rank") or {}),
                    }
                lineage.update({
                    "rubric_version": current_rubric,
                    "best_score": -1.0,
                    "best_candidate_id": None,
                    "best_accepted_score": -1.0,
                    "best_accepted_candidate_id": None,
                    "best_promising_score": -1.0,
                    "best_promising_candidate_id": None,
                    "best_promising_rank": {},
                    "best_promising_updated_at": None,
                    "stagnation_count": 0,
                    "status": "seed",
                    "latest_feedback": {},
                    "recent_revision_attempts": [],
                })
            state["rubric_version"] = current_rubric
        return state

    def select(
        self,
        portfolio: Dict[str, Any],
        *,
        iteration: int,
        session_iteration: int,
        paper_profile: Dict[str, Any],
        validation_available: bool,
        batch_mode: str = "mixed",
        target_lineage_id: Optional[str] = None,
        mixed_mode_weights: Optional[Dict[str, float]] = None,
        excluded_family_ids: Optional[Iterable[str]] = None,
        excluded_lineage_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        portfolio = self.normalize(portfolio)
        excluded_lineages = {
            str(item) for item in (excluded_lineage_ids or []) if item
        }
        lineages = [
            lineage
            for lineage in portfolio["lineages"].values()
            if lineage.get("status") not in {"retired"}
            and str(lineage.get("lineage_id")) not in excluded_lineages
        ]
        warmup = int(
            self.config.get("loop", {}).get("session_template_free_warmup", 3)
        )
        if batch_mode not in {"mixed", "explore", "improve", "validate"}:
            raise ValueError(f"Unsupported Batch mode: {batch_mode}")
        if batch_mode != "mixed":
            mode = batch_mode
            if mode == "improve" and not lineages:
                raise ValueError(f"{mode} requires an existing Lineage")
            if mode == "validate" and not validation_available:
                raise ValueError("validate requires a pending eligible template task")
        elif session_iteration <= warmup or not lineages:
            mode = "explore"
        elif bool(
            self.config.get("portfolio", {}).get(
                "force_explore_when_all_lineages_stagnated", True
            )
        ) and all(str(item.get("status")) == "stagnated" for item in lineages):
            mode = "explore"
        else:
            mode = self._deficit_mode(portfolio, mixed_mode_weights)
        if target_lineage_id:
            if mode != "improve":
                raise ValueError("target_lineage_id requires improve mode")
            lineages = [item for item in lineages if item.get("lineage_id") == target_lineage_id]
            if not lineages:
                raise ValueError(f"Lineage not available: {target_lineage_id}")

        rng = random.Random(self.random_seed + iteration)
        parent = None
        lineage_id: str
        if mode == "improve":
            parent = self._choose_lineage(lineages, rng, portfolio.get("recent_lineage_ids", []))
        if mode == "improve" and parent is not None:
            lineage_id = str(parent["lineage_id"])
            family_id = str(parent["family_id"])
        elif mode == "validate":
            # Strict validation audits a saved template; it is not a design
            # branch and is never charged to layout-family coverage.
            family_id = "validation_target"
            lineage_id = "validation-only"
        else:
            family_id = self.registry.choose(
                paper_profile,
                portfolio["family_counts"],
                random_seed=self.random_seed + iteration,
                exclude=excluded_family_ids,
            )
            lineage_id = f"lin_{iteration:06d}_{mode}"

        strategy = {
            "explore": "explore",
            "improve": "revise",
            "validate": "validate",
        }[mode]
        return {
            "schema_version": 1,
            "mode": mode,
            "strategy": strategy,
            "lineage_id": lineage_id,
            "parent_lineage_id": (
                str(parent.get("lineage_id")) if parent else None
            ),
            # Filled by the runner from the snapshot actually restored.
            "parent_candidate_id": None,
            "family_id": family_id,
            "template_free": mode != "validate",
            "created_at": _utc_now(),
        }

    def _deficit_mode(
        self,
        portfolio: Dict[str, Any],
        mode_weights: Optional[Dict[str, float]] = None,
    ) -> str:
        settings = self.config.get("portfolio", {})
        weights = mode_weights or settings.get("mode_weights") or {
            "explore": 0.45,
            "improve": 0.55,
        }
        if set(weights) != {"explore", "improve"}:
            raise ValueError(
                "Mixed scheduling weights must contain only explore and improve"
            )
        counts = portfolio["mixed_mode_counts"]
        # Historical mixed validation counts remain available for audit, but
        # are excluded from the new three-mode policy input and denominator.
        total = sum(int(counts.get(mode, 0)) for mode in weights)
        deficits = {
            mode: float(weights[mode]) * (total + 1) - int(counts.get(mode, 0))
            for mode in weights
        }
        return max(sorted(weights), key=lambda mode: deficits[mode])

    def _choose_lineage(
        self,
        lineages: Iterable[Dict[str, Any]],
        rng: random.Random,
        recent_lineage_ids: Iterable[str] = (),
    ) -> Dict[str, Any]:
        recent = set(list(recent_lineage_ids)[-3:])
        candidates = list(lineages)
        rng.shuffle(candidates)

        def priority(lineage: Dict[str, Any]) -> tuple:
            status_bonus = {
                "promising": 3,
                "accepted_poster": 4,
                "template_candidate": 5,
                "seed": 2,
                "stagnated": 0,
                "paused": -1,
            }.get(str(lineage.get("status")), 1)
            return (
                -int(str(lineage.get("lineage_id")) in recent),
                status_bonus,
                -int(lineage.get("stagnation_count", 0)),
                float(lineage.get("best_accepted_score", -1.0)),
                float(lineage.get("best_promising_score", -1.0)),
                -int(lineage.get("generation", 0)),
                str(lineage.get("lineage_id")),
            )

        return max(candidates, key=priority)

    def commit(
        self,
        portfolio: Dict[str, Any],
        task: Dict[str, Any],
        report: Dict[str, Any],
        *,
        accepted: bool,
        selected_template_ids: Iterable[str] = (),
        produced_template_id: Optional[str] = None,
        revision_context: Optional[Dict[str, Any]] = None,
        no_change: bool = False,
        batch_mode: str = "mixed",
    ) -> Dict[str, Any]:
        state = self.normalize(portfolio)
        mode = str(task["mode"])
        family_id = str(task["family_id"])
        lineage_id = str(task["lineage_id"])
        state["mode_counts"][mode] = int(
            state["mode_counts"].get(mode, 0)
        ) + 1
        if batch_mode == "mixed":
            state["mixed_mode_counts"][mode] = int(state["mixed_mode_counts"].get(mode, 0)) + 1
        if mode == "validate":
            history = state.setdefault("validation_history", [])
            history.append({
                "candidate_id": report.get("candidate_id"),
                "template_ids": sorted(
                    str(item) for item in selected_template_ids if item
                ),
                "family_id": family_id,
                "score": (
                    float(report["overall_score"])
                    if isinstance(report.get("overall_score"), (int, float))
                    else None
                ),
                "poster_evaluated": bool(
                    (report.get("poster_evaluation") or {}).get("evaluated", True)
                ),
                "poster_accepted": bool(accepted),
                "transfer_verified": bool(
                    (report.get("task_evaluation") or {}).get("passed")
                ),
                "recorded_at": _utc_now(),
            })
            del history[:-100]
            state["updated_at"] = _utc_now()
            return state
        if mode == "improve":
            state["recent_lineage_ids"] = (state["recent_lineage_ids"] + [str(task.get("parent_lineage_id") or lineage_id)])[-12:]
        state["family_counts"][family_id] = int(
            state["family_counts"].get(family_id, 0)
        ) + 1

        lineages = state["lineages"]
        lineage = lineages.get(lineage_id) or {
            "schema_version": LINEAGE_SCHEMA_VERSION,
            "lineage_id": lineage_id,
            "family_id": family_id,
            "origin": mode,
            "parent_lineage_id": task.get("parent_lineage_id"),
            "generation": 0,
            "status": "seed",
            "best_score": -1.0,
            "best_candidate_id": None,
            "best_accepted_score": -1.0,
            "best_accepted_candidate_id": None,
            "best_promising_score": -1.0,
            "best_promising_candidate_id": None,
            "best_promising_rank": {},
            "best_promising_updated_at": None,
            "latest_candidate_id": None,
            "stagnation_count": 0,
            "accepted_versions": [],
            "referenced_template_ids": [],
            "produced_template_ids": [],
            "critic_history": [],
            "latest_feedback": {},
            "recent_revision_attempts": [],
            "created_at": _utc_now(),
        }
        lineage["rubric_version"] = report.get(
            "rubric_version", self.config.get("rubric_version")
        )
        score = float(report.get("overall_score", 0.0))
        previous_best = float(lineage.get("best_score", -1.0))
        parent_score = (revision_context or {}).get("parent_score")
        revision_safe = (report.get("revision_admission") or {}).get("passed") is not False
        local_improvement = bool(
            not no_change
            and revision_safe
            and isinstance(parent_score, (int, float))
            and score > float(parent_score)
        )
        promising = deepcopy(
            report.get("promising_evaluation")
            or assess_promising_candidate(report)
        )
        candidate_promising_rank = promising.get("rank") or {}
        previous_promising_rank = lineage.get("best_promising_rank") or {}
        became_best_promising = bool(
            not accepted
            and not no_change
            and promising.get("eligible")
            and (
                not lineage.get("best_promising_candidate_id")
                or promising_rank_key(candidate_promising_rank)
                > promising_rank_key(previous_promising_rank)
            )
        )
        lineage["generation"] = int(lineage.get("generation", 0)) + 1
        lineage["latest_candidate_id"] = report.get("candidate_id")
        lineage["latest_score"] = score
        lineage["family_id"] = family_id
        observed_best = bool(not no_change and revision_safe and score > previous_best)
        if observed_best:
            lineage["best_score"] = score
            lineage["best_candidate_id"] = report.get("candidate_id")
        if became_best_promising:
            lineage["best_promising_score"] = score
            lineage["best_promising_candidate_id"] = report.get("candidate_id")
            lineage["best_promising_rank"] = deepcopy(candidate_promising_rank)
            lineage["best_promising_updated_at"] = _utc_now()
        portfolio_progress = bool(
            not no_change and (accepted or became_best_promising)
        )
        lineage["stagnation_count"] = (
            0
            if portfolio_progress
            else int(lineage.get("stagnation_count", 0)) + 1
        )
        if accepted and not no_change:
            lineage["accepted_versions"].append(report.get("candidate_id"))
            del lineage["accepted_versions"][:-20]
            if score > float(lineage.get("best_accepted_score", -1.0)):
                lineage["best_accepted_score"] = score
                lineage["best_accepted_candidate_id"] = report.get("candidate_id")
            lineage["status"] = "accepted_poster"
        elif became_best_promising:
            lineage["status"] = (
                "accepted_poster"
                if lineage.get("best_accepted_candidate_id")
                else "promising"
            )
        elif int(lineage["stagnation_count"]) >= int(
            self.config.get("portfolio", {}).get("stagnation_generations", 5)
        ):
            lineage["status"] = "stagnated"
        lineage["critic_history"].append({
            "candidate_id": report.get("candidate_id"),
            "score": score,
            "accepted": bool(accepted and not no_change),
            "decision": (
                "no_change_safe_fallback"
                if no_change else report.get("loop_disposition") or report.get("decision")
            ),
            "rubric_version": report.get("rubric_version"),
            "issue_ids": [
                item.get("issue_id") for item in report.get("issues", [])
            ],
        })
        del lineage["critic_history"][:-25]
        lineage["referenced_template_ids"] = sorted(set(
            list(lineage.get("referenced_template_ids", []))
            + [str(item) for item in selected_template_ids]
        ))
        if produced_template_id:
            lineage["produced_template_ids"] = sorted(set(
                list(lineage.get("produced_template_ids", []))
                + [str(produced_template_id)]
            ))
        context = deepcopy(revision_context or {})
        parent_score = context.get("parent_score")
        feedback = {
            "schema_version": 1,
            "lineage_id": lineage_id,
            "candidate_id": report.get("candidate_id"),
            "parent_candidate_id": task.get("parent_candidate_id"),
            "parent_score": parent_score,
            "score": score,
            "score_delta": (
                round(score - float(parent_score), 6)
                if isinstance(parent_score, (int, float)) else None
            ),
            "local_improvement": local_improvement,
            "promising_eligible": bool(promising.get("eligible")),
            "promising_reasons": list(promising.get("reasons") or []),
            "promising_rank": deepcopy(candidate_promising_rank),
            "became_best_promising": became_best_promising,
            "best_promising_candidate_id": lineage.get(
                "best_promising_candidate_id"
            ),
            "best_promising_score": lineage.get("best_promising_score"),
            "accepted": bool(accepted and not no_change),
            "no_change": bool(no_change),
            "became_best": bool(observed_best),
            "rubric_version": report.get("rubric_version"),
            "critic_report": deepcopy(report),
            "revision_plan": context.get("revision_plan") or {},
            "revision_execution_report": (
                context.get("revision_execution_report") or {}
            ),
            "content_revision": context.get("content_revision") or {},
            "recorded_at": _utc_now(),
        }
        lineage["latest_feedback"] = feedback
        history = list(lineage.get("recent_revision_attempts") or [])
        history.append({
            key: deepcopy(value)
            for key, value in feedback.items()
            if key not in {
                "critic_report",
                "revision_plan",
                "revision_execution_report",
                "content_revision",
            }
        } | {
            "issue_ids": [
                item.get("issue_id") for item in report.get("issues", [])
                if isinstance(item, dict)
            ],
            "attempted_operations": [
                item.get("operation")
                for item in (context.get("revision_plan") or {}).get(
                    "operations", []
                )
                if isinstance(item, dict) and item.get("operation")
            ],
        })
        lineage["recent_revision_attempts"] = history[-25:]
        lineage["updated_at"] = _utc_now()
        lineages[lineage_id] = lineage

        maximum = int(
            self.config.get("portfolio", {}).get("max_active_lineages", 8)
        )
        active = [
            item
            for item in lineages.values()
            if item.get("status") not in {"paused", "retired"}
        ]
        if len(active) > maximum:
            pausable = sorted(
                (
                    item
                    for item in active
                    if item["lineage_id"] != lineage_id
                    and item.get("status") not in {"template_candidate"}
                ),
                key=lambda item: (
                    float(item.get("best_accepted_score", -1.0)),
                    float(item.get("best_promising_score", -1.0)),
                ),
            )
            if pausable:
                pausable[0]["status"] = "paused"

        recent = list(state.get("recent_lineage_ids", []))
        recent.append(lineage_id)
        state["recent_lineage_ids"] = recent[-12:]
        state["updated_at"] = _utc_now()
        self._update_family_debt(state)
        return state

    def _update_family_debt(self, state: Dict[str, Any]) -> None:
        minimum = int(
            self.config.get("layout_families", {}).get(
                "minimum_seed_attempts_per_family", 2
            )
        )
        state["family_exploration_debt"] = {
            family_id: max(
                0, minimum - int(state["family_counts"].get(family_id, 0))
            )
            for family_id in self.registry.ids()
        }
