"""Diagnose whole-plan failures before choosing a field-only format repair.

Only explicit planning failures purchase the existing shared planning adjustment.
This is not a scientific coverage checker or a relaxed acceptance schema.
"""
from collections import Counter
from copy import deepcopy

from jsonschema import Draft202012Validator

from src.workflow.editorial_contract import EditorialOutputError, asset_index, module_limits

VERSION = 'editorial_planning_feedback_v1'


class EditorialPlanningError(EditorialOutputError):
    def __init__(self, draft, feedback):
        self.draft = deepcopy(draft)
        self.feedback = deepcopy(feedback)
        super().__init__('Invalid Curator plan: ' + '; '.join(i['message'] for i in feedback['issues']))


def check_plan(raw, state, zones, schema, *, allow_underfull):
    """Aggregate inspectable planning errors; ordinary malformed fields stay local.

Relax only the constraints diagnosed here to inspect an otherwise well-shaped
plan. The original schema and normalize_plan still validate every accepted reply.
Visual selection errors alone retain the existing scoped field repair; when a
whole-plan error coexists, include ownership diagnostics in that same feedback.
"""
    shape = deepcopy(schema)
    modules_shape = shape['properties']['modules']
    modules_shape.pop('minItems', None)
    modules_shape.pop('maxItems', None)
    props = modules_shape['items']['properties']
    props['zone_id'].pop('enum', None)
    shape['properties']['core_module_ids'].pop('maxItems', None)
    props['visual_ids'].pop('uniqueItems', None)
    props['visual_ids'].pop('maxItems', None)
    props['visual_ids']['items'].pop('enum', None)
    if not Draft202012Validator(shape).is_valid(raw):
        return  # Let the existing schema/field-repair path handle malformed data.

    modules = raw['modules']
    minimum, maximum = module_limits(zones)
    ids = [m['module_id'] for m in modules]
    zone_ids = {z['zone_id'] for z in zones}
    assets = asset_index(state)
    key = (state.get('classified_visuals') or {}).get('key_visual')
    if key is not None and key not in assets:
        # Invalid upstream state is not a model planning opportunity.
        raise ValueError('Classified key visual is not an actual paper asset')
    issues = []

    def issue(code, message, **details):
        issues.append({'code': code, 'message': message, **details})

    if not modules or len(modules) > maximum or (not allow_underfull and len(modules) < minimum):
        issue('module_count', f'Return meaningful modules within the actual {minimum}..{maximum} '
              'region allocation; the returned count is ' + str(len(modules)),
              actual=len(modules), minimum=minimum, maximum=maximum)
    unknown = [m['module_id'] for m in modules if m['zone_id'] not in zone_ids]
    if unknown:
        issue('unknown_regions', 'Use only the supplied region IDs', module_ids=unknown)
    occupancy = [{'zone_id': z['zone_id'], 'capacity': z['capacity'],
                  'module_ids': [m['module_id'] for m in modules if m['zone_id'] == z['zone_id']]}
                 for z in zones]
    for row in occupancy:
        count = len(row['module_ids'])
        if count > row['capacity']:
            issue('region_over_capacity', 'Region ' + row['zone_id'] + ' exceeds its capacity', **row)
        elif count == 0 and (len(modules) >= minimum or not allow_underfull):
            issue('empty_region', 'Region ' + row['zone_id'] + ' needs a meaningful module', **row)
    core = raw['core_module_ids']
    if len(core) > 2 or len(set(core)) != len(core) or not set(core) <= set(ids):
        issue('invalid_core_references', 'Select at most two distinct existing core modules',
              actual=core, available_module_ids=ids,
              unknown_module_ids=[mid for mid in core if mid not in ids])
    selected = [vid for m in modules for vid in m['visual_ids']]
    if key is not None and key not in selected:
        issue('missing_key_visual', 'Curator must visibly use the classified key visual: ' + key,
              key_visual=key)
    for m in modules:
        if not any(p['priority'] == 'core' for p in m['content_outline']):
            issue('missing_core_content', 'Each planned module needs a core content point',
                  module_id=m['module_id'])
    if not issues:
        return
    unknown_visuals = sorted(set(selected) - assets.keys())
    repeated = sorted(v for v, n in Counter(selected).items() if n > 1)
    if unknown_visuals:
        issue('unknown_visuals', 'Select only actual paper assets', visual_ids=unknown_visuals)
    if repeated:
        issue('repeated_visuals', 'Each selected visual must have exactly one owner', visual_ids=repeated)
    feedback = {'version': VERSION, 'reason': 'invalid_plan', 'issues': issues,
                'actual_module_count': len(modules), 'minimum_modules': minimum,
                'maximum_modules': maximum, 'region_occupancy': occupancy,
                'available_module_ids': ids, 'available_visual_ids': list(assets), 'key_visual': key,
                'underfull_initial_plan': allow_underfull and 0 < len(modules) < minimum,
                'instruction': 'Return one complete corrected plan using the supplied paper and actual '
                'regions. Reorganize content, titles, order, weights, core selection and visual ownership '
                'together. Preserve supported contributions, representative findings and necessary '
                'conditions; do not invent content or treat reason as returned modules. This uses the '
                'single adjustment shared with geometry replanning and legal region merging.'}
    raise EditorialPlanningError(raw, feedback)


def plan_changes(before, after):
    """Observed structural differences, not the model's claim of improvement."""
    old = {m['module_id']: m for m in before['modules']}
    new = {m['module_id']: m for m in after['modules']}
    return {'before_module_ids': [m['module_id'] for m in before['modules']],
            'after_module_ids': [m['module_id'] for m in after['modules']],
            'removed_module_ids': [mid for mid in old if mid not in new],
            'added_module_ids': [mid for mid in new if mid not in old],
            'changed_module_fields': {mid: [k for k in new[mid] if new[mid][k] != old[mid].get(k)]
                                      for mid in new if mid in old and new[mid] != old[mid]},
            'changed_global_fields': [k for k in ('core_module_ids', 'narrative_flow', 'reason')
                                      if before[k] != after[k]],
            'scientific_coverage_verified': False}
