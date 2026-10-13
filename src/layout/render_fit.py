"""Check editable body text against LibreOffice's rendered PDF glyph bounds.

Only uniquely and completely matched editable text is hard evidence. Unmatched
or ambiguous PDF fragments remain inconclusive, never a false quality failure.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

from src.layout.render_text_matching import MATCHING_POLICY_VERSION, match_text, normalized


RENDER_FIT_SCHEMA_VERSION = 3


def _normalized(value: Any) -> str:
    return normalized(value)


def _matches(elements, blocks):
    """Compatibility wrapper; callers requiring fragments use match_text."""
    matched, unmatched, _ = match_text(elements, blocks)
    return matched, unmatched


def _overlap(first: Sequence[float], second: Sequence[float]) -> tuple[float, float]:
    return (
        min(first[2], second[2]) - max(first[0], second[0]),
        min(first[3], second[3]) - max(first[1], second[1]),
    )


def evaluate_rendered_boxes(
    layout: Sequence[Dict[str, Any]],
    blocks: Sequence[Sequence[Any]],
    *,
    poster_width: float,
    poster_height: float,
    overflow_tolerance_inches: float = 0.15,
    collision_tolerance_inches: float = 0.05,
    minimum_title_gap_inches: float = 0.20,
    raw_pdf=None,
) -> Dict[str, Any]:
    """Compare high-confidence PDF body blocks with their planned text boxes."""

    matched, unmatched, coverage = match_text(layout, blocks, raw_pdf)
    issues: List[Dict[str, Any]] = []
    internal_gaps = []
    for title in (item for item in matched if item["element_type"] == "section_title"):
        followers = [item for item in layout if item.get("section_id") == title["section_id"]
                     and item.get("type") in {"visual", "text"}]
        if not followers:
            continue
        following = min(followers, key=lambda item: float(item["y"]))
        actual_following = next((item for item in matched if item["element_type"] == "text"
                                 and item["element_id"] == str(following.get("id") or following.get("section_id"))), None)
        known = following.get("type") == "visual" or actual_following is not None
        start = actual_following["rendered_box_inches"][1] if actual_following else float(following["y"])
        gap = round(start - title["rendered_box_inches"][3], 4)
        title_element = next(item for item in layout if item.get("type") == "section_title"
                             and str(item.get("section_id")) == title["section_id"])
        minimum = float(title_element.get("minimum_content_gap_inches", minimum_title_gap_inches))
        record = {"section_id": title["section_id"], "zone_id": title["zone_id"],
                  "gap_inches": gap, "minimum_gap_inches": minimum,
                  "following_type": following.get("type"),
                  "status": "measured" if known else "inconclusive"}
        internal_gaps.append(record)
        if known and gap < minimum - 0.01:
            issues.append({"code": "RENDER_TITLE_CONTENT_GAP", **record,
                           "element_id": title["element_id"]})
    for item in matched:
        x, y, width, height = item["planned_box_inches"]
        actual = item["rendered_box_inches"]
        box_tolerance = min(overflow_tolerance_inches, 0.05) if item["element_type"] == "section_title" else overflow_tolerance_inches
        if actual[2] > x + width + box_tolerance or (
            actual[3] > y + height + box_tolerance
        ):
            issues.append({
                "code": "RENDER_TEXT_BOX_OVERFLOW",
                "element_id": item["element_id"],
                "section_id": item["section_id"],
                "zone_id": item["zone_id"],
                "overflow_right_inches": round(max(0.0, actual[2] - x - width), 4),
                "overflow_bottom_inches": round(max(0.0, actual[3] - y - height), 4),
            })
        if (
            actual[0] < -collision_tolerance_inches
            or actual[1] < -collision_tolerance_inches
            or actual[2] > poster_width + collision_tolerance_inches
            or actual[3] > poster_height + collision_tolerance_inches
        ):
            issues.append({
                "code": "RENDER_TEXT_CANVAS_BOUNDS",
                "element_id": item["element_id"],
                "section_id": item["section_id"],
                "zone_id": item["zone_id"],
            })
        for other in layout:
            if (
                other.get("section_id") == item["section_id"]
                or other.get("type") not in {"section_title", "text", "visual"}
            ):
                continue
            other_box = [
                float(other["x"]), float(other["y"]),
                float(other["x"]) + float(other["width"]),
                float(other["y"]) + float(other["height"]),
            ]
            horizontal, vertical = _overlap(actual, other_box)
            if horizontal > collision_tolerance_inches and vertical > collision_tolerance_inches:
                issues.append({
                    "code": "RENDER_CROSS_SECTION_COLLISION",
                    "element_id": item["element_id"],
                    "section_id": item["section_id"],
                    "other_section_id": other.get("section_id"),
                    "other_element_type": other.get("type"),
                    "zone_id": item["zone_id"],
                    "overlap_width_inches": round(horizontal, 4),
                    "overlap_height_inches": round(vertical, 4),
                })
    return {
        "schema_version": RENDER_FIT_SCHEMA_VERSION,
        **coverage,
        "status": "failed" if issues else "passed" if not unmatched else "partial",
        "passed": not issues,
        "matched_text_count": len(matched),
        "unmatched_text_ids": unmatched,
        "matched_text_boxes": matched,
        "issue_count": len(issues),
        "issues": issues,
        "measurement_source": "libreoffice_pdf_pymupdf",
        "conclusive": not unmatched,
        "internal_title_gaps": internal_gaps,
        "title_gap_coverage": {
            "expected": sum(1 for item in layout if item.get("type") == "section_title"
                            and item.get("section_title") and any(
                                other.get("section_id") == item.get("section_id")
                                and other.get("type") in {"text", "visual"} for other in layout)),
            "measured": sum(item["status"] == "measured" for item in internal_gaps),
        },
    }


def audit_rendered_text(state: Dict[str, Any]) -> Dict[str, Any]:
    """Export a temporary PDF; keep the final PPTX/PNG path unchanged."""

    started = time.perf_counter()
    layout = state.get("styled_layout") or state.get("design_layout") or []

    def unavailable(reason):
        _, unmatched, coverage = match_text(layout, [])
        return {"schema_version": RENDER_FIT_SCHEMA_VERSION, **coverage,
                "matching_policy_version": MATCHING_POLICY_VERSION,
                "status": "unavailable", "passed": True, "conclusive": False,
                "matched_text_count": 0, "matched_text_boxes": [],
                "unmatched_text_ids": unmatched,
                "reason": reason, "issues": [], "issue_count": 0,
                "internal_title_gaps": [], "audit_seconds": round(time.perf_counter() - started, 6)}

    candidate = state.get("current_candidate") or {}
    pptx_path = Path(str(candidate.get("pptx_path") or ""))
    if not pptx_path.is_file():
        return unavailable("rendered_pptx_missing")
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is None:
        return unavailable("libreoffice_missing")
    report = None
    try:
        import pymupdf

        with tempfile.TemporaryDirectory(prefix="postergen-render-fit-") as temporary:
            directory = Path(temporary)
            subprocess.run(
                [
                    executable,
                    f"-env:UserInstallation={directory.joinpath('profile').as_uri()}",
                    "--headless", "--convert-to", "pdf:impress_pdf_Export",
                    "--outdir", str(directory), str(pptx_path),
                ],
                check=True, timeout=120, capture_output=True, text=True,
            )
            pdf_path = directory / f"{pptx_path.stem}.pdf"
            with pymupdf.open(pdf_path) as document:
                if len(document) != 1:
                    raise ValueError("rendered PDF must contain one slide")
                page = document[0]
                if (
                    abs(page.rect.width - float(state["poster_width"]) * 72) > 2
                    or abs(page.rect.height - float(state["poster_height"]) * 72) > 2
                ):
                    raise ValueError("rendered PDF page dimensions do not match poster")
                blocks = page.get_text("blocks")
                report = evaluate_rendered_boxes(
                    state.get("styled_layout") or state.get("design_layout") or [], blocks,
                    poster_width=float(state["poster_width"]),
                    poster_height=float(state["poster_height"]),
                    # Fine text evidence never needs potentially large embedded
                    # figure PNG/JPEG payloads included by default rawdict flags.
                    raw_pdf=lambda: page.get_text(
                        "rawdict", flags=pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES,
                    ),
                )
        report["audit_seconds"] = round(time.perf_counter() - started, 6)
        report["candidate_id"] = candidate.get("candidate_id")
        from src.config.poster_config import load_config
        from src.layout.whitespace import measure_composition_whitespace
        config = load_config()["layout"]
        report["composition_whitespace"] = measure_composition_whitespace(
            state.get("layout_spec") or {}, state.get("styled_layout") or state.get("design_layout") or [],
            poster_width=float(state["poster_width"]), poster_height=float(state["poster_height"]),
            poster_margin=float(config["poster_margin"]), title_height_fraction=float(config["title_height_fraction"]),
            rendered_boxes=report["matched_text_boxes"],
        )
        return report
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError, ImportError) as exc:
        if report is not None:
            # Optional composition/cleanup failure cannot erase measured text
            # evidence, especially an already confirmed overflow/collision.
            report["composition_measurement_status"] = "unavailable"
            report["composition_measurement_reason"] = type(exc).__name__
            report["audit_seconds"] = round(time.perf_counter() - started, 6)
            return report
        return unavailable(type(exc).__name__)
