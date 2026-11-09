"""Bounded plan -> actual frames -> prose requests for the default route."""
from copy import deepcopy
from pathlib import Path

from src.workflow.editorial_contract import (
    normalize_candidate, EditorialStructureError, EditorialOutputError, make_board)
from src.workflow.editorial_requests import obj, STRING, save, read
from utils.persistence import digest

VERSION = 'editorial_plan_then_write_v2'

CONTENT_POINT = obj({
    'point_id': {'type': 'string', 'minLength': 1},
    'priority': {'type': 'string', 'enum': ['core', 'optional']},
    'statement': {'type': 'string', 'minLength': 1},
    'required_conditions': {'type': 'array', 'items': {'type': 'string', 'minLength': 1}},
})


def plan_schema(candidate_schema):
    schema = deepcopy(candidate_schema)
    module = schema['properties']['modules']['items']
    del module['properties']['entries']
    module['properties']['content_outline'] = {
        'type': 'array', 'minItems': 1, 'items': deepcopy(CONTENT_POINT)}
    module['required'] = list(module['properties'])
    return schema


def skeleton(plan):
    raw = deepcopy(plan)
    for module in raw['modules']:
        module.pop('content_outline', None)
        module['entries'] = []
    return raw


def normalize_plan(raw, state, zones, *, allow_underfull=False):
    normalize_candidate(skeleton(raw), state, zones, allow_underfull=allow_underfull)
    for i, module in enumerate(raw['modules']):
        points = module['content_outline']
        if not points or not any(p['priority'] == 'core' for p in points):
            # Choosing a module's essential message is semantic planning, not a
            # field-format repair opportunity to rewrite its scientific content.
            raise EditorialOutputError('Each planned module needs a core content point')
        seen, paths = set(), []
        for j, point in enumerate(points):
            base = ('modules', i, 'content_outline', j)
            pid = point['point_id']
            if not pid.strip() or pid != pid.strip() or pid in seen:
                paths.append((*base, 'point_id'))
            seen.add(pid)
            if not point['statement'].strip():
                paths.append((*base, 'statement'))
            paths.extend((*base, 'required_conditions', k)
                         for k, condition in enumerate(point['required_conditions']) if not condition.strip())
        if paths:
            raise EditorialStructureError('Invalid content point ID or empty content field', paths)
    return deepcopy(raw)


def content_guidance(plan, module_id):
    """Bind priorities to original module IDs, never region/array position.

    The single capacity call precedes any capacity-driven merge/deletion. For a
    standalone diagnostic or a new ID, explicitly expose missing guidance rather
    than silently borrowing another module's obligations. Original plan receipts
    stay immutable after an intentional capacity patch.
    """
    modules = (plan or {}).get('modules', [])
    matches = [m for m in modules if m['module_id'] == module_id]
    if len(matches) > 1:
        raise EditorialOutputError('Ambiguous content guidance module ID')
    return {'source_module_id': module_id,
            'status': 'planned' if matches else 'not_planned',
            'content_outline': deepcopy(matches[0]['content_outline']) if matches else []}


def writing_payload(state, plan, geometry):
    from src.workflow.editorial_contract import paper_material
    frames = {f['module_id']: f for f in geometry['frames']}
    if len(frames) != len(geometry['frames']) or set(frames) != {m['module_id'] for m in plan['modules']}:
        raise EditorialOutputError('Writing tasks must match every actual body frame')
    tasks = []
    for module in plan['modules']:
        mid = module['module_id']; frame = frames[mid]
        tasks.append({'module_id': mid, 'title': module['title'],
                      'presentation_style': module['presentation_style'],
                      'body_frame': deepcopy(frame['body_frame']),
                      'body_layout': frame['body_layout'],
                      **deepcopy(frame['reference']),
                      'content_guidance': content_guidance(plan, mid)})
    # One budget/outline per module, ahead of the paper. The original plan and
    # geometry remain in durable local receipts; metadata here has no second
    # outline/word estimate for the model to reconcile.
    metadata = deepcopy(plan)
    for module in metadata['modules']:
        module.pop('content_outline')
    frame_details = deepcopy(geometry)
    for frame in frame_details['frames']:
        frame.pop('reference')
    return {'phase': 'writer', 'writing_tasks': {
                'font': {k: geometry['calibration'][k] for k in ('font_name', 'font_size_pt')},
                'modules': tasks},
            'plan': metadata, 'body_frames': frame_details,
            'paper': paper_material(state), 'content_status': 'not_preverified'}


def setup_geometry_style(state, plan):
    from src.agents.font_agent import FontAgent
    from src.agents.section_title_designer import SectionTitleDesigner
    state['styling_interfaces'] = FontAgent().get_styling_interfaces()
    # Colors do not affect measured dimensions. Use the same title template and
    # font as the later palette/title nodes, before any model color extraction.
    state['section_title_design'] = SectionTitleDesigner()._generate_colorblock_design(
        make_board(skeleton(plan)), {})


def writer_schema(plan, entry_schema):
    return obj({'modules': obj({m['module_id']: obj({
        'entries': {'type': 'array', 'items': deepcopy(entry_schema), 'minItems': 1}})
        for m in plan['modules']}), 'reason': STRING})


def written_candidate(raw, plan, state, zones):
    expected = {m['module_id'] for m in plan['modules']}
    if set(raw['modules']) != expected:
        raise EditorialOutputError('Writer must return exactly the planned module IDs')
    candidate = skeleton(plan)
    for module in candidate['modules']:
        module['entries'] = deepcopy(raw['modules'][module['module_id']]['entries'])
    try:
        return normalize_candidate(candidate, state, zones)
    except EditorialStructureError as exc:
        paths = []
        for path in exc.paths:
            if len(path) >= 3 and path[0] == 'modules' and isinstance(path[1], int) and path[2] == 'entries':
                paths.append(('modules', plan['modules'][path[1]]['module_id'], *path[2:]))
            else:
                raise EditorialOutputError('Writer cannot repair a frozen plan field') from exc
        raise EditorialStructureError(str(exc), paths) from exc


def write(state, plan, geometry, zones, request, charge, entry_schema):
    payload = writing_payload(state, plan, geometry)
    directory = 'editorial/writer'
    key = digest(payload)
    charge(state, 'writer', key, Path(state['sample_preparation_dir'])/directory)
    value = request(state, 'editorial_writer', payload, writer_schema(plan, entry_schema), directory=directory,
        validator=lambda raw: written_candidate(raw, plan, state, zones))
    return written_candidate(value, plan, state, zones)


def persist_geometry(state, plan, geometry):
    identity = digest({'version': VERSION, 'plan': plan, 'geometry': geometry,
                       'paper': state['paper_foundation_digest'], 'family': state['sample_family'],
                       'sample': state['iteration_context']})
    geometry['input_digest'] = identity
    record = {'input_digest': identity, 'plan': plan, 'geometry': geometry}
    path = Path(state['sample_preparation_dir'])/'editorial/authoring_geometry.json'
    if path.exists():
        if read(path, identity) != record:
            raise ValueError('Authoring geometry receipt changed')
    else:
        if (path.parent/'writer/request_00.json').exists():
            raise ValueError('Authoring geometry missing after writer charge')
        save(path, record)
    state['editorial_plan'] = deepcopy(plan)
    state['editorial_authoring_geometry'] = deepcopy(geometry)


def assert_authoring_receipt(state):
    geometry = state.get('editorial_authoring_geometry')
    if geometry is None:
        if any(c['phase'] == 'writer' for c in (state.get('editorial_budget') or {}).get('charges', [])):
            raise ValueError('Authoring geometry missing from a written sample')
        return  # Explicit standalone/diagnostic candidates retain their route.
    root = Path(state['sample_edit_budget_dir'])/'preparation/editorial'
    record = read(root/'authoring_geometry.json', geometry['input_digest'])
    if record['geometry'] != geometry or record['plan'] != state.get('editorial_plan'):
        raise ValueError('Authoring geometry or plan differs from its original receipt')
