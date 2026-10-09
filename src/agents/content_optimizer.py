"""Evidence-grounded text optimization for continuous poster iterations."""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from jinja2 import Template

from src.agents.claim_verifier import claim_verifier_node
from src.state.poster_state import PosterState
from utils.agent_policy import apply_agent_policy
from utils.evidence_utils import evidence_by_id, extract_numbers, normalize_space
from utils.grounded_content import (
    active_publishable_claims,
    add_claim_to_section,
    all_publishable_claims,
    claim_root_id,
    find_claim_by_evidence,
    merge_evidence_banks,
    relevant_evidence_ids,
    rematerialize_board,
    replace_claim_in_board,
)
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from utils.src.logging_utils import (
    log_agent_info,
    log_agent_success,
    log_agent_warning,
)


class GroundedContentOptimizer:
    """Execute bounded Planner content actions behind ClaimVerifier."""

    _OPERATIONS = {
        "use_claim_variant",
        "create_compact_variant",
        "add_existing_claim",
        "add_claim_from_evidence",
    }

    def __init__(self) -> None:
        self.name = "content_optimizer"
        self.prompt = load_prompt("config/prompts/optimize_grounded_content.txt")
        self.supplemental_prompt = load_prompt(
            "config/prompts/extract_supplemental_evidence.txt"
        )
        self.editorial_prompt = load_prompt(
            "config/prompts/verify_content_revision.txt"
        )

    def __call__(
        self,
        state: PosterState,
        *,
        board_override: Optional[Dict[str, Any]] = None,
        actions_override: Optional[List[Dict[str, Any]]] = None,
        save: bool = True,
    ) -> PosterState:
        log_agent_info(self.name, "optimizing grounded module text")
        board = deepcopy(
            board_override
            or state.get("revision_parent_story_board")
            or state.get("optimized_story_board")
            or state.get("story_board")
            or {}
        )
        if not board:
            state.setdefault("errors", []).append(
                f"{self.name}: missing story_board"
            )
            return state

        all_claims = all_publishable_claims(state)
        if not all_claims:
            state.setdefault("errors", []).append(
                f"{self.name}: no publishable claims"
            )
            return state

        settings = state.get("loop_config", {}).get("content_optimization", {})
        config_settings = state.get("critic_config", {}).get(
            "content_optimization", {}
        )
        if not bool(settings.get("enabled", config_settings.get("enabled", True))):
            state["content_revision"] = {"schema_version": 1, "disabled": True}
            return state

        maximum_actions = max(
            1,
            int(
                settings.get(
                    "max_poster_actions_per_iteration",
                    config_settings.get("max_poster_actions_per_iteration", 2),
                )
            ),
        )
        raw_actions = (
            actions_override if actions_override is not None
            else (state.get("revision_plan") or {}).get("content_actions")
        )
        actions = (
            raw_actions
            if isinstance(raw_actions, list) and raw_actions
            else self._deterministic_actions(state, board, all_claims)
        )

        variant_bank = deepcopy(
            state.get("verified_content_bank")
            or {"schema_version": 1, "claims": []}
        )
        supplemental_bank = deepcopy(
            state.get("supplemental_evidence_bank")
            or {"schema_version": 1, "items": []}
        )
        selection = deepcopy(
            state.get("content_selection")
            or {
                "schema_version": 1,
                "replacements": {},
                "active_supplemental_claim_ids": [],
                "disabled_claim_ids": [],
                "last_changed_iteration": {},
            }
        )
        last_changed = selection.setdefault("last_changed_iteration", {})
        current_iteration = int(
            (state.get("iteration_context") or {}).get("iteration", 0)
        )
        reverse_cooldown = max(0, int(config_settings.get(
            "reverse_action_cooldown_iterations", 3
        )))
        accepted_actions: List[Dict[str, Any]] = []
        rejected_actions: List[Dict[str, Any]] = []
        touched_sections = set()
        created_claim_ids: List[str] = []

        for raw_action in actions:
            if len(accepted_actions) >= maximum_actions:
                break
            action = self._sanitize_action(raw_action)
            if action is None:
                continue
            section_id = action["section_id"]
            if section_id in touched_sections:
                continue

            operation = action["operation"]
            success = False
            reason = "operation produced no safe change"
            all_claims = all_publishable_claims({
                **state,
                "verified_content_bank": variant_bank,
            })

            if operation == "use_claim_variant":
                old_id = action.get("claim_id", "")
                variant_id = action.get("variant_id", "")
                variant = all_claims.get(variant_id)
                old_claim = all_claims.get(old_id)
                root_id = claim_root_id(old_claim or {})
                last_change = int(last_changed.get(root_id, -reverse_cooldown))
                if (
                    variant
                    and old_claim
                    and variant.get("verified") is True
                    and claim_root_id(variant) == root_id
                    and current_iteration - last_change >= reverse_cooldown
                ):
                    reverified, _ = self._verify_candidate(
                        state, dict(variant), supplemental_bank
                    )
                    if reverified is not None and str(reverified.get("text")) == str(variant.get("text")):
                        success = replace_claim_in_board(
                            board,
                            old_claim_id=old_id,
                            new_claim_id=variant_id,
                            claim_index=all_claims,
                        )
                    if success:
                        selection.setdefault("replacements", {})[
                            claim_root_id(old_claim)
                        ] = variant_id
                        last_changed[root_id] = current_iteration

            elif operation == "add_existing_claim":
                claim_id = str(action.get("claim_id") or "")
                if not claim_id:
                    visible = self._visible_claim_ids(board)
                    candidate = find_claim_by_evidence(
                        active_publishable_claims({
                            **state,
                            "verified_content_bank": variant_bank,
                            "content_selection": selection,
                        }).get("claims", []),
                        action.get("evidence_ids")
                        or relevant_evidence_ids(state, section_id),
                        excluded_ids=visible,
                    )
                    claim_id = str((candidate or {}).get("claim_id") or "")
                claim = all_claims.get(claim_id)
                target_evidence = {
                    str(item) for item in (
                        action.get("evidence_ids")
                        or relevant_evidence_ids(state, section_id)
                    )
                }
                claim_evidence = {
                    str(item) for item in (claim or {}).get("evidence_ids", [])
                }
                is_relevant = bool(
                    claim
                    and (
                        str(claim.get("section_id") or "") == section_id
                        or bool(target_evidence.intersection(claim_evidence))
                    )
                )
                base_ids = {
                    str(item.get("claim_id"))
                    for item in (state.get("verified_claims") or {}).get("claims", [])
                    if isinstance(item, dict)
                }
                if is_relevant and claim_id not in base_ids:
                    reverified, _ = self._verify_candidate(
                        state, dict(claim), supplemental_bank
                    )
                    is_relevant = bool(
                        reverified is not None
                        and str(reverified.get("text")) == str(claim.get("text"))
                    )
                if is_relevant:
                    success = add_claim_to_section(
                        board, section_id=section_id, claim_id=claim_id,
                        claim_index=all_claims,
                    )
                else:
                    reason = "claim is not relevant or did not pass current verification"

            elif operation in {
                "create_compact_variant",
                "add_claim_from_evidence",
            }:
                candidate, supplemental = self._create_candidate(
                    state,
                    board,
                    action,
                    all_claims,
                    supplemental_bank,
                )
                candidate_supplemental_bank = deepcopy(supplemental_bank)
                if supplemental is not None:
                    candidate_supplemental_bank.setdefault("items", []).append(supplemental)
                if candidate is not None:
                    verified, verification = self._verify_candidate(
                        state,
                        candidate,
                        candidate_supplemental_bank,
                    )
                    source_claim = all_claims.get(str(action.get("claim_id") or ""))
                    if verified is not None and self._editorial_guard(
                        state,
                        operation=operation,
                        source_claim=source_claim,
                        candidate=verified,
                        board=board,
                        supplemental_bank=candidate_supplemental_bank,
                    ):
                        variant_kind = (
                            "compact"
                            if operation == "create_compact_variant"
                            else "supplemental_claim"
                        )
                        verified.update({
                            "root_claim_id": (
                                claim_root_id(source_claim)
                                if source_claim
                                else verified["claim_id"]
                            ),
                            "variant_kind": variant_kind,
                            "created_iteration": int(
                                (state.get("iteration_context") or {}).get(
                                    "iteration", 0
                                )
                            ),
                            "created_candidate_id": (
                                state.get("current_candidate") or {}
                            ).get("candidate_id"),
                            "verification_report": verification,
                            "outcomes": [],
                        })
                        candidate_claims = {
                            **all_claims, verified["claim_id"]: verified
                        }
                        if operation == "create_compact_variant" and source_claim:
                            success = replace_claim_in_board(
                                board,
                                old_claim_id=str(source_claim["claim_id"]),
                                new_claim_id=str(verified["claim_id"]),
                                claim_index=candidate_claims,
                            )
                            if success:
                                selection.setdefault("replacements", {})[
                                    claim_root_id(source_claim)
                                ] = verified["claim_id"]
                                last_changed[
                                    claim_root_id(source_claim)
                                ] = current_iteration
                        else:
                            success = add_claim_to_section(
                                board,
                                section_id=section_id,
                                claim_id=str(verified["claim_id"]),
                                claim_index=candidate_claims,
                            )
                            if success:
                                active_ids = selection.setdefault(
                                    "active_supplemental_claim_ids", []
                                )
                                if verified["claim_id"] not in active_ids:
                                    active_ids.append(verified["claim_id"])
                        if success:
                            variant_bank.setdefault("claims", []).append(verified)
                            supplemental_bank = candidate_supplemental_bank
                            created_claim_ids.append(verified["claim_id"])
                    else:
                        reason = "candidate failed scientific or editorial verification"

            if success:
                touched_sections.add(section_id)
                accepted_actions.append(action)
            else:
                rejected_actions.append({**action, "reason": reason})

        final_index = all_publishable_claims({
            **state,
            "verified_content_bank": variant_bank,
        })
        rematerialize_board(board, final_index)
        state["story_board"] = board
        state["verified_content_bank"] = variant_bank
        state["supplemental_evidence_bank"] = supplemental_bank
        state["content_selection"] = selection
        constraints = state.get("layout_revision_constraints")
        if isinstance(constraints, dict):
            final_sections = [
                item
                for item in board.get("spatial_content_plan", {}).get("sections", [])
                if isinstance(item, dict)
            ]
            constraints["must_retain_claim_ids"] = sorted({
                str(claim_id)
                for section in final_sections
                for claim_id in section.get("claim_ids", [])
                if claim_id
            })
            constraints["must_retain_visual_ids"] = sorted({
                str(visual.get("visual_id"))
                for section in final_sections
                for visual in section.get("visual_assets", [])
                if isinstance(visual, dict) and visual.get("visual_id")
            })
            constraints["content_actions_applied"] = deepcopy(accepted_actions)
            constraints["content_actions_rejected"] = deepcopy(rejected_actions)
        state["content_revision"] = {
            "schema_version": 1,
            "accepted_actions": accepted_actions,
            "rejected_actions": rejected_actions,
            "created_claim_ids": created_claim_ids,
        }
        state["current_agent"] = self.name
        if save:
            self._save(state)
        log_agent_success(
            self.name,
            f"applied {len(accepted_actions)} verified content actions",
        )
        return state

    @classmethod
    def _sanitize_action(cls, raw: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict):
            return None
        operation = str(raw.get("operation") or "")
        section_id = str(raw.get("section_id") or "")
        if operation not in cls._OPERATIONS or not section_id:
            return None
        result = {
            "operation": operation,
            "section_id": section_id,
            "reason": str(raw.get("reason") or ""),
        }
        for key in ("claim_id", "variant_id"):
            if raw.get(key):
                result[key] = str(raw[key])
        evidence_ids = raw.get("evidence_ids")
        if isinstance(evidence_ids, list):
            result["evidence_ids"] = [str(item) for item in evidence_ids][:8]
        for key in (
            "target_max_characters",
            "target_additional_lines",
            "target_height_reduction_inches",
        ):
            if raw.get(key) is not None:
                try:
                    result[key] = max(0.0, float(raw[key]))
                except (TypeError, ValueError):
                    pass
        return result

    def _deterministic_actions(
        self,
        state: Dict[str, Any],
        board: Dict[str, Any],
        claim_index: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        sections = {
            str(section.get("section_id")): section
            for section in board.get("spatial_content_plan", {}).get("sections", [])
        }
        for item in (state.get("critic_report") or {}).get("issues", []):
            issue_id = str(item.get("issue_id") or "")
            section_id = str((item.get("location") or {}).get("section_id") or "")
            section = sections.get(section_id)
            if section is None:
                continue
            if issue_id.startswith(("SECTION-OVERFLOW", "CONTENT-OVERFULL")):
                candidates = [
                    claim_index[claim_id]
                    for claim_id in section.get("claim_ids", [])
                    if claim_id in claim_index
                ]
                if candidates:
                    longest = max(candidates, key=lambda claim: len(str(claim.get("text", ""))))
                    actions.append({
                        "operation": "create_compact_variant",
                        "section_id": section_id,
                        "claim_id": longest["claim_id"],
                        "target_height_reduction_inches": (
                            item.get("evidence") or {}
                        ).get("required_reduction_inches", 0.5),
                        "reason": item.get("required_outcome", "reduce overflow"),
                    })
            elif issue_id.startswith(("SECTION-UNDERFILLED", "CONTENT-UNDERFILLED")):
                evidence_ids = (item.get("evidence") or {}).get(
                    "candidate_evidence_ids"
                ) or relevant_evidence_ids(state, section_id)
                actions.append({
                    "operation": "add_existing_claim",
                    "section_id": section_id,
                    "evidence_ids": evidence_ids,
                    "reason": item.get("required_outcome", "add grounded detail"),
                })
                actions.append({
                    "operation": "add_claim_from_evidence",
                    "section_id": section_id,
                    "evidence_ids": evidence_ids,
                    "reason": item.get("required_outcome", "add grounded detail"),
                })
        return actions

    @staticmethod
    def _visible_claim_ids(board: Dict[str, Any]) -> List[str]:
        return [
            str(claim_id)
            for section in board.get("spatial_content_plan", {}).get("sections", [])
            for claim_id in section.get("claim_ids", [])
        ]

    def _create_candidate(
        self,
        state: Dict[str, Any],
        board: Dict[str, Any],
        action: Dict[str, Any],
        claim_index: Dict[str, Dict[str, Any]],
        supplemental_bank: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        operation = action["operation"]
        source_claim = claim_index.get(str(action.get("claim_id") or ""))
        merged_evidence = merge_evidence_banks({
            **state,
            "supplemental_evidence_bank": supplemental_bank,
        })
        evidence_index = evidence_by_id(merged_evidence)
        evidence_ids = [
            evidence_id
            for evidence_id in action.get("evidence_ids", [])
            if evidence_id in evidence_index
        ]
        if source_claim:
            evidence_ids = [
                str(item)
                for item in source_claim.get("evidence_ids", [])
                if str(item) in evidence_index
            ]
        if not evidence_ids:
            evidence_ids = [
                evidence_id
                for evidence_id in relevant_evidence_ids(
                    state, action["section_id"]
                )
                if evidence_id in evidence_index
            ]

        visible_evidence = {
            str(evidence_id)
            for claim_id in self._visible_claim_ids(board)
            for evidence_id in claim_index.get(claim_id, {}).get("evidence_ids", [])
        }
        if operation == "add_claim_from_evidence":
            unused = [item for item in evidence_ids if item not in visible_evidence]
            evidence_ids = unused

        supplemental = None
        if not evidence_ids and operation == "add_claim_from_evidence":
            supplemental = self._extract_supplemental_evidence(
                state,
                action["section_id"],
                board,
                len(supplemental_bank.get("items", [])),
            )
            if supplemental is not None:
                evidence_index[supplemental["evidence_id"]] = supplemental
                evidence_ids = [supplemental["evidence_id"]]

        evidence = [evidence_index[item] for item in evidence_ids[:6]]
        if not evidence:
            return None, supplemental

        current_text = str((source_claim or {}).get("text", ""))
        target_max = action.get("target_max_characters")
        if operation == "create_compact_variant":
            target_max = int(target_max or max(40, len(current_text) * 0.72))
        else:
            target_max = int(target_max or 220)
        payload = {
            "action": {**action, "target_max_characters": target_max},
            "current_claim": source_claim,
            "evidence": evidence,
            "current_section_claims": [
                claim_index[claim_id].get("text", "")
                for section in board.get("spatial_content_plan", {}).get("sections", [])
                if str(section.get("section_id")) == action["section_id"]
                for claim_id in section.get("claim_ids", [])
                if claim_id in claim_index
            ],
        }
        result = self._model_json(state, self.prompt, payload)
        candidates = result.get("candidates", []) if isinstance(result, dict) else []
        if not isinstance(candidates, list) or not candidates:
            return None, supplemental
        raw = candidates[0]
        if not isinstance(raw, dict):
            return None, supplemental
        text = str(raw.get("text") or "").strip()
        candidate_evidence_ids = [
            str(item)
            for item in raw.get("evidence_ids", [])
            if str(item) in evidence_index and str(item) in evidence_ids
        ]
        if not text or not candidate_evidence_ids:
            return None, supplemental
        if operation == "create_compact_variant" and (
            not current_text or len(text) >= len(current_text)
        ):
            return None, supplemental
        visible_texts = {
            normalize_space(claim_index[claim_id].get("text", "")).casefold()
            for claim_id in self._visible_claim_ids(board)
            if claim_id in claim_index
        }
        if normalize_space(text).casefold() in visible_texts:
            return None, supplemental

        iteration = int((state.get("iteration_context") or {}).get("iteration", 0))
        candidate_id = f"cv_{iteration:06d}_{uuid.uuid4().hex[:10]}"
        return ({
            "claim_id": candidate_id,
            "section_id": action["section_id"],
            "text": text,
            "evidence_ids": candidate_evidence_ids,
            "claim_type": str(raw.get("claim_type") or "descriptive"),
            "risk_level": str(raw.get("risk_level") or "high"),
        }, supplemental)

    def _extract_supplemental_evidence(
        self,
        state: Dict[str, Any],
        section_id: str,
        board: Dict[str, Any],
        existing_count: int,
    ) -> Optional[Dict[str, Any]]:
        chunks = [
            chunk
            for chunk in (state.get("section_chunks") or [])
            if isinstance(chunk, dict) and str(chunk.get("content") or "").strip()
        ]
        if not chunks:
            return None
        base_index = evidence_by_id(state.get("evidence_bank") or {})
        related_sources = {
            str((base_index.get(evidence_id) or {}).get("source", {}).get("section_id"))
            for evidence_id in relevant_evidence_ids(state, section_id)
        }
        current_claims = []
        section_title = section_id
        for section in board.get("spatial_content_plan", {}).get("sections", []):
            if str(section.get("section_id")) == section_id:
                current_claims = list(section.get("text_content", []))
                section_title = str(section.get("section_title") or section_id)
                break
        topic_terms = {
            token.casefold() for token in re.findall(r"[\w-]{4,}", section_title)
        }
        windows = []
        for chunk in chunks:
            content = str(chunk.get("content") or "")
            for start in range(0, len(content), 11800):
                window = content[start:start + 12000]
                source_match = str(chunk.get("section_id")) in related_sources
                term_match = sum(
                    token in window.casefold() for token in topic_terms
                )
                windows.append((chunk, start, window, source_match, term_match))
        selected = sorted(
            windows,
            key=lambda item: (-int(item[3]), -item[4], str(item[0].get("section_id")), item[1]),
        )[:4]
        source_payload = [
            {
                "source_chunk_index": index,
                "section_id": chunk.get("section_id"),
                "section_name": chunk.get("section_name"),
                "section_type": chunk.get("section_type"),
                "window_start": start,
                "content": window,
            }
            for index, (chunk, start, window, _, _) in enumerate(selected)
        ]
        result = self._model_json(state, self.supplemental_prompt, {
            "section_intent": section_id,
            "current_claims": current_claims,
            "source_chunks": source_payload,
        })
        raw_items = result.get("evidence", []) if isinstance(result, dict) else []
        if not isinstance(raw_items, list) or not raw_items or not isinstance(raw_items[0], dict):
            return None
        raw = raw_items[0]
        try:
            source_index = int(raw.get("source_chunk_index", 0))
        except (TypeError, ValueError):
            source_index = 0
        if source_index < 0 or source_index >= len(source_payload):
            return None
        excerpt = normalize_space(raw.get("source_excerpt", ""))
        source_text = normalize_space(source_payload[source_index]["content"])
        claim = normalize_space(raw.get("claim", ""))
        if not excerpt or not claim or excerpt not in source_text:
            return None
        existing_excerpts = {
            normalize_space(item.get("source_excerpt", ""))
            for item in merge_evidence_banks(state).get("items", [])
            if isinstance(item, dict) and item.get("source_excerpt")
        }
        if excerpt in existing_excerpts:
            return None

        source_chunk, window_start, _, _, _ = selected[source_index]
        iteration = int((state.get("iteration_context") or {}).get("iteration", 0))
        try:
            confidence = float(raw.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        return {
            "evidence_id": f"sev_{iteration:06d}_{existing_count + 1:04d}_{uuid.uuid4().hex[:6]}",
            "claim": claim,
            "claim_type": str(raw.get("claim_type") or "background"),
            "source_excerpt": excerpt,
            "source_excerpt_verified": True,
            "entities": [str(item) for item in raw.get("entities", []) if str(item).strip()],
            "numbers": extract_numbers(excerpt),
            "metric": {"name": "", "direction": "unknown"},
            "metric_semantics_source_excerpt": "",
            "confidence": confidence,
            "source": {
                "section_id": source_chunk.get("section_id"),
                "section_name": source_chunk.get("section_name"),
                "section_type": source_chunk.get("section_type"),
                "chunk_index": source_chunk.get("chunk_index", source_index),
                "window_start": window_start,
                "page": source_chunk.get("page"),
            },
        }

    def _verify_candidate(
        self,
        state: Dict[str, Any],
        candidate: Dict[str, Any],
        supplemental_bank: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        isolated = dict(state)
        isolated["evidence_bank"] = merge_evidence_banks({
            **state,
            "supplemental_evidence_bank": supplemental_bank,
        })
        isolated["poster_claims"] = {"claims": [candidate]}
        isolated["verified_claims"] = None
        isolated["verification_report"] = None
        isolated["verification_passed"] = False
        isolated["errors"] = []
        isolated["output_dir"] = str(
            Path(state["output_dir"]) / "content_revision_verification"
        )
        verified_state = claim_verifier_node(isolated)
        report = verified_state.get("verification_report") or {}
        claims = (verified_state.get("verified_claims") or {}).get("claims", [])
        if verified_state.get("errors") or len(claims) != 1:
            return None, report
        verified = dict(claims[0])
        if str(verified.get("claim_id")) != str(candidate.get("claim_id")):
            return None, report
        return verified, report

    def _editorial_guard(
        self,
        state: Dict[str, Any],
        *,
        operation: str,
        source_claim: Optional[Dict[str, Any]],
        candidate: Dict[str, Any],
        board: Dict[str, Any],
        supplemental_bank: Dict[str, Any],
    ) -> bool:
        if operation == "create_compact_variant":
            if not source_claim or len(str(candidate.get("text") or "")) >= len(
                str(source_claim.get("text") or "")
            ):
                return False
        evidence_index = evidence_by_id(merge_evidence_banks({
            **state, "supplemental_evidence_bank": supplemental_bank,
        }))
        excerpts = [
            {
                "evidence_id": evidence_id,
                "source_excerpt": str(evidence_index[evidence_id].get("source_excerpt") or ""),
            }
            for evidence_id in candidate.get("evidence_ids", [])
            if evidence_id in evidence_index
            and evidence_index[evidence_id].get("source_excerpt")
        ]
        if not excerpts:
            return False
        section_id = str(candidate.get("section_id") or "")
        section = next((
            item for item in board.get("spatial_content_plan", {}).get("sections", [])
            if str(item.get("section_id")) == section_id
        ), {})
        result = self._model_json(state, self.editorial_prompt, {
            "operation": operation,
            "source_claim": source_claim,
            "candidate_text": candidate.get("text"),
            "section_title": section.get("section_title"),
            "current_section_text": section.get("text_content") or [],
            "original_paper_excerpts": excerpts,
        })
        if operation == "create_compact_variant":
            return result.get("grounded") is True and result.get("meaning_preserved") is True
        return (
            result.get("grounded") is True
            and result.get("relevant") is True
            and result.get("non_redundant") is True
        )

    def _model_json(
        self,
        state: Dict[str, Any],
        prompt: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            config = apply_agent_policy(state["text_model"], self.name)
            agent = LangGraphAgent(
                "You optimize poster text only within supplied paper evidence.",
                config,
                state,
                self.name,
            )
            response = agent.step(
                Template(prompt).render()
                + "\n\nINPUT DATA:\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            )
            state["tokens"].add_text(
                int(response.input_tokens), int(response.output_tokens)
            )
            result = extract_json(response.content)
            return result if isinstance(result, dict) else {}
        except Exception as exc:
            log_agent_warning(self.name, f"model content action failed: {exc}")
            return {}

    @staticmethod
    def _save(state: Dict[str, Any]) -> None:
        content_dir = Path(state["output_dir"]) / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        payloads = {
            "verified_content_bank.json": state.get("verified_content_bank"),
            "supplemental_evidence_bank.json": state.get("supplemental_evidence_bank"),
            "content_selection.json": state.get("content_selection"),
            "content_revision.json": state.get("content_revision"),
            "story_board.json": state.get("story_board"),
        }
        for filename, payload in payloads.items():
            (content_dir / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


content_optimizer = GroundedContentOptimizer()


def content_optimizer_node(state: PosterState) -> PosterState:
    return content_optimizer(state)
