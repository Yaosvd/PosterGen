"""Single-choice Critic references; expansion never infers a model's intent."""
from copy import deepcopy

from jsonschema import Draft202012Validator

from src.workflow.editorial_requests import obj, STRING
from src.workflow.editorial_contract import EditorialStructureError

VERSION = 'critic_references_v1'
EMPTY_LOCATION = {'zone_id': '', 'section_id': '', 'element_id': ''}


def catalog(references, modules):
    evidence = {'E000': {'measurement_id': '', 'finding_id': ''}}
    for measurement, findings in sorted(references['measurements'].items()):
        for finding in ['', *findings]:
            evidence[f'E{len(evidence):03d}'] = {
                'measurement_id': measurement, 'finding_id': finding}
    locations = {'L000': dict(EMPTY_LOCATION)}
    location_types = {'L000': 'global'}
    for zone in references['zone_ids']:
        location_types[f'L{len(locations):03d}'] = 'zone'
        locations[f'L{len(locations):03d}'] = {**EMPTY_LOCATION, 'zone_id': zone}
    owners = {m['module_id']: m['zone_id'] for m in modules}
    for module in references['module_ids']:
        location_types[f'L{len(locations):03d}'] = 'module'
        locations[f'L{len(locations):03d}'] = {
            **EMPTY_LOCATION, 'section_id': module, 'zone_id': owners[module]}
    for element, owner in sorted(references['elements'].items()):
        location_types[f'L{len(locations):03d}'] = owner['element_type']
        locations[f'L{len(locations):03d}'] = {
            'element_id': element, 'section_id': owner['module_id'], 'zone_id': owner['zone_id']}
    return {'version': VERSION, 'module_ids': references['module_ids'],
            'evidence_refs': evidence, 'location_refs': locations, 'location_types': location_types}


def request_schema(schema, references):
    result = deepcopy(schema)
    locations = {'type': 'array', 'minItems': 1,
                 'items': {'type': 'string', 'enum': list(references['location_refs'])}}
    for metric in result['properties']['assessments']['properties'].values():
        old = metric['properties']['evidence']['items']['properties']
        metric['properties']['evidence']['items'] = obj({
            'evidence_ref': {'type': 'string', 'enum': list(references['evidence_refs'])},
            'location_refs': deepcopy(locations),
            'observation': deepcopy(old['observation']), 'original_support': STRING})
    for field in ('issues', 'review_notes'):
        item = result['properties'][field]['items']
        item['properties'].pop('location')
        item['properties'].pop('locations', None)
        item['properties']['location_refs'] = deepcopy(locations)
        item['required'] = list(item['properties'])
    return result


def expand(raw, schema, references):
    """Validate wire fields first; old tuples and ambiguous global mixes are errors."""
    Draft202012Validator(schema).validate(raw)
    result = deepcopy(raw)

    def locations(row, path):
        refs = row.pop('location_refs')
        if len(set(refs)) != len(refs) or ('L000' in refs and len(refs) != 1):
            raise EditorialStructureError(
                'Location references must be distinct; global must stand alone', [(*path, 'location_refs')])
        return [deepcopy(references['location_refs'][ref]) for ref in refs]

    for name, metric in result['assessments'].items():
        for index, row in enumerate(metric['evidence']):
            row.update(references['evidence_refs'][row.pop('evidence_ref')])
            targets = locations(row, ('assessments', name, 'evidence', index))
            # Legacy consumers keep their singular fields. Multi-target observations
            # remain one evidence item and preserve every target in locations.
            target = targets[0] if len(targets) == 1 else EMPTY_LOCATION
            row.update(module_id=target['section_id'], element_id=target['element_id'])
            if len(targets) > 1 or (target['zone_id'] and not target['section_id']):
                row['locations'] = targets
    for field in ('issues', 'review_notes'):
        for index, row in enumerate(result[field]):
            targets = locations(row, (field, index))
            row['location'] = targets[0] if len(targets) == 1 else dict(EMPTY_LOCATION)
            if len(targets) > 1:
                row['locations'] = targets
    return result
