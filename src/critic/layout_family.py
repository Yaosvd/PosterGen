"""Layout-family contract and family-aware Critic evaluation."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.critic.base import CriticContext, EvaluationResult, issue
from src.layout.families import LayoutFamilyRegistry


def _overlap(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    x1 = max(float(left["x"]), float(right["x"]))
    y1 = max(float(left["y"]), float(right["y"]))
    x2 = min(
        float(left["x"]) + float(left["width"]),
        float(right["x"]) + float(right["width"]),
    )
    y2 = min(
        float(left["y"]) + float(left["height"]),
        float(right["y"]) + float(right["height"]),
    )
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


class LayoutFamilyCriticEvaluator:
    """Validate the grammar contract and add family-specific observations."""

    name = "layout_family"

    def __init__(self) -> None:
        self.registry = LayoutFamilyRegistry()

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = context.config["evaluators"].get(self.name, {})
        version = str(settings.get("version", "1.0.0"))
        hard_gate = bool(settings.get("hard_gate", True))
        spec = context.state.get("layout_spec") or {}
        family_id = str(spec.get("family_id") or "classic_three_column")
        problems: List[Dict[str, Any]] = []
        positives: List[Dict[str, Any]] = []

        if family_id not in self.registry.ids():
            problems.append(issue(
                "LAYOUT-FAMILY-UNKNOWN",
                severity="critical",
                scope="layout_family",
                observation=f"Unknown layout family: {family_id}",
                required_outcome="Select one registered layout family",
                allowed_operations=["switch_layout_family"],
                forbidden_operations=["supply_raw_coordinates"],
            ))
            return EvaluationResult(
                evaluator=self.name,
                version=version,
                hard_gate=hard_gate,
                passed=False,
                scores={"layout_integrity": 0.0},
                issues=problems,
            )

        zones = spec.get("zones") or []
        zone_ids = set()
        assigned: List[str] = []
        for zone in zones:
            zone_id = str(zone.get("zone_id") or "")
            try:
                values: Tuple[float, float, float, float] = tuple(
                    float(zone[key]) for key in ("x", "y", "width", "height")
                )
            except (KeyError, TypeError, ValueError):
                values = (-1.0, -1.0, -1.0, -1.0)
            x, y, width, height = values
            if (
                not zone_id
                or zone_id in zone_ids
                or width <= 0
                or height <= 0
                or x < 0
                or y < 0
                or x + width > 1.0001
                or y + height > 1.0001
            ):
                problems.append(issue(
                    "LAYOUT-FAMILY-ZONE-INVALID",
                    severity="critical",
                    scope="layout_family",
                    observation=f"Layout zone {zone_id or '<missing>'} is invalid",
                    required_outcome="Compile all zones inside normalized poster bounds",
                    location={"zone_id": zone_id},
                    allowed_operations=["switch_layout_family", "rebuild_layout_spec"],
                    forbidden_operations=["supply_raw_coordinates"],
                ))
            zone_ids.add(zone_id)
            assigned.extend(str(item) for item in zone.get("section_ids", []))

        for index, left in enumerate(zones):
            for right in zones[index + 1:]:
                if _overlap(left, right) > 1e-6:
                    problems.append(issue(
                        "LAYOUT-FAMILY-ZONES-OVERLAP",
                        severity="critical",
                        scope="layout_family",
                        observation=(
                            f"Zones {left.get('zone_id')} and "
                            f"{right.get('zone_id')} overlap"
                        ),
                        required_outcome="Use a non-overlapping registered family skeleton",
                        allowed_operations=["switch_layout_family", "rebuild_layout_spec"],
                        forbidden_operations=["supply_raw_coordinates"],
                    ))

        reading_order = [str(item) for item in spec.get("reading_order", [])]
        if len(assigned) != len(set(assigned)) or set(reading_order) != set(assigned):
            problems.append(issue(
                "LAYOUT-FAMILY-READING-ORDER",
                severity="major",
                scope="layout_family",
                observation="Reading order is missing, duplicated, or inconsistent with zone assignments",
                required_outcome="Give every visible section one unambiguous reading-order position",
                allowed_operations=["set_reading_order", "rebuild_layout_spec"],
                forbidden_operations=["rewrite_scientific_text"],
            ))

        containers = [
            item
            for item in (context.state.get("styled_layout") or context.state.get("design_layout") or [])
            if item.get("type") == "section_container"
        ]
        if (
            family_id != "classic_three_column"
            or context.state.get("generation_route") == "optimization_family"
        ):
            invalid_containers = [
                item for item in containers if item.get("zone_id") not in zone_ids
            ]
            if invalid_containers:
                problems.append(issue(
                    "LAYOUT-FAMILY-UNASSIGNED-CONTAINER",
                    severity="critical",
                    scope="layout_family",
                    observation="Rendered sections are not assigned to registered layout zones",
                    required_outcome="Compile every rendered section from LayoutSpec",
                    allowed_operations=["rebuild_layout_spec"],
                    forbidden_operations=["supply_raw_coordinates"],
                ))

        hero_zone = spec.get("primary_anchor_zone")
        if hero_zone:
            hero_sections = next(
                (
                    zone.get("section_ids", [])
                    for zone in zones
                    if zone.get("zone_id") == hero_zone
                ),
                [],
            )
            if not hero_sections:
                problems.append(issue(
                    "LAYOUT-FAMILY-HERO-EMPTY",
                    severity="major",
                    scope="visual_hierarchy",
                    observation="The selected hero zone has no scientific module",
                    required_outcome="Place a high-importance grounded module in the hero zone",
                    location={"zone_id": hero_zone},
                    allowed_operations=["move_section_to_zone", "set_primary_anchor"],
                    forbidden_operations=["invent_visual", "rewrite_scientific_text"],
                ))
            else:
                positives.append({
                    "pattern_id": "LAYOUT-FAMILY-HERO-ASSIGNED",
                    "scope": "visual_hierarchy",
                    "observation": "The family primary anchor contains a grounded module",
                })

        zone_sections = {
            str(zone.get("zone_id")): [
                str(item) for item in zone.get("section_ids", [])
            ]
            for zone in zones
        }
        required_anchors = {
            "method_flow_spine": ("flow_spine",),
            "comparison_split": ("comparison_a", "comparison_b"),
            "result_dashboard_cards": ("primary_result",),
            "top_hero_bottom_grid": ("top_hero",),
            "central_hero_side_rails": ("central_hero",),
            "modular_editorial_mosaic": ("lead",),
        }
        empty_required = [
            zone_id
            for zone_id in required_anchors.get(family_id, ())
            if not zone_sections.get(zone_id)
        ]
        if empty_required:
            problems.append(issue(
                "LAYOUT-FAMILY-REQUIRED-REGION-EMPTY",
                severity="major",
                scope="visual_hierarchy",
                observation=(
                    f"{family_id} has empty required regions: "
                    + ", ".join(empty_required)
                ),
                required_outcome="Assign grounded modules to every family-defining region",
                allowed_operations=["move_section_to_zone", "set_primary_anchor"],
                forbidden_operations=["invent_section", "rewrite_scientific_text"],
            ))

        if family_id == "small_multiples_matrix":
            occupancies = [len(items) for items in zone_sections.values()]
            if occupancies and max(occupancies) - min(occupancies) > 1:
                problems.append(issue(
                    "LAYOUT-FAMILY-SMALL-MULTIPLES-IMBALANCE",
                    severity="major",
                    scope="visual_balance",
                    observation="Small-multiple cells have strongly uneven module counts",
                    required_outcome="Distribute peer result modules evenly across matrix cells",
                    allowed_operations=["move_section_to_zone"],
                    forbidden_operations=["invent_visual", "rewrite_scientific_text"],
                ))

        if family_id in {
            "horizontal_narrative_bands",
            "timeline_stage_narrative",
        }:
            expected_order = [
                section_id
                for zone in zones
                for section_id in zone.get("section_ids", [])
            ]
            if reading_order != expected_order:
                problems.append(issue(
                    "LAYOUT-FAMILY-SEQUENCE-DISCONTINUITY",
                    severity="major",
                    scope="layout_family",
                    observation="Sequential family reading order does not follow its ordered zones",
                    required_outcome="Restore the family zone sequence without changing scientific text",
                    allowed_operations=["set_reading_order", "move_section_to_zone"],
                    forbidden_operations=["rewrite_scientific_text"],
                ))

        critical = any(
            item.get("severity") == "critical" for item in problems
        )
        major_count = sum(item.get("severity") == "major" for item in problems)
        layout_score = 0.0 if critical else max(70.0, 100.0 - major_count * 15.0)
        hierarchy_score = max(65.0, 95.0 - major_count * 15.0)
        return EvaluationResult(
            evaluator=self.name,
            version=version,
            hard_gate=hard_gate,
            passed=not critical,
            scores={
                "layout_integrity": layout_score,
                "visual_hierarchy": hierarchy_score,
            },
            issues=problems,
            positive_patterns=positives,
            metadata={
                "layout_family": family_id,
                "zone_count": len(zones),
                "reading_order": reading_order,
            },
        )
