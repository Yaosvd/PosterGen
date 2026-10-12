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
from itertools import combinations
from math import isfinite
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.layout.families import (
    LayoutArchitect,
    LayoutFamily,
    LayoutFamilyRegistry,
    compile_layout,
    valid_family_topology,
)
from src.layout.text_height_measurement import estimate_wrapped_line_count
from src.layout.paper_profile import narrative_role, narrative_title
from src.layout.measurement_context import current_context, measured_phase
from src.layout.whitespace import (
    measure_composition_whitespace,
    no_displaced_whitespace,
)


FIT_SCHEMA_VERSION = 5
COMPILED_PREFLIGHT_SCHEMA_VERSION = 4

PRESSURE_SAMPLE_LIMIT = 3
REPAIR_PRESSURE_SAMPLE_LIMIT = 128


def _visual_importance_weights(state: Dict[str, Any]) -> Dict[str, float]:
    """Prefer, but never require, the paper's approved editorial visuals."""

    classified = state.get("classified_visuals") or {}
    weights: Dict[str, float] = {}
    for field, weight in (
        ("main_results", 2.0),
        ("comparative_results", 1.5),
        ("method_workflow", 1.5),
    ):
        values = classified.get(field) or []
        for visual_id in values if isinstance(values, list) else [values]:
            if visual_id:
                weights[str(visual_id)] = max(weights.get(str(visual_id), 1.0), weight)
    key_visual = classified.get("key_visual")
    if isinstance(key_visual, str) and key_visual:
        weights[key_visual] = max(weights.get(key_visual, 1.0), 3.0)
    return weights


def _pressure_overage(sample: Dict[str, Any]) -> float:
    return float(sample["estimated_used_in"]) - float(sample["zone_limit_in"])


def _record_pressure_sample(
    diagnostics: Dict[str, Any], sample: Dict[str, Any], *, closest: bool = False,
    progress: bool = False,
) -> None:
    """Keep bounded, text-free evidence for repair and search diagnosis."""

    field = (
        "progress_pressure" if progress else
        "near_miss_pressure" if closest else "height_pressure"
    )
    samples = diagnostics.setdefault(field, [])
    identity = (
        sample.get("section_id"), sample.get("zone_id"),
        sample.get("placed_section_count", 0),
        sample.get("option_claim_count", 0),
        sample.get("option_visual_count", 0),
    )
    for index, existing in enumerate(samples):
        existing_identity = (
            existing.get("section_id"), existing.get("zone_id"),
            existing.get("placed_section_count", 0),
            existing.get("option_claim_count", 0),
            existing.get("option_visual_count", 0),
        )
        if existing_identity == identity:
            better = (
                _pressure_overage(sample) < _pressure_overage(existing)
                if closest or progress else
                _pressure_overage(sample) > _pressure_overage(existing)
            )
            if better:
                samples[index] = sample
            break
    else:
        samples.append(sample)
    samples.sort(key=lambda item: (
        -int(item.get("placed_section_count", 0)) if progress else 0,
        _pressure_overage(item) if closest or progress else -_pressure_overage(item),
        -int(item.get("option_claim_count", 0)),
        str(item.get("section_id")), str(item.get("zone_id")),
    ))
    del samples[PRESSURE_SAMPLE_LIMIT:]


def _repair_pressure_candidates(
    trials: Sequence[Dict[str, Any]], *, maximum_overage: float,
) -> Tuple[List[Dict[str, Any]], int]:
    """Summarize all searched variants before the display-only trial cap."""

    candidates: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for trial in trials:
        diagnostics = trial.get("diagnostics") or {}
        for field in ("near_miss_pressure", "progress_pressure", "height_pressure"):
            for sample in diagnostics.get(field) or []:
                try:
                    used = float(sample["estimated_used_in"])
                    limit = float(sample["zone_limit_in"])
                    overage = used - limit
                except (KeyError, TypeError, ValueError):
                    continue
                if not all(isfinite(value) for value in (used, limit, overage)):
                    continue
                if not 0 < overage <= maximum_overage:
                    continue
                section_id = str(sample.get("section_id") or "")
                zone_id = str(sample.get("zone_id") or "")
                if not section_id or not zone_id:
                    continue
                components = sample.get("height_components") or {}
                try:
                    safe_components = {
                        key: round(float(components[key]), 3)
                        for key in (
                            "title_height_in", "visual_height_in", "text_height_in",
                            "unattributed_height_in",
                        )
                        if key in components
                    }
                    claim_ids = [
                        str(item) for item in sample.get("option_claim_ids") or []
                    ]
                    placed_count = int(sample.get("placed_section_count", 0))
                    claim_count = int(sample.get("option_claim_count", len(claim_ids)))
                    visual_count = int(sample.get("option_visual_count", 0))
                except (TypeError, ValueError, OverflowError):
                    continue
                if not all(isfinite(value) for value in safe_components.values()):
                    continue
                candidate = {
                    "variant_id": str(trial.get("variant_id") or ""),
                    "geometry_fingerprint": str(
                        trial.get("geometry_fingerprint") or ""
                    ),
                    "section_id": section_id,
                    "zone_id": zone_id,
                    "estimated_used_in": round(used, 3),
                    "zone_limit_in": round(limit, 3),
                    "overage_in": round(overage, 3),
                    "placed_section_count": placed_count,
                    "option_claim_count": claim_count,
                    "option_visual_count": visual_count,
                    "option_claim_ids": claim_ids,
                    "height_components": safe_components,
                    "text_can_cover_overage": (
                        "text_height_in" not in safe_components
                        or safe_components["text_height_in"] + 1e-6 >= overage
                    ),
                }
                identity = (
                    candidate["geometry_fingerprint"], section_id, zone_id,
                    candidate["placed_section_count"], tuple(claim_ids),
                    candidate["estimated_used_in"], candidate["zone_limit_in"],
                )
                candidates[identity] = candidate
    ordered = sorted(candidates.values(), key=lambda item: (
        not item["text_can_cover_overage"],
        -item["placed_section_count"],
        item["overage_in"],
        -item["option_claim_count"],
        item["geometry_fingerprint"], item["section_id"], item["zone_id"],
    ))
    return ordered[:REPAIR_PRESSURE_SAMPLE_LIMIT], len(ordered)


class LayoutFeasibilityError(ValueError):
    """Raised when no bounded layout can be compiled for a candidate."""

    def __init__(self, message: str, report: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.report = report


def _failure_report(
    *,
    family_id: str,
    reason: str,
    reason_code: str,
    failure_stage: str,
    trials: List[Dict[str, Any]],
    settings: Dict[str, Any],
    board: Dict[str, Any],
    feasible_count: int,
    near_miss_rechecks: int = 0,
    repair_overage_limit: float = 2.0,
) -> Dict[str, Any]:
    """Bounded, text-free evidence about a failed *search*, not an impossibility proof."""

    sections = (board.get("spatial_content_plan") or {}).get("sections") or []
    blocker_counts: Dict[str, int] = {}
    for trial in trials:
        for key, count in (trial.get("diagnostics") or {}).get(
            "observed_blockers", {}
        ).items():
            blocker_counts[key] = blocker_counts.get(key, 0) + int(count)
    dominant = (
        max(sorted(blocker_counts), key=lambda key: blocker_counts[key])
        if blocker_counts else None
    )
    height_pressure = sorted(
        (
            sample
            for trial in trials
            for sample in (trial.get("diagnostics") or {}).get("height_pressure", [])
        ),
        key=lambda item: float(item.get("estimated_used_in", 0))
        - float(item.get("zone_limit_in", 0)),
        reverse=True,
    )[:3]
    near_pressure = sorted(
        (
            sample
            for trial in trials
            for sample in (trial.get("diagnostics") or {}).get(
                "near_miss_pressure", []
            )
        ),
        key=lambda item: (
            _pressure_overage(item),
            -int(item.get("placed_section_count", 0)),
            str(item.get("section_id")), str(item.get("zone_id")),
        ),
    )[:PRESSURE_SAMPLE_LIMIT]
    progress_pressure = sorted(
        (
            sample
            for trial in trials
            for sample in (trial.get("diagnostics") or {}).get("progress_pressure", [])
        ),
        key=lambda item: (
            -int(item.get("placed_section_count", 0)),
            _pressure_overage(item),
            -int(item.get("option_claim_count", 0)),
        ),
    )[:PRESSURE_SAMPLE_LIMIT]
    repair_candidates, repair_candidate_count = _repair_pressure_candidates(
        trials, maximum_overage=repair_overage_limit,
    )
    if reason_code == "INVALID_PARENT_LAYOUT_SPEC":
        failure_class = "structural_parent"
    elif reason_code == "NO_EXACT_COMPILABLE_VARIANT":
        failure_class = "exact_geometry_or_preflight"
    elif height_pressure:
        failure_class = "height_pressure_observed"
    else:
        failure_class = "search_or_assignment_limit"
    return {
        "schema_version": FIT_SCHEMA_VERSION,
        "status": "infeasible",
        "family_id": family_id,
        "reason": reason,
        "reason_code": reason_code,
        "failure_stage": failure_stage,
        "search_exhausted_not_proven_impossible": (
            reason_code != "INVALID_PARENT_LAYOUT_SPEC"
        ),
        "trial_count": len(trials),
        "feasible_count": feasible_count,
        "near_miss_rechecks": near_miss_rechecks,
        "trials": trials[:12],
        "diagnostic_trial_limit": 12,
        "observed_blockers": blocker_counts,
        "dominant_blocker": dominant,
        "failure_class": failure_class,
        "height_pressure_samples": height_pressure,
        "near_miss_pressure_samples": near_pressure,
        "progress_pressure_samples": progress_pressure,
        "repair_pressure_candidates": repair_candidates,
        "repair_pressure_candidate_count": repair_candidate_count,
        "repair_pressure_candidates_truncated": (
            repair_candidate_count > len(repair_candidates)
        ),
        "repair_pressure_candidate_limit": REPAIR_PRESSURE_SAMPLE_LIMIT,
        "input_summary": {
            "section_count": len(sections),
            "claim_count": sum(len(item.get("claim_ids") or []) for item in sections),
            "visual_count": sum(len(item.get("visual_assets") or []) for item in sections),
        },
        "search_limits": {
            "max_geometry_candidates_per_family": int(settings.get(
                "max_geometry_candidates_per_family", 4
            )),
            "max_adaptive_geometry_candidates": int(settings.get(
                "max_adaptive_geometry_candidates", 12
            )),
            "max_exact_candidates": int(settings.get("max_exact_candidates", 8)),
            "beam_width": int(settings.get("beam_width", 4)),
            "adaptive_beam_width": int(settings.get("adaptive_beam_width", 8)),
            "max_extra_claim_subsets_per_section": int(settings.get("max_extra_claim_subsets_per_section", 12)),
            "max_near_miss_rechecks": int(settings.get("max_near_miss_rechecks", 2)),
            "minimum_sections": int(settings.get("minimum_sections", 5)),
            "fast_measurement_safety_factor": float(settings.get(
                "fast_measurement_safety_factor", 1.20
            )),
            "max_repairable_overflow_inches": repair_overage_limit,
        },
    }


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


def _topology_candidates(
    family: LayoutFamily,
    zones: Sequence[Dict[str, Any]],
) -> List[Tuple[str, List[Dict[str, Any]], List[str]]]:
    """Generate legal local splits and spans without model-supplied coordinates."""

    if family.family_id == "classic_three_column":
        return []
    protected = {
        "flow_spine", "comparison_a", "comparison_b",
        "primary_result", "top_hero", "central_hero", "lead",
    }
    result: List[Tuple[str, List[Dict[str, Any]], List[str]]] = []
    for index, zone in enumerate(zones):
        if zone.get("role") == "hero" or int(zone.get("capacity", 1)) < 2:
            continue
        if float(zone["height"]) < 0.35:
            continue
        gap = min(0.02, float(zone["height"]) * 0.06)
        upper_height = (float(zone["height"]) - gap) * 0.5
        split = deepcopy(list(zones))
        split[index] = {
            **split[index],
            "height": round(upper_height, 6),
            "capacity": max(1, int(zone["capacity"]) // 2),
        }
        split.insert(index + 1, {
            **deepcopy(zone),
            "zone_id": f"{zone['zone_id']}__lower",
            "y": round(float(zone["y"]) + upper_height + gap, 6),
            "height": round(float(zone["height"]) - upper_height - gap, 6),
            "capacity": max(1, int(zone["capacity"]) - split[index]["capacity"]),
        })
        result.append((
            f"split_{zone['zone_id']}", split,
            ["split_zone", str(zone["zone_id"])],
        ))

    for index, left in enumerate(zones):
        if (
            left.get("role") != "support"
            or left.get("zone_id") in protected
            or int(left.get("capacity", 1)) != 1
        ):
            continue
        for other_index, right in enumerate(zones[index + 1:], index + 1):
            if (
                right.get("role") != "support"
                or right.get("zone_id") in protected
                or int(right.get("capacity", 1)) != 1
                or abs(float(left["y"]) - float(right["y"])) > 1e-6
                or abs(float(left["height"]) - float(right["height"])) > 1e-6
            ):
                continue
            gap = float(right["x"]) - float(left["x"]) - float(left["width"])
            if not 0 <= gap <= 0.06:
                continue
            merged = deepcopy(list(zones))
            merged[index] = {
                **merged[index],
                "width": round(
                    float(right["x"]) + float(right["width"])
                    - float(left["x"]), 6
                ),
                "capacity": 2,
            }
            del merged[other_index]
            result.append((
                f"span_{left['zone_id']}_{right['zone_id']}",
                merged,
                ["span_adjacent_zones", str(left["zone_id"]), str(right["zone_id"])],
            ))
    return result


def _boundary_candidates(
    zones: Sequence[Dict[str, Any]],
    *,
    random_seed: int,
) -> List[Tuple[str, List[Dict[str, Any]], List[str]]]:
    """Sample continuous shared-boundary changes while preserving gaps."""

    rng = random.Random(random_seed + 3301)
    result: List[Tuple[str, List[Dict[str, Any]], List[str]]] = []
    for index, left in enumerate(zones):
        for other_index, right in enumerate(zones[index + 1:], index + 1):
            horizontal = (
                abs(float(left["y"]) - float(right["y"])) < 1e-6
                and abs(float(left["height"]) - float(right["height"])) < 1e-6
                and 0 <= (
                    float(right["x"]) - float(left["x"]) - float(left["width"])
                ) <= 0.06
            )
            vertical = (
                abs(float(left["x"]) - float(right["x"])) < 1e-6
                and abs(float(left["width"]) - float(right["width"])) < 1e-6
                and 0 <= (
                    float(right["y"]) - float(left["y"]) - float(left["height"])
                ) <= 0.06
            )
            if not horizontal and not vertical:
                continue
            axis = "x" if horizontal else "y"
            size = "width" if horizontal else "height"
            for _ in range(2):
                delta = round(rng.uniform(-0.065, 0.065), 6)
                changed = deepcopy(list(zones))
                changed[index][size] = round(
                    float(changed[index][size]) + delta, 6
                )
                changed[other_index][axis] = round(
                    float(changed[other_index][axis]) + delta, 6
                )
                changed[other_index][size] = round(
                    float(changed[other_index][size]) - delta, 6
                )
                result.append((
                    f"boundary_{left['zone_id']}_{right['zone_id']}_{delta}",
                    changed,
                    ["shift_shared_boundary", str(left["zone_id"]), str(right["zone_id"])],
                ))
            if len(result) >= 8:
                return result
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

    candidates.extend(_topology_candidates(family, canonical))
    candidates.extend(_boundary_candidates(
        canonical, random_seed=random_seed
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
        if not _valid_zones(zones) or not valid_family_topology(family, zones):
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
        topology = [
            item for item in remainder
            if any(
                operation in {"split_zone", "span_adjacent_zones"}
                for operation in item["mutation_trace"]
            )
        ]
        selected_topology = topology[:1] if topology and maximum > 1 else []
        selected_ids = {
            item["geometry_fingerprint"] for item in selected_topology
        }
        variants = [
            canonical_variant,
            *selected_topology,
            *[
                item for item in remainder
                if item["geometry_fingerprint"] not in selected_ids
            ],
        ]
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


def _semantic_role(section: Dict[str, Any], state: Dict[str, Any]) -> str:
    section_id = str(section.get("section_id") or "")
    narrative_sections = {
        str(item.get("section_id")): item
        for item in (state.get("narrative_plan") or {}).get("sections", [])
        if isinstance(item, dict) and item.get("section_id")
    }
    narrative_section = narrative_sections.get(section_id, {})
    role = narrative_role(narrative_section)
    if role in {
        "foundation", "problem", "method", "theory", "results", "conclusion"
    }:
        return role
    title = str(section.get("section_title") or narrative_title(narrative_section)[1]).lower()
    if any(word in title for word in ("result", "finding", "performance", "evaluation")):
        return "results"
    if any(word in title for word in ("method", "approach", "pipeline")):
        return "method"
    if any(word in title for word in ("conclusion", "implication")):
        return "conclusion"
    return "supporting"


def _active_zone_roles(
    family_id: str,
    sections: Sequence[Dict[str, Any]],
    state: Dict[str, Any],
) -> Dict[str, set]:
    semantic_zones = {
        "result_dashboard_cards": {
            "primary_result": {"results"},
            "method": {"method"},
        },
        "method_flow_spine": {"flow_spine": {"method"}},
        "top_hero_bottom_grid": {"top_hero": {"results", "conclusion"}},
    }.get(family_id, {})
    present = {_semantic_role(section, state) for section in sections}
    return {
        zone_id: roles
        for zone_id, roles in semantic_zones.items()
        if present.intersection(roles)
    }


def _estimate_section_height(
    agent: Any,
    section: Dict[str, Any],
    *,
    zone_width: float,
    zone_height: float,
    state: Dict[str, Any],
    safety_factor: Optional[float] = None,
    components: Optional[Dict[str, float]] = None,
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
        measured = float(agent._calculate_precise_section_height(
            section, zone_width, state, zone_height
        ))
        if components is not None:
            components["unattributed_height_in"] = round(measured, 3)
        return measured

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
        safety_factor if safety_factor is not None else
        (state.get("critic_config") or {}).get("explore_layout", {}).get(
            "fast_measurement_safety_factor", 1.20
        )
    )
    title_height = 0.0
    visual_height_total = 0.0
    text_height = 0.0
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
        title_height += title_lines * title_size / 72 * 1.25
        title_height += float(
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
        visual_height_total += float(visual_height)
        visual_height_total += float(
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
        text_height += body_lines * body_size / 72 * 1.25
        text_height += content.count("\n") * body_size / 72 * 0.10
        text_height += 0.50

    if components is not None:
        components.update({
            "title_height_in": round(title_height * factor, 3),
            "visual_height_in": round(visual_height_total * factor, 3),
            "text_height_in": round(text_height * factor, 3),
        })
    return max(0.1, (title_height + visual_height_total + text_height) * factor)


def _content_options(
    agent: Any,
    section: Dict[str, Any],
    *,
    zone_width: float,
    zone_height: float,
    state: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    claim_ids = list(section.get("claim_ids") or [])
    text = list(section.get("text_content") or [])
    if not claim_ids or len(claim_ids) != len(text):
        return []
    visuals = list(section.get("visual_assets") or [])
    options = []
    visual_sets = [visuals]
    if len(visuals) > 1:
        visual_sets.extend(
            [visual] for visual in visuals
        )
    if visuals:
        visual_sets.append([])
    claim_count = len(claim_ids)
    max_nonprefix = max(0, min(32, int(
        (settings or (state.get("critic_config") or {}).get("explore_layout", {})).get(
            "max_extra_claim_subsets_per_section", 12
        )
    )))
    # Keep every historical prefix option, including a one-claim fallback.
    # Extra subsets expand the search without losing compact candidates.
    subsets = [tuple(range(count)) for count in range(claim_count, 0, -1)]
    seen_subsets = set(subsets)
    added_nonprefix = 0
    for count in (range(claim_count, 0, -1) if max_nonprefix else ()):
        for subset in combinations(range(claim_count), count):
            if subset in seen_subsets:
                continue
            subsets.append(subset)
            seen_subsets.add(subset)
            added_nonprefix += 1
            if added_nonprefix >= max_nonprefix:
                break
        if added_nonprefix >= max_nonprefix:
            break
    for selected_visuals in visual_sets:
        for subset in subsets:
            candidate = deepcopy(section)
            candidate["claim_ids"] = [claim_ids[index] for index in subset]
            candidate["text_content"] = [text[index] for index in subset]
            candidate["visual_assets"] = deepcopy(selected_visuals)
            components: Dict[str, float] = {}
            height = _estimate_section_height(
                agent,
                candidate,
                zone_width=zone_width,
                zone_height=zone_height,
                state=state,
                safety_factor=(settings or {}).get("fast_measurement_safety_factor"),
                components=components,
            )
            options.append({
                "section": candidate,
                "height": height,
                "retained_claims": len(subset),
                "retained_visuals": len(selected_visuals),
                "height_components": components,
            })
    options.sort(
        key=lambda item: (
            item["retained_claims"], item["retained_visuals"], -item["height"]
        ),
        reverse=True,
    )
    return options


@measured_phase("exact_candidate")
def _exact_refine_candidate(
    agent: Any,
    candidate: Dict[str, Any],
    source_board: Dict[str, Any],
    state: Dict[str, Any],
    settings: Dict[str, Any],
    *,
    allow_changes: bool,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Restore grounded content using the same section geometry as the compiler."""

    diagnostics = diagnostics if diagnostics is not None else {}
    result = deepcopy(candidate)
    board = result["board"]
    spec = result["layout_spec"]
    selected = {
        str(section["section_id"]): section
        for section in board["spatial_content_plan"]["sections"]
    }
    original = {
        str(section["section_id"]): section
        for section in source_board["spatial_content_plan"]["sections"]
        if isinstance(section, dict) and section.get("section_id")
    }
    semantic_zones = _active_zone_roles(
        str(spec.get("family_id") or ""),
        list(original.values()),
        state,
    )
    effective_height = float(state["poster_height"]) - 2 * agent.poster_margin
    body_height = effective_height * (1 - agent.title_height_fraction)
    body_width = float(state["poster_width"]) - 2 * agent.poster_margin
    gap = float(agent._inter_section_spacing(state))
    reserve = max(0.0, float(agent.layout_constants.get("body_render_reserve", 0.0)))
    target = min(1.0, float(settings.get("planning_target", 0.975)))
    maximum = min(1.0, float(settings.get("maximum_utilization", 1.0)))
    zone_by_id = {str(zone["zone_id"]): zone for zone in spec["zones"]}
    section_zone = {
        str(section_id): str(zone["zone_id"])
        for zone in spec["zones"]
        for section_id in zone.get("section_ids", [])
    }
    height_cache: Dict[Tuple[Any, ...], float] = {}

    def section_height(section: Dict[str, Any], zone_id: str) -> float:
        zone = zone_by_id[zone_id]
        width = max(0.5, float(zone["width"]) * body_width)
        height = max(0.5, float(zone["height"]) * body_height)
        key = (
            str(section["section_id"]),
            zone_id,
            tuple(section.get("claim_ids") or []),
            tuple(
                str(item.get("visual_id"))
                for item in section.get("visual_assets") or []
                if isinstance(item, dict)
            ),
        )
        if key not in height_cache:
            height_cache[key] = float(agent._calculate_precise_section_height(
                section, width, state, height
            ))
        return height_cache[key]

    def zone_used(zone_id: str) -> float:
        zone = zone_by_id[zone_id]
        ids = [str(item) for item in zone.get("section_ids", [])]
        return sum(section_height(selected[item], zone_id) for item in ids) + (
            max(0, len(ids) - 1) * gap
        )

    restored: List[Dict[str, str]] = []
    if allow_changes:
        # The fast beam may omit a whole section. Recover it before adding
        # detail to already visible sections, using the original verified text.
        for source in sorted(original.values(), key=_section_priority, reverse=True):
            section_id = str(source["section_id"])
            if section_id in selected or not source.get("claim_ids"):
                continue
            placements = []
            for zone_id, zone in zone_by_id.items():
                required_roles = semantic_zones.get(zone_id)
                if (
                    required_roles
                    and _semantic_role(source, state) not in required_roles
                ):
                    continue
                if len(zone.get("section_ids", [])) >= int(zone.get("capacity", 1)):
                    continue
                zone_height = max(0.5, float(zone["height"]) * body_height)
                extra = section_height(source, zone_id)
                spacing = gap if zone.get("section_ids") else 0.0
                new_use = zone_used(zone_id) + spacing + extra
                if new_use + reserve <= zone_height * maximum + 1e-6:
                    placements.append((
                        abs(new_use / zone_height - target),
                        zone_id,
                    ))
            if not placements:
                continue
            _, zone_id = min(placements)
            zone_by_id[zone_id].setdefault("section_ids", []).append(section_id)
            section_zone[section_id] = zone_id
            selected[section_id] = deepcopy(source)
            restored.append({
                "section_id": section_id,
                "kind": "section",
                "item_id": section_id,
            })

        constraints = state.get("layout_revision_constraints") or {}
        locked_zones = {
            str(section_id): str(zone_id)
            for section_id, zone_id in (
                constraints.get("section_to_zone") or {}
            ).items()
        }
        if not constraints.get("reading_order"):
            for _ in range(2):
                current_error = sum(
                    abs(
                        zone_used(zone_id)
                        / max(0.5, float(zone["height"]) * body_height)
                        - target
                    )
                    for zone_id, zone in zone_by_id.items()
                )
                moves = []
                for section_id, section in selected.items():
                    origin = section_zone[section_id]
                    if (
                        section_id in locked_zones
                        or len(zone_by_id[origin].get("section_ids", [])) <= 1
                    ):
                        continue
                    for target_id, target_zone in zone_by_id.items():
                        if target_id == origin:
                            continue
                        required_roles = semantic_zones.get(target_id)
                        if (
                            required_roles
                            and _semantic_role(section, state) not in required_roles
                        ):
                            continue
                        if len(target_zone.get("section_ids", [])) >= int(
                            target_zone.get("capacity", 1)
                        ):
                            continue
                        target_height = max(
                            0.5, float(target_zone["height"]) * body_height
                        )
                        target_extra = section_height(section, target_id)
                        target_spacing = gap if target_zone.get("section_ids") else 0.0
                        if (
                            zone_used(target_id) + target_spacing
                            + target_extra + reserve
                            > target_height * maximum + 1e-6
                        ):
                            continue
                        source_height = max(
                            0.5, float(zone_by_id[origin]["height"]) * body_height
                        )
                        source_new = (
                            zone_used(origin)
                            - section_height(section, origin)
                            - gap
                        ) / source_height
                        target_new = (
                            zone_used(target_id)
                            + target_spacing
                            + target_extra
                        ) / target_height
                        old_pair = (
                            abs(zone_used(origin) / source_height - target)
                            + abs(zone_used(target_id) / target_height - target)
                        )
                        new_error = (
                            current_error - old_pair
                            + abs(source_new - target)
                            + abs(target_new - target)
                        )
                        if new_error < current_error - 0.03:
                            moves.append((
                                new_error, section_id, origin, target_id
                            ))
                if not moves:
                    break
                _, section_id, origin, target_id = min(moves)
                zone_by_id[origin]["section_ids"].remove(section_id)
                zone_by_id[target_id]["section_ids"].append(section_id)
                section_zone[section_id] = target_id
                restored.append({
                    "section_id": section_id,
                    "kind": "move",
                    "item_id": f"{origin}->{target_id}",
                })

        maximum_steps = max(0, int(settings.get("max_exact_refill_steps", 24)))
        for _ in range(maximum_steps):
            choices = []
            for section_id, section in selected.items():
                zone_id = section_zone[section_id]
                zone_height = max(
                    0.5, float(zone_by_id[zone_id]["height"]) * body_height
                )
                current_used = zone_used(zone_id)
                source = original.get(section_id) or {}
                source_claim_ids = source.get("claim_ids") or []
                source_text = source.get("text_content") or []
                if len(source_claim_ids) == len(source_text):
                    claim_text = dict(zip(source_claim_ids, source_text))
                    for claim_id in source_claim_ids:
                        if claim_id in section.get("claim_ids", []):
                            continue
                        trial = deepcopy(section)
                        trial_ids = set(trial.get("claim_ids") or [])
                        trial_ids.add(claim_id)
                        trial["claim_ids"] = [
                            item for item in source_claim_ids if item in trial_ids
                        ]
                        trial["text_content"] = [
                            claim_text[item] for item in trial["claim_ids"]
                        ]
                        extra = section_height(trial, zone_id) - section_height(
                            section, zone_id
                        )
                        if (
                            extra > 0
                            and current_used + extra + reserve
                            <= zone_height * maximum + 1e-6
                        ):
                            new_use = (current_used + extra) / zone_height
                            choices.append((
                                1.0 + min(extra / zone_height, 1.0)
                                - max(0.0, new_use - target),
                                section_id,
                                "claim",
                                str(claim_id),
                                trial,
                            ))
                source_visuals = source.get("visual_assets") or []
                selected_visuals = {
                    str(item.get("visual_id"))
                    for item in section.get("visual_assets") or []
                    if isinstance(item, dict)
                }
                for visual in source_visuals:
                    visual_id = str(visual.get("visual_id") or "")
                    if not visual_id or visual_id in selected_visuals:
                        continue
                    trial = deepcopy(section)
                    trial["visual_assets"] = [
                        item for item in source_visuals
                        if str(item.get("visual_id")) in (
                            selected_visuals | {visual_id}
                        )
                    ]
                    extra = section_height(trial, zone_id) - section_height(
                        section, zone_id
                    )
                    if (
                        extra > 0
                        and current_used + extra + reserve
                        <= zone_height * maximum + 1e-6
                    ):
                        new_use = (current_used + extra) / zone_height
                        choices.append((
                            1.35 + min(extra / zone_height, 1.0)
                            - max(0.0, new_use - target),
                            section_id,
                            "visual",
                            visual_id,
                            trial,
                        ))
            if not choices:
                break
            _, section_id, kind, item_id, trial = max(
                choices, key=lambda item: (
                    item[0], item[1], item[2], item[3]
                )
            )
            selected[section_id] = trial
            restored.append({
                "section_id": section_id,
                "kind": kind,
                "item_id": item_id,
            })

    board["spatial_content_plan"]["sections"] = [
        selected[str(section["section_id"])]
        for section in source_board["spatial_content_plan"]["sections"]
        if str(section.get("section_id")) in selected
    ]
    assigned = [
        str(section_id)
        for zone in spec["zones"]
        for section_id in zone.get("section_ids", [])
    ]
    if set(spec.get("reading_order") or []) != set(assigned):
        spec["reading_order"] = assigned
    result["candidate_content_selection"]["dropped_section_ids"] = sorted(
        set(original) - set(selected)
    )
    try:
        layout = compile_layout(agent, board, state, spec)
        preflight = validate_compiled_layout(
            layout, spec, state,
            poster_margin=agent.poster_margin,
            title_height_fraction=agent.title_height_fraction,
        )
    except (ValueError, KeyError, TypeError) as exc:
        result["exact_failure"] = str(exc)
        diagnostics.update({
            "stage": "exact_compile",
            "reason_code": "EXACT_COMPILE_ERROR",
            "error_type": type(exc).__name__,
        })
        return None
    if not preflight["passed"]:
        diagnostics.update({
            "stage": "exact_preflight",
            "reason_code": "EXACT_PREFLIGHT_FAILED",
            "issue_count": int(preflight.get("issue_count", 0)),
            "issues": [
                {
                    "issue_id": issue.get("issue_id") or issue.get("code"),
                    "section_id": issue.get("section_id"),
                    "zone_id": issue.get("zone_id"),
                }
                for issue in (preflight.get("issues") or [])[:5]
                if isinstance(issue, dict)
            ],
        })
        return None

    containers = [
        item for item in layout if item.get("type") == "section_container"
    ]
    actual_utilization = {}
    bottom_gaps = {}
    for zone in spec["zones"]:
        zone_id = str(zone["zone_id"])
        zone_top = (
            agent.poster_margin
            + effective_height * agent.title_height_fraction
            + float(zone["y"]) * body_height
        )
        zone_height = max(0.5, float(zone["height"]) * body_height)
        owned = [
            item for item in containers
            if str(item.get("zone_id")) == zone_id
        ]
        last_bottom = max(
            (float(item["y"]) + float(item["height"]) for item in owned),
            default=zone_top,
        )
        actual_utilization[zone_id] = round(
            max(0.0, (last_bottom - zone_top) / zone_height), 6
        )
        bottom_gaps[zone_id] = round(
            max(0.0, zone_top + zone_height - last_bottom), 4
        )
    whitespace = measure_composition_whitespace(
        spec, layout,
        poster_width=float(state["poster_width"]),
        poster_height=float(state["poster_height"]),
        poster_margin=float(agent.poster_margin),
        title_height_fraction=float(agent.title_height_fraction),
    )

    source_claim_ids = {
        str(item)
        for section in original.values()
        for item in section.get("claim_ids") or []
    }
    source_visual_ids = {
        str(item.get("visual_id"))
        for section in original.values()
        for item in section.get("visual_assets") or []
        if isinstance(item, dict) and item.get("visual_id")
    }
    visible_claim_ids = {
        str(item)
        for section in selected.values()
        for item in section.get("claim_ids") or []
    }
    visible_visual_ids = {
        str(item.get("visual_id"))
        for section in selected.values()
        for item in section.get("visual_assets") or []
        if isinstance(item, dict) and item.get("visual_id")
    }
    density = sum(
        1.0 - abs(value - target)
        for value in actual_utilization.values()
    ) / max(1, len(actual_utilization))
    worst_density = min(actual_utilization.values() or [0.0])
    largest_bottom_gap = max(bottom_gaps.values() or [0.0])
    worst_gap_ratio = min(
        1.0,
        largest_bottom_gap / max(1.0, body_height),
    )
    claim_coverage = len(visible_claim_ids) / max(1, len(source_claim_ids))
    visual_weights = _visual_importance_weights(state)
    source_visual_weight = sum(visual_weights.get(item, 1.0) for item in source_visual_ids)
    visual_coverage = (
        sum(visual_weights.get(item, 1.0) for item in visible_visual_ids)
        / source_visual_weight if source_visual_weight else 1.0
    )
    section_coverage = len(selected) / max(1, len(original))
    parent_zones = {
        str(zone.get("zone_id")): zone
        for zone in (
            (state.get("revision_parent_layout_spec") or {}).get("zones") or []
        )
        if isinstance(zone, dict)
    }
    budget_preferences = (
        (state.get("layout_revision_constraints") or {})
        .get("zone_budget_preferences") or []
    )
    budget_met = []
    for preference in budget_preferences:
        zone_id = str(preference.get("zone_id") or "")
        old = parent_zones.get(zone_id)
        new = zone_by_id.get(zone_id)
        if not old or not new:
            continue
        old_area = float(old["width"]) * float(old["height"])
        new_area = float(new["width"]) * float(new["height"])
        direction = str(preference.get("direction") or "")
        if (
            direction == "shrink" and new_area < old_area - 0.005
        ) or (
            direction == "expand" and new_area > old_area + 0.005
        ):
            budget_met.append(zone_id)
    result["exact_score"] = round(
        0.27 * claim_coverage
        + 0.17 * visual_coverage
        + 0.20 * density
        + 0.20 * worst_density
        + 0.13 * section_coverage
        + 0.03 * (1.0 - worst_gap_ratio)
        - 0.04 * whitespace["largest_empty_rectangle_fraction"]
        - 0.02 * whitespace["unallocated_body_fraction"]
        - 0.04 * min(1.0, whitespace["largest_cross_zone_gap_inches"] / body_height)
        - 0.02 * min(1.0, whitespace["largest_within_zone_gap_inches"] / body_height)
        + 0.025 * len(budget_met),
        6,
    )
    result["zone_budget_preferences_met"] = budget_met
    result["exact_utilization"] = actual_utilization
    result["exact_bottom_gaps"] = bottom_gaps
    result["worst_zone_utilization"] = worst_density
    result["largest_bottom_gap_inches"] = largest_bottom_gap
    result["composition_whitespace"] = whitespace
    result["restored_content"] = restored
    selection = result["candidate_content_selection"]
    selection["visible_claim_ids"] = sorted(visible_claim_ids)
    selection["omitted_claim_ids"] = sorted(source_claim_ids - visible_claim_ids)
    selection["visible_visual_ids"] = sorted(visible_visual_ids)
    selection["omitted_visual_ids"] = sorted(source_visual_ids - visible_visual_ids)
    selection["reason"] = "exact_family_capacity_fit"
    return result


@measured_phase("fast_variant")
def _fit_one_variant(
    agent: Any,
    board: Dict[str, Any],
    state: Dict[str, Any],
    family: LayoutFamily,
    variant: Dict[str, Any],
    settings: Dict[str, Any],
    measurement_cache: Dict[Tuple[Any, ...], List[Dict[str, Any]]],
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics["stage"] = "fast_assignment"
    blockers: Dict[str, int] = diagnostics.setdefault("observed_blockers", {})

    def blocked(code: str) -> None:
        blockers[code] = blockers.get(code, 0) + 1

    sections = [
        deepcopy(item)
        for item in board.get("spatial_content_plan", {}).get("sections", [])
        if isinstance(item, dict) and item.get("section_id")
        and item.get("claim_ids")
    ]
    if not sections:
        diagnostics["reason_code"] = "NO_VALID_SECTIONS"
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
    zone_slots = sum(max(1, int(zone.get("capacity", 1))) for zone in variant["zones"])
    minimum_sections = min(
        len(sections), max(1, min(int(settings.get("minimum_sections", 5)), zone_slots))
    )
    diagnostics["effective_minimum_sections"] = minimum_sections
    diagnostics["zone_slots"] = zone_slots
    constraints = (
        state.get("layout_revision_constraints")
        if str((state.get("iteration_context") or {}).get("portfolio_mode")) == "improve"
        else {}
    ) or {}
    required_section_zones = {
        str(section_id): str(zone_id)
        for section_id, zone_id in (
            constraints.get("section_to_zone") or {}
        ).items()
    }
    must_retain_claim_ids = {
        str(item) for item in constraints.get("must_retain_claim_ids", [])
    }
    must_retain_visual_ids = {
        str(item) for item in constraints.get("must_retain_visual_ids", [])
    } | {
        str(item) for item in state.get("layout_required_visual_ids") or []
    }

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
    section_roles = {
        str(section["section_id"]): _semantic_role(section, state)
        for section in ordered
    }
    active_semantic_zones = _active_zone_roles(
        family.family_id, ordered, state
    )
    total_claims = sum(len(item.get("claim_ids") or []) for item in ordered)
    total_visuals = sum(len(item.get("visual_assets") or []) for item in ordered)
    visual_weights = _visual_importance_weights(state)
    total_visual_weight = sum(
        visual_weights.get(str(visual.get("visual_id")), 1.0)
        for section in ordered for visual in section.get("visual_assets") or []
        if isinstance(visual, dict) and visual.get("visual_id")
    )

    def priority_visual_coverage(item: Dict[str, Any]) -> float:
        if not total_visual_weight:
            return 1.0
        return float(item["retained_visual_weight"]) / total_visual_weight
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
                round(float(settings.get("fast_measurement_safety_factor", 1.20)), 3),
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
                    settings=settings,
                )
            option_cache[(section_id, zone_id)] = measurement_cache[
                cache_key
            ]
            if not option_cache[(section_id, zone_id)]:
                blocked("no_content_options")

    # Each beam state owns independent selected content and assignments.
    beam = [{
        "assignments": {str(item["zone_id"]): [] for item in zones},
        "heights": {str(item["zone_id"]): 0.0 for item in zones},
        "selected": [],
        "retained_claims": 0,
        "retained_visuals": 0,
        "retained_visual_weight": 0.0,
        "dropped_sections": [],
    }]

    for section_index, section in enumerate(ordered):
        expanded = []
        section_id = str(section["section_id"])
        section_claim_ids = {
            str(item) for item in section.get("claim_ids", [])
        }
        section_visual_ids = {
            str(item.get("visual_id"))
            for item in section.get("visual_assets", [])
            if isinstance(item, dict) and item.get("visual_id")
        }
        required_claims = section_claim_ids.intersection(must_retain_claim_ids)
        required_visuals = section_visual_ids.intersection(must_retain_visual_ids)
        required_zone = required_section_zones.get(section_id)
        for partial in beam:
            for zone_id, geometry in zone_geometry.items():
                if required_zone and zone_id != required_zone:
                    blocked("required_zone")
                    continue
                required_roles = active_semantic_zones.get(zone_id)
                if (
                    required_roles
                    and section_roles.get(section_id) not in required_roles
                ):
                    blocked("semantic_role")
                    continue
                assigned = partial["assignments"][zone_id]
                if len(assigned) >= geometry["capacity"]:
                    blocked("zone_capacity")
                    continue
                for option in option_cache[(section_id, zone_id)]:
                    option_claims = {
                        str(item) for item in option["section"].get("claim_ids", [])
                    }
                    option_visuals = {
                        str(item.get("visual_id"))
                        for item in option["section"].get("visual_assets", [])
                        if isinstance(item, dict) and item.get("visual_id")
                    }
                    if not required_claims.issubset(option_claims):
                        blocked("required_claim")
                        continue
                    if not required_visuals.issubset(option_visuals):
                        blocked("required_visual")
                        continue
                    spacing = gap if assigned else 0.0
                    resulting = (
                        partial["heights"][zone_id]
                        + spacing
                        + float(option["height"])
                    )
                    if resulting > geometry["height"] * hard_max + 1e-6:
                        blocked("estimated_height")
                        sample = {
                            "section_id": section_id,
                            "zone_id": zone_id,
                            "estimated_used_in": round(resulting, 3),
                            "zone_limit_in": round(
                                geometry["height"] * hard_max, 3
                            ),
                            "placed_section_count": len(partial["selected"]),
                            "option_claim_count": int(option["retained_claims"]),
                            "option_visual_count": int(option["retained_visuals"]),
                            "option_claim_ids": list(
                                option["section"].get("claim_ids") or []
                            ),
                            "option_visual_ids": [
                                str(item.get("visual_id"))
                                for item in option["section"].get("visual_assets") or []
                                if isinstance(item, dict) and item.get("visual_id")
                            ],
                            "prior_zone_used_in": round(
                                partial["heights"][zone_id], 3
                            ),
                            "height_components": dict(
                                option.get("height_components") or {}
                            ),
                        }
                        _record_pressure_sample(
                            diagnostics, sample, closest=False
                        )
                        _record_pressure_sample(
                            diagnostics, sample, closest=True
                        )
                        _record_pressure_sample(
                            diagnostics, sample, progress=True
                        )
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
                    candidate["retained_visual_weight"] += sum(
                        visual_weights.get(str(visual.get("visual_id")), 1.0)
                        for visual in chosen.get("visual_assets") or []
                        if isinstance(visual, dict) and visual.get("visual_id")
                    )
                    expanded.append(candidate)
            remaining = len(ordered) - section_index - 1
            can_drop = not (
                required_zone or required_claims or required_visuals
            )
            if can_drop and len(partial["selected"]) + remaining >= minimum_sections:
                candidate = deepcopy(partial)
                candidate["dropped_sections"].append(section_id)
                expanded.append(candidate)

        if not expanded:
            diagnostics["reason_code"] = "ASSIGNMENT_EXHAUSTED"
            diagnostics["first_unplaced_section_id"] = section_id
            return None

        def partial_score(item: Dict[str, Any]) -> Tuple[float, float, float]:
            coverage = item["retained_claims"] / max(total_claims, 1)
            visual = priority_visual_coverage(item)
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
            return coverage + 0.2 * visual + hero_bonus, fit, -len(
                item["dropped_sections"]
            )

        expanded.sort(key=partial_score, reverse=True)
        beam = expanded[:beam_width]
        if total_visuals and beam_width > 1:
            # Reserve one slot for a paper-approved visual-rich path.  The
            # ordinary high-claim beam remains available when imagery cannot
            # fit this family; the branch is not an image-count hard gate.
            visual_best = max(
                expanded,
                key=lambda item: (priority_visual_coverage(item), partial_score(item)),
            )
            if all(visual_best is not item for item in beam):
                beam[-1] = visual_best

    completed = [
        item for item in beam
        if len(item["selected"]) >= minimum_sections
        and (not hero_id or item["assignments"].get(hero_id))
    ]
    if not completed:
        diagnostics["reason_code"] = "MIN_SECTIONS_OR_ANCHOR_UNMET"
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
        return coverage + 0.2 * priority_visual_coverage(item), fit, balance, variant["variant_id"]

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
    requested_order = [
        str(item) for item in constraints.get("reading_order", [])
    ]
    assigned_section_ids = {
        str(item)
        for zone in spec.get("zones", [])
        for item in zone.get("section_ids", [])
    }
    if requested_order and set(requested_order) == assigned_section_ids:
        spec["reading_order"] = requested_order
    requested_anchor = str(constraints.get("primary_anchor_zone") or "")
    if requested_anchor and requested_anchor in {
        str(zone.get("zone_id")) for zone in spec.get("zones", [])
    }:
        spec["primary_anchor_zone"] = requested_anchor

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
    if not must_retain_claim_ids.issubset(retained_claim_ids):
        diagnostics["reason_code"] = "REQUIRED_CLAIMS_NOT_RETAINED"
        return None
    if not must_retain_visual_ids.issubset(retained_visual_ids):
        diagnostics["reason_code"] = "REQUIRED_VISUALS_NOT_RETAINED"
        return None
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


@measured_phase("family_fit")
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
    repair_overage_limit = max(0.0, float(
        ((config or {}).get("capacity_repair") or {}).get(
            "max_repairable_overflow_inches", 2.0
        )
    ))
    mode = str((state.get("iteration_context") or {}).get("portfolio_mode") or "")
    if mode == "improve":
        settings.update((config or {}).get("improve_layout", {}))
    registry = LayoutFamilyRegistry()
    family = registry.get(family_id)
    seed = int((state.get("iteration_context") or {}).get("random_seed", 0))
    maximum = int(settings.get("max_geometry_candidates_per_family", 4))
    adaptive_maximum = (
        max(maximum, min(12, int(settings.get("max_adaptive_geometry_candidates", 12))))
        if mode == "explore" and fixed_zones is None else maximum
    )
    if fixed_zones is not None:
        zones = [dict(item) for item in fixed_zones]
        variants = [{
            "variant_id": f"{family_id}_{_fingerprint(zones)}",
            "variant_label": "strict_fixed_topology",
            "geometry_fingerprint": _fingerprint(zones),
            "zones": zones,
            "mutation_trace": [],
        }]
    elif mode == "improve":
        parent_spec = state.get("revision_parent_layout_spec") or {}
        parent_zones = deepcopy(parent_spec.get("zones") or [])
        if (
            str(parent_spec.get("family_id") or "") != family_id
            or not _valid_zones(parent_zones)
        ):
            reason = "Improve requires a valid same-family parent LayoutSpec"
            raise LayoutFeasibilityError(reason, _failure_report(
                family_id=family_id,
                reason=reason,
                reason_code="INVALID_PARENT_LAYOUT_SPEC",
                failure_stage="parent_validation",
                trials=[], settings=settings, board=board,
                feasible_count=0,
            ))
        parent_fingerprint = str(
            parent_spec.get("geometry_fingerprint") or _fingerprint(parent_zones)
        )
        parent_variant = {
            "variant_id": f"{family_id}_parent_{parent_fingerprint[:12]}",
            "variant_label": "improve_parent_geometry",
            "geometry_fingerprint": parent_fingerprint,
            "zones": parent_zones,
            "mutation_trace": [],
        }
        variants = [parent_variant]
        if not state.get("improve_safe_fallback"):
            local_maximum = max(
                1, int(settings.get("local_geometry_candidates", maximum))
            )
            generated = generate_zone_variants(
                family,
                random_seed=seed,
                maximum=max(local_maximum * 2, maximum),
            )
            parent_by_id = {
                str(zone.get("zone_id")): zone for zone in parent_zones
            }

            def local_distance(candidate: Dict[str, Any]) -> tuple:
                distance = 0.0
                for zone in candidate.get("zones", []):
                    parent = parent_by_id.get(str(zone.get("zone_id")))
                    if parent is None:
                        return (float("inf"), str(candidate.get("variant_id")))
                    distance += sum(
                        abs(float(zone.get(key, 0.0)) - float(parent.get(key, 0.0)))
                        for key in ("x", "y", "width", "height")
                    )
                return (distance, str(candidate.get("variant_id")))

            generated = sorted(generated, key=local_distance)
            for candidate in generated:
                if candidate.get("geometry_fingerprint") == parent_fingerprint:
                    continue
                variants.append(candidate)
                if len(variants) >= local_maximum:
                    break
    else:
        variants = generate_zone_variants(
            family, random_seed=seed, maximum=adaptive_maximum
        )
        first_pass_count = min(maximum, len(variants))
        generated_count = len(variants)
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
                or not valid_family_topology(family, zones)
            ):
                continue
            variants.append(deepcopy(runtime_variant))
            known.add(fingerprint)

    if fixed_zones is not None or mode == "improve":
        first_pass_count = len(variants)
        generated_count = len(variants)
    initial_variants = [
        *variants[:first_pass_count], *variants[generated_count:]
    ]
    adaptive_variants = variants[first_pass_count:generated_count]

    trials = []
    feasible = []
    measurement_cache: Dict[
        Tuple[Any, ...], List[Dict[str, Any]]
    ] = {}
    exact_candidates = []
    exact_checked = 0
    near_miss_checked = 0
    exact_limit = max(1, int(settings.get("max_exact_candidates", 8)))
    near_limit = max(0, int(settings.get("max_near_miss_rechecks", 2)))
    reserved_exact = min(near_limit, max(0, exact_limit - 1))
    normal_exact_limit = exact_limit - reserved_exact
    measurements = current_context()
    if measurements:
        measurements.emit("geometry search", candidates=len(variants), initial=len(initial_variants),
                          exact_limit=exact_limit)
    trials_by_fingerprint: Dict[str, Dict[str, Any]] = {}
    variants_by_fingerprint = {
        item["geometry_fingerprint"]: item for item in variants
    }

    def search_batch(batch: Sequence[Dict[str, Any]]) -> None:
        for variant in batch:
            diagnostics: Dict[str, Any] = {}
            search_path = "standard_beam"
            result = _fit_one_variant(
                agent, board, state, family, variant, settings,
                measurement_cache, diagnostics,
            )
            adaptive_width = max(
                int(settings.get("beam_width", 4)),
                int(settings.get("adaptive_beam_width", 8)),
            )
            if result is None and adaptive_width > int(settings.get("beam_width", 4)):
                adaptive_settings = {**settings, "beam_width": adaptive_width}
                adaptive_diagnostics: Dict[str, Any] = {}
                result = _fit_one_variant(
                    agent, board, state, family, variant, adaptive_settings,
                    measurement_cache, adaptive_diagnostics,
                )
                if result is not None:
                    search_path = "adaptive_beam"
                diagnostics["adaptive_beam_width"] = adaptive_width
                diagnostics["adaptive_result"] = (
                    "feasible" if result is not None else adaptive_diagnostics.get("reason_code")
                )
                if result is None:
                    diagnostics["adaptive_blockers"] = adaptive_diagnostics.get(
                        "observed_blockers", {}
                    )
                    for sample in adaptive_diagnostics.get("height_pressure") or []:
                        _record_pressure_sample(
                            diagnostics, sample, closest=False
                        )
                    for sample in (
                        adaptive_diagnostics.get("near_miss_pressure")
                        or adaptive_diagnostics.get("height_pressure")
                        or []
                    ):
                        _record_pressure_sample(
                            diagnostics, sample, closest=True
                        )
                    for sample in adaptive_diagnostics.get("progress_pressure") or []:
                        _record_pressure_sample(
                            diagnostics, sample, progress=True
                        )
            if result is not None:
                result["fast_search_provenance"] = {
                    "path": search_path,
                    "safety_factor": float(
                        settings.get("fast_measurement_safety_factor", 1.20)
                    ),
                }
            trial = {
                "variant_id": variant["variant_id"],
                "geometry_fingerprint": variant["geometry_fingerprint"],
                "mutation_trace": list(variant.get("mutation_trace") or []),
                "feasible": result is not None,
                "max_physical_utilization": (
                    result.get("max_physical_utilization") if result else None
                ),
                "diagnostics": diagnostics if result is None else {},
            }
            trials.append(trial)
            trials_by_fingerprint[variant["geometry_fingerprint"]] = trial
            if result is not None:
                feasible.append(result)

    def refine_candidates(candidates: Sequence[Dict[str, Any]], limit: int) -> None:
        nonlocal exact_checked
        for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
            if exact_checked >= limit:
                break
            trial = trials_by_fingerprint[candidate["variant"]["geometry_fingerprint"]]
            if "exact_status" in trial:
                continue
            exact_checked += 1
            if measurements:
                measurements.emit("exact candidate", candidate=exact_checked, limit=exact_limit)
            exact_diagnostics: Dict[str, Any] = {}
            refined = _exact_refine_candidate(
                agent, candidate, board, state, settings,
                allow_changes=not bool(state.get("improve_safe_fallback")),
                diagnostics=exact_diagnostics,
            )
            trial["exact_status"] = "feasible" if refined else "rejected"
            if exact_diagnostics:
                trial["exact_diagnostics"] = exact_diagnostics
            if refined is not None:
                exact_candidates.append(refined)

    search_batch(initial_variants)
    refine_candidates(feasible, normal_exact_limit)
    initial_best = max(exact_candidates, key=lambda item: item["exact_score"], default=None)
    body_line_height = float(agent.config["typography"]["sizes"]["body_text"]) / 72.0 if hasattr(agent, "config") else 44.0 / 72.0
    expand_sparse = bool(
        initial_best is None
        or initial_best["worst_zone_utilization"] < 0.90
        or initial_best["largest_bottom_gap_inches"] > max(1.5, 2.5 * body_line_height)
    )
    if adaptive_variants and expand_sparse:
        if measurements:
            measurements.emit("geometry search expanded", additional=len(adaptive_variants))
        search_batch(adaptive_variants)
        refine_candidates(feasible, normal_exact_limit)

    near_candidates = []
    maximum_overage = float(settings.get("near_miss_max_overflow_inches", 2.0))
    for trial in trials:
        if trial["feasible"]:
            continue
        diagnostics = trial.get("diagnostics") or {}
        samples = [
            *(diagnostics.get("near_miss_pressure") or []),
            *(diagnostics.get("progress_pressure") or []),
        ] or diagnostics.get("height_pressure", [])
        eligible = [
            item for item in samples
            if 0 < _pressure_overage(item) <= maximum_overage
        ]
        if not eligible:
            continue
        best = min(eligible, key=lambda item: (
            -int(item.get("placed_section_count", 0)),
            _pressure_overage(item),
            -int(item.get("option_claim_count", 0)),
            str(item.get("section_id")), str(item.get("zone_id")),
        ))
        near_candidates.append((
            -int(best.get("placed_section_count", 0)),
            _pressure_overage(best),
            -int(best.get("option_claim_count", 0)),
            trial["geometry_fingerprint"],
        ))
    near_candidates.sort()
    relaxed_results = []
    if expand_sparse and hasattr(agent, "config"):
        adaptive_width = max(
            int(settings.get("beam_width", 4)),
            int(settings.get("adaptive_beam_width", 8)),
        )
        for _, _, _, fingerprint in near_candidates[:near_limit]:
            near_miss_checked += 1
            trial = trials_by_fingerprint[fingerprint]
            relaxed_diagnostics: Dict[str, Any] = {}
            result = _fit_one_variant(
                agent, board, state, family,
                variants_by_fingerprint[fingerprint],
                {
                    **settings,
                    "beam_width": adaptive_width,
                    "fast_measurement_safety_factor": 1.0,
                },
                measurement_cache, relaxed_diagnostics,
            )
            trial["diagnostics"]["near_miss_rechecked"] = True
            trial["diagnostics"]["near_miss_result"] = (
                "fast_feasible_pending_exact_compile"
                if result is not None else relaxed_diagnostics.get("reason_code")
            )
            if result is not None:
                result["fast_search_provenance"] = {
                    "path": "near_miss_recheck",
                    "safety_factor": 1.0,
                }
                trial["feasible"] = True
                trial["max_physical_utilization"] = result.get(
                    "max_physical_utilization"
                )
                feasible.append(result)
                relaxed_results.append(result)
    refine_candidates(relaxed_results, exact_limit)
    refine_candidates(feasible, exact_limit)
    if not feasible:
        reason = f"No capacity-safe {family_id} variant was found"
        raise LayoutFeasibilityError(reason, _failure_report(
            family_id=family_id,
            reason=reason,
            reason_code="NO_FAST_FEASIBLE_VARIANT",
            failure_stage="fast_assignment",
            trials=trials,
            settings=settings,
            board=board,
            feasible_count=0,
            near_miss_rechecks=near_miss_checked,
            repair_overage_limit=repair_overage_limit,
        ))
    if not exact_candidates:
        reason = f"No exactly compilable {family_id} variant was found"
        raise LayoutFeasibilityError(reason, _failure_report(
            family_id=family_id,
            reason=reason,
            reason_code="NO_EXACT_COMPILABLE_VARIANT",
            failure_stage="exact_compile_or_preflight",
            trials=trials,
            settings=settings,
            board=board,
            feasible_count=len(feasible),
            near_miss_rechecks=near_miss_checked,
            repair_overage_limit=repair_overage_limit,
        ))
    if mode == "improve" and state.get("revision_contract"):
        from src.agents.revision_contract import check_contract, deletion_guard
        safe_candidates = [item for item in exact_candidates if
            check_contract(state, item["board"])["passed"]
            and deletion_guard(state, {
                "composition_whitespace": item.get("composition_whitespace"),
                "zone_utilization": item.get("exact_utilization"),
                "exact_bottom_gaps": item.get("exact_bottom_gaps"),
            })["passed"]]
        # If none is safe, return the best measured candidate to the bounded
        # rollback path; do not hide the regression as a generic fit failure.
        if safe_candidates:
            exact_candidates = safe_candidates
    exact_candidates.sort(
        key=lambda item: (
            item["exact_score"],
            item["score"],
            item["variant"]["variant_id"],
        ),
        reverse=True,
    )
    best_exact_score = exact_candidates[0]["exact_score"]
    score_window = max(
        0.0, min(0.15, float(settings.get("exact_diversity_score_window", 0.035)))
    )
    top_k = [
        item for item in exact_candidates
        if item["exact_score"] >= best_exact_score - score_window
        and no_displaced_whitespace(
            exact_candidates[0].get("composition_whitespace") or {},
            item.get("composition_whitespace") or {},
        )
    ][: max(1, int(settings.get("diverse_top_k", 3)))]
    # Seeded selection only among near-best exact candidates preserves
    # diversity without choosing a visibly sparse variant for novelty alone.
    chosen = (
        exact_candidates[0]
        if mode == "improve"
        else random.Random(seed + 7919).choice(top_k)
    )
    report = {
        "schema_version": FIT_SCHEMA_VERSION,
        "status": "feasible",
        "family_id": family_id,
        "search_scope": (
            "parent_exact_fallback"
            if mode == "improve" and state.get("improve_safe_fallback")
            else "parent_local"
            if mode == "improve"
            else "strict_fixed_topology"
            if fixed_zones is not None
            else "family_exploration"
        ),
        "variant_id": chosen["variant"]["variant_id"],
        "geometry_fingerprint": chosen["variant"]["geometry_fingerprint"],
        "mutation_trace": list(chosen["variant"].get("mutation_trace") or []),
        "trials": trials,
        "trial_count": len(trials),
        "initial_variant_count": len(initial_variants),
        "adaptive_expanded": bool(adaptive_variants and expand_sparse),
        "feasible_count": len(feasible),
        "exact_feasible_count": len(exact_candidates),
        "near_miss_rechecks": near_miss_checked,
        "near_miss_candidate_count": len(near_candidates),
        "estimated_zone_utilization": chosen["utilization"],
        "zone_utilization": chosen["exact_utilization"],
        "exact_bottom_gaps": chosen["exact_bottom_gaps"],
        "worst_zone_utilization": chosen["worst_zone_utilization"],
        "largest_bottom_gap_inches": chosen["largest_bottom_gap_inches"],
        "body_line_height_inches": body_line_height,
        "composition_whitespace": chosen.get("composition_whitespace") or {},
        "exact_candidate_summaries": [
            {
                "variant_id": item["variant"]["variant_id"],
                "exact_score": item["exact_score"],
                "visible_visual_ids": (item.get("candidate_content_selection") or {}).get("visible_visual_ids", []),
                "worst_zone_utilization": item["worst_zone_utilization"],
                "composition_whitespace": item.get("composition_whitespace") or {},
            }
            for item in exact_candidates[:exact_limit]
        ],
        "search_scoring_version": "multifamily_composition_v1",
        "restored_content": chosen["restored_content"],
        "zone_budget_preferences_met": chosen[
            "zone_budget_preferences_met"
        ],
        "exact_score": chosen["exact_score"],
        "max_physical_utilization": max(
            chosen["exact_utilization"].values() or [0.0]
        ),
        "candidate_content_selection": chosen[
            "candidate_content_selection"
        ],
        "search_measurement": {
            "method": "conservative_search_then_exact_refill_and_compile",
            # Compatibility: this historical field denotes the configured
            # default, not necessarily the selected candidate's search path.
            "safety_factor": float(
                settings.get("fast_measurement_safety_factor", 1.20)
            ),
            "safety_factor_scope": "configured_default",
            "selected_candidate_safety_factor": float(
                (chosen.get("fast_search_provenance") or {}).get(
                    "safety_factor",
                    settings.get("fast_measurement_safety_factor", 1.20),
                )
            ),
            "selected_candidate_path": (
                (chosen.get("fast_search_provenance") or {}).get("path")
                or "standard_beam"
            ),
            "selected_from_near_miss_recheck": (
                (chosen.get("fast_search_provenance") or {}).get("path")
                == "near_miss_recheck"
            ),
            "final_exact_compile_required": True,
            "exact_candidates_checked": exact_checked,
        },
    }
    chosen["layout_spec"]["iteration_random_seed"] = seed
    return chosen["board"], chosen["layout_spec"], report


def validate_intra_section_layout(
    layout: Sequence[Dict[str, Any]],
    *,
    tolerance: float = 0.01,
) -> List[Dict[str, Any]]:
    """Validate child ownership, containment, title height, and flow overlap."""

    issues: List[Dict[str, Any]] = []
    containers = {
        str(item.get("section_id")): item
        for item in layout
        if item.get("type") == "section_container" and item.get("section_id")
    }
    flow_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for element in layout:
        element_type = str(element.get("type") or "")
        section_id = str(element.get("section_id") or "")
        if not section_id or element_type == "section_container":
            continue
        container = containers.get(section_id)
        if container is None:
            issues.append({
                "code": "PREFLIGHT_SECTION_CONTAINER_MISSING",
                "section_id": section_id,
                "element_type": element_type,
            })
            continue
        try:
            x, y, width, height = (
                float(element[key]) for key in ("x", "y", "width", "height")
            )
            cx, cy, cwidth, cheight = (
                float(container[key]) for key in ("x", "y", "width", "height")
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            x < cx - tolerance
            or y < cy - tolerance
            or x + width > cx + cwidth + tolerance
            or y + height > cy + cheight + tolerance
        ):
            issues.append({
                "code": "PREFLIGHT_SECTION_CHILD_BOUNDS",
                "section_id": section_id,
                "element_type": element_type,
                "box": [x, y, width, height],
                "container_box": [cx, cy, cwidth, cheight],
            })
        child_zone = str(element.get("zone_id") or "")
        container_zone = str(container.get("zone_id") or "")
        if child_zone and container_zone and child_zone != container_zone:
            issues.append({
                "code": "PREFLIGHT_CHILD_ZONE_MISMATCH",
                "section_id": section_id,
                "element_type": element_type,
                "zone_id": child_zone,
                "container_zone_id": container_zone,
            })
        if element_type == "section_title":
            try:
                required = float(element.get("required_text_height"))
            except (TypeError, ValueError):
                required = height
            if height + tolerance < required:
                issues.append({
                    "code": "PREFLIGHT_TITLE_HEIGHT",
                    "section_id": section_id,
                    "height": height,
                    "required_text_height": required,
                })
        if element_type in {"section_title", "visual", "text"}:
            flow_by_section.setdefault(section_id, []).append(element)

    for section_id, elements in flow_by_section.items():
        for index, first in enumerate(elements):
            for second in elements[index + 1:]:
                try:
                    ax, ay, aw, ah = (
                        float(first[key]) for key in ("x", "y", "width", "height")
                    )
                    bx, by, bw, bh = (
                        float(second[key]) for key in ("x", "y", "width", "height")
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                overlaps = not (
                    ax + aw <= bx + tolerance
                    or bx + bw <= ax + tolerance
                    or ay + ah <= by + tolerance
                    or by + bh <= ay + tolerance
                )
                if overlaps:
                    issues.append({
                        "code": "PREFLIGHT_SECTION_CHILD_OVERLAP",
                        "section_id": section_id,
                        "first_type": first.get("type"),
                        "second_type": second.get("type"),
                    })
    return issues


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
    issues = validate_intra_section_layout(layout, tolerance=tolerance)
    if state.get("generation_route") == "optimization_family":
        try:
            family = LayoutFamilyRegistry().get(
                str(layout_spec.get("family_id") or "")
            )
            valid_topology = valid_family_topology(
                family, layout_spec.get("zones") or []
            )
        except ValueError:
            valid_topology = False
        if not valid_topology:
            issues.append({
                "code": "PREFLIGHT_FAMILY_TOPOLOGY_INVALID",
                "family_id": layout_spec.get("family_id"),
            })
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
        "schema_version": COMPILED_PREFLIGHT_SCHEMA_VERSION,
        "passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "family_id": layout_spec.get("family_id"),
        "variant_id": layout_spec.get("variant_id"),
        "geometry_fingerprint": layout_spec.get("geometry_fingerprint"),
    }
