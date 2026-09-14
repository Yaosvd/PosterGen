"""
Column-space balancer with scientific-content protection.

The Balancer may optimize presentation/layout decisions, but verified
scientific text produced upstream is immutable.
"""

import json
from copy import deepcopy
from typing import Any, Dict

from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.langgraph_utils import (
    LangGraphAgent,
    extract_json,
    load_prompt,
)
from utils.src.logging_utils import (
    log_agent_error,
    log_agent_info,
    log_agent_success,
)


class BalancerAgent:
    def __init__(self):
        self.name = "balancer_agent"
        self.balancer_prompt = load_prompt(
            "config/prompts/layout_balancer.txt"
        )

    def __call__(
        self,
        initial_layout_data: Dict,
        column_analysis: Dict,
        state: PosterState,
    ) -> Dict:
        """
        Optimize column-space distribution.

        Scientific text is protected after the LLM response by
        _sanitize_optimized_story_board().
        """

        log_agent_info(
            self.name,
            "optimizing column balance",
        )

        structured_sections = state.get(
            "structured_sections"
        )

        story_board = state.get(
            "story_board"
        )

        if not story_board:
            raise ValueError(
                "story_board is missing"
            )

        if not column_analysis:
            raise ValueError(
                "column_analysis is missing"
            )

        columns = column_analysis[
            "columns"
        ]

        left_rate = columns[
            "left"
        ]["utilization_rate"]

        middle_rate = columns[
            "middle"
        ]["utilization_rate"]

        right_rate = columns[
            "right"
        ]["utilization_rate"]

        log_agent_info(
            self.name,
            (
                "utilization - "
                f"left: {left_rate:.1%}, "
                f"middle: {middle_rate:.1%}, "
                f"right: {right_rate:.1%}"
            ),
        )

        model_config = apply_agent_policy(
            state["text_model"],
            "layout_optimizer",
        )

        agent = LangGraphAgent(
            "layout optimization specialist",
            model_config,
            state,
            "layout_optimizer",
        )

        variables = {
            "structured_sections": json.dumps(
                structured_sections,
                indent=2,
                ensure_ascii=False,
            ),
            "current_story_board": json.dumps(
                story_board,
                indent=2,
                ensure_ascii=False,
            ),
            "column_analysis": json.dumps(
                column_analysis,
                indent=2,
                ensure_ascii=False,
            ),
            "available_height": column_analysis[
                "available_height"
            ],
            "left_utilization": (
                f"{left_rate:.1%}"
            ),
            "middle_utilization": (
                f"{middle_rate:.1%}"
            ),
            "right_utilization": (
                f"{right_rate:.1%}"
            ),
            "left_status": columns[
                "left"
            ]["status"],
            "middle_status": columns[
                "middle"
            ]["status"],
            "right_status": columns[
                "right"
            ]["status"],
        }

        max_attempts = 3

        for attempt in range(
            max_attempts
        ):
            prompt = (
                self.balancer_prompt.format(
                    **variables
                )
            )

            agent.reset()

            response = agent.step(
                prompt
            )

            log_agent_info(
                self.name,
                (
                    f"attempt {attempt + 1}: "
                    f"response "
                    f"{len(response.content)} chars"
                ),
            )

            try:
                raw_optimized = extract_json(
                    response.content
                )

                if not self._validate_story_board(
                    raw_optimized
                ):
                    log_agent_error(
                        self.name,
                        (
                            f"attempt {attempt + 1}: "
                            "validation failed"
                        ),
                    )
                    continue

                (
                    optimized_story_board,
                    guard_report,
                ) = (
                    self._sanitize_optimized_story_board(
                        raw_optimized,
                        story_board,
                    )
                )

                if not self._validate_story_board(
                    optimized_story_board
                ):
                    log_agent_error(
                        self.name,
                        (
                            f"attempt {attempt + 1}: "
                            "sanitized story board invalid"
                        ),
                    )
                    continue

                decisions = (
                    self._extract_decisions(
                        response.content
                    )
                )

                decisions[
                    "content_guard"
                ] = guard_report

                log_agent_success(
                    self.name,
                    (
                        f"optimized on attempt "
                        f"{attempt + 1}; "
                        "scientific text protected"
                    ),
                )

                return {
                    "optimized_story_board": (
                        optimized_story_board
                    ),
                    "balancer_decisions": (
                        decisions
                    ),
                    "input_tokens": (
                        response.input_tokens
                    ),
                    "output_tokens": (
                        response.output_tokens
                    ),
                }

            except Exception as exc:
                log_agent_error(
                    self.name,
                    (
                        f"attempt {attempt + 1}: "
                        "optimization failed - "
                        f"{exc}"
                    ),
                )

        # Fail closed: use the verified GroundedCurator board.
        log_agent_error(
            self.name,
            (
                f"failed after "
                f"{max_attempts} attempts; "
                "using original grounded story board"
            ),
        )

        return {
            "optimized_story_board": (
                deepcopy(
                    story_board
                )
            ),
            "balancer_decisions": {
                "content_guard": {
                    "fallback_to_original": True,
                }
            },
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _sanitize_optimized_story_board(
        self,
        optimized_story_board: Dict,
        original_story_board: Dict,
    ):
        """
        Copy only layout-safe decisions from the Balancer output.

        Allowed:
        - reorder existing sections;
        - move sections between columns;
        - change vertical_priority;
        - omit existing sections;
        - choose a subset of existing claim_ids;
        - remove already-approved visuals.

        Forbidden:
        - rewrite text_content;
        - invent scientific claims;
        - alter numbers;
        - alter comparison directions;
        - rename methods/entities;
        - create new scientific sections;
        - rewrite section titles.

        text_content is always reconstructed from the original
        GroundedCurator output.
        """

        original_plan = (
            original_story_board
            .get(
                "spatial_content_plan",
                {},
            )
        )

        optimized_plan = (
            optimized_story_board
            .get(
                "spatial_content_plan",
                {},
            )
        )

        original_sections = (
            original_plan.get(
                "sections",
                [],
            )
        )

        candidate_sections = (
            optimized_plan.get(
                "sections",
                [],
            )
        )

        original_by_id = {
            section.get(
                "section_id"
            ): section
            for section
            in original_sections
            if isinstance(
                section,
                dict,
            )
            and section.get(
                "section_id"
            )
        }

        report = {
            "llm_sections_received": (
                len(
                    candidate_sections
                )
                if isinstance(
                    candidate_sections,
                    list,
                )
                else 0
            ),
            "safe_sections_output": 0,
            "unknown_sections_removed": [],
            "duplicate_sections_removed": [],
            "text_rewrites_blocked": 0,
            "title_rewrites_blocked": 0,
            "claim_subsets_applied": 0,
            "invalid_claim_ids_removed": [],
            "unapproved_visuals_removed": [],
        }

        if not isinstance(
            candidate_sections,
            list,
        ):
            report[
                "fallback_to_original"
            ] = True

            return deepcopy(
                original_story_board
            ), report

        safe_sections = []
        used_section_ids = set()

        for candidate in (
            candidate_sections
        ):
            if not isinstance(
                candidate,
                dict,
            ):
                continue

            section_id = (
                candidate.get(
                    "section_id"
                )
            )

            # Balancer cannot create sections.
            if (
                section_id
                not in original_by_id
            ):
                report[
                    "unknown_sections_removed"
                ].append(
                    section_id
                )
                continue

            if (
                section_id
                in used_section_ids
            ):
                report[
                    "duplicate_sections_removed"
                ].append(
                    section_id
                )
                continue

            used_section_ids.add(
                section_id
            )

            original = (
                original_by_id[
                    section_id
                ]
            )

            # Start from grounded content.
            safe = deepcopy(
                original
            )

            # ------------------------------------------------
            # Layout-only changes
            # ------------------------------------------------

            column = candidate.get(
                "column_assignment"
            )

            if column in {
                "left",
                "middle",
                "right",
            }:
                safe[
                    "column_assignment"
                ] = column

            priority = candidate.get(
                "vertical_priority"
            )

            if priority in {
                "top",
                "middle",
                "bottom",
            }:
                safe[
                    "vertical_priority"
                ] = priority

            # ------------------------------------------------
            # Section title is immutable.
            # ------------------------------------------------

            if (
                "section_title"
                in candidate
                and candidate.get(
                    "section_title"
                )
                != original.get(
                    "section_title"
                )
            ):
                report[
                    "title_rewrites_blocked"
                ] += 1

            # ------------------------------------------------
            # Claim-level pruning
            #
            # The LLM may select claim IDs, but it can never
            # supply replacement claim text.
            # ------------------------------------------------

            original_claim_ids = (
                original.get(
                    "claim_ids",
                    [],
                )
            )

            original_texts = (
                original.get(
                    "text_content",
                    [],
                )
            )

            if isinstance(
                original_texts,
                str,
            ):
                original_texts = [
                    original_texts
                ]

            claim_text_map = {}

            if (
                isinstance(
                    original_claim_ids,
                    list,
                )
                and len(
                    original_claim_ids
                )
                == len(
                    original_texts
                )
            ):
                claim_text_map = {
                    claim_id: claim_text
                    for (
                        claim_id,
                        claim_text,
                    )
                    in zip(
                        original_claim_ids,
                        original_texts,
                    )
                }

            requested_claim_ids = (
                candidate.get(
                    "claim_ids"
                )
            )

            if (
                claim_text_map
                and isinstance(
                    requested_claim_ids,
                    list,
                )
            ):
                selected_claim_ids = []

                for claim_id in (
                    requested_claim_ids
                ):
                    if (
                        claim_id
                        in claim_text_map
                    ):
                        if (
                            claim_id
                            not in selected_claim_ids
                        ):
                            selected_claim_ids.append(
                                claim_id
                            )
                    else:
                        report[
                            "invalid_claim_ids_removed"
                        ].append(
                            claim_id
                        )

                # If Balancer returns an empty/invalid subset,
                # keep original verified claims.
                if selected_claim_ids:
                    safe[
                        "claim_ids"
                    ] = (
                        selected_claim_ids
                    )

                    safe[
                        "text_content"
                    ] = [
                        claim_text_map[
                            claim_id
                        ]
                        for claim_id
                        in selected_claim_ids
                    ]

                    if (
                        selected_claim_ids
                        != original_claim_ids
                    ):
                        report[
                            "claim_subsets_applied"
                        ] += 1

            # ------------------------------------------------
            # Detect attempted text rewrite.
            #
            # It is intentionally ignored.
            # ------------------------------------------------

            if (
                "text_content"
                in candidate
            ):
                candidate_text = (
                    candidate.get(
                        "text_content"
                    )
                )

                if (
                    candidate_text
                    != safe.get(
                        "text_content"
                    )
                ):
                    report[
                        "text_rewrites_blocked"
                    ] += 1

            # ------------------------------------------------
            # Visuals
            #
            # A visual may only remain if GroundedCurator had
            # already approved it for this same section.
            # ------------------------------------------------

            original_visuals = (
                original.get(
                    "visual_assets",
                    [],
                )
            )

            original_visual_map = {
                visual.get(
                    "visual_id"
                ): visual
                for visual
                in original_visuals
                if isinstance(
                    visual,
                    dict,
                )
                and visual.get(
                    "visual_id"
                )
            }

            requested_visuals = (
                candidate.get(
                    "visual_assets"
                )
            )

            if isinstance(
                requested_visuals,
                list,
            ):
                safe_visuals = []

                for visual in (
                    requested_visuals
                ):
                    if not isinstance(
                        visual,
                        dict,
                    ):
                        continue

                    visual_id = (
                        visual.get(
                            "visual_id"
                        )
                    )

                    if (
                        visual_id
                        in original_visual_map
                    ):
                        safe_visuals.append(
                            deepcopy(
                                original_visual_map[
                                    visual_id
                                ]
                            )
                        )

                    elif visual_id:
                        report[
                            "unapproved_visuals_removed"
                        ].append(
                            visual_id
                        )

                safe[
                    "visual_assets"
                ] = safe_visuals

            safe_sections.append(
                safe
            )

        # Fail closed.
        if not safe_sections:
            report[
                "fallback_to_original"
            ] = True

            safe_sections = deepcopy(
                original_sections
            )

        report[
            "safe_sections_output"
        ] = len(
            safe_sections
        )

        safe_plan = {
            key: deepcopy(
                value
            )
            for key, value
            in original_plan.items()
            if key != "sections"
        }

        safe_plan[
            "sections"
        ] = safe_sections

        return {
            "spatial_content_plan": (
                safe_plan
            )
        }, report

    def _validate_story_board(
        self,
        story_board: Dict,
    ) -> bool:
        """Validate minimum story-board structure."""

        if not isinstance(
            story_board,
            dict,
        ):
            return False

        scp = story_board.get(
            "spatial_content_plan"
        )

        if not isinstance(
            scp,
            dict,
        ):
            return False

        sections = scp.get(
            "sections"
        )

        if not isinstance(
            sections,
            list,
        ):
            return False

        if not sections:
            return False

        seen_ids = set()

        for section in sections:
            if section is None:
                log_agent_error(
                    self.name,
                    "null section found",
                )
                return False

            if not isinstance(
                section,
                dict,
            ):
                log_agent_error(
                    self.name,
                    (
                        "invalid section type: "
                        f"{type(section)}"
                    ),
                )
                return False

            section_id = section.get(
                "section_id"
            )

            if not section_id:
                log_agent_error(
                    self.name,
                    "section_id missing",
                )
                return False

            if (
                section_id
                in seen_ids
            ):
                log_agent_error(
                    self.name,
                    (
                        "duplicate section_id: "
                        f"{section_id}"
                    ),
                )
                return False

            seen_ids.add(
                section_id
            )

            column = section.get(
                "column_assignment"
            )

            if column not in {
                "left",
                "middle",
                "right",
            }:
                log_agent_error(
                    self.name,
                    (
                        "invalid column_assignment "
                        f"for {section_id}: "
                        f"{column}"
                    ),
                )
                return False

        return True

    def _extract_decisions(
        self,
        response_content: str,
    ) -> Dict:
        """Extract optimization diagnostics."""

        decisions = {
            "text_adjustments": [],
            "section_additions": [],
            "section_removals": [],
            "optimizations": [],
        }

        content_patterns = [
            "expanded text",
            "added detail",
            "enhanced content",
            "increased content",
            "reduced text",
            "shortened",
            "condensed content",
            "decreased content",
        ]

        addition_patterns = [
            "added section",
            "included section",
            "new section",
        ]

        removal_patterns = [
            "removed section",
            "deleted section",
            "eliminated section",
        ]

        optimization_patterns = [
            "within column",
            "column optimization",
            "adjusted in",
            "optimized in",
        ]

        for line in (
            response_content.split(
                "\n"
            )
        ):
            line_lower = (
                line.lower()
            )

            if any(
                pattern in line_lower
                for pattern
                in content_patterns
            ):
                decisions[
                    "text_adjustments"
                ].append(
                    line.strip()
                )

            elif any(
                pattern in line_lower
                for pattern
                in addition_patterns
            ):
                decisions[
                    "section_additions"
                ].append(
                    line.strip()
                )

            elif any(
                pattern in line_lower
                for pattern
                in removal_patterns
            ):
                decisions[
                    "section_removals"
                ].append(
                    line.strip()
                )

            elif any(
                pattern in line_lower
                for pattern
                in optimization_patterns
            ):
                decisions[
                    "optimizations"
                ].append(
                    line.strip()
                )

        return decisions


def balancer_agent_node(
    state: PosterState,
) -> Dict[str, Any]:
    """Balancer node for LangGraph."""

    try:
        agent = BalancerAgent()

        result = agent(
            state.get(
                "initial_layout_data"
            ),
            state.get(
                "column_analysis"
            ),
            state,
        )

        state["tokens"].add_text(
            result.get(
                "input_tokens",
                0,
            ),
            result.get(
                "output_tokens",
                0,
            ),
        )

        return {
            **state,
            "optimized_story_board": result[
                "optimized_story_board"
            ],
            "balancer_decisions": result[
                "balancer_decisions"
            ],
            "current_agent": (
                "balancer_agent"
            ),
        }

    except Exception as exc:
        log_agent_error(
            "balancer_agent",
            f"error: {exc}",
        )

        return {
            **state,
            "errors": (
                state.get(
                    "errors",
                    [],
                )
                + [
                    f"balancer_agent: {exc}"
                ]
            ),
        }
