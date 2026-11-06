"""Bounded measured transfers across shared region cuts in any layout family.

Region transfers keep authored weights. A separate bounded module-height pass
can coordinate weights within a region; prose, ownership, order, directions,
capacities, merge provenance and gutters remain intact.
"""
from copy import deepcopy

from src.layout.families import LayoutFamilyRegistry, valid_family_topology
from src.layout.region_merges import geometry_record
from utils.persistence import digest

AXES = (('x', 'width', 'y', 'height'), ('y', 'height', 'x', 'width'))


def _overlap(a, b, cross, extent):
    return min(a[cross]+a[extent], b[cross]+b[extent])-max(a[cross], b[cross]) > 1e-6


def shared_cuts(zones):
    """Collect actual neighbors, including both sides of spanning regions."""
    cuts = []
    for along, extent, cross, cross_extent in AXES:
        for start in sorted({round(z[along], 6) for z in zones if z[along] > 0}):
            after = [z for z in zones if abs(z[along]-start) < 1e-6]
            ends = sorted({round(z[along]+z[extent], 6) for z in zones
                           if -1e-6 <= start-z[along]-z[extent] <= .08})
            for end in ends:
                pairs = [(a['zone_id'], b['zone_id']) for a in zones for b in after
                         if abs(a[along]+a[extent]-end) < 1e-6
                         and _overlap(a, b, cross, cross_extent)]
                if pairs:
                    cuts.append({'along': along, 'extent': extent, 'gap': start-end,
                                 'before': {a for a, _ in pairs},
                                 'after': {b for _, b in pairs}, 'pairs': pairs})
    return cuts


def _needs(state, candidate, zones, baseline):
    """Minimum measured row demand, respecting each authored height share.

    Horizontal image rows expose alternative exact, readable splits. A current
    full-height image therefore does not hide the space it could safely donate.
    Width demand is only a search estimate; fast/exact measurements decide fit.
    """
    from src.agents.layout_agent import LayoutAgent
    agent = LayoutAgent()
    body_height = (float(state['poster_height'])-2*agent.poster_margin)*(1-agent.title_height_fraction)
    gap = agent._inter_section_spacing(state)
    modules = {m['module_id']: m for m in candidate['modules']}
    needs = {}
    for zone in zones:
        rows = [m for m in baseline['report']['modules'] if m['zone_id'] == zone['zone_id']]
        weights = sum(modules[m['module_id']]['space_weight'] for m in rows)
        required = max(m.get('minimum_intrinsic_height', m['intrinsic_height'])*weights /
                       modules[m['module_id']]['space_weight'] for m in rows)
        required += gap*max(0, len(rows)-1)
        needs[zone['zone_id']] = {
            'height': required/body_height,
            'width': zone['width']*max(m.get('minimum_intrinsic_height', m['intrinsic_height']) /
                                      m['allocated_height'] for m in rows)}
    return needs


def _transfer(before, after):
    # Positive pressure needs space, negative pressure can donate it. Move enough
    # to satisfy a deficit where possible, without treating a donor as unlimited.
    if before > 0 > after:
        return min(before, -after)
    if after > 0 > before:
        return -min(after, -before)
    return (before-after)/2


def _apply(zones, moves):
    trial = deepcopy(zones)
    for cut, delta in moves:
        for zone in trial:
            if zone['zone_id'] in cut['before']:
                zone[cut['extent']] += delta
            if zone['zone_id'] in cut['after']:
                zone[cut['along']] += delta
                zone[cut['extent']] -= delta
    for zone in trial:
        for key in ('x', 'y', 'width', 'height'):
            zone[key] = round(zone[key], 6)
    return trial


def _limit_donations(zones, moves, needs):
    """Coupled cuts must share a donor's one measured spare-space budget."""
    moves = list(moves)
    for extent in ('width', 'height'):
        factor = 1.0
        for zone in zones:
            change = sum(delta*((zone['zone_id'] in cut['before']) -
                                (zone['zone_id'] in cut['after']))
                         for cut, delta in moves if cut['extent'] == extent)
            if change < -1e-9:
                spare = max(0, zone[extent]-needs[zone['zone_id']][extent]-.00001)
                factor = min(factor, spare/-change)
        # A common factor per axis keeps compensating inflows/outflows coupled;
        # limiting donors one at a time can invalidate an earlier donor's inflow.
        moves = [(cut, delta*factor if cut['extent'] == extent else delta) for cut, delta in moves]
    return moves


def _contacts_preserved(trial, cuts):
    boxes = {z['zone_id']: z for z in trial}
    for cut in cuts:
        along, extent = cut['along'], cut['extent']
        cross, cross_extent = ('y', 'height') if along == 'x' else ('x', 'width')
        for a, b in cut['pairs']:
            a, b = boxes[a], boxes[b]
            if (not _overlap(a, b, cross, cross_extent) or
                    abs(b[along]-a[along]-a[extent]-cut['gap']) > 2e-6):
                return False
    return True


def redistribute_candidates(state, candidate, zones, baseline, *, maximum=12):
    family = LayoutFamilyRegistry().get(state['sample_family']['family'])
    cuts = shared_cuts(zones)
    needs = _needs(state, candidate, zones, baseline)
    originals = {z['zone_id']: z for z in zones}
    moves = []
    for cut in cuts:
        extent = cut['extent']
        before = max(needs[sid][extent]-originals[sid][extent] for sid in cut['before'])
        after = max(needs[sid][extent]-originals[sid][extent] for sid in cut['after'])
        delta = max(-.08, min(.08, _transfer(before, after)))
        if abs(delta) > 1e-6:
            moves.append((cut, delta))
    proposals = []
    # Coupled boundaries let a middle donor serve both neighboring rows in one
    # candidate. Both axes work for grids, sidebars and protected spanning bands.
    for factor in (1, .5):
        proposals.append([(cut, delta*factor) for cut, delta in moves])
        for along in ('x', 'y'):
            proposals.append([(cut, delta*factor) for cut, delta in moves if cut['along'] == along])
    for cut, delta in sorted(moves, key=lambda move: -abs(move[1])):
        for amount in (delta, delta/2, .025 if delta > 0 else -.025, -.025 if delta > 0 else .025):
            proposals.append([(cut, amount)])
    seen, ranked = {digest(geometry_record(zones))}, []
    for order, proposal in enumerate(proposals):
        trial = _apply(zones, _limit_donations(zones, proposal, needs))
        if not valid_family_topology(family, trial) or not _contacts_preserved(trial, cuts):
            continue
        # A zone may participate in several cuts. Bound final edge displacement,
        # not just each individual operation, so joint moves cannot evade limits.
        if any(abs(z[key]+(z[ext] if end else 0)-originals[z['zone_id']][key] -
                   (originals[z['zone_id']][ext] if end else 0)) > .080002
               for z in trial for key, ext in (('x','width'), ('y','height')) for end in (False, True)):
            continue
        key = digest(geometry_record(trial))
        if key in seen:
            continue
        seen.add(key)
        # Pressure is a proposal ranking only; no estimate certifies delivery.
        score = sum(max(0, needs[z['zone_id']][axis]-z[axis])**2
                    for z in trial for axis in ('width','height'))
        ranked.append((score, order, trial))
    ranked.sort(key=lambda row: row[:2])
    return [row[2] for row in ranked[:min(12, max(0, maximum))]]


HEIGHT_ALLOCATION_VERSION = 'editorial_height_allocation_v1'
HEIGHT_ALLOCATION_LIMIT = 3


def module_height_candidates(state, candidate, baseline):
    """Propose only height transfers from underfilled peers to overflowing ones.

    Minimum demand includes vertical image growth and readable horizontal plans.
    Estimates propose weights, never certify fit. Legal weights bound the ratio
    of any two module heights to three; clip the transfer, not individual weights.
    """
    from src.workflow.editorial_contract import normalize_candidate
    rows = baseline['report']['modules']
    grouped = {}
    for row in rows:
        grouped.setdefault(row['zone_id'], []).append(row)
    seen, proposals = {candidate['candidate_id']}, []
    # A little receiving headroom, minimum demand, then a partial transfer.
    for target_usage, fraction in ((.975, 1.0), (1.0, 1.0), (.975, .5)):
        weights = {}
        for peers in grouped.values():
            receivers = [r for r in peers if r['overage_inches'] > .01]
            donors = [r for r in peers if r['utilization'] < .9]
            if not receivers or not donors:
                continue
            heights = {r['module_id']: r['allocated_height'] for r in peers}
            demand = {r['module_id']: r.get('minimum_intrinsic_height', r['intrinsic_height'])
                      for r in peers}
            deficits = {r['module_id']: max(0, demand[r['module_id']]/target_usage -
                                           r['allocated_height']) for r in receivers}
            spare = {r['module_id']: max(0, r['allocated_height'] - demand[r['module_id']])
                     for r in donors}
            needed, available = sum(deficits.values()), sum(spare.values())
            if min(needed, available) <= .01:
                continue
            transfer = fraction*min(needed, available)
            delta = {mid: transfer*deficits.get(mid, 0)/needed -
                          transfer*spare.get(mid, 0)/available for mid in heights}
            alpha = 1.0
            for a in heights:
                for b in heights:
                    slope = delta[a]-3*delta[b]
                    if slope > 0:
                        alpha = min(alpha, max(0, (3*heights[b]-heights[a])/slope))
            if alpha*transfer <= .01:
                continue
            # Stay inside the closed 1..3 contract despite floating-point noise.
            alpha *= 1-1e-10
            target = {mid: h+alpha*delta[mid] for mid, h in heights.items()}
            scale = min(target.values())
            weights.update({mid: min(3.0, h/scale) for mid, h in target.items()})
        if not weights:
            continue
        raw = deepcopy(candidate)
        for module in raw['modules']:
            if module['module_id'] in weights:
                module['space_weight'] = weights[module['module_id']]
        proposed = normalize_candidate(raw, state, baseline['spec']['zones'])
        if proposed['candidate_id'] not in seen:
            seen.add(proposed['candidate_id'])
            proposals.append(proposed)
    return proposals[:HEIGHT_ALLOCATION_LIMIT]


def coordinate_module_heights(state, candidate, baseline):
    """At most three exact weight trials, with no state or authored-text mutation."""
    from src.layout.editorial_composition import VERSION, directions
    from src.layout.editorial_layout import measure
    from src.layout.whitespace import no_added_whitespace
    before = baseline['report']
    proposals = module_height_candidates(state, candidate, baseline)
    # First fitting may not have persisted its direction receipt yet. Preserve
    # the already chosen regional fit's directions throughout these weight trials.
    view = dict(state)
    if view.get('editorial_composition') is None:
        view['editorial_composition'] = {'version': VERSION,
            'input_digest': digest({'candidate': candidate, 'spec': baseline['spec']}),
            'modules': directions(candidate, baseline['layout'])}
    best, selected = baseline, candidate
    old_rows = {r['module_id']: r for r in before['modules']}
    trials = []
    # Removing a collision may create a normal inter-module gap. Check total
    # unused area, largest hole and bottom whitespace, not a zero gap caused by
    # the collision itself. Never optimize pure underfill by relocating blanks.
    space_keys = ('empty_body_fraction', 'unallocated_body_fraction',
                  'largest_empty_rectangle_fraction', 'mean_terminal_bottom_gap_inches',
                  'maximum_terminal_bottom_gap_inches', 'full_width_bottom_gap_inches')
    for proposed in proposals:
        trial = measure(view, proposed, baseline['spec']['zones'])
        report = trial['report']
        reasons = []
        if report['total_overflow_inches'] >= before['total_overflow_inches']-1e-6:
            reasons.append('no_overflow_reduction')
        if any(r['overage_inches'] > old_rows[r['module_id']]['overage_inches']+1e-6
               for r in report['modules']):
            reasons.append('module_overflow_regression')
        if report['total_underfill_inches'] > before['total_underfill_inches']+1e-6:
            reasons.append('underfill_regression')
        if before['preflight']['passed'] and not report['preflight']['passed']:
            reasons.append('preflight_regression')
        if not no_added_whitespace(
                {k: before['composition_whitespace'].get(k) for k in space_keys},
                {k: report['composition_whitespace'].get(k) for k in space_keys}):
            reasons.append('whitespace_regression')
        trials.append({'candidate_id': proposed['candidate_id'],
            'weights': {m['module_id']: m['space_weight'] for m in proposed['modules']},
            'total_overflow_inches': report['total_overflow_inches'],
            'total_underfill_inches': report['total_underfill_inches'],
            'empty_body_fraction': report['composition_whitespace']['empty_body_fraction'],
            'rejection_reasons': reasons})
        def rank(r):
            return (not r['passed'], r['total_overflow_inches'], r['total_underfill_inches'])
        if not reasons and rank(report) < rank(best['report']):
            best, selected = trial, proposed
    # Return detached records even on no-op; callers may persist/annotate them.
    best = deepcopy(best)
    best['candidate'] = deepcopy(selected)
    best['report']['height_allocation'] = {'version': HEIGHT_ALLOCATION_VERSION,
        'status': 'adopted' if selected != candidate else 'no_safe_gain' if proposals else 'not_needed',
        'exact_trial_limit': HEIGHT_ALLOCATION_LIMIT, 'trials': trials,
        'from_candidate_id': candidate['candidate_id'], 'to_candidate_id': selected['candidate_id'],
        'before_weights': {m['module_id']: m['space_weight'] for m in candidate['modules']},
        'after_weights': {m['module_id']: m['space_weight'] for m in selected['modules']}}
    if selected != candidate:
        best['allocation_baseline_report'] = {'modules': deepcopy(before['modules'])}
    return best
