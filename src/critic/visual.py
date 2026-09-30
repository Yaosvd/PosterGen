"""Multimodal outcome evaluator for the final rendered poster."""

import base64
import json
from pathlib import Path
from typing import Any, Dict, List

from src.critic.base import CriticContext, EvaluationResult, issue
from utils.agent_policy import apply_agent_policy
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt


class VisualCriticEvaluator:
    name = "visual"
    _DIMENSIONS = (
        "readability",
        "visual_hierarchy",
        "visual_balance",
        "aesthetics",
    )
    _SUBMETRICS = (
        "layout_structure",
        "whitespace_quality",
        "primary_anchor",
        "compositional_balance",
        "color_palette",
        "color_hierarchy",
        "color_contrast",
        "color_source",
        "font_hierarchy",
        "font_emphasis",
        "font_legibility",
        "element_alignment",
        "layout_robustness",
        "visual_relevance",
    )

    def __init__(self) -> None:
        self.prompt = load_prompt("config/prompts/critic_visual.txt")

    @staticmethod
    def _score(value: Any) -> float:
        try:
            return round(max(0.0, min(100.0, float(value))), 2)
        except (TypeError, ValueError):
            return 0.0


    @staticmethod
    def _validated_location(
        raw_location: Any,
        state: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Keep only artifact-backed section and zone identifiers."""

        raw = dict(raw_location) if isinstance(raw_location, dict) else {}
        spec = state.get("layout_spec") or {}
        board = (
            state.get("optimized_story_board")
            or state.get("story_board")
            or {}
        )
        sections = {
            str(item.get("section_id")): item
            for item in board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(item, dict) and item.get("section_id")
        }
        section_to_zone = {
            str(section_id): str(zone.get("zone_id"))
            for zone in spec.get("zones", [])
            if isinstance(zone, dict) and zone.get("zone_id")
            for section_id in zone.get("section_ids", [])
        }
        valid_zones = set(section_to_zone.values())
        valid_elements = {
            str(item.get("id"))
            for item in (
                state.get("styled_layout")
                or state.get("design_layout")
                or []
            )
            if isinstance(item, dict) and item.get("id")
        }
        location: Dict[str, Any] = {}
        zone_id = str(raw.get("zone_id") or "")
        section_id = str(raw.get("section_id") or "")
        element_id = str(raw.get("element_id") or "")
        if zone_id in valid_zones:
            location["zone_id"] = zone_id
        if section_id in sections:
            expected_zone = section_to_zone.get(section_id)
            if not zone_id or not expected_zone or zone_id == expected_zone:
                location["section_id"] = section_id
        if element_id in valid_elements:
            location["element_id"] = element_id
        evidence = {"source": "vision_model"}
        if location != {
            key: raw[key]
            for key in ("zone_id", "section_id", "element_id")
            if key in raw
        }:
            evidence["location_validation"] = "invalid identifiers removed"
            evidence["raw_location"] = raw
        return location, evidence

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = context.config["evaluators"].get(self.name, {})
        required = bool(settings.get("required_for_archive", True))
        candidate = context.state.get("current_candidate") or {}
        png_path = Path(candidate.get("png_path", ""))
        version = str(settings.get("version", "1.0.0"))

        if not png_path.is_file():
            missing_issue = issue(
                "VISUAL-PREVIEW-MISSING",
                severity="critical" if required else "warning",
                scope="renderer",
                observation="Visual Critic cannot access the poster PNG",
                required_outcome="Provide a rendered PNG for visual evaluation",
                allowed_operations=["rerender_candidate"],
            )
            return EvaluationResult(
                evaluator=self.name,
                version=version,
                hard_gate=bool(settings.get("hard_gate", required)),
                passed=not required,
                scores={dimension: 0.0 for dimension in self._DIMENSIONS},
                issues=[missing_issue],
            )

        try:
            image_data = base64.b64encode(png_path.read_bytes()).decode("ascii")
            model_config = apply_agent_policy(
                context.state["vision_model"],
                "critic_visual",
            )
            agent = LangGraphAgent(
                "You are a rigorous, layout-style-neutral academic poster critic.",
                model_config,
                context.state,
                "critic_visual",
            )
            iteration_context = context.state.get("iteration_context") or {}
            layout_spec = context.state.get("layout_spec") or {}
            section_zone = {
                str(section_id): str(zone.get("zone_id"))
                for zone in layout_spec.get("zones", [])
                if isinstance(zone, dict)
                for section_id in zone.get("section_ids", [])
            }
            visible_board = (
                context.state.get("optimized_story_board")
                or context.state.get("story_board")
                or {}
            )
            evaluation_context = {
                "poster_size_inches": [
                    context.state.get("poster_width"),
                    context.state.get("poster_height"),
                ],
                "generation_strategy": iteration_context.get("strategy", "single_pass"),
                "rubric_version": context.config.get("rubric_version"),
                "layout_family": layout_spec.get("family_id"),
                "primary_anchor_zone": layout_spec.get("primary_anchor_zone"),
                "reading_order": layout_spec.get("reading_order", []),
                "zones": [
                    {
                        "zone_id": zone.get("zone_id"),
                        "role": zone.get("role"),
                        "section_ids": zone.get("section_ids", []),
                    }
                    for zone in layout_spec.get("zones", [])
                    if isinstance(zone, dict)
                ],
                "sections": [
                    {
                        "section_id": item.get("section_id"),
                        "section_title": item.get("section_title"),
                        "zone_id": section_zone.get(str(item.get("section_id"))),
                    }
                    for item in visible_board.get(
                        "spatial_content_plan", {}
                    ).get("sections", [])
                    if isinstance(item, dict) and item.get("section_id")
                ],
                "do_not_prefer_any_layout_family": True,
            }
            messages = [
                {
                    "type": "text",
                    "text": self.prompt + "\nEvaluation context:\n" + json.dumps(
                        evaluation_context,
                        ensure_ascii=False,
                        indent=2,
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
            response = agent.step(json.dumps(messages))
            context.state["tokens"].add_vision(
                int(response.input_tokens),
                int(response.output_tokens),
            )
            payload = extract_json(response.content)
            scores = {
                dimension: self._score((payload.get("scores") or {}).get(dimension))
                for dimension in self._DIMENSIONS
            }
            raw_submetrics = payload.get("submetrics") or {}
            submetrics = {
                name: self._score(raw_submetrics.get(name))
                for name in self._SUBMETRICS
                if name in raw_submetrics
            }
            issues: List[Dict[str, Any]] = []
            for index, raw_issue in enumerate(payload.get("issues") or []):
                if not isinstance(raw_issue, dict):
                    continue
                validated_location, location_evidence = (
                    self._validated_location(
                        raw_issue.get("location"), context.state
                    )
                )
                issues.append(issue(
                    f"VISUAL-{index + 1:03d}",
                    severity=str(raw_issue.get("severity", "major")).lower(),
                    scope=str(raw_issue.get("scope", "visual_hierarchy")),
                    location=validated_location,
                    observation=str(raw_issue.get("observation", "Visual quality issue")),
                    evidence=location_evidence,
                    required_outcome=str(raw_issue.get("required_outcome", "Improve the visible outcome")),
                    allowed_operations=[str(item) for item in raw_issue.get("allowed_operations", [])],
                    forbidden_operations=[str(item) for item in raw_issue.get("forbidden_operations", [])],
                ))
            positive_patterns = [
                {
                    "scope": str(item.get("scope", "visual")),
                    "observation": str(item.get("observation", "")),
                }
                for item in (payload.get("positive_patterns") or [])
                if isinstance(item, dict) and item.get("observation")
            ]
            return EvaluationResult(
                evaluator=self.name,
                version=version,
                hard_gate=bool(settings.get("hard_gate", required)),
                passed=not any(item.get("severity") == "critical" for item in issues),
                scores=scores,
                issues=issues,
                positive_patterns=positive_patterns,
                metadata={
                    "model_evaluation_completed": True,
                    "submetrics": submetrics,
                    "evaluation_context": evaluation_context,
                },
            )
        except Exception as exc:
            failure_issue = issue(
                "VISUAL-EVALUATION-FAILED",
                severity="critical" if required else "warning",
                scope="critic",
                observation=f"Visual Critic failed: {exc}",
                required_outcome="Retry visual evaluation with an available vision model",
                allowed_operations=["retry_critic"],
            )
            return EvaluationResult(
                evaluator=self.name,
                version=version,
                hard_gate=bool(settings.get("hard_gate", required)),
                passed=not required,
                scores={dimension: 0.0 for dimension in self._DIMENSIONS},
                issues=[failure_issue],
                metadata={"model_evaluation_completed": False},
            )
