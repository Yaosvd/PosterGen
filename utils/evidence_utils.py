"""Utilities for grounded academic evidence and claim verification."""

import re
from typing import Any, Dict, Iterable, List, Tuple


NUMBER_RE = re.compile(
    r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+|\d*\.\d+)"
    r"(?:[eE][-+]?\d+)?%?"
)

COMPARISON_TERMS = (
    "higher",
    "lower",
    "greater",
    "smaller",
    "larger",
    "better",
    "worse",
    "outperform",
    "outperforms",
    "outperformed",
    "improve",
    "improves",
    "improved",
    "increase",
    "increases",
    "increased",
    "decrease",
    "decreases",
    "decreased",
    "reduce",
    "reduces",
    "reduced",
    "stronger",
    "weaker",
    "more",
    "less",
)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_number(value: str) -> str:
    value = str(value).strip().replace(",", "")

    if value.endswith("%"):
        number = value[:-1]
        suffix = "%"
    else:
        number = value
        suffix = ""

    try:
        numeric = float(number)

        if numeric.is_integer():
            normalized = str(int(numeric))
        else:
            normalized = format(numeric, ".12g")

        return normalized + suffix
    except Exception:
        return value


def extract_numbers(text: str) -> List[str]:
    return [
        normalize_number(match.group(0))
        for match in NUMBER_RE.finditer(str(text))
    ]


def evidence_by_id(
    evidence_bank: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    return {
        item["evidence_id"]: item
        for item in evidence_bank.get("items", [])
        if isinstance(item, dict)
        and item.get("evidence_id")
    }


def collect_evidence_text(
    evidence_ids: Iterable[str],
    evidence_index: Dict[str, Dict[str, Any]],
) -> str:
    chunks: List[str] = []

    for evidence_id in evidence_ids:
        item = evidence_index.get(evidence_id)

        if not item:
            continue

        for key in (
            "claim",
            "source_excerpt",
            "metric_semantics_source_excerpt",
        ):
            value = item.get(key)

            if value:
                chunks.append(str(value))

        numbers = item.get("numbers", [])

        if isinstance(numbers, list):
            chunks.extend(str(x) for x in numbers)

    return "\n".join(chunks)


def validate_claim_numbers(
    claim_text: str,
    evidence_ids: Iterable[str],
    evidence_index: Dict[str, Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    claim_numbers = extract_numbers(claim_text)

    if not claim_numbers:
        return True, []

    source_text = collect_evidence_text(
        evidence_ids,
        evidence_index,
    )

    source_numbers = set(
        extract_numbers(source_text)
    )

    unsupported = [
        number
        for number in claim_numbers
        if number not in source_numbers
    ]

    return len(unsupported) == 0, unsupported


def contains_comparison_language(text: str) -> bool:
    lowered = str(text).lower()

    return any(
        term in lowered
        for term in COMPARISON_TERMS
    )


def valid_evidence_ids(
    ids: Iterable[str],
    evidence_index: Dict[str, Dict[str, Any]],
) -> List[str]:
    seen = set()
    result = []

    for evidence_id in ids or []:
        if evidence_id not in evidence_index:
            continue

        if evidence_id in seen:
            continue

        seen.add(evidence_id)
        result.append(evidence_id)

    return result
