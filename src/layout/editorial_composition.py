"""Durable initial module directions; dimensions remain measured and editable."""
from copy import deepcopy
from pathlib import Path

from utils.persistence import digest

VERSION = 'editorial_module_composition_v1'
HORIZONTAL = 'image_left_text_right'
VERTICAL = 'image_above_text'
MODES = {HORIZONTAL, VERTICAL}


def frozen_mode(state, module_id):
    # Explicit old-source and standalone routes retain their adaptive behavior.
    if (state.get('editorial_version') != 'poster_editorial_v1' or
            state.get('generation_route') != 'optimization_family'):
        return None
    selection = state.get('editorial_composition')
    if selection is None:
        return None
    if selection.get('version') != VERSION:
        raise ValueError('Invalid frozen editorial composition version')
    return selection['modules'].get(module_id)


def directions(candidate, layout):
    result = {}
    for module in candidate['modules']:
        if not module['visual_ids']:
            continue
        elements = [e for e in layout if e.get('section_id') == module['module_id']
                    and e.get('type') in {'text', 'visual'}]
        modes = {e.get('body_layout') for e in elements}
        if len(elements) != len(module['visual_ids'])+1 or len(modes) != 1 or not modes <= MODES:
            raise ValueError('Initial editorial composition is missing or inconsistent')
        result[module['module_id']] = modes.pop()
    return result


def assert_composition(state, candidate=None, layout=None, *, durable=False):
    selection = state.get('editorial_composition')
    candidate = candidate or state['editorial_candidate']
    owners = {m['module_id'] for m in candidate['modules'] if m['visual_ids']}
    if (not isinstance(selection, dict) or selection.get('version') != VERSION or
            not selection.get('input_digest') or not isinstance(selection.get('modules'), dict) or
            set(selection['modules']) != owners or any(v not in MODES for v in selection['modules'].values())):
        raise ValueError('Frozen editorial composition changed or is missing')
    if durable:
        from src.workflow.editorial_requests import read
        root = Path(state['sample_edit_budget_dir'])/'preparation'
        record = read(root/'editorial/composition.json', selection['input_digest'])
        if record['selection'] != selection or directions(candidate, record['result']['layout']) != selection['modules']:
            raise ValueError('Frozen editorial composition differs from its initial fit receipt')
    if layout is not None:
        if directions(candidate, layout) != selection['modules']:
            raise ValueError('Compiled editorial composition differs from its frozen direction')
        for mid, mode in selection['modules'].items():
            text = next(e for e in layout if e.get('section_id') == mid and e.get('type') == 'text')
            visuals = [e for e in layout if e.get('section_id') == mid and e.get('type') == 'visual']
            if mode == HORIZONTAL:
                valid = (abs(text['y']-visuals[0]['y']) < 1e-6 and
                         all(e['x']+e['width'] <= text['x']+1e-6 for e in visuals))
            else:
                valid = all(e['y']+e['height'] <= text['y']+1e-6 for e in visuals)
            if not valid:
                raise ValueError('Compiled editorial boxes changed their frozen image/text direction')
    return selection


def initial_fit(state, fitter=None):
    """Persist the first fitted geometry and direction before any capacity call.

    Recovery reuses this exact result, so adding the lock cannot change the first
    edit's measurements or buy another geometry search/model opportunity.
    """
    from src.layout.editorial_layout import fit
    from src.workflow.editorial_contract import paper_identity, asset_index
    from src.workflow.editorial_requests import read, save
    from utils.persistence import file_hash
    context = state.get('iteration_context') or {}
    identity = digest({'version': VERSION, 'candidate': state['editorial_candidate'],
        'sample': {key: context.get(key) for key in ('run_id', 'sample_id', 'random_seed')},
        'zones': state['editorial_zones'], 'paper': paper_identity(state),
        'poster_inches': [state['poster_width'], state['poster_height']],
        'resources': {vid: file_hash(asset['path']) for vid, asset in asset_index(state).items() if asset.get('path')},
        'title_style': state.get('section_title_design'), 'interfaces': state.get('styling_interfaces'),
        'emphasis': state.get('editorial_emphasis'),
        'critic': state['critic_config']})
    path = Path(state['sample_preparation_dir'])/'editorial/composition.json'
    if path.exists():
        record = read(path, identity)
        if state.get('editorial_composition') not in (None, record['selection']):
            raise ValueError('Frozen editorial composition changed before initial-fit replay')
    else:
        from src.workflow.editorial_requests import read as read_ledger
        ledger_path = Path(state['sample_edit_budget_dir'])/'editorial_budget.json'
        ledger = state.get('editorial_budget') or {}
        if ledger_path.exists():
            ledger = read_ledger(ledger_path, ledger.get('input_digest'))
        if (state.get('editorial_composition') is not None or
                any(c['phase'] == 'capacity' for c in ledger.get('charges', [])) or
                any((path.parent/'edits').glob('*/request_*.json'))):
            raise ValueError('Initial editorial composition receipt missing after capacity editing')
        # Use the existing bounded initial selector; the lock takes effect only
        # after that actual fit has chosen its geometry and internal directions.
        result = (fitter or fit)(state, state['editorial_candidate'], state['editorial_zones'])
        selection = {'version': VERSION, 'input_digest': identity,
                     'modules': directions(state['editorial_candidate'], result['layout'])}
        for module in result['report']['modules']:
            module['composition_locked'] = module.get('body_layout') is not None
        record = {'input_digest': identity, 'selection': selection, 'result': result}
        save(path, record)
    state['editorial_composition'] = deepcopy(record['selection'])
    assert_composition(state, layout=record['result']['layout'], durable=True)
    return deepcopy(record['result'])
