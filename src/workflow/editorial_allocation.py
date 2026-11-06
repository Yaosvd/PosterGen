"""Per-region authoring constraints and bounded, position-only repair diagnostics."""
from collections import Counter
from copy import deepcopy

from src.workflow.editorial_contract import EditorialOutputError, EditorialStructureError


def zone_count_constraint(zone):
    """Full local Schema constraint; local model servers receive its description."""
    return {'contains': {'type': 'object',
                         'properties': {'zone_id': {'const': zone['zone_id']}},
                         'required': ['zone_id']},
            'minContains': 0, 'maxContains': zone['capacity']}


def is_zone_count_constraint(schema):
    """Recognize only our count clauses, not arbitrary user Schema/data."""
    if not isinstance(schema, dict) or set(schema) != {'contains', 'minContains', 'maxContains'}:
        return False
    item = schema['contains']
    return (schema['minContains'] == 0 and type(schema['maxContains']) is int
            and schema['maxContains'] > 0 and isinstance(item, dict)
            and set(item) == {'type', 'properties', 'required'} and item['type'] == 'object'
            and item['required'] == ['zone_id'] and isinstance(item['properties'], dict)
            and set(item['properties']) == {'zone_id'}
            and isinstance(item['properties']['zone_id'], dict)
            and set(item['properties']['zone_id']) == {'const'}
            and isinstance(item['properties']['zone_id']['const'], str))


class AllocationRepairError(EditorialStructureError):
    def __init__(self, details):
        occupancy = ', '.join(f"{z['zone_id']}={z['used']}/{z['capacity']}" for z in details['regions'])
        super().__init__('Curator region allocation is invalid: '+occupancy,
                         [('modules', i, 'zone_id') for i in details['movable_module_indices']]
                         + [('narrative_flow',)])
        self.details = details


def allocation_error(raw, zones, *, allow_underfull):
    """Diagnose only redistribution: never create/drop modules or choose their places.

    Call on a structurally valid draft (except possibly zone_id enums). All members
    of an overfull region are eligible so the author, not list position, chooses
    which explanation moves. A minimal move count keeps unrelated placements fixed.
    """
    modules = raw['modules']
    capacities = {z['zone_id']: z['capacity'] for z in zones}
    count = len(modules)
    if not modules or count > sum(capacities.values()) or (count < len(zones) and not allow_underfull):
        return None  # Preserve finite content failure / meaningful deficit handling.
    counts = Counter(m['zone_id'] for m in modules)
    unknown = [i for i, m in enumerate(modules) if m['zone_id'] not in capacities]
    overfull = {z for z, cap in capacities.items() if counts[z] > cap}
    require_occupied = count >= len(zones)
    empty = [z for z in capacities if not counts[z]] if require_occupied else []
    if not (unknown or overfull or empty):
        return None
    mandatory_moves = len(unknown) + sum(max(0, counts[z]-cap) for z, cap in capacities.items())
    minimum_moves = max(mandatory_moves, len(empty))
    sources = overfull if mandatory_moves >= len(empty) else {z for z in capacities if counts[z] > 1}
    movable = [i for i, m in enumerate(modules) if i in unknown or m['zone_id'] in sources]
    destinations = [z for z, cap in capacities.items() if counts[z] < cap]
    details = {
        'version': 'editorial_allocation_repair_v1',
        'regions': [{'zone_id': z, 'used': counts[z], 'capacity': cap,
                     'remaining_slots': max(0, cap-counts[z]),
                     'minimum_occupancy': int(require_occupied)} for z, cap in capacities.items()],
        'unknown_module_indices': unknown, 'movable_module_indices': movable,
        'minimum_moves': minimum_moves,
        'allowed_zone_ids': {str(i): [z for z in capacities
                                     if z == modules[i]['zone_id'] or z in destinations] for i in movable},
        'current_allocation': [{'module_index': i, 'module_id': m['module_id'], 'zone_id': m['zone_id']}
                               for i, m in enumerate(modules)],
    }
    return AllocationRepairError(details)


def diagnose_allocation(raw, zones, errors, *, allow_underfull):
    """Never map an array count error to a whole scientific modules replacement."""
    count_errors = [e for e in errors if tuple(e.absolute_path) == ('modules',)
                    and e.validator == 'maxContains' and is_zone_count_constraint(e.schema)]
    zone_errors = [e for e in errors if len(e.absolute_path) == 3
                   and tuple(e.absolute_path)[0] == 'modules'
                   and tuple(e.absolute_path)[2] == 'zone_id' and e.validator == 'enum']
    if len(count_errors) + len(zone_errors) != len(errors):
        if count_errors:
            raise EditorialOutputError('Region capacity violation with other invalid fields; '
                                       'refusing whole-module allocation repair')
        return None
    return allocation_error(raw, zones, allow_underfull=allow_underfull)


def constrain_allocation_plan(plan, error):
    if not isinstance(error, AllocationRepairError):
        return
    plan['allocation'] = deepcopy(error.details)
    for target in plan['targets']:
        path = target['path']
        if len(path) == 3 and path[0] == 'modules' and path[2] == 'zone_id':
            plan['schema']['properties']['repairs']['properties'][target['field']] = {
                'type': 'string', 'enum': list(error.details['allowed_zone_ids'][str(path[1])])}


def validate_allocation_repair(original, value, plan):
    if not plan.get('allocation'):
        return
    moved = sum(a['zone_id'] != b['zone_id'] for a, b in zip(original['modules'], value['modules']))
    if moved != plan['allocation']['minimum_moves']:
        raise EditorialOutputError('Allocation repair must change exactly the necessary number of module regions')
