"""Write poster-ready claims while preserving evidence provenance."""

import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.evidence_utils import (
    contains_comparison_language,
    evidence_by_id,
    extract_numbers,
    normalize_formula_multiplication,
    valid_evidence_ids,
    validate_claim_numbers,
)
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


class ClaimWriter:
    def __init__(self):
        self.name = "claim_writer"
        self.prompt = load_prompt(
            "config/prompts/write_poster_claims.txt"
        )

    def __call__(
        self,
        state: PosterState,
    ) -> PosterState:
        log_agent_info(
            self.name,
            "writing evidence-grounded poster claims",
        )

        try:
            evidence_bank = state.get(
                "evidence_bank"
            )

            narrative_plan = state.get(
                "narrative_plan"
            )

            if not evidence_bank:
                raise ValueError(
                    "missing evidence_bank"
                )

            if not narrative_plan:
                raise ValueError(
                    "missing narrative_plan"
                )

            evidence_index = evidence_by_id(
                evidence_bank
            )

            config = apply_agent_policy(
                state["text_model"],
                self.name,
            )

            agent = LangGraphAgent(
                (
                    "You write concise scientific claims "
                    "strictly from supplied evidence."
                ),
                config,
                state,
                self.name,
            )

            claims: List[Dict[str, Any]] = []

            for section in narrative_plan.get(
                "sections",
                [],
            ):
                evidence_ids = (
                    valid_evidence_ids(
                        section.get(
                            "evidence_ids",
                            [],
                        ),
                        evidence_index,
                    )
                )

                evidence = [
                    evidence_index[evidence_id]
                    for evidence_id
                    in evidence_ids
                ]

                if not evidence:
                    continue

                prompt = Template(
                    self.prompt
                ).render(
                    section=json.dumps(
                        section,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    evidence=json.dumps(
                        evidence,
                        ensure_ascii=False,
                        indent=2,
                    ),
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

                    raw_claims = result.get(
                        "claims",
                        [],
                    )

                    if not isinstance(
                        raw_claims,
                        list,
                    ):
                        continue

                    for raw_claim in raw_claims:
                        if not isinstance(
                            raw_claim,
                            dict,
                        ):
                            continue

                        text = str(
                            raw_claim.get(
                                "text",
                                "",
                            )
                        ).strip()
                        text = normalize_formula_multiplication(
                            text
                        )

                        if not text:
                            continue

                        claim_evidence_ids = (
                            valid_evidence_ids(
                                raw_claim.get(
                                    "evidence_ids",
                                    [],
                                ),
                                evidence_index,
                            )
                        )

                        # Claim may only cite evidence
                        # assigned to this narrative section.
                        claim_evidence_ids = [
                            evidence_id
                            for evidence_id
                            in claim_evidence_ids
                            if evidence_id
                            in evidence_ids
                        ]

                        if not claim_evidence_ids:
                            continue

                        numbers_ok, unsupported = (
                            validate_claim_numbers(
                                text,
                                claim_evidence_ids,
                                evidence_index,
                            )
                        )

                        if not numbers_ok:
                            log_agent_warning(
                                self.name,
                                (
                                    "discarding claim with "
                                    "unsupported numbers: "
                                    f"{unsupported}"
                                ),
                            )
                            continue

                        claim_type = str(
                            raw_claim.get(
                                "claim_type",
                                "descriptive",
                            )
                        )

                        risk = str(
                            raw_claim.get(
                                "risk_level",
                                "low",
                            )
                        )

                        if (
                            extract_numbers(text)
                            or contains_comparison_language(
                                text
                            )
                        ):
                            risk = "high"

                        claims.append(
                            {
                                "claim_id": (
                                    f"pc_{len(claims) + 1:04d}"
                                ),
                                "section_id": section[
                                    "section_id"
                                ],
                                "text": text,
                                "evidence_ids": (
                                    claim_evidence_ids
                                ),
                                "claim_type": (
                                    claim_type
                                ),
                                "risk_level": risk,
                            }
                        )

                except Exception as exc:
                    log_agent_warning(
                        self.name,
                        (
                            "claim generation failed for "
                            f"{section.get('section_id')}: "
                            f"{exc}"
                        ),
                    )

            if not claims:
                raise ValueError(
                    "claim writer produced zero grounded claims"
                )

            result = {
                "claims": claims,
            }

            state["poster_claims"] = result

            self._save(
                state,
                "poster_claims.json",
                result,
            )

            state["current_agent"] = (
                self.name
            )

            log_agent_success(
                self.name,
                f"created {len(claims)} claims",
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
    def _save(
        state: PosterState,
        filename: str,
        data: Dict[str, Any],
    ) -> None:
        path = (
            Path(state["output_dir"])
            / "content"
            / filename
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


claim_writer = ClaimWriter()


def claim_writer_node(
    state: PosterState,
) -> PosterState:
    return claim_writer(state)
