"""Fail-closed geometry validation between styling and rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.config.poster_config import load_config
from src.agents.revision_contract import compiled_contract_audit, final_deletion_guard
from src.layout.feasibility import (
    validate_compiled_layout,
    validate_intra_section_layout,
)
from src.state.poster_state import PosterState
from utils.src.logging_utils import (
    log_agent_error,
    log_agent_info,
    log_agent_success,
)


def layout_preflight_node(state: PosterState, *, persist: bool = True) -> Dict[str, Any]:
    """Reject infeasible family layouts before an artifact is rendered."""

    log_agent_info("layout_preflight", "checking compiled poster geometry")
    layout_spec = state.get("layout_spec") or {}
    family_id = str(layout_spec.get("family_id") or "classic_three_column")
    legacy_classic = (
        family_id == "classic_three_column"
        and state.get("generation_route") != "optimization_family"
        and not state.get("template_validation_topology")
        and not state.get("layout_feasibility_report")
    )
    if legacy_classic:
        issues = []
        poster_width = float(state["poster_width"])
        poster_height = float(state["poster_height"])
        for element in state.get("styled_layout") or []:
            try:
                x, y, width, height = (
                    float(element[key])
                    for key in ("x", "y", "width", "height")
                )
            except (KeyError, TypeError, ValueError):
                issues.append({
                    "code": "PREFLIGHT_INVALID_BOX",
                    "element_id": element.get("id"),
                })
                continue
            if (
                x < -0.01
                or y < -0.01
                or x + width > poster_width + 0.01
                or y + height > poster_height + 0.01
            ):
                issues.append({
                    "code": "PREFLIGHT_POSTER_BOUNDS",
                    "element_id": (
                        element.get("id") or element.get("section_id")
                    ),
                    "box": [x, y, width, height],
                })
        issues.extend(
            validate_intra_section_layout(state.get("styled_layout") or [])
        )
        report = {
            "schema_version": 1,
            "passed": not issues,
            "status": "passed" if not issues else "failed",
            "family_id": family_id,
            "issue_count": len(issues),
            "issues": issues,
        }
    else:
        config = load_config()
        report = validate_compiled_layout(
            state.get("styled_layout") or [],
            layout_spec,
            state,
            poster_margin=float(config["layout"]["poster_margin"]),
            title_height_fraction=float(
                config["layout"]["title_height_fraction"]
            ),
        )
        report["status"] = "passed" if report["passed"] else "failed"

    if (state.get("iteration_context") or {}).get("portfolio_mode") == "improve":
        audit = compiled_contract_audit(state, state.get("styled_layout") or [])
        execution = state.get("revision_execution_report") or {}
        execution["compiled_contract_check"] = audit
        state["revision_execution_report"] = execution
        if state.get("revision_contract") and not state.get("improve_safe_fallback"):
            config = load_config()
            safety = final_deletion_guard(
                state, state.get("styled_layout") or [],
                poster_margin=float(config["layout"]["poster_margin"]),
                title_height_fraction=float(config["layout"]["title_height_fraction"]),
            )
            state["revision_safety_report"] = safety
            execution["deletion_guard"] = safety
            if not safety["passed"]:
                report["issues"].append({"code": "FINAL_DELETION_REGRESSION", "reasons": safety["reasons"]})
                audit["passed"] = False
        if not audit["passed"]:
            report["issues"].extend(audit["violations"])
            report["issue_count"] = len(report["issues"])
            report["passed"] = False
            report["status"] = "failed"
            report["blocked_by"] = "compiled_revision_contract"
    state["layout_preflight_report"] = report
    state["layout_preflight_failed"] = not bool(report.get("passed"))
    if persist:
        persist_preflight_reports(state)

    if state["layout_preflight_failed"]:
        message = (
            "layout_preflight: compiled layout is infeasible "
            f"({report.get('issue_count', 0)} issues)"
        )
        state.setdefault("errors", []).append(message)
        log_agent_error("layout_preflight", message)
    else:
        state["current_agent"] = "layout_preflight"
        log_agent_success("layout_preflight", "geometry preflight passed")
    return state


def persist_preflight_reports(state: PosterState) -> None:
    """Publish reports only for geometry actually adopted by the candidate."""
    output_dir = Path(state["output_dir"]) / "content"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(
        output_dir / "layout_preflight_report.json", "w", encoding="utf-8"
    ) as handle:
        json.dump(state["layout_preflight_report"], handle, indent=2)
    if state.get("revision_execution_report"):
        with open(output_dir / "revision_execution_report.json", "w", encoding="utf-8") as handle:
            json.dump(state["revision_execution_report"], handle, indent=2)
        with open(output_dir / "revision_safety_report.json", "w", encoding="utf-8") as handle:
            json.dump(state.get("revision_safety_report") or {}, handle, indent=2)
