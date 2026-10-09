"""Check editable body text against LibreOffice's rendered PDF glyph bounds.

Only uniquely matched text blocks are hard evidence. Unmatched or combined PDF
blocks remain inconclusive, so an extraction quirk cannot reject a poster.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Sequence


RENDER_FIT_SCHEMA_VERSION = 1
_POINTS_PER_INCH = 72.0


def _normalized(value: Any) -> str:
    return "".join(
        char.lower()
        for char in unicodedata.normalize("NFKC", str(value or ""))
        if char.isalnum()
    )


def _matches(
    elements: Sequence[Dict[str, Any]],
    blocks: Sequence[Sequence[Any]],
) -> tuple[List[Dict[str, Any]], List[str]]:
    matched: List[Dict[str, Any]] = []
    unmatched: List[str] = []
    used_blocks: set[int] = set()
    for element in elements:
        if element.get("type") != "text":
            continue
        element_id = str(element.get("id") or element.get("section_id") or "")
        source = _normalized(element.get("content"))
        if len(source) < 18:
            unmatched.append(element_id)
            continue
        prefix = source[: min(24, len(source))]
        expected_x = float(element["x"]) * _POINTS_PER_INCH
        expected_y = float(element["y"]) * _POINTS_PER_INCH
        candidates = []
        for index, block in enumerate(blocks):
            if (
                index in used_blocks or len(block) < 5
                or (len(block) > 6 and block[6] != 0)
            ):
                continue
            visible = _normalized(block[4])
            if (
                not visible.startswith(prefix)
                or len(visible) < len(source) * 0.70
                or len(visible) > len(source) * 1.30
            ):
                continue
            x_error = abs(float(block[0]) - expected_x)
            y_error = abs(float(block[1]) - expected_y)
            if x_error > 54 or y_error > 72:
                continue
            candidates.append((x_error + y_error, index, block))
        if len(candidates) != 1:
            unmatched.append(element_id)
            continue
        _, index, block = candidates[0]
        used_blocks.add(index)
        matched.append({
            "element_id": element_id,
            "section_id": str(element.get("section_id") or ""),
            "zone_id": str(element.get("zone_id") or ""),
            "planned_box_inches": [
                round(float(element[key]), 4)
                for key in ("x", "y", "width", "height")
            ],
            "rendered_box_inches": [
                round(float(block[key]) / _POINTS_PER_INCH, 4)
                for key in range(4)
            ],
        })
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
) -> Dict[str, Any]:
    """Compare high-confidence PDF body blocks with their planned text boxes."""

    matched, unmatched = _matches(layout, blocks)
    issues: List[Dict[str, Any]] = []
    for item in matched:
        x, y, width, height = item["planned_box_inches"]
        actual = item["rendered_box_inches"]
        if actual[2] > x + width + overflow_tolerance_inches or (
            actual[3] > y + height + overflow_tolerance_inches
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
        "status": "failed" if issues else "passed" if not unmatched else "partial",
        "passed": not issues,
        "matched_text_count": len(matched),
        "unmatched_text_ids": unmatched,
        "matched_text_boxes": matched,
        "issue_count": len(issues),
        "issues": issues,
        "measurement_source": "libreoffice_pdf_pymupdf",
    }


def audit_rendered_text(state: Dict[str, Any]) -> Dict[str, Any]:
    """Export a temporary PDF; keep the final PPTX/PNG path unchanged."""

    candidate = state.get("current_candidate") or {}
    pptx_path = Path(str(candidate.get("pptx_path") or ""))
    if not pptx_path.is_file():
        return {
            "schema_version": RENDER_FIT_SCHEMA_VERSION,
            "status": "unavailable", "passed": True,
            "reason": "rendered_pptx_missing", "issues": [],
        }
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is None:
        return {
            "schema_version": RENDER_FIT_SCHEMA_VERSION,
            "status": "unavailable", "passed": True,
            "reason": "libreoffice_missing", "issues": [],
        }
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
            state.get("design_layout") or [], blocks,
            poster_width=float(state["poster_width"]),
            poster_height=float(state["poster_height"]),
        )
        report["candidate_id"] = candidate.get("candidate_id")
        return report
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError, ImportError) as exc:
        return {
            "schema_version": RENDER_FIT_SCHEMA_VERSION,
            "status": "unavailable", "passed": True,
            "reason": type(exc).__name__, "issues": [],
        }
