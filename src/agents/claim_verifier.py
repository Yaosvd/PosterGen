"""Rule-based and LLM-based scientific claim verification."""

import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.evidence_utils import (
    evidence_by_id,
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


class ClaimVerifier:
    """Verify poster claims against their referenced evidence."""

    def __init__(self):
        self.name = "claim_verifier"
        self.prompt = load_prompt(
            "config/prompts/verify_claims.txt"
        )

    def __call__(
        self,
        state: PosterState,
    ) -> PosterState:
        log_agent_info(
            self.name,
            "verifying poster claims",
        )

        try:
            evidence_bank = state.get(
                "evidence_bank"
            )
            poster_claims = state.get(
                "poster_claims"
            )

            if not evidence_bank:
                raise ValueError(
                    "missing evidence_bank"
                )

            if not poster_claims:
                raise ValueError(
                    "missing poster_claims"
                )

            evidence_index = evidence_by_id(
                evidence_bank
            )

            if not evidence_index:
                raise ValueError(
                    "evidence bank contains no valid items"
                )

            config = apply_agent_policy(
                state["text_model"],
                self.name,
            )

            agent = LangGraphAgent(
                (
                    "You verify academic poster claims "
                    "strictly against supplied paper evidence."
                ),
                config,
                state,
                self.name,
            )

            verified: List[
                Dict[str, Any]
            ] = []

            details: List[
                Dict[str, Any]
            ] = []

            claims = poster_claims.get(
                "claims",
                [],
            )

            if not isinstance(
                claims,
                list,
            ):
                raise ValueError(
                    "poster_claims.claims must be a list"
                )

            for claim in claims:
                if not isinstance(
                    claim,
                    dict,
                ):
                    continue

                claim_id = claim.get(
                    "claim_id"
                )

                text = str(
                    claim.get(
                        "text",
                        "",
                    )
                ).strip()

                evidence_ids = (
                    valid_evidence_ids(
                        claim.get(
                            "evidence_ids",
                            [],
                        ),
                        evidence_index,
                    )
                )

                # ----------------------------------------
                # Gate 1: claim must have valid evidence.
                # ----------------------------------------

                if (
                    not text
                    or not evidence_ids
                ):
                    details.append(
                        {
                            "claim_id": claim_id,
                            "status": "rejected",
                            "error_types": [
                                "unsupported_claim"
                            ],
                            "reason": (
                                "Claim has no text "
                                "or no valid evidence reference."
                            ),
                        }
                    )
                    continue

                # ----------------------------------------
                # Gate 2: deterministic number checking.
                #
                # The verifier LLM does NOT get an
                # opportunity to approve a number that
                # cannot be found in cited evidence.
                # ----------------------------------------

                (
                    numbers_ok,
                    unsupported_numbers,
                ) = validate_claim_numbers(
                    text,
                    evidence_ids,
                    evidence_index,
                )

                if not numbers_ok:
                    details.append(
                        {
                            "claim_id": claim_id,
                            "status": "rejected",
                            "error_types": [
                                "numeric_mismatch"
                            ],
                            "reason": (
                                "Claim contains numerical "
                                "values absent from cited "
                                "evidence: "
                                f"{unsupported_numbers}"
                            ),
                        }
                    )
                    continue

                evidence = [
                    evidence_index[
                        evidence_id
                    ]
                    for evidence_id
                    in evidence_ids
                ]

                prompt = Template(
                    self.prompt
                ).render(
                    claim=json.dumps(
                        claim,
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

                    response = agent.step(
                        prompt
                    )

                    state["tokens"].add_text(
                        int(
                            response.input_tokens
                        ),
                        int(
                            response.output_tokens
                        ),
                    )

                    result = extract_json(
                        response.content
                    )

                    if not isinstance(
                        result,
                        dict,
                    ):
                        raise ValueError(
                            "verifier response is not a JSON object"
                        )

                    # ------------------------------------
                    # Passed unchanged
                    # ------------------------------------

                    if (
                        result.get(
                            "supported"
                        )
                        is True
                    ):
                        accepted = dict(
                            claim
                        )
                        accepted[
                            "verified"
                        ] = True
                        accepted[
                            "repaired"
                        ] = False

                        verified.append(
                            accepted
                        )

                        details.append(
                            {
                                "claim_id": claim_id,
                                "status": "passed",
                                "error_types": [],
                                "reason": str(
                                    result.get(
                                        "reason",
                                        "",
                                    )
                                ),
                            }
                        )

                        continue

                    # ------------------------------------
                    # Rejected by semantic verifier
                    # ------------------------------------

                    raw_error_types = (
                        result.get(
                            "error_types",
                            [],
                        )
                    )

                    if isinstance(
                        raw_error_types,
                        list,
                    ):
                        error_types = [
                            str(x)
                            for x
                            in raw_error_types
                        ]
                    else:
                        error_types = [
                            "unsupported_claim"
                        ]

                    corrected = str(
                        result.get(
                            "corrected_text",
                            "",
                        )
                    ).strip()

                    # ------------------------------------
                    # Optional safe repair
                    # ------------------------------------

                    if corrected:
                        (
                            corrected_ok,
                            corrected_bad,
                        ) = validate_claim_numbers(
                            corrected,
                            evidence_ids,
                            evidence_index,
                        )

                        if corrected_ok:
                            repaired_claim = (
                                dict(
                                    claim
                                )
                            )

                            repaired_claim[
                                "text"
                            ] = corrected

                            repaired_claim[
                                "verified"
                            ] = True

                            repaired_claim[
                                "repaired"
                            ] = True

                            repaired_claim[
                                "original_text"
                            ] = text

                            verified.append(
                                repaired_claim
                            )

                            details.append(
                                {
                                    "claim_id": (
                                        claim_id
                                    ),
                                    "status": (
                                        "repaired"
                                    ),
                                    "error_types": (
                                        error_types
                                    ),
                                    "reason": str(
                                        result.get(
                                            "reason",
                                            "",
                                        )
                                    ),
                                    "original_text": (
                                        text
                                    ),
                                    "corrected_text": (
                                        corrected
                                    ),
                                }
                            )

                            continue

                        log_agent_warning(
                            self.name,
                            (
                                "discarded verifier "
                                "correction because it "
                                "introduced unsupported "
                                "numbers: "
                                f"{corrected_bad}"
                            ),
                        )

                    # ------------------------------------
                    # Cannot safely repair
                    # ------------------------------------

                    details.append(
                        {
                            "claim_id": claim_id,
                            "status": "rejected",
                            "error_types": (
                                error_types
                            ),
                            "reason": str(
                                result.get(
                                    "reason",
                                    "",
                                )
                            ),
                        }
                    )

                except Exception as exc:
                    # Academic strict behavior:
                    # if verification itself fails,
                    # do not publish the claim.
                    log_agent_warning(
                        self.name,
                        (
                            f"verification failed "
                            f"for {claim_id}: {exc}"
                        ),
                    )

                    details.append(
                        {
                            "claim_id": claim_id,
                            "status": "rejected",
                            "error_types": [
                                "verification_failure"
                            ],
                            "reason": str(
                                exc
                            ),
                        }
                    )

            if not verified:
                raise ValueError(
                    "all poster claims were rejected"
                )

            total = len(
                claims
            )

            passed = sum(
                item.get(
                    "status"
                )
                == "passed"
                for item in details
            )

            repaired = sum(
                item.get(
                    "status"
                )
                == "repaired"
                for item in details
            )

            rejected = sum(
                item.get(
                    "status"
                )
                == "rejected"
                for item in details
            )

            verified_count = len(
                verified
            )

            report = {
                "summary": {
                    "total_claims": total,
                    "passed": passed,
                    "repaired": repaired,
                    "rejected": rejected,
                    "verified_output_claims": (
                        verified_count
                    ),
                },
                "grounded_claim_rate": (
                    verified_count / total
                    if total
                    else 0.0
                ),
                "details": details,
            }

            state[
                "verified_claims"
            ] = {
                "claims": verified
            }

            state[
                "verification_report"
            ] = report

            state[
                "verification_passed"
            ] = (
                verified_count > 0
            )

            self._save_json(
                state,
                "verified_claims.json",
                state[
                    "verified_claims"
                ],
            )

            self._save_json(
                state,
                "verification_report.json",
                report,
            )

            state[
                "current_agent"
            ] = self.name

            log_agent_success(
                self.name,
                (
                    "verification complete: "
                    f"{passed} passed, "
                    f"{repaired} repaired, "
                    f"{rejected} rejected"
                ),
            )

        except Exception as exc:
            log_agent_error(
                self.name,
                f"failed: {exc}",
            )

            state[
                "verification_passed"
            ] = False

            state[
                "errors"
            ].append(
                f"{self.name}: {exc}"
            )

        return state

    @staticmethod
    def _save_json(
        state: PosterState,
        filename: str,
        data: Dict[str, Any],
    ) -> None:
        content_dir = (
            Path(
                state["output_dir"]
            )
            / "content"
        )

        content_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = (
            content_dir
            / filename
        )

        path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


claim_verifier = ClaimVerifier()


def claim_verifier_node(
    state: PosterState,
) -> PosterState:
    return claim_verifier(
        state
    )
