"""Paper-local retrieval context derived from the current module's verified roots.

These are retrieval hints, not a semantic membership/admission certificate.
No other storyboard or mutable parent is consulted.
"""

from utils.grounded_content import all_publishable_claims, claim_root_id, merge_evidence_banks
from utils.evidence_utils import evidence_by_id


def module_context(state, board, section_id):
    section = next((s for s in (board or {}).get('spatial_content_plan', {}).get('sections', [])
                    if str(s.get('section_id')) == str(section_id)), None)
    if section is None:
        return {'claim_ids': [], 'evidence_ids': [], 'source_section_ids': [], 'status': 'missing_module'}
    claims = all_publishable_claims(state)
    from src.layout.editorial_selection import root_allowed
    excluded = {str(root) for sid, root in
                (state.get('content_recovery_policy') or {}).get('excluded_claim_roots', [])
                if str(sid) == str(section_id)}
    roots = {str(r) for r in section.get('curated_claim_roots', [])} | {
        claim_root_id(claims[c]) for c in section.get('claim_ids', []) if c in claims}
    roots -= excluded
    related = [c for c in claims.values() if claim_root_id(c) in roots and root_allowed(board, state, c)]
    plan_ids = {str(c.get('section_id')) for c in related if c.get('section_id')}
    plan_ids.add(str(section_id))
    evidence = list(dict.fromkeys(str(e) for c in related for e in c.get('evidence_ids', [])))
    plans = [p for p in (state.get('narrative_plan') or {}).get('sections', [])
             if str(p.get('section_id')) in plan_ids]
    split_sources = set((section.get('presentation') or {}).get('source_claim_roots', {}))
    evidence.extend(str(e) for p in plans if str(p.get('section_id')) not in split_sources
                    for e in p.get('evidence_ids', []))
    index = evidence_by_id(merge_evidence_banks(state))
    from src.layout.editorial_selection import omitted_evidence
    omitted = omitted_evidence(board, state)
    evidence = list(dict.fromkeys(e for e in evidence if e in index and e not in omitted))
    return {
        'claim_ids': sorted(str(c['claim_id']) for c in related),
        'evidence_ids': evidence,
        'source_section_ids': sorted({str(index[e]['source']['section_id']) for e in evidence
                                      if (index[e].get('source') or {}).get('section_id') is not None}),
        'section_title': str(section.get('section_title') or section_id),
        'title_intents': [str(p['title_intent']) for p in plans if p.get('title_intent')],
        'status': 'grounded_context' if evidence else 'no_evidence_context',
    }


def existing_module_candidates(state, board, section_id, *, excluded_ids=(), evidence_ids=None):
    """Prefer original omitted roots; suppress visible roots and exact duplicates."""
    from src.layout.content_guards import claim_recovery_allowed
    from src.layout.editorial_selection import root_allowed
    claims = all_publishable_claims(state)
    context = module_context(state, board, section_id)
    original = set(context['claim_ids'])
    evidence = set(context['evidence_ids'])
    visible = {c for s in board.get('spatial_content_plan', {}).get('sections', [])
               for c in s.get('claim_ids', [])}
    visible_roots = {claim_root_id(claims[c]) for c in visible if c in claims}
    texts = {' '.join(str(claims[c].get('text', '')).split()).casefold() for c in visible if c in claims}
    selection = state.get('content_selection') or {}
    disabled = set(selection.get('disabled_claim_ids') or [])
    disabled_roots = {root for root, cid in (selection.get('replacements') or {}).items() if cid in disabled}
    excluded = set(excluded_ids) | disabled
    candidates = [c for cid, c in claims.items()
                  if cid not in visible | excluded and claim_root_id(c) not in visible_roots | disabled_roots
                  and (not evidence_ids or set(evidence_ids).intersection(c.get('evidence_ids', [])))
                  and (cid in original or evidence.intersection(c.get('evidence_ids', [])))
                  and ' '.join(str(c.get('text', '')).split()).casefold() not in texts
                  and claim_recovery_allowed(state, str(section_id), c)]
    candidates = [c for c in candidates if root_allowed(board, state, c)]
    return sorted(candidates, key=lambda c: (
        c['claim_id'] not in original,
        -len(evidence.intersection(c.get('evidence_ids', []))),
        len(str(c.get('text', ''))), str(c['claim_id'])))
