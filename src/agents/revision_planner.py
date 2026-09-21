"""Grounding-safe repair planner for Critic-directed poster iterations."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jinja2 import Template

from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.grounded_content import all_publishable_claims, claim_root_id
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from utils.src.logging_utils import log_agent_info, log_agent_success, log_agent_warning


class RevisionPlanner:
    """Translate Critic findings into validated story-board operations."""

    _COLUMNS = {"left", "middle", "right"}
    _PRIORITIES = {"top", "middle", "bottom"}
    _OPERATIONS = {
        "move_section",
        "swap_sections",
        "reorder_sections",
        "set_vertical_priority",
        "remove_claim",
        "remove_visual",
        "move_visual",
        "replace_visual",
        "restore_visual_aspect_ratio",
        "set_section_importance",
        "set_section_gap",
    }
    _CONTENT_OPERATIONS = {
        "use_claim_variant",
        "create_compact_variant",
        "add_existing_claim",
        "add_claim_from_evidence",
    }
    _LAYOUT_OPERATIONS = {
        "move_section_to_zone",
        "set_reading_order",
        "set_primary_anchor",
    }
    _STYLE_OPERATIONS = {
        "repair_text_contrast": ("contrast_mode", "wcag_aa"),
        "reduce_accent_density": ("accent_density", "reduced"),
        "use_accessible_palette_variant": ("palette_variant", "accessible"),
        "normalize_semantic_colors": ("semantic_colors", "normalized"),
        "normalize_typography_hierarchy": ("typography_hierarchy", "normalized"),
        "increase_title_separation": ("typography_hierarchy", "strong"),
        "normalize_font_family": ("font_family", "normalized"),
    }
    _FORBIDDEN_STYLE_KEYS = {
        "x", "y", "width", "height", "font_size", "font_family",
        "hex", "color", "theme_color", "replacement_text",
    }

    def __init__(self) -> None:
        self.name = "revision_planner"
        self.prompt = load_prompt("config/prompts/revision_planner.txt")

    def __call__(self, state: PosterState) -> PosterState:
        log_agent_info(self.name, "planning a grounded Critic-directed revision")
        source_board = deepcopy(
            state.get("optimized_story_board")
            or state.get("story_board")
            or {}
        )
        report = state.get("critic_report") or {}
        claim_index = all_publishable_claims(state)
        if not source_board or not claim_index:
            state["errors"].append(
                f"{self.name}: missing story board or verified claims"
            )
            return state

        raw_plan: Dict[str, Any] = {}
        try:
            config = apply_agent_policy(state["text_model"], self.name)
            agent = LangGraphAgent(
                "You repair poster plans while preserving immutable verified claims.",
                config,
                state,
                self.name,
            )
            rendered_prompt = Template(self.prompt).render()
            payload = {
                "critic_report": report,
                "story_board": source_board,
                "verified_claim_ids": sorted(claim_index),
                "publishable_claims": [
                    {
                        "claim_id": claim_id,
                        "text": claim.get("text", ""),
                        "evidence_ids": claim.get("evidence_ids", []),
                        "variant_kind": claim.get("variant_kind", "original"),
                    }
                    for claim_id, claim in claim_index.items()
                ],
                "template_context": state.get("template_context") or [],
                "iteration_context": state.get("iteration_context") or {},
                "layout_spec": state.get("layout_spec") or {},
                "approved_visual_ids": sorted(self._approved_visual_ids(state)),
                "current_style_overrides": state.get("style_overrides") or {},
            }
            response = agent.step(
                rendered_prompt
                + "\n\nINPUT DATA:\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            )
            state["tokens"].add_text(
                int(response.input_tokens),
                int(response.output_tokens),
            )
            raw_plan = extract_json(response.content)
        except Exception as exc:
            log_agent_warning(
                self.name,
                f"model revision failed; using deterministic repair: {exc}",
            )

        operations = raw_plan.get("operations") if isinstance(raw_plan, dict) else []
        revised_spec, accepted_layout_operations = (
            self.apply_layout_operations(
                state.get("layout_spec") or {},
                source_board,
                operations if isinstance(operations, list) else [],
            )
        )
        revised_board, accepted_operations = self.apply_operations(
            source_board,
            operations if isinstance(operations, list) else [],
            claim_index,
            approved_visual_ids=self._approved_visual_ids(state),
        )
        style_overrides, accepted_style_operations = self.apply_style_operations(
            state.get("style_overrides") or {},
            operations if isinstance(operations, list) else [],
        )
        accepted_operations.extend(accepted_layout_operations)
        accepted_operations.extend(accepted_style_operations)
        raw_content_actions = (
            raw_plan.get("content_actions", [])
            if isinstance(raw_plan, dict)
            else []
        )
        content_actions = self._sanitize_content_actions(
            raw_content_actions if isinstance(raw_content_actions, list) else [],
            revised_board,
            claim_index,
        )
        fallback_used = False
        if not accepted_operations and not content_actions:
            fallback_operations = self._deterministic_style_operations(report)
            style_overrides, accepted_style_operations = self.apply_style_operations(
                style_overrides, fallback_operations
            )
            accepted_operations.extend(accepted_style_operations)
            fallback_used = bool(accepted_style_operations)
        if not accepted_operations and not content_actions:
            fallback_operations = self._deterministic_operations(
                revised_board,
                report,
                state.get("final_column_analysis") or {},
            )
            revised_board, accepted_operations = self.apply_operations(
                revised_board,
                fallback_operations,
                claim_index,
            )
            fallback_used = True
        if not content_actions:
            content_actions = self._deterministic_content_actions(
                revised_board, report, claim_index
            )
            fallback_used = fallback_used or bool(content_actions)

        revision_plan = {
            "schema_version": 3,
            "parent_candidate_id": (state.get("iteration_context") or {}).get("parent_candidate_id"),
            "analysis_summary": str(
                raw_plan.get("analysis_summary", "Deterministic Critic repair")
                if isinstance(raw_plan, dict)
                else "Deterministic Critic repair"
            ),
            "critic_issues_addressed": [
                str(item)
                for item in (
                    raw_plan.get("critic_issues_addressed", [])
                    if isinstance(raw_plan, dict)
                    else []
                )
            ],
            "preserve": [
                str(item)
                for item in (
                    raw_plan.get("preserve", [])
                    if isinstance(raw_plan, dict)
                    else []
                )
            ],
            "operations": accepted_operations,
            "content_actions": content_actions,
            "design_directives": [
                str(item)
                for item in (
                    raw_plan.get("design_directives", [])
                    if isinstance(raw_plan, dict)
                    else []
                )
            ],
            "fallback_used": fallback_used,
        }
        state["style_overrides"] = style_overrides
        state["layout_overrides"] = {
            "section_gap_inches": revised_board.get("layout_preferences", {}).get("section_gap_inches")
        }
        state["story_board"] = revised_board
        if revised_spec:
            state["layout_spec"] = revised_spec
        state["revision_plan"] = revision_plan
        state["current_agent"] = self.name
        self._save(state, revised_board, revision_plan)
        log_agent_success(
            self.name,
            f"accepted {len(accepted_operations)} grounded revision operations",
        )
        return state

    @classmethod
    def apply_layout_operations(
        cls,
        layout_spec: Dict[str, Any],
        board: Dict[str, Any],
        operations: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Apply relational family operations; raw coordinates are never legal."""

        if not isinstance(layout_spec, dict) or not layout_spec.get("zones"):
            return layout_spec, []
        revised = deepcopy(layout_spec)
        zones = {
            str(zone.get("zone_id")): zone
            for zone in revised.get("zones", [])
            if isinstance(zone, dict) and zone.get("zone_id")
        }
        section_ids = {
            str(section.get("section_id"))
            for section in board.get(
                "spatial_content_plan", {}
            ).get("sections", [])
            if isinstance(section, dict) and section.get("section_id")
        }
        accepted: List[Dict[str, Any]] = []
        for raw in operations:
            if (
                not isinstance(raw, dict)
                or raw.get("operation") not in cls._LAYOUT_OPERATIONS
                or any(key in raw for key in ("x", "y", "width", "height"))
            ):
                continue
            operation = str(raw["operation"])
            changed = False
            if operation == "move_section_to_zone":
                section_id = str(raw.get("section_id") or "")
                zone_id = str(raw.get("zone_id") or "")
                if section_id in section_ids and zone_id in zones:
                    for zone in zones.values():
                        zone["section_ids"] = [
                            item
                            for item in zone.get("section_ids", [])
                            if str(item) != section_id
                        ]
                    zones[zone_id].setdefault("section_ids", []).append(
                        section_id
                    )
                    changed = True
            elif operation == "set_reading_order":
                order = [str(item) for item in raw.get("section_order", [])]
                assigned = {
                    str(item)
                    for zone in zones.values()
                    for item in zone.get("section_ids", [])
                }
                if len(order) == len(set(order)) and set(order) == assigned:
                    revised["reading_order"] = order
                    changed = True
            elif operation == "set_primary_anchor":
                zone_id = str(raw.get("zone_id") or "")
                if zone_id in zones:
                    revised["primary_anchor_zone"] = zone_id
                    changed = True
            if changed:
                accepted.append({
                    key: value
                    for key, value in raw.items()
                    if key not in {"x", "y", "width", "height", "replacement_text"}
                })
        return revised, accepted

    def apply_operations(
        self,
        board: Dict[str, Any],
        operations: List[Dict[str, Any]],
        claim_index: Dict[str, Dict[str, Any]],
        approved_visual_ids: set[str] | None = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Apply only allow-listed operations, then rematerialize claim text."""

        revised = deepcopy(board)
        sections = revised.get("spatial_content_plan", {}).get("sections", [])
        if not isinstance(sections, list):
            return board, []
        accepted: List[Dict[str, Any]] = []

        def section_map() -> Dict[str, Dict[str, Any]]:
            return {
                str(section.get("section_id")): section
                for section in sections
                if isinstance(section, dict) and section.get("section_id")
            }

        for raw_operation in operations:
            if not isinstance(raw_operation, dict):
                continue
            operation = str(raw_operation.get("operation", ""))
            if operation not in self._OPERATIONS:
                continue
            by_id = section_map()
            changed = False

            if operation == "move_section":
                section = by_id.get(str(raw_operation.get("section_id")))
                column = raw_operation.get("column")
                if section is not None and column in self._COLUMNS:
                    section["column_assignment"] = column
                    changed = True

            elif operation == "swap_sections":
                first = by_id.get(str(raw_operation.get("first_section_id")))
                second = by_id.get(str(raw_operation.get("second_section_id")))
                if first is not None and second is not None and first is not second:
                    first["column_assignment"], second["column_assignment"] = (
                        second.get("column_assignment", "left"),
                        first.get("column_assignment", "left"),
                    )
                    first["vertical_priority"], second["vertical_priority"] = (
                        second.get("vertical_priority", "middle"),
                        first.get("vertical_priority", "middle"),
                    )
                    changed = True

            elif operation == "reorder_sections":
                order = [str(item) for item in raw_operation.get("section_order", [])]
                requested = [by_id[item] for item in order if item in by_id]
                if requested:
                    requested_ids = {id(section) for section in requested}
                    sections[:] = requested + [
                        section for section in sections if id(section) not in requested_ids
                    ]
                    changed = True

            elif operation == "set_vertical_priority":
                section = by_id.get(str(raw_operation.get("section_id")))
                priority = raw_operation.get("priority")
                if section is not None and priority in self._PRIORITIES:
                    section["vertical_priority"] = priority
                    changed = True

            elif operation == "remove_claim":
                section = by_id.get(str(raw_operation.get("section_id")))
                claim_id = raw_operation.get("claim_id")
                if (
                    section is not None
                    and claim_id in section.get("claim_ids", [])
                    and len(section.get("claim_ids", [])) > 1
                ):
                    section["claim_ids"] = [
                        item for item in section["claim_ids"] if item != claim_id
                    ]
                    changed = True

            elif operation == "remove_visual":
                section = by_id.get(str(raw_operation.get("section_id")))
                visual_id = raw_operation.get("visual_id")
                if section is not None:
                    before = list(section.get("visual_assets", []))
                    section["visual_assets"] = [
                        item
                        for item in before
                        if item.get("visual_id") != visual_id
                    ]
                    changed = len(before) != len(section["visual_assets"])

            elif operation == "move_visual":
                visual_id = raw_operation.get("visual_id")
                target = by_id.get(str(raw_operation.get("target_section_id")))
                source = None
                visual = None
                for section in sections:
                    for item in section.get("visual_assets", []):
                        if item.get("visual_id") == visual_id:
                            source = section
                            visual = item
                            break
                    if visual is not None:
                        break
                if target is not None and source is not None and source is not target:
                    source["visual_assets"] = [
                        item
                        for item in source.get("visual_assets", [])
                        if item.get("visual_id") != visual_id
                    ]
                    if not any(
                        item.get("visual_id") == visual_id
                        for item in target.get("visual_assets", [])
                    ):
                        target.setdefault("visual_assets", []).append(visual)
                    changed = True

            elif operation == "replace_visual":
                visual_id = str(raw_operation.get("visual_id") or "")
                replacement_id = str(raw_operation.get("replacement_visual_id") or "")
                approved = approved_visual_ids or set()
                visible_ids = {
                    str(item.get("visual_id"))
                    for section in sections
                    for item in section.get("visual_assets", [])
                    if isinstance(item, dict)
                }
                if replacement_id in approved and replacement_id not in visible_ids:
                    for section in sections:
                        for item in section.get("visual_assets", []):
                            if str(item.get("visual_id")) == visual_id:
                                item["visual_id"] = replacement_id
                                changed = True
                                break
                        if changed:
                            break

            elif operation == "restore_visual_aspect_ratio":
                visual_id = str(raw_operation.get("visual_id") or "")
                if any(
                    str(item.get("visual_id")) == visual_id
                    for section in sections
                    for item in section.get("visual_assets", [])
                    if isinstance(item, dict)
                ):
                    revised.setdefault("layout_preferences", {}).setdefault(
                        "preserve_visual_aspect_ids", []
                    )
                    preserved = revised["layout_preferences"]["preserve_visual_aspect_ids"]
                    if visual_id not in preserved:
                        preserved.append(visual_id)
                    changed = True

            elif operation == "set_section_importance":
                section = by_id.get(str(raw_operation.get("section_id")))
                try:
                    importance = int(raw_operation.get("importance_level"))
                except (TypeError, ValueError):
                    importance = 0
                if section is not None and importance in {1, 2, 3}:
                    section["importance_level"] = importance
                    changed = True

            elif operation == "set_section_gap":
                try:
                    gap_inches = float(raw_operation.get("gap_inches"))
                except (TypeError, ValueError):
                    gap_inches = 0.0
                if 0.2 <= gap_inches <= 2.0:
                    revised.setdefault("layout_preferences", {})[
                        "section_gap_inches"
                    ] = round(gap_inches, 3)
                    changed = True

            if changed:
                accepted.append({
                    key: value
                    for key, value in raw_operation.items()
                    if key != "replacement_text"
                })

        # Fail closed: unknown and duplicated IDs are removed and every visible
        # string is rebuilt from the immutable verified-claim bank.
        seen_claims = set()
        sanitized_sections = []
        for section in sections:
            claim_ids = []
            for claim_id in section.get("claim_ids", []):
                if claim_id not in claim_index or claim_id in seen_claims:
                    continue
                seen_claims.add(claim_id)
                claim_ids.append(claim_id)
            if not claim_ids:
                continue
            section["claim_ids"] = claim_ids
            section["text_content"] = [
                claim_index[claim_id]["text"] for claim_id in claim_ids
            ]
            if section.get("column_assignment") not in self._COLUMNS:
                section["column_assignment"] = "left"
            if section.get("vertical_priority") not in self._PRIORITIES:
                section["vertical_priority"] = "middle"
            sanitized_sections.append(section)
        revised.setdefault("spatial_content_plan", {})["sections"] = sanitized_sections
        return revised, accepted
    @staticmethod
    def _approved_visual_ids(state: PosterState) -> set[str]:
        approved: set[str] = set()
        for prefix, collection_name in (("figure_", "images"), ("table_", "tables")):
            for key, record in (state.get(collection_name) or {}).items():
                approved.add(prefix + str(key))
                record_id = str(record.get("visual_id") or "") if isinstance(record, dict) else ""
                if record_id.startswith(prefix):
                    approved.add(record_id)
        return approved

    @classmethod
    def apply_style_operations(
        cls,
        current: Dict[str, Any],
        operations: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Resolve style repairs to named deterministic presets only."""

        overrides = deepcopy(current) if isinstance(current, dict) else {}
        accepted: List[Dict[str, Any]] = []
        for raw in operations:
            if not isinstance(raw, dict):
                continue
            operation = str(raw.get("operation") or "")
            if operation not in cls._STYLE_OPERATIONS:
                continue
            if cls._FORBIDDEN_STYLE_KEYS.intersection(raw):
                continue
            key, value = cls._STYLE_OPERATIONS[operation]
            overrides[key] = value
            accepted.append({
                "operation": operation,
                "preset": value,
                "reason": str(raw.get("reason") or "Critic-directed safe style repair"),
            })
        return overrides, accepted

    @classmethod
    def _deterministic_style_operations(cls, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        operations: List[Dict[str, Any]] = []
        seen = set()
        for finding in report.get("issues", []):
            for operation in finding.get("allowed_operations", []):
                operation = str(operation)
                if operation in cls._STYLE_OPERATIONS and operation not in seen:
                    operations.append({
                        "operation": operation,
                        "reason": f"deterministic repair for {finding.get('issue_id', 'Critic issue')}",
                    })
                    seen.add(operation)
                    break
            if len(operations) >= 2:
                break
        return operations

    @classmethod
    def _sanitize_content_actions(
        cls,
        actions: List[Dict[str, Any]],
        board: Dict[str, Any],
        claim_index: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        sections = {
            str(section.get("section_id")): section
            for section in board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(section, dict) and section.get("section_id")
        }
        visible = {
            str(claim_id)
            for section in sections.values()
            for claim_id in section.get("claim_ids", [])
        }
        accepted: List[Dict[str, Any]] = []
        touched_sections = set()
        for raw in actions:
            if not isinstance(raw, dict):
                continue
            operation = str(raw.get("operation") or "")
            section_id = str(raw.get("section_id") or "")
            if (
                operation not in cls._CONTENT_OPERATIONS
                or section_id not in sections
                or section_id in touched_sections
            ):
                continue
            claim_id = str(raw.get("claim_id") or "")
            variant_id = str(raw.get("variant_id") or "")
            if operation == "create_compact_variant" and (
                claim_id not in sections[section_id].get("claim_ids", [])
                or claim_id not in claim_index
            ):
                continue
            if operation == "use_claim_variant" and (
                claim_id not in visible
                or claim_id not in claim_index
                or variant_id not in claim_index
                or claim_index[variant_id].get("verified") is not True
                or claim_root_id(claim_index[variant_id]) != claim_root_id(claim_index[claim_id])
            ):
                continue
            if operation == "add_existing_claim" and claim_id and (
                claim_id not in claim_index or claim_id in visible
            ):
                continue
            clean = {
                key: value
                for key, value in raw.items()
                if key != "replacement_text"
            }
            clean["operation"] = operation
            clean["section_id"] = section_id
            if isinstance(clean.get("evidence_ids"), list):
                clean["evidence_ids"] = [
                    str(item) for item in clean["evidence_ids"]
                ][:8]
            accepted.append(clean)
            touched_sections.add(section_id)
        return accepted

    @staticmethod
    def _deterministic_content_actions(
        board: Dict[str, Any],
        report: Dict[str, Any],
        claim_index: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        sections = {
            str(section.get("section_id")): section
            for section in board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(section, dict) and section.get("section_id")
        }
        visible = {
            str(claim_id)
            for section in sections.values()
            for claim_id in section.get("claim_ids", [])
        }
        actions: List[Dict[str, Any]] = []
        touched = set()
        for issue in report.get("issues", []):
            issue_id = str(issue.get("issue_id") or "")
            section_id = str((issue.get("location") or {}).get("section_id") or "")
            section = sections.get(section_id)
            if section is None or section_id in touched:
                continue
            evidence = issue.get("evidence") or {}
            if issue_id.startswith(("SECTION-OVERFLOW", "CONTENT-OVERFULL")):
                candidates = [
                    claim_index[claim_id]
                    for claim_id in section.get("claim_ids", [])
                    if claim_id in claim_index
                ]
                if not candidates:
                    continue
                longest = max(
                    candidates,
                    key=lambda claim: len(str(claim.get("text", ""))),
                )
                actions.append({
                    "operation": "create_compact_variant",
                    "section_id": section_id,
                    "claim_id": longest["claim_id"],
                    "target_height_reduction_inches": evidence.get(
                        "required_reduction_inches", 0.5
                    ),
                    "reason": "reduce measured module overflow with a verified compact wording",
                })
                touched.add(section_id)
            elif issue_id.startswith(("SECTION-UNDERFILLED", "CONTENT-UNDERFILLED")):
                candidate_evidence = [
                    str(item)
                    for item in evidence.get("candidate_evidence_ids", [])
                ]
                omitted = next(
                    (
                        claim
                        for claim in claim_index.values()
                        if claim.get("claim_id") not in visible
                        and (
                            claim.get("section_id") == section_id
                            or set(candidate_evidence).intersection(
                                str(item) for item in claim.get("evidence_ids", [])
                            )
                        )
                    ),
                    None,
                )
                if omitted is not None:
                    actions.append({
                        "operation": "add_existing_claim",
                        "section_id": section_id,
                        "claim_id": omitted["claim_id"],
                        "evidence_ids": candidate_evidence,
                        "reason": "restore useful verified detail into an underfilled module",
                    })
                elif candidate_evidence:
                    actions.append({
                        "operation": "add_claim_from_evidence",
                        "section_id": section_id,
                        "evidence_ids": candidate_evidence,
                        "reason": "add one non-redundant claim from assigned paper evidence",
                    })
                elif evidence.get("supplemental_search_available"):
                    actions.append({
                        "operation": "add_claim_from_evidence",
                        "section_id": section_id,
                        "evidence_ids": [],
                        "reason": "extract one new exact source-grounded detail for an underfilled module",
                    })
                if actions:
                    touched.add(section_id)
            if len(actions) >= 2:
                break
        return actions


    @staticmethod
    def _deterministic_operations(
        board: Dict[str, Any],
        report: Dict[str, Any],
        column_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        sections = board.get("spatial_content_plan", {}).get("sections", [])
        columns = column_analysis.get("columns", {})
        overflow_columns = [
            item.get("location", {}).get("column")
            for item in report.get("issues", [])
            if item.get("issue_id", "").startswith("COLUMN-OVERFLOW")
        ]
        overflow_columns = [column for column in overflow_columns if column]
        if not overflow_columns:
            overflow_columns = [
                column
                for column, data in columns.items()
                if float(data.get("utilization_rate", 0)) > 1.0
            ]
        utilization = {
            column: float(data.get("utilization_rate", 0.0))
            for column, data in columns.items()
        }
        if overflow_columns and utilization:
            source_column = overflow_columns[0]
            target_column = min(utilization, key=utilization.get)
            candidates = [
                section
                for section in sections
                if section.get("column_assignment") == source_column
            ]
            if candidates and target_column != source_column:
                target = sorted(
                    candidates,
                    key=lambda section: (
                        {"bottom": 0, "middle": 1, "top": 2}.get(
                            section.get("vertical_priority"), 1
                        ),
                        -len(section.get("claim_ids", [])),
                    ),
                )[0]
                return [{
                    "operation": "move_section",
                    "section_id": target.get("section_id"),
                    "column": target_column,
                    "reason": "deterministic repair of the most overloaded column",
                }]

        largest = max(
            sections,
            key=lambda section: len(section.get("claim_ids", [])),
            default=None,
        )
        if largest and len(largest.get("claim_ids", [])) > 1:
            return [{
                "operation": "remove_claim",
                "section_id": largest.get("section_id"),
                "claim_id": largest["claim_ids"][-1],
                "reason": "deterministic density reduction after Critic rejection",
            }]
        if len(sections) > 1:
            return [{
                "operation": "swap_sections",
                "first_section_id": sections[0].get("section_id"),
                "second_section_id": sections[-1].get("section_id"),
                "reason": "deterministic layout mutation",
            }]
        return []

    @staticmethod
    def _save(
        state: PosterState,
        board: Dict[str, Any],
        plan: Dict[str, Any],
    ) -> None:
        output = Path(state["output_dir"]) / "content"
        output.mkdir(parents=True, exist_ok=True)
        (output / "revision_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (output / "story_board.json").write_text(
            json.dumps(board, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


revision_planner = RevisionPlanner()


def revision_planner_node(state: PosterState) -> PosterState:
    return revision_planner(state)
