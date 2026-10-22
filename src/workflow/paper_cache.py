"""Explicit reuse of hash-verified paper material, never sample prose or designs."""
from copy import deepcopy
from pathlib import Path
import shutil

from utils.persistence import digest, file_hash, read_json


def extraction_identity(settings):
    names = {'src/agents/parser.py', 'src/agents/evidence_builder.py',
             'src/agents/visual_classification.py', 'utils/section_utils.py',
             'utils/evidence_utils.py', 'utils/langgraph_utils.py', 'utils/model_requests.py',
             'utils/agent_policy.py', 'config/prompts/extract_evidence.txt',
             'config/prompts/classify_visuals.txt', 'config/prompts/extract_title_authors.txt'}
    code = settings.get('code_identity') or {}
    return {'code': {k: code.get(k) for k in sorted(names)},
            'agent_policy': settings.get('agent_policy_hash'),
            'poster_config': settings.get('poster'),
            'requests': (settings.get('critic') or {}).get('sample_execution')}


def copy_paper_cache(store, source_id, target_id, identity, settings):
    source_root = store.run_path(source_id)
    manifest = read_json(source_root/'manifest.json')
    if manifest.get('identity') != identity or extraction_identity(manifest['settings']) != extraction_identity(settings):
        raise ValueError('Paper cache input/model/extraction identity changed; prepare a new paper foundation')
    frozen = read_json(source_root/'paper_foundation/paper_state.json')
    fields = store.paper_foundation(source_id)
    if not fields:
        raise ValueError('Requested run has no verified paper foundation')
    if (frozen['fields'] != fields or digest(frozen) !=
            read_json(source_root/'paper_foundation/identity.json')['digest']):
        raise ValueError('Paper cache changed during validation')
    fields = deepcopy(fields)
    target = store.run_path(target_id)/'paper_foundation/assets'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('images', 'tables'):
        for key, asset in (fields.get(name) or {}).items():
            if not asset.get('path'):
                continue
            path = Path(asset['path'])
            if path.is_symlink() or not path.resolve().is_relative_to((source_root/'paper_foundation').resolve()):
                raise ValueError('Paper cache asset escapes its source foundation')
            expected = frozen['resource_hashes'].get(str(path.resolve()))
            if expected is None or file_hash(path) != expected:
                raise ValueError('Paper cache asset changed during validation')
            copied = target/f'{name}_{key}{path.suffix}'
            shutil.copyfile(path, copied)
            if file_hash(copied) != expected:
                raise ValueError('Paper cache asset copy digest mismatch')
            asset['path'] = str(copied)
    return fields
