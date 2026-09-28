"""Capacity-aware, content-grounded layout-family exploration.

The layout model is intentionally split into two layers:

* a family grammar supplies bounded normalized zones; and
* this module searches safe geometry/content assignments for one paper.

No model-supplied coordinates or scientific prose are accepted here.  Every
visible sentence is copied from the grounded story board. Search uses a
conservative font-aware estimate; the selected candidate is then compiled by
the renderer-facing LayoutAgent and must pass exact fail-closed preflight.
"""

from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.layout.families import LayoutArchitect, LayoutFamily, LayoutFamilyRegistry
from src.layout.text_height_measurement import estimate_wrapped_line_count


FIT_SCHEMA_VERSION = 1


class LayoutFeasibilityError(ValueError):
    """Raised when no bounded layout can be compiled for a candidate."""


def _fingerprint(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


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
        "x": round(float(x), 6),
        "y": round(float(y), 6),
        "width": round(float(width), 6),
        "height": round(float(height), 6),
        "role": role,
        "capacity": max(1, int(capacity)),
    }


def _valid_zones(zones: Sequence[Dict[str, Any]]) -> bool:
    identifiers = set()
    for item in zones:
        zone_id = str(item.get("zone_id") or "")
        try:
            x, y, width, height = (
                float(item[key]) for key in ("x", "y", "width", "height")
            )
        except (KeyError, TypeError, ValueError):
            return False
        if (
            not zone_id
            or zone_id in identifiers
            or x < -1e-6
            or y < -1e-6
            or width <= 0
            or height <= 0
            or x + width > 1.000001
            or y + height > 1.000001
        ):
            return False
        identifiers.add(zone_id)
    for index, left in enumerate(zones):
        for right in zones[index + 1 :]:
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


def _mirror(zones: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = deepcopy(list(zones))
    for item in result:
        item["x"] = round(
            1.0 - float(item["x"]) - float(item["width"]), 6
        )
    return result


def _weighted_columns(
    identifiers: Sequence[str],
    weights: Sequence[float],
    *,
    gap: float,
    y: float = 0.0,
    height: float = 1.0,
    roles: Optional[Dict[str, str]] = None,
    capacities: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    usable = 1.0 - gap * max(0, len(weights) - 1)
    total = sum(float(item) for item in weights)
    cursor = 0.0
    result = []
    for identifier, weight in zip(identifiers, weights):
        width = usable * float(weight) / total
        result.append(_zone(
            identifier,
            cursor,
            y,
            width,
            height,
            role=(roles or {}).get(identifier, "support"),
            capacity=(capacities or {}).get(identifier, 1),
        ))
        cursor += width + gap
    return result


def generate_zone_variants(
    family: LayoutFamily,
    *,
    random_seed: int,
    maximum: int = 24,
) -> List[Dict[str, Any]]:
    """Generate bounded family variants without accepting raw model geometry."""

    canonical = [dict(item) for item in family.zones]
    candidates: List[Tuple[str, List[Dict[str, Any]], List[str]]] = [
        ("canonical", canonical, [])
    ]
    family_id = family.family_id

    if family_id in {"classic_three_column", "asymmetric_two_column"}:
        if family_id == "classic_three_column":
            identifiers = ("left", "middle", "right")
            capacities = {item: 4 for item in identifiers}
            for name, weights in (
                ("left_emphasis", (1.18, 0.91, 0.91)),
                ("center_emphasis", (0.91, 1.18, 0.91)),
                ("right_emphasis", (0.91, 0.91, 1.18)),
            ):
                candidates.append((
                    name,
                    _weighted_columns(
                        identifiers, weights, gap=0.02, capacities=capacities
                    ),
                    ["resize_shared_boundaries"],
                ))
        else:
            for narrow in (0.26, 0.31, 0.36, 0.41):
                gap = 0.03
                candidates.append((
                    f"rail_{int(narrow * 100)}",
                    [
                        _zone(
                            "narrative_rail", 0.0, 0.0, narrow, 1.0,
                            capacity=4,
                        ),
                        _zone(
                            "evidence_field", narrow + gap, 0.0,
                            1.0 - narrow - gap, 1.0,
                            role="hero", capacity=5,
                        ),
                    ],
                    ["resize_shared_boundary"],
                ))

    elif family_id == "central_hero_side_rails":
        for side in (0.19, 0.23, 0.27):
            gap = 0.02
            center = 1.0 - 2 * side - 2 * gap
            candidates.append((
                f"center_{int(center * 100)}",
                [
                    _zone("left_rail", 0.0, 0.0, side, 1.0, capacity=3),
                    _zone(
                        "central_hero", side + gap, 0.0, center, 1.0,
                        role="hero", capacity=2,
                    ),
                    _zone(
                        "right_rail", side + gap + center + gap, 0.0,
                        side, 1.0, capacity=3,
                    ),
                ],
                ["resize_shared_boundaries"],
            ))

    elif family_id == "top_hero_bottom_grid":
        for hero_height in (0.30, 0.36, 0.42, 0.48):
            vertical_gap = 0.03
            bottom_y = hero_height + vertical_gap
            bottom_height = 1.0 - bottom_y
            for weights in ((1.0, 1.0, 1.0), (1.2, 0.9, 0.9), (0.9, 0.9, 1.2)):
                bottom = _weighted_columns(
                    ("bottom_left", "bottom_middle", "bottom_right"),
                    weights,
                    gap=0.02,
                    y=bottom_y,
                    height=bottom_height,
                    capacities={
                        "bottom_left": 2,
                        "bottom_middle": 2,
                        "bottom_right": 2,
                    },
                )
                candidates.append((
                    f"hero_{int(hero_height * 100)}_{_fingerprint(weights)[:4]}",
                    [
                        _zone(
                            "top_hero", 0.0, 0.0, 1.0, hero_height,
                            role="hero", capacity=1,
                        ),
                        *bottom,
                    ],
                    ["resize_hero", "redistribute_bottom_grid"],
                ))

    elif family_id == "horizontal_narrative_bands":
        gap = 0.02
        patterns = (
            (1.0, 1.0, 1.0, 1.0),
            (0.8, 1.1, 1.3, 0.8),
            (0.8, 1.35, 1.0, 0.85),
            (0.75, 1.0, 1.0, 1.25),
        )
        usable = 1.0 - gap * 3
        for pattern in patterns:
            cursor = 0.0
            total = sum(pattern)
            zones = []
            for index, weight in enumerate(pattern):
                height = usable * weight / total
                zones.append(_zone(
                    f"band_{index + 1}", 0.0, cursor, 1.0, height,
                    capacity=2,
                ))
                cursor += height + gap
            candidates.append((
                f"bands_{_fingerprint(pattern)[:6]}", zones,
                ["redistribute_band_heights"],
            ))

    elif family_id == "comparison_split":
        for comparison_height in (0.68, 0.75, 0.82):
            gap = 0.03
            candidates.append((
                f"comparison_{int(comparison_height * 100)}",
                [
                    _zone(
                        "comparison_a", 0.0, 0.0, 0.49,
                        comparison_height, capacity=3,
                    ),
                    _zone(
                        "comparison_b", 0.51, 0.0, 0.49,
                        comparison_height, capacity=3,
                    ),
                    _zone(
                        "shared_conclusion", 0.0,
                        comparison_height + gap, 1.0,
                        1.0 - comparison_height - gap,
                        role="conclusion", capacity=2,
                    ),
                ],
                ["resize_comparison_band"],
            ))

    elif family_id in {
        "four_column_modular", "timeline_stage_narrative"
    }:
        identifiers = (
            tuple(f"column_{index + 1}" for index in range(4))
            if family_id == "four_column_modular"
            else tuple(f"stage_{index + 1}" for index in range(4))
        )
        capacity = 3 if family_id == "four_column_modular" else 2
        capacities = {item: capacity for item in identifiers}
        for name, weights in (
            ("balanced", (1.0, 1.0, 1.0, 1.0)),
            ("opening_emphasis", (1.25, 0.95, 0.90, 0.90)),
            ("center_emphasis", (0.90, 1.10, 1.10, 0.90)),
            ("closing_emphasis", (0.90, 0.90, 0.95, 1.25)),
        ):
            candidates.append((
                name,
                _weighted_columns(
                    identifiers, weights, gap=0.018,
                    capacities=capacities,
                ),
                ["redistribute_column_widths"],
            ))

    elif family_id == "method_flow_spine":
        for spine_width in (0.30, 0.36, 0.42):
            gap = 0.025
            rail_width = (1.0 - spine_width - 2 * gap) / 2
            for upper_height in (0.44, 0.50, 0.56):
                vertical_gap = 0.03
                lower_y = upper_height + vertical_gap
                lower_height = 1.0 - lower_y
                candidates.append((
                    f"spine_{int(spine_width * 100)}_split_{int(upper_height * 100)}",
                    [
                        _zone(
                            "left_top", 0.0, 0.0, rail_width,
                            upper_height, capacity=2,
                        ),
                        _zone(
                            "left_bottom", 0.0, lower_y, rail_width,
                            lower_height, capacity=2,
                        ),
                        _zone(
                            "flow_spine", rail_width + gap, 0.0,
                            spine_width, 1.0, role="hero", capacity=2,
                        ),
                        _zone(
                            "right_top", rail_width + gap + spine_width + gap,
                            0.0, rail_width, upper_height, capacity=2,
                        ),
                        _zone(
                            "right_bottom",
                            rail_width + gap + spine_width + gap,
                            lower_y, rail_width, lower_height, capacity=2,
                        ),
                    ],
                    ["resize_spine", "redistribute_rail_rows"],
                ))

    elif family_id == "result_dashboard_cards":
        for hero_width in (0.52, 0.58, 0.64):
            horizontal_gap = 0.025
            side_x = hero_width + horizontal_gap
            side_width = 1.0 - side_x
            for upper_height in (0.56, 0.62, 0.68):
                row_gap = 0.025
                bottom_y = upper_height + row_gap
                bottom_height = 1.0 - bottom_y
                side_row_height = (upper_height - row_gap) / 2
                bottom = _weighted_columns(
                    ("result_card_1", "result_card_2", "result_card_3"),
                    (1.0, 1.0, 1.0), gap=0.02,
                    y=bottom_y, height=bottom_height,
                    capacities={
                        "result_card_1": 1,
                        "result_card_2": 1,
                        "result_card_3": 1,
                    },
                )
                candidates.append((
                    f"dashboard_{int(hero_width * 100)}_{int(upper_height * 100)}",
                    [
                        _zone(
                            "primary_result", 0.0, 0.0, hero_width,
                            upper_height, role="hero", capacity=2,
                        ),
                        _zone(
                            "context", side_x, 0.0, side_width,
                            side_row_height, capacity=1,
                        ),
                        _zone(
                            "method", side_x, side_row_height + row_gap,
                            side_width, side_row_height, capacity=1,
                        ),
                        *bottom,
                    ],
                    ["resize_primary_result", "redistribute_dashboard_rows"],
                ))

    elif family_id == "small_multiples_matrix":
        horizontal_gap = 0.02
        vertical_gap = 0.025
        for column_weights in (
            (1.0, 1.0, 1.0),
            (1.15, 0.95, 0.90),
            (0.90, 0.95, 1.15),
        ):
            widths = _weighted_columns(
                ("c1", "c2", "c3"), column_weights,
                gap=horizontal_gap,
            )
            for top_fraction in (0.45, 0.50, 0.55):
                zones = []
                for row in range(2):
                    y = 0.0 if row == 0 else top_fraction + vertical_gap
                    height = (
                        top_fraction if row == 0
                        else 1.0 - top_fraction - vertical_gap
                    )
                    for column, geometry in enumerate(widths):
                        zones.append(_zone(
                            f"cell_{row + 1}_{column + 1}",
                            geometry["x"], y, geometry["width"], height,
                            capacity=1,
                        ))
                candidates.append((
                    f"matrix_{_fingerprint(column_weights)[:4]}_{int(top_fraction * 100)}",
                    zones,
                    ["redistribute_matrix_columns", "redistribute_matrix_rows"],
                ))

    elif family_id == "modular_editorial_mosaic":
        for lead_width in (0.44, 0.50, 0.56):
            gap = 0.025
            right_x = lead_width + gap
            right_width = 1.0 - right_x
            for lead_height in (0.53, 0.59, 0.65):
                bottom_y = lead_height + gap
                bottom_height = 1.0 - bottom_y
                upper_gap = 0.02
                right_height = (lead_height - upper_gap) / 2
                bottom = _weighted_columns(
                    ("lower_left", "lower_middle", "lower_right"),
                    (1.0, 1.0, 1.0), gap=0.02,
                    y=bottom_y, height=bottom_height,
                    capacities={
                        "lower_left": 1,
                        "lower_middle": 1,
                        "lower_right": 1,
                    },
                )
                candidates.append((
                    f"mosaic_{int(lead_width * 100)}_{int(lead_height * 100)}",
                    [
                        _zone(
                            "lead", 0.0, 0.0, lead_width, lead_height,
                            role="hero", capacity=2,
                        ),
                        _zone(
                            "upper_right", right_x, 0.0, right_width,
                            right_height, capacity=1,
                        ),
                        _zone(
                            "middle_right", right_x,
                            right_height + upper_gap, right_width,
                            right_height, capacity=1,
                        ),
                        *bottom,
                    ],
                    ["resize_editorial_lead", "redistribute_mosaic_rows"],
                ))

    # Mirroring is a safe topology-preserving mutation for every asymmetric
    # grammar.  Symmetric candidates are removed by the fingerprint deduper.
    base_for_mirror = list(candidates)
    for name, zones, trace in base_for_mirror:
        candidates.append((
            f"{name}_mirror", _mirror(zones), [*trace, "mirror_layout"]
        ))

    unique: Dict[str, Dict[str, Any]] = {}
    for name, zones, trace in candidates:
        if not _valid_zones(zones):
            continue
        geometry = [
            {
                key: item.get(key)
                for key in (
                    "zone_id", "x", "y", "width", "height", "role",
                    "capacity",
                )
            }
            for item in zones
        ]
        geometry_fingerprint = _fingerprint(geometry)
        unique.setdefault(geometry_fingerprint, {
            "variant_id": f"{family_id}_{geometry_fingerprint}",
            "variant_label": name,
            "geometry_fingerprint": geometry_fingerprint,
            "zones": zones,
            "mutation_trace": trace,
        })

    variants = list(unique.values())
    if len(variants) > 1:
        canonical_variant = variants[0]
        remainder = variants[1:]
        random.Random(random_seed).shuffle(remainder)
        variants = [canonical_variant, *remainder]
    return variants[: max(1, int(maximum))]


def _section_priority(section: Dict[str, Any]) -> Tuple[int, int, int, str]:
    title = str(section.get("section_title") or "").lower()
    semantic = 2 if any(
        word in title for word in ("result", "conclusion", "finding")
    ) else 1 if any(word in title for word in ("method", "approach")) else 0
    vertical = {"top": 2, "middle": 1, "bottom": 0}.get(
        str(section.get("vertical_priority") or "middle"), 1
    )
    return (
        semantic,
        len(section.get("visual_assets") or []),
        vertical,
        str(section.get("section_id") or ""),
    )


def _estimate_section_height(
    agent: Any,
    section: Dict[str, Any],
    *,
    zone_width: float,
    zone_height: float,
    state: Dict[str, Any],
) -> float:
    """Fast conservative search estimate; final compilation remains exact."""

    # Test doubles and third-party LayoutAgent-compatible implementations may
    # expose only the exact method. Production LayoutAgent has the attributes
    # below and avoids calling expensive python-pptx fit_text during search.
    if not all(hasattr(agent, name) for name in (
        "config",
        "layout_constants",
        "body_text_font_family",
        "section_title_font_family",
    )):
        return float(agent._calculate_precise_section_height(
            section, zone_width, state, zone_height
        ))

    styling = state.get("styling_interfaces") or {}
    sizes = styling.get("font_sizes") or {}
    body_size = int(
        sizes.get(
            "body_text",
            agent.config["typography"]["sizes"]["body_text"],
        )
    )
    title_size = int(sizes.get("section_title", 64))
    factor = float(
        (state.get("critic_config") or {})
        .get("explore_layout", {})
        .get("fast_measurement_safety_factor", 1.20)
    )
    height = 0.0
    title = str(section.get("section_title") or "").strip()
    if title:
        title_padding = float(agent.layout_constants["title_padding"])
        title_width = max(
            0.1,
            zone_width
            - (2 * title_padding)
            - (title_size / 72),
        )
        title_lines = estimate_wrapped_line_count(
            title,
            title_width,
            agent.section_title_font_family,
            title_size,
            margins={
                "left": 0.10,
                "right": 0.10,
                "top": 0.05,
                "bottom": 0.05,
            },
            font_width_factor=float(
                agent.layout_constants.get(
                    "section_title_bold_width_factor", 1.1
                )
            ),
            render_width_factor=float(
                agent.layout_constants.get(
                    "section_title_render_width_factor", 0.98
                )
            ),
        )
        height += title_lines * title_size / 72 * 1.25
        height += float(
            agent.config["layout"]["title_to_content_spacing"]
        )

    visual_padding = float(
        agent.config["layout"]["text_padding"]["left_right"]
    )
    visual_width = max(0.1, zone_width - 2 * visual_padding)
    for visual in section.get("visual_assets") or []:
        visual_id = str(visual.get("visual_id") or "")
        if not visual_id:
            continue
        _, visual_height, _ = agent._calculate_visual_height(
            visual_id, visual_width, state, zone_height
        )
        height += float(visual_height)
        height += float(
            agent.config["layout"]["visual_spacing"]["below_visual"]
        )

    content = "\n".join(
        str(item).strip()
        for item in section.get("text_content") or []
        if str(item).strip()
    )
    if content:
        text_width = max(0.1, zone_width - 2 * visual_padding)
        body_lines = estimate_wrapped_line_count(
            content,
            text_width,
            agent.body_text_font_family,
            body_size,
            margins={
                "left": 0.10,
                "right": 0.10,
                "top": 0.05,
                "bottom": 0.05,
            },
            font_width_factor=1.03,
            render_width_factor=0.98,
        )
        # Include paragraph/newline reserve, textbox margins, emphasis buffer,
        # and the LayoutAgent's trailing text reserve.
        height += body_lines * body_size / 72 * 1.25
        height += content.count("\n") * body_size / 72 * 0.10
        height += 0.50

    return max(0.1, height * factor)


def _content_options(
    agent: Any,
    section: Dict[str, Any],
    *,
    zone_width: float,
    zone_height: float,
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    claim_ids = list(section.get("claim_ids") or [])
    text = list(section.get("text_content") or [])
    if not claim_ids or len(claim_ids) != len(text):
        return []
    visuals = list(section.get("visual_assets") or [])
    options = []
    visual_sets = [visuals]
    if visuals:
        visual_sets.append([])
    claim_count = len(claim_ids)
    counts = sorted({
        claim_count,
        max(1, round(claim_count * 0.6)),
        1,
    }, reverse=True)
    for selected_visuals in visual_sets:
        for count in counts:
            candidate = deepcopy(section)
            candidate["claim_ids"] = claim_ids[:count]
            candidate["text_content"] = text[:count]
            candidate["visual_assets"] = deepcopy(selected_visuals)
            height = _estimate_section_height(
                agent,
                candidate,
                zone_width=zone_width,
                zone_height=zone_height,
                state=state,
            )
            options.append({
                "section": candidate,
                "height": height,
                "retained_claims": count,
                "retained_visuals": len(selected_visuals),
            })
    options.sort(
        key=lambda item: (
            item["retained_claims"], item["retained_visuals"], -item["height"]
        ),
        reverse=True,
    )
    return options


def _fit_one_variant(
    agent: Any,
    board: Dict[str, Any],
    state: Dict[str, Any],
    family: LayoutFamily,
    variant: Dict[str, Any],
    settings: Dict[str, Any],
    measurement_cache: Dict[Tuple[Any, ...], List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    sections = [
        deepcopy(item)
        for item in board.get("spatial_content_plan", {}).get("sections", [])
        if isinstance(item, dict) and item.get("section_id")
        and item.get("claim_ids")
    ]
    if not sections:
        return None

    poster_width = float(state["poster_width"])
    poster_height = float(state["poster_height"])
    effective_height = poster_height - 2 * agent.poster_margin
    title_height = effective_height * agent.title_height_fraction
    body_width = poster_width - 2 * agent.poster_margin
    body_height = effective_height - title_height
    reserve = float(agent.layout_constants.get("body_render_reserve", 0.0))
    gap = float(agent._inter_section_spacing(state)) + reserve
    target = float(settings.get("planning_target", 0.975))
    hard_max = min(1.0, float(settings.get("maximum_utilization", 1.0)))
    beam_width = max(2, int(settings.get("beam_width", 4)))
    minimum_sections = min(
        len(sections), max(1, int(settings.get("minimum_sections", 5)))
    )

    zones = deepcopy(variant["zones"])
    zone_geometry = {}
    for item in zones:
        zone_geometry[str(item["zone_id"])] = {
            "width": max(0.5, float(item["width"]) * body_width),
            "height": max(0.5, float(item["height"]) * body_height),
            "capacity": max(1, int(item.get("capacity", 1))),
            "role": str(item.get("role") or "support"),
        }

    ordered = sorted(sections, key=_section_priority, reverse=True)
    total_claims = sum(len(item.get("claim_ids") or []) for item in ordered)
    total_visuals = sum(len(item.get("visual_assets") or []) for item in ordered)
    hero_id = next(
        (str(item["zone_id"]) for item in zones if item.get("role") == "hero"),
        None,
    )
    option_cache: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for section in ordered:
        section_id = str(section["section_id"])
        content_signature = _fingerprint({
            "claim_ids": section.get("claim_ids") or [],
            "text_content": section.get("text_content") or [],
            "visual_assets": section.get("visual_assets") or [],
            "section_title": section.get("section_title"),
        })
        for zone_id, geometry in zone_geometry.items():
            cache_key = (
                content_signature,
                round(float(geometry["width"]), 4),
                (
                    round(float(geometry["height"]), 4)
                    if section.get("visual_assets")
                    else None
                ),
            )
            if cache_key not in measurement_cache:
                measurement_cache[cache_key] = _content_options(
                    agent,
                    section,
                    zone_width=geometry["width"],
                    zone_height=geometry["height"],
                    state=state,
                )
            option_cache[(section_id, zone_id)] = measurement_cache[
                cache_key
            ]

    # Each beam state owns independent selected content and assignments.
    beam = [{
        "assignments": {str(item["zone_id"]): [] for item in zones},
        "heights": {str(item["zone_id"]): 0.0 for item in zones},
        "selected": [],
        "retained_claims": 0,
        "retained_visuals": 0,
        "dropped_sections": [],
    }]

    for section_index, section in enumerate(ordered):
        expanded = []
        section_id = str(section["section_id"])
        for partial in beam:
            for zone_id, geometry in zone_geometry.items():
                assigned = partial["assignments"][zone_id]
                if len(assigned) >= geometry["capacity"]:
                    continue
                for option in option_cache[(section_id, zone_id)]:
                    spacing = gap if assigned else 0.0
                    resulting = (
                        partial["heights"][zone_id]
                        + spacing
                        + float(option["height"])
                    )
                    if resulting > geometry["height"] * hard_max + 1e-6:
                        continue
                    candidate = deepcopy(partial)
                    candidate["assignments"][zone_id].append(section_id)
                    candidate["heights"][zone_id] = resulting
                    chosen = deepcopy(option["section"])
                    chosen["layout_zone_id"] = zone_id
                    candidate["selected"].append(chosen)
                    candidate["retained_claims"] += int(
                        option["retained_claims"]
                    )
                    candidate["retained_visuals"] += int(
                        option["retained_visuals"]
                    )
                    expanded.append(candidate)
            remaining = len(ordered) - section_index - 1
            if len(partial["selected"]) + remaining >= minimum_sections:
                candidate = deepcopy(partial)
                candidate["dropped_sections"].append(section_id)
                expanded.append(candidate)

        if not expanded:
            return None

        def partial_score(item: Dict[str, Any]) -> Tuple[float, float, float]:
            coverage = item["retained_claims"] / max(total_claims, 1)
            visual = item["retained_visuals"] / max(total_visuals, 1)
            utilizations = [
                item["heights"][zone_id] / geometry["height"]
                for zone_id, geometry in zone_geometry.items()
                if item["assignments"][zone_id]
            ]
            fit = -sum(abs(value - target) for value in utilizations)
            hero_bonus = 0.0
            if hero_id and item["assignments"].get(hero_id):
                hero_section = item["assignments"][hero_id][0]
                hero_bonus = 0.05 if hero_section == ordered[0]["section_id"] else 0.01
            return coverage + 0.1 * visual + hero_bonus, fit, -len(
                item["dropped_sections"]
            )

        expanded.sort(key=partial_score, reverse=True)
        beam = expanded[:beam_width]

    completed = [
        item for item in beam
        if len(item["selected"]) >= minimum_sections
        and (not hero_id or item["assignments"].get(hero_id))
    ]
    if not completed:
        return None

    def final_score(item: Dict[str, Any]) -> Tuple[float, float, float, str]:
        utilizations = {
            zone_id: item["heights"][zone_id] / geometry["height"]
            for zone_id, geometry in zone_geometry.items()
            if item["assignments"][zone_id]
        }
        coverage = item["retained_claims"] / max(total_claims, 1)
        fit = -sum(abs(value - target) for value in utilizations.values())
        balance = -(
            max(utilizations.values()) - min(utilizations.values())
            if len(utilizations) > 1 else 0.0
        )
        return coverage, fit, balance, variant["variant_id"]

    chosen = max(completed, key=final_score)
    selected_by_id = {
        str(item["section_id"]): item for item in chosen["selected"]
    }
    selected_sections = [
        selected_by_id[str(item["section_id"])]
        for item in sections
        if str(item["section_id"]) in selected_by_id
    ]
    assignments = {
        zone_id: list(section_ids)
        for zone_id, section_ids in chosen["assignments"].items()
    }
    selected_board = deepcopy(board)
    selected_board.setdefault("spatial_content_plan", {})["sections"] = (
        selected_sections
    )
    spec = LayoutArchitect().build(
        {
            **state,
            "story_board": selected_board,
            "optimized_story_board": selected_board,
        },
        family.family_id,
        random_seed=int(
            (state.get("iteration_context") or {}).get("random_seed", 0)
        ),
        zones_override=zones,
        assignments_override=assignments,
        variant_metadata=variant,
    )
    original_claims = {
        str(claim_id)
        for item in sections for claim_id in item.get("claim_ids", [])
    }
    retained_claim_ids = {
        str(claim_id)
        for item in selected_sections for claim_id in item.get("claim_ids", [])
    }
    original_visuals = {
        str(item.get("visual_id"))
        for section in sections for item in section.get("visual_assets", [])
        if item.get("visual_id")
    }
    retained_visual_ids = {
        str(item.get("visual_id"))
        for section in selected_sections
        for item in section.get("visual_assets", [])
        if item.get("visual_id")
    }
    utilizations = {
        zone_id: round(
            chosen["heights"][zone_id] / geometry["height"], 6
        )
        for zone_id, geometry in zone_geometry.items()
    }
    return {
        "board": selected_board,
        "layout_spec": spec,
        "variant": variant,
        "score": final_score(chosen),
        "utilization": utilizations,
        "max_physical_utilization": max(utilizations.values() or [0.0]),
        "candidate_content_selection": {
            "schema_version": 1,
            "visible_claim_ids": sorted(retained_claim_ids),
            "omitted_claim_ids": sorted(original_claims - retained_claim_ids),
            "visible_visual_ids": sorted(retained_visual_ids),
            "omitted_visual_ids": sorted(original_visuals - retained_visual_ids),
            "dropped_section_ids": sorted(chosen["dropped_sections"]),
            "reason": "family_capacity_fit",
        },
    }


def fit_family_layout(
    agent: Any,
    board: Dict[str, Any],
    state: Dict[str, Any],
    family_id: str,
    *,
    config: Optional[Dict[str, Any]] = None,
    fixed_zones: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Return a grounded board, LayoutSpec and auditable fit report."""

    settings = dict((config or {}).get("explore_layout", {}))
    registry = LayoutFamilyRegistry()
    family = registry.get(family_id)
    seed = int((state.get("iteration_context") or {}).get("random_seed", 0))
    maximum = int(settings.get("max_geometry_candidates_per_family", 4))
    if fixed_zones is not None:
        zones = [dict(item) for item in fixed_zones]
        variants = [{
            "variant_id": f"{family_id}_{_fingerprint(zones)}",
            "variant_label": "strict_fixed_topology",
            "geometry_fingerprint": _fingerprint(zones),
            "zones": zones,
            "mutation_trace": [],
        }]
    else:
        variants = generate_zone_variants(
            family, random_seed=seed, maximum=maximum
        )
        known = {
            str(item.get("geometry_fingerprint"))
            for item in variants
        }
        for runtime_variant in state.get("runtime_layout_variants") or []:
            if not isinstance(runtime_variant, dict):
                continue
            fingerprint = str(
                runtime_variant.get("geometry_fingerprint") or ""
            )
            zones = runtime_variant.get("zones") or []
            if (
                not fingerprint
                or fingerprint in known
                or not _valid_zones(zones)
            ):
                continue
            variants.append(deepcopy(runtime_variant))
            known.add(fingerprint)

    trials = []
    feasible = []
    measurement_cache: Dict[
        Tuple[Any, ...], List[Dict[str, Any]]
    ] = {}
    for variant in variants:
        result = _fit_one_variant(
            agent,
            board,
            state,
            family,
            variant,
            settings,
            measurement_cache,
        )
        trials.append({
            "variant_id": variant["variant_id"],
            "geometry_fingerprint": variant["geometry_fingerprint"],
            "mutation_trace": list(variant.get("mutation_trace") or []),
            "feasible": result is not None,
            "max_physical_utilization": (
                result.get("max_physical_utilization") if result else None
            ),
        })
        if result is not None:
            feasible.append(result)

    if not feasible:
        raise LayoutFeasibilityError(
            f"No capacity-safe {family_id} variant was found"
        )

    feasible.sort(key=lambda item: item["score"], reverse=True)
    top_k = feasible[: max(1, int(settings.get("diverse_top_k", 3)))]
    # Seeded selection among strong candidates avoids a single geometry
    # fossilizing while remaining reproducible for audit/retry.
    chosen = random.Random(seed + 7919).choice(top_k)
    report = {
        "schema_version": FIT_SCHEMA_VERSION,
        "status": "feasible",
        "family_id": family_id,
        "variant_id": chosen["variant"]["variant_id"],
        "geometry_fingerprint": chosen["variant"]["geometry_fingerprint"],
        "mutation_trace": list(chosen["variant"].get("mutation_trace") or []),
        "trials": trials,
        "trial_count": len(trials),
        "feasible_count": len(feasible),
        "zone_utilization": chosen["utilization"],
        "max_physical_utilization": chosen["max_physical_utilization"],
        "candidate_content_selection": chosen[
            "candidate_content_selection"
        ],
        "search_measurement": {
            "method": "font_aware_conservative_estimate",
            "safety_factor": float(
                settings.get("fast_measurement_safety_factor", 1.20)
            ),
            "final_exact_compile_required": True,
        },
    }
    return chosen["board"], chosen["layout_spec"], report


def validate_compiled_layout(
    layout: Sequence[Dict[str, Any]],
    layout_spec: Dict[str, Any],
    state: Dict[str, Any],
    *,
    poster_margin: float = 1.0,
    title_height_fraction: float = 0.18,
    tolerance: float = 0.01,
) -> Dict[str, Any]:
    """Fail-closed validation of compiled elements and zone ownership."""

    poster_width = float(state["poster_width"])
    poster_height = float(state["poster_height"])
    margin = float(poster_margin)
    title_fraction = float(title_height_fraction)
    effective_height = poster_height - 2 * margin
    body_y = margin + effective_height * title_fraction
    body_width = poster_width - 2 * margin
    body_height = effective_height - effective_height * title_fraction
    zone_boxes = {
        str(zone["zone_id"]): (
            margin + float(zone["x"]) * body_width,
            body_y + float(zone["y"]) * body_height,
            float(zone["width"]) * body_width,
            float(zone["height"]) * body_height,
        )
        for zone in layout_spec.get("zones", [])
    }
    issues = []
    containers = []
    for element in layout:
        try:
            x, y, width, height = (
                float(element[key]) for key in ("x", "y", "width", "height")
            )
        except (KeyError, TypeError, ValueError):
            issues.append({
                "code": "PREFLIGHT_INVALID_BOX",
                "element_id": element.get("id"),
            })
            continue
        if (
            x < -tolerance
            or y < -tolerance
            or x + width > poster_width + tolerance
            or y + height > poster_height + tolerance
        ):
            issues.append({
                "code": "PREFLIGHT_POSTER_BOUNDS",
                "element_id": element.get("id") or element.get("section_id"),
                "box": [x, y, width, height],
            })
        if element.get("type") == "section_container":
            containers.append(element)
            zone_id = str(element.get("zone_id") or "")
            zone_box = zone_boxes.get(zone_id)
            if zone_box is None:
                issues.append({
                    "code": "PREFLIGHT_ZONE_MISSING",
                    "section_id": element.get("section_id"),
                    "zone_id": zone_id,
                })
            else:
                zx, zy, zw, zh = zone_box
                if (
                    x < zx - tolerance
                    or y < zy - tolerance
                    or x + width > zx + zw + tolerance
                    or y + height > zy + zh + tolerance
                ):
                    issues.append({
                        "code": "PREFLIGHT_ZONE_BOUNDS",
                        "section_id": element.get("section_id"),
                        "zone_id": zone_id,
                        "box": [x, y, width, height],
                        "zone_box": [zx, zy, zw, zh],
                    })

    assigned = [
        str(section_id)
        for zone in layout_spec.get("zones", [])
        for section_id in zone.get("section_ids", [])
    ]
    rendered = [str(item.get("section_id")) for item in containers]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(rendered):
        issues.append({
            "code": "PREFLIGHT_ASSIGNMENT_MISMATCH",
            "assigned": assigned,
            "rendered": rendered,
        })
    return {
        "schema_version": FIT_SCHEMA_VERSION,
        "passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "family_id": layout_spec.get("family_id"),
        "variant_id": layout_spec.get("variant_id"),
        "geometry_fingerprint": layout_spec.get("geometry_fingerprint"),
    }
