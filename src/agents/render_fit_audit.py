"""Model-free audit of rendered loop text bounds before Critic admission."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from src.layout.render_fit import audit_rendered_text
from src.state.poster_state import PosterState
from utils.src.logging_utils import log_agent_info, log_agent_warning


def _correct_title_fit(state, report):
    """One geometry-only local correction, never a strict-template edit."""
    mode = (state.get("iteration_context") or {}).get("portfolio_mode")
    if mode not in {"explore", "improve"} or state.get("improve_safe_fallback") or state.get("template_validation_topology"):
        return None
    titles = {item["element_id"]: item for item in report.get("matched_text_boxes", [])
              if item.get("element_type") == "section_title"}
    relevant = [item for item in report.get("issues", []) if item.get("element_id") in titles]
    if not relevant:
        return None
    trial = deepcopy(state)
    changes = {}
    for problem in relevant:
        title = titles[problem["element_id"]]
        _, y, _, height = title["planned_box_inches"]
        extra = max(0.0, title["rendered_box_inches"][3] - y - height + 0.05)
        if problem["code"] == "RENDER_TITLE_CONTENT_GAP":
            extra = max(extra, problem["minimum_gap_inches"] - problem["gap_inches"] + 0.05)
        if extra > 0:
            changes[title["section_id"]] = max(changes.get(title["section_id"], 0.0), extra)
    if not changes:
        return None
    source_layout = state.get("styled_layout") or state.get("design_layout") or []
    containers = {str(item["section_id"]): item for item in source_layout if item.get("type") == "section_container"}
    if any(section_id not in containers for section_id in changes):
        report["title_correction"] = {"status": "ownership_unavailable", "attempts": 0}
        return None
    for field in ("styled_layout", "design_layout"):
        for element in trial.get(field) or []:
            owner = str(element.get("section_id") or "")
            container = containers.get(owner)
            if not container:
                continue
            for section_id, extra in changes.items():
                source = containers[section_id]
                if container.get("zone_id") != source.get("zone_id"):
                    continue
                if owner == section_id:
                    if element.get("type") in {"section_title", "section_container"}:
                        element["height"] = float(element["height"]) + extra
                        if element.get("type") == "section_title":
                            element["required_text_height"] = element["height"]
                    elif element.get("type") in {"text", "visual"}:
                        element["y"] = float(element["y"]) + extra
                elif float(container["y"]) > float(source["y"]):
                    element["y"] = float(element["y"]) + extra
    from src.layout.feasibility import validate_compiled_layout
    from src.config.poster_config import load_config
    config = load_config()["layout"]
    check = validate_compiled_layout(
        trial.get("styled_layout") or trial.get("design_layout") or [], trial.get("layout_spec") or {}, trial,
        poster_margin=config["poster_margin"], title_height_fraction=config["title_height_fraction"],
    )
    if not check["passed"]:
        report["title_correction"] = {"status": "not_feasible", "attempts": 1, "issues": check["issues"]}
        return None
    # The ordinary styled preflight also enforces Improve's contract/deletion guards.
    from src.agents.layout_preflight import layout_preflight_node, persist_preflight_reports
    from src.agents.renderer import renderer_node
    trial = layout_preflight_node(trial, persist=False)
    if trial.get("layout_preflight_failed"):
        report["title_correction"] = {"status": "contract_rejected", "attempts": 1}
        return None
    log_agent_info("render_fit_audit", "correcting title spacing: one local re-render")
    trial = renderer_node(trial)
    if trial.get("errors") or trial.get("attempt_failure_report"):
        state.update(trial)
        return {"status": "unavailable", "passed": False, "reason": "title_correction_render_failed", "issues": [],
                "title_correction": {"status": "generation_failed", "attempts": 1}}
    corrected = audit_rendered_text(trial)
    # A correction cannot erase a confirmed failure merely because the second
    # PDF extraction lost that text. Only fresh matching evidence can clear it.
    matched_ids = {item["element_id"] for item in corrected.get("matched_text_boxes", [])}
    measured_gaps = {item["section_id"] for item in corrected.get("internal_title_gaps", [])
                     if item.get("status") == "measured"}
    unresolved = [item for item in report["issues"]
                  if item.get("element_id") not in matched_ids
                  or (item.get("code") == "RENDER_TITLE_CONTENT_GAP"
                      and item.get("section_id") not in measured_gaps)]
    if unresolved:
        corrected.setdefault("issues", []).append({
            "code": "RENDER_CORRECTION_UNVERIFIED", "section_ids": sorted(changes),
            "evidence_basis": "prior_confirmed_failure_without_corrected_measurement",
            "original_issue_codes": sorted({item["code"] for item in unresolved}),
        })
        corrected.update(status="failed", passed=False, conclusive=False,
                         issue_count=len(corrected["issues"]))
    corrected["title_correction"] = {"status": corrected["status"], "attempts": 1,
                                      "section_ids": sorted(changes), "original_issues": report["issues"]}
    from src.layout.families import analyze_regions
    analysis = analyze_regions(
        trial.get("styled_layout") or [], trial["layout_spec"], trial,
        poster_margin=config["poster_margin"], title_height_fraction=config["title_height_fraction"],
    )
    trial["final_column_analysis"] = analysis
    trial["layout_family_analysis"] = analysis
    fit = trial.get("layout_feasibility_report") or {}
    if fit:
        from src.layout.whitespace import measure_composition_whitespace
        compiled_composition = measure_composition_whitespace(
            trial["layout_spec"], trial.get("styled_layout") or [],
            poster_width=float(trial["poster_width"]), poster_height=float(trial["poster_height"]),
            poster_margin=config["poster_margin"], title_height_fraction=config["title_height_fraction"],
        )
        containers = [item for item in trial.get("styled_layout") or [] if item.get("type") == "section_container"]
        body_height = (float(trial["poster_height"]) - 2 * config["poster_margin"]) * (1 - config["title_height_fraction"])
        body_top = config["poster_margin"] + (float(trial["poster_height"]) - 2 * config["poster_margin"]) * config["title_height_fraction"]
        uses, gaps = {}, {}
        for zone in trial["layout_spec"]["zones"]:
            top = body_top + float(zone["y"]) * body_height
            available = float(zone["height"]) * body_height
            bottom = max((float(item["y"]) + float(item["height"]) for item in containers if item.get("zone_id") == zone["zone_id"]), default=top)
            uses[str(zone["zone_id"])] = round((bottom - top) / max(0.1, available), 6)
            gaps[str(zone["zone_id"])] = round(max(0.0, top + available - bottom), 4)
        fit.update({"zone_utilization": uses, "exact_bottom_gaps": gaps,
                    "worst_zone_utilization": min(uses.values(), default=0),
                    "largest_bottom_gap_inches": max(gaps.values(), default=0),
                    "composition_whitespace": compiled_composition,
                    "rendered_composition_whitespace": corrected.get("composition_whitespace") or {},
                    "post_render_title_correction": corrected["title_correction"],
                    "exact_score_scope": "pre_render_selection"})
        trial["layout_feasibility_report"] = fit
    # Rendered files now belong to the corrected geometry, even if its audit
    # fails; retain matching state for existing retry/diagnostic semantics.
    state.update(trial)
    persist_preflight_reports(state)
    for field, filename in (("styled_layout", "styled_layout.json"), ("design_layout", "final_design_layout.json")):
        (Path(state["output_dir"]) / "content" / filename).write_text(json.dumps(state.get(field) or [], indent=2), encoding="utf-8")
    for field in ("final_column_analysis", "layout_feasibility_report"):
        if state.get(field):
            (Path(state["output_dir"]) / "content" / f"{field}.json").write_text(json.dumps(state[field], indent=2), encoding="utf-8")
    return corrected


def render_fit_audit_node(state: PosterState) -> PosterState:
    if state.get("generation_route") != "optimization_family":
        return state
    report = audit_rendered_text(state)
    if report.get("status") == "failed":
        corrected = _correct_title_fit(state, report)
        if corrected is not None:
            report = corrected
    state["render_fit_report"] = report
    output_dir = Path(state["output_dir"]) / "content"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "render_fit_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    status = report.get("status")
    coverage = report.get("text_coverage") or {}
    by_type = coverage.get("by_type") or {}
    titles = by_type.get("section_title") or {}
    body = by_type.get("text") or {}
    summary = (f"RenderFit {status} | matched {report.get('matched_text_count', 0)}/"
               f"{report.get('expected_text_count', '?')} | titles {titles.get('matched', 0)}/"
               f"{titles.get('expected', '?')} | body {body.get('matched', 0)}/{body.get('expected', '?')}")
    (log_agent_info if status == "passed" else log_agent_warning)("render_fit_audit", summary)
    reasons = report.get("unmatched_text_reasons") or []
    for item in reasons[:8]:
        log_agent_warning("render_fit_audit", f"RenderFit unmatched | {item['element_id']} | {item['reason']}")
    if len(reasons) > 8:
        log_agent_warning("render_fit_audit", f"RenderFit unmatched | {len(reasons) - 8} more; see render_fit_report.json")
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
            f"RenderFit inconclusive | {report.get('reason') or 'incomplete editable-text coverage'}; not an all-clear",
        )
    else:
        log_agent_info("render_fit_audit", "rendered text fit passed")
    return state
