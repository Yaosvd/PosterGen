"""Strict, paper-free assessment of saved layout-topology transfer."""

from __future__ import annotations

from typing import Any, Dict


def assess_template_transfer(state: Dict[str, Any]) -> Dict[str, Any]:
    """Compare compiled geometry with the selected template's saved topology.

    Content may be reflowed and reverified, but family, zone order, roles,
    primary anchor and normalized zone rectangles must remain unchanged.
    """
    source = state.get("template_validation_topology") or {}
    actual = state.get("layout_spec") or {}
    source_zones = source.get("zones") or []
    actual_zones = actual.get("zones") or []
    reasons = []
    max_delta = 0.0
    if not source_zones:
        reasons.append("source_template_lacks_strict_topology")
    if source.get("family_id") != actual.get("family_id"):
        reasons.append("family_changed")
    if source.get("primary_anchor_zone") != actual.get("primary_anchor_zone"):
        reasons.append("primary_anchor_changed")
    if len(source_zones) != len(actual_zones):
        reasons.append("zone_count_changed")
    for expected, observed in zip(source_zones, actual_zones):
        if (expected.get("zone_id") != observed.get("zone_id") or
                expected.get("role") != observed.get("role")):
            reasons.append("zone_identity_changed")
            break
        try:
            delta = max(abs(float(expected.get(key) or 0) - float(observed.get(key) or 0))
                        for key in ("x", "y", "width", "height"))
        except (TypeError, ValueError):
            reasons.append("invalid_zone_geometry")
            break
        max_delta = max(max_delta, delta)
        if delta > 0.001:
            reasons.append("zone_geometry_changed")
            break
    return {
        "status": "strict_transfer_passed" if not reasons else "strict_transfer_failed",
        "passed": not reasons,
        "template_id": state.get("validation_template_id"),
        "topology_deviation": round(max_delta, 6),
        "reasons": reasons,
    }
