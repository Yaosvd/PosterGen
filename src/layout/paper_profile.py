"""Deterministic, text-free paper descriptors; hints are not scientific proof."""

import re
from typing import Any, Dict


PAPER_PROFILE_VERSION = 2
SEMANTIC_RULE_VERSION = 1

# Word boundaries avoid accidental matches such as "database" or "baselineage".
_TITLE_RULES = (
    ("method_title", r"\b(method(?:s|ology|ologies)?|approach(?:es)?|frameworks?)\b", ("method_heavy",)),
    ("process_title", r"\b(pipelines?|workflows?|process(?:es)?)\b", ("process",)),
    ("comparison_title", r"\b(compar\w*|versus|vs\.?|ablations?|baselines?)\b", ("comparison",)),
    ("timeline_title", r"\b(timelines?|longitudinal|chronolog\w*)\b", ("timeline",)),
    ("stages_title", r"\b(stages?|phases?)\b", ("stages",)),
    ("results_title", r"\b(results?|findings?|evaluations?|performance)\b", ("results_heavy",)),
)
_ROLE_FLAGS = {
    "method": ("method_heavy",),
    "results": ("results_heavy",),
    "comparison": ("comparison",),
    "process": ("process",),
    "timeline": ("timeline",),
    "stages": ("stages",),
}
_ROLE_ALIASES = {
    "methods": "method", "methodology": "method", "result": "results",
    "finding": "results", "findings": "results", "stage": "stages",
}


def narrative_role(section: Dict[str, Any]) -> str:
    role = str(section.get("narrative_role") or "").strip().lower()
    return _ROLE_ALIASES.get(role, role)


def narrative_title(section: Dict[str, Any]) -> tuple[str, str]:
    """Prefer the active contract, then legacy labels; IDs are never prose."""
    for field in ("title_intent", "title", "section_title"):
        value = section.get(field)
        if isinstance(value, str) and value.strip():
            return field, value
    return "", ""


def build_paper_profile(state: Dict[str, Any]) -> Dict[str, Any]:
    claims = (state.get("verified_claims") or {}).get("claims", [])
    sections = (state.get("narrative_plan") or {}).get("sections", [])
    visual_count = len(state.get("images") or {}) + len(state.get("tables") or {})
    claim_count = len(claims)
    # These legacy categories intentionally retain their validation/retrieval identity.
    density = "low" if claim_count <= 8 else "medium" if claim_count <= 16 else "high"
    kind = "visual_heavy" if visual_count >= 4 else "text_heavy" if visual_count <= 1 else "balanced"
    signals = {
        flag: {"status": "unobserved", "strength": 0.0, "sources": []}
        for flag in ("method_heavy", "process", "comparison", "timeline", "stages", "results_heavy")
    }

    def record(flag, strength, section_id, field, rule):
        signal = signals[flag]
        signal["status"] = "detected"
        signal["strength"] = max(signal["strength"], strength)
        signal["sources"].append({
            "section_id": section_id, "field": field, "rule_id": rule,
        })

    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "")
        role = narrative_role(section)
        for flag in _ROLE_FLAGS.get(role, ()):
            record(flag, 1.0, section_id, "narrative_role", "role_" + role)
        field, title = narrative_title(section)
        for rule, pattern, flags in _TITLE_RULES:
            if re.search(pattern, title, re.IGNORECASE):
                for flag in flags:
                    record(flag, 0.5, section_id, field, rule)
    if visual_count >= 4:
        # Retain the old visual-rich hint, explicitly labeled as a weak heuristic.
        record("results_heavy", 0.5, None, "visual_count", "visual_count_at_least_four")
    return {
        "schema_version": PAPER_PROFILE_VERSION,
        "semantic_rule_version": SEMANTIC_RULE_VERSION,
        "profile_key": f"{kind}:{density}",
        "kind": kind,
        "content_density": density,
        "visual_count": visual_count,
        "claim_count": claim_count,
        "section_count": len(sections),
        "design_flags": sorted(flag for flag, value in signals.items() if value["status"] == "detected"),
        "semantic_signals": signals,
    }
