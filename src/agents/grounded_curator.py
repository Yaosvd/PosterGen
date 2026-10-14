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
from utils.grounded_content import active_publishable_claims
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
        self.family_prompt = load_prompt(
            "config/prompts/grounded_curator_family.txt"
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
            # Fresh layouts receive one active wording per immutable root claim,
            # never the complete bank of alternative variants.
            verified_claims = active_publishable_claims(state)

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
            family_mode = state.get("generation_route") == "optimization_family"

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
                self.family_prompt if family_mode else self.prompt
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

            if state.get("iteration_context"):
                design_context = {
                    "generation_mode": state.get("iteration_context"),
                    "template_context": state.get("template_context") or [],
                    "global_design_context": state.get("global_design_context") or {},
                    "previous_critic_report": state.get("critic_report") or {},
                    "anti_fixation_rules": [
                        "Do not copy template coordinates exactly.",
                        "Treat templates as optional, applicability-bound inspiration.",
                        "When template_context is empty, create a genuinely independent layout assignment.",
                    ],
                }
                prompt += (
                    "\n\nITERATION DESIGN CONTEXT:\n"
                    + json.dumps(design_context, ensure_ascii=False, indent=2)
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
                    family_mode=family_mode,
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
                        family_mode=family_mode,
                    )
                )

            key_seed_status = "not_applicable"
            if family_mode:
                key_seed_status = self._seed_relevant_key_visual(
                    board, narrative_plan, classified_visuals,
                    self._valid_visual_ids(images, tables),
                )
            available_ids = self._valid_visual_ids(images, tables)
            curated_ids = {
                str(visual.get("visual_id"))
                for section in board.get("spatial_content_plan", {}).get("sections", [])
                for visual in section.get("visual_assets") or []
                if isinstance(visual, dict) and visual.get("visual_id")
            }
            state["visual_curation_report"] = {
                "schema_version": 1,
                "route": state.get("generation_route") or "standalone_classic",
                "available_visual_ids": sorted(available_ids),
                "curated_visual_ids": sorted(curated_ids),
                "uncurated_visual_ids": sorted(available_ids - curated_ids),
                "key_visual_id": classified_visuals.get("key_visual"),
                "key_seed_status": key_seed_status,
            }

            state["story_board"] = board
            state["current_agent"] = self.name

            self._save(
                state,
                board,
            )
            self._save_visual_report(state)

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
        *,
        family_mode: bool = False,
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
        used_visuals = set()
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
            if family_mode:
                # Compatibility-only field; the family solver ignores columns.
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

                if visual_id in valid_visuals and (
                    not family_mode or visual_id not in used_visuals
                ):
                    visual_assets.append(
                        {
                            "visual_id": visual_id
                        }
                    )
                    used_visuals.add(visual_id)

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
        *,
        family_mode: bool = False,
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
                        "left" if family_mode else position[0]
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
    def _seed_relevant_key_visual(
        board: Dict[str, Any], narrative_plan: Dict[str, Any],
        classified: Dict[str, Any], available_ids: set[str],
    ) -> str:
        """Offer one valid omitted anchor to the solver, never force placement."""

        key = classified.get("key_visual")
        if not isinstance(key, str) or key not in available_ids:
            return "no_valid_key"
        sections = board.get("spatial_content_plan", {}).get("sections", [])
        if any(key == visual.get("visual_id") for section in sections
               for visual in section.get("visual_assets") or []
               if isinstance(visual, dict)):
            return "already_curated"
        roles = {
            "problem_illustration": {"problem", "foundation"},
            "method_workflow": {"method", "theory"},
            "main_results": {"results", "evaluation"},
            "comparative_results": {"results", "evaluation"},
        }
        visual_role = next(
            (
                role for role in roles
                if isinstance(classified.get(role), list)
                and key in classified[role]
            ), None
        )
        if visual_role is None:
            return "no_matching_scientific_role"
        planned = {
            str(item.get("section_id")): str(item.get("narrative_role") or "").lower()
            for item in narrative_plan.get("sections", []) if isinstance(item, dict)
        }
        matches = [
            section for section in sections
            if planned.get(str(section.get("section_id"))) in roles[visual_role]
        ]
        if not matches:
            return "no_matching_verified_module"
        target = min(matches, key=lambda item: len(item.get("visual_assets") or []))
        target.setdefault("visual_assets", []).append({"visual_id": key})
        return "seeded_as_optional_candidate"

    @staticmethod
    def _save_visual_report(state: PosterState) -> None:
        path = Path(state["output_dir"]) / "content" / "visual_curation_report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state["visual_curation_report"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

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
