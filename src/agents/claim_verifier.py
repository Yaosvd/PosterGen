"""Rule-based and LLM-based scientific claim verification."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.evidence_utils import (
    evidence_by_id,
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
                text = normalize_formula_multiplication(
                    text
                )

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

                # ----------------------------------------
                # Gate 3: cross-evidence consistency.
                #
                # A claim may be supported by its cited evidence
                # while conflicting with stronger evidence elsewhere
                # in the same paper.
                # ----------------------------------------
                conflict = (
                    self._cross_evidence_consistency_gate(
                        text,
                        evidence_ids,
                        evidence_index,
                    )
                )

                if conflict:
                    details.append(
                        {
                            "claim_id": claim_id,
                            "status": "rejected",
                            "error_types": [
                                "evidence_conflict"
                            ],
                            "reason": (
                                conflict["reason"]
                            ),
                            "conflicting_evidence_ids": (
                                conflict[
                                    "conflicting_evidence_ids"
                                ]
                            ),
                        }
                    )

                    log_agent_warning(
                        self.name,
                        (
                            f"rejected {claim_id}: "
                            "cross-evidence conflict "
                            f"{conflict['conflicting_evidence_ids']}"
                        ),
                    )

                    continue

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
                            "text"
                        ] = text
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
                    corrected = normalize_formula_multiplication(
                        corrected
                    )

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
                            corrected_conflict = (
                                self._cross_evidence_consistency_gate(
                                    corrected,
                                    evidence_ids,
                                    evidence_index,
                                )
                            )

                            if corrected_conflict:
                                details.append(
                                    {
                                        "claim_id": claim_id,
                                        "status": "rejected",
                                        "error_types": [
                                            "evidence_conflict"
                                        ],
                                        "reason": (
                                            corrected_conflict[
                                                "reason"
                                            ]
                                        ),
                                        "conflicting_evidence_ids": (
                                            corrected_conflict[
                                                "conflicting_evidence_ids"
                                            ]
                                        ),
                                        "original_text": text,
                                        "corrected_text": corrected,
                                    }
                                )

                                log_agent_warning(
                                    self.name,
                                    (
                                        "discarded verifier "
                                        f"correction for {claim_id}: "
                                        "cross-evidence conflict"
                                    ),
                                )

                                continue

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
    def _canonical_entity(
        value: str,
    ) -> str:
        """
        Normalize method names conservatively for pairwise
        comparison matching.

        Examples:
        DP-CutMixSL -> cutmix
        DP-CutMix   -> cutmix
        DP-MixSL    -> mix
        Vanilla Mixup -> mix
        """

        raw = str(
            value or ""
        ).lower()

        raw = (
            raw.replace(
                "rényi",
                "renyi",
            )
            .replace(
                "mixup",
                "mix",
            )
        )

        compact = re.sub(
            r"[^a-z0-9]+",
            "",
            raw,
        )

        for prefix in (
            "differentiallyprivate",
            "vanilla",
            "proposed",
            "dp",
        ):
            if (
                compact.startswith(prefix)
                and len(compact) > len(prefix) + 2
            ):
                compact = compact[
                    len(prefix):
                ]

        for suffix in (
            "counterpart",
            "algorithm",
            "framework",
            "method",
            "scheme",
        ):
            if (
                compact.endswith(suffix)
                and len(compact) > len(suffix) + 2
            ):
                compact = compact[
                    :-len(suffix)
                ]

        # Split-learning method suffix:
        # DP-CutMixSL -> CutMix
        # DP-MixSL    -> Mix
        if (
            compact.endswith("sl")
            and len(compact) > 4
        ):
            compact = compact[:-2]

        return compact

    @staticmethod
    def _is_metric_entity(
        value: str,
    ) -> bool:
        """Exclude obvious metric names from method pairs."""

        text = str(
            value or ""
        ).lower()

        metric_terms = (
            "rdp",
            "rényi",
            "renyi",
            "privacy budget",
            "privacy loss",
            "bound",
            "accuracy",
            "top-1",
            "top 1",
            "mse",
            "reconstruction loss",
            "iou",
            "f1",
            "precision",
            "recall",
            "robustness",
            "communication cost",
            "energy cost",
        )

        return any(
            term in text
            for term in metric_terms
        )

    @staticmethod
    def _metric_key(
        evidence: Dict[str, Any],
    ) -> str:
        """
        Produce a conservative metric family key.

        This intentionally collapses common surface forms such as
        'Rényi DP (RDP)', 'RDP bound', and 'RDP privacy budget'.
        """

        metric = evidence.get(
            "metric",
            {},
        )

        if isinstance(
            metric,
            dict,
        ):
            metric_name = str(
                metric.get(
                    "name",
                    "",
                )
            )
        else:
            metric_name = str(
                metric or ""
            )

        blob = " ".join(
            [
                metric_name,
                str(
                    evidence.get(
                        "claim",
                        "",
                    )
                ),
            ]
        ).lower()

        if (
            "rdp" in blob
            or "rényi" in blob
            or "renyi" in blob
        ):
            return "rdp"

        if (
            "mse" in blob
            or "mean squared error" in blob
        ):
            return "mse"

        if (
            "accuracy" in blob
            or "top-1" in blob
            or "top 1" in blob
        ):
            return "accuracy"

        if "iou" in blob:
            return "iou"

        if re.search(
            r"\bf1\b",
            blob,
        ):
            return "f1"

        normalized = re.sub(
            r"[^a-z0-9]+",
            " ",
            metric_name.lower(),
        )

        stopwords = {
            "metric",
            "score",
            "value",
            "result",
            "performance",
        }

        tokens = [
            token
            for token in normalized.split()
            if token not in stopwords
        ]

        return " ".join(tokens)

    @staticmethod
    def _comparison_operator(
        text: str,
    ):
        """
        Extract only explicit directional language.

        Returns one of:
        <, <=, >, >=
        """

        value = str(
            text or ""
        ).lower()

        if re.search(
            r"\bupper[\s-]*bound(?:ed)?\s+by\b",
            value,
        ):
            return "<="

        if re.search(
            r"\blower[\s-]*bound(?:ed)?\s+by\b",
            value,
        ):
            return ">="

        if re.search(
            r"\b("
            r"larger|greater|higher"
            r")\b",
            value,
        ):
            return ">"

        if re.search(
            r"\b("
            r"smaller|lower|tighter"
            r")\b",
            value,
        ):
            return "<"

        if re.search(
            r"\boutperform(?:s|ed|ing)?\b",
            value,
        ):
            return ">"

        return None

    def _relation_fact(
        self,
        evidence: Dict[str, Any],
        text_override: str = "",
    ):
        """
        Convert one explicit pairwise comparison into a normalized
        relation fact.

        Returns None when relation extraction is ambiguous.
        """

        entities = evidence.get(
            "entities",
            [],
        )

        if not isinstance(
            entities,
            list,
        ):
            return None

        method_entities = []

        for entity in entities:
            entity_text = str(
                entity or ""
            ).strip()

            if not entity_text:
                continue

            if self._is_metric_entity(
                entity_text
            ):
                continue

            canonical = (
                self._canonical_entity(
                    entity_text
                )
            )

            if not canonical:
                continue

            if (
                canonical
                not in [
                    item[0]
                    for item
                    in method_entities
                ]
            ):
                method_entities.append(
                    (
                        canonical,
                        entity_text,
                    )
                )

        # Conservative: only reason over a clear pair.
        if len(method_entities) != 2:
            return None

        relation_text = (
            text_override
            or str(
                evidence.get(
                    "claim",
                    "",
                )
            )
            or str(
                evidence.get(
                    "source_excerpt",
                    "",
                )
            )
        )

        operator = (
            self._comparison_operator(
                relation_text
            )
        )

        if not operator:
            return None

        lhs = method_entities[0][0]
        rhs = method_entities[1][0]

        if lhs == rhs:
            return None

        pair = tuple(
            sorted(
                (lhs, rhs)
            )
        )

        # Normalize direction relative to sorted pair.
        #
        # sign < 0 : pair[0] < pair[1]
        # sign > 0 : pair[0] > pair[1]
        if operator in (
            "<",
            "<=",
        ):
            lhs_vs_rhs = -1
        else:
            lhs_vs_rhs = 1

        if lhs == pair[0]:
            sign = lhs_vs_rhs
        else:
            sign = -lhs_vs_rhs

        return {
            "pair": pair,
            "sign": sign,
            "operator": operator,
            "lhs": lhs,
            "rhs": rhs,
            "metric": (
                self._metric_key(
                    evidence
                )
            ),
        }

    @staticmethod
    def _evidence_priority(
        evidence: Dict[str, Any],
    ) -> int:
        """
        Evidence specificity hierarchy.

        4: theorem / lemma / proposition / corollary
        3: explicit non-abstract comparison
        2: other non-abstract evidence
        1: abstract summary
        """

        source = evidence.get(
            "source",
            {},
        )

        if isinstance(
            source,
            dict,
        ):
            section_name = str(
                source.get(
                    "section_name",
                    "",
                )
            ).lower()
        else:
            section_name = ""

        blob = " ".join(
            [
                str(
                    evidence.get(
                        "claim",
                        "",
                    )
                ),
                str(
                    evidence.get(
                        "source_excerpt",
                        "",
                    )
                ),
            ]
        ).lower()

        if re.search(
            r"\b("
            r"theorem|lemma|proposition|corollary"
            r")\b",
            blob,
        ):
            return 4

        if "abstract" in section_name:
            return 1

        claim_type = str(
            evidence.get(
                "claim_type",
                "",
            )
        ).lower()

        if claim_type == "comparison":
            return 3

        return 2

    @staticmethod
    def _numeric_context(
        evidence: Dict[str, Any],
    ):
        """
        Extract explicit numeric literals to avoid comparing evidence
        that clearly refers to different numeric experimental settings.
        """

        blob = " ".join(
            [
                str(
                    evidence.get(
                        "claim",
                        "",
                    )
                ),
                str(
                    evidence.get(
                        "source_excerpt",
                        "",
                    )
                ),
            ]
        )

        return tuple(
            sorted(
                set(
                    re.findall(
                        r"(?<![A-Za-z])"
                        r"[-+]?"
                        r"(?:\d+\.\d+|\d+)"
                        r"(?:%|/255)?",
                        blob,
                    )
                )
            )
        )

    def _cross_evidence_consistency_gate(
        self,
        claim_text: str,
        evidence_ids: List[str],
        evidence_index: Dict[str, Dict[str, Any]],
    ):
        """
        Reject an explicit comparative claim when its cited relation
        conflicts with stronger, more specific evidence elsewhere in
        the paper.

        This is deliberately conservative. It does NOT attempt broad
        semantic contradiction detection.
        """

        cited_facts = []

        for evidence_id in evidence_ids:
            evidence = evidence_index.get(
                evidence_id
            )

            if not isinstance(
                evidence,
                dict,
            ):
                continue

            fact = self._relation_fact(
                evidence,
                text_override=claim_text,
            )

            if fact:
                cited_facts.append(
                    (
                        evidence_id,
                        evidence,
                        fact,
                    )
                )

        if not cited_facts:
            return None

        conflicts = []

        for (
            cited_id,
            cited_evidence,
            cited_fact,
        ) in cited_facts:

            cited_priority = (
                self._evidence_priority(
                    cited_evidence
                )
            )

            cited_numbers = (
                self._numeric_context(
                    cited_evidence
                )
            )

            for (
                other_id,
                other_evidence,
            ) in evidence_index.items():

                if other_id in evidence_ids:
                    continue

                if not isinstance(
                    other_evidence,
                    dict,
                ):
                    continue

                other_fact = (
                    self._relation_fact(
                        other_evidence
                    )
                )

                if not other_fact:
                    continue

                # Same metric family only.
                if (
                    not cited_fact["metric"]
                    or cited_fact["metric"]
                    != other_fact["metric"]
                ):
                    continue

                # Same method/entity pair only.
                if (
                    cited_fact["pair"]
                    != other_fact["pair"]
                ):
                    continue

                # Opposite direction only.
                if (
                    cited_fact["sign"]
                    == other_fact["sign"]
                ):
                    continue

                other_numbers = (
                    self._numeric_context(
                        other_evidence
                    )
                )

                # If both pieces of evidence clearly describe
                # different numeric settings, do not infer conflict.
                if (
                    cited_numbers
                    and other_numbers
                    and cited_numbers
                    != other_numbers
                ):
                    continue

                other_priority = (
                    self._evidence_priority(
                        other_evidence
                    )
                )

                # First version is intentionally asymmetric:
                # stronger evidence may invalidate weaker evidence,
                # but weaker summary wording cannot invalidate
                # stronger detailed evidence.
                if (
                    other_priority
                    <= cited_priority
                ):
                    continue

                conflicts.append(
                    {
                        "cited_id": cited_id,
                        "other_id": other_id,
                        "metric": (
                            cited_fact["metric"]
                        ),
                        "pair": list(
                            cited_fact["pair"]
                        ),
                        "cited_operator": (
                            cited_fact["operator"]
                        ),
                        "other_operator": (
                            other_fact["operator"]
                        ),
                        "cited_priority": (
                            cited_priority
                        ),
                        "other_priority": (
                            other_priority
                        ),
                    }
                )

        if not conflicts:
            return None

        conflicting_ids = sorted(
            {
                item["other_id"]
                for item in conflicts
            }
        )

        first = conflicts[0]

        return {
            "conflicting_evidence_ids": (
                conflicting_ids
            ),
            "reason": (
                "Cross-evidence conflict: the cited "
                "comparative relation for metric "
                f"'{first['metric']}' and entity pair "
                f"{first['pair']} is contradicted by "
                "stronger, more specific paper evidence "
                f"{conflicting_ids}."
            ),
            "conflicts": conflicts,
        }

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
