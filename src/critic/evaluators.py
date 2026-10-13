"""Deterministic poster evaluators used as Critic hard gates."""

import math
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from PIL import Image

from src.critic.base import CriticContext, EvaluationResult, issue
from src.critic.quality import (
    ColorQualityEvaluator,
    InformationNarrativeEvaluator,
    VisualAssetEvaluator,
)
from src.critic.section_fit import ContentAdequacyEvaluator, SectionFitEvaluator
from utils.grounded_content import all_publishable_claims


def _settings(context: CriticContext, name: str) -> Dict[str, Any]:
    return context.config["evaluators"].get(name, {})


def _result(
    context: CriticContext,
    name: str,
    *,
    passed: bool,
    scores: Dict[str, float],
    issues: List[Dict[str, Any]],
    positive_patterns: List[Dict[str, Any]] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> EvaluationResult:
    settings = _settings(context, name)
    return EvaluationResult(
        evaluator=name,
        version=str(settings.get("version", "1.0.0")),
        hard_gate=bool(settings.get("hard_gate", False)),
        passed=passed,
        scores=scores,
        issues=issues,
        positive_patterns=positive_patterns or [],
        metadata=metadata or {},
    )


class RenderArtifactEvaluator:
    name = "render_artifacts"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        candidate = context.state.get("current_candidate") or {}
        issues: List[Dict[str, Any]] = []
        metadata: Dict[str, Any] = {}

        requirements = (
            ("pptx", bool(settings.get("require_pptx", True))),
            ("png", bool(settings.get("require_png", True))),
        )
        for artifact_type, required in requirements:
            raw_path = candidate.get(f"{artifact_type}_path")
            path = Path(raw_path) if raw_path else None
            exists = bool(path and path.is_file() and path.stat().st_size > 0)
            metadata[f"{artifact_type}_exists"] = exists
            if required and not exists:
                issues.append(issue(
                    f"ARTIFACT-{artifact_type.upper()}-MISSING",
                    severity="critical",
                    scope="renderer",
                    observation=f"Required {artifact_type.upper()} artifact is missing",
                    required_outcome=f"Render a valid {artifact_type.upper()} artifact",
                    allowed_operations=["rerender_candidate"],
                ))
                continue

            if not exists:
                continue
            valid = True
            try:
                if artifact_type == "pptx":
                    valid = zipfile.is_zipfile(path)
                else:
                    with Image.open(path) as image:
                        image.verify()
            except Exception:
                valid = False
            metadata[f"{artifact_type}_valid"] = valid
            if not valid:
                issues.append(issue(
                    f"ARTIFACT-{artifact_type.upper()}-INVALID",
                    severity="critical",
                    scope="renderer",
                    observation=f"Rendered {artifact_type.upper()} artifact is invalid",
                    required_outcome=f"Regenerate a readable {artifact_type.upper()} file",
                    allowed_operations=["rerender_candidate"],
                ))

        passed = not issues
        return _result(
            context,
            self.name,
            passed=passed,
            # Artifact validity is a hard gate, not an aesthetic/layout score.
            scores={},
            issues=issues,
            metadata=metadata,
        )


class GeometryEvaluator:
    name = "geometry"
    _OVERLAP_TYPES = {
        "title",
        "section_title",
        "text",
        "visual",
        "conf_logo",
        "aff_logo",
        "qr_code",
    }

    @staticmethod
    def _box(element: Dict[str, Any]) -> Tuple[float, float, float, float] | None:
        try:
            x = float(element["x"])
            y = float(element["y"])
            width = float(element["width"])
            height = float(element["height"])
        except (KeyError, TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (x, y, width, height)):
            return None
        return x, y, width, height

    @staticmethod
    def _identity(element: Dict[str, Any], index: int) -> str:
        return str(
            element.get("id")
            or element.get("section_id")
            or element.get("visual_id")
            or f"{element.get('type', 'element')}_{index}"
        )

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        state = context.state
        layout = state.get("styled_layout") or state.get("design_layout") or []
        poster_width = float(state.get("poster_width", 0))
        poster_height = float(state.get("poster_height", 0))
        tolerance = float(settings.get("bounds_tolerance_inches", 0.02))
        area_tolerance = float(settings.get("overlap_area_tolerance", 0.02))
        ratio_tolerance = float(settings.get("overlap_ratio_tolerance", 0.05))
        issues: List[Dict[str, Any]] = []
        boxes: List[Tuple[int, Dict[str, Any], Tuple[float, float, float, float]]] = []

        render_fit = state.get("render_fit_report") or {}
        if render_fit.get("status") == "failed":
            for index, finding in enumerate(render_fit.get("issues") or [], start=1):
                issues.append(issue(
                    f"{finding.get('code') or 'RENDER-TEXT-FIT'}-{index}",
                    severity="critical",
                    scope="layout",
                    location={
                        "section_id": finding.get("section_id"),
                        "zone_id": finding.get("zone_id"),
                    },
                    observation=("Rendered title is too close to its module content"
                                 if finding.get("code") == "RENDER_TITLE_CONTENT_GAP"
                                 else "A confirmed rendered-text failure could not be verified after correction"
                                 if finding.get("code") == "RENDER_CORRECTION_UNVERIFIED"
                                 else "Rendered editable text exceeds its planned box or collides with another module"),
                    evidence={key: value for key, value in finding.items()
                              if key not in {"code", "section_id", "zone_id"}},
                    required_outcome="Reflow verified text or choose safe geometry without reducing fonts below the minimum",
                    allowed_operations=["adjust_zone_budget", "move_section_to_zone", "create_compact_variant"],
                    forbidden_operations=["invent_claim", "reduce_font_below_minimum"],
                ))

        for index, element in enumerate(layout):
            box = self._box(element)
            element_id = self._identity(element, index)
            if box is None:
                issues.append(issue(
                    f"GEOMETRY-INVALID-{index}",
                    severity="critical",
                    scope="layout",
                    location={"element_id": element_id},
                    observation="Element has missing or non-finite geometry",
                    required_outcome="Provide finite x, y, width, and height values",
                    allowed_operations=["recompute_layout"],
                ))
                continue
            x, y, width, height = box
            if width <= 0 or height <= 0:
                issues.append(issue(
                    f"GEOMETRY-SIZE-{index}",
                    severity="critical",
                    scope="layout",
                    location={"element_id": element_id},
                    observation="Element has a non-positive size",
                    required_outcome="Assign a positive width and height",
                    allowed_operations=["recompute_layout"],
                ))
                continue
            if (
                x < -tolerance
                or y < -tolerance
                or x + width > poster_width + tolerance
                or y + height > poster_height + tolerance
            ):
                issues.append(issue(
                    f"GEOMETRY-BOUNDS-{index}",
                    severity="critical",
                    scope="layout",
                    location={"element_id": element_id},
                    observation="Element extends outside the poster canvas",
                    evidence={
                        "box": [x, y, width, height],
                        "poster": [poster_width, poster_height],
                    },
                    required_outcome="Place the complete element inside the poster bounds",
                    allowed_operations=["move_section_to_zone", "reduce_spacing", "remove_low_priority_claim"],
                    forbidden_operations=["rewrite_claim", "reduce_font_below_minimum"],
                ))
            if element.get("type") in self._OVERLAP_TYPES:
                boxes.append((index, element, box))

        for left_index in range(len(boxes)):
            index_a, element_a, box_a = boxes[left_index]
            ax, ay, aw, ah = box_a
            for index_b, element_b, box_b in boxes[left_index + 1:]:
                bx, by, bw, bh = box_b
                overlap_width = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
                overlap_height = max(0.0, min(ay + ah, by + bh) - max(ay, by))
                overlap_area = overlap_width * overlap_height
                smaller_area = min(aw * ah, bw * bh)
                overlap_ratio = overlap_area / smaller_area if smaller_area else 0.0
                if overlap_area <= area_tolerance or overlap_ratio <= ratio_tolerance:
                    continue
                first_id = self._identity(element_a, index_a)
                second_id = self._identity(element_b, index_b)
                issues.append(issue(
                    f"GEOMETRY-OVERLAP-{index_a}-{index_b}",
                    severity="critical",
                    scope="layout",
                    location={"element_ids": [first_id, second_id]},
                    observation="Visible poster elements overlap",
                    evidence={
                        "overlap_area_inches_squared": round(overlap_area, 4),
                        "overlap_ratio": round(overlap_ratio, 4),
                    },
                    required_outcome="Separate the overlapping visible elements",
                    allowed_operations=["move_section_to_zone", "reduce_spacing", "remove_low_priority_claim"],
                    forbidden_operations=["rewrite_claim", "reduce_font_below_minimum"],
                ))

        critical_count = sum(item["severity"] == "critical" for item in issues)
        score = max(0.0, 100.0 - critical_count * 25.0)
        return _result(
            context,
            self.name,
            passed=critical_count == 0,
            scores={"layout_integrity": score},
            issues=issues,
            metadata={"element_count": len(layout)},
        )


class GroundingEvaluator:
    name = "grounding"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        state = context.state
        claim_index = all_publishable_claims(state)
        board = state.get("optimized_story_board") or state.get("story_board") or {}
        sections = board.get("spatial_content_plan", {}).get("sections", [])
        issues: List[Dict[str, Any]] = []
        seen = set()

        if state.get("scientific_guard_violation"):
            issues.append(issue(
                "GROUNDING-FROZEN-STATE-MUTATED",
                severity="critical",
                scope="scientific_integrity",
                observation="A design-stage agent attempted to mutate frozen scientific state",
                required_outcome="Keep extraction, evidence, and verified claims immutable during design iteration",
                forbidden_operations=["rewrite_claim", "invent_claim"],
            ))

        if not claim_index:
            issues.append(issue(
                "GROUNDING-NO-VERIFIED-CLAIMS",
                severity="critical",
                scope="scientific_integrity",
                observation="No verified claim bank is available",
                required_outcome="Evaluate only posters backed by verified claims",
            ))

        for section_index, section in enumerate(sections):
            claim_ids = section.get("claim_ids", [])
            texts = section.get("text_content", [])
            if len(claim_ids) != len(texts):
                issues.append(issue(
                    f"GROUNDING-LENGTH-{section_index}",
                    severity="critical",
                    scope="scientific_integrity",
                    location={"section_id": section.get("section_id")},
                    observation="Claim IDs and visible claim texts are not aligned",
                    required_outcome="Rebuild section text directly from verified claim IDs",
                    allowed_operations=["restore_verified_claim_text"],
                    forbidden_operations=["rewrite_claim"],
                ))
            for position, claim_id in enumerate(claim_ids):
                verified_claim = claim_index.get(claim_id)
                if verified_claim is None:
                    issues.append(issue(
                        f"GROUNDING-UNKNOWN-{section_index}-{position}",
                        severity="critical",
                        scope="scientific_integrity",
                        location={"section_id": section.get("section_id"), "claim_id": claim_id},
                        observation="Poster references an unknown claim ID",
                        required_outcome="Remove unknown claims",
                        allowed_operations=["remove_claim"],
                        forbidden_operations=["invent_claim"],
                    ))
                    continue
                if claim_id in seen:
                    issues.append(issue(
                        f"GROUNDING-DUPLICATE-{claim_id}",
                        severity="critical",
                        scope="scientific_integrity",
                        location={"claim_id": claim_id},
                        observation="The same verified claim appears more than once",
                        required_outcome="Keep a single occurrence of the claim",
                        allowed_operations=["remove_claim"],
                    ))
                seen.add(claim_id)
                visible_text = texts[position] if position < len(texts) else None
                if visible_text != verified_claim.get("text"):
                    issues.append(issue(
                        f"GROUNDING-TEXT-{claim_id}",
                        severity="critical",
                        scope="scientific_integrity",
                        location={"section_id": section.get("section_id"), "claim_id": claim_id},
                        observation="Poster claim text differs from its verified source",
                        required_outcome="Restore the exact verified claim text",
                        allowed_operations=["restore_verified_claim_text"],
                        forbidden_operations=["rewrite_claim"],
                    ))

        passed = not issues
        positives = []
        if passed:
            positives.append({
                "scope": "scientific_integrity",
                "observation": "All published claim text is traceable to verified claim IDs",
            })
        return _result(
            context,
            self.name,
            passed=passed,
            scores={"scientific_integrity": 100.0 if passed else 0.0},
            issues=issues,
            positive_patterns=positives,
            metadata={"published_claim_count": len(seen)},
        )


class TypographyEvaluator:
    name = "typography"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        layout = context.state.get("styled_layout") or context.state.get("design_layout") or []
        minimums = {
            "text": float(settings.get("minimum_body_font_size", 36)),
            "section_title": float(settings.get("minimum_section_title_font_size", 36)),
            "title": float(settings.get("minimum_title_font_size", 48)),
        }
        issues: List[Dict[str, Any]] = []
        sizes: Dict[str, List[float]] = {key: [] for key in minimums}
        font_families = set()
        emphasized = 0
        words = 0
        checked = 0
        for index, element in enumerate(layout):
            element_type = element.get("type")
            if element_type not in minimums:
                continue
            checked += 1
            try:
                font_size = float(element.get("font_size", 0))
            except (TypeError, ValueError):
                font_size = 0.0
            sizes[element_type].append(font_size)
            if element.get("font_family"):
                font_families.add(str(element["font_family"]))
            content = str(element.get("content") or "")
            words += len(content.split())
            emphasized += content.count("<color:") + content.count("**") // 2
            minimum = minimums[element_type]
            if font_size >= minimum:
                continue
            issues.append(issue(
                f"TYPOGRAPHY-MINIMUM-{index}",
                severity="critical",
                scope="typography",
                location={"element_id": element.get("id", f"{element_type}_{index}")},
                observation=f"{element_type} font size is below the configured minimum",
                evidence={"font_size": font_size, "minimum": minimum},
                required_outcome="Meet the minimum readable font size without changing claim text",
                allowed_operations=["remove_low_priority_claim", "move_section_to_zone", "reduce_spacing"],
                forbidden_operations=["reduce_font_below_minimum", "rewrite_claim"],
            ))

        body = max(sizes["text"] or [0.0])
        section = max(sizes["section_title"] or [0.0])
        title = max(sizes["title"] or [0.0])
        hierarchy_score = 100.0
        if body and section and section < body * float(settings.get("section_to_body_ratio", 1.10)):
            hierarchy_score -= 25.0
            issues.append(issue(
                "TYPOGRAPHY-SECTION-HIERARCHY-WEAK",
                severity="major",
                scope="visual_hierarchy",
                observation="Section headings are not sufficiently separated from body text",
                required_outcome="Use the deterministic stronger heading hierarchy preset",
                allowed_operations=["increase_title_separation", "normalize_typography_hierarchy"],
                forbidden_operations=["supply_raw_font_size", "rewrite_claim"],
            ))
        if section and title and title < section * float(settings.get("title_to_section_ratio", 1.25)):
            hierarchy_score -= 25.0
            issues.append(issue(
                "TYPOGRAPHY-TITLE-HIERARCHY-WEAK",
                severity="major",
                scope="visual_hierarchy",
                observation="The poster title does not clearly dominate section headings",
                required_outcome="Use the deterministic stronger title hierarchy preset",
                allowed_operations=["increase_title_separation", "normalize_typography_hierarchy"],
                forbidden_operations=["supply_raw_font_size"],
            ))
        emphasis_ratio = emphasized / max(words, 1)
        emphasis_score = max(0.0, 100.0 - max(0.0, emphasis_ratio - 0.20) * 200.0)
        if emphasis_ratio > float(settings.get("maximum_emphasis_ratio", 0.35)):
            hierarchy_score -= 20.0
            issues.append(issue(
                "TYPOGRAPHY-EMPHASIS-EXCESSIVE",
                severity="major",
                scope="visual_hierarchy",
                observation="Too much body text is emphasized, weakening scan hierarchy",
                evidence={"emphasis_ratio": round(emphasis_ratio, 4)},
                required_outcome="Reserve emphasis for a smaller set of meaningful keywords",
                allowed_operations=["reduce_accent_density"],
                forbidden_operations=["rewrite_claim"],
            ))
        maximum_families = int(settings.get("maximum_font_families", 2))
        family_score = max(0.0, 100.0 - max(0, len(font_families) - maximum_families) * 25.0)
        if len(font_families) > maximum_families:
            issues.append(issue(
                "TYPOGRAPHY-FONT-FAMILIES-EXCESSIVE",
                severity="major",
                scope="aesthetics",
                observation="The poster uses too many font families",
                evidence={"font_families": sorted(font_families)},
                required_outcome="Normalize typography to the deterministic poster font preset",
                allowed_operations=["normalize_font_family"],
                forbidden_operations=["supply_raw_font_family"],
            ))

        critical = sum(item["severity"] == "critical" for item in issues)
        readability = max(0.0, 100.0 - critical * 30.0)
        return _result(
            context,
            self.name,
            passed=critical == 0,
            scores={
                "readability": readability,
                "visual_hierarchy": max(0.0, hierarchy_score),
                "aesthetics": family_score,
            },
            issues=issues,
            metadata={
                "checked_text_elements": checked,
                "font_families": sorted(font_families),
                "emphasis_ratio": round(emphasis_ratio, 4),
                "submetrics": {
                    "font_legibility": readability,
                    "font_hierarchy": max(0.0, hierarchy_score),
                    "font_emphasis": round(emphasis_score, 2),
                },
            },
        )


class ColumnBalanceEvaluator:
    name = "column_balance"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        analysis = context.state.get("final_column_analysis") or {}
        columns = analysis.get("regions") or analysis.get("columns", {})
        group_kind = "region" if analysis.get("regions") else "column"
        maximum = float(settings.get("maximum_utilization", 1.0))
        preferred_minimum = float(settings.get("preferred_minimum_utilization", 0.65))
        issues: List[Dict[str, Any]] = []
        utilizations: Dict[str, float] = {}

        for column, details in columns.items():
            utilization = float(details.get("utilization_rate", 0.0))
            utilizations[column] = utilization
            if utilization > maximum:
                issues.append(issue(
                    f"COLUMN-OVERFLOW-{column.upper()}",
                    severity="critical",
                    scope="layout",
                    location={group_kind: column},
                    observation=f"{column} {group_kind} exceeds physical capacity",
                    evidence={
                        "utilization_rate": round(utilization, 4),
                        "maximum": maximum,
                        "excess_height": details.get("excess_height", 0),
                    },
                    required_outcome="Remove the overflow while preserving readable font sizes",
                    allowed_operations=["move_section_to_zone", "remove_low_priority_claim", "remove_visual", "reduce_spacing"],
                    forbidden_operations=["rewrite_claim", "reduce_font_below_minimum"],
                ))
            elif utilization < preferred_minimum:
                issues.append(issue(
                    f"COLUMN-UNDERUSE-{column.upper()}",
                    severity="warning",
                    scope="layout",
                    location={group_kind: column},
                    observation=f"{column} {group_kind} is substantially underused",
                    evidence={"utilization_rate": round(utilization, 4)},
                    required_outcome="Improve column balance without filling space artificially",
                    allowed_operations=["move_section_to_zone", "set_reading_order"],
                    forbidden_operations=["invent_claim"],
                ))

        hard_failures = [item for item in issues if item["severity"] == "critical"]
        if utilizations:
            spread = max(utilizations.values()) - min(utilizations.values())
            score = max(0.0, 100.0 - spread * 70.0 - len(hard_failures) * 30.0)
        else:
            score = 0.0
            hard_failures.append(issue(
                "REGION-ANALYSIS-MISSING",
                severity="critical",
                scope="layout",
                observation="Final layout-region utilization analysis is missing",
                required_outcome="Recompute final layout-region utilization",
                allowed_operations=["recompute_layout"],
            ))
            issues.extend(hard_failures)

        return _result(
            context,
            self.name,
            passed=not hard_failures,
            scores={
                "layout_integrity": score,
                "visual_balance": score,
            },
            issues=issues,
            metadata={"group_kind": group_kind, "region_utilization": utilizations},
        )


DEFAULT_DETERMINISTIC_EVALUATORS: Iterable[type] = (
    RenderArtifactEvaluator,
    GeometryEvaluator,
    GroundingEvaluator,
    InformationNarrativeEvaluator,
    TypographyEvaluator,
    ColorQualityEvaluator,
    VisualAssetEvaluator,
    ColumnBalanceEvaluator,
    SectionFitEvaluator,
    ContentAdequacyEvaluator,
)
