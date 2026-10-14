"""Text-free Improve contracts, recovery policy, and deletion admission guards.

The current storyboard is a working document; the parent is only evidence.
Policies are branch-local and never alter the immutable source-asset manifest.
"""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any, Dict, List

from src.layout.whitespace import no_displaced_whitespace
from utils.grounded_content import all_publishable_claims, claim_root_id


def readable_source_asset(state: Dict[str, Any], visual_id: str) -> bool:
    """File integrity only, not a pixel-based scientific classification."""
    prefix, _, number = visual_id.partition("_")
    collection = state.get("images" if prefix == "figure" else "tables" if prefix == "table" else "") or {}
    asset = collection.get(number) or {}
    try:
        from PIL import Image
        with Image.open(str(asset.get("path") or "")) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def sections(board: Any) -> Dict[str, Dict[str, Any]]:
    return {
        str(item["section_id"]): item
        for item in (board or {}).get("spatial_content_plan", {}).get("sections", [])
        if isinstance(item, dict) and item.get("section_id")
    }


def visual_occurrences(board: Any) -> set[tuple[str, str]]:
    return {
        (sid, str(asset["visual_id"]))
        for sid, section in sections(board).items()
        for asset in section.get("visual_assets") or []
        if isinstance(asset, dict) and asset.get("visual_id")
    }


def authorize_deletions(operations: List[Dict[str, Any]], state: Dict[str, Any],
                        board: Dict[str, Any]) -> tuple[list, list]:
    """Require scoped, actionable Critic evidence, not a free-form LLM reason."""
    base_report = state.get("critic_report") or {}
    latest_report = (state.get("lineage_feedback") or {}).get("critic_report") or {}
    issues = {
        str(item.get("issue_id")): item
        for report in (base_report, latest_report)
        if report.get("rubric_version") == base_report.get("rubric_version")
        for item in report.get("issues", [])
        if isinstance(item, dict) and item.get("issue_id")
    }
    approved, rejected = [], []
    remaining = Counter(
        (sid, str(asset.get("visual_id"))) for sid, section in sections(board).items()
        for asset in section.get("visual_assets", []) if isinstance(asset, dict) and asset.get("visual_id")
    )
    by_section = sections(board)
    for index, raw in enumerate(operations):
        op = deepcopy(raw)
        op["operation_id"] = f"op_{index + 1:03d}"
        kind = op.get("operation")
        if kind == "restore_visual":
            sid, visual_id = str(op.get("section_id") or ""), str(op.get("visual_id") or "")
            valid = bool(op.get("reason") and sid in by_section
                         and visual_id in (state.get("layout_visual_source_manifest") or {}).get(sid, [])
                         and readable_source_asset(state, visual_id))
            if not valid:
                rejected.append({"operation_id": op["operation_id"], "operation": kind,
                                 "section_id": sid, "object_id": visual_id,
                                 "reason": "restore requires a readable approved original source occurrence"})
                continue
        if kind not in {"remove_visual", "replace_visual", "remove_claim"}:
            approved.append(op)
            continue
        object_id = str(op.get("claim_id") if kind == "remove_claim" else op.get("visual_id") or "")
        sid = str(op.get("section_id") or "")
        if not sid and kind == "replace_visual":
            owners = [s for s, v in visual_occurrences(board) if v == object_id]
            sid = owners[0] if len(owners) == 1 else ""
            op["section_id"] = sid
        refs = op.get("critic_issue_ids", op.get("issue_ids", []))
        refs = refs if isinstance(refs, list) else []
        matched = []
        for ref in refs:
            issue = issues.get(str(ref)) or {}
            evidence = issue.get("evidence") or {}
            # Both deterministic and validated multimodal locations are supported.
            location = issue.get("location") or {}
            location = location if isinstance(location, dict) else {}
            issue_sid = str(issue.get("section_id") or location.get("section_id") or evidence.get("section_id") or "")
            object_ids = {
                str(value) for key in ("visual_id", "claim_id", "element_id")
                for value in [issue.get(key), evidence.get(key), location.get(key)] if value
            }
            for key in ("visual_ids", "claim_ids"):
                object_ids.update(str(value) for value in evidence.get(key, []) if value)
            # A section-scoped physical overflow may justify deleting a low-
            # priority occurrence, but an unrelated/global aesthetic issue cannot.
            scoped = object_id in object_ids if object_ids else (issue_sid == sid and bool(sid))
            if scoped and kind in issue.get("allowed_operations", []) and kind not in issue.get("forbidden_operations", []):
                matched.append(issue)
        if not op.get("reason") or sid not in by_section or not matched:
            rejected.append({"operation_id": op["operation_id"], "operation": kind,
                             "section_id": sid, "object_id": object_id,
                             "reason": "missing scoped Critic evidence or reason"})
            continue
        unusable = any(str(i.get("issue_id", "")).startswith((
            "VISUAL-ASSET-MISSING-", "VISUAL-ASSET-UNKNOWN-", "VISUAL-ASSET-UNREADABLE-"
        )) for i in matched)
        duplicate_only = all(i.get("issue_id") == "VISUAL-ASSET-DUPLICATED" for i in matched)
        protected = object_id == (state.get("classified_visuals") or {}).get("key_visual") or any(
            object_id in ((state.get("classified_visuals") or {}).get(role) or [])
            for role in ("main_results", "method_workflow")
        )
        object_evidence = any(
            (i.get("location") or {}).get("visual_id") == object_id
            or object_id in (i.get("evidence") or {}).get("visual_ids", [])
            or (i.get("evidence") or {}).get("visual_id") == object_id
            for i in matched
        )
        if (duplicate_only and sum(count for (_, v), count in remaining.items() if v == object_id) <= 1) or (
            protected and kind == "remove_visual" and not unusable and not object_evidence
        ):
            rejected.append({"operation_id": op["operation_id"], "operation": kind,
                             "object_id": object_id, "section_id": sid,
                             "reason": "last duplicate or protected visual lacks object-specific evidence"})
            continue
        if kind in {"remove_visual", "replace_visual"}:
            if duplicate_only:
                remaining[(sid, object_id)] = max(0, remaining[(sid, object_id)] - 1)
            else:
                remaining.pop((sid, object_id), None)
        codes = " ".join(str(i.get("issue_id", "")) for i in matched).upper()
        op["deletion_class"] = (
            "unusable_asset" if unusable else "duplicate_occurrence" if duplicate_only
            else "resolution" if "RESOLUTION" in codes or "DPI" in codes
            else "physical_capacity" if "OVERFLOW" in codes or "BOUNDS" in codes or "OVERFULL" in codes
            else "content_concision" if kind == "remove_claim" else "visual_relevance"
        )
        op["critic_issue_ids"] = [str(i["issue_id"]) for i in matched]
        approved.append(op)
    return approved, rejected


def revoke_harmful_deletions(state: Dict[str, Any], board: Dict[str, Any]) -> tuple[Dict[str, Any], list]:
    """One bounded rollback; never restore assets declared unusable by Critic."""
    contract = state.get("revision_contract") or {}
    parent = (state.get("improve_parent_snapshot") or {}).get("effective_board") or state.get("revision_parent_story_board") or {}
    revised = deepcopy(board)
    by_id, parent_sections = sections(revised), sections(parent)
    policy = deepcopy(state.get("revision_recovery_policy") or {})
    restored = []
    current_visuals = {v for _, v in visual_occurrences(revised)}
    for sid, visual_id in contract.get("removed_visual_occurrences", []):
        if visual_id in policy.get("unusable_visual_ids", []) or visual_id in current_visuals or sid not in by_id:
            continue
        if not readable_source_asset(state, visual_id):
            continue
        original = next((v for v in parent_sections.get(sid, {}).get("visual_assets", []) if v.get("visual_id") == visual_id), None)
        if original:
            for op in (state.get("revision_plan") or {}).get("operations", []):
                if op.get("operation") == "replace_visual" and str(op.get("section_id")) == sid and op.get("visual_id") == visual_id:
                    replacement_id = op.get("replacement_visual_id")
                    if (sid, str(replacement_id)) not in visual_occurrences(parent):
                        by_id[sid]["visual_assets"] = [v for v in by_id[sid].get("visual_assets", []) if v.get("visual_id") != replacement_id]
            by_id[sid].setdefault("visual_assets", []).append(deepcopy(original))
            policy["excluded_visual_occurrences"] = [item for item in policy.get("excluded_visual_occurrences", []) if item != [sid, visual_id]]
            policy.setdefault("visual_targets", {})[visual_id] = [sid]
            restored.append([sid, visual_id])
    index = all_publishable_claims(state)
    for sid, cid in contract.get("removed_claim_occurrences", []):
        if sid not in by_id or cid not in index:
            continue
        if cid not in by_id[sid].get("claim_ids", []):
            by_id[sid].setdefault("claim_ids", []).append(cid)
            root = claim_root_id(index[cid])
            policy["excluded_claim_roots"] = [item for item in policy.get("excluded_claim_roots", []) if item != [sid, root]]
            restored.append([sid, cid])
    if not restored:
        return revised, []
    from utils.grounded_content import rematerialize_board
    rematerialize_board(revised, index)
    state["revision_recovery_policy"] = policy
    # Recompute final retention, while keeping the original deletion audit.
    contract["desired_board"] = board_identity(revised)
    contract["recovery_policy"] = deepcopy(policy)
    contract["revoked_operation_ids"] = [
        op.get("operation_id") for op in (state.get("revision_plan") or {}).get("operations", [])
        if [str(op.get("section_id")), str(op.get("visual_id") or op.get("claim_id"))] in restored
        and op.get("operation") in {"remove_visual", "replace_visual", "remove_claim"}
    ]
    constraints = state.setdefault("layout_revision_constraints", {})
    constraints["must_retain_claim_ids"] = sorted({cid for item in by_id.values() for cid in item.get("claim_ids", [])})
    constraints["must_retain_visual_ids"] = sorted({v for _, v in visual_occurrences(revised)})
    return revised, restored


def operation_audit(state: Dict[str, Any], board: Dict[str, Any],
                    prior_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Audit actual final effects, including operations superseded by later ones."""
    actual = board_identity(board)
    desired = (state.get("revision_contract") or {}).get("desired_board") or actual
    revoked = (state.get("revision_contract") or {}).get("revoked_operation_ids", [])
    parent = board_identity(state.get("revision_parent_story_board") or {})
    result = []
    operations = (state.get("revision_plan") or {}).get("operations", [])
    zone_trace = {str(sid): str(zone.get("zone_id"))
                  for zone in (state.get("revision_parent_layout_spec") or {}).get("zones", [])
                  for sid in zone.get("section_ids", [])}

    def effect(op, identity):
        kind, sid = op.get("operation"), str(op.get("section_id") or "")
        module = identity["sections"].get(sid, {})
        if kind == "remove_claim":
            return op.get("claim_id") not in module.get("claim_ids", [])
        if kind == "remove_visual":
            if op.get("deletion_class") == "duplicate_occurrence":
                original_count = parent["sections"].get(sid, {}).get("visual_ids", []).count(op.get("visual_id"))
                return module.get("visual_ids", []).count(op.get("visual_id")) < original_count
            return op.get("visual_id") not in module.get("visual_ids", [])
        if kind == "replace_visual":
            return op.get("visual_id") not in module.get("visual_ids", []) and op.get("replacement_visual_id") in module.get("visual_ids", [])
        if kind == "move_visual":
            return op.get("visual_id") in identity["sections"].get(str(op.get("target_section_id")), {}).get("visual_ids", [])
        if kind == "restore_visual":
            return op.get("visual_id") in module.get("visual_ids", [])
        if kind == "set_section_importance":
            return module.get("importance_level") == int(op.get("importance_level"))
        if kind == "set_section_gap":
            return identity["layout_preferences"].get("section_gap_inches") == round(float(op.get("gap_inches")), 3)
        if kind == "restore_visual_aspect_ratio":
            return op.get("visual_id") in identity["layout_preferences"].get("preserve_visual_aspect_ids", [])
        return None

    for op, previous in zip(operations, prior_results):
        kind = op.get("operation")
        if kind == "move_section_to_zone":
            zone_trace[str(op.get("section_id"))] = str(op.get("zone_id"))
        elif kind == "swap_section_zones":
            first, second = str(op.get("first_section_id")), str(op.get("second_section_id"))
            zone_trace[first], zone_trace[second] = zone_trace.get(second), zone_trace.get(first)
        entry = {**previous, "operation_id": op.get("operation_id"),
                 "section_id": op.get("section_id"), "visual_id": op.get("visual_id"),
                 "claim_id": op.get("claim_id")}
        observed, expected = effect(op, actual), effect(op, desired)
        if state.get("improve_safe_fallback"):
            entry["status"] = "rolled_back"
        elif op.get("operation_id") in revoked:
            entry["status"] = "revoked"
        elif expected is False:
            entry["status"] = "superseded"
        elif observed is not None:
            entry["status"] = "already_satisfied" if observed and effect(op, parent) else "applied" if observed else "not_applied"
            entry["detail"] = "final visible storyboard effect verified"
        elif op.get("preset"):
            preset_keys = {
                "repair_text_contrast": "contrast_mode", "reduce_accent_density": "accent_density",
                "use_accessible_palette_variant": "palette_variant", "normalize_semantic_colors": "semantic_colors",
                "normalize_typography_hierarchy": "typography_hierarchy", "increase_title_separation": "typography_hierarchy",
                "normalize_font_family": "font_family",
            }
            key = preset_keys.get(op.get("operation"))
            entry["status"] = "applied" if key and (state.get("style_overrides") or {}).get(key) == op["preset"] else "superseded"
            entry["detail"] = "deterministic style preset verified"
        elif kind in {"move_section_to_zone", "swap_section_zones", "set_reading_order", "set_primary_anchor"}:
            constraints = state.get("layout_revision_constraints") or {}
            superseded = (
                kind == "move_section_to_zone" and
                (constraints.get("section_to_zone") or {}).get(str(op.get("section_id"))) != op.get("zone_id")
            ) or (
                kind == "set_reading_order" and
                constraints.get("reading_order") != op.get("section_order")
            ) or (
                kind == "set_primary_anchor" and
                constraints.get("primary_anchor_zone") != op.get("zone_id")
            ) or (
                kind == "swap_section_zones" and any(
                    (constraints.get("section_to_zone") or {}).get(sid) != zone_trace.get(sid)
                    for sid in (str(op.get("first_section_id")), str(op.get("second_section_id")))
                )
            )
            if superseded:
                entry["status"] = "superseded"
        result.append(entry)
    return result


def compiled_contract_audit(state: Dict[str, Any], layout: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Check that board changes actually reached the compiled/styled elements."""
    result = check_contract(state, state.get("optimized_story_board") or {})
    if not state.get("revision_contract") or state.get("improve_safe_fallback"):
        return result
    violations = list(result["violations"])
    desired = state["revision_contract"]["desired_board"]
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
        expected_text = "\n".join(sections(state.get("optimized_story_board") or {}).get(sid, {}).get("text_content", []))
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
    previous = state.get("revision_safety_report") or {}
    for key in ("rollback_status", "restored_occurrences", "original_failure"):
        if key in previous:
            result[key] = deepcopy(previous[key])
    result["measurement_source"] = "final_styled_section_containers"
    return result


def build_contract(state: Dict[str, Any], parent: Dict[str, Any], board: Dict[str, Any],
                   operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive effective exclusions from the final sequential board, not requests."""
    old, current = visual_occurrences(parent), visual_occurrences(board)
    index = all_publishable_claims(state)
    previous = state.get("revision_recovery_policy") or {}
    excluded = {tuple(item) for item in previous.get("excluded_visual_occurrences", [])}
    excluded.update(old - current)
    excluded.difference_update(current)  # explicit future placement revokes exclusion
    unusable = set(previous.get("unusable_visual_ids", []))
    # Only a verified explicit later placement can retire an old unusable flag.
    # A surviving duplicate in the parent is not evidence of file integrity.
    for op in operations:
        restored_id = ""
        if op.get("operation") == "restore_visual":
            restored_id = str(op.get("visual_id") or "")
        elif op.get("operation") == "replace_visual":
            restored_id = str(op.get("replacement_visual_id") or "")
        if restored_id and readable_source_asset(state, restored_id):
            unusable.discard(restored_id)
    for op in operations:
        if op.get("deletion_class") == "unusable_asset":
            unusable.add(str(op.get("visual_id")))
    excluded_roots = {tuple(item) for item in previous.get("excluded_claim_roots", [])}
    for sid, section in sections(parent).items():
        now = set(sections(board).get(sid, {}).get("claim_ids", []))
        for cid in set(section.get("claim_ids", [])) - now:
            excluded_roots.add((sid, claim_root_id(index.get(cid) or {"claim_id": cid})))
    for sid, section in sections(board).items():
        for cid in section.get("claim_ids", []):
            excluded_roots.discard((sid, claim_root_id(index.get(cid) or {"claim_id": cid})))
    targets = {str(key): list(value) for key, value in (previous.get("visual_targets") or {}).items()}
    for visual_id in {v for _, v in current}:
        targets[visual_id] = sorted(s for s, v in current if v == visual_id)
    policy = {
        "schema_version": 1,
        "excluded_visual_occurrences": [list(item) for item in sorted(excluded)],
        "unusable_visual_ids": sorted(unusable),
        "excluded_claim_roots": [list(item) for item in sorted(excluded_roots)],
        "visual_targets": targets,
    }
    state["revision_recovery_policy"] = policy
    return {
        "schema_version": 1, "desired_board": board_identity(board),
        "deletion_evidence": [{
            "operation_id": op.get("operation_id"), "section_id": op.get("section_id"),
            "object_id": op.get("visual_id") or op.get("claim_id"),
            "deletion_class": op.get("deletion_class"),
            "critic_issue_ids": list(op.get("critic_issue_ids", [])),
        } for op in operations if op.get("operation") in {"remove_visual", "replace_visual", "remove_claim"}],
        "duplicate_keep_visual_ids": sorted({
            str(op.get("visual_id")) for op in operations
            if "VISUAL-ASSET-DUPLICATED" in op.get("critic_issue_ids", [])
            and str(op.get("visual_id")) not in unusable
        }),
        "removed_visual_occurrences": [
            [sid, visual_id] for sid, section in sections(parent).items()
            for visual_id, count in Counter(
                str(v.get("visual_id")) for v in section.get("visual_assets", []) if isinstance(v, dict)
            ).items()
            for _ in range(max(0, count - sum(1 for v in sections(board).get(sid, {}).get("visual_assets", []) if v.get("visual_id") == visual_id)))
        ],
        "removed_claim_occurrences": [
            [sid, cid] for sid, section in sections(parent).items()
            for cid in section.get("claim_ids", [])
            if cid not in sections(board).get(sid, {}).get("claim_ids", [])
        ],
        "recovery_policy": deepcopy(policy), "revoked_operation_ids": [],
    }


def board_identity(board: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sections": {sid: {
            "claim_ids": list(item.get("claim_ids", [])),
            "visual_ids": [str(v.get("visual_id")) for v in item.get("visual_assets", []) if isinstance(v, dict)],
            "importance_level": item.get("importance_level"),
        } for sid, item in sections(board).items()},
        "layout_preferences": deepcopy(board.get("layout_preferences") or {}),
    }


def recovery_allowed(state: Dict[str, Any], sid: str, visual_id: str) -> bool:
    policy = state.get("revision_recovery_policy") or {}
    if visual_id in policy.get("unusable_visual_ids", []):
        return False
    if [sid, visual_id] in policy.get("excluded_visual_occurrences", []):
        return False
    targets = (policy.get("visual_targets") or {}).get(visual_id)
    return targets is None or sid in targets


def claim_recovery_allowed(state: Dict[str, Any], sid: str, claim: Dict[str, Any]) -> bool:
    return [sid, claim_root_id(claim)] not in (state.get("revision_recovery_policy") or {}).get("excluded_claim_roots", [])


def check_contract(state: Dict[str, Any], board: Dict[str, Any]) -> Dict[str, Any]:
    contract = state.get("revision_contract") or {}
    if not contract or state.get("improve_safe_fallback"):
        return {"passed": True, "status": "parent_fallback" if state.get("improve_safe_fallback") else "not_requested", "violations": []}
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
    contract = state.get("revision_contract") or {}
    requested = bool(contract.get("removed_visual_occurrences") or contract.get("removed_claim_occurrences"))
    if not requested or state.get("improve_safe_fallback"):
        return {"schema_version": 1, "passed": True, "status": "not_requested", "reasons": []}
    before = (state.get("improve_parent_snapshot") or {}).get("fit_report") or {}
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


def apply_revision_admission(state: Dict[str, Any], report: Dict[str, Any]) -> None:
    """Never change raw Critic scores or nested poster evaluation after render."""
    if (state.get("iteration_context") or {}).get("portfolio_mode") != "improve":
        return
    contract = check_contract(state, state.get("optimized_story_board") or {})
    guard = state.get("revision_safety_report") or {}
    compiled = (state.get("revision_execution_report") or {}).get("compiled_contract_check") or {}
    required = bool(state.get("revision_contract")) and not state.get("improve_safe_fallback")
    passed = contract["passed"] and compiled.get("passed", not required) and guard.get("passed", not required)
    report["revision_admission"] = {"passed": passed, "contract": contract,
                                    "deletion_guard": deepcopy(guard),
                                    "critic_archive_eligible": bool(report.get("archive_eligible"))}
    if not passed:
        report["archive_eligible"] = False
        report["template_eligible"] = False
        report["loop_disposition"] = "revision_safety_rejected"
