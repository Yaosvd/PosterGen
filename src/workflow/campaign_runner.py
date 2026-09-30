"""Execution engine for resumable continuous poster optimization campaigns."""

from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.templates.library import build_paper_profile
from src.workflow.campaign import (
    CampaignHandle,
    CampaignManager,
    IterationAttempt,
    _atomic_json,
    _canonical_digest,
)
from utils.src.logging_utils import log_agent_error, log_agent_success


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _portfolio_snapshot(portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
    mode_counts = portfolio_state.get("mode_counts") or {}
    return {
        "schema_version": int(portfolio_state.get("schema_version", 0) or 0),
        "commit_count": sum(
            int(value or 0) for value in mode_counts.values()
        ),
        "digest": _canonical_digest(portfolio_state),
        "lineage_count": len(portfolio_state.get("lineages") or {}),
    }


def _knowledge_snapshot(
    owner: Any,
    manager: CampaignManager,
    handle: CampaignHandle,
    portfolio_state: Dict[str, Any],
    content_memory: Dict[str, Any],
) -> Dict[str, Any]:
    campaign_state = manager.load_campaign_state(handle)
    return {
        "campaign_iteration": int(
            campaign_state.get("last_completed_iteration", 0)
        ),
        "campaign_content": manager.content_memory_snapshot(content_memory),
        "portfolio": _portfolio_snapshot(portfolio_state),
        "template_library": owner.library.knowledge_snapshot(),
        "global_design_memory": owner.global_knowledge.knowledge_snapshot(),
        "captured_at": _utc_now(),
    }


def run_optimization_campaign(
    owner: Any,
    state: Dict[str, Any],
    *,
    foundation_ready: bool = False,
    max_iterations_for_test: Optional[int] = None,
) -> Dict[str, Any]:
    """Run or resume one campaign until the user requests a stop.

    ``COMPLETED.json`` is the only iteration commit point. An interrupted
    attempt is abandoned, and the same iteration number is attempted again on
    the next launch.
    """

    base_output_dir = Path(state["output_dir"])
    base_output_dir.mkdir(parents=True, exist_ok=True)
    state["critic_config"] = owner.config
    handle = owner.campaign_manager.open_campaign(
        state,
        resume_mode=owner.resume_mode,
        campaign_id=owner.requested_campaign_id,
    )

    with owner.campaign_manager.lease(handle):
        return _run_locked(
            owner,
            state,
            handle,
            base_output_dir,
            foundation_ready=foundation_ready,
            max_iterations_for_test=max_iterations_for_test,
        )


def _run_locked(
    owner: Any,
    state: Dict[str, Any],
    handle: CampaignHandle,
    base_output_dir: Path,
    *,
    foundation_ready: bool,
    max_iterations_for_test: Optional[int],
) -> Dict[str, Any]:
    manager: CampaignManager = owner.campaign_manager
    manager.apply_persisted_input_paths(handle, state)
    last_completed = manager.recover_incomplete(handle)
    _discard_uncommitted_bundles(owner, handle)
    campaign_state = manager.load_campaign_state(handle)

    if campaign_state.get("random_seed") is not None:
        owner.random_seed = int(campaign_state["random_seed"])
    owner.selector.rng.seed(owner.random_seed)
    owner.selector.counts = {
        str(key): int(value)
        for key, value in (campaign_state.get("strategy_counts") or {}).items()
    }
    portfolio_state = owner.portfolio_scheduler.normalize(
        campaign_state.get("portfolio_state")
    )
    prior_batch = campaign_state.get("active_batch") or {}
    batch = manager.open_batch(
        handle,
        target_iterations=owner.batch_iterations,
        mode=owner.batch_mode,
        target_lineage_id=owner.target_lineage_id,
        batch_id=owner.requested_batch_id,
        new_batch=owner.new_batch,
    )

    batch_resumed = bool(batch.get("last_resumed_at")) or (
        prior_batch.get("batch_id") == batch["batch_id"]
        and int(prior_batch.get("completed_iterations", 0))
        < int(batch["target_iterations"])
    )
    batch_mode = batch["schedule_policy"]["mode"]
    target_lineage_id = batch["schedule_policy"].get("target_lineage_id")
    session_id = owner.storage.create_session(state["poster_name"])
    manager.register_session(handle, session_id, base_output_dir)
    loop_state: Dict[str, Any] = {
        "schema_version": 2,
        "campaign_id": handle.campaign_id,
        "session_id": session_id,
        "resumed": bool(handle.resumed),
        "status": "INITIALIZING",
        "started_at": _utc_now(),
        "updated_at": _utc_now(),
        "paper_id": handle.manifest.get("paper_sha256", state["poster_name"]),
        "run_output_dir": str(base_output_dir),
        "iteration": last_completed,
        "last_completed_iteration": last_completed,
        "session_completed_iterations": 0,
        "batch": dict(batch),
        "active_batch": dict(batch),
        "batch_mode": batch_mode,
        "portfolio_state": portfolio_state,
        "accepted_count": int(campaign_state.get("accepted_count", 0)),
        "rejected_count": int(campaign_state.get("rejected_count", 0)),
        "template_count": int(campaign_state.get("template_count", 0)),
        "validation_evidence_count": int(
            campaign_state.get("validation_evidence_count", 0)
        ),
        "best_candidate": campaign_state.get("best_candidate"),
        "strategy_counts": dict(owner.selector.counts),
        "random_seed": owner.random_seed,
        "stop_reason": None,
    }
    owner._active_campaign = handle
    state["loop_state"] = loop_state
    state["loop_config"] = {
        "enabled": True,
        "session_id": session_id,
        "campaign_id": handle.campaign_id,
        "resume_mode": owner.resume_mode,
        "content_optimization": dict(
            owner.config.get("content_optimization", {})
        ),
        "batch": {
            "batch_id": batch["batch_id"],
            "target_iterations": batch["target_iterations"],
            "mode": batch_mode,
            "target_lineage_id": target_lineage_id,
        },
    }
    owner._checkpoint(loop_state)
    owner._progress(
        loop_state, "session", campaign_id=handle.campaign_id,
        batch_id=batch["batch_id"], mode=batch_mode,
        resumed=bool(handle.resumed), batch_resumed=batch_resumed,
        completed=int(batch["completed_iterations"]),
        target=int(batch["target_iterations"]),
        accepted=loop_state["accepted_count"], rejected=loop_state["rejected_count"],
        templates=loop_state["template_count"],
        validation_evidence_count=loop_state["validation_evidence_count"],
        best_score=(loop_state.get("best_candidate") or {}).get("score", "-"),
        mode_weights=(batch.get("schedule_policy") or {}).get("mode_weights"),
    )
    owner._notify(
        loop_state,
        (
            f"Resuming campaign after iteration {last_completed}"
            if last_completed
            else "Preparing scientific foundation"
        ),
    )

    foundation_loaded = False
    if manager.has_foundation(handle):
        foundation_loaded = manager.load_foundation(handle, state)
    owner._progress(loop_state, "foundation", action=(
        "reused verified campaign snapshot" if foundation_loaded else
        "using supplied verified state" if foundation_ready else "building from paper"
    ))
    if not foundation_loaded and not foundation_ready:
        state["output_dir"] = str(base_output_dir)
        state = owner._run_nodes(state, owner.foundation_nodes, stage="foundation")

    if owner.control.stop_requested:
        return _finish(
            owner,
            state,
            loop_state,
            base_output_dir,
            "user_force_stop"
            if owner.control.force_stop_requested
            else "user_requested_before_iterations",
        )
    if state.get("errors") or not state.get("verification_passed"):
        loop_state.update({
            "status": "FAILED_REQUIRES_USER",
            "updated_at": _utc_now(),
            "stop_reason": "scientific_foundation_failed",
            "errors": list(state.get("errors", [])),
        })
        batch["status"] = "FAILED_REQUIRES_USER"
        batch["stop_reason"] = "scientific_foundation_failed"
        manager.save_batch(handle, batch)
        loop_state["batch"] = dict(batch)
        loop_state["active_batch"] = dict(batch)
        owner._checkpoint(loop_state)
        owner._progress(loop_state, "error", stage="scientific_foundation",
                        error_type="FoundationError",
                        message="; ".join(loop_state["errors"]) or "verification did not pass")
        _emit_finished(owner, loop_state)
        state["loop_state"] = loop_state
        state["output_dir"] = str(base_output_dir)
        return state
    if not foundation_loaded:
        manager.save_foundation(handle, state)

    manager.load_last_snapshot(handle, state)
    campaign_content_memory = manager.load_campaign_content_memory(
        handle, state
    )
    state.setdefault("verified_content_bank", {"schema_version": 1, "claims": []})
    state.setdefault("supplemental_evidence_bank", {"schema_version": 1, "items": []})
    state.setdefault("content_selection", {
        "schema_version": 1,
        "replacements": {},
        "active_supplemental_claim_ids": [],
        "disabled_claim_ids": [],
        "last_changed_iteration": {},
    })

    frozen = {
        name: deepcopy(state.get(name))
        for name in owner.SCIENTIFIC_FIELDS
    }
    paper_profile = build_paper_profile(state)
    _reconcile_accepted_bundles(owner, handle)
    _reconcile_layout_archetypes(
        owner,
        handle,
        paper_id=str(loop_state["paper_id"]),
        paper_profile=paper_profile,
    )
    owner.global_knowledge.reconcile_campaign(handle.path, paper_profile)
    _reconcile_template_usage(
        owner, handle, str(loop_state["paper_id"]), paper_profile["profile_key"]
    )
    _reconcile_lineage_artifacts(
        manager, handle, portfolio_state
    )
    launch_knowledge = _knowledge_snapshot(
        owner, manager, handle, portfolio_state, campaign_content_memory
    )
    watermarks = batch.setdefault("knowledge_watermarks", {})
    watermarks.setdefault("created_snapshot", deepcopy(launch_knowledge))
    watermarks["last_resumed_snapshot"] = deepcopy(launch_knowledge)
    manager.save_batch(handle, batch)
    loop_state["batch"] = dict(batch)
    loop_state["active_batch"] = dict(batch)
    validation_template_ids = None
    if batch_mode == "validate":
        policy = batch.setdefault("schedule_policy", {})
        changed = "validation_counts" not in batch
        batch.setdefault("validation_counts", {
            "attempts": 0,
            "new_tasks": 0,
            "retry_attempts": 0,
            "passed": 0,
            "final_failures": 0,
            "retry_pending": 0,
            "source_replays": 0,
        })
        if "validation_template_ids" not in policy:
            policy["validation_template_ids"] = owner.library.validation_candidate_ids(
                paper_id=str(loop_state["paper_id"]),
                paper_profile=paper_profile,
            )
            policy["validation_snapshot_created_at"] = _utc_now()
            changed = True
        if "validation_blocked_templates" not in policy:
            policy["validation_blocked_templates"] = (
                owner.library.validation_blocked_candidates(
                    paper_profile=paper_profile,
                )
            )
            changed = True
        if changed:
            manager.save_batch(handle, batch)
            loop_state["batch"] = dict(batch)
            loop_state["active_batch"] = dict(batch)
        validation_template_ids = list(
            policy.get("validation_template_ids") or []
        )
        owner._progress(
            loop_state, "validation_snapshot",
            eligible_count=len(validation_template_ids),
            blocked_templates=list(
                policy.get("validation_blocked_templates") or []
            ),
            frozen=True,
        )
    if batch_mode == "improve":
        candidates = [
            item for item in portfolio_state["lineages"].values()
            if item.get("status") != "retired"
        ]
        if target_lineage_id:
            candidates = [
                item for item in candidates
                if item.get("lineage_id") == target_lineage_id
            ]
        if not candidates:
            batch["status"] = "UNAVAILABLE"
            batch["stop_reason"] = "lineage_unavailable"
            manager.save_batch(handle, batch)
            loop_state["batch"] = dict(batch)
            loop_state["active_batch"] = dict(batch)
            return _finish(owner, state, loop_state, base_output_dir, "lineage_unavailable")
    recent_templates = list(campaign_state.get("recent_template_ids") or [])
    previous_accepted = campaign_state.get("previous_accepted")
    lineage_depth = int(campaign_state.get("lineage_depth", 0))
    rubric_version = str(owner.config.get("rubric_version", "unknown"))
    best_by_rubric = loop_state.setdefault("best_candidates_by_rubric", {})
    legacy_best = loop_state.get("best_candidate") or {}
    if legacy_best.get("rubric_version") == rubric_version:
        best_by_rubric.setdefault(rubric_version, legacy_best)
    prior_best = best_by_rubric.get(rubric_version) or {}
    best_score = float(prior_best.get("score", -1.0))
    loop_state["best_candidate"] = prior_best or None
    prior_archive_path = prior_best.get("archive_dir")
    prior_archive_dir = Path(str(prior_archive_path)) if prior_archive_path else None
    if prior_archive_dir is not None and prior_archive_dir.is_dir():
        owner.storage.promote_best(
            state,
            {
                "pptx_path": str(prior_archive_dir / "poster.pptx"),
                "png_path": str(prior_archive_dir / "poster.png"),
            },
            base_output_dir,
        )
    iteration = last_completed
    session_completed = 0
    batch_completed = int(batch.get("completed_iterations", 0))
    fatal_reason: Optional[str] = None
    preflight_excluded_families: set[str] = set()
    preflight_retry_count = 0
    improve_fallback_requested = False

    while not owner.control.stop_requested:
        owner.control.wait_while_paused(owner.status_callback)
        if owner.control.stop_requested:
            break

        validation_available = (
            batch_mode == "validate"
            and owner.library.has_validation_candidate(
                paper_id=str(loop_state["paper_id"]),
                paper_profile=paper_profile,
                template_ids=validation_template_ids,
            )
        )
        if batch_mode == "validate" and not validation_available:
            batch["status"] = "EXHAUSTED"
            batch["stop_reason"] = "validation_queue_exhausted"
            manager.save_batch(handle, batch)
            loop_state["batch"] = dict(batch)
            loop_state["active_batch"] = dict(batch)
            loop_state["stop_reason"] = "validation_queue_exhausted"
            break
        iteration += 1
        task = owner.portfolio_scheduler.select(
            portfolio_state,
            iteration=iteration,
            session_iteration=session_completed + 1,
            paper_profile=paper_profile,
            validation_available=validation_available,
            batch_mode=batch_mode,
            target_lineage_id=target_lineage_id,
            mixed_mode_weights=(batch.get("schedule_policy") or {}).get(
                "mode_weights"
            ),
            excluded_family_ids=preflight_excluded_families,
        )
        requested_mode = str(task["mode"])
        strategy = str(task["strategy"])
        # Explore never retrieves a saved poster template or its content. It may
        # sample at most two promoted paper-free geometry archetypes alongside
        # fresh seed-family variants; exact template retrieval remains reserved
        # for explicit validation.
        if task["mode"] == "explore":
            strategy = "explore"
            task["strategy"] = strategy
            task["template_free"] = True

        source_lineage_id = (
            task["lineage_id"] if task["mode"] == "improve" else None
        )
        if source_lineage_id:
            loaded = manager.load_lineage_snapshot(
                handle, str(source_lineage_id), state
            )
            if loaded:
                task["parent_candidate_id"] = loaded.get("candidate_id")
                task["parent_snapshot_kind"] = loaded.get("snapshot_kind")
                task["parent_score"] = loaded.get("score")
                removed_selection_ids = (
                    manager.sanitize_content_selection(state)
                )
                if removed_selection_ids:
                    owner._progress(
                        loop_state,
                        "content_selection_repaired",
                        iteration=iteration,
                        lineage=str(source_lineage_id),
                        removed_ids=removed_selection_ids,
                    )
            if not loaded:
                if batch_mode == "mixed":
                    task = owner.portfolio_scheduler.select(
                        portfolio_state,
                        iteration=iteration,
                        session_iteration=session_completed + 1,
                        paper_profile=paper_profile,
                        validation_available=False,
                        batch_mode="explore",
                    )
                    strategy = "explore"
                else:
                    iteration -= 1
                    batch["status"] = "UNAVAILABLE"
                    batch["stop_reason"] = "lineage_snapshot_missing"
                    manager.save_batch(handle, batch)
                    loop_state["batch"] = dict(batch)
                    loop_state["active_batch"] = dict(batch)
                    loop_state["stop_reason"] = "lineage_snapshot_missing"
                    break
        template_context, template_knowledge = (
            owner.library.retrieve_with_snapshot(
                strategy=strategy,
                campaign_id=handle.campaign_id,
                paper_id=str(loop_state["paper_id"]),
                paper_profile=paper_profile,
                iteration=iteration,
                recent_template_ids=recent_templates,
                random_seed=owner.random_seed + iteration,
                validation_template_ids=validation_template_ids,
            )
        )
        if strategy == "validate" and not template_context and batch_mode == "validate":
            iteration -= 1
            batch["status"] = "EXHAUSTED"
            batch["stop_reason"] = "validation_queue_exhausted"
            manager.save_batch(handle, batch)
            loop_state["batch"] = dict(batch)
            loop_state["active_batch"] = dict(batch)
            loop_state["stop_reason"] = "validation_queue_exhausted"
            break
        if strategy in {"adapt", "validate"} and not template_context:
            task = owner.portfolio_scheduler.select(
                portfolio_state,
                iteration=iteration,
                session_iteration=session_completed + 1,
                paper_profile=paper_profile,
                validation_available=False,
                batch_mode="explore",
            )
            strategy = "explore"

        if template_context:
            template_family = template_context[0].get("family")
            if template_family in owner.portfolio_scheduler.registry.ids():
                task["family_id"] = template_family
        selected_template_ids = [
            item["template_id"]
            for item in template_context
            if item.get("template_id")
        ]
        validation_task = (
            template_context[0]
            if task["mode"] == "validate" and template_context else {}
        )
        if task["mode"] != "validate":
            recent_templates.extend(selected_template_ids)
            recent_templates = recent_templates[
                -int(owner.config["loop"].get("recent_template_window", 10)):
            ]
        validation_identity = {}
        if task["mode"] == "validate":
            if len(selected_template_ids) != 1:
                raise ValueError(
                    "strict validation requires exactly one saved template"
                )
            validation_identity = owner.library.validation_identity(
                selected_template_ids[0]
            )
            if not validation_identity:
                raise ValueError("strict validation template identity is missing")

        candidate_id = (
            f"{handle.campaign_id}_i{iteration:06d}_{uuid.uuid4().hex[:8]}"
        )
        candidate_dir = base_output_dir / "iterations" / f"{iteration:06d}"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        state["output_dir"] = str(candidate_dir)
        state["iteration_context"] = {
            "campaign_id": handle.campaign_id,
            "batch_id": batch["batch_id"],
            "session_id": session_id,
            "iteration": iteration,
            "session_iteration": session_completed + 1,
            "candidate_id": candidate_id,
            "strategy": strategy,
            "portfolio_mode": task["mode"],
            "requested_mode": requested_mode,
            "batch_mode": batch_mode,
            "lineage_id": task["lineage_id"],
            "parent_lineage_id": task.get("parent_lineage_id"),
            "parent_candidate_id": task.get("parent_candidate_id"),
            "parent_snapshot_kind": task.get("parent_snapshot_kind"),
            "layout_family": task["family_id"],
            "lineage_depth": lineage_depth,
            "random_seed": owner.random_seed + iteration,
            "validation_target": validation_task.get("validation_target"),
            "validation_attempt": validation_task.get("validation_attempt"),
            "validation_max_attempts": validation_task.get(
                "validation_max_attempts"
            ),
            "validation_template_fingerprint": validation_identity.get(
                "fingerprint"
            ),
            "validation_topology_sha256": validation_identity.get(
                "topology_sha256"
            ),
            "anti_fixation": {
                "template_free": bool(task.get("template_free")),
                "copy_coordinates_forbidden": True,
                "recent_template_ids": list(recent_templates),
                "family_counts": dict(
                    portfolio_state.get("family_counts", {})
                ),
                "family_exploration_debt": dict(
                    portfolio_state.get("family_exploration_debt", {})
                ),
            },
        }
        state["template_context"] = template_context
        state["validation_template_id"] = (
            selected_template_ids[0] if task["mode"] == "validate" and selected_template_ids else None
        )
        state["template_validation_topology"] = (
            owner.library.validation_topology(state["validation_template_id"])
            if state["validation_template_id"] else {}
        )
        (
            state["global_design_context"],
            global_design_knowledge,
        ) = owner.global_knowledge.retrieve_with_snapshot(
            rubric_version=rubric_version,
            paper_profile=paper_profile,
            family_id=str(task["family_id"]),
            mode=str(task["mode"]),
        )
        knowledge_inputs = {
            "campaign_iteration": iteration - 1,
            "campaign_content": manager.content_memory_snapshot(
                campaign_content_memory
            ),
            "portfolio": _portfolio_snapshot(portfolio_state),
            "template_library": template_knowledge,
            "global_design_memory": global_design_knowledge,
            "captured_at": _utc_now(),
        }
        state["iteration_context"]["knowledge_inputs"] = deepcopy(
            knowledge_inputs
        )
        previous_report = (
            deepcopy(state.get("critic_report") or {})
            if task["mode"] == "improve" else None
        )
        state["current_candidate"] = {
            "candidate_id": candidate_id,
            "candidate_dir": str(candidate_dir),
            "pptx_path": str(candidate_dir / f"{state['poster_name']}.pptx"),
            "png_path": str(candidate_dir / f"{state['poster_name']}.png"),
            "status": "planned",
            "knowledge_inputs": deepcopy(knowledge_inputs),
            "selected_template_ids": list(selected_template_ids),
        }
        attempt = manager.begin_iteration(
            handle,
            iteration=iteration,
            session_id=session_id,
            candidate=state["current_candidate"],
            batch_id=batch["batch_id"],
        )
        state["iteration_context"].update({
            "attempt_id": attempt.attempt_id,
            "attempt_number": attempt.attempt_number,
        })
        state["errors"] = []
        if task["mode"] != "improve":
            for field in owner.DESIGN_FIELDS:
                if field != "current_candidate":
                    state[field] = None
        state["runtime_layout_variants"] = (
            owner.layout_archetypes.retrieve(
                family_id=str(task["family_id"]),
                paper_id=str(loop_state["paper_id"]),
                limit=2,
            )
            if task["mode"] == "explore"
            else []
        )
        state["improve_safe_fallback"] = bool(
            task["mode"] == "improve" and improve_fallback_requested
        )
        if state["improve_safe_fallback"]:
            state["revision_parent_layout_spec"] = deepcopy(
                state.get("layout_spec") or {}
            )
            state["revision_parent_story_board"] = deepcopy(
                state.get("story_board") or {}
            )
            state["layout_revision_constraints"] = {}
            state["revision_plan"] = {
                "schema_version": 3,
                "parent_candidate_id": task.get("parent_candidate_id"),
                "analysis_summary": (
                    "Planner repair rolled back after repeated preflight failure"
                ),
                "operations": [],
                "content_actions": [],
                "fallback_used": True,
                "safe_parent_fallback": True,
            }
            state["content_revision"] = {
                "schema_version": 1,
                "skipped": True,
                "reason": "safe_parent_fallback",
            }

        loop_state.update({
            "status": "RUNNING",
            "iteration": iteration,
            "attempt_id": attempt.attempt_id,
            "attempt_number": attempt.attempt_number,
            "strategy": strategy,
            "updated_at": _utc_now(),
        })
        owner._checkpoint(loop_state)
        owner._progress(
            loop_state, "iteration", iteration=iteration,
            batch_ordinal=batch_completed + 1,
            batch_target=int(batch["target_iterations"]),
            attempt_number=attempt.attempt_number,
            mode=str(task["mode"]), strategy=strategy,
            family=str(task["family_id"]), lineage=str(task["lineage_id"]),
            template_ids=selected_template_ids,
            candidate_id=candidate_id,
            validation_target=validation_task.get("validation_target"),
            validation_attempt=validation_task.get("validation_attempt"),
            validation_max_attempts=validation_task.get(
                "validation_max_attempts"
            ),
        )
        owner._notify(loop_state, f"Iteration {iteration}: {strategy}")

        active_stage = "design"
        try:
            nodes = (
                owner.revision_design_nodes[2:]
                if task["mode"] == "improve" and improve_fallback_requested
                else owner.revision_design_nodes
                if task["mode"] == "improve"
                else owner.fresh_design_nodes
            )
            state = owner._run_nodes(
                state,
                nodes,
                stage=f"iteration_{iteration}",
            )
            if owner.control.force_stop_requested:
                manager.abandon_attempt(attempt, "user_force_stop")
                owner._cleanup_iteration_artifacts(state)
                owner.storage.discard_pending(candidate_id)
                loop_state["stop_reason"] = "user_force_stop"
                break

            validation_preflight_failure = False
            if state.get("layout_preflight_failed"):
                feasibility_report = state.get("layout_feasibility_report") or {}
                preflight_report = state.get("layout_preflight_report") or {}
                _atomic_json(
                    attempt.path / "layout_feasibility_report.json",
                    feasibility_report,
                )
                _atomic_json(
                    attempt.path / "layout_preflight_report.json",
                    preflight_report,
                )
                family_id = str(task.get("family_id") or "unknown")
                preflight_retry_count += 1
                reason = str((state.get("errors") or ["infeasible"])[-1])

                if task["mode"] == "validate":
                    validation_preflight_failure = True
                    report = {
                        "schema_version": 3,
                        "report_kind": "validation_preflight_failure",
                        "candidate_id": candidate_id,
                        "iteration": iteration,
                        "decision": "validation_failed_before_render",
                        "overall_score": None,
                        "archive_eligible": False,
                        "template_eligible": False,
                        "poster_evaluation": {
                            "evaluated": False,
                            "reason": "layout_preflight_failed",
                        },
                        "task_evaluation": {
                            "task": "strict_template_transfer",
                            "evaluated": True,
                            "passed": False,
                            "status": "strict_transfer_failed",
                            "reasons": ["layout_preflight_failed"],
                        },
                        "issues": [{
                            "issue_id": "VALIDATION-PREFLIGHT",
                            "category": "layout_preflight",
                            "observation": reason,
                            "required_outcome": (
                                "The frozen template topology must compile "
                                "without bounds, ownership, or overflow errors."
                            ),
                        }],
                        "rejection_summary": (
                            "Strict validation failed before rendering because "
                            "the frozen topology did not pass layout preflight."
                        ),
                        "layout_feasibility_report": deepcopy(feasibility_report),
                        "layout_preflight_report": deepcopy(preflight_report),
                    }
                    state["critic_report"] = report
                    accepted = False
                    owner._progress(
                        loop_state,
                        "validation_preflight_failed",
                        iteration=iteration,
                        family=family_id,
                        attempt=validation_task.get("validation_attempt"),
                        max_attempts=validation_task.get(
                            "validation_max_attempts"
                        ),
                        budget_consumed=True,
                        reason=reason,
                    )
                else:
                    manager.abandon_attempt(
                        attempt, "layout_preflight_infeasible"
                    )
                    owner._cleanup_iteration_artifacts(state)
                    owner.storage.discard_pending(candidate_id)
                    if task["mode"] == "explore":
                        preflight_excluded_families.add(family_id)
                        maximum_retries = max(
                            1,
                            int(
                                owner.config.get("explore_layout", {}).get(
                                    "max_family_attempts_per_iteration",
                                    len(
                                        owner.portfolio_scheduler.registry.compatible_ids(
                                            paper_profile
                                        )
                                    ),
                                )
                            ),
                        )
                        compatible = set(
                            owner.portfolio_scheduler.registry.compatible_ids(
                                paper_profile
                            )
                        )
                        exhausted = (
                            not compatible
                            or compatible.issubset(preflight_excluded_families)
                        )
                    elif task["mode"] == "improve":
                        maximum_retries = max(
                            1,
                            int(
                                owner.config.get("improve_layout", {}).get(
                                    "max_preflight_recovery_attempts", 3
                                )
                            ),
                        )
                        exhausted = False
                        if preflight_retry_count == maximum_retries - 1:
                            improve_fallback_requested = True
                    else:
                        maximum_retries = 1
                        exhausted = True
                    owner._progress(
                        loop_state,
                        "layout_fit_retry",
                        iteration=iteration,
                        family=family_id,
                        mode=str(task["mode"]),
                        retry=preflight_retry_count,
                        excluded=sorted(preflight_excluded_families),
                        safe_parent_fallback=improve_fallback_requested,
                        budget_consumed=False,
                        reason=reason,
                    )
                    if preflight_retry_count >= maximum_retries or exhausted:
                        fatal_reason = (
                            "improve_parent_layout_unrecoverable"
                            if task["mode"] == "improve"
                            else "layout_family_search_exhausted"
                        )
                        batch["status"] = "FAILED_REQUIRES_USER"
                        batch["stop_reason"] = fatal_reason
                        manager.save_batch(handle, batch)
                        loop_state["batch"] = dict(batch)
                        loop_state["active_batch"] = dict(batch)
                        loop_state["stop_reason"] = fatal_reason
                        break
                    iteration -= 1
                    continue

            if not validation_preflight_failure:
                preflight_excluded_families.clear()
                preflight_retry_count = 0
                improve_fallback_requested = False
                guard_violation = False
                for field, value in frozen.items():
                    if state.get(field) != value:
                        guard_violation = True
                        state[field] = deepcopy(value)
                state["scientific_guard_violation"] = guard_violation

                active_stage = "critic"
                owner._progress(
                    loop_state, "stage_start", iteration=iteration,
                    stage="critic", stage_index=len(nodes) + 1,
                    stage_total=len(nodes) + 2,
                )
                critic_started = time.perf_counter()
                state = owner.critic(state)
                owner._record_timing(
                    state,
                    "critic",
                    time.perf_counter() - critic_started,
                    iteration,
                )
                report = state["critic_report"]
                owner._progress(
                    loop_state, "stage_done", iteration=iteration,
                    stage="critic", elapsed=time.perf_counter() - critic_started,
                )
                accepted = bool(report.get("archive_eligible"))
                owner._progress(
                    loop_state, "critic", iteration=iteration,
                    decision=report.get("decision"),
                    score=report.get("overall_score"),
                    accepted=accepted,
                    template_eligible=bool(
                        report.get("template_eligible", accepted)
                    ),
                    issues=[
                        str(item.get("issue_id"))
                        for item in report.get("issues", [])
                        if isinstance(item, dict) and item.get("issue_id")
                    ][:3],
                )
                if owner.control.force_stop_requested:
                    manager.abandon_attempt(
                        attempt, "user_force_stop_after_critic"
                    )
                    owner._cleanup_iteration_artifacts(state)
                    owner.storage.discard_pending(candidate_id)
                    loop_state["stop_reason"] = (
                        "user_force_stop_after_critic"
                    )
                    owner._progress(
                        loop_state,
                        "attempt_abandoned",
                        iteration=iteration,
                        attempt=attempt.attempt_number,
                        stage="critic",
                        reason="user_force_stop_after_critic",
                        budget_consumed=False,
                    )
                    owner._notify(
                        loop_state,
                        "Force stop acknowledged after Critic. "
                        "Attempt abandoned; Batch budget was not consumed.",
                    )
                    break
            else:
                state["scientific_guard_violation"] = False
            # Fail scientific-content identity conflicts before staging bundles
            # or mutating Portfolio/Batch counters. commit_iteration repeats the
            # check as a persistence-layer invariant.
            manager.validate_content_memory_state(handle, state)
            active_stage = "commit"
            commit_started = time.perf_counter()
            owner._progress(loop_state, "stage_start", iteration=iteration,
                            stage="commit", stage_index=len(nodes) + 2,
                            stage_total=len(nodes) + 2)
            is_validation = task["mode"] == "validate"
            poster_evaluated = bool(
                (report.get("poster_evaluation") or {}).get("evaluated", True)
            )
            validation_passed = bool(
                is_validation
                and accepted
                and (report.get("task_evaluation") or {}).get("passed")
            )
            no_change_safe_fallback = bool(
                task["mode"] == "improve"
                and state.get("improve_safe_fallback")
            )
            committed_accepted = bool(accepted and not no_change_safe_fallback)
            if no_change_safe_fallback:
                report["loop_disposition"] = "no_change_safe_fallback"
                report["archive_eligible"] = False
                report["template_eligible"] = False
                owner._progress(
                    loop_state,
                    "no_change_safe_fallback",
                    iteration=iteration,
                    lineage=str(task["lineage_id"]),
                    parent_candidate=task.get("parent_candidate_id"),
                    budget_consumed=True,
                    archive_created=False,
                    template_created=False,
                )
            if not is_validation and not no_change_safe_fallback:
                previous_accepted = committed_accepted
                lineage_depth = (
                    0 if committed_accepted else lineage_depth + 1
                )
            owner.storage.save_iteration_report(session_id, iteration, report)

            template_registration = None
            archive = None
            template = None
            validation_evidence = None
            rejected_artifact = None
            if is_validation:
                template_registration = {
                    "registered": False,
                    "reason": "validation_updates_existing_template",
                    "template_id": selected_template_ids[0],
                    "new_template_created": False,
                }
                validation_evidence = {
                    "artifact_kind": "validation_evidence",
                    "saved": False,
                    "candidate_id": candidate_id,
                    "validated_template_id": selected_template_ids[0],
                    "critic_report_path": str(attempt.path / "critic_report.json"),
                }
                if validation_passed:
                    validation_evidence = owner.storage.prepare_validation_evidence(
                        session_id,
                        state,
                        report,
                        template_id=selected_template_ids[0],
                        template_fingerprint=validation_identity.get("fingerprint"),
                        paper_id=str(loop_state["paper_id"]),
                    )
                    archive = validation_evidence
                    owner._cleanup_iteration_artifacts(state)
                elif poster_evaluated:
                    rejection_kind = (
                        "strict_validation_failed"
                        if accepted
                        else "poster_rejected"
                    )
                    rejected_artifact = (
                        owner.storage.prepare_rejected_poster(
                            session_id,
                            state,
                            report,
                            rejection_kind=rejection_kind,
                        )
                    )
                    owner.storage.discard_candidate_artifacts(state)
                else:
                    owner.storage.discard_candidate_artifacts(state)
                if poster_evaluated:
                    loop_state["accepted_count"] += int(accepted)
                    loop_state["rejected_count"] += int(not accepted)
            elif committed_accepted:
                template = owner.distiller.distill(state, report, paper_profile)
                archive = owner.storage.prepare_accepted_bundle(
                    session_id, state, report, template
                )
                template_registration = {
                    "registered": True,
                    "reason": "pending_commit",
                    "template": template,
                }
                loop_state["accepted_count"] += 1
                loop_state["template_count"] += 1
                score = float(report.get("overall_score", 0.0))
                if score > best_score:
                    best_score = score
                    best_record = {
                        "candidate_id": report.get("candidate_id"),
                        "score": score,
                        "archive_dir": archive.get("archive_dir"),
                        "rubric_version": report.get("rubric_version"),
                        "critic_system_version": report.get("critic_system_version"),
                    }
                    loop_state["best_candidate"] = best_record
                    best_by_rubric[rubric_version] = best_record
                owner._cleanup_iteration_artifacts(state)
            elif no_change_safe_fallback:
                template_registration = {
                    "registered": False,
                    "reason": "no_change_safe_fallback",
                    "new_template_created": False,
                }
                owner.storage.discard_candidate_artifacts(state)
            else:
                loop_state["rejected_count"] += 1
                rejected_artifact = owner.storage.record_rejection(
                    session_id, state, report
                )

            if not is_validation and not no_change_safe_fallback:
                _record_content_outcomes(state, report, committed_accepted)
            produced_template_id = (
                template.get("template_id") if isinstance(template, dict)
                else None
            )
            portfolio_state = owner.portfolio_scheduler.commit(
                portfolio_state,
                task,
                report,
                accepted=committed_accepted,
                selected_template_ids=selected_template_ids,
                produced_template_id=produced_template_id,
                revision_context={
                    "parent_score": task.get("parent_score"),
                    "revision_plan": state.get("revision_plan") or {},
                    "revision_execution_report": (
                        state.get("revision_execution_report") or {}
                    ),
                    "content_revision": state.get("content_revision") or {},
                },
                no_change=no_change_safe_fallback,
                batch_mode=batch_mode,
            )
            lineage = (
                portfolio_state["lineages"][task["lineage_id"]]
                if not is_validation else None
            )
            if (
                lineage is not None
                and template_registration
                and template_registration.get("registered")
            ):
                lineage["status"] = "template_candidate"
                lineage["distilled_template_id"] = (
                    template_registration.get("template") or {}
                ).get("template_id")

            session_completed += 1
            batch_completed += 1
            batch["completed_iterations"] = batch_completed
            if poster_evaluated and not no_change_safe_fallback:
                batch["accepted_count"] = int(
                    batch.get("accepted_count", 0)
                ) + int(accepted)
                batch["rejected_count"] = int(
                    batch.get("rejected_count", 0)
                ) + int(not accepted)
            if is_validation and not poster_evaluated:
                batch["validation_preflight_failures"] = int(
                    batch.get("validation_preflight_failures", 0)
                ) + 1
            family_counter = (
                "validation_family_counts" if is_validation else "family_counts"
            )
            batch.setdefault(family_counter, {})[task["family_id"]] = int(
                batch.setdefault(family_counter, {}).get(task["family_id"], 0)
            ) + 1
            if validation_evidence and validation_evidence.get("saved"):
                batch["validation_evidence_count"] = int(
                    batch.get("validation_evidence_count", 0)
                ) + 1
                loop_state["validation_evidence_count"] += 1
            batch.setdefault("requested_mode_counts", {})[requested_mode] = int(
                batch.setdefault("requested_mode_counts", {}).get(requested_mode, 0)
            ) + 1
            batch.setdefault("executed_mode_counts", {})[task["mode"]] = int(
                batch.setdefault("executed_mode_counts", {}).get(task["mode"], 0)
            ) + 1
            if requested_mode != task["mode"]:
                batch.setdefault("fallback_counts", {})[requested_mode] = int(
                    batch.setdefault("fallback_counts", {}).get(requested_mode, 0)
                ) + 1
            batch.setdefault("mode_counts", {})[task["mode"]] = int(
                batch.setdefault("mode_counts", {}).get(task["mode"], 0)
            ) + 1
            batch["end_iteration"] = iteration
            batch["updated_at"] = _utc_now()
            batch.setdefault("knowledge_watermarks", {})[
                "last_iteration_snapshot"
            ] = deepcopy(knowledge_inputs)
            if not is_validation:
                owner.selector.counts[strategy] = int(
                    owner.selector.counts.get(strategy, 0)
                ) + 1
            loop_state.update({
                "last_completed_iteration": iteration,
                "session_completed_iterations": session_completed,
                "last_candidate_id": report.get("candidate_id"),
                "last_decision": (
                    report.get("loop_disposition")
                    or report.get("decision")
                ),
                "last_score": report.get("overall_score"),
                "last_rejection_summary": report.get("rejection_summary"),
                "last_template_registration": (
                    template_registration.get("reason")
                    if template_registration
                    else None
                ),
                "strategy_counts": dict(owner.selector.counts),
                "portfolio_state": portfolio_state,
                "batch": dict(batch),
                "active_batch": dict(batch),
                "layout_family": task["family_id"],
                "lineage_id": task["lineage_id"],
                "portfolio_mode": task["mode"],
                "requested_mode": requested_mode,
                "batch_mode": batch_mode,
                "recent_template_ids": list(recent_templates),
                "previous_accepted": previous_accepted,
                "lineage_depth": lineage_depth,
                "updated_at": _utc_now(),
            })
            manager.commit_iteration(
                handle,
                attempt,
                state=state,
                report=report,
                outcome={
                    "accepted": committed_accepted,
                    "critic_accepted": accepted,
                    "no_change_safe_fallback": no_change_safe_fallback,
                    "archive": archive,
                    "template_registration": template_registration,
                    "selected_template_ids": selected_template_ids,
                    "portfolio_task": task,
                    "requested_mode": requested_mode,
                    "knowledge_inputs": knowledge_inputs,
                    "validation_evidence": validation_evidence,
                    "rejected_artifact": rejected_artifact,
                    "validation_identity": validation_identity,
                    "poster_evaluated": poster_evaluated,
                    "validation_failure_reason": (
                        "layout_preflight_failed"
                        if is_validation and not poster_evaluated else None
                    ),
                    "validation_task": {
                        "target": validation_task.get("validation_target"),
                        "attempt": validation_task.get("validation_attempt"),
                        "max_attempts": validation_task.get("validation_max_attempts"),
                    } if task["mode"] == "validate" else None,
                },
                loop_state=loop_state,
            )
            batch.clear()
            batch.update(loop_state["batch"])
            batch_completed = int(batch["completed_iterations"])
            campaign_content_memory = (
                manager.reconcile_content_memory(handle)
            )
            usage_failed = False
            try:
                if rejected_artifact and rejected_artifact.get("saved"):
                    _publish_rejected_artifact(
                        owner,
                        handle,
                        iteration,
                        rejected_artifact,
                    )
                if is_validation:
                    if validation_evidence and validation_evidence.get("saved"):
                        owner.storage.publish_validation_evidence(
                            validation_evidence
                        )
                elif archive is not None:
                    owner.storage.publish_accepted_bundle(archive)
                    template_registration = owner.library.register(template)
                    if (
                        loop_state.get("best_candidate", {}).get("candidate_id")
                        == report.get("candidate_id")
                    ):
                        owner.storage.promote_best(
                            state, archive, base_output_dir
                        )
                owner.library.record_usage(
                    template_ids=selected_template_ids,
                    campaign_id=handle.campaign_id,
                    paper_id=str(loop_state["paper_id"]),
                    profile_key=paper_profile["profile_key"],
                    iteration=iteration,
                    accepted=committed_accepted,
                    score=(
                        float(report["overall_score"])
                        if isinstance(report.get("overall_score"), (int, float))
                        else None
                    ),
                    event_id=f"{handle.campaign_id}:{iteration}",
                    batch_id=batch["batch_id"],
                    validation_run=is_validation,
                    transfer_verified=bool(
                        (report.get("task_evaluation") or {}).get("passed")
                    ),
                    transfer_reasons=(
                        (report.get("task_evaluation") or {}).get("reasons")
                        or []
                    ),
                    candidate_id=candidate_id,
                    validation_evidence=validation_evidence,
                    expected_template_fingerprint=validation_identity.get(
                        "fingerprint"
                    ),
                    expected_topology_sha256=validation_identity.get(
                        "topology_sha256"
                    ),
                    poster_evaluated=poster_evaluated,
                    validation_failure_reason=(
                        "layout_preflight_failed"
                        if is_validation and not poster_evaluated else None
                    ),
                )
                if is_validation and selected_template_ids:
                    event_id = f"{handle.campaign_id}:{iteration}"
                    summaries = owner.library.validation_summaries(
                        selected_template_ids,
                        paper_id=str(loop_state["paper_id"]),
                    )
                    summary = summaries.get(selected_template_ids[0], {})
                    if _apply_validation_batch_event(
                        batch,
                        event_id=event_id,
                        target=str(
                            validation_task.get("validation_target") or "unknown"
                        ),
                        attempt=int(
                            validation_task.get("validation_attempt") or 1
                        ),
                        passed=validation_passed,
                        trial_status=summary.get("trial_status"),
                    ):
                        manager.save_batch(handle, batch)
                        loop_state["batch"] = dict(batch)
                        loop_state["active_batch"] = dict(batch)
                _atomic_json(
                    handle.path / "iterations" / f"{iteration:06d}"
                    / "TEMPLATE_USAGE_APPLIED.json",
                    {
                        "event_id": f"{handle.campaign_id}:{iteration}",
                        "batch_id": batch["batch_id"],
                    },
                )
            except (OSError, TypeError, ValueError) as exc:
                usage_failed = True
                log_agent_error(
                    "post_commit_publication",
                    f"deferred committed publication: {exc}",
                )
            if not is_validation and not no_change_safe_fallback:
                try:
                    owner.global_knowledge.record(
                        campaign_id=handle.campaign_id,
                        iteration=iteration,
                        paper_profile=paper_profile,
                        batch_id=batch["batch_id"],
                        report=report,
                        requested_mode=requested_mode,
                        executed_mode=str(task["mode"]),
                        previous_report=previous_report,
                        operations=[
                            item.get("type") or item.get("operation")
                            for item in (
                                state.get("revision_plan") or {}
                            ).get("operations", [])
                            if isinstance(item, dict)
                        ],
                    )
                except (OSError, TypeError, ValueError) as exc:
                    # COMPLETED.json already committed; startup retries it.
                    log_agent_error(
                        "global_knowledge",
                        f"deferred committed event: {exc}",
                    )
                if committed_accepted:
                    try:
                        registered_template = (
                            template_registration.get("template") or {}
                        )
                        archetype = owner.layout_archetypes.record_accepted(
                            event_id=f"{handle.campaign_id}:{iteration}",
                            paper_id=str(loop_state["paper_id"]),
                            paper_profile=paper_profile,
                            candidate_id=str(candidate_id),
                            layout_spec=state.get("layout_spec") or {},
                            design_score=registered_template.get(
                                "template_design_score"
                            ),
                            template_id=registered_template.get(
                                "template_id"
                            ),
                        )
                        owner._progress(
                            loop_state,
                            "layout_archetype",
                            iteration=iteration,
                            archetype_id=archetype.get("archetype_id"),
                            family=archetype.get("family_id"),
                            status=archetype.get("status"),
                            accepted_posters=archetype.get(
                                "accepted_poster_count", 0
                            ),
                            distinct_papers=archetype.get(
                                "distinct_paper_count", 0
                            ),
                        )
                    except (OSError, TypeError, ValueError, KeyError) as exc:
                        log_agent_error(
                            "layout_archetypes",
                            f"deferred committed archetype event: {exc}",
                        )
                manager.save_lineage_snapshot(
                    handle,
                    task["lineage_id"],
                    state,
                    lineage,
                    accepted=committed_accepted,
                )
            manager.save_batch(handle, batch)
            owner._progress(loop_state, "stage_done", iteration=iteration,
                            stage="commit", elapsed=time.perf_counter() - commit_started)
            if usage_failed:
                owner._progress(loop_state, "error", iteration=iteration,
                                stage="post_commit_publication",
                                error_type="DeferredPublication",
                                message=(
                                    "Committed iteration requires startup replay; "
                                    "artifact or usage publication is not "
                                    "confirmed"
                                ))
                fatal_reason = "post_commit_publication_deferred"
                break
            registered_template = (template_registration or {}).get("template") or {}
            validation_details = None
            if task["mode"] == "validate":
                if usage_failed:
                    validation_details = "usage deferred after commit"
                else:
                    summaries = owner.library.validation_summaries(
                        selected_template_ids,
                        paper_id=str(loop_state["paper_id"]),
                    )
                    passed = bool(
                        accepted and (report.get("task_evaluation") or {}).get("passed")
                    )
                    detail_parts = []
                    for template_id in selected_template_ids:
                        summary = summaries.get(template_id, {})
                        if validation_task.get("validation_target") == "cross_paper":
                            trial_status = summary.get("trial_status")
                            conclusion = (
                                "passed" if passed
                                else "final failure" if trial_status == "failed_final"
                                else "failed; retry pending"
                            )
                            detail_parts.append(
                                "{} cross-paper attempt {}/{} {} L{} ({})".format(
                                    template_id,
                                    summary.get("attempts_completed", 0),
                                    summary.get("max_attempts", 3),
                                    conclusion,
                                    summary.get("level", 0),
                                    summary.get("status", "pending"),
                                )
                            )
                        else:
                            detail_parts.append(
                                "{} source replay {} L{} ({})".format(
                                    template_id,
                                    "passed" if passed else "failed",
                                    summary.get("level", 0),
                                    summary.get("status", "pending"),
                                )
                            )
                    validation_details = (
                        ", ".join(detail_parts) or "no template selected"
                    )
            owner._progress(
                loop_state, "committed", iteration=iteration,
                completed=batch_completed, target=int(batch["target_iterations"]),
                accepted=loop_state["accepted_count"],
                rejected=loop_state["rejected_count"],
                templates=loop_state["template_count"],
                validation_evidence_count=loop_state[
                    "validation_evidence_count"
                ],
                best_score=(loop_state.get("best_candidate") or {}).get("score", "-"),
                archive=str(archive.get("archive_dir")) if archive else None,
                template={
                    "registered": bool((template_registration or {}).get("registered")),
                    "reason": (template_registration or {}).get(
                        "reason", "poster_rejected" if not accepted else "not_eligible"
                    ),
                    "template_id": (
                        registered_template.get("template_id")
                        or (template_registration or {}).get("template_id")
                    ),
                    "new_template_created": bool(
                        (template_registration or {}).get(
                            "new_template_created",
                            (template_registration or {}).get("registered"),
                        )
                    ),
                    "design_score": registered_template.get("template_design_score"),
                    "design_rubric": (registered_template.get("template_evaluation") or {}).get("rubric_version"),
                    "level": registered_template.get("template_level"),
                    "retrieval_enabled": registered_template.get("retrieval_enabled"),
                    "retrieval_reason": registered_template.get("retrieval_reason"),
                    "preview_png": archive.get("template_png_path") if archive else None,
                    "preview_pptx": archive.get("template_pptx_path") if archive else None,
                },
                validation=validation_details,
                validation_evidence=validation_evidence,
                rejected_artifact=rejected_artifact,
                best=bool(archive and
                          (loop_state.get("best_candidate") or {}).get("candidate_id")
                          == report.get("candidate_id")),
            )
            owner._notify(
                loop_state,
                f"Iteration {iteration}: "
                f"{report.get('loop_disposition') or report.get('decision')} "
                f"({report.get('overall_score') if poster_evaluated else 'not scored'})",
            )
            if batch_completed >= int(batch["target_iterations"]):
                loop_state["stop_reason"] = "batch_complete"
                batch["status"] = "COMPLETED"
                batch["completed_at"] = _utc_now()
                loop_state["batch"] = dict(batch)
                loop_state["active_batch"] = dict(batch)
                manager.save_batch(handle, batch, complete=True)
                break
            if owner.control.force_stop_requested:
                loop_state["stop_reason"] = (
                    "user_force_stop_after_commit"
                )
                owner._notify(
                    loop_state,
                    "Force stop arrived during atomic commit. "
                    "The commit finished before pausing the Batch.",
                )
                break
        except Exception as exc:
            committed = (
                handle.path / "iterations" / f"{iteration:06d}" / "COMPLETED.json"
            ).is_file()
            if not committed:
                manager.abandon_attempt(attempt, "iteration_exception")
                owner.storage.discard_pending(candidate_id)
            message = f"iteration {iteration}: {exc}"
            state.setdefault("errors", []).append(message)
            log_agent_error("loop_controller", message)
            owner._progress_error(loop_state, active_stage, exc, iteration)
            fatal_reason = (
                "post_commit_bookkeeping_failed" if committed
                else "iteration_failed_before_commit"
            )
            break

        if (
            max_iterations_for_test is not None
            and session_completed >= max_iterations_for_test
        ):
            loop_state["stop_reason"] = "test_iteration_limit"
            break

    if fatal_reason:
        loop_state.update({
            "status": "FAILED_REQUIRES_USER",
            "updated_at": _utc_now(),
            "stopped_at": _utc_now(),
            "stop_reason": fatal_reason,
            "errors": list(state.get("errors", [])),
        })
        batch["status"] = "FAILED_REQUIRES_USER"
        batch["stop_reason"] = fatal_reason
        manager.save_batch(handle, batch)
        loop_state["batch"] = dict(batch)
        loop_state["active_batch"] = dict(batch)
        owner._checkpoint(loop_state)
        owner._progress(loop_state, "error", iteration=iteration,
                        stage=fatal_reason, error_type="LoopFailure",
                        message="See run.log and the last attempt for details")
        _emit_finished(owner, loop_state)
        state["loop_state"] = loop_state
        state["output_dir"] = str(base_output_dir)
        return state
    return _finish(
        owner,
        state,
        loop_state,
        base_output_dir,
        loop_state.get("stop_reason") or "user_requested",
    )


def _discard_uncommitted_bundles(owner: Any, handle: CampaignHandle) -> None:
    """Never retain a staged artifact without an iteration commit marker."""
    for iteration_dir in (handle.path / "iterations").glob("[0-9]*"):
        if (iteration_dir / "COMPLETED.json").is_file():
            continue
        for status_file in (iteration_dir / "attempts").glob("*/status.json"):
            status = json.loads(status_file.read_text(encoding="utf-8"))
            owner.storage.discard_pending(
                str(status.get("candidate_id") or "")
            )


def _publish_rejected_artifact(
    owner: Any,
    handle: CampaignHandle,
    iteration: int,
    diagnostic: Dict[str, Any],
) -> None:
    """Publish once; a marker makes later user deletion intentionally final."""

    iteration_dir = handle.path / "iterations" / f"{iteration:06d}"
    marker = iteration_dir / "REJECTED_ARTIFACT_PUBLISHED.json"
    if marker.is_file():
        return
    owner.storage.publish_rejected_poster(diagnostic)
    _atomic_json(marker, {
        "schema_version": 1,
        "campaign_id": handle.campaign_id,
        "iteration": iteration,
        "candidate_id": diagnostic.get("candidate_id"),
        "archive_dir": diagnostic.get("archive_dir"),
        "published_at": _utc_now(),
        "deletion_policy": (
            "diagnostic_only_user_deletion_does_not_require_replay"
        ),
    })


def _reconcile_accepted_bundles(owner: Any, handle: CampaignHandle) -> None:
    """Replay committed artifact publication and template registration."""
    for marker in sorted((handle.path / "iterations").glob("*/COMPLETED.json")):
        completion = json.loads(marker.read_text(encoding="utf-8"))
        attempt = marker.parent / "attempts" / completion["attempt_id"]
        outcome = json.loads(
            (attempt / "outcome.json").read_text(encoding="utf-8")
        )
        diagnostic = outcome.get("rejected_artifact") or {}
        if diagnostic.get("saved"):
            _publish_rejected_artifact(
                owner,
                handle,
                int(completion["iteration"]),
                diagnostic,
            )
        evidence = outcome.get("validation_evidence") or {}
        if evidence.get("saved"):
            owner.storage.publish_validation_evidence(evidence)
        if not outcome.get("accepted"):
            continue
        archive = outcome.get("archive") or {}
        registration = outcome.get("template_registration") or {}
        template = registration.get("template")
        if archive.get("template_json_path") and template:
            owner.storage.publish_accepted_bundle(archive)
            owner.library.register(template)


def _reconcile_lineage_artifacts(
    manager: CampaignManager,
    handle: CampaignHandle,
    portfolio_state: Dict[str, Any],
) -> None:
    """Rebuild derived Lineage snapshots from committed iteration records."""

    lineages = portfolio_state.get("lineages") or {}
    for marker in sorted(
        (handle.path / "iterations").glob("*/COMPLETED.json")
    ):
        try:
            completion = json.loads(marker.read_text(encoding="utf-8"))
            attempt = (
                marker.parent / "attempts" / completion["attempt_id"]
            )
            outcome = json.loads(
                (attempt / "outcome.json").read_text(encoding="utf-8")
            )
            task = outcome.get("portfolio_task") or {}
            if task.get("mode") == "validate":
                continue
            lineage_id = str(task.get("lineage_id") or "")
            lineage = lineages.get(lineage_id)
            if not lineage_id or not isinstance(lineage, dict):
                continue
            snapshot = json.loads(
                (attempt / "state_snapshot.json").read_text(
                    encoding="utf-8"
                )
            )
            report = json.loads(
                (attempt / "critic_report.json").read_text(
                    encoding="utf-8"
                )
            )
            replay_state = dict(snapshot.get("fields") or {})
            replay_state["critic_report"] = report
            manager.save_lineage_snapshot(
                handle,
                lineage_id,
                replay_state,
                lineage,
                accepted=bool(outcome.get("accepted")),
            )
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue



def _reconcile_layout_archetypes(
    owner: Any,
    handle: CampaignHandle,
    *,
    paper_id: str,
    paper_profile: Dict[str, Any],
) -> None:
    """Replay accepted committed geometry into the derived archetype index."""

    for marker in sorted(
        (handle.path / "iterations").glob("*/COMPLETED.json")
    ):
        completion = json.loads(marker.read_text(encoding="utf-8"))
        attempt = marker.parent / "attempts" / completion["attempt_id"]
        outcome = json.loads(
            (attempt / "outcome.json").read_text(encoding="utf-8")
        )
        task = outcome.get("portfolio_task") or {}
        if not outcome.get("accepted") or task.get("mode") == "validate":
            continue
        snapshot = json.loads(
            (attempt / "state_snapshot.json").read_text(encoding="utf-8")
        )
        report = json.loads(
            (attempt / "critic_report.json").read_text(encoding="utf-8")
        )
        fields = snapshot.get("fields") or {}
        layout_spec = fields.get("layout_spec") or {}
        if not layout_spec.get("zones"):
            # Synthetic/legacy test commits and very old snapshots may not
            # carry a reusable topology; they are not archetype evidence.
            continue
        registration = outcome.get("template_registration") or {}
        template = registration.get("template") or {}
        owner.layout_archetypes.record_accepted(
            event_id=(
                f"{handle.campaign_id}:"
                f"{int(completion['iteration'])}"
            ),
            paper_id=paper_id,
            paper_profile=paper_profile,
            candidate_id=str(
                completion.get("candidate_id")
                or report.get("candidate_id")
                or ""
            ),
            layout_spec=layout_spec,
            design_score=template.get("template_design_score"),
            template_id=template.get("template_id"),
        )


def _apply_validation_batch_event(
    batch: Dict[str, Any],
    *,
    event_id: str,
    target: str,
    attempt: int,
    passed: bool,
    trial_status: Optional[str],
) -> bool:
    """Apply one validation Batch counter update idempotently."""
    applied = set(batch.get("validation_event_ids") or [])
    if event_id in applied:
        return False
    counts = batch.setdefault("validation_counts", {
        "attempts": 0,
        "new_tasks": 0,
        "retry_attempts": 0,
        "passed": 0,
        "final_failures": 0,
        "retry_pending": 0,
        "source_replays": 0,
    })
    for key in (
        "attempts", "new_tasks", "retry_attempts", "passed",
        "final_failures", "retry_pending", "source_replays",
    ):
        counts.setdefault(key, 0)
    counts["attempts"] += 1
    counts["new_tasks" if attempt <= 1 else "retry_attempts"] += 1
    if target == "source_replay":
        counts["source_replays"] += 1
    elif passed:
        counts["passed"] += 1
    elif trial_status == "failed_final":
        counts["final_failures"] += 1
    else:
        counts["retry_pending"] += 1
    applied.add(event_id)
    batch["validation_event_ids"] = sorted(applied)[-10000:]
    return True

def _reconcile_template_usage(
    owner: Any,
    handle: CampaignHandle,
    paper_id: str,
    profile_key: str,
) -> None:
    """Finish committed template outcomes before another validation is selected."""
    for marker in sorted((handle.path / "iterations").glob("*/COMPLETED.json")):
        applied = marker.parent / "TEMPLATE_USAGE_APPLIED.json"
        if applied.is_file():
            continue
        completion = json.loads(marker.read_text(encoding="utf-8"))
        attempt = marker.parent / "attempts" / completion["attempt_id"]
        outcome = json.loads((attempt / "outcome.json").read_text(encoding="utf-8"))
        report = json.loads((attempt / "critic_report.json").read_text(encoding="utf-8"))
        iteration = int(completion["iteration"])
        owner.library.record_usage(
            template_ids=outcome.get("selected_template_ids") or [],
            campaign_id=handle.campaign_id,
            paper_id=paper_id,
            profile_key=profile_key,
            iteration=iteration,
            accepted=bool(outcome.get("accepted")),
            score=(
                float(report["overall_score"])
                if isinstance(report.get("overall_score"), (int, float))
                else None
            ),
            event_id=f"{handle.campaign_id}:{iteration}",
            batch_id=completion.get("batch_id"),
            validation_run=(outcome.get("portfolio_task") or {}).get("mode") == "validate",
            transfer_verified=bool((report.get("task_evaluation") or {}).get("passed")),
            transfer_reasons=((report.get("task_evaluation") or {}).get(
                "reasons"
            ) or []),
            candidate_id=(
                (outcome.get("validation_evidence") or {}).get("candidate_id")
                or report.get("candidate_id")
            ),
            validation_evidence=outcome.get("validation_evidence"),
            expected_template_fingerprint=(
                outcome.get("validation_identity") or {}
            ).get("fingerprint"),
            expected_topology_sha256=(
                outcome.get("validation_identity") or {}
            ).get("topology_sha256"),
            poster_evaluated=bool(outcome.get("poster_evaluated", True)),
            validation_failure_reason=outcome.get(
                "validation_failure_reason"
            ),
        )
        validation_run = (
            (outcome.get("portfolio_task") or {}).get("mode") == "validate"
        )
        campaign_manager = getattr(owner, "campaign_manager", None)
        selected = outcome.get("selected_template_ids") or []
        if validation_run and campaign_manager is not None and selected:
            summaries = owner.library.validation_summaries(
                selected, paper_id=paper_id
            )
            summary = summaries.get(selected[0], {})
            task_info = outcome.get("validation_task") or {}
            owning_batch = None
            owning_batch_id = completion.get("batch_id")
            if owning_batch_id:
                try:
                    owning_batch = campaign_manager.load_batch(
                        handle, str(owning_batch_id)
                    )
                except ValueError:
                    owning_batch = None
            if owning_batch is None:
                owning_batch = campaign_manager.load_campaign_state(handle).get(
                    "active_batch"
                )
            if isinstance(owning_batch, dict) and _apply_validation_batch_event(
                owning_batch,
                event_id=f"{handle.campaign_id}:{iteration}",
                target=str(task_info.get("target") or "unknown"),
                attempt=int(task_info.get("attempt") or 1),
                passed=bool(
                    outcome.get("accepted")
                    and (report.get("task_evaluation") or {}).get("passed")
                ),
                trial_status=summary.get("trial_status"),
            ):
                campaign_manager.save_batch(handle, owning_batch)
        _atomic_json(
            applied,
            {
                "event_id": f"{handle.campaign_id}:{iteration}",
                "batch_id": completion.get("batch_id"),
            },
        )


def _record_content_outcomes(
    state: Dict[str, Any],
    report: Dict[str, Any],
    accepted: bool,
) -> None:
    bank = state.get("verified_content_bank") or {}
    visible = {
        str(claim_id)
        for section in (
            state.get("story_board") or {}
        ).get("spatial_content_plan", {}).get("sections", [])
        for claim_id in section.get("claim_ids", [])
    }
    for claim in bank.get("claims", []):
        if str(claim.get("claim_id")) not in visible:
            continue
        outcomes = claim.setdefault("outcomes", [])
        outcomes.append({
            "campaign_id": (state.get("iteration_context") or {}).get(
                "campaign_id"
            ),
            "batch_id": (state.get("iteration_context") or {}).get("batch_id"),
            "iteration": report.get("iteration"),
            "accepted": accepted,
            "score": report.get("overall_score"),
        })
        del outcomes[:-50]


def _emit_finished(owner: Any, loop_state: Dict[str, Any]) -> None:
    batch = loop_state.get("batch") or {}
    owner._progress(
        loop_state, "finished", status=loop_state.get("status"),
        reason=loop_state.get("stop_reason"),
        completed=int(batch.get("completed_iterations", 0)),
        target=int(batch.get("target_iterations", 0)),
        accepted=int(loop_state.get("accepted_count", 0)),
        rejected=int(loop_state.get("rejected_count", 0)),
        templates=int(loop_state.get("template_count", 0)),
        validation_evidence_count=int(
            loop_state.get("validation_evidence_count", 0)
        ),
    )


def _finish(
    owner: Any,
    state: Dict[str, Any],
    loop_state: Dict[str, Any],
    base_output_dir: Path,
    reason: str,
) -> Dict[str, Any]:
    batch = loop_state.get("batch") or {}
    handle = getattr(owner, "_active_campaign", None)
    terminal = reason in {
        "batch_complete", "validation_queue_exhausted",
        "lineage_unavailable", "lineage_snapshot_missing",
    }
    if handle is not None and batch and not terminal:
        owner.campaign_manager.pause_batch(handle, batch, reason=reason)
        loop_state["batch"] = dict(batch)
        loop_state["active_batch"] = dict(batch)
    loop_state.update({
        "status": (
            "COMPLETED" if reason == "batch_complete"
            else "EXHAUSTED" if reason == "validation_queue_exhausted"
            else "UNAVAILABLE" if reason in {"lineage_unavailable", "lineage_snapshot_missing"}
            else "PAUSED"
        ),
        "updated_at": _utc_now(),
        "stopped_at": _utc_now(),
        "stop_reason": reason,
    })
    owner._checkpoint(loop_state)
    _emit_finished(owner, loop_state)
    notification = {
        "batch_complete": "Optimization Batch completed",
        "validation_queue_exhausted": "Optimization Batch exhausted its validation queue",
        "lineage_unavailable": "Optimization Batch unavailable: no eligible Lineage",
        "lineage_snapshot_missing": "Optimization Batch unavailable: Lineage snapshot missing",
    }.get(reason, "Optimization Batch paused")
    owner._notify(loop_state, notification)
    state["loop_state"] = loop_state
    state["output_dir"] = str(base_output_dir)
    log_agent_success(
        "loop_controller",
        f"campaign {loop_state['campaign_id']} stopped after "
        f"iteration {loop_state['last_completed_iteration']}",
    )
    return state
