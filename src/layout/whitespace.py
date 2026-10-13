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


def module_adjacencies(layout: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Directional physical neighbors; side neighbors cannot mask vertical gaps.

    Intervening modules subtract their covered corridor intervals. Exposed
    spans below 20% are terminal slivers, measured by empty-area/bottom metrics
    instead of a misleading full-width adjacency.
    """
    modules = [item for item in layout if item.get("type") == "section_container"]
    result = []
    for first in modules:
        for second in modules:
            if first is second:
                continue
            ax, ay, aw, ah = (float(first[key]) for key in ("x", "y", "width", "height"))
            bx, by, bw, bh = (float(second[key]) for key in ("x", "y", "width", "height"))
            for axis, lo, hi, end, start in (
                ("vertical", max(ax, bx), min(ax + aw, bx + bw), ay + ah, by),
                ("horizontal", max(ay, by), min(ay + ah, by + bh), ax + aw, bx),
            ):
                if hi - lo <= 0.01 or start < end - 1e-6:
                    continue
                exposed = [(lo, hi)]
                for other in modules:
                    if other is first or other is second:
                        continue
                    ox, oy, ow, oh = (float(other[key]) for key in ("x", "y", "width", "height"))
                    cross_lo, cross_hi, along_lo, along_hi = (
                        (ox, ox + ow, oy, oy + oh) if axis == "vertical"
                        else (oy, oy + oh, ox, ox + ow)
                    )
                    if along_lo < start and along_hi > end:
                        remaining = []
                        for left, right in exposed:
                            if cross_hi <= left or cross_lo >= right:
                                remaining.append((left, right))
                            else:
                                if cross_lo > left:
                                    remaining.append((left, min(cross_lo, right)))
                                if cross_hi < right:
                                    remaining.append((max(cross_hi, left), right))
                        exposed = remaining
                exposed_span = sum(right - left for left, right in exposed)
                # Tiny terminal slivers belong to bottom/empty-area metrics,
                # not a false full-height "gap" through intervening modules.
                if exposed_span >= max(0.01, (hi - lo) * 0.20):
                    result.append({
                        "axis": axis, "after_section_id": str(first.get("section_id") or ""),
                        "before_section_id": str(second.get("section_id") or ""),
                        "after_zone_id": str(first.get("zone_id") or ""),
                        "before_zone_id": str(second.get("zone_id") or ""),
                        "cross_zone": first.get("zone_id") != second.get("zone_id"),
                        "gap_inches": round(max(0.0, start - end), 4),
                        "shared_span_inches": round(exposed_span, 4),
                        "projection_span_inches": round(hi - lo, 4),
                    })
    return result


def visible_module_envelopes(layout, rendered_boxes=()):
    """Use uniquely measured glyphs where available, planned children otherwise."""
    actual = {str(item["element_id"]): item["rendered_box_inches"] for item in rendered_boxes}
    result = []
    for container in layout:
        if container.get("type") != "section_container":
            continue
        children = [item for item in layout if item.get("section_id") == container.get("section_id")
                    and item.get("type") in {"section_title", "text", "visual"}]
        boxes = []
        for item in children:
            identity = str(item.get("id") or (str(item.get("section_id")) + "_title"
                           if item.get("type") == "section_title" else item.get("section_id") or ""))
            rendered = actual.get(identity) if item.get("type") in {"text", "section_title"} else None
            boxes.append(rendered or [float(item["x"]), float(item["y"]),
                         float(item["x"]) + float(item["width"]), float(item["y"]) + float(item["height"])])
        if boxes:
            top, bottom = min(box[1] for box in boxes), max(box[3] for box in boxes)
            result.append({**container, "y": top, "height": bottom - top})
        else:
            result.append(dict(container))
    return result


def _bottom_edges(body, modules):
    xs = sorted({body[0], body[2], *(edge for _, rect in modules for edge in (rect[0], rect[2]))})
    gaps = []
    for left, right in zip(xs, xs[1:]):
        occupied = [rect for _, rect in modules if rect[0] < right and rect[2] > left]
        if occupied:
            gaps.append((right - left, max(0.0, body[3] - max(rect[3] for rect in occupied))))
    span = sum(width for width, _ in gaps)
    return {
        "mean_terminal_bottom_gap_inches": round(sum(width * gap for width, gap in gaps) / span, 4) if span else None,
        "maximum_terminal_bottom_gap_inches": round(max((gap for _, gap in gaps), default=0.0), 4),
        "full_width_bottom_gap_inches": round(max(0.0, body[3] - max((rect[3] for _, rect in modules), default=body[1])), 4),
        "bottom_edge_coverage_fraction": round(span / max(0.1, body[2] - body[0]), 6),
    }


def measure_composition_whitespace(
    spec: Dict[str, Any],
    layout: Sequence[Dict[str, Any]],
    *,
    poster_width: float,
    poster_height: float,
    poster_margin: float,
    title_height_fraction: float,
    rendered_boxes: Sequence[Dict[str, Any]] = (),
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
    adjacency = module_adjacencies(layout)
    cross = [item["gap_inches"] for item in adjacency if item["cross_zone"]]
    visible = visible_module_envelopes(layout, rendered_boxes)
    visible_adjacency = module_adjacencies(visible)
    by_id = {str(item.get("section_id")): item for item in layout if item.get("type") == "section_container"}
    visible_by_id = {str(item.get("section_id")): item for item in visible}
    zones = {str(zone.get("zone_id")): zone for zone in spec.get("zones") or []}
    for item in visible_adjacency:
        if item["axis"] != "vertical" or not item["cross_zone"]:
            continue
        upper = by_id[item["after_section_id"]]
        lower = by_id[item["before_section_id"]]
        first = zones.get(item["after_zone_id"])
        second = zones.get(item["before_zone_id"])
        if not first or not second or not {"y", "height"}.issubset(first) or "y" not in second:
            item["gap_decomposition_status"] = "zone_geometry_unavailable"
            continue
        content = visible_by_id[item["after_section_id"]]
        next_content = visible_by_id[item["before_section_id"]]
        container_bottom = float(upper["y"]) + float(upper["height"])
        content_bottom = float(content["y"]) + float(content["height"])
        zone_bottom = body[1] + (float(first["y"]) + float(first["height"])) * body_height
        next_zone_top = body[1] + float(second["y"]) * body_height
        item["gap_decomposition"] = {
            "content_box_tail_inches": round(container_bottom - content_bottom, 4),
            "unused_upper_zone_inches": round(zone_bottom - container_bottom, 4),
            "zone_gutter_inches": round(next_zone_top - zone_bottom, 4),
            "lower_module_offset_inches": round(float(lower["y"]) - next_zone_top, 4),
            "lower_visible_inset_inches": round(float(next_content["y"]) - float(lower["y"]), 4),
        }
    return {
        "schema_version": 2,
        "measurement_source": "compiled_section_containers",
        "body_area_square_inches": round(body_area, 4),
        "unallocated_body_fraction": round(max(0.0, 1.0 - min(1.0, zone_area)), 6),
        "largest_empty_rectangle_fraction": round(
            _largest_empty_rectangle(body, occupied) / body_area, 6
        ),
        "largest_cross_zone_gap_inches": round(max(cross, default=0.0), 4),
        "largest_vertical_gap_inches": max((item["gap_inches"] for item in adjacency if item["axis"] == "vertical"), default=0.0),
        "largest_horizontal_gap_inches": max((item["gap_inches"] for item in adjacency if item["axis"] == "horizontal"), default=0.0),
        "module_adjacencies": adjacency,
        "visible_module_adjacencies": visible_adjacency,
        "visible_bounds_source": "mixed_rendered_glyphs_and_planned_children" if rendered_boxes else "planned_children",
        "rendered_text_count": len(rendered_boxes),
        **_bottom_edges(body, _rectangles(visible, body)),
        "largest_within_zone_gap_inches": round(max(internal_gaps, default=0.0), 4),
        "visible_module_count": len(modules),
    }


def no_displaced_whitespace(
    before: Dict[str, Any], after: Dict[str, Any], *, tolerance: float = 0.01,
    gap_tolerance_inches: float = 0.35,
) -> bool:
    """A local density gain must not create a materially worse global hole."""

    existing = (
        float(after.get("unallocated_body_fraction", 0.0))
        <= float(before.get("unallocated_body_fraction", 0.0)) + tolerance
        and float(after.get("largest_empty_rectangle_fraction", 0.0))
        <= float(before.get("largest_empty_rectangle_fraction", 0.0)) + tolerance
        and float(after.get("largest_cross_zone_gap_inches", 0.0))
        <= float(before.get("largest_cross_zone_gap_inches", 0.0)) + gap_tolerance_inches
        and float(after.get("largest_within_zone_gap_inches", 0.0))
        <= float(before.get("largest_within_zone_gap_inches", 0.0)) + gap_tolerance_inches
    )
    # Compare new observations only when both sides measured them. Missing
    # historical evidence is never manufactured as a zero-width bottom gap.
    return existing and all(
        float(after[key]) <= float(before[key]) + gap_tolerance_inches
        for key in ("largest_vertical_gap_inches", "largest_horizontal_gap_inches",
                    "mean_terminal_bottom_gap_inches", "maximum_terminal_bottom_gap_inches",
                    "full_width_bottom_gap_inches")
        if before.get(key) is not None and after.get(key) is not None
    )
