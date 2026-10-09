"""Model-free audit of rendered loop text bounds before Critic admission."""

from __future__ import annotations

import json
from pathlib import Path

from src.layout.render_fit import audit_rendered_text
from src.state.poster_state import PosterState
from utils.src.logging_utils import log_agent_info, log_agent_warning


def render_fit_audit_node(state: PosterState) -> PosterState:
    if state.get("generation_route") != "optimization_family":
        return state
    report = audit_rendered_text(state)
    state["render_fit_report"] = report
    output_dir = Path(state["output_dir"]) / "content"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "render_fit_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    status = report.get("status")
    if status == "failed":
        log_agent_warning(
            "render_fit_audit",
            f"rendered text failed fit audit: {report.get('issue_count', 0)} issues",
        )
        if (state.get("iteration_context") or {}).get("portfolio_mode") != "validate":
            state["layout_preflight_failed"] = True
            state.setdefault("errors", []).append(
                "render_fit_audit: rendered text overflow or collision"
            )
    elif status in {"unavailable", "partial"}:
        log_agent_warning(
            "render_fit_audit",
            f"rendered text audit {status}; Critic remains authoritative",
        )
    else:
        log_agent_info("render_fit_audit", "rendered text fit passed")
    return state
