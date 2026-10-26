"""ID-only display decisions, separate from the immutable scientific bank."""

from copy import deepcopy
from utils.grounded_content import claim_root_id, layout_claims as all_publishable_claims

SELECTION_VERSION = 'editorial_selection_v1'
REASONS = {'core', 'condition', 'useful', 'secondary', 'redundant', 'out_of_scope', 'unclassified'}


def sanitize_selection(raw, claims, visible=(), required=(), dependencies=()):
    """Required/context closure wins over contradictory omission suggestions."""
    raw = raw if isinstance(raw, dict) else {}
    items = {}
    for entry in raw.get('items', []) if isinstance(raw.get('items'), list) else []:
        if not isinstance(entry, dict):
            continue
        cid = entry.get('claim_id')
        disposition, reason = entry.get('disposition'), entry.get('reason')
        if (isinstance(cid, str) and cid in claims and isinstance(disposition, str) and disposition in {'required', 'optional', 'omit'}
                and isinstance(reason, str) and reason in REASONS and not (disposition == 'omit' and reason not in {'secondary', 'redundant', 'out_of_scope'})):
            items[cid] = {'claim_id': cid, 'disposition': disposition, 'reason': reason}
    protected = set(required) & claims.keys()
    protected.update(cid for cid, entry in items.items() if entry['disposition'] == 'required')
    visible = {cid for cid in visible if items.get(cid, {}).get('disposition') != 'omit'}
    # Prerequisites of retained optional claims are necessary too.
    retained = visible | protected
    edges = [(a, b) for a, b in dependencies if a in claims and b in claims]
    while True:
        new = {b for a, b in edges if a in retained}
        if new.issubset(protected):
            break
        protected.update(new)
        retained.update(new)
    for cid in claims:
        if cid in protected:
            reason = items.get(cid, {}).get('reason') if items.get(cid, {}).get('disposition') == 'required' else ('core' if cid in required else 'condition')
            items[cid] = {'claim_id': cid, 'disposition': 'required', 'reason': reason}
        elif cid not in items:
            items[cid] = {'claim_id': cid, 'disposition': 'optional',
                          'reason': 'useful' if cid in visible else 'unclassified'}
    return {'version': SELECTION_VERSION, 'items': list(items.values())}


def contract_for(board):
    return (board or {}).get('editorial_selection') or {}


def dispositions(board, state):
    claims = all_publishable_claims(state)
    return {claim_root_id(claims.get(i['claim_id'], {'claim_id': i['claim_id']})): i
            for i in contract_for(board).get('items', []) if i.get('claim_id') in claims}


def root_allowed(board, state, claim):
    return dispositions(board, state).get(claim_root_id(claim), {}).get('disposition') != 'omit'


def required_roots(board, state):
    selection = state.get('content_selection') or {}
    disabled = set(selection.get('disabled_claim_ids') or [])
    replacements = selection.get('replacements') or {}
    excluded = {root for _, root in (state.get('content_recovery_policy') or {}).get('excluded_claim_roots', [])}
    return {root for root, item in dispositions(board, state).items()
            if item['disposition'] == 'required' and root not in excluded
            and replacements.get(root, root) not in disabled}


def omitted_evidence(board, state):
    claims = all_publishable_claims(state)
    omitted = {root for root, item in dispositions(board, state).items() if item['disposition'] == 'omit'}
    # Conservatively protect the whole omitted excerpt from source-search
    # resurrection; existing same-root compaction remains possible.
    return {eid for claim in claims.values() if claim_root_id(claim) in omitted
            for eid in claim.get('evidence_ids', [])}


def filter_board(board, state):
    """Keep decisions on the board so snapshots/rollback retain them together."""
    result = deepcopy(board)
    claims = all_publishable_claims(state)
    for section in result.get('spatial_content_plan', {}).get('sections', []):
        pairs = [(cid, text) for cid, text in zip(section.get('claim_ids', []), section.get('text_content', []))
                 if root_allowed(result, state, claims.get(cid, {'claim_id': cid}))]
        section['claim_ids'] = [cid for cid, _ in pairs]
        section['text_content'] = [text for _, text in pairs]
    result['spatial_content_plan']['sections'] = [s for s in result['spatial_content_plan']['sections']
                                                 if s.get('claim_ids') or s.get('visual_assets')]
    return result
