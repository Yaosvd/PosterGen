"""Grounded poster curation.

The LLM may arrange verified claims, but cannot rewrite them.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

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
    log_agent_warning,
)


class GroundedCurator:
    def __init__(self):
        self.name = "grounded_curator"
        self.prompt = load_prompt(
            "config/prompts/grounded_curator.txt"
        )

    def __call__(
        self,
        state: PosterState,
    ) -> PosterState:
        log_agent_info(
            self.name,
            "arranging verified claims",
        )

        try:
            verified_claims = state.get(
                "verified_claims"
            )

            narrative_plan = state.get(
                "narrative_plan"
            )

            if not verified_claims:
                raise ValueError(
                    "missing verified_claims"
                )

            if not narrative_plan:
                raise ValueError(
                    "missing narrative_plan"
                )

            claim_index = {
                claim["claim_id"]: claim
                for claim in verified_claims.get(
                    "claims",
                    [],
                )
                if claim.get("claim_id")
            }

            if not claim_index:
                raise ValueError(
                    "verified claim index is empty"
                )

            classified_visuals = (
                state.get(
                    "classified_visuals"
                )
                or {}
            )

            images = state.get(
                "images"
            ) or {}

            tables = state.get(
                "tables"
            ) or {}

            config = apply_agent_policy(
                state["text_model"],
                "curator",
            )

            agent = LangGraphAgent(
                (
                    "You arrange verified academic "
                    "content without changing it."
                ),
                config,
                state,
                "grounded_curator",
            )

            prompt = Template(
                self.prompt
            ).render(
                narrative_plan=json.dumps(
                    narrative_plan,
                    ensure_ascii=False,
                    indent=2,
                ),
                verified_claims=json.dumps(
                    verified_claims,
                    ensure_ascii=False,
                    indent=2,
                ),
                classified_visuals=json.dumps(
                    classified_visuals,
                    ensure_ascii=False,
                    indent=2,
                ),
                available_images=json.dumps(
                    {
                        f"figure_{key}": {
                            "caption": value.get(
                                "caption",
                                "",
                            ),
                            "aspect": value.get(
                                "aspect",
                                1.0,
                            ),
                        }
                        for key, value
                        in images.items()
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                available_tables=json.dumps(
                    {
                        f"table_{key}": {
                            "caption": value.get(
                                "caption",
                                "",
                            ),
                            "aspect": value.get(
                                "aspect",
                                1.0,
                            ),
                        }
                        for key, value
                        in tables.items()
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            board = None

            try:
                agent.reset()
                response = agent.step(prompt)

                state["tokens"].add_text(
                    int(response.input_tokens),
                    int(response.output_tokens),
                )

                raw_board = extract_json(
                    response.content
                )

                board = self._materialize(
                    raw_board,
                    claim_index,
                    images,
                    tables,
                )

            except Exception as exc:
                log_agent_warning(
                    self.name,
                    (
                        "LLM curation failed; "
                        f"using deterministic fallback: {exc}"
                    ),
                )

            if not board:
                board = (
                    self._deterministic_board(
                        narrative_plan,
                        claim_index,
                    )
                )

            state["story_board"] = board
            state["current_agent"] = self.name

            self._save(
                state,
                board,
            )

            sections = board.get(
                "spatial_content_plan",
                {},
            ).get(
                "sections",
                [],
            )

            log_agent_success(
                self.name,
                (
                    "created grounded story board "
                    f"with {len(sections)} sections"
                ),
            )

        except Exception as exc:
            log_agent_error(
                self.name,
                f"failed: {exc}",
            )

            state["errors"].append(
                f"{self.name}: {exc}"
            )

        return state

    @staticmethod
    def _valid_visual_ids(
        images: Dict[str, Any],
        tables: Dict[str, Any],
    ) -> set:
        return {
            *{
                f"figure_{key}"
                for key in images
            },
            *{
                f"table_{key}"
                for key in tables
            },
        }

    def _materialize(
        self,
        raw_board: Dict[str, Any],
        claim_index: Dict[str, Dict[str, Any]],
        images: Dict[str, Any],
        tables: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        if not isinstance(
            raw_board,
            dict,
        ):
            return None

        plan = raw_board.get(
            "spatial_content_plan"
        )

        if not isinstance(
            plan,
            dict,
        ):
            return None

        raw_sections = plan.get(
            "sections",
            [],
        )

        if not isinstance(
            raw_sections,
            list,
        ):
            return None

        valid_visuals = self._valid_visual_ids(
            images,
            tables,
        )

        used_claims = set()
        sections = []

        valid_columns = {
            "left",
            "middle",
            "right",
        }

        valid_priorities = {
            "top",
            "middle",
            "bottom",
        }

        for index, raw_section in enumerate(
            raw_sections
        ):
            if not isinstance(
                raw_section,
                dict,
            ):
                continue

            claim_ids = []

            for claim_id in raw_section.get(
                "claim_ids",
                [],
            ):
                if claim_id not in claim_index:
                    continue

                if claim_id in used_claims:
                    continue

                used_claims.add(claim_id)
                claim_ids.append(claim_id)

            if not claim_ids:
                continue

            column = raw_section.get(
                "column_assignment",
                "left",
            )

            if column not in valid_columns:
                column = "left"

            priority = raw_section.get(
                "vertical_priority",
                "middle",
            )

            if priority not in valid_priorities:
                priority = "middle"

            visual_assets = []

            for visual in raw_section.get(
                "visual_assets",
                [],
            ):
                if not isinstance(
                    visual,
                    dict,
                ):
                    continue

                visual_id = visual.get(
                    "visual_id"
                )

                if visual_id in valid_visuals:
                    visual_assets.append(
                        {
                            "visual_id": visual_id
                        }
                    )

            title = str(
                raw_section.get(
                    "section_title",
                    f"Section {index + 1}",
                )
            ).strip()

            title_words = title.split()

            if len(title_words) > 5:
                title = " ".join(
                    title_words[:5]
                )

            sections.append(
                {
                    "section_id": str(
                        raw_section.get(
                            "section_id",
                            f"sec_{index + 1}",
                        )
                    ),
                    "section_title": (
                        title
                    ),
                    "column_assignment": (
                        column
                    ),
                    "vertical_priority": (
                        priority
                    ),
                    # CRITICAL:
                    # text comes directly from
                    # verified claims.
                    "text_content": [
                        claim_index[
                            claim_id
                        ]["text"]
                        for claim_id
                        in claim_ids
                    ],
                    "claim_ids": (
                        claim_ids
                    ),
                    "visual_assets": (
                        visual_assets
                    ),
                }
            )

        if not sections:
            return None

        # Include verified claims the LLM
        # accidentally omitted.
        missing_claim_ids = [
            claim_id
            for claim_id
            in claim_index
            if claim_id
            not in used_claims
        ]

        for claim_id in missing_claim_ids:
            target = min(
                sections,
                key=lambda section: len(
                    section["text_content"]
                ),
            )

            target["claim_ids"].append(
                claim_id
            )

            target["text_content"].append(
                claim_index[claim_id]["text"]
            )

        return {
            "spatial_content_plan": {
                "sections": sections
            }
        }

    @staticmethod
    def _deterministic_board(
        narrative_plan: Dict[str, Any],
        claim_index: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        sections = []

        positions = [
            ("left", "top"),
            ("left", "bottom"),
            ("middle", "top"),
            ("middle", "bottom"),
            ("right", "top"),
            ("right", "bottom"),
            ("right", "middle"),
            ("middle", "middle"),
        ]

        used_claims = set()

        for plan_section in narrative_plan.get(
            "sections",
            [],
        ):
            section_id = plan_section.get(
                "section_id"
            )

            matching = [
                claim
                for claim in claim_index.values()
                if claim.get(
                    "section_id"
                ) == section_id
                and claim["claim_id"]
                not in used_claims
            ]

            if not matching:
                continue

            position = positions[
                len(sections)
                % len(positions)
            ]

            claim_ids = [
                claim["claim_id"]
                for claim in matching
            ]

            used_claims.update(
                claim_ids
            )

            title = str(
                plan_section.get(
                    "title_intent",
                    "Research Findings",
                )
            )

            if len(title.split()) > 5:
                title = " ".join(
                    title.split()[:5]
                )

            sections.append(
                {
                    "section_id": (
                        section_id
                        or f"sec_{len(sections) + 1}"
                    ),
                    "section_title": title,
                    "column_assignment": (
                        position[0]
                    ),
                    "vertical_priority": (
                        position[1]
                    ),
                    "claim_ids": claim_ids,
                    "text_content": [
                        claim["text"]
                        for claim in matching
                    ],
                    "visual_assets": [],
                }
            )

        if not sections:
            raise ValueError(
                "unable to construct grounded story board"
            )

        return {
            "spatial_content_plan": {
                "sections": sections
            }
        }

    @staticmethod
    def _save(
        state: PosterState,
        data: Dict[str, Any],
    ) -> None:
        path = (
            Path(state["output_dir"])
            / "content"
            / "story_board.json"
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


grounded_curator = GroundedCurator()


def grounded_curator_node(
    state: PosterState,
) -> PosterState:
    return grounded_curator(state)
