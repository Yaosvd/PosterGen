"""ID-only display decisions, separate from the immutable scientific bank."""

from copy import deepcopy
from utils.grounded_content import claim_root_id, all_publishable_claims

SELECTION_VERSION = 'editorial_selection_v2'
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
            scope = entry.get('required_for_claim_ids')
            if reason == 'condition' and isinstance(scope, list):
                scope = list(dict.fromkeys(c for c in scope if isinstance(c, str) and c in claims and c != cid))
                if scope:
                    items[cid]['required_for_claim_ids'] = scope
    protected = set(required) & claims.keys()
    protected.update(cid for cid, entry in items.items() if entry['disposition'] == 'required'
                     and not entry.get('required_for_claim_ids'))
    visible = {cid for cid in visible if items.get(cid, {}).get('disposition') != 'omit'}
    # Only unconditional requirements close globally. Optional facts carry
    # their prerequisites at candidate selection time, not permanently.
    retained = set(protected)
    edges = [(a, b) for a, b in dependencies if a in claims and b in claims]
    edges.extend((a, cid) for cid, entry in items.items() for a in entry.get('required_for_claim_ids', []))
    while True:
        new = {b for a, b in edges if a in retained}
        if new.issubset(protected):
            break
        protected.update(new)
        retained.update(new)
    for cid in claims:
        if cid in protected:
            reason = items.get(cid, {}).get('reason') if items.get(cid, {}).get('disposition') == 'required' else ('core' if cid in required else 'condition')
            items[cid] = {**items.get(cid, {}), 'claim_id': cid, 'disposition': 'required', 'reason': reason}
            if cid in required:
                items[cid].pop('required_for_claim_ids', None)
        elif cid not in items:
            items[cid] = {'claim_id': cid, 'disposition': 'optional',
                          'reason': 'useful' if cid in visible else 'unclassified'}
    result = {'version': SELECTION_VERSION, 'items': list(items.values())}
    if edges:
        result['dependencies'] = [list(edge) for edge in dict.fromkeys(edges)]
    if required:
        result['planner_required_claim_ids'] = sorted(set(required) & claims.keys())
    return result


def contract_for(board):
    return (board or {}).get('editorial_selection') or {}


def dispositions(board, state):
    claims = all_publishable_claims(state)
    result = {}
    def priority(item):
        return (4 if item['disposition'] == 'required' and not item.get('required_for_claim_ids')
                else 3 if item['disposition'] == 'required'
                else 2 if item['disposition'] == 'omit'
                else 1 if item.get('reason') != 'unclassified' else 0)
    for item in contract_for(board).get('items', []):
        if item.get('claim_id') not in claims:
            continue
        root = claim_root_id(claims[item['claim_id']])
        # An unselected bank variant must not erase its source requirement or
        # explicit omission just because it was appended later in the bank.
        if root not in result or priority(item) > priority(result[root]):
            result[root] = item
    return result


def root_allowed(board, state, claim):
    return dispositions(board, state).get(claim_root_id(claim), {}).get('disposition') != 'omit'


def required_roots(board, state):
    selection = state.get('content_selection') or {}
    disabled = set(selection.get('disabled_claim_ids') or [])
    replacements = selection.get('replacements') or {}
    excluded = {root for _, root in (state.get('revision_recovery_policy') or {}).get('excluded_claim_roots', [])}
    decisions = dispositions(board, state)
    result = {root for root, item in decisions.items()
              if item['disposition'] == 'required' and not item.get('required_for_claim_ids')}
    claims = all_publishable_claims(state)
    while True:
        more = {claim_root_id(claims.get(b, {'claim_id': b})) for a, b in dependency_edges(board)
                if claim_root_id(claims.get(a, {'claim_id': a})) in result}
        if more.issubset(result):
            break
        result.update(more)
    return {root for root in result if root not in excluded and replacements.get(root, root) not in disabled}


def dependency_edges(board):
    contract = contract_for(board)
    edges = [tuple(e) for e in contract.get('dependencies', [])
             if isinstance(e, (list, tuple)) and len(e) == 2 and all(isinstance(c, str) for c in e)]
    edges.extend((a, i['claim_id']) for i in contract.get('items', [])
                 for a in i.get('required_for_claim_ids', []) if isinstance(a, str))
    return list(dict.fromkeys(edges))


def contexts_met(board, state, selected=None):
    claims = all_publishable_claims(state)
    selected = board if selected is None else selected
    roots = {claim_root_id(claims.get(c, {'claim_id': c}))
             for s in selected.get('spatial_content_plan', {}).get('sections', []) for c in s.get('claim_ids', [])}
    linked = all(claim_root_id(claims.get(a, {'claim_id': a})) not in roots
               or claim_root_id(claims.get(b, {'claim_id': b})) in roots for a, b in dependency_edges(board))
    return linked and all(claim_root_id(claims.get(i['claim_id'], {'claim_id': i['claim_id']})) not in roots
        or any(claim_root_id(claims.get(c, {'claim_id': c})) in roots for c in i['required_for_claim_ids'])
        for i in contract_for(board).get('items', []) if i.get('required_for_claim_ids'))


def selection_audit(board, state):
    """Structural signals trigger review, never prove scientific dispensability."""
    contract = contract_for(board)
    claims = all_publishable_claims(state)
    visible = {claim_root_id(claims.get(c, {'claim_id': c}))
               for s in board.get('spatial_content_plan', {}).get('sections', []) for c in s.get('claim_ids', [])}
    required = required_roots(board, state)
    issues = [{'code': 'SELECTION_REQUIRED_REASON_UNSUPPORTED', 'claim_id': i['claim_id']}
              for i in contract.get('items', []) if i.get('disposition') == 'required'
              and i.get('reason') not in {'core', 'condition'}]
    return {'version': SELECTION_VERSION, 'passed': not issues, 'issues': issues,
            'visible_root_count': len(visible), 'required_root_count': len(required & visible),
            'optional_root_count': len(visible - required),
            'all_visible_required': bool(visible and visible.issubset(required)),
            'review_is_not_a_semantic_proof': True}


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
