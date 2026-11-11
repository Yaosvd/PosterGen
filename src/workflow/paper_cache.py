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
    if settings.get('preparation_policy_version') in {'sample_source_science_v1', 'sample_source_science_v2'}:
        names -= {'src/agents/evidence_builder.py', 'config/prompts/extract_evidence.txt'}
        names.add('src/workflow/source_document.py')
        if settings.get('preparation_policy_version') == 'sample_source_science_v2':
            names.add('utils/source_pdf.py')
    if settings.get('preparation_policy_version') == 'sample_editorial_v1':
        names -= {'src/agents/evidence_builder.py', 'config/prompts/extract_evidence.txt'}
        names.update({'src/workflow/editorial_parser.py','src/workflow/editorial_requests.py',
                      'src/workflow/editorial_format.py',
                      'src/workflow/editorial_contract.py','utils/source_pdf.py',
                      'utils/editorial_pdf.py','utils/pdf_ocr.py',
                      'utils/marker_proofreading.py','utils/marker_worker.py','utils/concurrency.py',
                      'config/prompts/editorial_proofreading.txt',
                      *('config/prompts/editorial_'+name+'.txt' for name in ('metadata','abt','sections','visuals'))})
        return {'foundation_contract':'organized_editorial_v1',
                'project_identity':settings.get('project_identity'),
                'code':{k:code.get(k) for k in sorted(names)},
                'agent_policy':settings.get('agent_policy_hash'),'poster_config':settings.get('poster'),
                'requests':(settings.get('critic') or {}).get('sample_execution'),
                'source_extraction_environment':settings.get('source_extraction_environment')}
    return {'foundation_contract': ({'sample_source_science_v1':'original_sections_v1','sample_source_science_v2':'original_sections_v2'}.get(settings.get('preparation_policy_version'),'evidence_foundation')),
            'code': {k: code.get(k) for k in sorted(names)},
            'agent_policy': settings.get('agent_policy_hash'),
            'poster_config': settings.get('poster'),
            'requests': (settings.get('critic') or {}).get('sample_execution'),
            'source_extraction_environment': settings.get('source_extraction_environment')
                if settings.get('preparation_policy_version') == 'sample_source_science_v2' else None}


def copy_paper_cache(store, source_id, target_id, identity, settings, *,
                     source_sample_id=None, target_sample_id=None):
    source_root = store.run_path(source_id)
    manifest = read_json(source_root/'manifest.json')
    if manifest.get('settings_digest') != digest(manifest['settings']):
        raise ValueError('Paper cache settings digest mismatch')
    source_identity = manifest.get('identity')
    if manifest['settings'].get('task_entry_policy') == 'full_paper_tasks_v1':
        from src.workflow.task_inputs import VERSION
        if source_sample_id is None:
            if manifest.get('samples') != 1:
                raise ValueError('Choose paper_cache_sample_id for a multi-task source run')
            source_sample_id = 'sample_000001'
        receipt = read_json(store.sample_path(source_id, source_sample_id) / 'task_inputs.json')
        value = receipt['payload']
        tasks = read_json(source_root / 'sample_plan.json')
        if (receipt.get('digest') != digest(value) or value.get('version') != VERSION or
                value.get('run_id') != source_id or value.get('task', {}).get('sample_id') != source_sample_id or
                value.get('settings_digest') != manifest.get('settings_digest') or
                tasks.get('digest') != digest(tasks.get('tasks')) or value.get('task') not in tasks['tasks']):
            raise ValueError('Paper cache task input receipt changed')
        number = value['task']['number']
        parent = manifest['identity']
        declared = (parent['task_inputs'][number - 1] if 'task_inputs' in parent else parent)
        if value['identity'] != declared:
            raise ValueError('Paper cache task identity differs from its run inputs')
        source_identity = value['identity']
    if source_identity != identity or extraction_identity(manifest['settings']) != extraction_identity(settings):
        raise ValueError('Paper cache input/model/extraction identity changed; prepare a new paper foundation')
    source_paper = store.paper_path(source_id, source_sample_id)
    frozen = read_json(source_paper / 'paper_state.json')
    fields = (store.paper_foundation(source_id) if source_sample_id is None else
              store.paper_foundation(source_id, source_sample_id))
    if not fields:
        raise ValueError('Requested run has no verified paper foundation')
    if (frozen['fields'] != fields or digest(frozen) !=
            read_json(source_paper / 'identity.json')['digest']):
        raise ValueError('Paper cache changed during validation')
    fields = deepcopy(fields)
    target = store.paper_path(target_id, target_sample_id) / 'assets'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('images', 'tables'):
        for key, asset in (fields.get(name) or {}).items():
            if not asset.get('path'):
                continue
            path = Path(asset['path'])
            if path.is_symlink() or not path.resolve().is_relative_to(source_paper.resolve()):
                raise ValueError('Paper cache asset escapes its source foundation')
            expected = frozen['resource_hashes'].get(str(path.resolve()))
            if expected is None or file_hash(path) != expected:
                raise ValueError('Paper cache asset changed during validation')
            copied = target/f'{name}_{key}{path.suffix}'
            shutil.copyfile(path, copied)
            if file_hash(copied) != expected:
                raise ValueError('Paper cache asset copy digest mismatch')
            asset['path'] = str(copied)
    if fields.get('source_editorial_version') == 'source_editorial_v1':
        # Copied foundations are self-contained; never keep asset paths into the donor.
        doc = deepcopy(fields['source_document'])
        for visual_id, asset in doc['assets'].items():
            prefix, key = visual_id.split('_', 1)
            asset['source_path'] = fields['images' if prefix == 'figure' else 'tables'][key].get('path')
        doc.pop('digest')
        doc['digest'] = digest(doc)
        fields['source_document'] = doc
    return fields
