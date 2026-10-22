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
        self.family_prompt = load_prompt('config/prompts/write_sample_claims.txt')
        self.module_prompt = load_prompt('config/prompts/write_sample_modules.txt')

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
            module_plan = state.get('sample_module_plan') if state.get('generation_route') == 'optimization_family' else None
            sections = (module_plan['modules'] if module_plan else narrative_plan.get('sections', []))
            unit_index = {u['section_id']: u for u in narrative_plan.get('sections', [])}

            for section in sections:
                module_start = len(claims)
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
                    self.module_prompt if module_plan else
                    self.family_prompt if state.get('generation_route') == 'optimization_family' else self.prompt
                ).render(
                    family_mode=state.get('generation_route') == 'optimization_family',
                    narrative_summary=narrative_plan.get('narrative_summary', ''),
                    module_context=json.dumps([{'title': s.get('title'), 'writing_brief': s.get('writing_brief')}
                                               for s in sections], ensure_ascii=False) if module_plan else '',
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
                                "section_id": section.get('section_id', ''),
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
                        if module_plan:
                            item = claims[-1]
                            origins = [sid for sid in section['source_plan_unit_ids']
                                       if set(unit_index[sid]['evidence_ids']).intersection(claim_evidence_ids)]
                            item.update(body_contract='sample_body_v2', display_module_id=section['module_id'],
                                        source_plan_unit_ids=origins,
                                        section_id=origins[0] if len(origins) == 1 else '',
                                        required_evidence_ids=sorted(set(section['required_evidence_ids']) & set(claim_evidence_ids)),
                                        essential=raw_claim.get('essential') is True,
                                        discourse_kind=raw_claim.get('kind', ''),
                                        display_label=raw_claim.get('display_label', ''),
                                        step_index=raw_claim.get('step_index'),
                                        _item_id=raw_claim.get('item_id'),
                                        _requires=raw_claim.get('requires_item_ids') or [],
                                        _parent=raw_claim.get('parent_item_id'))
                    if module_plan:
                        body = claims[module_start:]
                        ids = [c['_item_id'] for c in body]
                        if not body or any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
                            raise ValueError('Module writer returned missing or duplicate item identities')
                        mapping = {c['_item_id']: c['claim_id'] for c in body}
                        for c in body:
                            refs = [*c['_requires'], *([c['_parent']] if c['_parent'] else [])]
                            if any(r not in mapping or r == c['_item_id'] for r in refs):
                                raise ValueError('Module writer returned foreign or self prerequisite')
                            c['requires_claim_ids'] = list(dict.fromkeys(mapping[r] for r in refs))
                            c['parent_claim_id'] = mapping.get(c['_parent'])
                            c['module_context'] = {'task': section['writing_brief'],
                                'items': [{'claim_id': v['claim_id'], 'text': v['text']} for v in body]}
                            for key in ['_item_id', '_requires', '_parent']:
                                c.pop(key)

                except Exception as exc:
                    if module_plan:
                        raise ValueError(f"Module {section['module_id']} writing failed") from exc
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
