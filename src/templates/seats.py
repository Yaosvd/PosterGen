"""Derived, level-isolated retrieval seats for the global template library."""

from collections import defaultdict
from typing import Any, Dict, List, Sequence

from src.templates.scoring import TEMPLATE_RUBRIC_VERSION


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    length = max(len(left), len(right))
    if not length:
        return float("inf")
    a = list(left) + [0.0] * (length - len(left))
    b = list(right) + [0.0] * (length - len(right))
    return (sum((x - y) ** 2 for x, y in zip(a, b)) / length) ** 0.5


def _near_duplicate(left: Dict[str, Any], right: Dict[str, Any], threshold: float) -> bool:
    left_fingerprint = left.get("fingerprint")
    if left_fingerprint and left_fingerprint == right.get("fingerprint"):
        return True
    if int(left.get("signature_schema_version") or 1) != int(
        right.get("signature_schema_version") or 1
    ):
        return False
    return _distance(left.get("signature_vector") or [], right.get("signature_vector") or []) < threshold


def _rank(template: Dict[str, Any]) -> tuple:
    evaluation = template.get("template_evaluation") or {}
    valid = evaluation.get("rubric_version") == TEMPLATE_RUBRIC_VERSION
    score = template.get("template_design_score") if valid else None
    coverage = evaluation.get("coverage", 0.0) if valid else 0.0
    return (
        -float(coverage or 0.0),
        -float(score) if score is not None else float("inf"),
        str(template.get("created_at") or ""),
        str(template.get("template_id") or ""),
    )


def rebuild_retrieval_seats(index: Dict[str, Any], settings: Dict[str, Any]) -> None:
    """Select up to N globally per family *and* level, without deleting records."""
    limits = settings.get("retrieval_slots_by_level") or {str(level): 10 for level in range(4)}
    threshold = float(settings.get("novelty_distance_threshold", 0.08))
    selected_by_level: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    family_counts: Dict[tuple, int] = defaultdict(int)
    templates = index.get("templates", [])
    for template in templates:
        template["retrieval_enabled"] = False
        template["retrieval_reason"] = "not_ranked"
    for template in sorted(templates, key=_rank):
        level = int(template.get("template_level", 0))
        family = str(template.get("family") or "unknown")
        if template.get("status") in {"superseded", "retired"}:
            template["retrieval_reason"] = "retired"
        elif family_counts[(family, level)] >= int(limits[str(level)]):
            template["retrieval_reason"] = "tier_capacity"
        elif any(_near_duplicate(template, peer, threshold) for peer in selected_by_level[level]):
            template["retrieval_reason"] = "near_duplicate"
        else:
            template["retrieval_enabled"] = True
            template["retrieval_reason"] = "selected"
            family_counts[(family, level)] += 1
            selected_by_level[level].append(template)
