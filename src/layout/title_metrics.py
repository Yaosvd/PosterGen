"""Loop-only title typography contract shared by compiler and renderer."""

from __future__ import annotations

from typing import Any, Dict
from math import isfinite

from src.layout.text_height_measurement import estimate_wrapped_line_count, measure_text_height


TITLE_POLICY_VERSION = "loop_title_v1"
TITLE_MARGINS = {"left": 0.10, "right": 0.10, "top": 0.05, "bottom": 0.05}


def title_policy(config: Dict[str, Any]) -> Dict[str, float]:
    values = (config.get("text_measurement") or {}).get("loop_section_title") or {}
    result = {
        "line_advance": float(values.get("line_advance", 1.20)),
        "width_factor": float(values.get("width_factor", 1.0)),
        "render_width_factor": float(values.get("render_width_factor", 0.98)),
        "height_reserve_inches": float(values.get("height_reserve_inches", 0.05)),
        "minimum_gap_font_lines": float(values.get("minimum_gap_font_lines", 0.225)),
    }
    for name, low, high in (("line_advance", 1.0, 2.0), ("width_factor", 0.9, 1.2),
                            ("render_width_factor", 0.9, 1.0), ("height_reserve_inches", 0.0, 0.5),
                            ("minimum_gap_font_lines", 0.1, 1.0)):
        if not isfinite(result[name]) or not low <= result[name] <= high:
            raise ValueError(f"invalid loop_section_title.{name}")
    return result


def measure_loop_title(text: str, width: float, font_name: str, font_size: float,
                       config: Dict[str, Any], *, bold: bool = True) -> Dict[str, Any]:
    policy = title_policy(config)
    measured = measure_text_height(
        text_content=text, width_inches=width, font_name=font_name,
        font_size=font_size, line_spacing=policy["line_advance"],
        margins=TITLE_MARGINS, bold=bold,
    )
    lines = estimate_wrapped_line_count(
        text_content=text, width_inches=width, font_name=font_name,
        font_size=font_size, margins=TITLE_MARGINS, bold=bold,
        font_width_factor=policy["width_factor"],
        render_width_factor=policy["render_width_factor"],
    )
    minimum = (lines * font_size / 72 * policy["line_advance"]
               + TITLE_MARGINS["top"] + TITLE_MARGINS["bottom"]
               + policy["height_reserve_inches"])
    return {
        "height": max(float(measured["optimal_height"]), minimum),
        "measured_height": measured["optimal_height"],
        "renderer_minimum_height": minimum,
        "measured_lines": lines, "renderer_safe_lines": lines,
        "renderer_wrap_reserve": max(0.0, minimum - measured["optimal_height"]),
        "title_policy_version": TITLE_POLICY_VERSION,
        "title_line_advance": policy["line_advance"],
        "minimum_content_gap_inches": font_size / 72 * policy["minimum_gap_font_lines"],
    }
