"""Bounded plan -> actual frames -> prose requests for the default route."""
from copy import deepcopy
from pathlib import Path

from src.workflow.editorial_contract import (
    normalize_candidate, EditorialStructureError, EditorialOutputError, make_board)
from src.workflow.editorial_requests import obj, STRING, save, read
from utils.persistence import digest

VERSION = 'editorial_plan_then_write_v1'


def plan_schema(candidate_schema):
    schema = deepcopy(candidate_schema)
    module = schema['properties']['modules']['items']
    del module['properties']['entries']
    module['properties']['content_outline'] = {'type': 'array', 'minItems': 1, 'items': STRING}
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
        if not module['content_outline'] or any(not s.strip() for s in module['content_outline']):
            raise EditorialStructureError('Planning needs nonempty content intentions',
                                           [('modules', i, 'content_outline')])
    return deepcopy(raw)


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
    from src.workflow.editorial_contract import paper_material
    payload = {'phase': 'writer', 'paper': paper_material(state), 'plan': plan,
               'body_frames': geometry, 'content_status': 'not_preverified'}
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
