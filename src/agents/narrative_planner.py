"""Evidence-grounded poster narrative planning."""

import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.evidence_utils import evidence_by_id
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


class NarrativePlanner:
    def __init__(self):
        self.name = "narrative_planner"
        self.prompt = load_prompt(
            "config/prompts/plan_narrative.txt"
        )

    def __call__(
        self,
        state: PosterState,
    ) -> PosterState:
        log_agent_info(
            self.name,
            "planning grounded poster narrative",
        )

        try:
            evidence_bank = state.get(
                "evidence_bank"
            )

            if not evidence_bank:
                raise ValueError(
                    "missing evidence_bank"
                )

            evidence_index = evidence_by_id(
                evidence_bank
            )

            compact_items = []

            for item in evidence_bank.get(
                "items",
                [],
            ):
                compact_items.append(
                    {
                        "evidence_id": item[
                            "evidence_id"
                        ],
                        "claim": item.get(
                            "claim",
                            "",
                        ),
                        "claim_type": item.get(
                            "claim_type",
                            "",
                        ),
                        "entities": item.get(
                            "entities",
                            [],
                        ),
                        "numbers": item.get(
                            "numbers",
                            [],
                        ),
                        "metric": item.get(
                            "metric",
                            {},
                        ),
                        "source": item.get(
                            "source",
                            {},
                        ),
                    }
                )

            config = apply_agent_policy(
                state["text_model"],
                self.name,
            )

            agent = LangGraphAgent(
                (
                    "You organize verified academic "
                    "evidence into a poster narrative."
                ),
                config,
                state,
                self.name,
            )

            prompt = Template(
                self.prompt
            ).render(
                evidence_bank=json.dumps(
                    {
                        "items": compact_items
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )

            agent.reset()
            response = agent.step(prompt)

            state["tokens"].add_text(
                int(response.input_tokens),
                int(response.output_tokens),
            )

            result = extract_json(
                response.content
            )

            sections = result.get(
                "sections",
                [],
            )

            if not isinstance(
                sections,
                list,
            ):
                sections = []

            normalized_sections = []

            used_ids = set()

            for index, section in enumerate(
                sections
            ):
                if not isinstance(
                    section,
                    dict,
                ):
                    continue

                raw_ids = section.get(
                    "evidence_ids",
                    [],
                )

                if not isinstance(
                    raw_ids,
                    list,
                ):
                    continue

                valid_ids = [
                    evidence_id
                    for evidence_id in raw_ids
                    if evidence_id
                    in evidence_index
                ]

                valid_ids = list(
                    dict.fromkeys(valid_ids)
                )

                if not valid_ids:
                    continue

                used_ids.update(valid_ids)

                normalized_sections.append(
                    {
                        "section_id": (
                            f"poster_sec_"
                            f"{len(normalized_sections) + 1}"
                        ),
                        "title_intent": str(
                            section.get(
                                "title_intent",
                                "Research Findings",
                            )
                        ),
                        "evidence_ids": valid_ids,
                        "importance": int(
                            section.get(
                                "importance",
                                2,
                            )
                        ),
                        "narrative_role": str(
                            section.get(
                                "narrative_role",
                                "supporting",
                            )
                        ),
                    }
                )

            if not normalized_sections:
                normalized_sections = (
                    self._deterministic_fallback(
                        evidence_bank
                    )
                )

            narrative_plan = {
                "narrative_summary": str(
                    result.get(
                        "narrative_summary",
                        "",
                    )
                ),
                "sections": normalized_sections,
                "unused_evidence_ids": [
                    evidence_id
                    for evidence_id
                    in evidence_index
                    if evidence_id
                    not in used_ids
                ],
            }

            state["narrative_plan"] = (
                narrative_plan
            )

            self._save(
                state,
                narrative_plan,
            )

            state["current_agent"] = (
                self.name
            )

            log_agent_success(
                self.name,
                (
                    "created narrative with "
                    f"{len(normalized_sections)} "
                    "sections"
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
    def _deterministic_fallback(
        evidence_bank: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        groups = {
            "foundation": [],
            "problem": [],
            "method": [],
            "theory": [],
            "results": [],
            "conclusion": [],
        }

        mapping = {
            "background": "foundation",
            "problem": "problem",
            "method": "method",
            "definition": "method",
            "theory": "theory",
            "numeric_result": "results",
            "comparison": "results",
            "limitation": "conclusion",
            "conclusion": "conclusion",
        }

        for item in evidence_bank.get(
            "items",
            [],
        ):
            group = mapping.get(
                item.get("claim_type"),
                "results",
            )

            groups[group].append(
                item["evidence_id"]
            )

        titles = {
            "foundation": "Background",
            "problem": "Research Problem",
            "method": "Proposed Method",
            "theory": "Theory",
            "results": "Key Results",
            "conclusion": "Implications",
        }

        result = []

        for group, ids in groups.items():
            if not ids:
                continue

            result.append(
                {
                    "section_id": (
                        f"poster_sec_{len(result) + 1}"
                    ),
                    "title_intent": titles[group],
                    "evidence_ids": ids[:6],
                    "importance": (
                        1
                        if group
                        in {
                            "method",
                            "results",
                        }
                        else 2
                    ),
                    "narrative_role": group,
                }
            )

        return result

    @staticmethod
    def _save(
        state: PosterState,
        data: Dict[str, Any],
    ) -> None:
        path = (
            Path(state["output_dir"])
            / "content"
            / "narrative_plan.json"
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


narrative_planner = NarrativePlanner()


def narrative_planner_node(
    state: PosterState,
) -> PosterState:
    return narrative_planner(state)
