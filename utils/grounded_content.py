"""Helpers for append-only, evidence-grounded poster content variants.

The parser-to-verifier output remains immutable during continuous optimization.
Any later wording variant lives in ``verified_content_bank`` and is publishable
only after passing the same ClaimVerifier used by the initial pipeline.
"""

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional


def verified_variant_claims(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return only explicitly verified claims from the append-only bank."""

    bank = state.get("verified_content_bank") or {}
    return [
        claim
        for claim in bank.get("claims", [])
        if isinstance(claim, dict)
        and claim.get("claim_id")
        and claim.get("verified") is True
    ]


def all_publishable_claims(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index immutable base claims plus every verified loop-time variant."""

    claims: Dict[str, Dict[str, Any]] = {}
    for claim in (state.get("verified_claims") or {}).get("claims", []):
        if isinstance(claim, dict) and claim.get("claim_id"):
            claims[str(claim["claim_id"])] = claim
    for claim in verified_variant_claims(state):
        claims[str(claim["claim_id"])] = claim
    return claims


def active_publishable_claims(state: Dict[str, Any]) -> Dict[str, Any]:
    """Materialize the paper-specific active claim set for fresh layouts.

    A compact/expanded variant replaces its immutable root claim. Supplemental
    claims are included only after the optimizer explicitly activates them.
    The complete variant bank is deliberately not exposed to GroundedCurator,
    otherwise original and alternative wording would be published together.
    """

    base = [
        deepcopy(claim)
        for claim in (state.get("verified_claims") or {}).get("claims", [])
        if isinstance(claim, dict) and claim.get("claim_id")
    ]
    all_claims = all_publishable_claims(state)
    selection = state.get("content_selection") or {}
    replacements = selection.get("replacements") or {}
    disabled = {str(item) for item in selection.get("disabled_claim_ids", [])}
    active: List[Dict[str, Any]] = []
    seen = set()

    for claim in base:
        root_id = str(claim["claim_id"])
        selected_id = str(replacements.get(root_id, root_id))
        selected = all_claims.get(selected_id)
        if selected is None or selected_id in disabled or selected_id in seen:
            continue
        active.append(deepcopy(selected))
        seen.add(selected_id)

    for claim_id in selection.get("active_supplemental_claim_ids", []):
        claim_id = str(claim_id)
        selected_id = str(replacements.get(claim_id, claim_id))
        claim = all_claims.get(selected_id)
        if claim is None or selected_id in disabled or selected_id in seen:
            continue
        active.append(deepcopy(claim))
        seen.add(selected_id)

    return {"claims": active}


def merge_evidence_banks(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return base and validated supplemental evidence without mutating either."""

    result = deepcopy(state.get("evidence_bank") or {"version": 1, "items": []})
    items = result.setdefault("items", [])
    existing = {
        str(item.get("evidence_id"))
        for item in items
        if isinstance(item, dict) and item.get("evidence_id")
    }
    for item in (state.get("supplemental_evidence_bank") or {}).get("items", []):
        if not isinstance(item, dict) or not item.get("evidence_id"):
            continue
        evidence_id = str(item["evidence_id"])
        if evidence_id in existing or item.get("source_excerpt_verified") is not True:
            continue
        items.append(deepcopy(item))
        existing.add(evidence_id)
    return result


def claim_root_id(claim: Dict[str, Any]) -> str:
    """Return the immutable root id for a base claim or wording variant."""

    return str(claim.get("root_claim_id") or claim.get("claim_id") or "")


def replace_claim_in_board(
    board: Dict[str, Any],
    *,
    old_claim_id: str,
    new_claim_id: str,
    claim_index: Dict[str, Dict[str, Any]],
) -> bool:
    """Replace one visible claim id and rematerialize exact verified text."""

    changed = False
    for section in board.get("spatial_content_plan", {}).get("sections", []):
        claim_ids = list(section.get("claim_ids", []))
        if old_claim_id not in claim_ids:
            continue
        section["claim_ids"] = [
            new_claim_id if claim_id == old_claim_id else claim_id
            for claim_id in claim_ids
        ]
        changed = True
    if changed:
        rematerialize_board(board, claim_index)
    return changed


def add_claim_to_section(
    board: Dict[str, Any],
    *,
    section_id: str,
    claim_id: str,
    claim_index: Dict[str, Dict[str, Any]],
) -> bool:
    """Append one verified claim to a named section if it is not visible."""

    visible = {
        str(item)
        for section in board.get("spatial_content_plan", {}).get("sections", [])
        for item in section.get("claim_ids", [])
    }
    if claim_id in visible or claim_id not in claim_index:
        return False
    for section in board.get("spatial_content_plan", {}).get("sections", []):
        if str(section.get("section_id")) != str(section_id):
            continue
        section.setdefault("claim_ids", []).append(claim_id)
        rematerialize_board(board, claim_index)
        return True
    return False


def rematerialize_board(
    board: Dict[str, Any],
    claim_index: Dict[str, Dict[str, Any]],
    *,
    remove_unknown: bool = True,
) -> None:
    """Rebuild every visible string exactly from the publishable claim bank."""

    seen = set()
    sections = board.get("spatial_content_plan", {}).get("sections", [])
    for section in sections:
        valid_ids = []
        for raw_claim_id in section.get("claim_ids", []):
            claim_id = str(raw_claim_id)
            if claim_id in seen:
                continue
            if claim_id not in claim_index:
                if not remove_unknown:
                    valid_ids.append(claim_id)
                continue
            seen.add(claim_id)
            valid_ids.append(claim_id)
        section["claim_ids"] = valid_ids
        section["text_content"] = [
            str(claim_index[claim_id].get("text", ""))
            for claim_id in valid_ids
        ]


def relevant_evidence_ids(
    state: Dict[str, Any],
    section_id: str,
) -> List[str]:
    """Return evidence assigned to a narrative section in stable order."""

    for section in (state.get("narrative_plan") or {}).get("sections", []):
        if str(section.get("section_id")) == str(section_id):
            return [str(item) for item in section.get("evidence_ids", [])]
    return []


def find_claim_by_evidence(
    claims: Iterable[Dict[str, Any]],
    evidence_ids: Iterable[str],
    *,
    excluded_ids: Optional[Iterable[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Find the first claim supported by relevant evidence and not excluded."""

    relevant = {str(item) for item in evidence_ids}
    excluded = {str(item) for item in (excluded_ids or [])}
    for claim in claims:
        claim_id = str(claim.get("claim_id", ""))
        if not claim_id or claim_id in excluded:
            continue
        if relevant.intersection(str(item) for item in claim.get("evidence_ids", [])):
            return claim
    return None
