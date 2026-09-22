"""Versioned structural scoring excluding scientific/content dimensions."""

import math
from typing import Any, Dict, Optional


TEMPLATE_RUBRIC_VERSION = "structural_template_v1"

# These are structural/presentation observations, never scientific or content
# quality dimensions. Missing observations are reported, not replaced by the
# source poster's overall score.
TEMPLATE_COMPONENT_WEIGHTS = {
    "topology_integrity": 20,
    "layout_structure": 15,
    "whitespace_quality": 10,
    "primary_anchor": 10,
    "compositional_balance": 10,
    "element_alignment": 10,
    "layout_robustness": 10,
    "font_hierarchy": 10,
    "font_legibility": 5,
}


def _bounded_score(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not 0 <= number <= 100:
        return None
    return number


def _topology_score(template: Dict[str, Any]) -> Optional[float]:
    topology = template.get("zone_topology") or {}
    zones = topology.get("zones") or []
    if not zones:
        return None
    boxes = []
    ids = set()
    for zone in zones:
        if not isinstance(zone, dict):
            return 0.0
        zone_id = zone.get("zone_id")
        if not zone_id or zone_id in ids:
            return 0.0
        ids.add(zone_id)
        try:
            x, y, width, height = (
                float(zone[key]) for key in ("x", "y", "width", "height")
            )
        except (KeyError, TypeError, ValueError):
            return 0.0
        if not all(math.isfinite(value) for value in (x, y, width, height)):
            return 0.0
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1.001 or y + height > 1.001:
            return 0.0
        boxes.append((x, y, x + width, y + height))
    if topology.get("primary_anchor_zone") not in ids:
        return 50.0
    for index, (left, top, right, bottom) in enumerate(boxes):
        for other_left, other_top, other_right, other_bottom in boxes[index + 1:]:
            if min(right, other_right) - max(left, other_left) > 0.001 and min(bottom, other_bottom) - max(top, other_top) > 0.001:
                return 0.0
    return 100.0


def score_template(
    template: Dict[str, Any],
    critic_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Grade structure without using poster total/content/scientific scores."""
    report = critic_report or {}
    submetrics = report.get("submetric_scores") or (
        report.get("poster_evaluation") or {}
    ).get("submetric_scores") or {}
    components = {}
    topology = _topology_score(template)
    if topology is not None:
        components["topology_integrity"] = topology
    for name in TEMPLATE_COMPONENT_WEIGHTS:
        if name == "topology_integrity":
            continue
        value = _bounded_score(submetrics.get(name))
        if value is not None:
            components[name] = value
    available_weight = sum(TEMPLATE_COMPONENT_WEIGHTS[name] for name in components)
    score = (
        round(sum(components[name] * TEMPLATE_COMPONENT_WEIGHTS[name] for name in components) / available_weight, 2)
        if available_weight else None
    )
    return {
        "rubric_version": TEMPLATE_RUBRIC_VERSION,
        "score": score,
        "status": "scored" if available_weight == 100 else "partial" if available_weight else "unscored",
        "coverage": round(available_weight / 100, 2),
        "components": components,
        "missing_components": [name for name in TEMPLATE_COMPONENT_WEIGHTS if name not in components],
        "source": "saved_topology_and_critic_submetrics",
    }
