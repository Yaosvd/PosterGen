"""Full-input task boundaries; source preparation belongs to each poster."""
from copy import deepcopy
from dataclasses import asdict
import json
import math
from pathlib import Path
import shutil

from utils.persistence import _atomic_json, digest, file_hash, read_json

VERSION = 'full_paper_tasks_v1'
INPUT_FILES = ('pdf_path', 'logo_path', 'aff_logo_path')


def input_identity(state):
    inputs = {key: file_hash(state[key]) if state.get(key) and Path(state[key]).is_file() else None
              for key in INPUT_FILES}
    if inputs['pdf_path'] is None:
        raise ValueError('A readable source PDF is required for every poster task')
    value = {'inputs': inputs, 'width': state['poster_width'], 'height': state['poster_height'],
             'text_model': asdict(state['text_model']), 'vision_model': asdict(state['vision_model']),
             'url': state.get('url', ''), 'poster_name': state['poster_name']}
    return value


def enter_task(store, run_id, task, state, identity, settings_digest, cache):
    root = store.sample_path(run_id, task['sample_id'])
    receipt = root / 'task_inputs.json'
    paths = {key: str(root / 'inputs' / (key + Path(state[key]).suffix.lower()))
             for key in INPUT_FILES if identity['inputs'][key] is not None}
    payload = {'version': VERSION, 'run_id': run_id, 'task': deepcopy(task),
               'identity': identity, 'settings_digest': settings_digest, 'cache': cache, 'paths': paths}
    if receipt.exists():
        saved = read_json(receipt)
        if saved.get('digest') != digest(saved.get('payload')) or saved.get('payload') != payload:
            raise ValueError('Poster task input receipt changed')
    else:
        # Losing a receipt after any model/render work must not buy another preparation.
        if any((root / name).exists() for name in ('paper_foundation', 'preparation', 'attempts', 'family_assignment.json')):
            raise ValueError('Poster task input identity receipt missing from existing history')
        for key, target in paths.items():
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.is_symlink() or file_hash(target) != identity['inputs'][key]:
                    raise ValueError('Poster task input copy changed')
            else:
                shutil.copyfile(state[key], target)
            if file_hash(target) != identity['inputs'][key]:
                raise ValueError('Poster task input copy digest mismatch')
        _atomic_json(receipt, {'payload': payload, 'digest': digest(payload)})
    for key, path in paths.items():
        if Path(path).is_symlink() or file_hash(path) != identity['inputs'][key]:
            raise ValueError('Poster task input copy changed')
        state[key] = path
    state['task_input_digest'] = digest(payload)
    return state


def create_input_state(spec, defaults, base, factory):
    value = {**defaults, **spec}
    def path(name):
        raw = value.get(name)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(name + ' must be a nonempty path')
        candidate = Path(raw).expanduser()
        return (base / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    pdf = path('paper_path')
    if not pdf.is_file():
        raise ValueError('PDF not found: ' + str(pdf))
    width, height = value['poster_width'], value['poster_height']
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in (width, height)):
        raise ValueError('Poster dimensions must be finite positive numbers')
    ratio = width / height
    if not 1.4 <= ratio <= 2:
        raise ValueError('Poster aspect ratio must be between 1.4 and 2.0')
    for key in ('text_model', 'vision_model'):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(key + ' must be a nonempty model name')
    if not isinstance(value.get('url', ''), str):
        raise ValueError('url must be text')
    logos = []
    for key, fallback in (('logo', 'logo.png'), ('aff_logo', 'aff.png')):
        asset = path(key) if value.get(key) is not None else pdf.parent / fallback
        if value.get(key) is not None and not asset.is_file():
            raise ValueError('Logo not found: ' + str(asset))
        logos.append(str(asset) if asset.is_file() else '')
    state = factory(str(pdf), value['text_model'], value['vision_model'], 54, 54 / ratio,
                    value.get('url', ''), *logos)
    if 'random_seed' in spec:
        if type(spec['random_seed']) is not int:
            raise ValueError('Task random_seed must be an integer')
        state['task_random_seed'] = spec['random_seed']
    return state


def load_task_file(path, defaults, factory):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'tasks'} or
            type(value['schema_version']) is not int or value['schema_version'] != 1 or
            not isinstance(value['tasks'], list) or not value['tasks']):
        raise ValueError('Task file requires schema_version=1 and a nonempty tasks array')
    allowed = {'paper_path', 'logo', 'aff_logo', 'text_model', 'vision_model',
               'poster_width', 'poster_height', 'url', 'random_seed'}
    states = []
    for number, spec in enumerate(value['tasks'], 1):
        if not isinstance(spec, dict) or 'paper_path' not in spec or set(spec) - allowed:
            raise ValueError(f'Invalid input fields for task {number}')
        states.append(create_input_state(spec, defaults, path.parent, factory))
    return states
