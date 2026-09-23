"""Persistent multi-lineage portfolio scheduling for poster optimization."""

from __future__ import annotations

import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from src.layout.families import LayoutFamilyRegistry


PORTFOLIO_SCHEMA_VERSION = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_portfolio_state() -> Dict[str, Any]:
    return {
        "schema_version": PORTFOLIO_SCHEMA_VERSION,
        "lineages": {},
        "mixed_mode_counts": {"explore": 0, "improve": 0, "mutate": 0, "validate": 0},
        "mode_counts": {
            "explore": 0,
            "improve": 0,
            "mutate": 0,
            "validate": 0,
        },
        "family_counts": {},
        "family_exploration_debt": {},
        "recent_lineage_ids": [],
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
        state["schema_version"] = PORTFOLIO_SCHEMA_VERSION
        state.setdefault("lineages", {})
        state.setdefault("mode_counts", {})
        state.setdefault("mixed_mode_counts", dict(state["mode_counts"]))
        for mode in ("explore", "improve", "mutate", "validate"):
            state["mode_counts"].setdefault(mode, 0)
            state["mixed_mode_counts"].setdefault(mode, 0)
        state.setdefault("family_counts", {})
        state.setdefault("family_exploration_debt", {})
        state.setdefault("recent_lineage_ids", [])
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
                    }
                lineage.update({
                    "rubric_version": current_rubric,
                    "best_score": -1.0,
                    "best_candidate_id": None,
                    "best_accepted_score": -1.0,
                    "best_accepted_candidate_id": None,
                    "stagnation_count": 0,
                    "status": "seed",
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
    ) -> Dict[str, Any]:
        portfolio = self.normalize(portfolio)
        lineages = [
            lineage
            for lineage in portfolio["lineages"].values()
            if lineage.get("status") not in {"retired"}
        ]
        warmup = int(
            self.config.get("loop", {}).get("session_template_free_warmup", 3)
        )
        if batch_mode not in {"mixed", "explore", "improve", "mutate", "validate"}:
            raise ValueError(f"Unsupported Batch mode: {batch_mode}")
        if batch_mode != "mixed":
            mode = batch_mode
            if mode in {"improve", "mutate"} and not lineages:
                raise ValueError(f"{mode} requires an existing Lineage")
            if mode == "validate" and not validation_available:
                raise ValueError("validate requires a pending eligible template task")
        elif session_iteration <= warmup or not lineages:
            mode = "explore"
        else:
            mode = self._deficit_mode(portfolio, mixed_mode_weights)
        if target_lineage_id:
            if mode not in {"improve", "mutate"}:
                raise ValueError("target_lineage_id requires improve or mutate mode")
            lineages = [item for item in lineages if item.get("lineage_id") == target_lineage_id]
            if not lineages:
                raise ValueError(f"Lineage not available: {target_lineage_id}")

        rng = random.Random(self.random_seed + iteration)
        parent = None
        lineage_id: str
        if mode in {"improve", "mutate"}:
            parent = self._choose_lineage(lineages, rng, portfolio.get("recent_lineage_ids", []))
        if mode == "improve" and parent is not None:
            lineage_id = str(parent["lineage_id"])
            family_id = str(parent["family_id"])
        elif mode == "mutate" and parent is not None:
            family_id = self.registry.choose(
                paper_profile,
                portfolio["family_counts"],
                random_seed=self.random_seed + iteration,
                exclude=[str(parent.get("family_id"))],
            )
            lineage_id = f"lin_{iteration:06d}_mutation"
        else:
            family_id = self.registry.choose(
                paper_profile,
                portfolio["family_counts"],
                random_seed=self.random_seed + iteration,
            )
            lineage_id = f"lin_{iteration:06d}_{mode}"

        strategy = {
            "explore": "explore",
            "improve": "revise",
            "mutate": "mutate",
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
            "parent_candidate_id": (
                parent.get("best_candidate_id") if parent else None
            ),
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
            "explore": 0.40,
            "improve": 0.45,
            "mutate": 0.15,
        }
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
                float(lineage.get("best_score", -1.0)),
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
        if mode in {"improve", "mutate"}:
            state["recent_lineage_ids"] = (state["recent_lineage_ids"] + [str(task.get("parent_lineage_id") or lineage_id)])[-12:]
        state["family_counts"][family_id] = int(
            state["family_counts"].get(family_id, 0)
        ) + 1

        lineages = state["lineages"]
        lineage = lineages.get(lineage_id) or {
            "schema_version": 1,
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
            "latest_candidate_id": None,
            "stagnation_count": 0,
            "accepted_versions": [],
            "template_ids": [],
            "critic_history": [],
            "created_at": _utc_now(),
        }
        lineage["rubric_version"] = report.get(
            "rubric_version", self.config.get("rubric_version")
        )
        score = float(report.get("overall_score", 0.0))
        previous_best = float(lineage.get("best_score", -1.0))
        lineage["generation"] = int(lineage.get("generation", 0)) + 1
        lineage["latest_candidate_id"] = report.get("candidate_id")
        lineage["latest_score"] = score
        lineage["family_id"] = family_id
        lineage["stagnation_count"] = (
            0 if score > previous_best else int(lineage.get("stagnation_count", 0)) + 1
        )
        if score > previous_best:
            lineage["best_score"] = score
            lineage["best_candidate_id"] = report.get("candidate_id")
        if accepted:
            lineage["accepted_versions"].append(report.get("candidate_id"))
            del lineage["accepted_versions"][:-20]
            if score > float(lineage.get("best_accepted_score", -1.0)):
                lineage["best_accepted_score"] = score
                lineage["best_accepted_candidate_id"] = report.get("candidate_id")
            lineage["status"] = "accepted_poster"
        elif score > previous_best:
            lineage["status"] = "promising"
        elif int(lineage["stagnation_count"]) >= int(
            self.config.get("portfolio", {}).get("stagnation_generations", 5)
        ):
            lineage["status"] = "stagnated"
        lineage["critic_history"].append({
            "candidate_id": report.get("candidate_id"),
            "score": score,
            "accepted": accepted,
            "decision": report.get("decision"),
            "rubric_version": report.get("rubric_version"),
            "issue_ids": [
                item.get("issue_id") for item in report.get("issues", [])
            ],
        })
        del lineage["critic_history"][:-25]
        lineage["template_ids"] = sorted(set(
            list(lineage.get("template_ids", []))
            + [str(item) for item in selected_template_ids]
        ))
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
                    float(item.get("best_score", -1.0)),
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
