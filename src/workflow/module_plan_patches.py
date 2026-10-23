"""Stable module identities and bounded ID-only plan edits, never semantic guesses."""
from copy import deepcopy

from src.workflow.sample_modules import ModulePlanValidationError

FIELDS = {'title', 'writing_brief', 'evidence_ids', 'source_plan_unit_ids', 'required_unit_ids',
          'required_evidence_ids', 'visual_ids', 'module_purpose', 'presentation_style'}


def identify_modules(raw):
    result = deepcopy(raw)
    if isinstance(result, dict) and isinstance(result.get('modules'), list):
        for index, row in enumerate(result['modules'], 1):
            if not isinstance(row, dict):
                result['modules'][index-1] = row = {'_invalid_module': True}
            row['module_id'] = f'display_{index:03d}'
    return result


def apply_module_patch(draft, patch):
    def fail(code):
        raise ModulePlanValidationError([{'code': code}])
    if not isinstance(patch, dict):
        fail('invalid_patch_format')
    usable = (isinstance(draft, dict) and isinstance(draft.get('modules'), list) and
              bool(draft['modules']) and all(isinstance(m, dict) for m in draft['modules']) and
              any(not m.get('_invalid_module') for m in draft['modules']))
    if not usable:
        if set(patch) != {'replacement_modules'} or not isinstance(patch['replacement_modules'], list):
            fail('invalid_draft_requires_explicit_replacement')
        return identify_modules({'modules': patch['replacement_modules']})
    if not set(patch) <= {'updates', 'add_modules', 'module_order'}:
        fail('full_replan_not_allowed')
    updates, additions = patch.get('updates', []), patch.get('add_modules', [])
    if not isinstance(updates, list) or not isinstance(additions, list):
        fail('invalid_patch_operations')
    result = deepcopy(draft)
    modules = result['modules']
    by_id = {m['module_id']: m for m in modules}
    edited = set()
    for update in updates:
        if not isinstance(update, dict) or set(update) != {'module_id', 'set'}:
            fail('invalid_module_update')
        mid, fields = update['module_id'], update['set']
        if not isinstance(mid, str) or mid not in by_id or mid in edited:
            fail('unknown_or_duplicate_patch_target')
        if not isinstance(fields, dict) or not set(fields) <= FIELDS:
            fail('invalid_module_update_fields')
        by_id[mid].update(deepcopy(fields))
        by_id[mid].pop('_invalid_module', None)
        edited.add(mid)
    for row in additions:
        if not isinstance(row, dict) or not set(row) <= FIELDS:
            fail('invalid_added_module')
        module = deepcopy(row)
        module['module_id'] = f'display_{len(modules)+1:03d}'
        modules.append(module)
        by_id[module['module_id']] = module
    if 'module_order' in patch:
        order = patch['module_order']
        if (not isinstance(order, list) or any(not isinstance(v, str) for v in order) or
                len(order) != len(by_id) or set(order) != set(by_id)):
            fail('invalid_module_order')
        result['modules'] = [by_id[mid] for mid in order]
    return result
