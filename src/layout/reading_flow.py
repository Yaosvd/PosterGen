"""Shared presentation order, without inferring scientific relationships.

Primary paper-body sources establish precedence, with explicit Planner roles
as a legacy fallback. Only declared findings can be a separate entry point;
comparison branches and matrix cells remain independent sequences.
"""

from src.layout.family_contract import ordered_zones
from src.layout.paper_profile import narrative_role


READING_POLICY_VERSION = "family_reading_v4"
ROLE_RANK = {
    'foundation': 0, 'background': 0, 'problem': 1, 'motivation': 1,
    'insight': 1, 'method': 2, 'theory': 2, 'results': 3, 'evaluation': 3,
    'conclusion': 4, 'impact': 4, 'implications': 4, 'discussion': 4,
}


def planned_for_sections(state, sections):
    """Resolve regrouped IDs only from their explicit original Planner roles."""
    from src.layout.presentation_policy import ordered_plan
    originals = ordered_plan(state)
    if state.get('source_editorial_version') == 'source_editorial_v1':
        return originals
    from copy import deepcopy
    planned = deepcopy(originals)
    from src.layout.presentation_policy import section_sources
    for section in sections:
        sid = str(section.get('section_id'))
        sources = set(section_sources(section, state))
        roles = {narrative_role(originals.get(source, {})) for source in sources}
        if len(roles) == 1 and '' not in roles:
            source = min((originals[s] for s in sources if s in originals),
                         key=lambda s: s.get('source_order', 0))
            if sid not in sources:
                planned[sid] = {**source, 'section_id': sid, 'narrative_role': next(iter(roles))}
        elif sources:
            known = [originals[s] for s in sources if s in originals]
            if known:
                source = min(known, key=lambda s: s.get('source_order', 0))
                # Preserve mixed origins even when the surviving display ID was
                # an original source ID. It must not impersonate that one role.
                planned[sid] = {**source, 'section_id': sid, 'narrative_role': '',
                                'original_narrative_roles': sorted(roles),
                                'source_order_end': max(s.get('source_order', 0) for s in known)}
    return planned


def contract_for_spec(spec):
    from src.layout.families import LayoutFamilyRegistry
    from src.layout.family_contract import FamilyContract
    family_id = spec.get('family_id')
    if not family_id:
        return FamilyContract(reading='columns')
    try:
        return LayoutFamilyRegistry().get(family_id).contract
    except ValueError:
        return FamilyContract()  # An unregistered grammar cannot certify order.


def ordered_known(ids, role, key):
    """Sort classified slots, leaving unclassified modules in their own slots."""
    known = iter(sorted((sid for sid in ids if role(sid) in ROLE_RANK), key=key))
    return [next(known) if role(sid) in ROLE_RANK else sid for sid in ids]


def ordered_source(ids, source_order, key):
    """Unknown sources keep their slots instead of becoming a final stage."""
    known = iter(sorted((sid for sid in ids if sid in source_order), key=key))
    return [next(known) if sid in source_order else sid for sid in ids]


def presentation_zones(spec, contract):
    zones = spec.get('zones') or []
    if all('x' in z and 'y' in z for z in zones):
        return ordered_zones(zones, contract)
    return list(zones)


def reading_sequences(spec, contract):
    zones = presentation_zones(spec, contract)
    if not zones:
        # Legacy/partial inputs can expose order, but cannot establish a hero
        # exemption or independent branches without actual zone ownership.
        return [list(spec.get('reading_order') or [])]
    if contract.reading in {'parallel', 'matrix'}:
        return [list(z.get('section_ids') or []) for z in zones]
    if contract.entry_roles:
        heroes = [list(z.get('section_ids') or []) for z in zones if z.get('role') == 'hero']
        body = [sid for z in zones if z.get('role') != 'hero' for sid in z.get('section_ids', [])]
        return [*heroes, body]
    return [[sid for z in zones for sid in z.get('section_ids', [])]]


def reading_conflicts(spec, contract, role, order=None):
    conflicts = []
    for sequence in reading_sequences(spec, contract):
        if order is not None:
            known = [sid for sid in sequence if sid in order]
            conflicts.extend((a, b) for a, b in zip(known, known[1:]) if order[a] > order[b])
            continue
        known = [sid for sid in sequence if role(sid) in ROLE_RANK]
        conflicts.extend((a, b) for a, b in zip(known, known[1:])
                         if ROLE_RANK[role(a)] > ROLE_RANK[role(b)])
    return conflicts


def analyze_reading(spec, contract, planned):
    """Text-free evidence used by both fitting and the ordinary Critic."""
    if any(s.get('source_editorial_version') == 'source_editorial_v1' for s in planned.values()):
        return {'policy_version': 'visual_natural_reading_v1', 'scope_status': 'requires_actual_image',
            'ordering_basis': 'visual_model', 'conflicts': [], 'source_order_conflicts': [],
            'actual_reading_order': [], 'sequences': [], 'role_ranks': [],
            'declared_order_matches_positions': None, 'positions_complete': bool(spec.get('zones')),
            'unknown_role_section_ids': [], 'anchor_section_ids': [], 'traversal': 'not_fixed'}
    role = lambda sid: narrative_role(planned.get(str(sid), {}))
    source_ordered = any(s.get('source_order_provenance') == 'evidence_source' for s in planned.values())
    order = {sid: s['source_order'] for sid, s in planned.items()
             if s.get('source_order_provenance') == 'evidence_source'} if source_ordered else None
    sequences = reading_sequences(spec, contract)
    zones = presentation_zones(spec, contract)
    actual = ([sid for z in zones for sid in z.get('section_ids', [])]
              if zones else list(spec.get('reading_order') or []))
    unknown = [sid for sid in actual if role(sid) not in ROLE_RANK]
    positions_complete = bool(zones) and all('x' in z and 'y' in z for z in zones)
    return {
        'policy_version': READING_POLICY_VERSION,
        'traversal': contract.reading,
        'positions_complete': positions_complete,
        'scope_status': ('partial' if unknown or not positions_complete or
                         (order is not None and any(sid not in order for sid in actual)) else 'checked'),
        'actual_reading_order': actual,
        'declared_order_matches_positions': list(spec.get('reading_order') or []) == actual,
        'sequences': sequences,
        'role_ranks': [ROLE_RANK.get(role(sid)) for sid in actual],
        'unknown_role_section_ids': unknown,
        'ordering_basis': 'paper_body_sources' if source_ordered else 'legacy_roles_and_plan',
        'source_order_conflicts': [list(pair) for pair in reading_conflicts(spec, contract, role, order)] if order is not None else [],
        'conflicts': [list(pair) for pair in reading_conflicts(spec, contract, role, order)],
        'anchor_section_ids': [sid for z in zones if z.get('role') == 'hero'
                               and contract.entry_roles
                               for sid in z.get('section_ids', [])],
    }


def reassign_reading(spec, selected, priorities, contract, *, fits, pins, allowed,
                     maximum_states=256):
    """Find bounded, order-preserving partitions of the exact visible modules.

    Keeps topology, hero ownership, every module/claim/visual and all pins. The
    caller supplies exact height checks; the resulting layout still compiles
    and passes ordinary preflight. No wording, geometry or typography changes.
    """
    from copy import deepcopy
    if getattr(priorities, 'visual_reading', False):
        return None, {'status': 'delegated_to_visual_model', 'states': 0}

    zones = ordered_zones(spec['zones'], contract)
    body = [z for z in zones if not (contract.entry_roles
                                    and z.get('role') == 'hero')]
    if contract.reading in {'parallel', 'matrix'}:
        return None, {'status': 'independent_sequences', 'states': 0}
    ids = [sid for z in body for sid in z.get('section_ids', [])]
    role = lambda sid: priorities.role(selected[sid])
    ordered = (ordered_source(ids, priorities.source_order, lambda sid: priorities.rank(selected[sid])) if priorities.source_ordered
               else ordered_known(ids, role, lambda sid: priorities.rank(selected[sid])))
    prior = {sid: z['zone_id'] for z in body for sid in z.get('section_ids', [])}
    states, complete = 0, []

    def search(index, cursor, assignments):
        nonlocal states
        if states >= maximum_states:
            return
        states += 1
        if index == len(body):
            if cursor == len(ordered):
                moved = sum(prior[sid] != zid for zid, items in assignments.items() for sid in items)
                complete.append((moved, deepcopy(assignments)))
            return
        zone = body[index]
        zid = zone['zone_id']
        remaining = body[index + 1:]
        capacity = int(zone.get('capacity', 1))
        minimum = max(bool(zone.get('section_ids')), len(ordered) - cursor
                      - sum(int(z.get('capacity', 1)) for z in remaining))
        maximum = min(capacity, len(ordered) - cursor
                      - sum(bool(z.get('section_ids')) for z in remaining))
        for count in sorted(range(int(minimum), maximum + 1),
                            key=lambda n: (abs(n - len(zone.get('section_ids', []))), n)):
            items = ordered[cursor:cursor + count]
            if any((sid in pins and pins[sid] != zid) or not allowed(sid, zid) for sid in items):
                continue
            if not fits(zid, items):
                continue
            assignments[zid] = items
            search(index + 1, cursor + count, assignments)
            assignments.pop(zid)

    search(0, 0, {})
    audit = {'status': 'no_safe_assignment', 'states': states,
             'state_limit': maximum_states, 'limit_reached': states >= maximum_states}
    if not complete:
        return None, audit
    _, assignments = min(complete, key=lambda item: (item[0], tuple(
        tuple(item[1][z['zone_id']]) for z in body)))
    result = deepcopy(spec)
    for zone in result['zones']:
        if zone['zone_id'] in assignments:
            zone['section_ids'] = assignments[zone['zone_id']]
    result['zones'] = ordered_zones(result['zones'], contract)
    result['reading_order'] = [sid for z in result['zones'] for sid in z.get('section_ids', [])]
    if reading_conflicts(result, contract, role, priorities.source_order if priorities.source_ordered else None):
        return None, audit
    return result, {**audit, 'status': 'adopted', 'moved_section_ids': sorted(
        sid for zid, items in assignments.items() for sid in items if prior[sid] != zid)}
