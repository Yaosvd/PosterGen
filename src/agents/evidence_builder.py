"""Grounded evidence extraction from parsed paper sections."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.evidence_utils import normalize_space
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


class EvidenceBuilder:
    def __init__(self):
        self.name = "evidence_builder"
        self.prompt = load_prompt(
            "config/prompts/extract_evidence.txt"
        )

    def __call__(
        self,
        state: PosterState,
    ) -> PosterState:
        log_agent_info(
            self.name,
            "building grounded evidence bank",
        )

        try:
            sections = (
                state.get("section_chunks")
                or state.get(
                    "structured_sections",
                    {},
                ).get("paper_sections", [])
            )

            if not sections:
                raise ValueError(
                    "no parsed sections available"
                )

            config = apply_agent_policy(
                state["text_model"],
                self.name,
            )

            agent = LangGraphAgent(
                (
                    "You extract scientific evidence "
                    "without adding unsupported claims."
                ),
                config,
                state,
                self.name,
            )

            items: List[Dict[str, Any]] = []
            entity_set = set()

            for section_index, section in enumerate(
                sections
            ):
                section_name = str(
                    section.get(
                        "section_name",
                        f"Section {section_index + 1}",
                    )
                )

                section_type = str(
                    section.get(
                        "section_type",
                        "other",
                    )
                )

                section_content = str(
                    section.get(
                        "content",
                        "",
                    )
                ).strip()

                if not section_content:
                    continue

                prompt = Template(
                    self.prompt
                ).render(
                    section_name=section_name,
                    section_type=section_type,
                    section_content=section_content,
                )

                try:
                    agent.reset()
                    response = agent.step(prompt)

                    state["tokens"].add_text(
                        int(response.input_tokens),
                        int(response.output_tokens),
                    )

                    result = extract_json(
                        response.content
                    )

                    evidence_list = result.get(
                        "evidence",
                        [],
                    )

                    if not isinstance(
                        evidence_list,
                        list,
                    ):
                        raise ValueError(
                            "evidence must be a list"
                        )

                    normalized_source = normalize_space(
                        section_content
                    )

                    for raw_item in evidence_list:
                        if not isinstance(
                            raw_item,
                            dict,
                        ):
                            continue

                        claim = normalize_space(
                            raw_item.get(
                                "claim",
                                "",
                            )
                        )

                        excerpt = normalize_space(
                            raw_item.get(
                                "source_excerpt",
                                "",
                            )
                        )

                        if not claim or not excerpt:
                            continue

                        # Critical grounding rule:
                        # evidence excerpt must actually exist
                        # in the source section.
                        if excerpt not in normalized_source:
                            log_agent_warning(
                                self.name,
                                (
                                    "discarding evidence with "
                                    "non-verbatim source excerpt: "
                                    f"{section_name}"
                                ),
                            )
                            continue

                        metric = raw_item.get(
                            "metric",
                            {},
                        )

                        if not isinstance(
                            metric,
                            dict,
                        ):
                            metric = {}

                        direction = metric.get(
                            "direction",
                            "unknown",
                        )

                        allowed_directions = {
                            "higher_is_better",
                            "lower_is_better",
                            "neutral",
                            "unknown",
                        }

                        if (
                            direction
                            not in allowed_directions
                        ):
                            direction = "unknown"

                        semantics_excerpt = (
                            normalize_space(
                                raw_item.get(
                                    "metric_semantics_source_excerpt",
                                    "",
                                )
                            )
                        )

                        (
                            metric,
                            semantics_excerpt,
                        ) = self._sanitize_metric_semantics(
                            metric=metric,
                            semantics_excerpt=semantics_excerpt,
                            normalized_source=normalized_source,
                        )

                        entities = raw_item.get(
                            "entities",
                            [],
                        )

                        if not isinstance(
                            entities,
                            list,
                        ):
                            entities = []

                        entities = [
                            normalize_space(x)
                            for x in entities
                            if normalize_space(x)
                        ]

                        entity_set.update(
                            entities
                        )

                        numbers = raw_item.get(
                            "numbers",
                            [],
                        )

                        if not isinstance(
                            numbers,
                            list,
                        ):
                            numbers = []

                        evidence_id = (
                            f"ev_{len(items) + 1:04d}"
                        )

                        item = {
                            "evidence_id": evidence_id,
                            "claim": claim,
                            "claim_type": str(
                                raw_item.get(
                                    "claim_type",
                                    "background",
                                )
                            ),
                            "source_excerpt": excerpt,
                            "entities": entities,
                            "numbers": [
                                str(x)
                                for x in numbers
                            ],
                            "metric": metric,
                            "metric_semantics_source_excerpt": (
                                semantics_excerpt
                            ),
                            "confidence": float(
                                raw_item.get(
                                    "confidence",
                                    0.5,
                                )
                            ),
                            "source": {
                                "section_id": section.get(
                                    "section_id"
                                ),
                                "section_name": (
                                    section_name
                                ),
                                "section_type": (
                                    section_type
                                ),
                                "chunk_index": section.get(
                                    "chunk_index",
                                    0,
                                ),
                                "page": section.get(
                                    "page"
                                ),
                            },
                        }

                        items.append(item)

                except Exception as exc:
                    log_agent_warning(
                        self.name,
                        (
                            f"section extraction failed "
                            f"for {section_name}: {exc}"
                        ),
                    )

            if not items:
                raise ValueError(
                    "evidence extraction produced zero grounded items"
                )

            evidence_bank = {
                "version": 1,
                "items": items,
            }

            state["evidence_bank"] = (
                evidence_bank
            )

            state["academic_entities"] = {
                "entities": sorted(
                    entity_set,
                    key=str.lower,
                )
            }

            self._save_json(
                state,
                "evidence_bank.json",
                evidence_bank,
            )

            self._save_json(
                state,
                "academic_entities.json",
                state["academic_entities"],
            )

            state["current_agent"] = (
                self.name
            )

            log_agent_success(
                self.name,
                (
                    f"built evidence bank "
                    f"with {len(items)} items"
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
    def _sanitize_metric_semantics(
        metric: Dict[str, Any],
        semantics_excerpt: str,
        normalized_source: str,
    ):
        """
        Make metric-direction metadata deterministic and grounded.

        Scientific metric semantics must never depend on generic
        model knowledge such as:

            "typically lower is better"
            "generally higher is preferred"

        Rules:
        1. A non-unknown direction requires a supporting verbatim
           excerpt from the source section.
        2. If direction is unknown, no directional semantics excerpt
           is retained.
        3. Free-form LLM interpretation is never trusted for metric
           optimization direction. It is replaced with deterministic
           metadata derived only from the validated direction.
        """

        if not isinstance(
            metric,
            dict,
        ):
            metric = {}

        # Do not mutate the raw LLM object in-place.
        metric = dict(
            metric
        )

        direction = str(
            metric.get(
                "direction",
                "unknown",
            )
        ).strip()

        allowed_directions = {
            "higher_is_better",
            "lower_is_better",
            "neutral",
            "unknown",
        }

        if (
            direction
            not in allowed_directions
        ):
            direction = "unknown"

        semantics_excerpt = (
            normalize_space(
                semantics_excerpt
            )
        )

        semantics_supported = bool(
            semantics_excerpt
            and semantics_excerpt
            in normalized_source
        )

        # Any claimed direction must have an actual source excerpt.
        if (
            direction != "unknown"
            and not semantics_supported
        ):
            direction = "unknown"

        # ----------------------------------------------------
        # Deterministic interpretation.
        #
        # Never preserve the LLM's free-form interpretation,
        # because it may contain unsupported generic knowledge.
        # ----------------------------------------------------

        if direction == "unknown":
            semantics_excerpt = ""

            interpretation = (
                "The source does not explicitly define "
                "whether higher or lower values are "
                "preferable in this context."
            )

        elif direction == "higher_is_better":
            interpretation = (
                "The source explicitly supports higher "
                "values as preferable in this context."
            )

        elif direction == "lower_is_better":
            interpretation = (
                "The source explicitly supports lower "
                "values as preferable in this context."
            )

        else:
            interpretation = (
                "The source explicitly treats this metric "
                "as non-directional in this context."
            )

        metric[
            "direction"
        ] = direction

        metric[
            "interpretation"
        ] = interpretation

        return (
            metric,
            semantics_excerpt,
        )

    @staticmethod
    def _save_json(
        state: PosterState,
        filename: str,
        data: Dict[str, Any],
    ) -> None:
        content_dir = (
            Path(state["output_dir"])
            / "content"
        )

        content_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = content_dir / filename

        with path.open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
            )


evidence_builder = EvidenceBuilder()


def evidence_builder_node(
    state: PosterState,
) -> PosterState:
    return evidence_builder(state)
