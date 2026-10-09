"""Text-free, exact-geometry whitespace measurements for loop layouts.

The body, zones, and section containers are measured in inches.  The largest
empty rectangle is measured against *visible module containers*, rather than
against zone boundaries: shrinking a zone cannot make an empty patch disappear
merely by moving it outside the zone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


Rect = Tuple[float, float, float, float]


def _clipped(rect: Rect, body: Rect) -> Rect | None:
    x1 = max(rect[0], body[0])
    y1 = max(rect[1], body[1])
    x2 = min(rect[2], body[2])
    y2 = min(rect[3], body[3])
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


def _rectangles(layout: Sequence[Dict[str, Any]], body: Rect) -> List[Tuple[str, Rect]]:
    result = []
    for item in layout:
        if item.get("type") != "section_container" or not item.get("section_id"):
            continue
        try:
            x, y = float(item["x"]), float(item["y"])
            width, height = float(item["width"]), float(item["height"])
        except (KeyError, TypeError, ValueError):
            continue
        clipped = _clipped((x, y, x + width, y + height), body)
        if clipped:
            result.append((str(item.get("zone_id") or ""), clipped))
    return result


def _largest_empty_rectangle(body: Rect, occupied: Sequence[Rect]) -> float:
    xs = sorted({body[0], body[2], *(edge for rect in occupied for edge in (rect[0], rect[2]))})
    ys = sorted({body[1], body[3], *(edge for rect in occupied for edge in (rect[1], rect[3]))})
    if len(xs) < 2 or len(ys) < 2:
        return 0.0
    free = []
    for left, right in zip(xs, xs[1:]):
        column = []
        for top, bottom in zip(ys, ys[1:]):
            column.append(not any(
                rect[0] < right and rect[2] > left
                and rect[1] < bottom and rect[3] > top
                for rect in occupied
            ))
        free.append(column)
    largest = 0.0
    for left in range(len(free)):
        rows = [True] * (len(ys) - 1)
        for right in range(left, len(free)):
            rows = [a and b for a, b in zip(rows, free[right])]
            start = None
            for index in range(len(rows) + 1):
                if index < len(rows) and rows[index]:
                    if start is None:
                        start = index
                elif start is not None:
                    largest = max(
                        largest,
                        (xs[right + 1] - xs[left]) * (ys[index] - ys[start]),
                    )
                    start = None
    return largest


def _nearest_cross_zone_gap(modules: Sequence[Tuple[str, Rect]]) -> float:
    nearest = []
    for index, (zone, rect) in enumerate(modules):
        candidates = []
        for other_index, (other_zone, other) in enumerate(modules):
            if index == other_index or zone == other_zone:
                continue
            horizontal_overlap = min(rect[2], other[2]) - max(rect[0], other[0])
            vertical_overlap = min(rect[3], other[3]) - max(rect[1], other[1])
            if horizontal_overlap > 0.01:
                gap = max(other[1] - rect[3], rect[1] - other[3])
                if gap >= 0:
                    candidates.append(gap)
            if vertical_overlap > 0.01:
                gap = max(other[0] - rect[2], rect[0] - other[2])
                if gap >= 0:
                    candidates.append(gap)
        if candidates:
            nearest.append(min(candidates))
    return max(nearest, default=0.0)


def measure_composition_whitespace(
    spec: Dict[str, Any],
    layout: Sequence[Dict[str, Any]],
    *,
    poster_width: float,
    poster_height: float,
    poster_margin: float,
    title_height_fraction: float,
) -> Dict[str, Any]:
    """Measure whitespace without rewarding a zone that merely shrank."""

    usable_height = max(0.1, poster_height - 2 * poster_margin)
    body = (
        poster_margin,
        poster_margin + usable_height * title_height_fraction,
        poster_width - poster_margin,
        poster_height - poster_margin,
    )
    body_width = max(0.1, body[2] - body[0])
    body_height = max(0.1, body[3] - body[1])
    body_area = body_width * body_height
    modules = _rectangles(layout, body)
    occupied = [rect for _, rect in modules]
    zone_area = sum(
        max(0.0, float(zone.get("width", 0)))
        * max(0.0, float(zone.get("height", 0)))
        for zone in spec.get("zones") or []
    )
    internal_gaps = []
    for zone in spec.get("zones") or []:
        zone_id = str(zone.get("zone_id") or "")
        ordered = sorted((rect for owner, rect in modules if owner == zone_id), key=lambda r: r[1])
        for before, after in zip(ordered, ordered[1:]):
            internal_gaps.append(max(0.0, after[1] - before[3]))
    return {
        "schema_version": 1,
        "measurement_source": "compiled_section_containers",
        "body_area_square_inches": round(body_area, 4),
        "unallocated_body_fraction": round(max(0.0, 1.0 - min(1.0, zone_area)), 6),
        "largest_empty_rectangle_fraction": round(
            _largest_empty_rectangle(body, occupied) / body_area, 6
        ),
        "largest_cross_zone_gap_inches": round(_nearest_cross_zone_gap(modules), 4),
        "largest_within_zone_gap_inches": round(max(internal_gaps, default=0.0), 4),
        "visible_module_count": len(modules),
    }


def no_displaced_whitespace(
    before: Dict[str, Any], after: Dict[str, Any], *, tolerance: float = 0.01,
    gap_tolerance_inches: float = 0.35,
) -> bool:
    """A local density gain must not create a materially worse global hole."""

    return (
        float(after.get("unallocated_body_fraction", 0.0))
        <= float(before.get("unallocated_body_fraction", 0.0)) + tolerance
        and float(after.get("largest_empty_rectangle_fraction", 0.0))
        <= float(before.get("largest_empty_rectangle_fraction", 0.0)) + tolerance
        and float(after.get("largest_cross_zone_gap_inches", 0.0))
        <= float(before.get("largest_cross_zone_gap_inches", 0.0)) + gap_tolerance_inches
        and float(after.get("largest_within_zone_gap_inches", 0.0))
        <= float(before.get("largest_within_zone_gap_inches", 0.0)) + gap_tolerance_inches
    )
