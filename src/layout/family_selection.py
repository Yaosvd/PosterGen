"""Versioned coverage-first selection policy, independent of model execution."""

import hashlib
import json
import math
from copy import deepcopy

from src.layout.paper_profile import PAPER_PROFILE_VERSION


FAMILY_SELECTION_VERSION = 1


class FamilySelectionExhausted(ValueError):
    def __init__(self, report):
        super().__init__("No enabled layout family remains for this iteration")
        self.report = report


def validate_family_selection_policy(policy, registered_ids):
    if not isinstance(policy, dict):
        raise ValueError("family_selection policy must be an object")
    if type(policy.get("version")) is not int or policy["version"] != FAMILY_SELECTION_VERSION:
        raise ValueError("Unsupported family_selection policy version")
    if policy.get("profile_schema_version") != PAPER_PROFILE_VERSION:
        raise ValueError("Unsupported family_selection profile schema")
    if policy.get("coverage_basis") != "committed_design_family_uses":
        raise ValueError("Unsupported family_selection coverage basis")
    enabled = policy.get("enabled_families")
    if (not isinstance(enabled, list) or not enabled
            or any(not isinstance(item, str) for item in enabled)
            or len(set(enabled)) != len(enabled)
            or set(enabled) - set(registered_ids)):
        raise ValueError("family_selection enabled_families must be unique registered IDs")
    if "classic_three_column" not in enabled:
        raise ValueError("classic_three_column must remain enabled")
    bonus = policy.get("semantic_bonus_max")
    if (isinstance(bonus, bool) or not isinstance(bonus, (int, float))
            or not math.isfinite(bonus) or not 0 <= bonus <= 0.5):
        raise ValueError("family_selection.semantic_bonus_max must be between 0 and 0.5")
    return deepcopy(policy)


def make_family_selection_policy(settings, registered_ids):
    selection = settings.get("selection", {})
    return validate_family_selection_policy({
        "version": selection.get("version", FAMILY_SELECTION_VERSION),
        "profile_schema_version": PAPER_PROFILE_VERSION,
        "coverage_basis": "committed_design_family_uses",
        "semantic_bonus_max": selection.get("semantic_bonus_max", 0.5),
        "enabled_families": list(settings.get("enabled", registered_ids)),
    }, registered_ids)


def profile_identity(profile):
    """Only allow the text-free descriptor contract into selection audits."""
    summary = {key: deepcopy(profile[key]) for key in (
        "schema_version", "semantic_rule_version", "profile_key", "kind",
        "content_density", "visual_count", "claim_count", "section_count",
        "design_flags", "semantic_signals",
    ) if key in profile}
    digest = hashlib.sha256(json.dumps(
        summary, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()
    return {"digest": digest, "summary": summary}


def semantic_match(family, profile):
    """Bounded hints, not an eligibility predicate or a relationship verifier."""
    matches = []
    flags = set(profile.get("design_flags") or [])
    signals = profile.get("semantic_signals") or {}
    hints = set(family.preferred_profiles) | {
        "method_flow_spine": {"method_heavy", "process"},
        "comparison_split": {"comparison"},
        "timeline_stage_narrative": {"timeline", "stages"},
    }.get(family.family_id, set())
    for preferred in sorted(hints):
        if profile.get("kind") == preferred:
            matches.append({"signal": preferred, "source": "kind", "strength": 0.5})
        if preferred in flags:
            strength = (signals.get(preferred) or {}).get("strength", 0.5)
            if not isinstance(strength, (int, float)) or not math.isfinite(strength):
                strength = 0.0
            matches.append({"signal": preferred, "source": "design_flags",
                            "strength": max(0.0, min(1.0, float(strength)))})
    return max((item["strength"] for item in matches), default=0.0), matches
