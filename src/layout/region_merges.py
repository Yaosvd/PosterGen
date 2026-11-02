"""Nonrecursive, disjoint pair merges of ordinary family regions."""

from copy import deepcopy
from itertools import combinations


def geometry_record(zones):
    return [{key: z.get(key) for key in
             ('zone_id', 'x', 'y', 'width', 'height', 'role', 'capacity', 'merged_from')}
            for z in zones]


def protected_regions(family):
    return set(family.contract.required_zones) | set(family.contract.protected_spans)


def pair_axis(first, second):
    """Return an aligned adjacency axis; gaps are normalized body units."""
    for axis, cross, extent, cross_extent in (
        ('horizontal', 'y', 'width', 'height'),
        ('vertical', 'x', 'height', 'width'),
    ):
        along = 'x' if axis == 'horizontal' else 'y'
        if (abs(float(first[cross]) - float(second[cross])) > 1e-6
                or abs(float(first[cross_extent]) - float(second[cross_extent])) > 1e-6):
            continue
        before, after = sorted((first, second), key=lambda z: float(z[along]))
        gap = float(after[along]) - float(before[along]) - float(before[extent])
        if -1e-6 <= gap <= .06 + 1e-6:
            return axis
    return None


def eligible_pairs(family, zones):
    if not family.contract.allow_span:
        return []
    protected = protected_regions(family)
    ordinary = [z for z in zones if z.get('role') == 'support'
                and z['zone_id'] not in protected and z.get('capacity') == 1
                and not z.get('merged_from')]
    return [(a, b, axis) for a, b in combinations(ordinary, 2)
            if (axis := pair_axis(a, b)) is not None]


def merge_candidates(family, zones):
    """Merge one or two disjoint original pairs, never a merge result."""
    if any(z.get('merged_from') for z in zones):
        return []
    pairs = eligible_pairs(family, zones)
    candidates = []
    for count in (1, 2):
        for choices in combinations(pairs, count):
            members = [z['zone_id'] for a, b, _ in choices for z in (a, b)]
            if len(set(members)) != 2 * count:
                continue
            changed = deepcopy(list(zones))
            trace = []
            names = []
            for a, b, axis in choices:
                kept = next(z for z in changed if z['zone_id'] == a['zone_id'])
                x, y = min(a['x'], b['x']), min(a['y'], b['y'])
                right = max(a['x'] + a['width'], b['x'] + b['width'])
                bottom = max(a['y'] + a['height'], b['y'] + b['height'])
                kept.update(x=x, y=y, width=round(right-x, 6), height=round(bottom-y, 6),
                            capacity=2, merged_from=[a['zone_id'], b['zone_id']])
                changed = [z for z in changed if z['zone_id'] != b['zone_id']]
                trace.extend(['span_adjacent_zones', axis, a['zone_id'], b['zone_id']])
                names.append(f"{a['zone_id']}_{b['zone_id']}")
            candidates.append(('span_' + '__'.join(names), changed, trace))
    return candidates


def valid_region_membership(family, zones):
    """No omitted regions, inflated capacities, splits or forged merge chains."""
    originals = {z['zone_id']: z for z in family.zones}
    protected = protected_regions(family)
    covered = []
    merge_count = 0
    for zone in zones:
        identity = zone.get('zone_id')
        if identity not in originals or zone.get('role') != originals[identity].get('role'):
            return False
        capacity = zone.get('capacity')
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            return False
        members = zone.get('merged_from')
        if members is None:
            if capacity > int(originals[identity]['capacity']):
                return False
            covered.append(identity)
            continue
        if (not family.contract.allow_span or not isinstance(members, list)
                or len(members) != 2 or any(not isinstance(m, str) for m in members)
                or len(set(members)) != 2
                or identity != members[0] or capacity != 2
                or any(not isinstance(m, str) or m not in originals for m in members)):
            return False
        a, b = (originals[m] for m in members)
        if (any(m in protected for m in members) or a.get('role') != 'support'
                or b.get('role') != 'support' or a['capacity'] != 1 or b['capacity'] != 1
                or pair_axis(a, b) is None):
            return False
        merge_count += 1
        covered.extend(members)
    return (merge_count <= 2 and len(covered) == len(set(covered))
            and set(covered) == set(originals))
