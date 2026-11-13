"""Fixed family routes and nonblocking reading diagnostics, never prose sorting."""
from collections import Counter

VERSION = 'editorial_reading_routes_v1'
STAGES = ('background', 'method', 'results')
STAGE_LIMITS = {'background': 1, 'results': 2}
ROUTES = {
    'classic_three_column': ('left', 'middle', 'right'),
    'asymmetric_two_column': ('narrative_rail', 'evidence_field'),
    'four_column_modular': tuple(f'column_{i}' for i in range(1, 5)),
    'central_hero_side_rails': ('left_rail', 'central_hero', 'right_rail'),
    'top_hero_bottom_grid': ('top_hero', 'bottom_left', 'bottom_middle', 'bottom_right'),
    'horizontal_narrative_bands': tuple(f'band_{i}' for i in range(1, 5)),
    'method_flow_spine': ('left_top', 'left_bottom', 'flow_spine', 'right_top', 'right_bottom'),
    'comparison_split': ('comparison_a', 'comparison_b', 'shared_conclusion'),
    'result_dashboard_cards': ('primary_result', 'context', 'method', 'result_card_1', 'result_card_2', 'result_card_3'),
    'small_multiples_matrix': tuple(f'cell_{r}_{c}' for r in (1, 2) for c in (1, 2, 3)),
    'timeline_stage_narrative': tuple(f'stage_{i}' for i in range(1, 5)),
    'modular_editorial_mosaic': ('lead', 'upper_right', 'middle_right', 'lower_left', 'lower_middle', 'lower_right'),
    'framed_multicolumn': ('overview', 'body_left', 'body_middle', 'body_right', 'conclusion'),
    'narrative_evidence_grid': ('narrative_rail', 'evidence_1_1', 'evidence_1_2', 'evidence_2_1', 'evidence_2_2', 'conclusion'),
    'central_evidence_band': ('top_left', 'top_right', 'central_evidence', 'bottom_left', 'bottom_middle', 'bottom_right'),
}


def consecutive(contract, members):
    """Legacy grammars without an explicit route keep their own merge policy."""
    route = contract.reading_route
    if not route:
        return True
    if len(set(members)) != len(members) or any(mid not in route for mid in members):
        return False
    indices = sorted(route.index(mid) for mid in members)
    return indices == list(range(indices[0], indices[0] + len(indices)))


def region_order(family, zones):
    return ordered_region_ids(family.contract, zones)


def ordered_region_ids(contract, zones):
    route = contract.reading_route
    if not route:
        raise ValueError('Editorial family must declare an explicit reading route')
    covered, positions = [], {}
    for zone in zones:
        members = zone.get('merged_from') or [zone['zone_id']]
        if not consecutive(contract, members):
            raise ValueError('Merged regions must be consecutive in the family reading route')
        covered.extend(members)
        positions[zone['zone_id']] = min(route.index(mid) for mid in members)
    if len(positions) != len(zones) or len(set(covered)) != len(covered) or set(covered) != set(route):
        raise ValueError('Reading route must cover every original region exactly once')
    return sorted(positions, key=positions.get)


def route_brief(family, zones):
    order = region_order(family, zones)
    labels = ({'primary_result': 'Upper-left lead area', 'context': 'Upper-right area',
               'method': 'Middle-right area', 'result_card_1': 'Lower-left area',
               'result_card_2': 'Lower-middle area', 'result_card_3': 'Lower-right area'}
              if family.family_id == 'result_dashboard_cards' else
              {zid: zid.replace('_', ' ') for zid in family.contract.reading_route})
    by_id = {z['zone_id']: z for z in zones}
    return {'version': VERSION, 'region_order': order,
            'within_region': 'top_to_bottom', 'stage_order': list(STAGES),
            'suggested_modules': {'background': [1], 'results': [1, 2]},
            'maximum_modules_by_stage': dict(STAGE_LIMITS),
            'order_errors': 'record_only_no_retry_or_reordering',
            'region_labels': {zid: ' / '.join(labels[mid] for mid in
                (by_id[zid].get('merged_from') or [zid])) for zid in order}}



def geometry_order_issues(family, zones):
    """Detect reversed canonical spatial relations without rejecting the sample."""
    owners = {mid: z for z in zones for mid in (z.get('merged_from') or [z['zone_id']])}
    issues = []
    for i, first in enumerate(family.zones):
        for second in family.zones[i+1:]:
            for along, extent, cross, cross_extent in (('x','width','y','height'), ('y','height','x','width')):
                if min(first[cross]+first[cross_extent], second[cross]+second[cross_extent]) <= max(first[cross], second[cross])+1e-6:
                    continue
                a,b = sorted((first,second), key=lambda z:z[along])
                if a[along]+a[extent] > b[along]+1e-6:
                    continue
                actual_a,actual_b = owners[a['zone_id']],owners[b['zone_id']]
                if actual_a is actual_b:
                    continue
                if actual_a[along]+actual_a[extent] > actual_b[along]+1e-6:
                    issue = {'code':'geometry_route_conflict', 'before_zone':actual_a['zone_id'],
                             'after_zone':actual_b['zone_id'], 'axis':along}
                    if issue not in issues:
                        issues.append(issue)
    return issues


def reading_report(family, zones, modules):
    route = route_brief(family, zones)
    actual = [m for zid in route['region_order'] for m in modules if m['zone_id'] == zid]
    declared_ids = [m['module_id'] for m in modules]
    actual_ids = [m['module_id'] for m in actual]
    issues = geometry_order_issues(family, zones)
    unknown = [m['module_id'] for m in modules if m['zone_id'] not in route['region_order']]
    if unknown:
        issues.append({'code': 'unknown_regions', 'module_ids': unknown})
    if declared_ids != actual_ids:
        issues.append({'code': 'array_route_mismatch', 'declared_order': declared_ids,
                       'spatial_order': actual_ids})
    for before, after in zip(actual, actual[1:]):
        a, b = before.get('narrative_stage'), after.get('narrative_stage')
        if a in STAGES and b in STAGES and STAGES.index(a) > STAGES.index(b):
            issues.append({'code': 'stage_regression', 'before_module': before['module_id'],
                           'after_module': after['module_id'], 'before_stage': a, 'after_stage': b,
                           'before_zone': before['zone_id'], 'after_zone': after['zone_id']})
    return {**route, 'declared_module_order': declared_ids, 'spatial_module_order': actual_ids,
            'module_stages': {m['module_id']: m.get('narrative_stage') for m in modules},
            'stage_counts': dict(Counter(m.get('narrative_stage', 'unknown') for m in modules)),
            'issues': issues, 'status': 'issues_recorded' if issues else 'structure_consistent',
            'scientific_content_verified': False, 'visual_readability_verified': False}
