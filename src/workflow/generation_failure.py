"""Candidate-local generation failures, distinct from poster quality outcomes."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any


class GenerationFailure(RuntimeError):
    """Generation did not produce a current, rendered candidate for Critic."""


def capture_failure(state: dict[str, Any], exc: Exception, *, agent: str,
                    phase: str) -> dict[str, Any]:
    # Keep the innermost cause; outer agent wrappers must not replace it.
    if state.get("attempt_failure_report"):
        return state["attempt_failure_report"]
    context = state.get("iteration_context") or {}
    loop = state.get("loop_state") or {}
    report = {
        "schema_version": 1, "failure_kind": "commit_error" if phase == "commit" else "generation_error",
        "campaign_id": context.get("campaign_id") or loop.get("campaign_id"),
        "batch_id": context.get("batch_id") or (loop.get("batch") or {}).get("batch_id"),
        "iteration": context.get("iteration"), "attempt_id": context.get("attempt_id"),
        "candidate_id": context.get("candidate_id") or (state.get("current_candidate") or {}).get("candidate_id"),
        "family_id": context.get("family_id") or context.get("layout_family"),
        "agent": agent, "phase": phase,
        "exception_type": type(exc).__name__, "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "retryable": False, "budget_consumed": False,
    }
    state["attempt_failure_report"] = report
    return report


def require_rendered_candidate(state: dict[str, Any], candidate_id: str,
                               candidate_dir: Path) -> None:
    """Check readiness/identity only; Critic still owns artifact validity."""
    candidate = state.get("current_candidate") or {}
    problems = []
    if candidate.get("candidate_id") != candidate_id:
        problems.append("candidate identity mismatch")
    if candidate.get("status") != "rendered":
        problems.append("rendering did not complete")
    for kind in ("pptx", "png"):
        raw = candidate.get(f"{kind}_path")
        path = Path(raw).resolve() if raw else None
        if path is None or not path.is_relative_to(candidate_dir.resolve()):
            problems.append(f"{kind.upper()} is not owned by this attempt")
        elif not path.is_file() or path.stat().st_size == 0:
            problems.append(f"{kind.upper()} missing or empty")
    if problems:
        raise GenerationFailure("; ".join(problems))
