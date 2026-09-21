"""Execution engine for resumable continuous poster optimization campaigns."""

from __future__ import annotations

import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.templates.library import build_paper_profile
from src.workflow.campaign import CampaignHandle, CampaignManager, IterationAttempt
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
    batch = manager.open_batch(
        handle,
        target_iterations=owner.batch_iterations,
    )

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
        },
    }
    owner._checkpoint(loop_state)
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

        iteration += 1
        validation_available = owner.library.has_validation_candidate(
            paper_id=str(loop_state["paper_id"]),
            paper_profile=paper_profile,
        )
        task = owner.portfolio_scheduler.select(
            portfolio_state,
            iteration=iteration,
            session_iteration=session_completed + 1,
            paper_profile=paper_profile,
            validation_available=validation_available,
        )
        strategy = str(task["strategy"])
        warmup = int(
            owner.config.get("loop", {}).get(
                "session_template_free_warmup", 3
            )
        )
        if (
            task["mode"] == "explore"
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
            manager.load_lineage_snapshot(
                handle, str(source_lineage_id), state
            )

        template_context = owner.library.retrieve(
            strategy=strategy,
            campaign_id=handle.campaign_id,
            paper_id=str(loop_state["paper_id"]),
            paper_profile=paper_profile,
            iteration=iteration,
            recent_template_ids=recent_templates,
            random_seed=owner.random_seed + iteration,
        )
        if strategy in {"adapt", "validate"} and not template_context:
            strategy = "explore"
            task.update({
                "mode": "explore",
                "strategy": "explore",
                "template_free": True,
            })
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
            "lineage_id": task["lineage_id"],
            "parent_lineage_id": task.get("parent_lineage_id"),
            "parent_candidate_id": task.get("parent_candidate_id"),
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
        owner._notify(loop_state, f"Iteration {iteration}: {strategy}")

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

            critic_started = time.perf_counter()
            state = owner.critic(state)
            owner._record_timing(
                state,
                "critic",
                time.perf_counter() - critic_started,
                iteration,
            )
            report = state["critic_report"]
            accepted = bool(report.get("archive_eligible"))
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
            _record_content_outcomes(state, report, accepted)
            portfolio_state = owner.portfolio_scheduler.commit(
                portfolio_state,
                task,
                report,
                accepted=accepted,
                selected_template_ids=selected_template_ids,
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
                },
                loop_state=loop_state,
            )
            manager.save_lineage_snapshot(
                handle,
                task["lineage_id"],
                state,
                lineage,
                accepted=accepted,
            )
            manager.save_batch(handle, batch)
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
            manager.abandon_attempt(attempt, "iteration_exception")
            message = f"iteration {iteration}: {exc}"
            state.setdefault("errors", []).append(message)
            log_agent_error("loop_controller", message)
            fatal_reason = "iteration_failed_before_commit"
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


def _finish(
    owner: Any,
    state: Dict[str, Any],
    loop_state: Dict[str, Any],
    base_output_dir: Path,
    reason: str,
) -> Dict[str, Any]:
    loop_state.update({
        "status": "COMPLETED" if reason == "batch_complete" else "STOPPED",
        "updated_at": _utc_now(),
        "stopped_at": _utc_now(),
        "stop_reason": reason,
    })
    owner._checkpoint(loop_state)
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
