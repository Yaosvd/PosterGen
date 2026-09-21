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
from src.workflow.campaign import CampaignHandle, CampaignManager, IterationAttempt, _atomic_json
from utils.src.logging_utils import log_agent_error, log_agent_success


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    )

    batch_resumed = (
        prior_batch.get("batch_id") == batch["batch_id"]
        and int(prior_batch.get("completed_iterations", 0)) < int(batch["target_iterations"])
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
        best_score=(loop_state.get("best_candidate") or {}).get("score", "-"),
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
    owner.global_knowledge.reconcile_campaign(handle.path, paper_profile)
    _reconcile_template_usage(
        owner, handle, str(loop_state["paper_id"]), paper_profile["profile_key"]
    )
    if batch_mode in {"improve", "mutate"}:
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

    while not owner.control.stop_requested:
        owner.control.wait_while_paused(owner.status_callback)
        if owner.control.stop_requested:
            break

        validation_available = owner.library.has_validation_candidate(
            paper_id=str(loop_state["paper_id"]),
            paper_profile=paper_profile,
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
        )
        requested_mode = str(task["mode"])
        strategy = str(task["strategy"])
        warmup = int(
            owner.config.get("loop", {}).get(
                "session_template_free_warmup", 3
            )
        )
        if (
            batch_mode == "mixed"
            and task["mode"] == "explore"
            and session_completed + 1 > warmup
            and iteration % 4 == 0
        ):
            strategy = "adapt"
            task["strategy"] = strategy
            task["template_free"] = False

        source_lineage_id = (
            task["lineage_id"]
            if task["mode"] == "improve"
            else task.get("parent_lineage_id")
        )
        if source_lineage_id:
            loaded = manager.load_lineage_snapshot(
                handle, str(source_lineage_id), state
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
        mutation_parent_context = None
        if task["mode"] == "mutate":
            parent_spec = state.get("layout_spec") or {}
            mutation_parent_context = {
                "parent_family": parent_spec.get("family_id"),
                "reading_order": list(parent_spec.get("reading_order") or [])[:24],
                "anchor_role": next(
                    (zone.get("role") for zone in parent_spec.get("zones", [])
                     if zone.get("zone_id") == parent_spec.get("primary_anchor_zone")),
                    None,
                ),
                "instruction": "Preserve useful scientific narrative relationships while changing the layout family and spatial structure; never copy coordinates.",
            }

        template_context = owner.library.retrieve(
            strategy=strategy,
            campaign_id=handle.campaign_id,
            paper_id=str(loop_state["paper_id"]),
            paper_profile=paper_profile,
            iteration=iteration,
            recent_template_ids=recent_templates,
            random_seed=owner.random_seed + iteration,
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
        recent_templates.extend(selected_template_ids)
        recent_templates = recent_templates[
            -int(owner.config["loop"].get("recent_template_window", 10)):
        ]

        candidate_id = (
            f"{handle.campaign_id}_i{iteration:06d}_{uuid.uuid4().hex[:8]}"
        )
        candidate_dir = base_output_dir / "iterations" / f"{iteration:06d}"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        state["output_dir"] = str(candidate_dir)
        state["iteration_context"] = {
            "campaign_id": handle.campaign_id,
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
            "structural_mutation_parent": mutation_parent_context,
            "layout_family": task["family_id"],
            "lineage_depth": lineage_depth,
            "random_seed": owner.random_seed + iteration,
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
        state["global_design_context"] = owner.global_knowledge.retrieve(
            rubric_version=rubric_version,
            paper_profile=paper_profile,
            family_id=str(task["family_id"]),
            mode=str(task["mode"]),
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
        }
        attempt = manager.begin_iteration(
            handle,
            iteration=iteration,
            session_id=session_id,
            candidate=state["current_candidate"],
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
        )
        owner._notify(loop_state, f"Iteration {iteration}: {strategy}")

        active_stage = "design"
        try:
            nodes = (
                owner.revision_design_nodes
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
                loop_state["stop_reason"] = "user_force_stop"
                break

            guard_violation = False
            for field, value in frozen.items():
                if state.get(field) != value:
                    guard_violation = True
                    state[field] = deepcopy(value)
            state["scientific_guard_violation"] = guard_violation

            active_stage = "critic"
            owner._progress(loop_state, "stage_start", iteration=iteration,
                            stage="critic", stage_index=len(nodes) + 1,
                            stage_total=len(nodes) + 2)
            critic_started = time.perf_counter()
            state = owner.critic(state)
            owner._record_timing(
                state,
                "critic",
                time.perf_counter() - critic_started,
                iteration,
            )
            report = state["critic_report"]
            owner._progress(loop_state, "stage_done", iteration=iteration,
                            stage="critic", elapsed=time.perf_counter() - critic_started)
            accepted = bool(report.get("archive_eligible"))
            owner._progress(
                loop_state, "critic", iteration=iteration,
                decision=report.get("decision"), score=report.get("overall_score"),
                accepted=accepted, template_eligible=bool(report.get("template_eligible", accepted)),
                issues=[str(item.get("issue_id")) for item in report.get("issues", [])
                        if isinstance(item, dict) and item.get("issue_id")][:3],
            )
            active_stage = "commit"
            commit_started = time.perf_counter()
            owner._progress(loop_state, "stage_start", iteration=iteration,
                            stage="commit", stage_index=len(nodes) + 2,
                            stage_total=len(nodes) + 2)
            previous_accepted = accepted
            lineage_depth = 0 if accepted else lineage_depth + 1
            owner.storage.save_iteration_report(session_id, iteration, report)

            template_registration = None
            archive = None
            if accepted:
                archive = owner.storage.archive_candidate(session_id, state, report)
                loop_state["accepted_count"] += 1
                score = float(report.get("overall_score", 0.0))
                if score > best_score:
                    best_score = score
                    owner.storage.promote_best(state, archive, base_output_dir)
                    best_record = {
                        "candidate_id": report.get("candidate_id"),
                        "score": score,
                        "archive_dir": archive.get("archive_dir"),
                        "rubric_version": report.get("rubric_version"),
                        "critic_system_version": report.get("critic_system_version"),
                    }
                    loop_state["best_candidate"] = best_record
                    best_by_rubric[rubric_version] = best_record
                if report.get("template_eligible", accepted):
                    template = owner.distiller.distill(state, report, paper_profile)
                    template_registration = owner.library.register(template)
                    if template_registration.get("registered"):
                        loop_state["template_count"] += 1
                owner._cleanup_iteration_artifacts(state)
            else:
                loop_state["rejected_count"] += 1
                owner.storage.record_rejection(session_id, state, report)

            _record_content_outcomes(state, report, accepted)
            portfolio_state = owner.portfolio_scheduler.commit(
                portfolio_state,
                task,
                report,
                accepted=accepted,
                selected_template_ids=selected_template_ids,
                batch_mode=batch_mode,
            )
            lineage = portfolio_state["lineages"][task["lineage_id"]]
            if (
                template_registration
                and template_registration.get("registered")
            ):
                lineage["status"] = "template_candidate"
                lineage["distilled_template_id"] = (
                    template_registration.get("template") or {}
                ).get("template_id")

            session_completed += 1
            batch_completed += 1
            batch["completed_iterations"] = batch_completed
            batch["accepted_count"] = int(
                batch.get("accepted_count", 0)
            ) + int(accepted)
            batch["rejected_count"] = int(
                batch.get("rejected_count", 0)
            ) + int(not accepted)
            batch.setdefault("family_counts", {})[task["family_id"]] = int(
                batch.setdefault("family_counts", {}).get(
                    task["family_id"], 0
                )
            ) + 1
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
            owner.selector.counts[strategy] = int(
                owner.selector.counts.get(strategy, 0)
            ) + 1
            loop_state.update({
                "last_completed_iteration": iteration,
                "session_completed_iterations": session_completed,
                "last_candidate_id": report.get("candidate_id"),
                "last_decision": report.get("decision"),
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
                    "accepted": accepted,
                    "archive": archive,
                    "template_registration": template_registration,
                    "selected_template_ids": selected_template_ids,
                    "portfolio_task": task,
                    "requested_mode": requested_mode,
                },
                loop_state=loop_state,
            )
            usage_failed = False
            try:
                owner.library.record_usage(
                    template_ids=selected_template_ids,
                    campaign_id=handle.campaign_id,
                    paper_id=str(loop_state["paper_id"]),
                    profile_key=paper_profile["profile_key"],
                    iteration=iteration,
                    accepted=accepted,
                    score=float(report.get("overall_score", 0.0)),
                    event_id=f"{handle.campaign_id}:{iteration}",
                    validation_run=task["mode"] == "validate",
                )
                _atomic_json(
                    handle.path / "iterations" / f"{iteration:06d}"
                    / "TEMPLATE_USAGE_APPLIED.json",
                    {"event_id": f"{handle.campaign_id}:{iteration}"},
                )
            except (OSError, TypeError, ValueError) as exc:
                usage_failed = True
                log_agent_error("template_usage", f"deferred committed usage: {exc}")
            try:
                owner.global_knowledge.record(
                    campaign_id=handle.campaign_id,
                    iteration=iteration,
                    paper_profile=paper_profile,
                    report=report,
                    requested_mode=requested_mode,
                    executed_mode=str(task["mode"]),
                    previous_report=previous_report,
                    operations=[
                        item.get("type") or item.get("operation")
                        for item in (state.get("revision_plan") or {}).get("operations", [])
                        if isinstance(item, dict)
                    ],
                )
            except (OSError, TypeError, ValueError) as exc:
                # COMPLETED.json already committed; startup reconciliation retries.
                log_agent_error("global_knowledge", f"deferred committed event: {exc}")
            manager.save_lineage_snapshot(
                handle,
                task["lineage_id"],
                state,
                lineage,
                accepted=accepted,
            )
            manager.save_batch(handle, batch)
            owner._progress(loop_state, "stage_done", iteration=iteration,
                            stage="commit", elapsed=time.perf_counter() - commit_started)
            registered_template = (template_registration or {}).get("template") or {}
            validation_details = None
            if task["mode"] == "validate":
                if usage_failed:
                    validation_details = "usage deferred after commit"
                else:
                    summaries = owner.library.validation_summaries(selected_template_ids)
                    validation_details = ", ".join(
                        f"{template_id} {'passed' if accepted else 'failed'} "
                        f"L{summaries.get(template_id, {}).get('level', 0)} "
                        f"({summaries.get(template_id, {}).get('status', 'pending')})"
                        for template_id in selected_template_ids
                    ) or "no template selected"
            owner._progress(
                loop_state, "committed", iteration=iteration,
                completed=batch_completed, target=int(batch["target_iterations"]),
                accepted=loop_state["accepted_count"],
                rejected=loop_state["rejected_count"],
                templates=loop_state["template_count"],
                best_score=(loop_state.get("best_candidate") or {}).get("score", "-"),
                archive=str(archive.get("archive_dir")) if archive else None,
                template={
                    "registered": bool((template_registration or {}).get("registered")),
                    "reason": (template_registration or {}).get(
                        "reason", "poster_rejected" if not accepted else "not_eligible"
                    ),
                    "template_id": registered_template.get("template_id"),
                },
                validation=validation_details,
                best=bool(archive and
                          (loop_state.get("best_candidate") or {}).get("candidate_id")
                          == report.get("candidate_id")),
            )
            if usage_failed:
                fatal_reason = "template_usage_deferred_after_commit"
                break
            owner._notify(
                loop_state,
                f"Iteration {iteration}: {report.get('decision')} "
                f"({report.get('overall_score')})",
            )
            if batch_completed >= int(batch["target_iterations"]):
                loop_state["stop_reason"] = "batch_complete"
                batch["status"] = "COMPLETED"
                batch["completed_at"] = _utc_now()
                loop_state["batch"] = dict(batch)
                loop_state["active_batch"] = dict(batch)
                manager.save_batch(handle, batch, complete=True)
                break
        except Exception as exc:
            committed = (
                handle.path / "iterations" / f"{iteration:06d}" / "COMPLETED.json"
            ).is_file()
            if not committed:
                manager.abandon_attempt(attempt, "iteration_exception")
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
            score=float(report.get("overall_score", 0.0)),
            event_id=f"{handle.campaign_id}:{iteration}",
            validation_run=(outcome.get("portfolio_task") or {}).get("mode") == "validate",
        )
        _atomic_json(
            applied, {"event_id": f"{handle.campaign_id}:{iteration}"}
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
    )


def _finish(
    owner: Any,
    state: Dict[str, Any],
    loop_state: Dict[str, Any],
    base_output_dir: Path,
    reason: str,
) -> Dict[str, Any]:
    loop_state.update({
        "status": (
            "COMPLETED" if reason == "batch_complete"
            else "EXHAUSTED" if reason == "validation_queue_exhausted"
            else "UNAVAILABLE" if reason in {"lineage_unavailable", "lineage_snapshot_missing"}
            else "STOPPED"
        ),
        "updated_at": _utc_now(),
        "stopped_at": _utc_now(),
        "stop_reason": reason,
    })
    owner._checkpoint(loop_state)
    _emit_finished(owner, loop_state)
    owner._notify(
        loop_state,
        "Optimization Batch completed"
        if reason == "batch_complete"
        else "Optimization loop stopped",
    )
    state["loop_state"] = loop_state
    state["output_dir"] = str(base_output_dir)
    log_agent_success(
        "loop_controller",
        f"campaign {loop_state['campaign_id']} stopped after "
        f"iteration {loop_state['last_completed_iteration']}",
    )
    return state
