"""Optional same-module original visuals under a separate durable finite ledger."""
from copy import deepcopy
from pathlib import Path

from src.workflow.source_document import SourceOutputError, check_stop
from src.workflow.source_editorial import normalize_candidate, install_candidate
from src.workflow.source_requests import save, read
from utils.persistence import digest


def offer_key_reserve(candidate, state, *, allow_missing=False):
    """Reuse the existing role-based optional offer; no hard retention or image judge."""
    key = (state.get('classified_visuals') or {}).get('key_visual')
    if key not in state['source_document']['assets'] or any(key in m['visual_ids'] or key in m['reserve_visual_ids'] for m in candidate['modules']):
        return candidate
    role_map = {'problem_illustration': {'problem','background','motivation'},
                'method_workflow': {'method','theory'},
                'main_results': {'results','evaluation'}, 'comparative_results': {'results','evaluation'}}
    role = next((r for r in role_map if key in (state.get('classified_visuals') or {}).get(r, [])), None)
    matches = [m for m in candidate['modules'] if role and m['narrative_role'] in role_map[role]]
    if not matches:
        return candidate
    updated = deepcopy(candidate)
    target_id = min(matches, key=lambda m: (len(m['visual_ids']), m['module_id']))['module_id']
    target = next(m for m in updated['modules'] if m['module_id'] == target_id)
    target['reserve_visual_ids'].append(key)
    return normalize_candidate({'modules': updated['modules']}, state, allow_missing=allow_missing)


def restore_source_visuals(state, result):
    from src.workflow.source_preparation import _fit, clone
    from src.workflow.source_verification import verify_candidate, assert_verified
    from src.layout.module_repair import space_preserved
    from src.layout.whitespace import no_displaced_whitespace
    settings = state['critic_config'].get('capacity_repair') or {}
    if not settings.get('enabled', True):
        return state, result
    root = Path(state['sample_preparation_dir'])/'source/visual_probes'
    ledger = Path(state['sample_edit_budget_dir'])/'source_visual_restoration_budget.json'
    context = state['iteration_context']
    identity = digest({'policy': 'source_visual_v1', 'paper': state['paper_foundation_digest'],
        'source': state['source_document']['digest'], 'sample': context.get('sample_id'),
        'run': context.get('run_id'), 'family': state['sample_family']})
    if not ledger.exists() and any(root.glob('*.json')):
        raise ValueError('Source visual ledger missing from existing history')
    usage = read(ledger, identity) if ledger.exists() else {'input_digest': identity, 'charges': []}
    limit = min(4, int(settings.get('max_visual_restore_attempts_per_iteration',4)))
    if len(usage['charges']) > limit:
        raise ValueError('Source visual ledger exceeds its frozen allowance')
    options = [(m['module_id'], v) for m in state['source_candidate']['modules'] for v in m['reserve_visual_ids']]
    options = options[:min(2, int(settings.get('max_visual_restore_attempts',2)))]
    audit = []
    for mid, visual in options:
        check_stop(state)
        key = digest({'candidate': state['source_candidate'], 'spec': result[1], 'module': mid, 'visual': visual})
        path = root/(key+'.json')
        charged = any(r['key'] == key for r in usage['charges'])
        if charged:
            if not path.exists():
                raise ValueError('Source visual probe charged but missing result; refusing automatic resubmission')
            saved = read(path, key)
            if saved.get('fields'):
                state.update(deepcopy(saved['fields'])); result = tuple(saved['result'])
            audit.append(saved['audit'])
            continue
        if path.exists():
            raise ValueError('Source visual probe has no durable charge')
        if len(usage['charges']) >= limit:
            break
        usage['charges'].append({'key':key, 'module_id':mid, 'visual_id':visual})
        save(ledger, usage)
        trial = clone(state)
        candidate = deepcopy(state['source_candidate'])
        module = next(m for m in candidate['modules'] if m['module_id'] == mid)
        module['visual_ids'].append(visual);module['reserve_visual_ids'].remove(visual)
        install_candidate(trial, normalize_candidate({'modules':candidate['modules']},trial))
        trial['draft_layout_mode'] = True
        # Preserve the existing geometry/owners and every already visible visual.
        fitted, failure = _fit(trial, draft=True, physical_baseline=result)
        row = {'module_id':mid, 'visual_id':visual, 'status':'not_placed'}
        adopted = False
        try:
            if failure:
                row['reason'] = failure.get('reason_code')
            elif not space_preserved(result[2],fitted[2]) or not no_displaced_whitespace(
                    result[2].get('composition_whitespace') or {}, fitted[2].get('composition_whitespace') or {},
                    tolerance=settings.get('max_whitespace_regression_fraction',.01),
                    gap_tolerance_inches=settings.get('max_gap_regression_inches',.35)):
                row['reason'] = 'measured_space_regression'
            else:
                proof = verify_candidate(trial,trial['source_candidate'],previous=state['source_candidate'])
                install_candidate(trial,trial['source_candidate'],verified=proof)
                trial['draft_layout_mode'] = False
                final, failure = _fit(trial,draft=False,physical_baseline=fitted)
                if failure:
                    row['reason'] = failure.get('reason_code')
                else:
                    assert_verified(trial,final[0])
                    state,result=trial,final;row['status']='restored';adopted=True
        except SourceOutputError as exc:
            row['reason'] = str(exc)
        from src.workflow.content_contracts import science_fields
        save(path, {'input_digest':key,'audit':row,'fields':science_fields(state) if adopted else None,
                    'result':tuple(result) if adopted else None})
        audit.append(row)
    state['source_visual_report'] = audit
    result[2]['visual_restoration'] = deepcopy(audit)
    return state,result
