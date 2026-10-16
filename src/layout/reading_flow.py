"""Shared presentation order, without inferring scientific relationships.

Only explicit NarrativePlanner roles establish precedence. A leading visual or
takeaway is a separate entry point; comparison branches and matrix cells are
independent sequences. Unknown roles never become a synthetic final stage.
"""

from src.layout.family_contract import ordered_zones
from src.layout.paper_profile import narrative_role


READING_POLICY_VERSION = "family_reading_v2"
ROLE_RANK = {
    'foundation': 0, 'background': 0, 'problem': 1, 'motivation': 1,
    'insight': 1, 'method': 2, 'theory': 2, 'results': 3, 'evaluation': 3,
    'conclusion': 4, 'impact': 4, 'implications': 4, 'discussion': 4,
}


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


def presentation_zones(spec, contract):
    zones = spec.get('zones') or []
    if all('x' in z and 'y' in z for z in zones):
        return ordered_zones(zones, contract)
    return list(zones)


def reading_sequences(spec, contract):
    zones = presentation_zones(spec, contract)
    if contract.reading == 'neutral':
        return []
    if not zones:
        # Legacy/partial inputs can expose order, but cannot establish a hero
        # exemption or independent branches without actual zone ownership.
        return [list(spec.get('reading_order') or [])]
    if contract.reading in {'parallel', 'matrix'}:
        return [list(z.get('section_ids') or []) for z in zones]
    if contract.reading in {'anchor_first', 'spine'}:
        heroes = [list(z.get('section_ids') or []) for z in zones if z.get('role') == 'hero']
        body = [sid for z in zones if z.get('role') != 'hero' for sid in z.get('section_ids', [])]
        return [*heroes, body]
    return [[sid for z in zones for sid in z.get('section_ids', [])]]


def reading_conflicts(spec, contract, role):
    conflicts = []
    for sequence in reading_sequences(spec, contract):
        known = [sid for sid in sequence if role(sid) in ROLE_RANK]
        conflicts.extend((a, b) for a, b in zip(known, known[1:])
                         if ROLE_RANK[role(a)] > ROLE_RANK[role(b)])
    return conflicts


def analyze_reading(spec, contract, planned):
    """Text-free evidence used by both fitting and the ordinary Critic."""
    role = lambda sid: narrative_role(planned.get(str(sid), {}))
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
        'scope_status': ('neutral' if contract.reading == 'neutral' else
                         'partial' if unknown or not positions_complete else 'checked'),
        'actual_reading_order': actual,
        'declared_order_matches_positions': list(spec.get('reading_order') or []) == actual,
        'sequences': sequences,
        'role_ranks': [ROLE_RANK.get(role(sid)) for sid in actual],
        'unknown_role_section_ids': unknown,
        'conflicts': [list(pair) for pair in reading_conflicts(spec, contract, role)],
        'anchor_section_ids': [sid for z in zones if z.get('role') == 'hero'
                               and contract.reading in {'anchor_first', 'spine'}
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

    zones = ordered_zones(spec['zones'], contract)
    body = [z for z in zones if not (contract.reading in {'anchor_first', 'spine'}
                                    and z.get('role') == 'hero')]
    if contract.reading in {'neutral', 'parallel', 'matrix'}:
        return None, {'status': 'independent_sequences', 'states': 0}
    ids = [sid for z in body for sid in z.get('section_ids', [])]
    role = lambda sid: priorities.role(selected[sid])
    ordered = ordered_known(ids, role, lambda sid: priorities.rank(selected[sid]))
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
    if reading_conflicts(result, contract, role):
        return None, audit
    return result, {**audit, 'status': 'adopted', 'moved_section_ids': sorted(
        sid for zid, items in assignments.items() for sid in items if prior[sid] != zid)}
