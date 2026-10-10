"""Content, color, and visual-asset quality evaluators.

These evaluators turn the paper-derived quality rubric into grounded,
layout-family-neutral checks.  Deterministic evidence always wins over model
opinion: the optional semantic content pass may refine a score, but it cannot
invent missing paper content or make an ungrounded repair request.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image

from src.critic.base import CriticContext, EvaluationResult, issue
from utils.agent_policy import apply_agent_policy
from utils.grounded_content import all_publishable_claims
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt


def _settings(context: CriticContext, name: str) -> Dict[str, Any]:
    return context.config.get("evaluators", {}).get(name, {})


def _result(
    context: CriticContext,
    name: str,
    *,
    passed: bool,
    scores: Dict[str, float],
    issues: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    positives: Optional[List[Dict[str, Any]]] = None,
) -> EvaluationResult:
    settings = _settings(context, name)
    return EvaluationResult(
        evaluator=name,
        version=str(settings.get("version", "1.0.0")),
        hard_gate=bool(settings.get("hard_gate", False)),
        passed=passed,
        scores=scores,
        issues=issues,
        positive_patterns=positives or [],
        metadata=metadata or {},
    )


def _sections(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    board = state.get("optimized_story_board") or state.get("story_board") or {}
    return [
        section
        for section in board.get("spatial_content_plan", {}).get("sections", [])
        if isinstance(section, dict) and section.get("section_id")
    ]


def _clamp(value: Any) -> float:
    try:
        return round(max(0.0, min(100.0, float(value))), 2)
    except (TypeError, ValueError):
        return 0.0


class InformationNarrativeEvaluator:
    """Evaluate information coverage, depth, hierarchy, flow, and concision."""

    name = "information_narrative"
    _ROLE_ORDER = {
        "foundation": 0,
        "background": 0,
        "problem": 1,
        "motivation": 1,
        "method": 2,
        "theory": 2,
        "results": 3,
        "evaluation": 3,
        "conclusion": 4,
        "impact": 4,
        "supporting": 5,
    }
    _SUBMETRICS = (
        "information_layering",
        "information_coverage",
        "information_depth",
        "information_completeness",
        "narrative_structure",
        "narrative_flow",
        "narrative_conciseness",
    )

    def __init__(self) -> None:
        self.prompt = load_prompt("config/prompts/critic_content.txt")

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        state = context.state
        settings = _settings(context, self.name)
        sections = _sections(state)
        claims = all_publishable_claims(state)
        narrative_sections = {
            str(item.get("section_id")): item
            for item in (state.get("narrative_plan") or {}).get("sections", [])
            if isinstance(item, dict) and item.get("section_id")
        }
        visible_claim_ids = [
            str(claim_id)
            for section in sections
            for claim_id in section.get("claim_ids", [])
            if str(claim_id) in claims
        ]
        used_evidence = {
            str(evidence_id)
            for claim_id in visible_claim_ids
            for evidence_id in claims[claim_id].get("evidence_ids", [])
        }
        assigned_evidence = {
            str(evidence_id)
            for item in narrative_sections.values()
            for evidence_id in item.get("evidence_ids", [])
        }
        high_priority_evidence = {
            str(evidence_id)
            for item in narrative_sections.values()
            if int(item.get("importance", 2) or 2) == 1
            for evidence_id in item.get("evidence_ids", [])
        }
        coverage = (
            len(used_evidence.intersection(assigned_evidence))
            / len(assigned_evidence)
            if assigned_evidence else 1.0
        )
        high_coverage = (
            len(used_evidence.intersection(high_priority_evidence))
            / len(high_priority_evidence)
            if high_priority_evidence else 1.0
        )

        importance_levels = {
            int(section.get("importance_level", 2) or 2)
            for section in sections
        }
        anchor_zone = (state.get("layout_spec") or {}).get("primary_anchor_zone")
        anchor_sections = {
            str(section_id)
            for zone in (state.get("layout_spec") or {}).get("zones", [])
            if zone.get("zone_id") == anchor_zone
            for section_id in zone.get("section_ids", [])
        }
        high_importance_ids = {
            str(section.get("section_id"))
            for section in sections
            if int(section.get("importance_level", 2) or 2) == 1
        }
        layering = 100.0
        if len(sections) > 1 and len(importance_levels) < 2:
            layering -= 25.0
        if anchor_zone and not anchor_sections.intersection(high_importance_ids):
            layering -= 25.0

        evidence_types = {
            str(item.get("claim_type", ""))
            for item in (state.get("evidence_bank") or {}).get("items", [])
            if str(item.get("evidence_id")) in used_evidence
        }
        required_role_groups = []
        all_roles = {
            str(item.get("narrative_role", "supporting")).lower()
            for item in narrative_sections.values()
        }
        for group in (
            {"foundation", "background", "problem", "motivation"},
            {"method", "theory"},
            {"results", "evaluation"},
        ):
            if all_roles.intersection(group):
                required_role_groups.append(group)
        visible_roles = {
            str(
                narrative_sections.get(str(section.get("section_id")), {}).get(
                    "narrative_role", section.get("content_type", "supporting")
                )
            ).lower()
            for section in sections
        }
        represented_groups = sum(
            bool(visible_roles.intersection(group)) for group in required_role_groups
        )
        structure_score = (
            100.0 * represented_groups / len(required_role_groups)
            if required_role_groups else 100.0
        )
        depth_score = min(
            100.0,
            45.0 + len(used_evidence) * 7.0 + len(evidence_types) * 6.0,
        ) if visible_claim_ids else 0.0

        reading_order = [
            str(item)
            for item in (state.get("layout_spec") or {}).get("reading_order", [])
        ] or [str(section.get("section_id")) for section in sections]
        ranks = []
        for section_id in reading_order:
            item = narrative_sections.get(section_id, {})
            role = str(item.get("narrative_role", "supporting")).lower()
            ranks.append(self._ROLE_ORDER.get(role, 5))
        inversions = sum(
            ranks[index] > ranks[index + 1]
            for index in range(max(0, len(ranks) - 1))
        )
        flow_score = max(0.0, 100.0 - inversions * 18.0)

        max_words = int(settings.get("maximum_words_per_claim", 45))
        visible_texts = [str(claims[item].get("text", "")) for item in visible_claim_ids]
        excessive = [
            (claim_id, len(re.findall(r"\b\w+\b", str(claims[claim_id].get("text", "")))))
            for claim_id in visible_claim_ids
            if len(re.findall(r"\b\w+\b", str(claims[claim_id].get("text", "")))) > max_words
        ]
        normalized = [re.sub(r"\s+", " ", item).strip().casefold() for item in visible_texts]
        duplicates = max(0, len(normalized) - len(set(normalized)))
        concision = max(0.0, 100.0 - len(excessive) * 12.0 - duplicates * 25.0)

        submetrics = {
            "information_layering": _clamp(layering),
            "information_coverage": _clamp(coverage * 100.0),
            "information_depth": _clamp(depth_score),
            "information_completeness": _clamp(high_coverage * 100.0),
            "narrative_structure": _clamp(structure_score),
            "narrative_flow": _clamp(flow_score),
            "narrative_conciseness": _clamp(concision),
        }
        semantic = self._semantic_scores(context, sections, claims, submetrics)
        if semantic:
            semantic_weight = float(settings.get("semantic_weight", 0.4))
            semantic_weight = max(0.0, min(1.0, semantic_weight))
            for key in self._SUBMETRICS:
                if key in semantic:
                    submetrics[key] = round(
                        submetrics[key] * (1.0 - semantic_weight)
                        + semantic[key] * semantic_weight,
                        2,
                    )

        problems: List[Dict[str, Any]] = []
        missing_assigned = sorted(assigned_evidence - used_evidence)
        missing_high = sorted(high_priority_evidence - used_evidence)
        if coverage < float(settings.get("preferred_evidence_coverage", 0.70)):
            problems.append(issue(
                "CONTENT-COVERAGE-LOW",
                severity="major",
                scope="content_quality",
                observation="The poster omits a substantial share of evidence assigned to its narrative",
                evidence={
                    "coverage": round(coverage, 4),
                    "missing_evidence_ids": missing_assigned[:12],
                },
                required_outcome="Restore the most relevant omitted verified evidence without adding filler",
                allowed_operations=["add_existing_claim", "add_claim_from_evidence"],
                forbidden_operations=["invent_claim", "add_filler_text"],
            ))
        if missing_high:
            problems.append(issue(
                "CONTENT-HIGH-PRIORITY-MISSING",
                severity="major",
                scope="content_quality",
                observation="High-priority narrative evidence is absent from the visible poster",
                evidence={"missing_evidence_ids": missing_high[:12]},
                required_outcome="Include a concise verified claim covering the missing high-priority evidence",
                allowed_operations=["add_existing_claim", "add_claim_from_evidence", "move_section_to_zone"],
                forbidden_operations=["invent_claim", "replacement_text"],
            ))
        if inversions:
            problems.append(issue(
                "NARRATIVE-ORDER-INVERSION",
                severity="major" if inversions > 1 else "warning",
                scope="content_quality",
                observation="The declared reading order reverses part of the paper's problem-method-results progression",
                evidence={"reading_order": reading_order, "role_ranks": ranks},
                required_outcome="Restore a coherent reading sequence while preserving the selected layout family",
                allowed_operations=["set_reading_order", "move_section_to_zone"],
                forbidden_operations=["rewrite_claim", "switch_layout_family"],
            ))
        if excessive:
            problems.append(issue(
                "CONTENT-CLAIMS-VERBOSE",
                severity="major" if len(excessive) > 1 else "warning",
                scope="content_quality",
                observation="One or more visible claims are too long for concise poster reading",
                evidence={"claims": [{"claim_id": item, "word_count": words} for item, words in excessive[:8]]},
                required_outcome="Create shorter verified variants without changing scientific meaning",
                allowed_operations=["create_compact_variant"],
                forbidden_operations=["replacement_text", "rewrite_claim"],
            ))
        if submetrics["information_layering"] < 75:
            problems.append(issue(
                "CONTENT-LAYERING-WEAK",
                severity="major",
                scope="visual_hierarchy",
                observation="Section importance and the primary anchor do not express a clear information hierarchy",
                evidence={
                    "importance_levels": sorted(importance_levels),
                    "anchor_section_ids": sorted(anchor_sections),
                    "high_importance_section_ids": sorted(high_importance_ids),
                },
                required_outcome="Make a high-importance grounded section the primary anchor",
                allowed_operations=["set_section_importance", "move_section_to_zone", "set_primary_anchor"],
                forbidden_operations=["invent_section", "rewrite_claim"],
            ))

        score = round(sum(submetrics.values()) / len(submetrics), 2)
        positives = []
        if score >= 85:
            positives.append({
                "scope": "content_quality",
                "observation": "The poster preserves broad grounded coverage with a concise, coherent narrative",
            })
        return _result(
            context,
            self.name,
            passed=True,
            scores={"content_quality": score},
            issues=problems,
            metadata={
                "submetrics": submetrics,
                "semantic_model_completed": bool(semantic),
                "visible_claim_count": len(visible_claim_ids),
                "used_evidence_count": len(used_evidence),
                "assigned_evidence_count": len(assigned_evidence),
            },
            positives=positives,
        )

    def _semantic_scores(
        self,
        context: CriticContext,
        sections: List[Dict[str, Any]],
        claims: Dict[str, Dict[str, Any]],
        deterministic: Dict[str, float],
    ) -> Dict[str, float]:
        settings = _settings(context, self.name)
        if not settings.get("semantic_enabled", True) or not context.state.get("text_model"):
            return {}
        payload = {
            "layout_family": (context.state.get("layout_spec") or {}).get("family_id"),
            "reading_order": (context.state.get("layout_spec") or {}).get("reading_order", []),
            "deterministic_scores": deterministic,
            "sections": [
                {
                    "section_id": section.get("section_id"),
                    "section_title": section.get("section_title"),
                    "importance_level": section.get("importance_level"),
                    "claims": [
                        {
                            "claim_id": claim_id,
                            "text": claims.get(str(claim_id), {}).get("text", ""),
                            "evidence_ids": claims.get(str(claim_id), {}).get("evidence_ids", []),
                        }
                        for claim_id in section.get("claim_ids", [])
                    ],
                }
                for section in sections
            ],
        }
        try:
            config = apply_agent_policy(context.state["text_model"], "critic_content")
            agent = LangGraphAgent(
                "You are a strict evidence-grounded academic-poster content critic.",
                config,
                context.state,
                "critic_content",
            )
            response = agent.step(
                self.prompt + "\n\nINPUT DATA:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
            )
            context.state["tokens"].add_text(
                int(response.input_tokens), int(response.output_tokens)
            )
            raw = extract_json(response.content)
            raw_scores = raw.get("scores") if isinstance(raw, dict) else {}
            return {
                key: _clamp(raw_scores.get(key))
                for key in self._SUBMETRICS
                if isinstance(raw_scores, dict) and key in raw_scores
            }
        except Exception:
            return {}


def _hex_rgb(value: Any) -> Optional[Tuple[int, int, int]]:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not match:
        return None
    raw = match.group(1)
    return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))


def _luminance(rgb: Tuple[int, int, int]) -> float:
    values = []
    for channel in rgb:
        normalized = channel / 255.0
        values.append(
            normalized / 12.92
            if normalized <= 0.03928
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def _contrast(left: Any, right: Any) -> Optional[float]:
    left_rgb = _hex_rgb(left)
    right_rgb = _hex_rgb(right)
    if left_rgb is None or right_rgb is None:
        return None
    high, low = sorted((_luminance(left_rgb), _luminance(right_rgb)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ColorQualityEvaluator:
    """Check palette validity, provenance, semantic consistency, and WCAG contrast."""

    name = "color_quality"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        scheme = context.state.get("color_scheme") or {}
        threshold = float(settings.get("minimum_contrast_ratio", 4.5))
        problems: List[Dict[str, Any]] = []
        palette_keys = ("theme", "mono_light", "mono_dark", "text", "text_on_theme", "contrast")
        invalid = [key for key in palette_keys if _hex_rgb(scheme.get(key)) is None]
        if invalid:
            problems.append(issue(
                "COLOR-PALETTE-INVALID",
                severity="critical",
                scope="color",
                observation="The resolved poster palette contains missing or invalid colors",
                evidence={"invalid_keys": invalid},
                required_outcome="Regenerate a complete accessible palette from an approved source",
                allowed_operations=["use_accessible_palette_variant", "normalize_semantic_colors"],
            ))

        backgrounds = {"white": "#FFFFFF"}
        if _hex_rgb(scheme.get("mono_light")):
            backgrounds["mono_light"] = scheme["mono_light"]
        pairs = []
        if not invalid:
            for background_name, background in backgrounds.items():
                pairs.append(("body_text", background_name, scheme["text"], background))
                pairs.append(("highlight", background_name, scheme["contrast"], background))
            pairs.append(("text_on_theme", "theme", scheme["text_on_theme"], scheme["theme"]))

        ratios: Dict[str, float] = {}
        failed_pairs = []
        for role, background_name, foreground, background in pairs:
            ratio = _contrast(foreground, background)
            if ratio is None:
                continue
            key = f"{role}_on_{background_name}"
            ratios[key] = round(ratio, 3)
            if ratio < threshold:
                failed_pairs.append({"pair": key, "ratio": round(ratio, 3)})
        if failed_pairs:
            problems.append(issue(
                "COLOR-CONTRAST-INSUFFICIENT",
                severity="critical",
                scope="color",
                observation="One or more rendered text roles fail the configured WCAG contrast ratio",
                evidence={"minimum_ratio": threshold, "failed_pairs": failed_pairs},
                required_outcome="Use a deterministic accessible foreground/palette variant with at least 4.5:1 contrast",
                allowed_operations=["repair_text_contrast", "use_accessible_palette_variant", "reduce_accent_density"],
                forbidden_operations=["supply_raw_hex_color", "reduce_font_below_minimum"],
            ))

        provenance = context.state.get("color_provenance") or {}
        source_known = str(provenance.get("source", "")).lower() in {
            "affiliation_logo", "key_visual", "configured_fallback", "critic_accessible_variant"
        }
        if not source_known:
            problems.append(issue(
                "COLOR-SOURCE-UNKNOWN",
                severity="warning",
                scope="color",
                observation="The palette source is not recorded",
                evidence={"provenance": provenance},
                required_outcome="Record whether the theme came from the affiliation logo, key visual, or configured fallback",
                allowed_operations=["normalize_semantic_colors"],
            ))

        minimum_ratio = min(ratios.values()) if ratios else 0.0
        contrast_score = min(100.0, minimum_ratio / threshold * 100.0) if ratios else 0.0
        palette_score = 100.0 if not invalid else max(0.0, 100.0 - len(invalid) * 20.0)
        source_score = 100.0 if source_known else 70.0
        submetrics = {
            "color_palette": round(palette_score, 2),
            "color_hierarchy": 90.0 if scheme.get("contrast") != scheme.get("theme") else 65.0,
            "color_contrast": round(contrast_score, 2),
            "color_source": source_score,
        }
        readability = submetrics["color_contrast"]
        aesthetics = round(
            submetrics["color_palette"] * 0.45
            + submetrics["color_hierarchy"] * 0.35
            + submetrics["color_source"] * 0.20,
            2,
        )
        critical = any(item.get("severity") == "critical" for item in problems)
        return _result(
            context,
            self.name,
            passed=not critical,
            scores={"readability": readability, "aesthetics": aesthetics},
            issues=problems,
            metadata={
                "submetrics": submetrics,
                "contrast_ratios": ratios,
                "palette_source": provenance,
            },
            positives=[{
                "scope": "color",
                "observation": "The palette has recorded provenance and all text roles meet WCAG contrast",
            }] if not problems else [],
        )


def _asset_record(state: Dict[str, Any], visual_id: str) -> Optional[Dict[str, Any]]:
    raw = str(visual_id)
    if raw.startswith("figure_"):
        key = raw[len("figure_"):]
        return (state.get("images") or {}).get(key) or (state.get("images") or {}).get(raw)
    if raw.startswith("table_"):
        key = raw[len("table_"):]
        return (state.get("tables") or {}).get(key) or (state.get("tables") or {}).get(raw)
    return (state.get("images") or {}).get(raw) or (state.get("tables") or {}).get(raw)


class VisualAssetEvaluator:
    """Validate provenance, uniqueness, aspect ratio, and effective resolution."""

    name = "visual_assets"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        state = context.state
        visual_ids = [
            str(asset.get("visual_id"))
            for section in _sections(state)
            for asset in section.get("visual_assets", [])
            if isinstance(asset, dict) and asset.get("visual_id")
        ]
        counts = Counter(visual_ids)
        layout_visuals = {
            str(item.get("visual_id")): item
            for item in (state.get("styled_layout") or state.get("design_layout") or [])
            if item.get("type") == "visual" and item.get("visual_id")
        }
        problems: List[Dict[str, Any]] = []
        metadata_assets: Dict[str, Any] = {}
        score = 100.0
        for visual_id in sorted(set(visual_ids)):
            record = _asset_record(state, visual_id)
            if not isinstance(record, dict):
                problems.append(issue(
                    f"VISUAL-ASSET-UNKNOWN-{visual_id}",
                    severity="critical",
                    scope="visual_relevance",
                    location={"visual_id": visual_id},
                    observation="The poster references a visual that is not present in the approved paper assets",
                    required_outcome="Remove or replace the visual with an approved paper figure/table",
                    allowed_operations=["remove_visual", "replace_visual"],
                    forbidden_operations=["invent_visual"],
                ))
                score -= 40.0
                continue
            path = Path(str(record.get("path") or ""))
            if not path.is_file():
                problems.append(issue(
                    f"VISUAL-ASSET-MISSING-{visual_id}",
                    severity="critical",
                    scope="visual_relevance",
                    location={"visual_id": visual_id},
                    observation="An approved visual asset file is missing",
                    required_outcome="Restore the extracted asset or remove it from the poster",
                    allowed_operations=["remove_visual", "replace_visual", "rerender_candidate"],
                    forbidden_operations=["invent_visual"],
                ))
                score -= 40.0
                continue

            entry: Dict[str, Any] = {"path": str(path), "placements": counts[visual_id]}
            rendered = layout_visuals.get(visual_id)
            try:
                with Image.open(path) as image:
                    pixel_width, pixel_height = image.size
                source_aspect = pixel_width / max(pixel_height, 1)
                entry.update({
                    "pixel_size": [pixel_width, pixel_height],
                    "source_aspect": round(source_aspect, 4),
                })
                if rendered:
                    rendered_width = float(rendered.get("width", 0.0))
                    rendered_height = float(rendered.get("height", 0.0))
                    rendered_aspect = rendered_width / rendered_height if rendered_height > 0 else 0.0
                    deviation = abs(rendered_aspect - source_aspect) / source_aspect if source_aspect else 1.0
                    dpi = pixel_width / rendered_width if rendered_width > 0 else 0.0
                    entry.update({
                        "rendered_aspect": round(rendered_aspect, 4),
                        "aspect_deviation": round(deviation, 4),
                        "effective_dpi": round(dpi, 2),
                    })
                    if deviation > float(settings.get("maximum_aspect_deviation", 0.03)):
                        problems.append(issue(
                            f"VISUAL-ASSET-DISTORTED-{visual_id}",
                            severity="major",
                            scope="visual_relevance",
                            location={"visual_id": visual_id},
                            observation="A visual is rendered with a distorted aspect ratio",
                            evidence={"aspect_deviation": round(deviation, 4)},
                            required_outcome="Restore the source aspect ratio through deterministic layout",
                            allowed_operations=["restore_visual_aspect_ratio", "move_visual"],
                        ))
                        score -= 20.0
                    if dpi < float(settings.get("minimum_effective_dpi", 72.0)):
                        problems.append(issue(
                            f"VISUAL-ASSET-LOW-RESOLUTION-{visual_id}",
                            severity="major",
                            scope="visual_relevance",
                            location={"visual_id": visual_id},
                            observation="A visual has insufficient effective resolution at its rendered size",
                            evidence={"effective_dpi": round(dpi, 2)},
                            required_outcome="Use a smaller rendering or another approved higher-resolution visual",
                            allowed_operations=["move_visual", "replace_visual", "remove_visual"],
                            forbidden_operations=["invent_visual"],
                        ))
                        score -= 15.0
            except Exception:
                problems.append(issue(
                    f"VISUAL-ASSET-UNREADABLE-{visual_id}",
                    severity="critical",
                    scope="visual_relevance",
                    location={"visual_id": visual_id},
                    observation="A paper visual cannot be decoded as an image",
                    required_outcome="Remove or replace the unreadable asset",
                    allowed_operations=["remove_visual", "replace_visual"],
                ))
                score -= 40.0
            metadata_assets[visual_id] = entry

        duplicates = sorted(item for item, count in counts.items() if count > 1)
        if duplicates:
            problems.append(issue(
                "VISUAL-ASSET-DUPLICATED",
                severity="major",
                scope="visual_relevance",
                observation="The same paper visual appears in more than one poster section",
                evidence={"visual_ids": duplicates},
                required_outcome="Keep one purposeful occurrence of each visual",
                allowed_operations=["remove_visual", "replace_visual"],
            ))
            score -= len(duplicates) * 15.0

        critical = any(item.get("severity") == "critical" for item in problems)
        score = _clamp(score)
        source_manifest = state.get("layout_visual_source_manifest") or {}
        source_ids = {
            str(visual_id)
            for ids in source_manifest.values()
            for visual_id in ids
        }
        omitted_source_ids = sorted(source_ids - set(visual_ids))
        key_visual = (state.get("classified_visuals") or {}).get("key_visual")
        available_ids = {
            f"{prefix}_{key}"
            for prefix, field in (("figure", "images"), ("table", "tables"))
            for key in (state.get(field) or {})
        }
        curated_ids = {
            str(item.get("visual_id"))
            for section in (state.get("story_board") or {}).get("spatial_content_plan", {}).get("sections", [])
            for item in section.get("visual_assets") or []
            if isinstance(item, dict) and item.get("visual_id")
        }
        return _result(
            context,
            self.name,
            passed=not critical,
            scores={"aesthetics": score},
            issues=problems,
            metadata={
                "submetrics": {
                    "visual_provenance": 0.0 if critical else 100.0,
                    "visual_asset_presentation": score,
                },
                "assets": metadata_assets,
                "source_visual_selection": {
                    "available_visual_ids": sorted(available_ids),
                    "curated_visual_ids": sorted(curated_ids),
                    "uncurated_visual_ids": sorted(available_ids - curated_ids),
                    "visible_visual_ids": sorted(set(visual_ids)),
                    "key_visual_uncurated": bool(
                        isinstance(key_visual, str)
                        and key_visual in available_ids - curated_ids
                    ),
                    "classification_policy_version": (
                        (state.get("visual_classification_report") or {}).get("policy_version")
                        or "legacy_unversioned"
                    ),
                    "source_visual_ids": sorted(source_ids),
                    "omitted_source_visual_ids": omitted_source_ids,
                    "key_visual_omitted": bool(
                        isinstance(key_visual, str) and key_visual in omitted_source_ids
                    ),
                    "capacity_restore_attempts": (
                        (state.get("capacity_repair_report") or {}).get("visual_restoration") or []
                    ),
                },
            },
            positives=[{
                "scope": "visual_relevance",
                "observation": "All visible figures and tables are unique, decodable paper assets rendered without distortion",
            }] if visual_ids and not problems else [],
        )
