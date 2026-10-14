"""Shared allow-list and compatibility mapping for Improve revisions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional


LAYOUT_OPERATIONS = {
    "move_section_to_zone",
    "swap_section_zones",
    "set_reading_order",
    "set_primary_anchor",
    "adjust_zone_budget",
}

BOARD_OPERATIONS = {
    "remove_claim",
    "remove_visual",
    "move_visual",
    "replace_visual",
    "restore_visual",
    "restore_visual_aspect_ratio",
    "set_section_importance",
    "set_section_gap",
}

CONTENT_OPERATIONS = {
    "use_claim_variant",
    "create_compact_variant",
    "add_existing_claim",
    "add_claim_from_evidence",
}

STYLE_OPERATIONS = {
    "repair_text_contrast",
    "reduce_accent_density",
    "use_accessible_palette_variant",
    "normalize_semantic_colors",
    "normalize_typography_hierarchy",
    "increase_title_separation",
    "normalize_font_family",
}

ALL_OPERATIONS = (
    LAYOUT_OPERATIONS | BOARD_OPERATIONS | CONTENT_OPERATIONS | STYLE_OPERATIONS
)


def normalize_revision_operation(raw: Any) -> Optional[Dict[str, Any]]:
    """Translate safe legacy requests and reject ambiguous column semantics."""

    if not isinstance(raw, dict):
        return None
    operation = str(raw.get("operation") or "")
    normalized = deepcopy(raw)
    if operation == "move_section" and raw.get("zone_id"):
        normalized["operation"] = "move_section_to_zone"
        normalized.pop("column", None)
    elif operation == "reorder_sections":
        normalized["operation"] = "set_reading_order"
    elif operation == "swap_sections":
        normalized["operation"] = "swap_section_zones"
    elif operation == "set_vertical_priority":
        level = {"top": 1, "middle": 2, "bottom": 3}.get(
            str(raw.get("priority") or "")
        )
        if level is None:
            return None
        normalized = {
            "operation": "set_section_importance",
            "section_id": raw.get("section_id"),
            "importance_level": level,
            "reason": raw.get("reason"),
        }
    if normalized.get("operation") not in ALL_OPERATIONS:
        return None
    return normalized
