"""Parse and format simple inline math scripts for PowerPoint text runs."""

from typing import Any, Dict, List, Optional, Tuple

from pptx.util import Pt


SCRIPT_FONT_SCALE = 0.72
SCRIPT_BASELINES = {
    "subscript": -25000,
    "superscript": 30000,
}
SCRIPT_MARKERS = {
    "_": "subscript",
    "^": "superscript",
}


def _parse_script_payload(
    text: str,
    start: int,
) -> Optional[Tuple[str, int]]:
    """Return a script payload and the first index after it."""

    if start >= len(text):
        return None

    if text[start] == "{":
        depth = 1
        index = start + 1

        while index < len(text):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    payload = text[start + 1:index]
                    if payload:
                        return payload, index + 1
                    return None
            index += 1

        return None

    if not text[start].isalnum():
        return None

    index = start + 1
    while index < len(text) and text[index].isalnum():
        index += 1

    return text[start:index], index


def split_inline_math(text: str) -> List[Dict[str, Optional[str]]]:
    """Split ``_``/``^`` script notation into visible text segments.

    Braced scripts may contain multiple characters, as in ``max_{i in C}``.
    Unbraced scripts consume one alphanumeric token, so both ``lambda_i`` and
    ``epsilon_CutMix`` remain convenient inputs. Escaped markers stay literal.
    """

    segments: List[Dict[str, Optional[str]]] = []
    regular: List[str] = []
    index = 0

    def flush_regular() -> None:
        if not regular:
            return
        segments.append(
            {
                "text": "".join(regular),
                "baseline": None,
            }
        )
        regular.clear()

    while index < len(text):
        char = text[index]

        if (
            char == "\\"
            and index + 1 < len(text)
            and text[index + 1] in {"_", "^", "{", "}"}
        ):
            regular.append(text[index + 1])
            index += 2
            continue

        if char in SCRIPT_MARKERS:
            previous = text[index - 1] if index else ""
            attached_to_base = (
                previous.isalnum()
                or previous in ")]}"
            )
            parsed = (
                _parse_script_payload(text, index + 1)
                if attached_to_base
                else None
            )

            if parsed is not None:
                payload, next_index = parsed
                flush_regular()
                segments.append(
                    {
                        "text": payload,
                        "baseline": SCRIPT_MARKERS[char],
                    }
                )
                index = next_index
                continue

        regular.append(char)
        index += 1

    flush_regular()
    return segments


def visible_inline_math_text(text: str) -> str:
    """Return the text visible after inline script markers are interpreted."""

    return "".join(
        str(segment["text"])
        for segment in split_inline_math(text)
    )


def apply_script_format(
    run: Any,
    baseline: Optional[str],
    base_font_size: Any,
) -> None:
    """Apply editable DrawingML subscript or superscript formatting."""

    if baseline not in SCRIPT_BASELINES:
        return

    run.font.size = Pt(base_font_size.pt * SCRIPT_FONT_SCALE)
    # python-pptx has no public script API. DrawingML stores the vertical
    # offset as a signed 1/1000 percent value on the run properties.
    run.font._element.set(
        "baseline",
        str(SCRIPT_BASELINES[baseline]),
    )
