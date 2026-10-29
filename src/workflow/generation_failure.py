"""Candidate-local generation failures, distinct from poster quality outcomes."""

from __future__ import annotations

import traceback
import shutil
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
    report = {
        "schema_version": 1, "failure_kind": "commit_error" if phase == "commit" else "generation_error",
        "run_id": context.get("run_id"),
        "sample_id": context.get("sample_id"),
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
    if state.get('source_editorial_version') == 'source_editorial_v1':
        from src.workflow.source_verification import assert_compiled_text
        try:
            assert_compiled_text(state)
        except ValueError as exc:
            raise GenerationFailure(str(exc)) from exc
    if state.get('editorial_version') == 'poster_editorial_v1':
        from src.workflow.editorial_contract import assert_editorial_ready
        assert_editorial_ready(state, compiled=True)
    candidate = state.get("current_candidate") or {}
    problems = []
    if state.get('draft_layout_mode'):
        problems.append('unverified physical draft cannot be published')
    if state.get('joint_preparation') and (state.get('joint_candidate') or {}).get('status') != (
            'render_ready' if state.get('editorial_version') == 'poster_editorial_v1' else 'verified_feasible'):
        problems.append('joint candidate is not scientifically and physically ready')
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


def retain_render_fit_preview(attempt_path, state):
    """Keep an internal retry preview only when owned by this attempt."""
    candidate = state.get('current_candidate') or {}
    if not candidate.get('candidate_dir') or not candidate.get('png_path'):
        return False
    png = Path(candidate['png_path']).resolve()
    if not png.is_relative_to(Path(candidate['candidate_dir']).resolve()):
        return False
    if not png.is_file() or png.suffix.lower() != '.png':
        return False
    try:
        shutil.copy2(png, Path(attempt_path) / 'render_fit_preview.png')
    except OSError:
        return False
    return True
