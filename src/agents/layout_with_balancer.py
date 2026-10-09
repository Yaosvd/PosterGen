"""
3-phase layout optimization orchestrator
"""

import json
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.state.poster_state import PosterState
from src.agents.layout_agent import LayoutAgent
from src.agents.balancer_agent import BalancerAgent
from src.layout.feasibility import (
    LayoutFeasibilityError,
    fit_family_layout,
    validate_compiled_layout,
)
from utils.src.logging_utils import log_agent_info, log_agent_success, log_agent_error

class LayoutWithBalancerAgent:
    def __init__(self):
        self.name = "layout_with_balancer"
        self.layout_agent = LayoutAgent()
        self.balancer_agent = BalancerAgent()

    def __call__(self, state: PosterState) -> PosterState:
        """execute 3-phase layout optimization"""
        log_agent_info(self.name, "starting 3-phase layout optimization")
        
        try:
            context = state.get("iteration_context") or {}
            current_spec = state.get("layout_spec") or {}
            requested_family = str(
                context.get("layout_family")
                or current_spec.get("family_id")
                or "classic_three_column"
            )
            route = state.get("generation_route")
            if route == "standalone_classic":
                requested_family = "classic_three_column"
            if route == "optimization_family" or (
                route is None and requested_family != "classic_three_column"
            ):
                return self._run_family_constraint_engine(
                    state, requested_family
                )

            # phase 1: initial layout generation
            log_agent_info(self.name, "phase 1: generating initial layout")
            initial_state = self.layout_agent(state, mode="initial")
            if initial_state.get("errors"):
                return initial_state

            # phase 2: balancer optimization  
            log_agent_info(self.name, "phase 2: optimizing with balancer")
            balancer_result = self.balancer_agent(
                initial_layout_data=initial_state["initial_layout_data"],
                column_analysis=initial_state["column_analysis"],
                state=initial_state
            )
            
            # save balancer decisions
            (
                optimized_story_board,
                capacity_fill_report,
            ) = self._restore_grounded_claims_to_capacity(
                optimized_story_board=balancer_result[
                    "optimized_story_board"
                ],
                original_story_board=initial_state[
                    "story_board"
                ],
                state=initial_state,
            )

            balancer_result[
                "optimized_story_board"
            ] = optimized_story_board

            content_guard = (
                balancer_result
                .setdefault("balancer_decisions", {})
                .setdefault("content_guard", {})
            )
            content_guard[
                "capacity_fill"
            ] = capacity_fill_report

            self._save_balancer_output(
                balancer_result,
                initial_state,
            )
            
            # update state with optimized story board
            initial_state["optimized_story_board"] = balancer_result["optimized_story_board"]
            initial_state["balancer_decisions"] = balancer_result["balancer_decisions"]
            
            # phase 3: final layout generation
            log_agent_info(self.name, "phase 3: generating final layout")
            final_state = self.layout_agent(initial_state, mode="final")
            if final_state.get("errors"):
                return final_state
            
            # update token counts
            final_state["tokens"].add_text(
                balancer_result.get("input_tokens", 0),
                balancer_result.get("output_tokens", 0)
            )
            
            log_agent_success(self.name, "3-phase layout optimization complete")
            return final_state
            
        except Exception as e:
            log_agent_error(self.name, f"3-phase optimization error: {e}")
            state.setdefault("errors", []).append(f"{self.name}: {e}")
            return state

    def _run_family_constraint_engine(
        self,
        state: PosterState,
        family_id: str,
    ) -> PosterState:
        """Fit grounded content to a bounded family before rendering."""

        log_agent_info(
            self.name,
            f"searching capacity-safe variants for {family_id}",
        )
        board = state.get("story_board")
        if not isinstance(board, dict):
            raise ValueError("missing story_board from curator")
        topology = state.get("template_validation_topology") or {}
        fixed_zones = topology.get("zones") if topology else None
        context = state.get("iteration_context") or {}
        if context.get("portfolio_mode") == "improve":
            state.setdefault(
                "revision_parent_layout_spec",
                deepcopy(state.get("layout_spec") or {}),
            )
            if state.get("improve_safe_fallback"):
                state["layout_revision_constraints"] = (
                    self._constraints_from_current_parent(state)
                )
        try:
            fitted_board, layout_spec, fit_report = fit_family_layout(
                self.layout_agent,
                board,
                state,
                family_id,
                config=state.get("critic_config") or {},
                fixed_zones=fixed_zones,
            )
        except LayoutFeasibilityError as exc:
            fit_report = exc.report or {
                "schema_version": 1,
                "status": "infeasible",
                "family_id": family_id,
                "reason": str(exc),
            }
            state["layout_feasibility_report"] = fit_report
            state["layout_preflight_report"] = {
                "schema_version": 1,
                "status": "not_run",
                "passed": False,
                "issue_count": 0,
                "issues": [],
                "family_id": family_id,
                "blocked_by": "layout_feasibility",
            }
            state["layout_preflight_failed"] = True
            state.setdefault("errors", []).append(
                f"{self.name}: {exc}"
            )
            self._save_family_fit_artifacts(state)
            detail = (
                f" | {fit_report.get('reason_code')} | "
                f"{fit_report.get('feasible_count', 0)}/"
                f"{fit_report.get('trial_count', 0)} variants | "
                f"frequent gate {fit_report.get('dominant_blocker') or 'unknown'}"
                if fit_report.get("reason_code") else ""
            )
            log_agent_error(self.name, str(exc) + detail)
            return state

        log_agent_info(
            self.name,
            "fit search: "
            f"{fit_report.get('feasible_count', 0)}/"
            f"{fit_report.get('trial_count', 0)} variants feasible; "
            f"selected {fit_report.get('variant_id')}",
        )
        if topology:
            layout_spec["validation_template_id"] = state.get(
                "validation_template_id"
            )
        state["optimized_story_board"] = fitted_board
        state["layout_spec"] = layout_spec
        state["layout_feasibility_report"] = fit_report
        state["layout_content_selection"] = deepcopy(
            fit_report.get("candidate_content_selection") or {}
        )
        if context.get("portfolio_mode") == "improve":
            state["revision_execution_report"] = (
                self._revision_execution_report(state, fitted_board, layout_spec)
            )
            if state["revision_execution_report"]["status"] == "constraint_failure":
                state["layout_preflight_report"] = {
                    "schema_version": 1,
                    "status": "not_run",
                    "passed": False,
                    "issue_count": 0,
                    "issues": [],
                    "family_id": family_id,
                    "blocked_by": "revision_constraints",
                }
                state["layout_preflight_failed"] = True
                state.setdefault("errors", []).append(
                    f"{self.name}: Improve revision constraints were not preserved"
                )
                self._save_family_fit_artifacts(state)
                return state
        state["balancer_decisions"] = {
            "schema_version": 3,
            "skipped": True,
            "reason": "capacity_aware_family_constraint_engine",
            "layout_family": family_id,
            "variant_id": layout_spec.get("variant_id"),
            "content_guard": {
                "scientific_text_rewritten": False,
                "visible_claims_grounded": True,
                "capacity_selection": deepcopy(
                    state["layout_content_selection"]
                ),
            },
        }
        self._save_family_fit_artifacts(state)

        final_state = self.layout_agent(state, mode="final")
        if final_state.get("errors"):
            final_state["layout_preflight_failed"] = True
            return final_state

        preflight = validate_compiled_layout(
            final_state.get("design_layout") or [],
            final_state.get("layout_spec") or {},
            final_state,
            poster_margin=self.layout_agent.poster_margin,
            title_height_fraction=self.layout_agent.title_height_fraction,
        )
        final_state["layout_preflight_report"] = preflight
        final_state["layout_feasibility_report"]["compiled_preflight"] = (
            deepcopy(preflight)
        )
        self._save_family_fit_artifacts(final_state)
        if not preflight["passed"]:
            final_state["layout_preflight_failed"] = True
            final_state.setdefault("errors", []).append(
                f"{self.name}: compiled layout failed preflight "
                f"({preflight['issue_count']} issues)"
            )
            return final_state

        final_state["layout_preflight_failed"] = False
        log_agent_success(
            self.name,
            f"capacity-safe {family_id} variant compiled",
        )
        return final_state

    @staticmethod
    def _constraints_from_current_parent(state: PosterState) -> Dict[str, Any]:
        spec = state.get("layout_spec") or {}
        board = state.get("story_board") or {}
        sections = [
            item for item in board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(item, dict)
        ]
        return {
            "schema_version": 1,
            "section_to_zone": {
                str(section_id): str(zone.get("zone_id"))
                for zone in spec.get("zones", [])
                if isinstance(zone, dict) and zone.get("zone_id")
                for section_id in zone.get("section_ids", [])
            },
            "reading_order": [
                str(item) for item in spec.get("reading_order", [])
            ],
            "primary_anchor_zone": spec.get("primary_anchor_zone"),
            "must_retain_claim_ids": sorted({
                str(claim_id)
                for section in sections
                for claim_id in section.get("claim_ids", [])
                if claim_id
            }),
            "must_retain_visual_ids": sorted({
                str(visual.get("visual_id"))
                for section in sections
                for visual in section.get("visual_assets", [])
                if isinstance(visual, dict) and visual.get("visual_id")
            }),
            "requested_operations": [],
            "safe_parent_fallback": True,
        }

    @staticmethod
    def _revision_execution_report(
        state: PosterState,
        board: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        constraints = state.get("layout_revision_constraints") or {}
        sections = [
            item for item in board.get("spatial_content_plan", {}).get("sections", [])
            if isinstance(item, dict)
        ]
        visible_claims = {
            str(claim_id)
            for section in sections for claim_id in section.get("claim_ids", [])
        }
        visible_visuals = {
            str(visual.get("visual_id"))
            for section in sections
            for visual in section.get("visual_assets", [])
            if isinstance(visual, dict) and visual.get("visual_id")
        }
        actual_zones = {
            str(section_id): str(zone.get("zone_id"))
            for zone in spec.get("zones", [])
            if isinstance(zone, dict)
            for section_id in zone.get("section_ids", [])
        }
        expected_zones = {
            str(key): str(value)
            for key, value in (constraints.get("section_to_zone") or {}).items()
        }
        mismatched_zones = sorted(
            section_id for section_id, zone_id in expected_zones.items()
            if actual_zones.get(section_id) != zone_id
        )
        missing_claims = sorted(
            set(constraints.get("must_retain_claim_ids", [])) - visible_claims
        )
        missing_visuals = sorted(
            set(constraints.get("must_retain_visual_ids", [])) - visible_visuals
        )
        requested_order = [
            str(item) for item in constraints.get("reading_order", [])
        ]
        reading_order_applied = (
            not requested_order
            or requested_order == [
                str(item) for item in spec.get("reading_order", [])
            ]
        )
        requested_anchor = constraints.get("primary_anchor_zone")
        anchor_applied = (
            not requested_anchor
            or str(spec.get("primary_anchor_zone")) == str(requested_anchor)
        )
        applied = not (
            mismatched_zones or missing_claims or missing_visuals
            or not reading_order_applied or not anchor_applied
        )
        operation_results = []
        for operation in (state.get("revision_plan") or {}).get(
            "operations", []
        ):
            if not isinstance(operation, dict):
                continue
            kind = str(operation.get("operation") or "")
            operation_applied = True
            detail = "accepted by the grounded Planner"
            if kind == "move_section_to_zone":
                section_id = str(operation.get("section_id") or "")
                operation_applied = (
                    actual_zones.get(section_id)
                    == str(operation.get("zone_id") or "")
                )
                detail = "section-zone assignment verified"
            elif kind == "swap_section_zones":
                operation_applied = not any(
                    str(operation.get(key) or "") in mismatched_zones
                    for key in ("first_section_id", "second_section_id")
                )
                detail = "both swapped section-zone assignments verified"
            elif kind == "set_reading_order":
                operation_applied = reading_order_applied
                detail = "reading order verified"
            elif kind == "set_primary_anchor":
                operation_applied = anchor_applied
                detail = "primary anchor verified"
            elif kind == "adjust_zone_budget":
                zone_id = str(operation.get("zone_id") or "")
                operation_applied = zone_id in (
                    (state.get("layout_feasibility_report") or {})
                    .get("zone_budget_preferences_met") or []
                )
                detail = (
                    "bounded zone-area change verified"
                    if operation_applied
                    else "no safe zone-area change found"
                )
            operation_results.append({
                "operation": kind,
                "status": "applied" if operation_applied else "not_applied",
                "detail": detail,
            })
        content_revision = state.get("content_revision") or {}
        accepted_content = {
            (
                str(item.get("operation") or ""),
                str(item.get("section_id") or ""),
            )
            for item in content_revision.get("accepted_actions", [])
            if isinstance(item, dict)
        }
        rejected_content = {
            (
                str(item.get("operation") or ""),
                str(item.get("section_id") or ""),
            ): str(item.get("reason") or "rejected")
            for item in content_revision.get("rejected_actions", [])
            if isinstance(item, dict)
        }
        content_action_results = []
        for action in (state.get("revision_plan") or {}).get(
            "content_actions", []
        ):
            if not isinstance(action, dict):
                continue
            key = (
                str(action.get("operation") or ""),
                str(action.get("section_id") or ""),
            )
            status = (
                "applied" if key in accepted_content
                else "rejected" if key in rejected_content
                else "not_executed"
            )
            content_action_results.append({
                "operation": key[0],
                "section_id": key[1],
                "status": status,
                "detail": rejected_content.get(key),
            })
        return {
            "schema_version": 2,
            "status": "rolled_back_to_parent" if state.get("improve_safe_fallback")
            else "applied" if applied else "constraint_failure",
            "parent_candidate_id": (
                state.get("iteration_context") or {}
            ).get("parent_candidate_id"),
            "requested_operations": deepcopy(
                constraints.get("requested_operations") or []
            ),
            "content_revision": deepcopy(content_revision),
            "operation_results": operation_results,
            "content_action_results": content_action_results,
            "mismatched_section_zones": mismatched_zones,
            "missing_claim_ids": missing_claims,
            "missing_visual_ids": missing_visuals,
            "reading_order_applied": reading_order_applied,
            "primary_anchor_applied": anchor_applied,
            "safe_parent_fallback": bool(state.get("improve_safe_fallback")),
        }

    @staticmethod
    def _save_family_fit_artifacts(state: PosterState) -> None:
        output_dir = Path(state["output_dir"]) / "content"
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {
            "layout_feasibility_report.json": state.get(
                "layout_feasibility_report", {}
            ),
            "layout_preflight_report.json": state.get(
                "layout_preflight_report", {}
            ),
            "optimized_story_board.json": state.get(
                "optimized_story_board", {}
            ),
            "layout_content_selection.json": state.get(
                "layout_content_selection", {}
            ),
            "revision_execution_report.json": state.get(
                "revision_execution_report", {}
            ),
        }
        for filename, payload in artifacts.items():
            with open(output_dir / filename, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)

    def _restore_grounded_claims_to_capacity(
        self,
        optimized_story_board: Dict[str, Any],
        original_story_board: Dict[str, Any],
        state: PosterState,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Enforce physical capacity, then restore source claims that fit."""

        board = deepcopy(optimized_story_board)
        optimized_sections = (
            board
            .get("spatial_content_plan", {})
            .get("sections", [])
        )
        original_sections = (
            original_story_board
            .get("spatial_content_plan", {})
            .get("sections", [])
        )
        original_by_id = {
            section.get("section_id"): section
            for section in original_sections
            if isinstance(section, dict)
            and section.get("section_id")
        }

        skipped_sections: List[str] = []
        claim_text_maps: Dict[str, Dict[str, str]] = {}
        for section in optimized_sections:
            if not isinstance(section, dict):
                continue

            section_id = section.get("section_id")
            original = original_by_id.get(section_id)
            if not original:
                continue

            original_claim_ids = original.get("claim_ids", [])
            original_texts = original.get("text_content", [])
            selected_claim_ids = section.get("claim_ids", [])
            if (
                not isinstance(original_claim_ids, list)
                or not isinstance(original_texts, list)
                or len(original_claim_ids) != len(original_texts)
                or not isinstance(selected_claim_ids, list)
            ):
                skipped_sections.append(section_id)
                continue

            claim_text_map = dict(
                zip(original_claim_ids, original_texts)
            )
            selected_set = {
                claim_id
                for claim_id in selected_claim_ids
                if claim_id in claim_text_map
            }
            normalized_claim_ids = [
                claim_id
                for claim_id in original_claim_ids
                if claim_id in selected_set
            ]
            section["claim_ids"] = normalized_claim_ids
            section["text_content"] = [
                claim_text_map[claim_id]
                for claim_id in normalized_claim_ids
            ]
            claim_text_maps[section_id] = claim_text_map

        llm_selected_claim_count = sum(
            len(section.get("claim_ids", []))
            for section in optimized_sections
            if isinstance(section, dict)
        )

        available_height, column_width = (
            self._column_geometry(state)
        )
        # Track the content target and actual renderer spacing separately.
        # This also catches an overflowing initial Balancer selection before
        # any grounded claims are restored.
        max_utilization = self.layout_agent.column_balancing.get(
            "target_utilization",
            0.9,
        )
        max_column_height = available_height * max_utilization
        max_physical_utilization = (
            self.layout_agent.column_balancing.get(
                "overflow_threshold",
                1.0,
            )
        )
        max_physical_height = (
            available_height * max_physical_utilization
        )

        section_heights = {}
        column_sections = {
            "left": [],
            "middle": [],
            "right": [],
        }

        for section in optimized_sections:
            if not isinstance(section, dict):
                continue

            section_id = section.get("section_id")
            column = section.get("column_assignment")
            if not section_id or column not in column_sections:
                continue

            section_heights[section_id] = (
                self._measure_section_height(
                    section,
                    column_width,
                    available_height,
                    state,
                )
            )
            column_sections[column].append(section_id)

        column_heights = {
            column: self._column_height(
                section_ids,
                section_heights,
            )
            for column, section_ids in column_sections.items()
        }
        llm_utilization = {
            column: (
                height / available_height
                if available_height
                else 0.0
            )
            for column, height in column_heights.items()
        }

        physical_column_heights = {
            column: self._column_height(
                section_ids,
                section_heights,
                include_renderer_reserve=True,
            )
            for column, section_ids in column_sections.items()
        }
        llm_physical_utilization = {
            column: (
                height / available_height
                if available_height
                else 0.0
            )
            for column, height in physical_column_heights.items()
        }

        section_by_id = {
            section.get("section_id"): section
            for section in optimized_sections
            if isinstance(section, dict)
            and section.get("section_id")
        }
        priority_rank = {
            "bottom": 0,
            "middle": 1,
            "top": 2,
        }
        pruned_due_physical_overflow = []
        rebalanced_sections_due_physical_overflow = []
        removed_sections_due_physical_overflow = []

        for column, section_ids in column_sections.items():
            while (
                physical_column_heights[column]
                > max_physical_height
            ):
                rebalanced_sections = (
                    self._rebalance_sections_to_physical_capacity(
                        optimized_sections=optimized_sections,
                        column_sections=column_sections,
                        section_heights=section_heights,
                        max_physical_height=max_physical_height,
                    )
                )
                if rebalanced_sections:
                    rebalanced_sections_due_physical_overflow.extend(
                        rebalanced_sections
                    )
                    column_heights = {
                        candidate_column: self._column_height(
                            candidate_section_ids,
                            section_heights,
                        )
                        for candidate_column, candidate_section_ids
                        in column_sections.items()
                    }
                    physical_column_heights = {
                        candidate_column: self._column_height(
                            candidate_section_ids,
                            section_heights,
                            include_renderer_reserve=True,
                        )
                        for candidate_column, candidate_section_ids
                        in column_sections.items()
                    }
                    continue

                candidates = []
                for position, section_id in enumerate(section_ids):
                    section = section_by_id.get(section_id)
                    if (
                        not section
                        or section_id not in claim_text_maps
                        or not section.get("claim_ids")
                    ):
                        continue
                    can_trim_claim = (
                        len(section["claim_ids"]) > 1
                    )
                    can_remove_section = (
                        section.get("vertical_priority") == "bottom"
                        and len(section_ids) > 1
                    )
                    if not can_trim_claim and not can_remove_section:
                        continue
                    candidates.append((
                        priority_rank.get(
                            section.get("vertical_priority"),
                            1,
                        ),
                        -position,
                        section_id,
                    ))

                if not candidates:
                    break

                _, _, section_id = min(candidates)
                section = section_by_id[section_id]
                if (
                    len(section["claim_ids"]) == 1
                    and section.get("vertical_priority") == "bottom"
                    and len(section_ids) > 1
                ):
                    removed_sections_due_physical_overflow.append({
                        "section_id": section_id,
                        "column": column,
                        "claim_ids": list(section["claim_ids"]),
                    })
                    optimized_sections.remove(section)
                    section_ids.remove(section_id)
                    section_heights.pop(section_id, None)
                    section_by_id.pop(section_id, None)
                    column_heights[column] = self._column_height(
                        section_ids,
                        section_heights,
                    )
                    physical_column_heights[column] = (
                        self._column_height(
                            section_ids,
                            section_heights,
                            include_renderer_reserve=True,
                        )
                    )
                    continue

                removed_claim_id = section["claim_ids"][-1]
                section["claim_ids"] = section["claim_ids"][:-1]
                section["text_content"] = [
                    claim_text_maps[section_id][claim_id]
                    for claim_id in section["claim_ids"]
                ]

                new_height = self._measure_section_height(
                    section,
                    column_width,
                    available_height,
                    state,
                )
                section_heights[section_id] = new_height
                column_heights[column] = self._column_height(
                    section_ids,
                    section_heights,
                )
                physical_column_heights[column] = (
                    self._column_height(
                        section_ids,
                        section_heights,
                        include_renderer_reserve=True,
                    )
                )
                pruned_due_physical_overflow.append({
                    "claim_id": removed_claim_id,
                    "section_id": section_id,
                    "column": column,
                })

        before_utilization = {
            column: (
                height / available_height
                if available_height
                else 0.0
            )
            for column, height in column_heights.items()
        }
        physical_before_utilization = {
            column: (
                height / available_height
                if available_height
                else 0.0
            )
            for column, height in physical_column_heights.items()
        }
        unresolved_physical_overflow_columns = [
            column
            for column, height in physical_column_heights.items()
            if height > max_physical_height
        ]

        restored_claim_ids: List[str] = []
        skipped_due_capacity: List[str] = []

        for section in optimized_sections:
            if not isinstance(section, dict):
                continue

            section_id = section.get("section_id")
            column = section.get("column_assignment")
            original = original_by_id.get(section_id)
            if (
                not original
                or column not in column_sections
                or section_id not in section_heights
            ):
                continue

            original_claim_ids = original.get("claim_ids", [])
            selected_claim_ids = section.get("claim_ids", [])
            claim_text_map = claim_text_maps.get(section_id)
            if claim_text_map is None:
                continue

            selected_set = {
                claim_id
                for claim_id in selected_claim_ids
                if claim_id in claim_text_map
            }
            missing_claim_ids = [
                claim_id
                for claim_id in original_claim_ids
                if claim_id not in selected_set
            ]

            if not missing_claim_ids:
                section["claim_ids"] = [
                    claim_id
                    for claim_id in original_claim_ids
                    if claim_id in selected_set
                ]
                section["text_content"] = [
                    claim_text_map[claim_id]
                    for claim_id in section["claim_ids"]
                ]
                continue

            # Restore an original-order prefix. The LLM-selected claims
            # remain, and every trial is measured with renderer geometry.
            low = 0
            high = len(missing_claim_ids)
            best_height = section_heights[section_id]

            while low < high:
                trial_count = (low + high + 1) // 2
                trial_set = selected_set.union(
                    missing_claim_ids[:trial_count]
                )
                trial_claim_ids = [
                    claim_id
                    for claim_id in original_claim_ids
                    if claim_id in trial_set
                ]
                trial_section = deepcopy(section)
                trial_section["claim_ids"] = trial_claim_ids
                trial_section["text_content"] = [
                    claim_text_map[claim_id]
                    for claim_id in trial_claim_ids
                ]
                trial_height = self._measure_section_height(
                    trial_section,
                    column_width,
                    available_height,
                    state,
                )
                trial_column_height = (
                    column_heights[column]
                    - section_heights[section_id]
                    + trial_height
                )
                trial_section_heights = dict(section_heights)
                trial_section_heights[section_id] = trial_height
                trial_physical_height = self._column_height(
                    column_sections[column],
                    trial_section_heights,
                    include_renderer_reserve=True,
                )

                if (
                    trial_column_height <= max_column_height
                    and trial_physical_height
                    <= max_physical_height
                ):
                    low = trial_count
                    best_height = trial_height
                else:
                    high = trial_count - 1

            restored = missing_claim_ids[:low]
            selected_set.update(restored)
            final_claim_ids = [
                claim_id
                for claim_id in original_claim_ids
                if claim_id in selected_set
            ]
            section["claim_ids"] = final_claim_ids
            section["text_content"] = [
                claim_text_map[claim_id]
                for claim_id in final_claim_ids
            ]

            column_heights[column] = (
                column_heights[column]
                - section_heights[section_id]
                + best_height
            )
            section_heights[section_id] = best_height
            physical_column_heights[column] = (
                self._column_height(
                    column_sections[column],
                    section_heights,
                    include_renderer_reserve=True,
                )
            )
            restored_claim_ids.extend(restored)
            skipped_due_capacity.extend(
                missing_claim_ids[low:]
            )

        after_utilization = {
            column: (
                height / available_height
                if available_height
                else 0.0
            )
            for column, height in column_heights.items()
        }
        physical_after_utilization = {
            column: (
                height / available_height
                if available_height
                else 0.0
            )
            for column, height in physical_column_heights.items()
        }
        original_claim_count = sum(
            len(section.get("claim_ids", []))
            for section in original_sections
            if isinstance(section, dict)
        )
        final_claim_count = sum(
            len(section.get("claim_ids", []))
            for section in optimized_sections
            if isinstance(section, dict)
        )

        report = {
            "applied": bool(
                restored_claim_ids
                or pruned_due_physical_overflow
                or rebalanced_sections_due_physical_overflow
                or removed_sections_due_physical_overflow
            ),
            "max_utilization": max_utilization,
            "max_physical_utilization": (
                max_physical_utilization
            ),
            "available_height": available_height,
            "original_claim_count": original_claim_count,
            "llm_selected_claim_count": llm_selected_claim_count,
            "final_claim_count": final_claim_count,
            "pruned_due_physical_overflow": (
                pruned_due_physical_overflow
            ),
            "rebalanced_sections_due_physical_overflow": (
                rebalanced_sections_due_physical_overflow
            ),
            "removed_sections_due_physical_overflow": (
                removed_sections_due_physical_overflow
            ),
            "restored_claim_ids": restored_claim_ids,
            "skipped_due_capacity": skipped_due_capacity,
            "skipped_sections": skipped_sections,
            "llm_utilization": llm_utilization,
            "llm_physical_utilization": (
                llm_physical_utilization
            ),
            "utilization_before": before_utilization,
            "utilization_after": after_utilization,
            "physical_utilization_before": (
                physical_before_utilization
            ),
            "physical_utilization_after": (
                physical_after_utilization
            ),
            "unresolved_physical_overflow_columns": (
                unresolved_physical_overflow_columns
            ),
        }

        log_agent_info(
            self.name,
            (
                "capacity guard pruned "
                f"{len(pruned_due_physical_overflow)} and restored "
                f"{len(restored_claim_ids)} grounded claims; removed "
                f"{len(removed_sections_due_physical_overflow)} sections; "
                f"rebalanced "
                f"{len(rebalanced_sections_due_physical_overflow)}; "
                f"final count {final_claim_count}"
            ),
        )

        return board, report

    def _rebalance_sections_to_physical_capacity(
        self,
        optimized_sections: List[Dict[str, Any]],
        column_sections: Dict[str, List[str]],
        section_heights: Dict[str, float],
        max_physical_height: float,
    ) -> List[Dict[str, str]]:
        """Move at most two non-top sections when all columns then fit."""

        columns = ("left", "middle", "right")
        section_by_id = {
            section.get("section_id"): section
            for section in optimized_sections
            if isinstance(section, dict)
            and section.get("section_id") in section_heights
            and section.get("column_assignment") in columns
        }
        current_assignments = {
            section_id: section["column_assignment"]
            for section_id, section in section_by_id.items()
        }
        movable_section_ids = [
            section_id
            for section_id, section in section_by_id.items()
            if section.get("vertical_priority") != "top"
        ]
        if not movable_section_ids:
            return []

        priority_move_cost = {
            "bottom": 1,
            "middle": 2,
        }
        best_candidate = None

        for destinations in product(
            columns,
            repeat=len(movable_section_ids),
        ):
            assignments = dict(current_assignments)
            assignments.update(zip(movable_section_ids, destinations))
            moved_section_ids = [
                section_id
                for section_id in movable_section_ids
                if assignments[section_id]
                != current_assignments[section_id]
            ]
            if not moved_section_ids or len(moved_section_ids) > 2:
                continue

            candidate_columns = {
                column: []
                for column in columns
            }
            for section in optimized_sections:
                if not isinstance(section, dict):
                    continue
                section_id = section.get("section_id")
                destination = assignments.get(section_id)
                if destination in candidate_columns:
                    candidate_columns[destination].append(section_id)

            if any(
                not candidate_columns[column]
                for column in columns
            ):
                continue

            candidate_heights = {
                column: self._column_height(
                    candidate_columns[column],
                    section_heights,
                    include_renderer_reserve=True,
                )
                for column in columns
            }
            if any(
                height > max_physical_height
                for height in candidate_heights.values()
            ):
                continue

            move_cost = sum(
                priority_move_cost.get(
                    section_by_id[section_id].get(
                        "vertical_priority"
                    ),
                    2,
                )
                for section_id in moved_section_ids
            )
            heights = tuple(candidate_heights.values())
            score = (
                move_cost,
                len(moved_section_ids),
                max(heights),
                max(heights) - min(heights),
                destinations,
            )
            if best_candidate is None or score < best_candidate[0]:
                best_candidate = (
                    score,
                    assignments,
                    candidate_columns,
                    moved_section_ids,
                )

        if best_candidate is None:
            return []

        _, assignments, candidate_columns, moved_section_ids = (
            best_candidate
        )
        moves = []
        for section_id in moved_section_ids:
            section = section_by_id[section_id]
            source = current_assignments[section_id]
            destination = assignments[section_id]
            section["column_assignment"] = destination
            moves.append({
                "section_id": section_id,
                "from_column": source,
                "to_column": destination,
                "vertical_priority": section.get(
                    "vertical_priority",
                    "middle",
                ),
            })

        for column in columns:
            column_sections[column][:] = candidate_columns[column]

        return moves

    def _column_geometry(
        self,
        state: PosterState,
    ) -> Tuple[float, float]:
        effective_height = (
            state["poster_height"]
            - 2 * self.layout_agent.poster_margin
        )
        title_region_height = (
            effective_height
            * self.layout_agent.title_height_fraction
        )
        available_height = (
            effective_height - title_region_height
        )
        column_width = (
            state["poster_width"]
            - 2 * self.layout_agent.poster_margin
            - 2 * self.layout_agent.column_spacing
        ) / 3
        return available_height, column_width

    def _measure_section_height(
        self,
        section: Dict[str, Any],
        column_width: float,
        available_height: float,
        state: PosterState,
    ) -> float:
        return self.layout_agent._calculate_precise_section_height(
            section,
            column_width,
            state,
            available_height,
        )

    def _column_height(
        self,
        section_ids: List[str],
        section_heights: Dict[str, float],
        include_renderer_reserve: bool = False,
    ) -> float:
        height = sum(
            section_heights[section_id]
            for section_id in section_ids
        )
        if len(section_ids) > 1:
            spacing = self.layout_agent.layout_constants[
                "section_padding"
            ]
            if include_renderer_reserve:
                spacing += self.layout_agent.layout_constants.get(
                    "body_render_reserve",
                    0.0,
                )
            height += (
                (len(section_ids) - 1)
                * spacing
            )
        return height

    def _save_balancer_output(self, balancer_result: Dict, state: PosterState):
        """save balancer optimization results"""
        output_dir = Path(state["output_dir"]) / "content"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_dir / "optimized_story_board.json", "w", encoding='utf-8') as f:
            json.dump(balancer_result["optimized_story_board"], f, indent=2)
        
        with open(output_dir / "balancer_decisions.json", "w", encoding='utf-8') as f:
            json.dump(balancer_result["balancer_decisions"], f, indent=2)


def layout_with_balancer_node(state: PosterState) -> Dict[str, Any]:
    """layout with balancer node for langgraph"""
    try:
        agent = LayoutWithBalancerAgent()
        result = agent(state)
        
        return {
            **state,
            "design_layout": result.get("design_layout"),
            "optimized_column_assignment": result.get("optimized_column_assignment"),
            "optimized_story_board": result.get("optimized_story_board"),
            "balancer_decisions": result.get("balancer_decisions"),
            "tokens": result.get("tokens"),
            "current_agent": result.get("current_agent"),
            "errors": result.get("errors", [])
        }
    except Exception as e:
        log_agent_error("layout_with_balancer", f"node error: {e}")
        return {**state, "errors": state.get("errors", []) + [f"layout_with_balancer: {e}"]}
