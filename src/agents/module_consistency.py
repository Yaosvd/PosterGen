"""Check and conservatively repair module membership before rendering."""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.semantic.consistency import (
    audit_board, board_content_identity, enabled, preserve_content,
    save_reports, sections, settings, visible_board,
    compiled_consistent,
)
from utils.grounded_content import (all_publishable_claims, rematerialize_board,
                                    claim_root_id, relevant_evidence_ids, find_claim_by_evidence)
from utils.src.logging_utils import log_agent_info, log_agent_warning

REPAIR_POLICY = "source_association_repair_v2"


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
        if len(found) != 1 or any(v.get("visual_id") == vid for v in target.get("visual_assets", [])):
            return None
        source["visual_assets"].remove(found[0])
        target.setdefault("visual_assets", []).append(found[0])
    else:
        return None
    return trial if preserve_content(board, trial) and board_content_identity(board) != board_content_identity(trial) else None


def _amend_contract(state: dict, original: dict, board: dict, proposals: list[dict]) -> bool:
    """Replay only confirmed edits; never waive an unrelated Planner constraint."""
    from src.agents.revision_contract import board_identity, check_contract, claim_recovery_allowed
    if not check_contract(state, original)["passed"]:
        return False
    expected = deepcopy(original)
    for proposal in proposals:
        changed = apply_semantic_proposal(expected, state.get("module_consistency_report") or {}, proposal, state)
        if changed is None:
            return False
        expected = changed
    if expected != board:
        return False
    policy = deepcopy(state.get("revision_recovery_policy") or {})
    claims = all_publishable_claims(state)
    for proposal in proposals:
        sid = str(proposal.get("target_section_id") or "")
        if proposal["operation"] == "move_visual":
            vid = proposal["visual_id"]
            if vid in policy.get("unusable_visual_ids", []) or [sid, vid] in policy.get("excluded_visual_occurrences", []):
                return False
            policy.setdefault("visual_targets", {})[vid] = [sid]
        elif proposal["operation"] == "move_claim":
            if not claim_recovery_allowed(state, sid, claims.get(proposal["claim_id"]) or {}):
                return False
    state["revision_recovery_policy"] = policy
    if state.get("revision_contract"):
        state["revision_contract"]["desired_board"] = board_identity(board)
        state["revision_contract"]["recovery_policy"] = deepcopy(policy)
        state["revision_contract"].setdefault("semantic_amendments", []).extend(
            {**deepcopy(p), "policy": REPAIR_POLICY} for p in proposals)
    return check_contract(state, board)["passed"]


def _owned_inventory(board: dict) -> dict:
    return {str(s["section_id"]): {
        "claims": Counter(zip(s.get("claim_ids") or [], s.get("text_content") or [])),
        "visuals": Counter(v["visual_id"] for v in s.get("visual_assets") or []),
        "title": s.get("section_title"),
    } for s in sections(board)}


def _content_changes_safe(before: dict, after: dict, state: dict, actions: list[dict], affected: set[str]) -> bool:
    """Only verified action receipts may replace roots or add related claims."""
    if any(not s.get("claim_ids") or len(s["claim_ids"]) != len(s.get("text_content") or [])
           or len(s["claim_ids"]) != len(set(s["claim_ids"])) for s in sections(after)):
        return False
    old, new = _owned_inventory(before), _owned_inventory(after)
    if set(old) != set(new):
        return False
    index = all_publishable_claims(state)
    allowed_new, allowed_old = {}, {}
    for action in actions:
        sid = str(action.get("section_id") or "")
        if sid not in affected or action.get("operation") not in {
            "use_claim_variant", "create_compact_variant", "add_existing_claim", "add_claim_from_evidence"
        }:
            return False
        allowed_new.setdefault(sid, set()).update(str(cid) for cid in action.get("result_claim_ids", []))
        if action["operation"] in {"use_claim_variant", "create_compact_variant"}:
            allowed_old.setdefault(sid, set()).add(str(action.get("claim_id")))
    for sid in old:
        if old[sid]["visuals"] != new[sid]["visuals"] or old[sid]["title"] != new[sid]["title"]:
            return False
        if sid not in affected and old[sid] != new[sid]:
            return False
        old_ids = Counter(cid for cid, _ in old[sid]["claims"].elements())
        new_ids = Counter(cid for cid, _ in new[sid]["claims"].elements())
        if (not set(old_ids - new_ids).issubset(allowed_old.get(sid, set()))
            or not set(new_ids - old_ids).issubset(allowed_new.get(sid, set()))):
            return False
        def roots(ids):
            return Counter(claim_root_id(index.get(cid) or {"claim_id": cid}) for cid in ids.elements())
        old_roots, new_roots = roots(old_ids), roots(new_ids)
        if old_roots - new_roots or any(new_roots[root] > count for root, count in old_roots.items()):
            return False
        for cid, text in new[sid]["claims"].elements():
            if cid not in index or index[cid].get("text") != text:
                return False
    return True


def _content_actions(state: dict, board: dict, report: dict, affected: set[str]) -> list[dict]:
    from src.layout.capacity_repair import CapacityActionPlanner
    from src.agents.revision_contract import claim_recovery_allowed
    scoped = deepcopy(report)
    for zone in (scoped.get("selected_layout_spec") or {}).get("zones", []):
        zone["section_ids"] = [sid for sid in zone.get("section_ids", []) if str(sid) in affected]
    for field in ("repair_pressure_candidates", "near_miss_pressure_samples", "progress_pressure_samples"):
        if field in scoped:
            scoped[field] = [p for p in scoped[field] if str(p.get("section_id")) in affected]
    actions = CapacityActionPlanner.plan(state, board, scoped, round_index=0, maximum_actions=2)
    actions = [a for a in actions if a["section_id"] in affected][:2]
    selected = {cid for s in sections(board) for cid in s.get("claim_ids", [])}
    index = all_publishable_claims(state)
    selected_roots = {claim_root_id(index.get(cid) or {"claim_id": cid}) for cid in selected}
    for action in actions:
        if action["operation"] == "add_existing_claim":
            relevant = relevant_evidence_ids(state, action["section_id"])
            # Current-module evidence supports custom/cross-chapter modules too.
            relevant = sorted(set(relevant) | {str(eid) for s in sections(board)
                if str(s["section_id"]) == action["section_id"] for cid in s.get("claim_ids", [])
                for eid in (index.get(cid) or {}).get("evidence_ids", [])})
            action["evidence_ids"] = relevant
            excluded = selected | {cid for cid, claim in index.items()
                if claim_root_id(claim) in selected_roots
                or not claim_recovery_allowed(state, action["section_id"], claim)}
            available = find_claim_by_evidence(index.values(), relevant, excluded_ids=excluded)
            if available:
                action["claim_id"] = available["claim_id"]
            else:
                action["operation"] = "add_claim_from_evidence"
    return actions


def _refit(state: dict, board: dict, *, proposals: list[dict] | None = None,
           audit: dict | None = None, semantic_report: dict | None = None) -> tuple[dict | None, str]:
    """At most two isolated fixed-topology fits, with one grounded content round.

    Quality is assessed on the corrected poster, never against its erroneous
    predecessor. Source checks, exact geometry and normal Critic still gate it.
    """
    from src.agents.font_agent import FontAgent
    from src.agents.layout_agent import LayoutAgent
    from src.agents.layout_preflight import layout_preflight_node
    from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError
    from src.layout.measurement_context import measurement_scope
    from src.agents.content_optimizer import GroundedContentOptimizer
    proposals = proposals or []
    audit = audit if audit is not None else {}
    trial = deepcopy(state)
    trial["tokens"] = state.get("tokens")
    trial["timing_metrics"] = state.get("timing_metrics")
    for field in ("module_semantic_cache", "module_semantic_runtime"):
        trial[field] = state.setdefault(field, {} if field.endswith("cache") else {"model_calls": 0})
    if not _amend_contract(trial, visible_board(state), board, proposals):
        return None, "revision_contract_conflict"
    trial["story_board"] = deepcopy(board)
    trial["errors"] = []
    trial["layout_preflight_failed"] = False
    trial["module_semantic_contracts"] = {m["section_id"]: deepcopy(m)
        for m in (semantic_report or {}).get("modules", []) if m["status"] == "passed"}
    affected = {str(p.get(key)) for p in proposals for key in ("section_id", "target_section_id") if p.get(key)}
    spec = state.get("layout_spec") or {}
    if not spec.get("zones"):
        return None, "missing_geometry_baseline"
    remaining = max(0, int((state.get("iteration_context") or {}).get("capacity_repair_remaining",
        (state.get("critic_config") or {}).get("capacity_repair", {}).get("max_rounds_per_iteration", 4)))
        - int((state.get("capacity_repair_report") or {}).get("rounds_attempted", 0)))
    with TemporaryDirectory(prefix="postergen-semantic-fit-") as temporary:
        trial["output_dir"] = temporary
        with measurement_scope((state.get("critic_config") or {}).get("layout_performance") or {}):
            agent = LayoutAgent()
            current = deepcopy(board)
            corrected_fallback = None
            for attempt in range(2):
                trial["semantic_refit_constraints"] = {
                    "policy": REPAIR_POLICY,
                    "must_retain_claim_ids": [cid for s in sections(current) for cid in s.get("claim_ids", [])],
                    "must_retain_visual_ids": [v["visual_id"] for s in sections(current) for v in s.get("visual_assets", [])],
                }
                audit["refit_attempts"] = audit.get("refit_attempts", 0) + 1
                log_agent_info("module_consistency", f"semantic repair: refitting corrected modules ({attempt + 1}/2)")
                result = None
                try:
                    result = fit_family_layout(agent, current, trial, spec["family_id"],
                        config=trial.get("critic_config") or {}, fixed_zones=spec["zones"])
                    fit_report = {**result[2], "selected_layout_spec": result[1]}
                except LayoutFeasibilityError as exc:
                    fit_report = exc.report or {}
                    if attempt and corrected_fallback is not None:
                        # Optional text work cannot erase an already feasible
                        # corrected association. This is not the erroneous board.
                        result, current, trial = corrected_fallback
                        audit["content_status"] = "rolled_back_to_corrected_fit"
                        trial["tokens"] = state.get("tokens")
                        trial["timing_metrics"] = state.get("timing_metrics")
                        for field in ("module_semantic_cache", "module_semantic_runtime"):
                            trial[field] = state[field]
                content_enabled = (trial.get("loop_config") or {}).get("content_optimization", {}).get(
                    "enabled", (trial.get("critic_config") or {}).get("content_optimization", {}).get("enabled", True))
                if (attempt or not remaining or not affected or not content_enabled
                    or not trial.get("text_model") or trial.get("tokens") is None
                    or not (trial.get("critic_config") or {}).get("capacity_repair", {}).get("enabled", True)):
                    break
                actions = _content_actions(trial, current, fit_report, affected)
                if not actions:
                    break
                audit["content_rounds_attempted"] = 1
                audit["content_actions_requested"] = deepcopy(actions)
                before_content = deepcopy(current)
                before_trial = deepcopy(trial)
                if result is not None:
                    corrected_fallback = (deepcopy(result), deepcopy(current), before_trial)
                GroundedContentOptimizer()(trial, board_override=current, actions_override=actions, save=False)
                if trial.get("errors"):
                    raise RuntimeError("Semantic repair content optimization failed: " + str(trial["errors"][-1]))
                accepted = (trial.get("content_revision") or {}).get("accepted_actions") or []
                audit["content_revision"] = deepcopy(trial.get("content_revision") or {})
                if not accepted or not _content_changes_safe(before_content, trial["story_board"], trial, accepted, affected):
                    audit["content_status"] = "not_adopted"
                    trial = before_trial
                    # Keep live cost/budget objects even when staged content rolls back.
                    trial["tokens"] = state.get("tokens")
                    trial["timing_metrics"] = state.get("timing_metrics")
                    for field in ("module_semantic_cache", "module_semantic_runtime"):
                        trial[field] = state[field]
                    break
                current = deepcopy(trial["story_board"])
                audit["content_status"] = "staged"
                log_agent_info("module_consistency", f"semantic repair: {len(accepted)} verified content actions staged")
            if result is None:
                audit["fit_failure"] = {"reason_code": fit_report.get("reason_code"), "stage": fit_report.get("failure_stage")}
                return None, "corrected_association_layout_infeasible"
            fitted, new_spec, fit = result
            if _owned_inventory(current) != _owned_inventory(fitted):
                return None, "repair_lost_content"
            if audit.get("content_status") == "staged":
                # Keep the earlier Planner/content actions in the same candidate's
                # outcome audit; semantic text adjustment must not erase them.
                prior = state.get("content_revision") or {}
                revision = deepcopy(trial.get("content_revision") or {})
                for key in ("accepted_actions", "rejected_actions", "created_claim_ids"):
                    revision[key] = deepcopy(prior.get(key) or []) + list(revision.get(key) or [])
                trial["content_revision"] = revision
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
    trial.pop("semantic_refit_constraints", None)
    trial.pop("module_semantic_repair_baseline", None)
    return trial, "passed"


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
    state.pop("module_semantic_repair_baseline", None)  # historical snapshots cannot revive the retired gate
    audit = {"schema_version": 2, "policy": REPAIR_POLICY, "quality_admission": "normal_critic",
             "rounds": [], "refit_attempts": 0, "content_rounds_attempted": 0,
             "status": "not_needed" if report["status"] == "passed" else "unresolved"}
    state["module_semantic_repair_report"] = audit
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
                 "section_id": proposal.get("section_id"), "proposal": deepcopy(proposal),
                 "target_section_id": proposal.get("target_section_id"), "status": "not_adopted"}
        audit["rounds"].append(entry)
        log_agent_info("module_consistency", "semantic repair: " + str(proposal.get("operation"))
                       + " | " + str(proposal.get("section_id")) + " -> " + str(proposal.get("target_section_id") or "same module"))
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
        trial, reason = _refit(state, proposed, proposals=[r["proposal"] for r in audit["rounds"]],
                               audit=audit, semantic_report=candidate_report)
        audit["association_status"] = "verified"
        audit["layout_status"] = reason
        if trial is None:
            entry["reason"] = reason
            log_agent_warning("module_consistency", "semantic repair: correct association verified; " + reason)
            break
        final_report = audit_board(trial, visible_board(trial), refresh_index=True)
        if final_report["status"] != "passed" or not compiled_consistent(trial, visible_board(trial)):
            entry["reason"] = "refit_semantics_unverified"
            break
        fields = ("story_board", "optimized_story_board", "layout_spec", "layout_content_selection",
                  "layout_feasibility_report", "design_layout", "styled_layout", "final_column_analysis",
                  "layout_preflight_report", "revision_execution_report", "revision_safety_report",
                  "revision_contract", "revision_recovery_policy", "layout_revision_constraints",
                  "verified_content_bank", "supplemental_evidence_bank", "content_selection", "content_revision",
                  "paper_semantic_index")
        for field in fields:
            if field in trial:
                state[field] = trial[field]
        board, report = visible_board(state), final_report
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
        if audit.get("content_status") == "staged":
            audit["content_status"] = "adopted"
        log_agent_info("module_consistency", "semantic repair: adopted; normal Critic evaluation follows")
        target = Path(state["output_dir"]) / "content"
        target.mkdir(parents=True, exist_ok=True)
        for field in fields:
            if state.get(field) is not None:
                (target / f"{field}.json").write_text(json.dumps(state[field], ensure_ascii=False, indent=2), encoding="utf-8")
    if audit["status"] != "repaired":
        board, report = original_board, original_report
        if audit.get("content_status") == "staged":
            audit["content_status"] = "rolled_back"
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
