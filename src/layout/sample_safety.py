"""Reusable compiled-content and whitespace protection within a single sample.

No historical parent lookup, mode scheduler, or cross-sample inheritance.
"""
import re
from collections import Counter
from copy import deepcopy
from typing import Any, Dict, List
from src.layout.content_guards import sections, board_identity, recovery_allowed, claim_recovery_allowed
from src.layout.whitespace import no_displaced_whitespace
from utils.grounded_content import all_publishable_claims

def visual_occurrences(board: Any) -> set[tuple[str, str]]:
    return {
        (sid, str(asset["visual_id"]))
        for sid, section in sections(board).items()
        for asset in section.get("visual_assets") or []
        if isinstance(asset, dict) and asset.get("visual_id")
    }

def compiled_contract_audit(state: Dict[str, Any], layout: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Check that board changes actually reached the compiled/styled elements."""
    result = check_contract(state, state.get("optimized_story_board") or {})
    if not state.get("sample_content_contract"):
        return result
    violations = list(result["violations"])
    desired = state["sample_content_contract"]["desired_board"]
    containers = {str(item.get("section_id")): item for item in layout if item.get("type") == "section_container"}
    visible = {(str(item.get("section_id")), str(item.get("visual_id"))) for item in layout if item.get("type") == "visual"}
    for sid, module in desired["sections"].items():
        if sid not in containers:
            violations.append({"code": "compiled_module_missing", "section_id": sid})
        elif module.get("importance_level") is not None and containers[sid].get("importance_level") != module["importance_level"]:
            violations.append({"code": "compiled_importance_mismatch", "section_id": sid})
        for visual_id in module.get("visual_ids", []):
            if (sid, visual_id) not in visible:
                violations.append({"code": "compiled_visual_missing", "section_id": sid, "visual_id": visual_id})
        # FontAgent may add emphasis tags, never change the visible prose. Only
        # compare in memory; audit files contain identifiers/codes, not prose.
        def visible_text(value):
            without_tags = re.sub(r"<color:#[0-9a-fA-F]{6}>|</color>", "", str(value))
            without_emphasis = re.sub(r"(?<!\\)\*{1,3}", "", without_tags)
            # FontAgent escapes trusted literal backslashes/asterisks before
            # adding its own tags. Decode those escapes just as Renderer does.
            return " ".join(re.sub(r"\\([\\*])", r"\1", without_emphasis).split())
        from src.layout.editorial import presentation_lines
        expected_text = "\n".join(presentation_lines(sections(state.get("optimized_story_board") or {}).get(sid, {})))
        actual_text = "\n".join(str(item.get("content") or "") for item in layout if item.get("type") == "text" and str(item.get("section_id")) == sid)
        if " ".join(expected_text.split()) != visible_text(actual_text):
            violations.append({"code": "compiled_scientific_text_mismatch", "section_id": sid})
    for sid, visual_id in visible:
        if not recovery_allowed(state, sid, visual_id):
            violations.append({"code": "compiled_excluded_visual", "section_id": sid, "visual_id": visual_id})
    requested_gap = desired.get("layout_preferences", {}).get("section_gap_inches")
    observed_gaps = []
    for zone in (state.get("layout_spec") or {}).get("zones", []):
        ordered = [containers[sid] for sid in zone.get("section_ids", []) if sid in containers]
        for first, second in zip(ordered, ordered[1:]):
            gap = float(second["y"]) - float(first["y"]) - float(first["height"])
            observed_gaps.append(round(gap, 4))
            if requested_gap is not None and abs(gap - float(requested_gap)) > 0.01:
                violations.append({"code": "compiled_gap_mismatch", "zone_id": zone.get("zone_id")})
    return {"passed": not violations, "status": "passed" if not violations else "failed",
            "violations": violations, "observed_inter_module_gaps_inches": observed_gaps,
            "gap_status": "measured" if observed_gaps else "no_adjacent_modules"}

def final_deletion_guard(state: Dict[str, Any], layout: List[Dict[str, Any]], *,
                         poster_margin: float, title_height_fraction: float) -> Dict[str, Any]:
    """Re-measure styled module containers; never trust stale solver metrics."""
    from src.layout.whitespace import measure_composition_whitespace
    spec = state.get("layout_spec") or {}
    metrics = deepcopy(state.get("layout_feasibility_report") or {})
    metrics["composition_whitespace"] = measure_composition_whitespace(
        spec, layout, poster_width=float(state["poster_width"]),
        poster_height=float(state["poster_height"]), poster_margin=poster_margin,
        title_height_fraction=title_height_fraction,
    )
    containers = {str(item.get("section_id")): item for item in layout if item.get("type") == "section_container"}
    body_height = (float(state["poster_height"]) - 2 * poster_margin) * (1 - title_height_fraction)
    body_top = poster_margin + (float(state["poster_height"]) - 2 * poster_margin) * title_height_fraction
    utilization, gaps = {}, {}
    for zone in spec.get("zones", []):
        zone_id = str(zone.get("zone_id"))
        height = float(zone.get("height", 0)) * body_height
        top = body_top + float(zone.get("y", 0)) * body_height
        bottom = max((float(containers[sid]["y"]) + float(containers[sid]["height"]) for sid in zone.get("section_ids", []) if sid in containers), default=top)
        utilization[zone_id] = max(0.0, (bottom - top) / height) if height > 0 else 0.0
        gaps[zone_id] = max(0.0, top + height - bottom)
    metrics["zone_utilization"], metrics["exact_bottom_gaps"] = utilization, gaps
    result = deletion_guard(state, metrics)
    previous = state.get("sample_safety_report") or {}
    for key in ("rollback_status", "restored_occurrences", "original_failure"):
        if key in previous:
            result[key] = deepcopy(previous[key])
    result["measurement_source"] = "final_styled_section_containers"
    return result

def check_contract(state: Dict[str, Any], board: Dict[str, Any]) -> Dict[str, Any]:
    contract = state.get("sample_content_contract") or {}
    if not contract:
        return {"passed": True, "status": "not_requested", "violations": []}
    desired = contract.get("desired_board", {}).get("sections", {})
    actual = board_identity(board)
    violations = []
    for sid, section in desired.items():
        visible = actual["sections"].get(sid, {})
        for key in ("claim_ids", "visual_ids"):
            if not set(section.get(key, [])).issubset(visible.get(key, [])):
                violations.append({"code": "required_occurrence_missing", "section_id": sid, "field": key})
        for visual_id, count in Counter(visible.get("visual_ids", [])).items():
            if count > max(1, section.get("visual_ids", []).count(visual_id)):
                violations.append({"code": "unexpected_duplicate_visual", "section_id": sid, "visual_id": visual_id})
        if visible.get("importance_level") != section.get("importance_level"):
            violations.append({"code": "importance_not_preserved", "section_id": sid})
    for sid, visual_id in visual_occurrences(board):
        if not recovery_allowed(state, sid, visual_id):
            violations.append({"code": "excluded_visual_restored", "section_id": sid, "visual_id": visual_id})
    for visual_id in contract.get("duplicate_keep_visual_ids", []):
        if not any(v == visual_id for _, v in visual_occurrences(board)):
            violations.append({"code": "last_duplicate_removed", "visual_id": visual_id})
    index = all_publishable_claims(state)
    for sid, section in sections(board).items():
        for cid in section.get("claim_ids", []):
            if not claim_recovery_allowed(state, sid, index.get(cid) or {"claim_id": cid}):
                violations.append({"code": "excluded_claim_restored", "section_id": sid, "claim_id": cid})
    if actual["layout_preferences"] != contract.get("desired_board", {}).get("layout_preferences", {}):
        violations.append({"code": "layout_preferences_not_preserved"})
    return {"passed": not violations, "status": "passed" if not violations else "failed", "violations": violations}

def deletion_guard(state: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    contract = state.get("sample_content_contract") or {}
    requested = bool(contract.get("removed_visual_occurrences") or contract.get("removed_claim_occurrences"))
    if not requested:
        return {"schema_version": 1, "passed": True, "status": "not_requested", "reasons": []}
    before = (state.get("sample_fit_baseline") or {}).get("fit_report") or {}
    settings = (state.get("critic_config") or {}).get("capacity_repair") or {}
    fraction = float(settings.get("max_whitespace_regression_fraction", 0.01))
    gap = float(settings.get("max_gap_regression_inches", 0.35))
    reasons = []
    baseline = bool(before.get("composition_whitespace") and before.get("zone_utilization"))
    if baseline:
        if not no_displaced_whitespace(before["composition_whitespace"], report.get("composition_whitespace") or {}, tolerance=fraction, gap_tolerance_inches=gap):
            reasons.append("whole_poster_whitespace_regression")
        old_fill = min((before.get("zone_utilization") or {}).values(), default=1.0)
        new_fill = min((report.get("zone_utilization") or {}).values(), default=0.0)
        if new_fill + fraction < old_fill:
            reasons.append("worst_zone_utilization_regression")
        old_gap = max((before.get("exact_bottom_gaps") or {}).values(), default=0.0)
        new_gap = max((report.get("exact_bottom_gaps") or {}).values(), default=0.0)
        if new_gap > old_gap + gap:
            reasons.append("bottom_gap_regression")
    # Absolute severe-fit admission remains the responsibility of the ordinary
    # section-fit Critic. Missing baselines are never reported as a measured win.
    return {"schema_version": 1, "passed": not reasons,
            "status": "passed" if not reasons else "failed",
            "baseline_status": "available" if baseline else "unavailable_absolute_critic_required",
            "before": {k: deepcopy(before.get(k)) for k in ("composition_whitespace", "zone_utilization", "exact_bottom_gaps")},
            "after": {k: deepcopy(report.get(k)) for k in ("composition_whitespace", "zone_utilization", "exact_bottom_gaps")},
            "reasons": reasons, "target_utilization": [0.95, 1.0]}
