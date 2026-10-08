"""Fail-closed geometry validation between styling and rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.config.poster_config import load_config
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


def layout_preflight_node(state: PosterState) -> Dict[str, Any]:
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

    state["layout_preflight_report"] = report
    state["layout_preflight_failed"] = not bool(report.get("passed"))
    output_dir = Path(state["output_dir"]) / "content"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(
        output_dir / "layout_preflight_report.json", "w", encoding="utf-8"
    ) as handle:
        json.dump(report, handle, indent=2)

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
