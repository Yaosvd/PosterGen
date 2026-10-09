"""Bounded, evidence-grounded content repairs for loop-family fit searches."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from src.agents.content_optimizer import content_optimizer
from src.layout.feasibility import LayoutFeasibilityError, fit_family_layout
from utils.grounded_content import all_publishable_claims, claim_root_id


def _visible_claim_ids(board: Dict[str, Any]) -> set[str]:
    return {
        str(claim_id)
        for section in board.get("spatial_content_plan", {}).get("sections", [])
        for claim_id in section.get("claim_ids", [])
    }


class CapacityActionPlanner:
    """Translate measured fit pressure into allow-listed content requests."""

    @staticmethod
    def plan(
        state: Dict[str, Any],
        board: Dict[str, Any],
        report: Dict[str, Any],
        *,
        round_index: int,
        maximum_actions: int,
    ) -> List[Dict[str, Any]]:
        sections = {
            str(item.get("section_id")): item
            for item in board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(item, dict) and item.get("section_id")
        }
        claims = all_publishable_claims(state)
        if report.get("status") == "feasible":
            utilization = report.get("zone_utilization") or {}
            sparse_zones = sorted(
                (zone_id for zone_id, value in utilization.items() if float(value) < 0.70),
                key=lambda zone_id: float(utilization[zone_id]),
            )
            spec = report.get("selected_layout_spec") or {}
            actions = []
            for zone_id in sparse_zones:
                zone = next((
                    item for item in spec.get("zones", [])
                    if str(item.get("zone_id")) == str(zone_id)
                ), {})
                for section_id in zone.get("section_ids", []):
                    if str(section_id) not in sections:
                        continue
                    actions.append({
                        "operation": (
                            "add_existing_claim" if round_index == 0
                            else "add_claim_from_evidence"
                        ),
                        "section_id": str(section_id),
                        "reason": "add relevant paper-supported detail to sparse zone",
                    })
                    break
                if len(actions) >= maximum_actions:
                    break
            return actions

        if report.get("reason_code") not in {
            "NO_FAST_FEASIBLE_VARIANT", "NO_EXACT_COMPILABLE_VARIANT"
        }:
            return []
        pressure = []
        for trial in report.get("trials") or []:
            pressure.extend((trial.get("diagnostics") or {}).get("height_pressure") or [])
        pressure.sort(
            key=lambda item: float(item.get("estimated_used_in", 0))
            - float(item.get("zone_limit_in", 0)),
            reverse=True,
        )
        actions = []
        used_sections = set()
        for item in pressure:
            overage = float(item.get("estimated_used_in", 0)) - float(
                item.get("zone_limit_in", 0)
            )
            maximum_overage = float(
                (state.get("critic_config") or {}).get("capacity_repair", {}).get(
                    "max_repairable_overflow_inches", 2.0
                )
            )
            if overage <= 0 or overage > maximum_overage:
                continue
            section_id = str(item.get("section_id") or "")
            section = sections.get(section_id)
            if section is None or section_id in used_sections:
                continue
            visible = sorted(
                (
                    claims[claim_id]
                    for claim_id in section.get("claim_ids", [])
                    if claim_id in claims
                ),
                key=lambda claim: len(str(claim.get("text") or "")),
                reverse=True,
            )
            if not visible:
                continue
            source = visible[min(round_index, len(visible) - 1)]
            root = claim_root_id(source)
            alternatives = sorted(
                (
                    claim for claim in claims.values()
                    if round_index == 0
                    and claim.get("verified") is True
                    and claim.get("claim_id") != source.get("claim_id")
                    and claim_root_id(claim) == root
                    and len(str(claim.get("text") or "")) < len(str(source.get("text") or ""))
                ),
                key=lambda claim: len(str(claim.get("text") or "")),
            )
            action = {
                "operation": "use_claim_variant" if alternatives else "create_compact_variant",
                "section_id": section_id,
                "claim_id": str(source["claim_id"]),
                "target_height_reduction_inches": max(
                    0.0,
                    float(item.get("estimated_used_in", 0))
                    - float(item.get("zone_limit_in", 0)),
                ),
                "reason": "reduce measured zone height pressure",
            }
            if alternatives:
                action["variant_id"] = str(alternatives[0]["claim_id"])
            actions.append(action)
            used_sections.add(section_id)
            if len(actions) >= maximum_actions:
                break
        return actions


def repair_family_fit(
    agent: Any,
    state: Dict[str, Any],
    board: Dict[str, Any],
    family_id: str,
    *,
    initial_report: Dict[str, Any],
    initial_result: Optional[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = None,
    fixed_zones: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]], Dict[str, Any]]:
    settings = (state.get("critic_config") or {}).get("capacity_repair") or {}
    mode = str((state.get("iteration_context") or {}).get("portfolio_mode") or "")
    maximum_rounds = min(
        max(0, int(settings.get("max_rounds_per_family", 2))),
        max(0, int((state.get("iteration_context") or {}).get(
            "capacity_repair_remaining", settings.get("max_rounds_per_iteration", 4)
        ))),
    )
    audit: Dict[str, Any] = {
        "schema_version": 1,
        "status": "skipped",
        "mode": mode,
        "family_id": family_id,
        "rounds_attempted": 0,
        "rounds": [],
        "initial_fit": {
            "status": initial_report.get("status"),
            "reason_code": initial_report.get("reason_code"),
            "worst_zone_utilization": initial_report.get("worst_zone_utilization"),
            "largest_bottom_gap_inches": initial_report.get("largest_bottom_gap_inches"),
        },
    }
    if (
        state.get("generation_route") != "optimization_family"
        or state.get("improve_safe_fallback")
        or not bool(settings.get("enabled", True))
        or maximum_rounds < 1
        or not state.get("text_model")
        or not state.get("tokens")
    ):
        return initial_result, audit

    working = dict(state)
    for field in (
        "verified_content_bank", "supplemental_evidence_bank", "content_selection",
        "content_revision", "layout_revision_constraints",
    ):
        working[field] = deepcopy(state.get(field))
    source_board = deepcopy(initial_result[0] if initial_result else board)
    current_report = deepcopy(initial_report)
    if initial_result is not None:
        current_report["selected_layout_spec"] = deepcopy(initial_result[1])
    previous_worst = float(initial_report.get("worst_zone_utilization", 0.0))
    for round_index in range(maximum_rounds):
        actions = CapacityActionPlanner.plan(
            working, source_board, current_report,
            round_index=round_index,
            maximum_actions=max(1, int(settings.get("max_actions_per_round", 2))),
        )
        if not actions:
            break
        audit["rounds_attempted"] += 1
        trial = dict(working)
        for field in (
            "verified_content_bank", "supplemental_evidence_bank", "content_selection",
            "layout_revision_constraints",
        ):
            trial[field] = deepcopy(working.get(field))
        trial["errors"] = []
        trial = content_optimizer(
            trial, board_override=source_board,
            actions_override=actions, save=False,
        )
        accepted = (trial.get("content_revision") or {}).get("accepted_actions") or []
        round_audit = {
            "round": round_index + 1,
            "actions": actions,
            "accepted_actions": accepted,
            "status": "no_safe_content_change",
        }
        audit["rounds"].append(round_audit)
        if trial.get("errors") or not accepted:
            continue
        changed_board = trial["story_board"]
        try:
            result = fit_family_layout(
                agent, changed_board, trial, family_id,
                config=state.get("critic_config") or {},
                fixed_zones=fixed_zones,
            )
        except LayoutFeasibilityError as exc:
            current_report = exc.report or current_report
            round_audit["status"] = "still_infeasible"
            round_audit["reason_code"] = current_report.get("reason_code")
            working = trial
            source_board = changed_board
            continue
        changed_ids = _visible_claim_ids(changed_board) - _visible_claim_ids(source_board)
        if not changed_ids or not changed_ids.issubset(_visible_claim_ids(result[0])):
            round_audit["status"] = "changed_content_not_visible_after_fit"
            continue
        candidate_worst = float(result[2].get("worst_zone_utilization", 0.0))
        if initial_result is not None and candidate_worst < previous_worst + 0.03:
            round_audit["status"] = "no_measured_density_gain"
            continue
        visible_after = _visible_claim_ids(result[0])
        committed_claim_ids = {
            str(item.get("claim_id"))
            for item in (state.get("verified_content_bank") or {}).get("claims", [])
        }
        bank_claims = [
            item for item in (trial.get("verified_content_bank") or {}).get("claims", [])
            if str(item.get("claim_id")) in committed_claim_ids | visible_after
        ]
        trial["verified_content_bank"]["claims"] = bank_claims
        referenced_evidence = {
            str(evidence_id)
            for claim in bank_claims
            for evidence_id in claim.get("evidence_ids", [])
        }
        committed_evidence_ids = {
            str(item.get("evidence_id"))
            for item in (state.get("supplemental_evidence_bank") or {}).get("items", [])
        }
        trial["supplemental_evidence_bank"]["items"] = [
            item for item in (trial.get("supplemental_evidence_bank") or {}).get("items", [])
            if str(item.get("evidence_id")) in committed_evidence_ids | referenced_evidence
        ]
        selection = trial.get("content_selection") or {}
        selection["replacements"] = {
            root: claim_id
            for root, claim_id in (selection.get("replacements") or {}).items()
            if str(claim_id) in committed_claim_ids | visible_after
        }
        previous_changed = (
            (state.get("content_selection") or {}).get("last_changed_iteration") or {}
        )
        selection["last_changed_iteration"] = {
            root: iteration
            for root, iteration in (selection.get("last_changed_iteration") or {}).items()
            if root in previous_changed or root in selection["replacements"]
        }
        selection["active_supplemental_claim_ids"] = [
            claim_id for claim_id in selection.get("active_supplemental_claim_ids", [])
            if str(claim_id) in visible_after
        ]
        for field in (
            "story_board", "verified_content_bank", "supplemental_evidence_bank",
            "content_selection", "layout_revision_constraints",
        ):
            state[field] = deepcopy(trial.get(field))
        prior_revision = state.get("content_revision") or {}
        revision = deepcopy(trial.get("content_revision") or {})
        revision["accepted_actions"] = list(prior_revision.get("accepted_actions") or []) + list(accepted)
        state["content_revision"] = revision
        round_audit["status"] = "fit_improved"
        round_audit["worst_zone_utilization_before"] = previous_worst
        round_audit["worst_zone_utilization_after"] = candidate_worst
        round_audit["zone_utilization_after"] = result[2].get("zone_utilization")
        round_audit["largest_bottom_gap_after_inches"] = result[2].get(
            "largest_bottom_gap_inches"
        )
        audit["status"] = "applied"
        return result, audit
    audit["status"] = "no_safe_improvement"
    return initial_result, audit
