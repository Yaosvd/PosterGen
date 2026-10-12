"""Bounded, evidence-grounded content repairs for loop-family fit searches."""

from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.agents.content_optimizer import content_optimizer
from src.agents.revision_contract import recovery_allowed
from src.layout.feasibility import LayoutFeasibilityError, fit_family_layout
from src.layout.whitespace import no_displaced_whitespace
from src.layout.measurement_context import current_context, measured_phase
from utils.grounded_content import all_publishable_claims, claim_root_id


def _visible_claim_ids(board: Dict[str, Any]) -> set[str]:
    return {
        str(claim_id)
        for section in board.get("spatial_content_plan", {}).get("sections", [])
        for claim_id in section.get("claim_ids", [])
    }


def _visible_visual_ids(board: Dict[str, Any]) -> set[str]:
    return {
        str(visual["visual_id"])
        for section in board.get("spatial_content_plan", {}).get("sections", [])
        for visual in section.get("visual_assets") or []
        if isinstance(visual, dict) and visual.get("visual_id")
    }


def feasible_repair_zones(
    report: Dict[str, Any], settings: Dict[str, Any],
) -> List[str]:
    """Use the same exact-layout trigger at entry and inside the planner."""

    threshold = float(settings.get("active_utilization_threshold", 0.90))
    line_height = max(0.1, float(report.get("body_line_height_inches") or 0.61))
    gap_limit = line_height * float(settings.get("large_bottom_gap_body_lines", 2.0))
    utilization = report.get("zone_utilization") or {}
    gaps = report.get("exact_bottom_gaps") or {}
    return sorted(
        (
            str(zone_id) for zone_id, value in utilization.items()
            if float(value) < threshold or float(gaps.get(zone_id, 0.0)) > gap_limit
        ),
        key=lambda zone_id: (float(utilization[zone_id]), -float(gaps.get(zone_id, 0.0))),
    )


def needs_feasible_repair(
    report: Dict[str, Any], settings: Dict[str, Any],
) -> bool:
    return report.get("status") == "feasible" and bool(feasible_repair_zones(report, settings))


def important_visual_omitted(report: Dict[str, Any], state: Dict[str, Any]) -> bool:
    key_visual = (state.get("classified_visuals") or {}).get("key_visual")
    if not isinstance(key_visual, str) or not key_visual:
        return False
    manifest = state.get("layout_visual_source_manifest") or {}
    targets = (state.get("revision_recovery_policy") or {}).get("visual_targets", {}).get(key_visual)
    source_sections = targets if targets is not None else [sid for sid, ids in manifest.items() if key_visual in ids]
    return (
        any(recovery_allowed(state, str(sid), key_visual) for sid in source_sections)
        and key_visual in (
            (report.get("candidate_content_selection") or {}).get("omitted_visual_ids") or []
        )
    )


def _approved_visual_path(state: Dict[str, Any], visual_id: str) -> bool:
    kind, _, number = visual_id.partition("_")
    collection = state.get("images" if kind == "figure" else "tables" if kind == "table" else "") or {}
    record = collection.get(number) if isinstance(collection, dict) else None
    return isinstance(record, dict) and Path(str(record.get("path") or "")).is_file()


def _visual_recovery_candidates(
    state: Dict[str, Any], original_board: Dict[str, Any], visible: set[str],
) -> List[Tuple[str, str]]:
    manifest = state.get("layout_visual_source_manifest") or {}
    if not manifest:
        manifest = {
            str(section.get("section_id")): [
                str(visual.get("visual_id"))
                for visual in section.get("visual_assets") or []
                if isinstance(visual, dict) and visual.get("visual_id")
            ]
            for section in original_board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(section, dict) and section.get("section_id")
        }
    classified = state.get("classified_visuals") or {}
    priority = []
    for field in ("key_visual", "main_results", "method_workflow", "comparative_results"):
        values = classified.get(field) or []
        priority.extend(values if isinstance(values, list) else [values])
    priority.extend(visual for values in manifest.values() for visual in values)
    candidates = []
    seen = set(visible)
    for visual_id in priority:
        visual_id = str(visual_id or "")
        if not visual_id or visual_id in seen:
            continue
        seen.add(visual_id)
        if not _approved_visual_path(state, visual_id):
            continue
        targets = (state.get("revision_recovery_policy") or {}).get("visual_targets", {}).get(visual_id)
        section_id = next(
            (section for section in (targets if targets is not None else manifest)
             if (targets is not None or visual_id in manifest[section])
             and recovery_allowed(state, str(section), visual_id)),
            None,
        )
        if section_id:
            candidates.append((str(section_id), visual_id))
    return candidates


@measured_phase("visual_recovery")
def _try_visual_recovery(
    agent: Any,
    state: Dict[str, Any],
    original_board: Dict[str, Any],
    current: Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]],
    fixed_zones: Optional[List[Dict[str, Any]]],
    settings: Dict[str, Any],
) -> Tuple[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]], List[Dict[str, str]]]:
    """Restore only originally assigned, approved visuals; never move science."""

    attempts: List[Dict[str, str]] = []
    audit = state.get("capacity_repair_report")
    if isinstance(audit, dict):
        audit["visual_restoration"] = attempts
    limit = max(0, min(
        4,
        int(settings.get("max_visual_restore_attempts", 2)),
        int((state.get("iteration_context") or {}).get(
            "visual_restore_remaining", settings.get("max_visual_restore_attempts_per_iteration", 4)
        )),
    ))
    candidates = _visual_recovery_candidates(
        state, original_board, _visible_visual_ids(current[0])
    )[:limit]
    for section_id, visual_id in candidates:
        context = current_context()
        if context:
            context.emit("visual recovery attempt", attempt=len(attempts) + 1, limit=limit)
        trial_board = deepcopy(current[0])
        section = next((item for item in trial_board["spatial_content_plan"]["sections"]
                        if str(item.get("section_id")) == section_id), None)
        audit = {"section_id": section_id, "visual_id": visual_id, "status": "not_placed"}
        attempts.append(audit)
        if section is None:
            audit["status"] = "source_section_not_visible"
            if context:
                context.emit("visual recovery not adopted", reason=audit["status"])
            continue
        section.setdefault("visual_assets", []).append({"visual_id": visual_id})
        trial_state = dict(state)
        trial_state["layout_required_visual_ids"] = [visual_id]
        try:
            result = fit_family_layout(
                agent, trial_board, trial_state,
                str(current[2].get("family_id") or ""),
                config=state.get("critic_config") or {}, fixed_zones=fixed_zones,
            )
        except LayoutFeasibilityError as exc:
            audit["status"] = str((exc.report or {}).get("reason_code") or "no_exact_fit")
            if context:
                context.emit("visual recovery not adopted", reason=audit["status"])
            continue
        if (
            visual_id not in _visible_visual_ids(result[0])
            or not _visible_visual_ids(current[0]).issubset(_visible_visual_ids(result[0]))
            or not _visible_claim_ids(current[0]).issubset(_visible_claim_ids(result[0]))
            or not no_displaced_whitespace(
                current[2].get("composition_whitespace") or {},
                result[2].get("composition_whitespace") or {},
                tolerance=float(settings.get("max_whitespace_regression_fraction", 0.01)),
                gap_tolerance_inches=float(settings.get("max_gap_regression_inches", 0.35)),
            )
        ):
            audit["status"] = "content_or_whitespace_regression"
            if context:
                context.emit("visual recovery not adopted", reason=audit["status"])
            continue
        current = result
        audit["status"] = "restored"
        if context:
            context.emit("visual recovery adopted", attempt=len(attempts))
    return current, attempts


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
        actions, _ = CapacityActionPlanner.plan_with_reason(
            state, board, report,
            round_index=round_index, maximum_actions=maximum_actions,
        )
        return actions

    @staticmethod
    def plan_with_reason(
        state: Dict[str, Any],
        board: Dict[str, Any],
        report: Dict[str, Any],
        *,
        round_index: int,
        maximum_actions: int,
    ) -> Tuple[List[Dict[str, Any]], str]:
        sections = {
            str(item.get("section_id")): item
            for item in board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(item, dict) and item.get("section_id")
        }
        claims = all_publishable_claims(state)
        if report.get("status") == "feasible":
            sparse_zones = feasible_repair_zones(
                report, (state.get("critic_config") or {}).get("capacity_repair") or {}
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
            return actions, "actions_ready" if actions else "no_sparse_zone_action"

        if report.get("reason_code") == "NO_EXACT_COMPILABLE_VARIANT":
            return [], "exact_geometry_or_preflight"
        if report.get("reason_code") != "NO_FAST_FEASIBLE_VARIANT":
            return [], "unsupported_failure"
        pressure = []
        saw_height_pressure = bool(report.get("height_pressure_samples"))
        truncated = bool(report.get("repair_pressure_candidates_truncated"))
        if "repair_pressure_candidates" in report:
            # Schema-v5 candidates are built from every searched variant before
            # the display-only limit on the detailed trial list is applied.
            pressure.extend(report.get("repair_pressure_candidates") or [])
        else:
            # Schema-v3/v4 compatibility: include report-wide summaries so
            # pressure beyond the displayed trials is not silently discarded.
            for trial in report.get("trials") or []:
                diagnostics = trial.get("diagnostics") or {}
                saw_height_pressure |= bool(diagnostics.get("height_pressure"))
                pressure.extend(diagnostics.get("near_miss_pressure") or [])
                pressure.extend(diagnostics.get("progress_pressure") or [])
                if "near_miss_pressure" not in diagnostics:
                    pressure.extend(diagnostics.get("height_pressure") or [])
            pressure.extend(report.get("near_miss_pressure_samples") or [])
            pressure.extend(report.get("progress_pressure_samples") or [])
        if not pressure:
            if truncated:
                return [], "diagnostic_sample_limit"
            return [], "no_near_miss" if saw_height_pressure else "no_height_pressure"
        pressure.sort(
            key=lambda item: (
                -int(item.get("placed_section_count", 0)),
                float(item.get("estimated_used_in", 0))
                - float(item.get("zone_limit_in", 0)),
                str(item.get("section_id") or ""),
            ),
        )
        actions = []
        used_sections = set()
        found_repairable_overage = False
        found_text_pressure = False
        maximum_overage = float(
            (state.get("critic_config") or {}).get("capacity_repair", {}).get(
                "max_repairable_overflow_inches", 2.0
            )
        )
        for item in pressure:
            overage = float(item.get("estimated_used_in", 0)) - float(
                item.get("zone_limit_in", 0)
            )
            if overage <= 0 or overage > maximum_overage:
                continue
            found_repairable_overage = True
            components = item.get("height_components") or {}
            if (
                "text_height_in" in components
                and float(components["text_height_in"]) + 1e-6 < overage
            ):
                continue
            found_text_pressure = True
            section_id = str(item.get("section_id") or "")
            section = sections.get(section_id)
            if section is None or section_id in used_sections:
                continue
            selected_ids = (
                {str(value) for value in item.get("option_claim_ids") or []}
                if "option_claim_ids" in item else
                {str(value) for value in section.get("claim_ids", [])}
            )
            visible = sorted(
                (
                    claims[claim_id]
                    for claim_id in section.get("claim_ids", [])
                    if claim_id in claims and claim_id in selected_ids
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
        if actions:
            return actions, "actions_ready"
        if truncated:
            return [], "diagnostic_sample_limit"
        if not found_repairable_overage:
            return [], "no_near_miss"
        if not found_text_pressure:
            return [], "insufficient_target_text_height"
        return [], "no_grounded_action"


@measured_phase("capacity_repair")
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
        "schema_version": 2,
        "status": "skipped",
        "skip_reason": None,
        "mode": mode,
        "family_id": family_id,
        "rounds_attempted": 0,
        "rounds": [],
        "initial_fit": {
            "status": initial_report.get("status"),
            "reason_code": initial_report.get("reason_code"),
            "worst_zone_utilization": initial_report.get("worst_zone_utilization"),
            "largest_bottom_gap_inches": initial_report.get("largest_bottom_gap_inches"),
            "composition_whitespace": initial_report.get("composition_whitespace"),
        },
        "visual_restoration": [],
    }
    # Publish the audit before optional work; exceptions must retain the original
    # measured fit and repair progress without publishing trial content banks.
    state["capacity_repair_report"] = audit
    skip_reason = next((reason for condition, reason in (
        (state.get("generation_route") != "optimization_family", "not_loop_route"),
        (bool(state.get("improve_safe_fallback")), "exact_parent_fallback"),
        (not bool(settings.get("enabled", True)), "disabled"),
    ) if condition), None)
    if skip_reason:
        audit["skip_reason"] = skip_reason
        return initial_result, audit

    if initial_result is not None and initial_report.get("status") == "feasible":
        restored, visual_attempts = _try_visual_recovery(
            agent, state, board, initial_result, fixed_zones, settings,
        )
        audit["visual_restoration"] = visual_attempts
        if restored is not initial_result:
            initial_result = restored
            audit["status"] = "applied"
            audit["visual_restored_count"] = sum(
                item["status"] == "restored" for item in visual_attempts
            )

    if maximum_rounds < 1 or not state.get("text_model") or not state.get("tokens"):
        audit["skip_reason"] = (
            "repair_budget_exhausted" if maximum_rounds < 1 else "model_unavailable"
        )
        audit["final_fit"] = {
            "worst_zone_utilization": initial_result[2].get("worst_zone_utilization"),
            "composition_whitespace": initial_result[2].get("composition_whitespace"),
        } if initial_result else None
        return initial_result, audit

    working = dict(state)
    for field in (
        "verified_content_bank", "supplemental_evidence_bank", "content_selection",
        "content_revision", "layout_revision_constraints", "revision_contract", "revision_recovery_policy",
    ):
        working[field] = deepcopy(state.get(field))
    source_board = deepcopy(initial_result[0] if initial_result else board)
    current_report = deepcopy(initial_result[2] if initial_result else initial_report)
    if initial_result is not None:
        current_report["selected_layout_spec"] = deepcopy(initial_result[1])
    previous_worst = float(current_report.get("worst_zone_utilization", 0.0))
    for round_index in range(maximum_rounds):
        context = current_context()
        if context:
            context.emit("content repair round", round=round_index + 1, limit=maximum_rounds)
        actions, reason = CapacityActionPlanner.plan_with_reason(
            working, source_board, current_report,
            round_index=round_index,
            maximum_actions=max(1, int(settings.get("max_actions_per_round", 2))),
        )
        if not actions:
            audit["skip_reason"] = reason
            if context:
                context.emit("content repair skipped", reason=reason)
            break
        audit["rounds_attempted"] += 1
        trial = dict(working)
        for field in (
            "verified_content_bank", "supplemental_evidence_bank", "content_selection",
            "layout_revision_constraints", "revision_contract", "revision_recovery_policy",
        ):
            trial[field] = deepcopy(working.get(field))
        trial["errors"] = []
        try:
            with (context.phase("content_optimizer", round=round_index + 1)
                  if context else nullcontext()):
                trial = content_optimizer(
                    trial, board_override=source_board,
                    actions_override=actions, save=False,
                )
        except Exception as exc:
            from src.workflow.generation_failure import capture_failure
            audit["status"] = "error"
            audit["rounds"].append({"round": round_index + 1,
                                    "actions": actions, "status": "error"})
            capture_failure(state, exc, agent="content_optimizer",
                            phase="capacity_repair/content_optimizer")
            raise
        accepted = (trial.get("content_revision") or {}).get("accepted_actions") or []
        round_audit = {
            "round": round_index + 1,
            "actions": actions,
            "accepted_actions": accepted,
            "status": "no_safe_content_change",
        }
        audit["rounds"].append(round_audit)
        if trial.get("errors") or not accepted:
            if context:
                context.emit("repair not adopted", reason=round_audit["status"])
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
            if context:
                context.emit("repair not adopted", reason="still_infeasible")
            continue
        changed_ids = _visible_claim_ids(changed_board) - _visible_claim_ids(source_board)
        if not changed_ids or not changed_ids.issubset(_visible_claim_ids(result[0])):
            round_audit["status"] = "changed_content_not_visible_after_fit"
            if context:
                context.emit("repair not adopted", reason=round_audit["status"])
            continue
        candidate_worst = float(result[2].get("worst_zone_utilization", 0.0))
        if initial_result is not None and candidate_worst < previous_worst + 0.03:
            round_audit["status"] = "no_measured_density_gain"
            if context:
                context.emit("repair not adopted", reason=round_audit["status"])
            continue
        if initial_result is not None and (
            not _visible_visual_ids(initial_result[0]).issubset(_visible_visual_ids(result[0]))
            or not _visible_claim_ids(initial_result[0]).issubset(_visible_claim_ids(result[0]))
            or not no_displaced_whitespace(
                initial_result[2].get("composition_whitespace") or {},
                result[2].get("composition_whitespace") or {},
                tolerance=float(settings.get("max_whitespace_regression_fraction", 0.01)),
                gap_tolerance_inches=float(settings.get("max_gap_regression_inches", 0.35)),
            )
        ):
            round_audit["status"] = "content_or_whitespace_regression"
            if context:
                context.emit("repair not adopted", reason=round_audit["status"])
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
            "content_selection", "layout_revision_constraints", "revision_contract", "revision_recovery_policy",
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
        round_audit["composition_whitespace_after"] = result[2].get(
            "composition_whitespace"
        )
        audit["final_fit"] = {
            "worst_zone_utilization": candidate_worst,
            "composition_whitespace": result[2].get("composition_whitespace"),
        }
        audit["status"] = "applied"
        return result, audit
    if audit["status"] != "applied":
        audit["status"] = "no_safe_improvement"
    if audit["rounds_attempted"] == 0 and audit["status"] != "applied":
        audit["status"] = "skipped"
    audit["final_fit"] = {
        "worst_zone_utilization": initial_result[2].get("worst_zone_utilization"),
        "composition_whitespace": initial_result[2].get("composition_whitespace"),
    } if initial_result else None
    return initial_result, audit
