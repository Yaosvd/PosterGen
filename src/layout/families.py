"""Versioned, content-agnostic layout-family grammar and compiler.

The language model never owns final coordinates.  A family describes normalized
body zones, the architect assigns grounded sections to those zones, and the
compiler asks the existing LayoutAgent measurement helpers to materialize exact
editable-PowerPoint geometry.
"""

from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence


LAYOUT_ENGINE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LayoutFamily:
    family_id: str
    label: str
    description: str
    zones: Sequence[Dict[str, Any]]
    capabilities: Sequence[str]
    preferred_profiles: Sequence[str] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family_id": self.family_id,
            "label": self.label,
            "description": self.description,
            "zones": [dict(zone) for zone in self.zones],
            "capabilities": list(self.capabilities),
            "preferred_profiles": list(self.preferred_profiles),
        }


def _zone(
    zone_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    role: str = "support",
    capacity: int = 1,
) -> Dict[str, Any]:
    return {
        "zone_id": zone_id,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "role": role,
        "capacity": capacity,
    }


FAMILIES: Sequence[LayoutFamily] = (
    LayoutFamily(
        "classic_three_column",
        "Classic three column",
        "The preserved balanced PosterGen baseline.",
        (
            _zone("left", 0.00, 0.00, 0.32, 1.00, capacity=4),
            _zone("middle", 0.34, 0.00, 0.32, 1.00, capacity=4),
            _zone("right", 0.68, 0.00, 0.32, 1.00, capacity=4),
        ),
        ("general", "balanced"),
    ),
    LayoutFamily(
        "asymmetric_two_column",
        "Asymmetric two column",
        "A narrow narrative rail paired with a wide evidence field.",
        (
            _zone("narrative_rail", 0.00, 0.00, 0.31, 1.00, capacity=4),
            _zone("evidence_field", 0.34, 0.00, 0.66, 1.00, role="hero", capacity=5),
        ),
        ("general", "hero", "asymmetric"),
        ("visual_heavy", "balanced"),
    ),
    LayoutFamily(
        "four_column_modular",
        "Four-column modular",
        "Four compact tracks that support short, numerous modules.",
        tuple(
            _zone(f"column_{index + 1}", index * 0.255, 0.00, 0.235, 1.00, capacity=3)
            for index in range(4)
        ),
        ("dense", "modular", "small_multiples"),
        ("visual_heavy",),
    ),
    LayoutFamily(
        "central_hero_side_rails",
        "Central hero with side rails",
        "A dominant central evidence region with two supporting rails.",
        (
            _zone("left_rail", 0.00, 0.00, 0.23, 1.00, capacity=3),
            _zone("central_hero", 0.25, 0.00, 0.50, 1.00, role="hero", capacity=2),
            _zone("right_rail", 0.77, 0.00, 0.23, 1.00, capacity=3),
        ),
        ("hero", "visual_focus"),
        ("visual_heavy", "balanced"),
    ),
    LayoutFamily(
        "top_hero_bottom_grid",
        "Top hero with bottom grid",
        "A full-width finding or figure followed by a modular evidence grid.",
        (
            _zone("top_hero", 0.00, 0.00, 1.00, 0.40, role="hero"),
            _zone("bottom_left", 0.00, 0.43, 0.32, 0.57, capacity=2),
            _zone("bottom_middle", 0.34, 0.43, 0.32, 0.57, capacity=2),
            _zone("bottom_right", 0.68, 0.43, 0.32, 0.57, capacity=2),
        ),
        ("hero", "grid", "result_first"),
        ("visual_heavy", "balanced"),
    ),
    LayoutFamily(
        "horizontal_narrative_bands",
        "Horizontal narrative bands",
        "Full-width bands express a strong top-to-bottom scientific story.",
        tuple(
            _zone(f"band_{index + 1}", 0.00, index * 0.255, 1.00, 0.235, capacity=2)
            for index in range(4)
        ),
        ("sequence", "wide_content", "narrative"),
        ("text_heavy", "balanced"),
    ),
    LayoutFamily(
        "method_flow_spine",
        "Method flow spine",
        "A central process spine with evidence and interpretation on both sides.",
        (
            _zone("left_top", 0.00, 0.00, 0.29, 0.48, capacity=2),
            _zone("left_bottom", 0.00, 0.52, 0.29, 0.48, capacity=2),
            _zone("flow_spine", 0.32, 0.00, 0.36, 1.00, role="hero", capacity=2),
            _zone("right_top", 0.71, 0.00, 0.29, 0.48, capacity=2),
            _zone("right_bottom", 0.71, 0.52, 0.29, 0.48, capacity=2),
        ),
        ("process", "sequence", "method"),
        ("method_heavy",),
    ),
    LayoutFamily(
        "comparison_split",
        "Comparison split",
        "Aligned left/right comparison fields with a shared conclusion band.",
        (
            _zone("comparison_a", 0.00, 0.00, 0.49, 0.77, capacity=3),
            _zone("comparison_b", 0.51, 0.00, 0.49, 0.77, capacity=3),
            _zone("shared_conclusion", 0.00, 0.80, 1.00, 0.20, role="conclusion", capacity=2),
        ),
        ("comparison", "symmetry", "shared_conclusion"),
        ("comparison",),
    ),
    LayoutFamily(
        "result_dashboard_cards",
        "Result dashboard cards",
        "A primary result plus compact, aligned secondary result cards.",
        (
            _zone("primary_result", 0.00, 0.00, 0.58, 0.62, role="hero", capacity=2),
            _zone("context", 0.61, 0.00, 0.39, 0.29, capacity=1),
            _zone("method", 0.61, 0.33, 0.39, 0.29, capacity=1),
            _zone("result_card_1", 0.00, 0.66, 0.32, 0.34, capacity=1),
            _zone("result_card_2", 0.34, 0.66, 0.32, 0.34, capacity=1),
            _zone("result_card_3", 0.68, 0.66, 0.32, 0.34, capacity=1),
        ),
        ("results", "cards", "hero"),
        ("visual_heavy", "results_heavy"),
    ),
    LayoutFamily(
        "small_multiples_matrix",
        "Small-multiples matrix",
        "A regular matrix for several equally important figures or findings.",
        tuple(
            _zone(
                f"cell_{row + 1}_{column + 1}",
                column * 0.34,
                row * 0.51,
                0.32,
                0.49,
                capacity=1,
            )
            for row in range(2)
            for column in range(3)
        ),
        ("grid", "small_multiples", "results"),
        ("visual_heavy",),
    ),
    LayoutFamily(
        "timeline_stage_narrative",
        "Timeline or stage narrative",
        "Ordered stages progress horizontally across the poster.",
        tuple(
            _zone(f"stage_{index + 1}", index * 0.255, 0.00, 0.235, 1.00, capacity=2)
            for index in range(4)
        ),
        ("timeline", "sequence", "stages"),
        ("timeline", "method_heavy"),
    ),
    LayoutFamily(
        "modular_editorial_mosaic",
        "Modular editorial mosaic",
        "A bounded large/medium/small editorial composition for uneven content.",
        (
            _zone("lead", 0.00, 0.00, 0.49, 0.58, role="hero", capacity=2),
            _zone("upper_right", 0.51, 0.00, 0.49, 0.28, capacity=1),
            _zone("middle_right", 0.51, 0.30, 0.49, 0.28, capacity=1),
            _zone("lower_left", 0.00, 0.61, 0.32, 0.39, capacity=1),
            _zone("lower_middle", 0.34, 0.61, 0.32, 0.39, capacity=1),
            _zone("lower_right", 0.68, 0.61, 0.32, 0.39, capacity=1),
        ),
        ("editorial", "mosaic", "asymmetric"),
        ("balanced", "visual_heavy"),
    ),
)


class LayoutFamilyRegistry:
    """Registry, applicability rules, and anti-dominance family selection."""

    def __init__(self, families: Iterable[LayoutFamily] = FAMILIES) -> None:
        self._families = {family.family_id: family for family in families}
        if "classic_three_column" not in self._families:
            raise ValueError("classic_three_column must remain registered")

    def all(self) -> List[LayoutFamily]:
        return list(self._families.values())

    def get(self, family_id: str) -> LayoutFamily:
        return self._families.get(family_id) or self._families["classic_three_column"]

    def ids(self) -> List[str]:
        return list(self._families)

    def compatible_ids(self, profile: Dict[str, Any]) -> List[str]:
        flags = set(profile.get("design_flags") or [])
        kind = str(profile.get("kind") or "balanced")
        compatible: List[str] = []
        for family in self.all():
            preferred = set(family.preferred_profiles)
            if family.family_id == "comparison_split" and "comparison" not in flags:
                continue
            if family.family_id == "timeline_stage_narrative" and not flags.intersection({"timeline", "stages"}):
                continue
            if family.family_id == "method_flow_spine" and not flags.intersection({"process", "method_heavy"}):
                continue
            if not preferred or kind in preferred or flags.intersection(preferred):
                compatible.append(family.family_id)
            else:
                # Keep broad controlled exploration open unless the family has
                # a semantic precondition handled above.
                compatible.append(family.family_id)
        return compatible or ["classic_three_column"]

    def choose(
        self,
        profile: Dict[str, Any],
        family_counts: Dict[str, int],
        *,
        random_seed: int,
        exclude: Optional[Iterable[str]] = None,
    ) -> str:
        excluded = set(exclude or [])
        candidates = [
            family_id
            for family_id in self.compatible_ids(profile)
            if family_id not in excluded
        ] or self.compatible_ids(profile)
        minimum = min(int(family_counts.get(item, 0)) for item in candidates)
        least_used = [
            item for item in candidates if int(family_counts.get(item, 0)) == minimum
        ]
        return random.Random(random_seed).choice(sorted(least_used))


class LayoutArchitect:
    """Create a content-safe LayoutSpec from a registered family."""

    def __init__(self, registry: Optional[LayoutFamilyRegistry] = None) -> None:
        self.registry = registry or LayoutFamilyRegistry()

    def build(
        self,
        state: Dict[str, Any],
        family_id: str,
        *,
        random_seed: int = 0,
    ) -> Dict[str, Any]:
        family = self.registry.get(family_id)
        board = state.get("optimized_story_board") or state.get("story_board") or {}
        sections = list(board.get("spatial_content_plan", {}).get("sections", []))
        zones = [dict(zone) for zone in family.zones]

        # A visual-rich/high-importance section should receive the primary
        # anchor when a family has one.  Remaining order is deterministic but
        # seed-sensitive so repeated exploration does not fossilize.
        def importance(section: Dict[str, Any]) -> tuple:
            return (
                len(section.get("visual_assets") or []),
                -int(section.get("importance_level", 2)),
                len(section.get("claim_ids") or []),
                str(section.get("section_id", "")),
            )

        ordered = sorted(sections, key=importance, reverse=True)
        rng = random.Random(random_seed)
        non_primary = ordered[1:]
        rng.shuffle(non_primary)
        ordered = ordered[:1] + non_primary if ordered else []

        assignments = {zone["zone_id"]: [] for zone in zones}
        hero = next((zone for zone in zones if zone.get("role") == "hero"), None)
        if hero and ordered:
            assignments[hero["zone_id"]].append(str(ordered.pop(0).get("section_id")))

        placement_zones = [zone for zone in zones if zone is not hero] + ([hero] if hero else [])
        cursor = 0
        for section in ordered:
            available = [
                zone for zone in placement_zones
                if len(assignments[zone["zone_id"]]) < int(zone.get("capacity", 1))
            ]
            target = (available or placement_zones)[cursor % len(available or placement_zones)]
            assignments[target["zone_id"]].append(str(section.get("section_id")))
            cursor += 1

        for zone in zones:
            zone["section_ids"] = assignments[zone["zone_id"]]

        canonical = "|".join(
            f"{zone['zone_id']}:{','.join(zone['section_ids'])}" for zone in zones
        )
        return {
            "schema_version": LAYOUT_ENGINE_SCHEMA_VERSION,
            "family_id": family.family_id,
            "family_label": family.label,
            "family_description": family.description,
            "zones": zones,
            "reading_order": [
                section_id
                for zone in zones
                for section_id in zone.get("section_ids", [])
            ],
            "primary_anchor_zone": hero.get("zone_id") if hero else None,
            "constraints": {
                "normalized_bounds": True,
                "overlap_forbidden": True,
                "copy_template_coordinates_forbidden": True,
            },
            "variant_id": hashlib.sha256(
                f"{family.family_id}:{random_seed}:{canonical}".encode("utf-8")
            ).hexdigest()[:16],
        }


def compile_layout(
    agent: Any,
    story_board: Dict[str, Any],
    state: Dict[str, Any],
    layout_spec: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Compile normalized zones with existing exact text/visual measurement."""

    poster_width = float(state["poster_width"])
    poster_height = float(state["poster_height"])
    effective_height = poster_height - 2 * agent.poster_margin
    title_region_height = effective_height * agent.title_height_fraction
    body_x = agent.poster_margin
    body_y = agent.poster_margin + title_region_height
    body_width = poster_width - 2 * agent.poster_margin
    body_height = effective_height - title_region_height

    elements: List[Dict[str, Any]] = []
    title = agent._create_title_element(state, poster_width, title_region_height)
    if title:
        elements.append(title)
    elements.extend(agent._create_logo_elements(state, poster_width, title_region_height))

    sections = {
        str(section.get("section_id")): deepcopy(section)
        for section in story_board.get("spatial_content_plan", {}).get("sections", [])
        if isinstance(section, dict) and section.get("section_id")
    }
    gap = agent._inter_section_spacing(state)
    for zone in layout_spec.get("zones", []):
        zone_x = body_x + float(zone.get("x", 0.0)) * body_width
        zone_y = body_y + float(zone.get("y", 0.0)) * body_height
        zone_width = max(0.5, float(zone.get("width", 0.0)) * body_width)
        zone_height = max(0.5, float(zone.get("height", 0.0)) * body_height)
        current_y = zone_y
        for index, section_id in enumerate(zone.get("section_ids", [])):
            section = sections.pop(str(section_id), None)
            if not section:
                continue
            section["layout_zone_id"] = zone.get("zone_id")
            section_elements = agent._create_section_elements(
                section,
                zone_x,
                current_y,
                zone_width,
                state,
                zone_height,
            )
            bottom = max(
                (float(item["y"]) + float(item["height"]) for item in section_elements),
                default=current_y,
            )
            section_height = max(0.1, bottom - current_y)
            elements.append({
                "type": "section_container",
                "x": zone_x,
                "y": current_y,
                "width": zone_width,
                "height": section_height,
                "section_id": section_id,
                "zone_id": zone.get("zone_id"),
                "layout_family": layout_spec.get("family_id"),
                "planned_zone_height": zone_height,
                "importance_level": section.get("importance_level", 2),
                "priority": 0.1,
            })
            elements.extend(section_elements)
            current_y = bottom + (gap if index < len(zone.get("section_ids", [])) - 1 else 0.0)

    # Fail closed on assignment omissions: retain the grounded content in the
    # last zone instead of silently dropping it.
    if sections and layout_spec.get("zones"):
        fallback = layout_spec["zones"][-1]
        fallback_x = body_x + float(fallback.get("x", 0.0)) * body_width
        fallback_y = body_y + float(fallback.get("y", 0.0)) * body_height
        fallback_width = max(0.5, float(fallback.get("width", 0.0)) * body_width)
        current_y = max(
            [
                float(item["y"]) + float(item["height"])
                for item in elements
                if item.get("type") == "section_container"
                and item.get("zone_id") == fallback.get("zone_id")
            ]
            or [fallback_y]
        )
        for section_id, section in sections.items():
            current_y += gap
            section_elements = agent._create_section_elements(
                section, fallback_x, current_y, fallback_width, state, body_height
            )
            bottom = max(
                (float(item["y"]) + float(item["height"]) for item in section_elements),
                default=current_y,
            )
            elements.append({
                "type": "section_container",
                "x": fallback_x,
                "y": current_y,
                "width": fallback_width,
                "height": max(0.1, bottom - current_y),
                "section_id": section_id,
                "zone_id": fallback.get("zone_id"),
                "layout_family": layout_spec.get("family_id"),
                "planned_zone_height": body_height * float(fallback.get("height", 1.0)),
                "importance_level": section.get("importance_level", 2),
                "priority": 0.1,
            })
            elements.extend(section_elements)
            current_y = bottom
    return elements


def analyze_regions(
    layout_data: Sequence[Dict[str, Any]],
    layout_spec: Dict[str, Any],
    state: Dict[str, Any],
    *,
    poster_margin: float,
    title_height_fraction: float,
) -> Dict[str, Any]:
    """Generalized replacement for legacy three-column utilization data."""

    poster_width = float(state["poster_width"])
    poster_height = float(state["poster_height"])
    effective_height = poster_height - 2 * poster_margin
    title_height = effective_height * title_height_fraction
    body_width = poster_width - 2 * poster_margin
    body_height = effective_height - title_height
    containers = [item for item in layout_data if item.get("type") == "section_container"]
    regions: Dict[str, Any] = {}
    for zone in layout_spec.get("zones", []):
        zone_id = str(zone.get("zone_id"))
        zone_area = max(
            0.001,
            float(zone.get("width", 0.0)) * body_width
            * float(zone.get("height", 0.0)) * body_height,
        )
        assigned = [item for item in containers if item.get("zone_id") == zone_id]
        used_area = sum(
            max(0.0, float(item.get("width", 0.0)) * float(item.get("height", 0.0)))
            for item in assigned
        )
        regions[zone_id] = {
            "utilization_rate": used_area / zone_area,
            "used_area": used_area,
            "available_area": zone_area,
            "section_ids": [item.get("section_id") for item in assigned],
            "status": "overflow" if used_area > zone_area else "underutilized" if used_area / zone_area < 0.65 else "balanced",
        }
    return {
        "analysis_kind": "layout_regions",
        "layout_family": layout_spec.get("family_id"),
        "available_height": body_height,
        "regions": regions,
        # Preserve the key for older observability consumers.  These are zones,
        # not assumed physical columns.
        "columns": regions,
    }
