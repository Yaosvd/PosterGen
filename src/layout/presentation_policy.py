"""Paper-local presentation structure, independent of layout-family IDs.

These are editorial priorities over verified IDs, not scientific membership or
image-association judgments. No sentence, evidence bank or foundation is edited.
"""

from collections import Counter
from copy import deepcopy
import re

from src.layout.paper_profile import narrative_role
from utils.grounded_content import all_publishable_claims, claim_root_id


PRESENTATION_POLICY_VERSION = 'paper_presentation_v1'
CORE_ROLES = {'method', 'theory', 'results', 'evaluation', 'insight'}
FOCUS_COMPANION_ROLES = CORE_ROLES | {'conclusion', 'impact', 'implications', 'discussion', 'supporting'}


def ordered_plan(state):
    """Use primary body-source order; legacy inputs retain planned order.

    A section's most represented body source avoids abstract previews or a
    repeated introductory result overriding its real place in the paper.
    Ties use the original source/Planner order, never lexicographic IDs.
    """
    plan = deepcopy((state.get('narrative_plan') or {}).get('sections', []))
    evidence = {str(e['evidence_id']): e for e in (state.get('evidence_bank') or {}).get('items', [])}
    sources = {}
    for evidence_item in evidence.values():
        source = evidence_item.get('source') or {}
        sid = str(source.get('section_id') or '')
        if sid:
            sources.setdefault(sid, len(sources))
    ranked = []
    for index, section in enumerate(plan):
        if section.get('source_order_provenance') in {'evidence_source', 'planned_order'}:
            value = section.get('source_order')
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                ranked.append((value, index, section))
                continue
        counts = Counter()
        introductory = set()
        for eid in section.get('evidence_ids', []):
            source = (evidence.get(str(eid)) or {}).get('source') or {}
            name = str(source.get('section_name') or '').strip().lower()
            sid = str(source.get('section_id') or '')
            if sid in sources and not re.search(r'^(abstract|references|acknowledg|related work)', name):
                counts[sid] += 1
                if re.search(r'^(?:\d+(?:\.\d+)*[.)]?\s*)?introduction\b', name):
                    introductory.add(sid)
        if narrative_role(section) in CORE_ROLES | {'conclusion', 'impact', 'implications', 'discussion'}:
            counts = Counter({sid: count for sid, count in counts.items() if sid not in introductory})
        if counts:
            source = min(counts, key=lambda sid: (-counts[sid], sources[sid]))
            rank = sources[source]
            section['source_order_provenance'] = 'evidence_source'
            section['primary_source_section_id'] = source
        else:
            rank = index
            section['source_order_provenance'] = 'planned_order'
        ranked.append((rank, index, section))
    for rank, (_, _, section) in enumerate(sorted(ranked, key=lambda item: item[:2])):
        section['source_order'] = rank
    return {str(s['section_id']): s for s in plan}


def _claims(section, state):
    bank = all_publishable_claims(state)
    return bank, [bank.get(str(cid), {'claim_id': str(cid)}) for cid in section.get('claim_ids', [])]


def section_sources(section, state):
    bank, claims = _claims(section, state)
    original = [bank.get(claim_root_id(c), c) for c in claims]
    return list(dict.fromkeys(str(c['section_id']) for c in original if c.get('section_id')))


def contribution_roots(section, state):
    """A Curator label alone cannot manufacture a dataset contribution."""
    bank, claims = _claims(section, state)
    plan = ordered_plan(state)
    roots = set()
    for claim in claims:
        original = bank.get(claim_root_id(claim), claim)
        source = plan.get(str(original.get('section_id')), {})
        declared = set(source.get('contribution_evidence_ids') or [])
        explicit = re.search(
            r'\b(?:introduc\w*|releas\w*|contribut\w*|creat\w*)\s+'
            r'(?:(?:a|an|the|our|new|novel|public|open|large[- ]scale|benchmark)\s+){0,6}'
            r'(?:dataset|benchmark|corpus|database)\b'
            r'|\b(?:dataset|benchmark|corpus)\b.{0,45}\b(?:newly introduced|newly released|novel)\b',
            str(original.get('text') or ''), re.I)
        if explicit or declared.intersection(claim.get('evidence_ids') or []):
            roots.add(claim_root_id(claim))
    return roots


def section_role(section, state):
    plan = ordered_plan(state)
    sources = section_sources(section, state)
    roles = {narrative_role(plan.get(sid, {})) for sid in sources}
    if len(roles) == 1:
        return next(iter(roles))
    sid = str(section.get('section_id'))
    return narrative_role(plan.get(sid, {})) if sid in sources or not sources else ''


def is_auxiliary(section, state):
    if contribution_roots(section, state):
        return False
    meta = section.get('editorial') or {}
    supporting = set((section.get('presentation') or {}).get('supporting_claim_roots', []))
    if supporting and {claim_root_id(c) for c in _claims(section, state)[1]} - supporting:
        return False
    kinds = {h['claim_id']: h.get('kind') for h in meta.get('items', [])}
    values = [kinds.get(cid, '') for cid in section.get('claim_ids', [])]
    if not values:
        return False
    setup = sum(kind == 'setup' for kind in values)
    # Function metadata, rather than the word "Dataset", identifies routine
    # supporting material. Unknown prose cannot certify a contribution.
    return (not section.get('visual_assets') and
            (meta.get('module_purpose') == 'supporting' or
             (setup > 0 and (setup / len(values) >= .6 or not any(kind in
              {'method', 'result', 'interpretation', 'definition', 'goal'} for kind in values)))))


def required_supporting_contexts(section, state, claims=None):
    """Retain useful merged context through same-root wording freedom.

    Explicit exclusions/disabled roots remain authoritative; this never
    resurrects an intentionally deleted fact or imposes a sentence count.
    """
    claims = all_publishable_claims(state) if claims is None else claims
    excluded = {tuple(pair) for pair in (state.get('revision_recovery_policy') or {}).get('excluded_claim_roots', [])}
    selection = state.get('content_selection') or {}
    disabled = set(selection.get('disabled_claim_ids') or [])
    replacements = selection.get('replacements') or {}
    result = []
    for group in (section.get('presentation') or {}).get('supporting_context_groups', []):
        available = {root for root in group['claim_roots'] if replacements.get(root, root) not in disabled
                     and (str(section['section_id']), root) not in excluded
                     and (str(group['source_section_id']), root) not in excluded}
        if available:
            result.append(available.intersection(group.get('preferred_roots') or []) or available)
    return result


def supporting_contexts_preserved(section, state, claims=None):
    claims = all_publishable_claims(state) if claims is None else claims
    visible = {claim_root_id(claims.get(cid, {'claim_id': cid})) for cid in section.get('claim_ids', [])}
    return all(visible.intersection(group) for group in required_supporting_contexts(section, state, claims))


def prepare_structure(board, state, family):
    """Classify every module; regroup bounded auxiliaries before selection."""
    from src.layout.editorial import sections, locked, _organize
    result = deepcopy(board)
    report = {'version': PRESENTATION_POLICY_VERSION, 'merges': [], 'unresolved_section_ids': []}
    active = state.get('generation_route') == 'optimization_family'
    if not active:
        return result, report
    if locked(state):
        report['reason'] = 'locked'
        return result, report
    for section in sections(result):
        policy = section.setdefault('presentation', {})
        policy.update(version=PRESENTATION_POLICY_VERSION,
                      original_auxiliary=policy.get('original_auxiliary', is_auxiliary(section, state)))
    if state.get('layout_revision_constraints') or not family.contract.allow_module_grouping:
        report['reason'] = 'locked_or_grouping_disabled'
        report['unresolved_section_ids'] = [s['section_id'] for s in sections(result)
            if (s.get('presentation') or {}).get('original_auxiliary')]
        return result, report
    for _ in range(4):
        ordered = sections(result)
        auxiliary = next((s for s in ordered if (s.get('presentation') or {}).get('original_auxiliary')
                          and s['section_id'] not in report['unresolved_section_ids']), None)
        if auxiliary is None:
            break
        position = ordered.index(auxiliary)
        # Attach to an existing adjacent scientific stage. A source-specific
        # grouping hint is optional; it never overrides incompatible roles.
        role = section_role(auxiliary, state)
        compatible = {'results', 'evaluation'} if role in {'results', 'evaluation'} else {'method', 'theory', 'evaluation'}
        candidates = [s for s in ordered if s is not auxiliary
                      and not (s.get('presentation') or {}).get('original_auxiliary')
                      and section_role(s, state) in compatible]
        if role not in {'method', 'theory', 'evaluation', 'results', 'supporting', ''}:
            candidates = []
        if not candidates:
            report['unresolved_section_ids'].append(auxiliary['section_id'])
            continue
        target = min(candidates, key=lambda s: (abs(ordered.index(s) - position), ordered.index(s) > position))
        bank, auxiliary_claims = _claims(auxiliary, state)
        auxiliary_roots = {claim_root_id(c) for c in auxiliary_claims}
        preferred = {claim_root_id(bank.get(cid, {'claim_id': cid})) for cid in auxiliary.get('core_claim_ids', [])}
        target['presentation'].setdefault('supporting_context_groups', []).append({
            'source_section_id': auxiliary['section_id'], 'claim_roots': sorted(auxiliary_roots),
            'preferred_roots': sorted(preferred & auxiliary_roots)})
        for field in ('claim_ids', 'text_content', 'visual_assets'):
            target.setdefault(field, []).extend(deepcopy(auxiliary.get(field) or []))
        for field in ('core_claim_ids', 'curated_claim_roots'):
            target[field] = list(dict.fromkeys(target.get(field, []) + auxiliary.get(field, [])))
        a, b = target.setdefault('editorial', {}), auxiliary.get('editorial') or {}
        a['items'] = a.get('items', []) + deepcopy(b.get('items', []))
        a['source_section_ids'] = list(dict.fromkeys(a.get('source_section_ids', []) + b.get('source_section_ids', [])))
        a['merged_section_ids'] = list(dict.fromkeys(a.get('merged_section_ids', [target['section_id']])
                                                    + b.get('merged_section_ids', [auxiliary['section_id']])))
        title = 'Results' if section_role(target, state) in {'results', 'evaluation'} else 'Methods'
        a.update(source_title=title, title_candidates=[])
        target['section_title'] = title
        target['presentation']['supporting_claim_roots'] = sorted(set(
            target['presentation'].get('supporting_claim_roots', [])) | {
                claim_root_id(c) for c in _claims(auxiliary, state)[1]})
        _organize(target)
        ordered.remove(auxiliary)
        report['merges'].append({'section_id': auxiliary['section_id'], 'into_section_id': target['section_id']})
    report['unresolved_section_ids'] = sorted(set(report['unresolved_section_ids']) | {
        s['section_id'] for s in sections(result) if (s.get('presentation') or {}).get('original_auxiliary')})
    return result, report


def focus_roots(state, contract):
    plan = ordered_plan(state)
    eligible = {sid: s for sid, s in plan.items() if narrative_role(s) in set(contract.focus_roles)}
    if not eligible:
        return set()
    importance = lambda s: int(s.get('importance', 2) or 2)
    best = min(importance(s) for s in eligible.values())
    primary = {sid for sid, s in eligible.items() if importance(s) == best}
    claims = all_publishable_claims(state)
    return {claim_root_id(c) for c in claims.values()
            if str(claims.get(claim_root_id(c), c).get('section_id')) in primary}


def focus_allowed(section, state, contract):
    roots = {claim_root_id(c) for c in _claims(section, state)[1]}
    return bool(roots & focus_roots(state, contract) or contribution_roots(section, state))


def focus_placement_allowed(section, state, contract):
    return focus_allowed(section, state, contract) or section_role(section, state) in FOCUS_COMPANION_ROLES


def structure_audit(board, spec, state, contract):
    from src.layout.editorial import sections
    from src.layout.reading_flow import analyze_reading, planned_for_sections
    by_id = {str(s['section_id']): s for s in sections(board)}
    problems = []
    if state.get('generation_route') != 'optimization_family':
        return {'version': PRESENTATION_POLICY_VERSION, 'passed': True, 'issues': [], 'status': 'not_applicable'}
    for sid, section in by_id.items():
        if not supporting_contexts_preserved(section, state):
            problems.append({'code': 'SUPPORTING_CONTEXT_LOST', 'section_id': sid})
        if is_auxiliary(section, state) or (section.get('presentation') or {}).get('original_auxiliary'):
            problems.append({'code': 'AUXILIARY_MODULE_STANDALONE', 'section_id': sid})
        support = set((section.get('presentation') or {}).get('supporting_claim_roots', []))
        roots = {claim_root_id(c) for c in _claims(section, state)[1]}
        if support and roots and roots.issubset(support) and not section.get('visual_assets'):
            problems.append({'code': 'MODULE_LOST_INDEPENDENT_FUNCTION', 'section_id': sid})
    for zone in spec.get('zones', []):
        if zone.get('role') != 'hero':
            continue
        ids = zone.get('section_ids', [])
        if ids and not any(focus_allowed(by_id.get(str(sid), {}), state, contract) for sid in ids):
            problems.append({'code': 'HERO_NOT_PAPER_FOCUS', 'zone_id': zone['zone_id']})
        for sid in ids:
            section = by_id.get(str(sid), {})
            if not focus_placement_allowed(section, state, contract):
                problems.append({'code': 'HERO_NOT_PAPER_FOCUS', 'section_id': sid, 'zone_id': zone['zone_id']})
            if contract.entry_roles and section_role(section, state) not in contract.entry_roles:
                problems.append({'code': 'INVALID_READING_ENTRY', 'section_id': sid, 'zone_id': zone['zone_id']})
    reading = analyze_reading(spec, contract, planned_for_sections(state, sections(board)))
    if reading['conflicts'] or reading.get('source_order_conflicts'):
        problems.append({'code': 'NATURAL_READING_ORDER_CONFLICT'})
    if not reading['declared_order_matches_positions']:
        problems.append({'code': 'DECLARED_READING_ORDER_MISMATCH'})
    return {'version': PRESENTATION_POLICY_VERSION, 'passed': not problems,
            'issues': problems, 'reading_flow': reading,
            'independent_section_ids': sorted(sid for sid, s in by_id.items() if not is_auxiliary(s, state))}
