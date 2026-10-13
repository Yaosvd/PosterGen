"""Bounded, exact, position-aware PDF text matching (no scientific text logs).

Block matching is the fast path. Unresolved elements may consume disjoint PDF
characters across wrapped lines, even when PDF extraction merged textboxes.
Ambiguity, incomplete text and resource exhaustion remain inconclusive.
"""

from __future__ import annotations

import time
import unicodedata
from collections import Counter
from typing import Any, Callable, Sequence

from utils.text_formatting import editable_text_parts


MATCHING_POLICY_VERSION = "editable_exact_fragments_v1"
MAX_PDF_CHARACTERS = 200_000
MAX_PDF_LINES = 10_000
MAX_SEARCH_STEPS = 50_000
MAX_PATH_LINES = 256
MAX_ACTIVE_PATHS = 64
MAX_MATCH_CHARACTERS = 32_000


def normalized(value: Any) -> str:
    return "".join(char.lower() for char in unicodedata.normalize("NFKC", str(value or "")) if char.isalnum())


def _union(boxes):
    return [min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes)]


def _near(box, element):
    # Origin proximity only: never clip to the planned frame, hiding overflow.
    return abs(box[0] - float(element["x"]) * 72) <= 54 and abs(box[1] - float(element["y"]) * 72) <= 72


def _pdf_lines(raw):
    lines = []
    character_count = 0
    for block_index, block in enumerate(raw.get("blocks", [])):
        if block.get("type", 0) != 0:
            continue
        block_id = block.get("number", block_index)
        for line_index, line in enumerate(block.get("lines", [])):
            chars = [char for span in line.get("spans", []) for char in span.get("chars", [])]
            character_count += len(chars)
            if character_count > MAX_PDF_CHARACTERS or len(lines) >= MAX_PDF_LINES:
                return [], "pdf_fragment_budget_exhausted"
            text, mapping = [], []
            for index, char in enumerate(chars):
                token = normalized(char.get("c", ""))
                text.append(token)
                mapping.extend([index] * len(token))
            if mapping:
                lines.append({"text": "".join(text), "mapping": mapping, "chars": chars,
                              "key": (block_id, line_index), "bbox": _union([c["bbox"] for c in chars])})
    return sorted(lines, key=lambda item: (item["bbox"][1], item["bbox"][0], item["key"])), None


def _piece(line, start, length):
    first, last = line["mapping"][start], line["mapping"][start + length - 1]
    # Include adjacent punctuation; normalized letters alone would understate
    # visible overflow. Whitespace cannot belong to two independent subranges.
    while first > 0 and not normalized(line["chars"][first - 1].get("c", "")) and not line["chars"][first - 1].get("c", "").isspace():
        first -= 1
    while last + 1 < len(line["chars"]) and not normalized(line["chars"][last + 1].get("c", "")) and not line["chars"][last + 1].get("c", "").isspace():
        last += 1
    keys = {(line["key"], index) for index in range(first, last + 1)}
    return keys, _union([char["bbox"] for char in line["chars"][first:last + 1]])


def _separate_subrange(line, start, length):
    """Never truncate a word/paragraph to claim a complete text match.

    A subrange inside one PDF line must be separated from other letters by a
    physical gap, as when independent textboxes share a PDF extraction line.
    Ordinary single-space word separation is insufficient evidence.
    """
    mapping, chars = line["mapping"], line["chars"]
    end = start + length
    minimum = max(12, (line["bbox"][3] - line["bbox"][1]) * 0.5)
    if start and chars[mapping[start]]["bbox"][0] - chars[mapping[start - 1]]["bbox"][2] < minimum:
        return False
    if end < len(mapping) and chars[mapping[end]]["bbox"][0] - chars[mapping[end - 1]]["bbox"][2] < minimum:
        return False
    return True


def _fragment_candidates(source, element, lines, used_blocks, used_chars):
    if len(source) > MAX_MATCH_CHARACTERS:
        return [], "fragment_text_budget_exhausted", 0
    complete = {}
    steps = 0
    stack = []
    for index, line in enumerate(lines):
        if line["key"][0] in used_blocks:
            continue
        text = line["text"]
        # Enumerate exact starts, including very short first wrapped lines.
        starts = {0} if source.startswith(text) else set()
        needle = source[:min(12, len(source))]
        start = text.find(needle)
        while start >= 0:
            starts.add(start)
            start = text.find(needle, start + 1)
        for start in sorted(starts):
            count = min(len(source), len(text) - start)
            if text[start:start + count] != source[:count]:
                continue
            if not _separate_subrange(line, start, count):
                continue
            keys, box = _piece(line, start, count)
            if not _near(box, element) or keys & used_chars:
                continue
            stack.append((index, count, keys, [box], box[0]))
            if len(stack) > MAX_ACTIVE_PATHS:
                return [], "fragment_branch_budget_exhausted", steps
    while stack:
        steps += 1
        if steps > MAX_SEARCH_STEPS:
            return [], "fragment_search_budget_exhausted", steps
        index, consumed, keys, boxes, origin_x = stack.pop()
        if consumed == len(source):
            complete[frozenset(keys)] = (keys, _union(boxes), "exact_fragments")
            if len(complete) > 1:
                return [], "ambiguous_fragments", steps
            continue
        if len(boxes) >= MAX_PATH_LINES:
            return [], "fragment_path_budget_exhausted", steps
        previous = boxes[-1]
        for next_index in range(index + 1, len(lines)):
            steps += 1
            if steps > MAX_SEARCH_STEPS:
                return [], "fragment_search_budget_exhausted", steps
            line = lines[next_index]
            box = line["bbox"]
            if box[1] - previous[1] > max(72, (previous[3] - previous[1]) * 3):
                break
            if (box[1] <= previous[1] + 1 or abs(box[0] - origin_x) > 54
                    or line["key"][0] in used_blocks):
                continue
            count = min(len(source) - consumed, len(line["text"]))
            if line["text"][:count] != source[consumed:consumed + count]:
                continue
            if not _separate_subrange(line, 0, count):
                continue
            next_keys, next_box = _piece(line, 0, count)
            if next_keys & (keys | used_chars):
                continue
            stack.append((next_index, consumed + count, keys | next_keys, boxes + [next_box], origin_x))
            if len(stack) > MAX_ACTIVE_PATHS:
                return [], "fragment_branch_budget_exhausted", steps
    return list(complete.values()), None if complete else "exact_text_not_found", steps


def match_text(elements: Sequence[dict], blocks: Sequence[Sequence[Any]],
               raw_pdf: dict | Callable[[], dict] | None = None) -> tuple[list, list, dict]:
    started = time.perf_counter()
    expected, excluded = [], []
    reasons = {}
    for element in elements:
        if element.get("type") not in {"text", "section_title"}:
            continue
        title = element["type"] == "section_title"
        element_id = str(element.get("id") or (str(element.get("section_id")) + "_title" if title else element.get("section_id")) or "")
        if title:
            source, formulas = str(element.get("section_title") or ""), 0
        else:
            parts, formulas = editable_text_parts(str(element.get("content") or ""))
            source = "\n".join(parts)
        if formulas:
            excluded.append({"element_id": element_id, "kind": "display_formula_image",
                             "count": formulas, "text_verified": False})
        source = normalized(source)
        if source:
            expected.append((element_id, element, source))
            if len(source) < (3 if title else 18):
                reasons[element_id] = "text_too_short"

    proposals = {}
    for element_id, element, source in expected:
        if element_id in reasons:
            continue
        candidates = []
        for index, block in enumerate(blocks):
            if len(block) < 5 or (len(block) > 6 and block[6] != 0):
                continue
            if normalized(block[4]) == source and _near(block[:4], element):
                candidates.append((block[5] if len(block) > 5 else index, block))
        if len(candidates) == 1:
            proposals[element_id] = candidates[0]
        elif len(candidates) > 1:
            reasons[element_id] = "ambiguous_blocks"
    block_counts = Counter(value[0] for value in proposals.values())
    matches, used_blocks, used_chars = {}, set(), set()
    for element_id, (block_id, block) in proposals.items():
        if block_counts[block_id] != 1:
            reasons[element_id] = "shared_pdf_evidence"
        else:
            matches[element_id] = (block[:4], "exact_block", 1)
            used_blocks.add(block_id)

    unresolved = [entry for entry in expected if entry[0] not in matches and entry[0] not in reasons]
    fallback_count, search_steps, extraction_seconds = 0, 0, 0.0
    if unresolved and raw_pdf is not None:
        extraction_start = time.perf_counter()
        try:
            raw = raw_pdf() if callable(raw_pdf) else raw_pdf
            lines, failure = _pdf_lines(raw)
        except (OSError, ValueError, RuntimeError):
            # Keep already confirmed block evidence and geometry failures.
            lines, failure = [], "pdf_fragment_extraction_unavailable"
        extraction_seconds = time.perf_counter() - extraction_start
        fragment_proposals = {}
        for element_id, element, source in unresolved:
            fallback_count += 1
            if failure:
                reasons[element_id] = failure
                continue
            candidates, reason, steps = _fragment_candidates(source, element, lines, used_blocks, used_chars)
            search_steps += steps
            if len(candidates) == 1:
                fragment_proposals[element_id] = candidates[0]
            else:
                reasons[element_id] = reason or "exact_text_not_found"
        ownership = Counter(char for keys, _, _ in fragment_proposals.values() for char in keys)
        for element_id, (keys, box, method) in fragment_proposals.items():
            if any(ownership[char] > 1 for char in keys):
                reasons[element_id] = "shared_pdf_evidence"
            else:
                matches[element_id] = (box, method, len({key[0] for key in keys}))
                used_chars.update(keys)

    matched, unmatched = [], []
    counts = {kind: {"expected": 0, "matched": 0, "unmatched": 0} for kind in ("section_title", "text")}
    for element_id, element, source in expected:
        kind = element["type"]
        counts[kind]["expected"] += 1
        if element_id not in matches:
            counts[kind]["unmatched"] += 1
            unmatched.append(element_id)
            reasons.setdefault(element_id, "fragment_evidence_unavailable" if raw_pdf is None else "exact_text_not_found")
            continue
        box, method, fragment_count = matches[element_id]
        counts[kind]["matched"] += 1
        matched.append({"element_id": element_id, "element_type": kind,
                        "section_id": str(element.get("section_id") or ""),
                        "zone_id": str(element.get("zone_id") or ""),
                        "planned_box_inches": [round(float(element[key]), 4) for key in ("x", "y", "width", "height")],
                        "rendered_box_inches": [round(float(value) / 72, 4) for value in box],
                        "match_method": method, "fragment_count": fragment_count,
                        "expected_normalized_characters": len(source), "matched_normalized_characters": len(source)})
    return matched, unmatched, {
        "matching_policy_version": MATCHING_POLICY_VERSION,
        "expected_text_count": len(expected), "unmatched_text_count": len(unmatched),
        "text_coverage": {"matched": len(matched), "expected": len(expected),
                          "fraction": len(matched) / len(expected) if expected else None,
                          "by_type": counts, "scope": "editable_body_and_section_titles"},
        "unmatched_text_reasons": [{"element_id": key, "reason": reasons[key]} for key in unmatched],
        "excluded_noneditable_content": excluded,
        "matching_diagnostics": {"fallback_elements": fallback_count, "search_steps": search_steps,
                                 "fragment_extraction_seconds": round(extraction_seconds, 6),
                                 "matching_seconds": round(time.perf_counter() - started, 6),
                                 "limits": {"pdf_characters": MAX_PDF_CHARACTERS, "pdf_lines": MAX_PDF_LINES,
                                            "search_steps_per_element": MAX_SEARCH_STEPS, "path_lines": MAX_PATH_LINES,
                                            "active_paths": MAX_ACTIVE_PATHS, "match_characters": MAX_MATCH_CHARACTERS}},
    }
