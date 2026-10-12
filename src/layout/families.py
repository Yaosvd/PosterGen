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

from src.layout.family_selection import (
    FamilySelectionExhausted, make_family_selection_policy, profile_identity,
    semantic_match, validate_family_selection_policy,
)


LAYOUT_ENGINE_SCHEMA_VERSION = 3


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


def valid_family_topology(
    family: LayoutFamily,
    zones: Sequence[Dict[str, Any]],
) -> bool:
    """Accept bounded family grammar mutations, including split and span zones."""

    if not zones or len(zones) > 18:
        return False
    source = {str(zone["zone_id"]): zone for zone in family.zones}
    required = {
        "classic_three_column": {"left", "middle", "right"},
        "method_flow_spine": {"flow_spine"},
        "comparison_split": {"comparison_a", "comparison_b"},
        "result_dashboard_cards": {"primary_result"},
        "top_hero_bottom_grid": {"top_hero"},
        "central_hero_side_rails": {"central_hero"},
        "modular_editorial_mosaic": {"lead"},
    }.get(family.family_id, set())
    identifiers = set()
    for zone in zones:
        zone_id = str(zone.get("zone_id") or "")
        base_id = zone_id.removesuffix("__lower")
        if not zone_id or zone_id in identifiers or base_id not in source:
            return False
        identifiers.add(zone_id)
        try:
            x, y, width, height = (
                float(zone[key]) for key in ("x", "y", "width", "height")
            )
            capacity = int(zone.get("capacity", 1))
        except (KeyError, TypeError, ValueError):
            return False
        if (
            x < -1e-6 or y < -1e-6
            or width < 0.10 or height < 0.10
            or x + width > 1.000001
            or y + height > 1.000001
            or capacity < 1
        ):
            return False
        if zone_id in required and zone.get("role") != source[zone_id].get("role"):
            return False
    if not required.issubset(identifiers):
        return False
    if family.family_id == "classic_three_column" and identifiers != required:
        return False
    for index, left in enumerate(zones):
        for right in zones[index + 1:]:
            horizontal = min(
                float(left["x"]) + float(left["width"]),
                float(right["x"]) + float(right["width"]),
            ) - max(float(left["x"]), float(right["x"]))
            vertical = min(
                float(left["y"]) + float(left["height"]),
                float(right["y"]) + float(right["height"]),
            ) - max(float(left["y"]), float(right["y"]))
            if horizontal > 1e-6 and vertical > 1e-6:
                return False
    return True


class LayoutFamilyRegistry:
    """Registry, applicability rules, and anti-dominance family selection."""

    def __init__(self, families: Iterable[LayoutFamily] = FAMILIES) -> None:
        self._families = {family.family_id: family for family in families}
        if "classic_three_column" not in self._families:
            raise ValueError("classic_three_column must remain registered")

    def all(self) -> List[LayoutFamily]:
        return list(self._families.values())

    def get(self, family_id: str) -> LayoutFamily:
        try:
            return self._families[family_id]
        except KeyError as exc:
            raise ValueError(f"unknown layout family: {family_id}") from exc

    def ids(self) -> List[str]:
        return list(self._families)

    def compatible_ids(self, profile: Dict[str, Any]) -> List[str]:
        """All registered grammars are explorable, even with unknown semantics."""
        return self.ids()

    def choose(
        self,
        profile: Dict[str, Any],
        family_counts: Dict[str, int],
        *,
        random_seed: int,
        exclude: Optional[Iterable[str]] = None,
        policy: Optional[Dict[str, Any]] = None,
    ) -> str:
        family_id, _ = self.choose_with_report(
            profile, family_counts, random_seed=random_seed, exclude=exclude,
            policy=policy,
        )
        return family_id

    def choose_with_report(
        self, profile, family_counts, *, random_seed, exclude=None, policy=None,
    ):
        policy = (
            make_family_selection_policy({}, self.ids()) if policy is None
            else validate_family_selection_policy(policy, self.ids())
        )
        excluded = set(exclude or [])
        enabled = sorted(policy["enabled_families"])
        candidates = [item for item in enabled if item not in excluded]
        counts = {item: int(family_counts.get(item, 0)) for item in enabled}
        if any(value < 0 for value in counts.values()):
            raise ValueError("Family use counts cannot be negative")
        scores = {}
        for item in enabled:
            strength, matches = semantic_match(self.get(item), profile)
            scores[item] = {"match_strength": strength, "matches": matches,
                            "weight": 1.0 + policy["semantic_bonus_max"] * strength}
        report = {
            "schema_version": 1, "policy": policy,
            "paper_profile": profile_identity(profile), "random_seed": random_seed,
            "enabled_families": enabled, "available_families": candidates,
            "excluded_families": sorted(excluded.intersection(enabled)),
            "exclusion_reason": "current_iteration_layout_failure",
            "family_use_counts": counts, "semantic_scores": scores,
            "least_used_candidates": [], "selected_family": None,
            "status": "exhausted" if not candidates else "selected",
        }
        if not candidates:
            raise FamilySelectionExhausted(report)
        minimum = min(counts[item] for item in candidates)
        least_used = [
            item for item in candidates if counts[item] == minimum
        ]
        selected = random.Random(random_seed).choices(
            least_used, weights=[scores[item]["weight"] for item in least_used], k=1,
        )[0]
        report.update({"least_used_candidates": least_used,
                       "selected_family": selected, "minimum_use_count": minimum})
        return selected, report


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
        zones_override: Optional[Sequence[Dict[str, Any]]] = None,
        assignments_override: Optional[Dict[str, Sequence[str]]] = None,
        variant_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        family = self.registry.get(family_id)
        board = state.get("optimized_story_board") or state.get("story_board") or {}
        sections = list(board.get("spatial_content_plan", {}).get("sections", []))
        topology = state.get("template_validation_topology") or {}
        if topology:
            if topology.get("family_id") != family.family_id:
                raise ValueError("Validation topology family mismatch")
            source_zones = topology.get("zones") or []
            if not valid_family_topology(family, source_zones):
                raise ValueError("Validation topology violates its family grammar")
            zones = [dict(zone) for zone in source_zones]
            for zone in zones:
                for key in ("x", "y", "width", "height"):
                    zone[key] = float(zone[key])
                if (zone["x"] < 0 or zone["y"] < 0 or zone["width"] <= 0
                        or zone["height"] <= 0 or zone["x"] + zone["width"] > 1.0001
                        or zone["y"] + zone["height"] > 1.0001):
                    raise ValueError("Validation topology has invalid geometry")
        elif zones_override is not None:
            zones = [dict(zone) for zone in zones_override]
            if not valid_family_topology(family, zones):
                raise ValueError("Layout variant violates its family grammar")
        else:
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

        assignments = {str(zone["zone_id"]): [] for zone in zones}
        anchor = topology.get("primary_anchor_zone") if topology else None
        hero = next((zone for zone in zones if zone.get("zone_id") == anchor), None) if anchor else next((zone for zone in zones if zone.get("role") == "hero"), None)
        if assignments_override is not None:
            assignments = {
                str(zone["zone_id"]): [
                    str(item)
                    for item in assignments_override.get(str(zone["zone_id"]), [])
                ]
                for zone in zones
            }
            assigned = [item for values in assignments.values() for item in values]
            expected = [str(item.get("section_id")) for item in sections]
            if len(assigned) != len(set(assigned)) or set(assigned) != set(expected):
                raise ValueError(
                    "Layout assignments must own every visible section exactly once"
                )
            for zone in zones:
                zone_id = str(zone["zone_id"])
                if len(assignments[zone_id]) > int(zone.get("capacity", 1)):
                    raise ValueError(f"Zone {zone_id} exceeds its section capacity")
        else:
            if hero and ordered:
                assignments[hero["zone_id"]].append(str(ordered.pop(0).get("section_id")))

            placement_zones = [zone for zone in zones if zone is not hero] + ([hero] if hero else [])
            cursor = 0
            for section in ordered:
                available = [
                    zone for zone in placement_zones
                    if len(assignments[zone["zone_id"]]) < int(zone.get("capacity", 1))
                ]
                # Generic specs remain backward compatible for inspection.
                # Production non-classic compilation supplies strict,
                # physically measured assignments_override from the
                # feasibility solver.
                target_pool = available or placement_zones
                target = target_pool[cursor % len(target_pool)]
                assignments[target["zone_id"]].append(str(section.get("section_id")))
                cursor += 1

        for zone in zones:
            zone["section_ids"] = assignments[zone["zone_id"]]

        canonical = "|".join(
            f"{zone['zone_id']}:{','.join(zone['section_ids'])}" for zone in zones
        )
        metadata = dict(variant_metadata or {})
        variant_id = metadata.get("variant_id") or hashlib.sha256(
            f"{family.family_id}:{random_seed}:{canonical}".encode("utf-8")
        ).hexdigest()[:16]
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
            "variant_id": variant_id,
            "variant_label": metadata.get("variant_label", "canonical"),
            "geometry_fingerprint": metadata.get("geometry_fingerprint", ""),
            "generation_method": metadata.get("generation_method", "seed_grammar"),
            "mutation_trace": list(metadata.get("mutation_trace") or []),
            "iteration_random_seed": int(metadata.get("iteration_random_seed", random_seed)),
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
            if bottom > zone_y + zone_height + 0.01:
                raise ValueError(
                    f"Section {section_id} exceeds layout zone {zone.get('zone_id')}"
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

    if sections:
        raise ValueError(
            "LayoutSpec omitted grounded sections: " + ", ".join(sorted(sections))
        )
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
