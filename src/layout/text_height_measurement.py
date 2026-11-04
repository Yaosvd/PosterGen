"""
text height measurement using binary search overflow detection
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from typing import Dict, Any, List, Optional
from pathlib import Path
from functools import lru_cache
import shutil
import subprocess
import math
import hashlib
import traceback
from PIL import ImageFont
from src.config.poster_config import load_config
from src.layout.measurement_context import (cached_measurement, current_context, file_identity,
    measurement_identity, diagnostic_values)
from src.layout.text_fit_adapter import OptimizedFitError, TextWidthError, fitting_prefix, fit_text
from utils.display_formula import (
    CONTENT_BLOCK_GAP,
    FORMULA_VERTICAL_PADDING,
    measure_formula,
    split_content_blocks,
)
from utils.inline_math import (
    apply_script_format,
    split_inline_math,
    visible_inline_math_text,
)

class TextMeasurementError(RuntimeError):
    """Explicit unavailable measurement, never a fabricated successful height."""
    def __init__(self, code, details):
        self.code, self.details = code, diagnostic_values(details)
        super().__init__(code + ': ' + str(self.details))


@lru_cache(maxsize=64)
def get_font_file_path(font_name: str, bold: bool = False) -> str:
    """Resolve the same system font face that LibreOffice will render."""

    if shutil.which("fc-match"):
        style = "Bold" if bold else "Regular"
        try:
            result = subprocess.run(
                [
                    "fc-match",
                    "-f",
                    "%{file}\n",
                    f"{font_name}:style={style}",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            resolved = result.stdout.splitlines()[0].strip()
            if resolved and Path(resolved).is_file():
                return resolved
        except (OSError, subprocess.SubprocessError, IndexError):
            pass

    font_mapping = {
        "Arial": "fonts/Arial.ttf",
        "Helvetica Neue": "fonts/HelveticaNeue.ttf",
    }
    font_file = font_mapping.get(font_name, "fonts/Arial.ttf")
    project_root = Path(__file__).parent.parent.parent
    return str(project_root / font_file)


def _measurement_config():
    context = current_context()
    return context.config(load_config) if context and context.settings["enabled"] else load_config()


@cached_measurement("line")
def estimate_wrapped_line_count(
    text_content: str,
    width_inches: float,
    font_name: str,
    font_size: int,
    margins: Optional[Dict[str, float]] = None,
    font_width_factor: float = 1.0,
    render_width_factor: float = 1.0,
    bold: bool = False,
) -> int:
    """Estimate word-wrapped lines with explicit font-width reserves."""

    config = _measurement_config()
    effective_margins = dict(
        config["text_measurement"]["margins"]
    )
    if margins is not None:
        effective_margins.update(margins)

    available_width = max(
        1.0,
        (
            width_inches
            - effective_margins["left"]
            - effective_margins["right"]
        )
        * 72
        * render_width_factor,
    )
    context = current_context()
    font_path = get_font_file_path(font_name, bold=bold)
    if context and context.settings["enabled"]:
        identity = file_identity(font_path)
        font = context.memo("font", (identity, font_size),
                            lambda: ImageFont.truetype(font_path, font_size))
    else:
        font = ImageFont.truetype(font_path, font_size)

    line_count = 0
    visible_text = "\n".join(
        visible_inline_math_text(line)
        for line in text_content.split("\n")
    )

    for explicit_line in visible_text.split("\n"):
        words = explicit_line.strip().split()
        if not words:
            line_count += 1
            continue

        current_line = ""
        for word in words:
            candidate = (
                f"{current_line} {word}"
                if current_line
                else word
            )
            if context and context.settings["enabled"]:
                length = context.memo("glyph", ("getlength", candidate, identity, font_size),
                                      lambda: font.getlength(candidate))
            else:
                length = font.getlength(candidate)
            candidate_width = length * font_width_factor
            if candidate_width <= available_width:
                current_line = candidate
                continue
            if current_line:
                line_count += 1
            current_line = word
            def word_width(value):
                return font.getlength(value) * font_width_factor
            while current_line and word_width(current_line) > available_width:
                try:
                    _, current_line = fitting_prefix(current_line, available_width, word_width)
                except TextWidthError as exc:
                    details = {**measurement_identity(), 'text_digest': hashlib.sha256(text_content.encode()).hexdigest(),
                        'text_length': len(text_content), 'width_inches': width_inches, 'font_name': font_name,
                        'font_size': font_size, 'margins': effective_margins, 'cause': str(exc),
                        'traceback': traceback.format_exception(type(exc), exc, exc.__traceback__)}
                    if context:
                        context.record_failure('TEXT_WIDTH_INFEASIBLE', details)
                    raise TextMeasurementError('TEXT_WIDTH_INFEASIBLE', details) from exc
                line_count += 1

        if current_line:
            line_count += 1

    return max(1, line_count)

def _measure_plain_text_height(
    text_content: str,
    width_inches: float,
    font_name: str = "Arial",
    font_size: int = 44,
    line_spacing: float = 1.0,
    precision: float = 0.001,
    margins: Optional[Dict[str, float]] = None,
    bold: bool = False,
) -> Dict[str, Any]:
    """find minimum height for text to fit without font size reduction"""
    
    config = _measurement_config()

    effective_margins = dict(
        config["text_measurement"]["margins"]
    )

    if margins is not None:
        effective_margins.update(margins)

    prs = Presentation()
    slide_layout_index = config["powerpoint"]["slide_layout_blank"]
    slide = prs.slides.add_slide(prs.slide_layouts[slide_layout_index])
    
    min_height = config["text_measurement"]["min_height"]
    max_height = config["text_measurement"]["max_height"]
    tolerance = precision
    
    details = {**measurement_identity(), 'text_digest': hashlib.sha256(text_content.encode('utf-8')).hexdigest(),
               'text_length': len(text_content), 'width_inches': width_inches,
               'font_name': font_name, 'font_size': font_size, 'margins': effective_margins}
    def fail(code, exc, height=None):
        record = {**details, 'test_height': height, 'cause': type(exc).__name__ + ': ' + str(exc),
                  'traceback': traceback.format_exception(type(exc), exc, exc.__traceback__)}
        context = current_context()
        if context:
            context.record_failure(code, record)
        return TextMeasurementError(code, record)
    if not all(math.isfinite(v) and v > 0 for v in (font_size, line_spacing, precision)) or font_size < 1:
        raise fail('TEXT_INVALID_PARAMETERS', ValueError('Invalid font size, line spacing or precision'))
    if not math.isfinite(width_inches) or width_inches <= effective_margins['left'] + effective_margins['right']:
        raise fail('TEXT_INVALID_GEOMETRY', ValueError('Invalid usable width'))

    soft_lines = 0
    def fits(test_height):
        nonlocal soft_lines
        textbox = None
        if text_content.strip() and test_height <= effective_margins['top'] + effective_margins['bottom']:
            return False
        try:
            textbox = slide.shapes.add_textbox(
                left=Inches(config["powerpoint"]["text_frame_positioning"]["default_left"]),
                top=Inches(config["powerpoint"]["text_frame_positioning"]["default_top"]),
                width=Inches(width_inches),
                height=Inches(test_height)
            )
            
            text_frame = textbox.text_frame
            text_frame.clear()
            text_frame.word_wrap = True
            text_frame.auto_size = MSO_AUTO_SIZE.NONE
            # Use caller-specific margins when supplied.
            # Body text keeps the configured defaults; section titles
            # use the same compact margins as the renderer.
            text_frame.margin_left = Inches(
                effective_margins["left"]
            )
            text_frame.margin_right = Inches(
                effective_margins["right"]
            )
            text_frame.margin_top = Inches(
                effective_margins["top"]
            )
            text_frame.margin_bottom = Inches(
                effective_margins["bottom"]
            )
            
            # process text exactly like renderer: split by single newlines
            lines = text_content.split('\n')
            
            for line_idx, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # create paragraph for each line (matching renderer behavior)
                if line_idx == 0 and len(text_frame.paragraphs) > 0:
                    p = text_frame.paragraphs[0]
                else:
                    p = text_frame.add_paragraph()

                p.alignment = PP_ALIGN.LEFT
                p.line_spacing = line_spacing

                for segment in split_inline_math(line):
                    run = p.add_run()
                    run.text = str(segment["text"])
                    run.font.name = font_name
                    run.font.size = Pt(font_size)
                    run.font.bold = bold
                    apply_script_format(
                        run,
                        segment["baseline"],
                        Pt(font_size),
                    )

            original_size = font_size
            font_file_path = get_font_file_path(font_name, bold=bold)
            info = fit_text(text_frame, font_file_path, font_size)
            if info:
                soft_lines = max(soft_lines, info.get('soft_wrapped_lines', 0))
                if info.get('height_probe_fits') is False:
                    return False
            return not any(run.font.size and run.font.size.pt < (original_size - 0.5)
                           for paragraph in text_frame.paragraphs for run in paragraph.runs)
        except OptimizedFitError as exc:
            context = current_context()
            if context:
                context.record_failure('TEXT_ADAPTER_ERROR', {**details, 'test_height': test_height,
                    'cause': str(exc), 'traceback': traceback.format_exception(type(exc), exc, exc.__traceback__)})
            raise
        except TextWidthError as exc:
            raise fail('TEXT_WIDTH_INFEASIBLE', exc, test_height) from exc
        except Exception as exc:
            raise fail('TEXT_MEASUREMENT_UNAVAILABLE', exc, test_height) from exc
        finally:
            if textbox is not None:
                sp = textbox._element
                sp.getparent().remove(sp)

    # Establish a genuinely fitting upper bound. A failed probe is not a height.
    if not fits(max_height):
        lines = estimate_wrapped_line_count(text_content, width_inches, font_name, int(font_size),
                                           margins=effective_margins, bold=bold)
        max_height = max(max_height * 2, lines * font_size / 72 * max(1, line_spacing) * 2
                         + effective_margins['top'] + effective_margins['bottom'])
        if not fits(max_height):
            raise fail('TEXT_HEIGHT_LIMIT', ValueError('No verified fitting upper bound'), max_height)
    while (max_height - min_height) > tolerance:
        test_height = (min_height + max_height) / 2
        if fits(test_height):
            max_height = test_height
        else:
            min_height = test_height

    # calculate newline offset to compensate for pptx rendering discrepancy
    newline_count = text_content.count('\n')
    newline_offset = newline_count * (font_size / 72) * config["text_measurement"]["newline_offset_ratio"]
    final_height = max_height + newline_offset
    if soft_lines:
        lines = estimate_wrapped_line_count(text_content, width_inches, font_name, int(font_size),
                                           margins=effective_margins, bold=bold)
        final_height = max(final_height, max(lines, soft_lines) * font_size / 72 * 1.20 * line_spacing
                           + effective_margins['top'] + effective_margins['bottom'])
    
    return {
        "optimal_height": final_height,
        "text_content": text_content,
        "width_inches": width_inches,
        "font_name": font_name,
        "font_size": font_size,
        "line_spacing": line_spacing,
        "precision": precision,
        "newline_count": newline_count,
        "newline_offset": newline_offset
    }


@cached_measurement("exact")
def measure_text_height(
    text_content: str,
    width_inches: float,
    font_name: str = "Arial",
    font_size: int = 44,
    line_spacing: float = 1.0,
    precision: float = 0.001,
    margins: Optional[Dict[str, float]] = None,
    bold: bool = False,
) -> Dict[str, Any]:
    """Measure text blocks and vertically stacked display fractions."""

    blocks = split_content_blocks(text_content)
    formula_blocks = [
        block
        for block in blocks
        if block.kind == "formula" and block.formula is not None
    ]
    if not formula_blocks:
        return _measure_plain_text_height(
            text_content=text_content,
            width_inches=width_inches,
            font_name=font_name,
            font_size=font_size,
            line_spacing=line_spacing,
            precision=precision,
            margins=margins,
            bold=bold,
        )

    config = _measurement_config()
    effective_margins = dict(
        config["text_measurement"]["margins"]
    )
    if margins is not None:
        effective_margins.update(margins)

    formula_width = max(
        0.1,
        width_inches
        - effective_margins["left"]
        - effective_margins["right"],
    )
    total_height = 0.0
    measured_block_count = 0

    for block in blocks:
        block_has_content = (
            (block.kind == "text" and bool(block.text.strip()))
            or (
                block.kind == "formula"
                and block.formula is not None
            )
        )
        if not block_has_content:
            continue
        if measured_block_count:
            total_height += CONTENT_BLOCK_GAP
        measured_block_count += 1

        if block.kind == "text":
            total_height += _measure_plain_text_height(
                text_content=block.text,
                width_inches=width_inches,
                font_name=font_name,
                font_size=font_size,
                line_spacing=line_spacing,
                precision=precision,
                margins=margins,
                bold=bold,
            )["optimal_height"]
            continue

        formula = block.formula
        if formula is None:
            continue
        if formula.prefix:
            total_height += _measure_plain_text_height(
                text_content=formula.prefix,
                width_inches=width_inches,
                font_name=font_name,
                font_size=font_size,
                line_spacing=line_spacing,
                precision=precision,
                margins=margins,
                bold=bold,
            )["optimal_height"]

        _, formula_height = measure_formula(
            formula.mathtext,
            font_size,
            formula_width,
        )
        total_height += formula_height + (2 * FORMULA_VERTICAL_PADDING)

    return {
        "optimal_height": total_height,
        "text_content": text_content,
        "width_inches": width_inches,
        "font_name": font_name,
        "font_size": font_size,
        "line_spacing": line_spacing,
        "precision": precision,
        "newline_count": text_content.count("\n"),
        "newline_offset": 0.0,
        "display_formula_count": len(formula_blocks),
    }
