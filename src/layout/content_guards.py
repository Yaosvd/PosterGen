"""Content identity and source selection guards for one sample only."""
from typing import Any, Dict
from copy import deepcopy
from utils.grounded_content import claim_root_id

def sections(board: Any) -> Dict[str, Dict[str, Any]]:
    return {
        str(item["section_id"]): item
        for item in (board or {}).get("spatial_content_plan", {}).get("sections", [])
        if isinstance(item, dict) and item.get("section_id")
    }


def board_identity(board: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sections": {sid: {
            "claim_ids": list(item.get("claim_ids", [])),
            "visual_ids": [str(v.get("visual_id")) for v in item.get("visual_assets", []) if isinstance(v, dict)],
            "importance_level": item.get("importance_level"),
        } for sid, item in sections(board).items()},
        "layout_preferences": deepcopy(board.get("layout_preferences") or {}),
    }



def recovery_allowed(state, sid, visual_id):
    policy = state.get('content_recovery_policy') or {}
    if visual_id in policy.get('unusable_visual_ids', []):
        return False
    if [sid, visual_id] in policy.get('excluded_visual_occurrences', []):
        return False
    targets = (policy.get('visual_targets') or {}).get(visual_id)
    return targets is None or sid in targets

def claim_recovery_allowed(state, sid, claim):
    from src.layout.editorial_selection import root_allowed
    return (root_allowed(state.get('story_board'), state, claim)
            and [sid, claim_root_id(claim)] not in
            (state.get('content_recovery_policy') or {}).get('excluded_claim_roots', []))
