"""
3-phase layout optimization orchestrator
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.state.poster_state import PosterState
from src.agents.layout_agent import LayoutAgent
from src.agents.balancer_agent import BalancerAgent
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
            return {"errors": [f"{self.name}: {e}"]}

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
        removed_sections_due_physical_overflow = []

        for column, section_ids in column_sections.items():
            while (
                physical_column_heights[column]
                > max_physical_height
            ):
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
                f"final count {final_claim_count}"
            ),
        )

        return board, report

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
