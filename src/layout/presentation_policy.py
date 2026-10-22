"""Paper-local presentation structure, independent of layout-family IDs.

These are editorial priorities over verified IDs, not scientific membership or
image-association judgments. No sentence, evidence bank or foundation is edited.
"""

from collections import Counter
from copy import deepcopy
import re

from src.layout.paper_profile import narrative_role
from utils.grounded_content import all_publishable_claims, claim_root_id


PRESENTATION_POLICY_VERSION = 'paper_presentation_v3'
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
    from utils.source_context import evidence_contexts
    overlay = {eid: context for eid, context in evidence_contexts(state).get('evidence', {}).items()
               if context.get('status') == 'located_body'}
    sources = {}
    for evidence_item in evidence.values():
        source = evidence_item.get('source') or {}
        sid = str(source.get('section_id') or '')
        if sid:
            sources.setdefault(sid, len(sources))
    ranked = []
    for index, section in enumerate(plan):
        if not overlay and section.get('source_order_provenance') in {'evidence_source', 'planned_order'}:
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
        located = [overlay[eid] for eid in section.get('evidence_ids', [])
                   if overlay.get(eid, {}).get('status') == 'located_body'
                   and not re.search(r'^(abstract|references|acknowledg|related work)',
                                     overlay[eid]['heading_path'][-1].lower() if overlay[eid]['heading_path'] else '')]
        if narrative_role(section) in CORE_ROLES | {'conclusion', 'impact', 'implications', 'discussion'}:
            located = [c for c in located if not re.search(r'^(?:\d+(?:\.\d+)*[.)]?\s*)?introduction\b',
                       c['heading_path'][-1].lower() if c['heading_path'] else '')]
        if located:
            contexts = Counter(c['body_start_char'] for c in located)
            anchor = min(contexts, key=lambda a: (-contexts[a], a))
            rank = anchor
            section['source_order_provenance'] = 'evidence_source'
            section['body_context_anchor'] = anchor
            section['primary_source_section_id'] = 'body_' + str(anchor)
        elif overlay:
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
    from src.workflow.sample_modules import source_units
    return list(dict.fromkeys(sid for c in original for sid in source_units(c)))


def claim_source_plan(claim, plan):
    from src.workflow.sample_modules import source_units
    sources = [plan[s] for s in source_units(claim) if s in plan]
    if len(sources) == 1:
        return sources[0]
    roles = {narrative_role(s) for s in sources}
    functions = {s.get('presentation_function', '') for s in sources}
    return {'narrative_role': next(iter(roles)) if len(roles) == 1 else '',
            'presentation_function': next(iter(functions)) if len(functions) == 1 else '',
            'required_evidence_ids': sorted({e for s in sources for e in s.get('required_evidence_ids', [])}),
            'contribution_evidence_ids': sorted({e for s in sources if s.get('central_subject')
                                                for e in s.get('contribution_evidence_ids', [])}),
            'central_subject': any(s.get('central_subject') for s in sources)}


def contribution_roots(section, state):
    """A Curator label alone cannot manufacture a dataset contribution."""
    bank, claims = _claims(section, state)
    plan = ordered_plan(state)
    roots = set()
    for claim in claims:
        original = bank.get(claim_root_id(claim), claim)
        source = claim_source_plan(original, plan)
        declared = set(source.get('contribution_evidence_ids') or [])
        # Introducing data is not itself proof of centrality. The existing
        # Planner must explicitly ground a central scientific subject.
        if source.get('central_subject') is True and declared.intersection(claim.get('evidence_ids') or []):
            roots.add(claim_root_id(claim))
    return roots


def section_role(section, state):
    plan = ordered_plan(state)
    sources = section_sources(section, state)
    roles = {narrative_role(plan.get(sid, {})) for sid in sources}
    if len(roles) == 1:
        return next(iter(roles))
    sid = str(section.get('section_id'))
    return narrative_role(plan.get(sid, {})) if not sources else ''


def auxiliary_assessment(section, state):
    """Resolve display function from original roots, not a setup-count alone.

    Core hints are editorial metadata over verified IDs, not scientific proof.
    Require a compatible original Planner function as well; a primary label or
    another module's variant/source ID cannot make routine data independent.
    """
    if contribution_roots(section, state):
        return {'auxiliary': False, 'reason': 'grounded_central_subject'}
    meta = section.get('editorial') or {}
    supporting = set((section.get('presentation') or {}).get('supporting_claim_roots', []))
    bank, claims = _claims(section, state)
    if supporting and {claim_root_id(c) for c in claims} - supporting:
        return {'auxiliary': False, 'reason': 'retained_independent_roots'}
    kinds = {h['claim_id']: h.get('kind') for h in meta.get('items', [])}
    values = [kinds.get(cid, '') for cid in section.get('claim_ids', [])]
    if not values:
        return {'auxiliary': False, 'reason': 'unknown_function'}
    setup = sum(kind == 'setup' for kind in values)
    core = {claim_root_id(bank.get(cid, {'claim_id': cid})) for cid in section.get('core_claim_ids', [])}
    plan = ordered_plan(state)
    independent, task_kinds = set(), set()
    for claim in claims:
        root = claim_root_id(claim)
        if root not in core or claim.get('claim_id') not in bank:
            continue
        original = bank.get(root, claim)
        source = claim_source_plan(original, plan)
        role, function = narrative_role(source), source.get('presentation_function')
        kind = kinds.get(claim['claim_id'], '')
        if (kind in {'definition', 'goal'} and
                (function == 'task_definition' or role in {'foundation', 'background', 'problem', 'motivation', 'insight'})
                and function not in {'evaluation', 'method', 'results', 'research_insight'}):
            independent.add(root)
            task_kinds.add(kind)
        elif ((kind == 'method' and (role in {'method', 'theory'} or function == 'method'))
              or (kind in {'result', 'interpretation'} and
                  (role in {'results', 'evaluation', 'conclusion', 'impact', 'implications', 'discussion', 'insight'}
                   or function in {'results', 'evaluation', 'implications', 'research_insight'}))):
            independent.add(root)
    explicit_supporting = meta.get('module_purpose') == 'supporting'
    # A full task definition can survive a mistaken module-purpose hint. Mixed
    # routine data/method groups still follow their explicit supporting policy.
    if independent and (not explicit_supporting or task_kinds == {'definition', 'goal'}):
        return {'auxiliary': False, 'reason': 'source_supported_independent_core',
                'independent_core_roots': sorted(independent)}
    routine = explicit_supporting or (setup > 0 and (setup / len(values) >= .6 or not any(
        kind in {'method', 'result', 'interpretation', 'definition', 'goal'} for kind in values)))
    return {'auxiliary': routine, 'reason': 'routine_support' if routine else 'non_supporting_function'}


def is_auxiliary(section, state):
    return auxiliary_assessment(section, state)['auxiliary']


def required_supporting_contexts(section, state, claims=None):
    """Retain useful merged context through same-root wording freedom.

    Explicit exclusions/disabled roots remain authoritative; this never
    resurrects an intentionally deleted fact or imposes a sentence count.
    """
    claims = all_publishable_claims(state) if claims is None else claims
    excluded = {tuple(pair) for pair in (state.get('content_recovery_policy') or {}).get('excluded_claim_roots', [])}
    selection = state.get('content_selection') or {}
    disabled = set(selection.get('disabled_claim_ids') or [])
    replacements = selection.get('replacements') or {}
    result = []
    for root in (section.get('presentation') or {}).get('required_claim_roots', []):
        if (replacements.get(root, root) not in disabled and
                not any((str(sid), root) in excluded for sid in
                        (section.get('editorial') or {}).get('merged_section_ids', [section['section_id']]))):
            result.append({root})
    for group in (section.get('presentation') or {}).get('supporting_context_groups', []):
        available = {root for root in group.get('required_roots', []) if replacements.get(root, root) not in disabled
                     and (str(section['section_id']), root) not in excluded
                     and (str(group['source_section_id']), root) not in excluded}
        if available:
            result.append(available.intersection(group.get('preferred_roots') or []) or available)
    return result


def supporting_contexts_preserved(section, state, claims=None):
    claims = all_publishable_claims(state) if claims is None else claims
    visible = {claim_root_id(claims.get(cid, {'claim_id': cid})) for cid in section.get('claim_ids', [])}
    return all(visible.intersection(group) for group in required_supporting_contexts(section, state, claims))


def _merge_into(target, source, state, *, supporting=False, required=()):
    """Move verified entries and their original provenance as one transaction."""
    bank, claims = _claims(source, state)
    roots = {claim_root_id(c) for c in claims}
    presentation = target.setdefault('presentation', {})
    for field in ('claim_ids', 'text_content', 'visual_assets'):
        target.setdefault(field, []).extend(deepcopy(source.get(field) or []))
    for field in ('core_claim_ids', 'curated_claim_roots'):
        target[field] = list(dict.fromkeys(target.get(field, []) + source.get(field, [])))
    a, b = target.setdefault('editorial', {}), source.get('editorial') or {}
    a['items'] = a.get('items', []) + deepcopy(b.get('items', []))
    a['source_section_ids'] = list(dict.fromkeys(a.get('source_section_ids', []) + b.get('source_section_ids', [])))
    a['merged_section_ids'] = list(dict.fromkeys(a.get('merged_section_ids', [target['section_id']])
                                               + b.get('merged_section_ids', [source['section_id']])))
    presentation['required_claim_roots'] = sorted(set(presentation.get('required_claim_roots', []))
                                                 | set((source.get('presentation') or {}).get('required_claim_roots', [])))
    if supporting:
        preferred = {claim_root_id(bank.get(cid, {'claim_id': cid})) for cid in source.get('core_claim_ids', [])}
        presentation.setdefault('supporting_context_groups', []).append({
            'source_section_id': source['section_id'], 'claim_roots': sorted(roots),
            'preferred_roots': sorted(preferred & roots), 'required_roots': sorted(roots & set(required))})
        presentation['supporting_claim_roots'] = sorted(set(presentation.get('supporting_claim_roots', [])) | roots)
    # A split source has separate owners for separate roots. Refill must not
    # copy its entire former module into every destination.
    for sid, assigned in (source.get('presentation') or {}).get('source_claim_roots', {}).items():
        current = presentation.setdefault('source_claim_roots', {}).setdefault(sid, [])
        presentation['source_claim_roots'][sid] = sorted(set(current) | set(assigned))
    from src.layout.editorial import _organize
    _organize(target)


def _claim_use(claim, kind, state, source_plan):
    from utils.source_context import evidence_contexts
    overlay = evidence_contexts(state).get('evidence', {})
    contexts = [overlay[e] for e in claim.get('evidence_ids', [])
                if overlay.get(e, {}).get('status') == 'located_body']
    if kind == 'method':
        return 'method', contexts
    explicit = source_plan.get('presentation_function')
    if explicit in {'method', 'evaluation', 'results'}:
        return explicit, contexts
    types = {c['section_type'] for c in contexts}
    if len(types) == 1 and types & {'evaluation', 'method'}:
        return next(iter(types)), contexts
    role = narrative_role(source_plan)
    return (role if role in {'method', 'theory', 'evaluation', 'results'} else ''), contexts


def context_pair(left, right, state):
    """Only coherent context/task definition; substantive insights stay separate."""
    plan = ordered_plan(state)
    roles = [section_role(s, state) for s in (left, right)]
    functions = [plan.get(str(s['section_id']), {}).get('presentation_function') for s in (left, right)]
    context = {'foundation', 'background', 'problem', 'motivation'}
    if roles[0] not in context:
        return False
    if functions[1] == 'research_insight':
        return False
    if roles[1] in context or functions[1] == 'task_definition':
        return True
    hints = (right.get('editorial') or {}).get('items', [])
    # Conservative legacy support: a definition-labelled problem, never an
    # unclassified insight or a dense independent formal statement.
    return (roles[1] == 'insight' and hints and
            all(h.get('kind') in {'definition', 'goal'} for h in hints)
            and len(right.get('claim_ids', [])) <= 2 and not right.get('visual_assets'))


def prepare_structure(board, state, family):
    """Necessity first, then context-supported attribution; no family IDs."""
    from src.layout.editorial import sections, locked
    from src.layout.editorial_selection import filter_board, required_roots
    result = deepcopy(board)
    report = {'version': PRESENTATION_POLICY_VERSION, 'merges': [], 'attributions': [],
              'unresolved_section_ids': [], 'classifications': {}}
    if state.get('generation_route') != 'optimization_family':
        return result, report
    if locked(state):
        report['reason'] = 'locked'
        return result, report
    result = filter_board(result, state)
    required = required_roots(result, state)
    bank = all_publishable_claims(state)
    plan = ordered_plan(state)
    for claim in bank.values():
        original = bank.get(claim_root_id(claim), claim)
        if (original.get('body_contract') != 'sample_body_v2' and
                set(claim_source_plan(original, plan).get('required_evidence_ids', [])).intersection(original.get('evidence_ids', []))):
            required.add(claim_root_id(claim))
    module_owned = bool(state.get('verified_module_board') and state.get('sample_module_plan'))
    for section in sections(result):
        policy = section.setdefault('presentation', {})
        assessment = auxiliary_assessment(section, state)
        report['classifications'][section['section_id']] = assessment
        policy['required_claim_roots'] = sorted(required & {claim_root_id(c) for c in _claims(section, state)[1]})
        was_auxiliary = (policy.get('original_auxiliary', assessment['auxiliary'])
                         if policy.get('version') == PRESENTATION_POLICY_VERSION else assessment['auxiliary'])
        policy.update(version=PRESENTATION_POLICY_VERSION, original_auxiliary=was_auxiliary)
    if module_owned:
        report['reason'] = 'verified_module_prose_ownership'
        report['unresolved_section_ids'] = [s['section_id'] for s in sections(result)
                                           if s['presentation']['original_auxiliary']]
        if report['unresolved_section_ids'] and (state.get('layout_revision_constraints')
                                                or not family.contract.allow_module_grouping):
            report['reason'] = 'locked_or_grouping_disabled'
        report['module_loads'] = [{'section_id': s['section_id'], 'claim_count': len(s.get('claim_ids', [])),
                                   'word_count': sum(len(t.split()) for t in s.get('text_content', []))}
                                  for s in sections(result)]
        return result, report
    if state.get('layout_revision_constraints') or not family.contract.allow_module_grouping:
        report['reason'] = 'locked_or_grouping_disabled'
        report['unresolved_section_ids'] = [s['section_id'] for s in sections(result)
            if (s.get('presentation') or {}).get('original_auxiliary')]
        return result, report
    for auxiliary in list(sections(result)):
        if len(report['merges']) >= 4 or not auxiliary['presentation']['original_auxiliary']:
            continue
        ordered = sections(result)
        position = ordered.index(auxiliary)
        hints = {h['claim_id']: h.get('kind') for h in (auxiliary.get('editorial') or {}).get('items', [])}
        owners = {}
        unresolved = False
        for cid in auxiliary['claim_ids']:
            claim = bank.get(cid, {'claim_id': cid})
            original = bank.get(claim_root_id(claim), claim)
            use, contexts = _claim_use(original, hints.get(cid), state, claim_source_plan(original, plan))
            compatible = {'results', 'evaluation'} if use in {'evaluation', 'results'} else {'method', 'theory'} if use in {'method', 'theory'} else set()
            candidates = []
            for target in ordered:
                if target is auxiliary or target['presentation']['original_auxiliary'] or section_role(target, state) not in compatible:
                    continue
                target_pos = ordered.index(target)
                between = ordered[min(position, target_pos) + 1:max(position, target_pos)]
                if any(not s['presentation']['original_auxiliary'] and section_role(s, state) not in compatible for s in between):
                    continue
                _, target_claims = _claims(target, state)
                target_contexts = [_claim_use(c, '', state, {})[1] for c in target_claims]
                anchors = {c['body_start_char'] for group in target_contexts for c in group}
                shared = any(c['body_start_char'] in anchors for c in contexts)
                # Context/use qualifies an owner first. Distance only resolves
                # a tie between scientifically compatible owners.
                candidates.append((not shared, abs(target_pos - position), target_pos, target))
            if not candidates:
                unresolved = True
                break
            target = min(candidates, key=lambda item: item[:3])[-1]
            owners.setdefault(target['section_id'], []).append(cid)
            report['attributions'].append({'claim_id': cid, 'into_section_id': target['section_id'],
                                           'basis': 'body_context_and_function' if contexts else 'legacy_planner_function'})
        owner_for = {cid: sid for sid, ids in owners.items() for cid in ids}
        for hint in (auxiliary.get('editorial') or {}).get('items', []):
            if hint.get('claim_id') in owner_for and any(
                    dep in owner_for and owner_for[dep] != owner_for[hint['claim_id']]
                    for dep in hint.get('requires_claim_ids', [])):
                unresolved = True
        if auxiliary.get('visual_assets') and len(owners) > 1:
            unresolved = True
        if unresolved:
            report['unresolved_section_ids'].append(auxiliary['section_id'])
            continue
        for owner, ids in owners.items():
            target = next(s for s in ordered if s['section_id'] == owner)
            part = deepcopy(auxiliary)
            pairs = [(cid, text) for cid, text in zip(auxiliary['claim_ids'], auxiliary['text_content']) if cid in ids]
            part['claim_ids'], part['text_content'] = [p[0] for p in pairs], [p[1] for p in pairs]
            part['core_claim_ids'] = [cid for cid in part.get('core_claim_ids', []) if cid in ids]
            roots = {claim_root_id(bank[cid]) for cid in ids}
            part['editorial']['items'] = [h for h in part['editorial'].get('items', []) if h.get('claim_id') in ids]
            part['curated_claim_roots'] = sorted(roots)
            part['presentation']['required_claim_roots'] = sorted(roots & required)
            part['presentation']['source_claim_roots'] = {auxiliary['section_id']: sorted(roots)}
            _merge_into(target, part, state, supporting=True, required=required)
            report['merges'].append({'section_id': auxiliary['section_id'], 'into_section_id': owner})
        ordered.remove(auxiliary)
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
    from src.layout.editorial_selection import dispositions, required_roots
    decisions = dispositions(board, state)
    required = required_roots(board, state)
    visible = {claim_root_id(c) for s in by_id.values() for c in _claims(s, state)[1]}
    for root, item in decisions.items():
        if root in required and root not in visible:
            problems.append({'code': 'REQUIRED_INFORMATION_LOST', 'claim_root_id': root})
        if item['disposition'] == 'omit' and root in visible:
            problems.append({'code': 'OMITTED_INFORMATION_RESTORED', 'claim_root_id': root})
    for sid, section in by_id.items():
        if not supporting_contexts_preserved(section, state):
            problems.append({'code': 'SUPPORTING_CONTEXT_LOST', 'section_id': sid})
        if is_auxiliary(section, state) or (section.get('presentation') or {}).get('original_auxiliary'):
            problems.append({'code': 'AUXILIARY_MODULE_STANDALONE', 'section_id': sid})
        support = set((section.get('presentation') or {}).get('supporting_claim_roots', []))
        roots = {claim_root_id(c) for c in _claims(section, state)[1]}
        if support and roots and roots.issubset(support):
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


def context_alternative(board, state, family):
    """One optional coherent context composition, sharing existing search seats."""
    from src.layout.editorial import sections, locked, _organize
    if (state.get('verified_module_board') or locked(state) or state.get('layout_revision_constraints')
            or not family.contract.allow_module_grouping):
        return None
    result = deepcopy(board)
    ordered = sections(result)
    for left, right in zip(ordered, ordered[1:]):
        if not context_pair(left, right, state):
            continue
        if right.get('visual_assets') or len(right.get('claim_ids', [])) > 3:
            continue
        _merge_into(left, right, state)
        left['section_title'] = 'Research Problem'
        left['editorial'].update(source_title='Research Problem', title_candidates=[])
        _organize(left)
        ordered.remove(right)
        return result
    return None
