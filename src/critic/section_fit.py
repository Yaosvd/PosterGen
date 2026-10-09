"""Deterministic section utilization, whitespace, and content adequacy."""

from __future__ import annotations

import re
from statistics import median
from typing import Any, Dict, List

from src.config.poster_config import load_config
from src.critic.base import CriticContext, EvaluationResult, issue
from src.layout.whitespace import measure_composition_whitespace
from utils.grounded_content import all_publishable_claims


def _settings(context: CriticContext, name: str) -> Dict[str, Any]:
    return context.config.get("evaluators", {}).get(name, {})


def _result(
    context: CriticContext,
    name: str,
    *,
    passed: bool,
    scores: Dict[str, float],
    issues: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    positives: List[Dict[str, Any]] | None = None,
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
        metadata=metadata,
    )


def _safe_id(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(value)).strip("-").upper()


def _board_sections(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    board = state.get("optimized_story_board") or state.get("story_board") or {}
    return {
        str(section.get("section_id")): section
        for section in board.get("spatial_content_plan", {}).get("sections", [])
        if isinstance(section, dict) and section.get("section_id")
    }


class SectionFitEvaluator:
    """Measure intrinsic section height against an independent height budget."""

    name = "section_fit"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        state = context.state
        settings = _settings(context, self.name)
        layout = state.get("styled_layout") or state.get("design_layout") or []
        containers = [
            element
            for element in layout
            if isinstance(element, dict)
            and element.get("type") == "section_container"
            and element.get("section_id")
        ]
        if not containers:
            missing = issue(
                "SECTION-FIT-MISSING",
                severity="critical",
                scope="layout",
                observation="Section containers are unavailable for utilization analysis",
                required_outcome="Render section containers with stable section IDs",
                allowed_operations=["recompute_layout"],
            )
            analysis = {
                "schema_version": 1,
                "sections": {},
                "gaps": [],
                "all_sections_ideal": False,
                "gaps_acceptable": False,
            }
            state["section_fit_analysis"] = analysis
            return _result(
                context,
                self.name,
                passed=False,
                scores={"layout_integrity": 0.0, "visual_balance": 0.0},
                issues=[missing],
                metadata={"section_fit": analysis},
            )

        poster_config = load_config()
        margin = float(poster_config.get("layout", {}).get("poster_margin", 1.0))
        width = float(state.get("poster_width", 54.0))
        height = float(state.get("poster_height", 36.0))
        board_sections = _board_sections(state)
        minimum = float(settings.get("ideal_minimum", 0.95))
        maximum = float(settings.get("ideal_maximum", 1.0))
        planning_target = float(settings.get("planning_target", 0.975))
        tolerance = float(settings.get("overflow_tolerance", 0.005))
        strong_underuse = float(settings.get("strong_underuse_threshold", 0.90))

        text_fonts = [
            float(element.get("font_size", 44.0))
            for element in layout
            if element.get("type") == "text"
            and isinstance(element.get("font_size"), (int, float))
        ]
        body_line_height = max(0.2, (median(text_fonts) if text_fonts else 44.0) / 72.0)
        preferred_gap = body_line_height * float(
            settings.get("preferred_gap_body_lines", 1.0)
        )
        maximum_gap = body_line_height * float(
            settings.get("maximum_gap_body_lines", 1.5)
        )
        critical_gap = body_line_height * float(
            settings.get("critical_gap_body_lines", 2.0)
        )

        layout_spec = state.get("layout_spec") or {}
        is_zoned = bool(
            layout_spec.get("family_id")
            and (
                layout_spec.get("family_id") != "classic_three_column"
                or state.get("generation_route") == "optimization_family"
            )
            and layout_spec.get("zones")
        )
        group_kind = "zone" if is_zoned else "column"
        if is_zoned:
            groups: Dict[str, List[Dict[str, Any]]] = {
                str(zone.get("zone_id")): []
                for zone in layout_spec.get("zones", [])
                if zone.get("zone_id")
            }
        else:
            groups = {"left": [], "middle": [], "right": []}
        for container in containers:
            section_id = str(container["section_id"])
            section = board_sections.get(section_id, {})
            group = str(container.get("zone_id") or "") if is_zoned else section.get("column_assignment")
            if group not in groups and not is_zoned:
                midpoint = float(container.get("x", 0.0)) + float(container.get("width", 0.0)) / 2
                group = "left" if midpoint < width / 3 else "middle" if midpoint < 2 * width / 3 else "right"
            if group in groups:
                groups[group].append(container)

        issues: List[Dict[str, Any]] = []
        section_metrics: Dict[str, Dict[str, Any]] = {}
        gap_metrics: List[Dict[str, Any]] = []
        section_scores: List[float] = []
        gap_scores: List[float] = []
        critical_failure = False
        empty_regions: List[str] = []
        region_utilization: Dict[str, float] = {}

        for group, group_containers in groups.items():
            if not group_containers:
                if is_zoned:
                    critical_failure = True
                    empty_regions.append(group)
                    region_utilization[group] = 0.0
                    section_scores.append(0.0)
                    issues.append(issue(
                        f"REGION-EMPTY-{_safe_id(group)}",
                        severity="critical",
                        scope="layout",
                        location={"zone_id": group},
                        observation=f"The {group} zone contains no scientific module",
                        required_outcome=(
                            "Assign a grounded module or choose a topology "
                            "without this unused zone"
                        ),
                        allowed_operations=[
                            "move_section_to_zone", "adjust_zone_budget"
                        ],
                        forbidden_operations=[
                            "invent_claim", "add_filler_text"
                        ],
                    ))
                continue
            ordered = sorted(group_containers, key=lambda item: float(item.get("y", 0.0)))
            top = min(float(item.get("y", 0.0)) for item in ordered)
            available = (
                max(0.1, max(float(item.get("planned_zone_height", 0.0)) for item in ordered))
                if is_zoned
                else max(0.1, height - margin - top)
            )
            content_space = max(0.1, available - preferred_gap * (len(ordered) - 1))
            weights = []
            for container in ordered:
                section = board_sections.get(str(container["section_id"]), {})
                try:
                    importance = int(container.get(
                        "importance_level", section.get("importance_level", 2)
                    ) or 2)
                except (TypeError, ValueError):
                    importance = 2
                base_weight = {1: 1.30, 2: 1.0, 3: 0.80}.get(importance, 1.0)
                visual_bonus = min(0.4, 0.2 * len(section.get("visual_assets", [])))
                weights.append(base_weight + visual_bonus)
            weight_total = sum(weights) or 1.0

            for container, weight in zip(ordered, weights):
                section_id = str(container["section_id"])
                intrinsic = max(0.0, float(container.get("height", 0.0)))
                allocated = content_space * weight / weight_total
                utilization = intrinsic / allocated if allocated else 0.0
                in_ideal = minimum <= utilization <= maximum + tolerance
                metric = {
                    "section_id": section_id,
                    "layout_region": group,
                    "region_kind": group_kind,
                    "intrinsic_height": round(intrinsic, 4),
                    "allocated_height": round(allocated, 4),
                    "utilization": round(utilization, 4),
                    "ideal_minimum": minimum,
                    "ideal_maximum": maximum,
                    "in_ideal_band": in_ideal,
                }
                section_metrics[section_id] = metric
                if utilization > maximum + tolerance:
                    reduction = max(0.0, intrinsic - allocated * planning_target)
                    issues.append(issue(
                        f"SECTION-ALLOCATION-IMBALANCE-{_safe_id(section_id)}",
                        severity="major",
                        scope="layout",
                        location={"section_id": section_id, f"{group_kind}_id" if is_zoned else "column": group},
                        observation=f"Section {section_id} exceeds its weighted target share; this alone does not prove physical overflow",
                        evidence={**metric, "required_reduction_inches": round(reduction, 4)},
                        required_outcome="Rebalance the module allocation without hiding or shrinking grounded content",
                        allowed_operations=[
                            "create_compact_variant", "move_claim", "remove_low_priority_claim",
                            "move_section_to_zone", "adjust_zone_budget",
                        ],
                        forbidden_operations=["invent_claim", "reduce_font_below_minimum"],
                    ))
                elif utilization < minimum:
                    severity = "major" if utilization < strong_underuse else "warning"
                    missing_height = max(0.0, allocated * planning_target - intrinsic)
                    issues.append(issue(
                        f"SECTION-UNDERFILLED-{_safe_id(section_id)}",
                        severity=severity,
                        scope="layout",
                        location={"section_id": section_id, f"{group_kind}_id" if is_zoned else "column": group},
                        observation=f"Section {section_id} uses less than 95% of its height budget",
                        evidence={**metric, "available_height_inches": round(missing_height, 4)},
                        required_outcome="Add useful grounded content or reduce/reallocate the module budget without filler",
                        allowed_operations=[
                            "add_existing_claim", "add_claim_from_evidence",
                            "move_section_to_zone", "adjust_zone_budget",
                        ],
                        forbidden_operations=["invent_claim", "add_filler_text"],
                    ))
                deviation = 0.0 if in_ideal else min(abs(utilization - planning_target), 1.0)
                section_scores.append(max(0.0, 100.0 - deviation * 180.0))

            for index, (current, following) in enumerate(zip(ordered, ordered[1:])):
                current_bottom = float(current.get("y", 0.0)) + float(current.get("height", 0.0))
                gap = max(0.0, float(following.get("y", 0.0)) - current_bottom)
                gap_entry = {
                    "layout_region": group,
                    "region_kind": group_kind,
                    "after_section_id": str(current["section_id"]),
                    "before_section_id": str(following["section_id"]),
                    "gap_inches": round(gap, 4),
                    "gap_body_lines": round(gap / body_line_height, 4),
                }
                gap_metrics.append(gap_entry)
                if gap > maximum_gap:
                    severity = "major" if gap > critical_gap else "warning"
                    issues.append(issue(
                        f"SECTION-GAP-LARGE-{_safe_id(group)}-{index + 1}",
                        severity=severity,
                        scope="layout",
                        location={f"{group_kind}_id" if is_zoned else "column": group, "after_section_id": current["section_id"]},
                        observation=f"Visible gap between modules in the {group} {group_kind} is too large",
                        evidence={**gap_entry, "target_gap_inches": round(preferred_gap, 4)},
                        required_outcome="Reduce visible inter-module whitespace while keeping sections distinct",
                        allowed_operations=["set_section_gap", "set_reading_order", "move_section_to_zone"],
                    ))
                gap_scores.append(max(0.0, 100.0 - max(0.0, gap - preferred_gap) / body_line_height * 30.0))

            last_bottom = max(
                float(item.get("y", 0.0)) + float(item.get("height", 0.0))
                for item in ordered
            )
            group_bottom = top + available
            if last_bottom > group_bottom + tolerance:
                critical_failure = True
                issues.append(issue(
                    f"REGION-PHYSICAL-OVERFLOW-{_safe_id(group)}",
                    severity="critical",
                    scope="layout",
                    location={f"{group_kind}_id" if is_zoned else "column": group},
                    observation=f"Content physically extends below the {group} {group_kind}",
                    evidence={"overflow_inches": round(last_bottom - group_bottom, 4)},
                    required_outcome="Fit grounded content within the actual region bounds",
                    allowed_operations=["adjust_zone_budget", "create_compact_variant"],
                    forbidden_operations=["invent_claim", "reduce_font_below_minimum"],
                ))
            bottom_gap = max(0.0, group_bottom - last_bottom)
            region_utilization[group] = round(
                max(0.0, min(1.0, (last_bottom - top) / available)),
                4,
            )
            if bottom_gap > critical_gap:
                severe_dead_space = (
                    is_zoned and region_utilization[group] < 0.55
                )
                if severe_dead_space:
                    critical_failure = True
                issues.append(issue(
                    f"REGION-BOTTOM-GAP-{_safe_id(group)}",
                    severity="critical" if severe_dead_space else "major",
                    scope="layout",
                    location={f"{group_kind}_id" if is_zoned else "column": group},
                    observation=f"The {group} {group_kind} leaves a large unused bottom area",
                    evidence={
                        "bottom_gap_inches": round(bottom_gap, 4),
                        "bottom_gap_body_lines": round(bottom_gap / body_line_height, 4),
                    },
                    required_outcome="Redistribute modules or add useful grounded content to reduce dead space",
                    allowed_operations=["move_section_to_zone", "add_existing_claim", "add_claim_from_evidence", "adjust_zone_budget"],
                    forbidden_operations=["add_filler_text"],
                ))

        all_ideal = bool(section_metrics) and not empty_regions and all(
            item["in_ideal_band"] for item in section_metrics.values()
        )
        gaps_acceptable = all(
            float(item["gap_inches"]) <= maximum_gap for item in gap_metrics
        )
        section_score = sum(section_scores) / len(section_scores) if section_scores else 0.0
        gap_score = sum(gap_scores) / len(gap_scores) if gap_scores else 100.0
        score = round(section_score * 0.8 + gap_score * 0.2, 2)
        analysis = {
            "schema_version": 1,
            "planning_target": planning_target,
            "ideal_band": [minimum, maximum],
            "body_line_height_inches": round(body_line_height, 4),
            "preferred_gap_inches": round(preferred_gap, 4),
            "maximum_gap_inches": round(maximum_gap, 4),
            "region_kind": group_kind,
            "sections": section_metrics,
            "gaps": gap_metrics,
            "region_utilization": region_utilization,
            "empty_regions": empty_regions,
            "all_sections_ideal": all_ideal,
            "gaps_acceptable": gaps_acceptable,
        }
        if is_zoned:
            analysis["composition_whitespace"] = measure_composition_whitespace(
                layout_spec, layout,
                poster_width=width,
                poster_height=height,
                poster_margin=margin,
                title_height_fraction=float(
                    poster_config.get("layout", {}).get("title_height_fraction", 0.18)
                ),
            )
        state["section_fit_analysis"] = analysis
        positives = []
        if all_ideal and gaps_acceptable:
            positives.append({
                "scope": "layout",
                "observation": "All content modules use 95%-100% of their independent height budgets with controlled gaps",
            })
        return _result(
            context,
            self.name,
            passed=not critical_failure,
            scores={"layout_integrity": score, "visual_balance": score},
            issues=issues,
            metadata={"section_fit": analysis},
            positives=positives,
        )


class ContentAdequacyEvaluator:
    """Explain whether underfilled sections have grounded content to add."""

    name = "content_adequacy"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        state = context.state
        claim_index = all_publishable_claims(state)
        sections = _board_sections(state)
        fit = state.get("section_fit_analysis") or {}
        narrative = {
            str(section.get("section_id")): section
            for section in (state.get("narrative_plan") or {}).get("sections", [])
            if isinstance(section, dict) and section.get("section_id")
        }
        issues: List[Dict[str, Any]] = []
        duplicate_count = 0
        underfilled_count = 0
        coverage_values: List[float] = []
        supplemental_available = bool(state.get("section_chunks"))

        for section_id, section in sections.items():
            claim_ids = [str(item) for item in section.get("claim_ids", [])]
            texts = [
                re.sub(r"\s+", " ", str(claim_index.get(item, {}).get("text", ""))).strip().casefold()
                for item in claim_ids
                if item in claim_index
            ]
            duplicate_count += max(0, len(texts) - len(set(texts)))
            used_evidence = {
                str(evidence_id)
                for claim_id in claim_ids
                for evidence_id in claim_index.get(claim_id, {}).get("evidence_ids", [])
            }
            assigned = [
                str(item)
                for item in narrative.get(section_id, {}).get("evidence_ids", [])
            ]
            if assigned:
                coverage_values.append(len(used_evidence.intersection(assigned)) / len(assigned))
            unused = [item for item in assigned if item not in used_evidence]
            metric = (fit.get("sections") or {}).get(section_id, {})
            utilization = float(metric.get("utilization", 1.0))
            minimum = float((fit.get("ideal_band") or [0.95, 1.0])[0])
            if utilization < minimum:
                underfilled_count += 1
                allowed = ["move_section_to_zone", "adjust_zone_budget"]
                if unused or supplemental_available:
                    allowed = ["add_existing_claim", "add_claim_from_evidence", *allowed]
                issues.append(issue(
                    f"CONTENT-UNDERFILLED-{_safe_id(section_id)}",
                    severity="major" if utilization < 0.90 else "warning",
                    scope="content_quality",
                    location={
                        "section_id": section_id,
                        ("zone_id" if metric.get("region_kind") == "zone" else "column"): metric.get("layout_region"),
                    },
                    observation=(
                        f"Section {section_id} has grounded unused evidence available"
                        if unused
                        else f"Section {section_id} has no unused assigned evidence; exact source-chunk search is {'available' if supplemental_available else 'unavailable'}"
                    ),
                    evidence={
                        "utilization": round(utilization, 4),
                        "candidate_evidence_ids": unused[:8],
                        "grounded_addition_available": bool(unused),
                        "supplemental_search_available": supplemental_available,
                    },
                    required_outcome=(
                        "Add at most one non-redundant verified claim, then remeasure"
                        if unused
                        else "Try one exact source-chunk extraction when available; otherwise shrink or reallocate without filler"
                    ),
                    allowed_operations=allowed,
                    forbidden_operations=["invent_claim", "add_filler_text"],
                ))

        average_coverage = (
            sum(coverage_values) / len(coverage_values)
            if coverage_values else 1.0
        )
        score = max(
            0.0,
            100.0
            - duplicate_count * 25.0
            - underfilled_count * 6.0
            - max(0.0, 0.5 - average_coverage) * 30.0,
        )
        positives = []
        if duplicate_count == 0:
            positives.append({
                "scope": "content_quality",
                "observation": "Published section claims are non-duplicative",
            })
        return _result(
            context,
            self.name,
            passed=True,
            scores={"content_quality": round(score, 2)},
            issues=issues,
            metadata={
                "average_assigned_evidence_coverage": round(average_coverage, 4),
                "underfilled_section_count": underfilled_count,
                "duplicate_claim_count": duplicate_count,
            },
            positives=positives,
        )
