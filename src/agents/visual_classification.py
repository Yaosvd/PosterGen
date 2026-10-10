"""Paper-semantic visual roles, independent of poster geometry."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


ROLE_FIELDS = (
    "problem_illustration",
    "method_workflow",
    "main_results",
    "comparative_results",
    "supporting",
)
POLICY_VERSION = "semantic_visual_roles_v2"


def _caption_role(caption: str) -> str:
    text = str(caption or "").casefold()
    if any(word in text for word in ("comparison", "baseline", "ablation", "versus", " vs ")):
        return "comparative_results"
    if any(word in text for word in ("result", "performance", "accuracy", "evaluation")):
        return "main_results"
    if any(word in text for word in ("method", "architecture", "framework", "workflow", "pipeline")):
        return "method_workflow"
    if any(word in text for word in ("problem", "challenge", "motivation")):
        return "problem_illustration"
    return "supporting"


def _conservative_key(classification: Dict[str, Any], visual_ids: List[str]) -> str | None:
    # A caption heuristic cannot rank several competing scientific visuals.
    prominent = [
        visual_id for role in ("main_results", "method_workflow", "comparative_results")
        for visual_id in classification[role]
    ]
    if len(prominent) == 1:
        return prominent[0]
    return visual_ids[0] if len(visual_ids) == 1 else None


def normalize_visual_classification(
    raw: Any, visuals: List[Dict[str, Any]], *, source: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Keep valid model roles; repair unknown, duplicate, and omitted IDs safely.

    ``key_visual`` is a pointer to one role member, not a sixth role.
    The audit deliberately contains IDs/counts only, not paper captions.
    """

    available = {
        str(item.get("id")): item for item in visuals
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }
    ids = list(available)
    result: Dict[str, Any] = {"key_visual": None, **{role: [] for role in ROLE_FIELDS}}
    observations: List[Dict[str, str]] = []
    seen = set()
    model = raw if isinstance(raw, dict) else {}
    for role in ROLE_FIELDS:
        values = model.get(role, [])
        if not isinstance(values, list):
            observations.append({"code": "invalid_role_type", "role": role})
            continue
        for value in values:
            if not isinstance(value, str) or value not in available:
                observations.append({"code": "unknown_visual_id", "role": role})
            elif value in seen:
                observations.append({"code": "duplicate_visual_id", "visual_id": value})
            else:
                result[role].append(value)
                seen.add(value)
    for visual_id in ids:
        if visual_id not in seen:
            role = _caption_role(str(available[visual_id].get("caption") or ""))
            result[role].append(visual_id)
            observations.append({"code": "missing_role_filled", "visual_id": visual_id, "role": role})
    key = model.get("key_visual")
    if isinstance(key, str) and key in available:
        result["key_visual"] = key
    elif key is None and "key_visual" in model:
        result["key_visual"] = None
    else:
        if key is not None:
            observations.append({"code": "invalid_key_visual"})
        result["key_visual"] = _conservative_key(result, ids)
    audit = {
        "policy_version": POLICY_VERSION,
        "source": source,
        "input_modality": "captions_and_aspect_only",
        "available_visual_ids": ids,
        "key_visual_id": result["key_visual"],
        "observations": observations,
    }
    return result, audit
