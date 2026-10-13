"""Renderer-faithful styling grammar, shared with rendered-text auditing.

Malformed tags and unmatched emphasis are literal text, not disposable markup.
Color contents deliberately are not recursively parsed (legacy render behavior).
"""

import re

from utils.display_formula import extract_display_formula
from utils.inline_math import split_inline_math


def decode_formatting_literals(text: str) -> str:
    decoded = []
    index = 0
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text) and text[index + 1] in {"\\", "*"}:
            index += 1
        decoded.append(text[index])
        index += 1
    return "".join(decoded)


def tokenize_styling(text: str) -> list:
    segments, regular = [], []
    index = 0

    def flush():
        if regular:
            segments.append({"text": "".join(regular), "bold": False, "italic": False, "color": None})
            regular.clear()

    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text) and text[index + 1] in {"\\", "*"}:
            regular.append(text[index + 1])
            index += 2
            continue
        color = re.match(r"<color:(#[0-9A-Fa-f]{6})>", text[index:])
        closing = re.search(r"</color>", text[index + color.end():]) if color else None
        if color and closing:
            flush()
            start = index + color.end()
            content = decode_formatting_literals(text[start:start + closing.start()])
            if content.strip():
                segments.append({"text": content, "bold": True, "italic": False, "color": color.group(1)})
            index = start + closing.end()
            continue
        # An unclosed color opening is consumed literally one character at a time.
        if color:
            regular.append(text[index])
            index += 1
            continue
        emphasis = re.match(r"\*\*(.*?)\*\*", text[index:])
        bold = emphasis is not None
        if emphasis is None:
            emphasis = re.match(r"\*(.*?)\*", text[index:])
        if emphasis:
            flush()
            segments.append({"text": decode_formatting_literals(emphasis.group(1)),
                             "bold": bold, "italic": not bold, "color": None})
            index += emphasis.end()
            continue
        regular.append(text[index])
        index += 1
    flush()
    return segments


def tokenize_formatting(text: str) -> list:
    return [{**segment, "text": math["text"], "baseline": math["baseline"]}
            for segment in tokenize_styling(text)
            for math in split_inline_math(segment["text"])]


def editable_text_parts(text: str) -> tuple[list[str], int]:
    """Return editable paragraphs plus explicitly excluded display-image count.

    Renderer styles each stripped paragraph independently. Display formulas are
    images, whereas supported inline scripts remain editable DrawingML runs.
    """
    parts = []
    formula_count = 0
    for line in text.split("\n"):
        plain = "".join(segment["text"] for segment in tokenize_styling(line))
        formula = extract_display_formula(plain)
        if formula is not None:
            formula_count += 1
            if formula.prefix:
                parts.append("".join(segment["text"] for segment in tokenize_formatting(formula.prefix.strip())))
        elif line.strip():
            parts.append("".join(segment["text"] for segment in tokenize_formatting(line.strip())))
    return parts, formula_count
