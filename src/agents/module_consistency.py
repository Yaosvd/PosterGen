"""Check and conservatively repair module membership before rendering."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.semantic.consistency import (
    audit_board, board_content_identity, digest, enabled, preserve_content,
    save_reports, sections, settings, visible_board,
    compiled_consistent,
)
from utils.grounded_content import all_publishable_claims, rematerialize_board
from utils.src.logging_utils import log_agent_info, log_agent_warning


def apply_semantic_proposal(board: dict, report: dict, proposal: dict, state: dict) -> dict | None:
    """Only confirmed object-specific errors authorize content-preserving edits."""
    if not isinstance(proposal, dict):
        return None
    sid = str(proposal.get("section_id") or "")
    module = next((m for m in report.get("modules", []) if m.get("section_id") == sid), {})
    failed = {(c["kind"], c["id"]) for c in module.get("checks", []) if c["status"] == "failed"}
    issue = (proposal.get("issue_kind"), proposal.get("issue_id"))
    if issue not in failed:
        return None
    trial = deepcopy(board)
    by_id = {str(s["section_id"]): s for s in sections(trial)}
    source = by_id.get(sid)
    target = by_id.get(str(proposal.get("target_section_id") or ""))
    operation = proposal.get("operation")
    if source is None:
        return None
    if operation == "retitle_module":
        title = proposal.get("title")
        if issue[0] != "title" or not isinstance(title, str) or not 1 <= len(title.strip()) <= 180:
            return None
        if any(char in title for char in ("\n", "<", ">", "{", "}")):
            return None
        source["section_title"] = title.strip()
    elif operation == "move_claim":
        cid = str(proposal.get("claim_id") or "")
        if issue != ("claim", cid) or target is None or target is source or cid not in source.get("claim_ids", []) or len(source["claim_ids"]) <= 1:
            return None
        source["claim_ids"].remove(cid)
        target["claim_ids"].append(cid)
        rematerialize_board(trial, all_publishable_claims(state))
    elif operation == "move_visual":
        vid = str(proposal.get("visual_id") or "")
        if issue != ("visual", vid) or target is None or target is source:
            return None
        found = [v for v in source.get("visual_assets", []) if v.get("visual_id") == vid]
        if len(found) != 1:
            return None
        source["visual_assets"].remove(found[0])
        target.setdefault("visual_assets", []).append(found[0])
    else:
        return None
    return trial if preserve_content(board, trial) and board_content_identity(board) != board_content_identity(trial) else None


def fit_nonregression(before: dict, after: dict) -> bool:
    from src.layout.whitespace import no_displaced_whitespace
    required = ("composition_whitespace", "zone_utilization", "exact_bottom_gaps")
    if any(not isinstance(before.get(key), dict) or not isinstance(after.get(key), dict)
           or not before[key] or not after[key] for key in required):
        return False
    # Tiny numeric tolerances only; repairs may not spend the ordinary density
    # repair's larger whitespace tolerance to buy semantic improvement.
    return (no_displaced_whitespace(before["composition_whitespace"], after["composition_whitespace"],
                                    tolerance=1e-6, gap_tolerance_inches=0.01)
            and min(after["zone_utilization"].values()) + 1e-6 >= min(before["zone_utilization"].values())
            and max(after["exact_bottom_gaps"].values()) <= max(before["exact_bottom_gaps"].values()) + 0.01)


def _refit(state: dict, board: dict) -> tuple[dict | None, str]:
    """One isolated same-topology exact fit, without content-model repairs."""
    from src.agents.font_agent import FontAgent
    from src.agents.layout_agent import LayoutAgent
    from src.agents.layout_preflight import layout_preflight_node
    from src.agents.revision_contract import check_contract
    from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError
    from src.layout.measurement_context import measurement_scope
    if not check_contract(state, board)["passed"]:
        return None, "revision_contract_conflict"
    trial = deepcopy(state)
    trial["tokens"] = state.get("tokens")
    trial["story_board"] = deepcopy(board)
    trial["errors"] = []
    trial["layout_preflight_failed"] = False
    constraints = trial.setdefault("layout_revision_constraints", {}) or {}
    constraints = deepcopy(constraints)
    constraints["must_retain_claim_ids"] = [cid for s in sections(board) for cid in s.get("claim_ids", [])]
    constraints["must_retain_visual_ids"] = [v["visual_id"] for s in sections(board) for v in s.get("visual_assets", [])]
    trial["layout_revision_constraints"] = constraints
    spec = state.get("layout_spec") or {}
    if not spec.get("zones"):
        return None, "missing_geometry_baseline"
    with TemporaryDirectory(prefix="postergen-semantic-fit-") as temporary:
        trial["output_dir"] = temporary
        with measurement_scope((state.get("critic_config") or {}).get("layout_performance") or {}):
            agent = LayoutAgent()
            try:
                fitted, new_spec, fit = fit_family_layout(agent, board, trial, spec["family_id"],
                    config=trial.get("critic_config") or {}, fixed_zones=spec["zones"])
            except LayoutFeasibilityError:
                return None, "repair_infeasible"
            if not preserve_content(board, fitted):
                return None, "repair_lost_content"
            if not fit_nonregression(state.get("layout_feasibility_report") or {}, fit):
                return None, "repair_layout_regression"
            trial.update(optimized_story_board=fitted, layout_spec=new_spec,
                         layout_feasibility_report=fit,
                         layout_content_selection=deepcopy(fit.get("candidate_content_selection") or {}))
            agent(trial, mode="final")
            if trial.get("errors"):
                raise RuntimeError("Semantic repair compilation failed: " + str(trial["errors"][-1]))
            # Preserve the existing font/emphasis presets; membership repair does
            # not need another keyword model call or permit smaller type.
            font = FontAgent()
            trial["styled_layout"] = font._apply_styling(trial["design_layout"], trial.get("color_scheme") or {},
                                                        trial.get("keywords") or {}, trial)
            layout_preflight_node(trial, persist=False)
            if trial.get("layout_preflight_failed"):
                return None, "repair_preflight_failed"
    trial["output_dir"] = state["output_dir"]
    return trial, "passed"


def _rendered_baseline(state: dict) -> dict | None:
    """An isolated original render permits comparison with the final Critic.

    Only needed for an otherwise admissible automatic repair. Temporary rendering
    never publishes a template, global event, Lineage, or a Campaign commit.
    """
    from src.agents.renderer import renderer_node
    from src.agents.render_fit_audit import render_fit_audit_node
    from src.critic.engine import PosterCritic
    log_agent_info("module_consistency", "checking temporary original-render baseline; not a Batch iteration")
    baseline = deepcopy(state)
    baseline["tokens"] = state.get("tokens")
    baseline["timing_metrics"] = state.get("timing_metrics")
    baseline["errors"] = []
    baseline["module_semantic_blocked"] = False
    baseline["improve_safe_fallback"] = True  # audit only; never geometry correction
    with TemporaryDirectory(prefix="postergen-semantic-baseline-") as temporary:
        baseline["output_dir"] = temporary
        baseline["current_candidate"] = {"candidate_id": "semantic_repair_baseline", "candidate_dir": temporary}
        renderer_node(baseline)
        if baseline.get("errors"):
            raise RuntimeError("Semantic baseline rendering failed: " + str(baseline["errors"][-1]))
        render_fit_audit_node(baseline)
        if baseline.get("layout_preflight_failed") or (baseline.get("render_fit_report") or {}).get("status") != "passed":
            return None
        PosterCritic(state.get("critic_config"))(baseline)
        report = baseline["critic_report"]
        # An evaluator outage cannot serve as an artificially low baseline.
        if any(str(i.get("issue_id") or "").startswith("EVALUATOR-") for i in report.get("issues", [])):
            return None
        visual = next((e for e in report.get("evaluations", []) if e.get("evaluator") == "visual"), {})
        if (visual.get("metadata") or {}).get("model_evaluation_completed") is not True:
            return None
        return {"dimension_scores": report.get("dimension_scores") or {},
                "rubric_version": report.get("rubric_version"),
                "board_identity": digest(board_content_identity(visible_board(state))),
                "styled_layout_digest": digest(state.get("styled_layout") or [])}


def apply_semantic_repair_admission(state: dict, report: dict) -> None:
    baseline = state.get("module_semantic_repair_baseline")
    if not baseline:
        return
    dimensions = ("scientific_integrity", "content_quality", "layout_integrity", "readability",
                  "visual_hierarchy", "visual_balance", "aesthetics")
    old, new = baseline.get("dimension_scores") or {}, report.get("dimension_scores") or {}
    reasons = [name for name in dimensions if name not in old or name not in new or float(new[name]) + 0.01 < float(old[name])]
    if baseline.get("rubric_version") != report.get("rubric_version"):
        reasons.append("rubric_not_comparable")
    report["module_semantic_admission"] = {"passed": not reasons, "regressed_dimensions": reasons,
                                           "baseline": baseline, "raw_archive_eligible": report.get("archive_eligible")}
    if reasons:
        report["archive_eligible"] = False
        report["template_eligible"] = False
        report["loop_disposition"] = "semantic_repair_regression"


def module_semantic_prepare_node(state: dict) -> dict:
    if not enabled(state):
        return state
    # Start from the Planner/Curator's current board, never a stale visible parent.
    report = audit_board(state, state.get("story_board") or {}, refresh_index=True)
    state["module_consistency_report"] = report
    state["module_semantic_contracts"] = {m["section_id"]: deepcopy(m)
        for m in report.get("modules", []) if m["status"] == "passed"}
    save_reports(state)
    log_agent_info("module_consistency", f"initial module check: {report['status']} | {report.get('coverage', {})}")
    return state


def module_semantic_finalize_node(state: dict) -> dict:
    if not enabled(state) or state.get("layout_preflight_failed") or state.get("errors"):
        return state
    board = visible_board(state)
    report = audit_board(state, board, refresh_index=True)
    original_report = deepcopy(report)
    original_board = deepcopy(board)
    state["module_consistency_report"] = deepcopy(report)
    audit = {"schema_version": 1, "rounds": [], "status": "not_needed" if report["status"] == "passed" else "unresolved"}
    locked = bool(state.get("template_validation_topology") or state.get("improve_safe_fallback"))
    for round_index in range(settings(state)["max_repairs"] if not locked else 0):
        if report["status"] != "failed":
            break
        proposals = [p for m in report["modules"] for p in m.get("repair_proposals") or []]
        proposal = next((p for p in proposals if apply_semantic_proposal(board, report, p, state) is not None), None)
        if proposal is None:
            break
        proposed = apply_semantic_proposal(board, report, proposal, state)
        entry = {"round": round_index + 1, "operation": proposal.get("operation"),
                 "section_id": proposal.get("section_id"), "status": "not_adopted"}
        audit["rounds"].append(entry)
        candidate_report = audit_board(state, proposed)
        # All modules must pass before attempting geometry. No trading one
        # mismatch for another or deleting content to get a green check.
        if candidate_report["status"] != "passed":
            entry["reason"] = "repair_semantics_unverified"
            def failures(result):
                return {(m["section_id"], c["kind"], c["id"]) for m in result.get("modules", [])
                        for c in m.get("checks", []) if c["status"] == "failed"}
            if (candidate_report["status"] == "failed" and
                not any(m["status"] == "inconclusive" for m in candidate_report["modules"]) and
                failures(candidate_report) < failures(report)):
                board, report = proposed, candidate_report
                entry["status"] = "staged"
                continue
            break
        trial, reason = _refit(state, proposed)
        if trial is None:
            entry["reason"] = reason
            break
        final_report = audit_board(state, visible_board(trial))
        if final_report["status"] != "passed":
            entry["reason"] = "refit_semantics_unverified"
            break
        baseline = _rendered_baseline(state)
        if baseline is None:
            entry["reason"] = "rendered_quality_baseline_unavailable"
            break
        fields = ("story_board", "optimized_story_board", "layout_spec", "layout_content_selection",
                  "layout_feasibility_report", "design_layout", "styled_layout", "final_column_analysis",
                  "layout_preflight_report", "revision_execution_report", "revision_safety_report")
        for field in fields:
            if field in trial:
                state[field] = trial[field]
        board, report = visible_board(state), final_report
        state["module_semantic_repair_baseline"] = baseline
        owners = deepcopy(state.get("layout_visual_source_manifest") or {})
        old_owners = {v["visual_id"]: s["section_id"] for s in sections(original_board) for v in s.get("visual_assets", [])}
        new_owners = {v["visual_id"]: s["section_id"] for s in sections(board) for v in s.get("visual_assets", [])}
        for vid, sid in new_owners.items():
            if old_owners.get(vid) != sid:
                owners = {key: [v for v in ids if v != vid] for key, ids in owners.items()}
                owners.setdefault(sid, []).append(vid)
        state["layout_visual_source_manifest"] = owners
        entry.update(status="adopted", reason="semantic_and_layout_checks_passed")
        for staged in audit["rounds"]:
            if staged["status"] == "staged":
                staged.update(status="adopted", reason="complete_transaction_verified")
        audit["status"] = "repaired"
        target = Path(state["output_dir"]) / "content"
        target.mkdir(parents=True, exist_ok=True)
        for field in fields:
            if state.get(field) is not None:
                (target / f"{field}.json").write_text(json.dumps(state[field], ensure_ascii=False, indent=2), encoding="utf-8")
    if audit["status"] != "repaired":
        board, report = original_board, original_report
        for entry in audit["rounds"]:
            if entry["status"] == "staged":
                entry.update(status="not_adopted", reason="complete_repair_not_verified")
    if report["status"] == "passed" and not compiled_consistent(state, board):
        report["status"] = "inconclusive"
        report["reason"] = "compiled_content_mismatch"
    state["module_consistency_report"] = report
    state["module_semantic_contracts"] = {m["section_id"]: deepcopy(m) for m in report.get("modules", []) if m["status"] == "passed"}
    state["module_semantic_repair_report"] = audit
    state["module_semantic_blocked"] = report["status"] != "passed"
    save_reports(state)
    log_agent_info("module_consistency", f"final module check: {report['status']} | {report.get('coverage', {})}")
    if state["module_semantic_blocked"]:
        log_agent_warning("module_consistency", "semantic admission blocked; candidate not rendered or archived")
    return state


def semantic_failure_report(state: dict, config: dict) -> dict:
    candidate = state.get("current_candidate") or {}
    report = state.get("module_consistency_report") or {}
    return {"schema_version": 3, "report_kind": "module_consistency_blocked",
            "critic_system_version": config["critic_system_version"], "rubric_version": config["rubric_version"],
            "candidate_id": candidate.get("candidate_id"),
            "iteration": (state.get("iteration_context") or {}).get("iteration"),
            "layout_family": (state.get("layout_spec") or {}).get("family_id"),
            "decision": "semantic_failed" if report.get("status") == "failed" else "semantic_unresolved",
            "overall_score": None, "archive_eligible": False, "template_eligible": False,
            "hard_gate_passed": False, "module_consistency": deepcopy(report),
            "poster_evaluation": {"evaluated": False, "reason": "module_consistency_blocked"},
            "task_evaluation": {"status": "blocked_by_content", "passed": False, "evaluated": False,
                                "reasons": ["module_consistency_blocked"]},
            "issues": [{"issue_id": "MODULE-CONSISTENCY-BLOCKED", "scope": "scientific_integrity",
                        "severity": "major", "observation": "Module relationships did not pass source-backed checks",
                        "required_outcome": "Verify the module title, claims and visuals against original sources",
                        "allowed_operations": ["repair_module_semantics"],
                        "forbidden_operations": ["rewrite_claim", "delete_content_to_pass"]}],
            "rejection_summary": "Module semantic check failed or is inconclusive; no poster quality score assigned"}
