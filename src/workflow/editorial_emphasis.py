"""At most two Curator-selected panels with durable, owner-local color sources."""
from copy import deepcopy
from pathlib import Path

from src.layout.emphasis import resolve_emphasis
from utils.persistence import digest, file_hash

VERSION = 'editorial_core_panels_v1'


def sources(candidate, state):
    from src.workflow.editorial_contract import asset_index
    modules = {m['module_id']: m for m in candidate['modules']}
    assets = asset_index(state)
    key = (state.get('classified_visuals') or {}).get('key_visual')
    result = {}
    for mid in candidate['core_module_ids']:
        visuals = modules[mid]['visual_ids']
        visual = (key if key in visuals else visuals[0]) if visuals else None
        result[mid] = {'source': 'module_visual' if visual else 'global_palette',
                       'visual_id': visual,
                       'asset_hash': file_hash(assets[visual]['path']) if visual else None}
    return result


def identity(candidate, state):
    return digest({'version': VERSION, 'core_module_ids': candidate['core_module_ids'],
                   'sources': sources(candidate, state), 'palette': state['color_scheme']})


def prepare(state, agent, extract):
    """Resolve once after final Curator selection; replay never repeats extraction."""
    from src.workflow.editorial_contract import asset_index, EditorialOutputError
    from src.workflow.editorial_requests import read, save
    from utils.model_requests import SampleRequestFailure
    candidate = state['editorial_candidate']
    key = identity(candidate, state)
    path = Path(state['sample_preparation_dir'])/'editorial/emphasis.json'
    if path.exists():
        record = read(path, key)
    else:
        panels = {}
        for mid, source in sources(candidate, state).items():
            colors = state['color_scheme']
            failure = None
            if source['visual_id']:
                try:
                    theme = extract(asset_index(state)[source['visual_id']]['path'], 'core_'+mid)
                    if theme is None:
                        failure = 'no_suitable_image_accent'
                    else:
                        colors = agent._add_contrast_color(agent._generate_color_scheme(theme))
                        colors, _ = agent._apply_style_overrides(colors, state)
                except (SampleRequestFailure, TimeoutError, EditorialOutputError) as exc:
                    failure = type(exc).__name__
            resolved, report = (resolve_emphasis(colors, state.get('critic_config')) if failure is None
                                else (None, {'status': 'unavailable', 'reason': failure}))
            receipt_root = path.parent/'palette'/('core_'+mid)
            receipts = {p.name: file_hash(p) for p in receipt_root.glob('*.json')} if source['visual_id'] else {}
            panels[mid] = {**source, 'theme_color': colors['theme'] if failure is None else None,
                           'resolved': resolved, 'resolution': report, 'receipts': receipts}
        record = {'version': VERSION, 'input_digest': key,
                  'core_module_ids': list(candidate['core_module_ids']), 'panels': panels}
        save(path, record)
    state['editorial_emphasis'] = record
    assert_emphasis(state, durable=True)
    return record


def assert_emphasis(state, candidate=None, *, durable=False, layout=None):
    candidate = candidate or state['editorial_candidate']
    record = state.get('editorial_emphasis')
    if (not isinstance(record, dict) or record.get('version') != VERSION
            or record.get('core_module_ids') != candidate['core_module_ids']
            or set(record.get('panels', {})) != set(candidate['core_module_ids'])
            or record.get('input_digest') != identity(candidate, state)):
        raise ValueError('Core panel selection, resources or palette changed or is missing')
    for mid, source in sources(candidate, state).items():
        if any(record['panels'][mid].get(k) != v for k, v in source.items()):
            raise ValueError('Core panel color source changed')
    if durable:
        from src.workflow.editorial_requests import read
        path = Path(state['sample_edit_budget_dir'])/'preparation/editorial/emphasis.json'
        if read(path, record['input_digest']) != record:
            raise ValueError('Core panel palette differs from its receipt')
        for mid, panel in record['panels'].items():
            root = path.parent/'palette'/('core_'+mid)
            receipts = {p.name: file_hash(p) for p in root.glob('*.json')}
            if receipts != panel['receipts']:
                raise ValueError('Core panel extraction receipts changed or are missing')
    if layout is not None:
        expected = {m['module_id'] for m in candidate['modules']}
        containers = [e for e in layout if e.get('type') == 'section_container']
        if len(containers) != len(expected) or {e.get('section_id') for e in containers} != expected:
            raise ValueError('Core panel containers differ from authored modules')
        for element in containers:
            resolved = (record['panels'].get(element['section_id']) or {}).get('resolved') or {}
            if (element.get('emphasis_background') != resolved.get('background')
                    or element.get('emphasis_disabled') != (not bool(resolved))):
                raise ValueError('Compiled core panel background differs from frozen palette')
    return record


def apply(board, record):
    for section in board['spatial_content_plan']['sections']:
        meta = section['editorial']
        resolved = ((record or {}).get('panels', {}).get(section['section_id']) or {}).get('resolved')
        meta['emphasis_disabled'] = not bool(resolved)
        if resolved:
            meta.update(deepcopy(resolved))
    return board
