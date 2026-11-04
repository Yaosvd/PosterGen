"""Measured capacity tasks and observed results, never model-certified success."""
from copy import deepcopy
import math

GUIDANCE_VERSION = 'editorial_capacity_guidance_v2'
RESULT_VERSION = 'editorial_capacity_result_v2'


def capacity_guidance(report):
    """One final evidence record; bounded search history stays local."""
    result = {k: deepcopy(v) for k, v in report.items() if k != 'geometry_trials'}
    result['measurement_version'] = result.pop('version', None)
    result.update(version=GUIDANCE_VERSION, ideal_band=[.9, 1.0])
    modules = []
    for row in report.get('modules', []):
        usage = row['utilization']
        # Use the fitter's existing physical tolerance, not float roundoff.
        compress = usage > 1 and row.get('overage_inches', 1) > .01
        action = 'compress' if compress else 'expand' if usage < .9 else 'keep'
        modules.append({**deepcopy(row), 'utilization_percent': round(100 * usage, 4),
                        'suggested_action': action})
    result['modules'] = modules
    return result


def module_tasks(report):
    """State the requested operation; numerical evidence has a single owner."""
    guidance = capacity_guidance(report)
    issues = (report.get('preflight') or {}).get('issues', [])
    tasks = []
    for row in guidance['modules']:
        mid = row['module_id']
        affected = any(i.get('section_id') == mid or
            (i.get('zone_id') and i['zone_id'] == row.get('zone_id')) or
            i.get('element_id') == mid or str(i.get('element_id', '')).startswith(mid + '_')
            for i in issues)
        budget = row.get('text_budget') or {}
        action = row['suggested_action']
        if budget.get('layout_pressure') or (affected and action == 'keep'):
            action = 'adjust_layout'
        tasks.append({'module_id': mid, 'action': action,
                      'priority': 1 if action in {'compress', 'adjust_layout'} else 2 if action == 'expand' else 3,
                      'measurement_status': budget.get('status', 'unavailable')})
    return tasks


def observed_edit(before, after):
    """Derive changes from candidates; never parse a model's reason."""
    old = {m['module_id']: m for m in before['modules']}
    new = {m['module_id']: m for m in after['modules']}
    changed = []
    for mid, module in new.items():
        if mid not in old or old[mid] == module:
            continue
        previous = old[mid]
        old_entries = {e['item_id']: e for e in previous['entries']}
        new_entries = {e['item_id']: e for e in module['entries']}
        changed.append({'module_id': mid,
            'changed_fields': [key for key in module if module[key] != previous.get(key)],
            'added_entry_ids': [eid for eid in new_entries if eid not in old_entries],
            'removed_entry_ids': [eid for eid in old_entries if eid not in new_entries],
            'rewritten_entry_ids': [eid for eid, entry in new_entries.items()
                if eid in old_entries and entry['text'] != old_entries[eid]['text']],
            'presentation_changed_entry_ids': [eid for eid, entry in new_entries.items()
                if eid in old_entries and any(entry[key] != old_entries[eid][key]
                    for key in ('display_label', 'parent_item_id'))],
            'entry_order_changed': list(old_entries) != list(new_entries),
            'before_words': sum(len(e['text'].split()) for e in previous['entries']),
            'after_words': sum(len(e['text'].split()) for e in module['entries'])})
    return {'version': 'editorial_observed_edit_v2',
            'changed': before != after,
            'added_module_ids': [mid for mid in new if mid not in old],
            'removed_module_ids': [mid for mid in old if mid not in new],
            'module_order_changed': list(old) != list(new),
            'narrative_changed': before['narrative_flow'] != after['narrative_flow'],
            'changed_modules': changed}


def _facts(row):
    if row is None:
        return None
    return {k: deepcopy(row[k]) for k in ('zone_id', 'current_words', 'utilization',
            'allocated_height', 'intrinsic_height', 'overage_inches', 'missing_height_inches',
            'width_inches', 'text_budget') if k in row}


def _direction(before, after, tolerance):
    if (type(before) not in (int, float) or type(after) not in (int, float)
            or not math.isfinite(before) or not math.isfinite(after)):
        return 'unavailable'
    return 'unchanged' if abs(after - before) <= tolerance else 'reduced' if after < before else 'increased'


def _result(record):
    before, after = record['measurements_before'], record['measurements_after']
    old = {m['module_id']: m for m in before.get('modules', [])}
    new = {m['module_id']: m for m in after.get('modules', [])}
    diffs = {m['module_id']: m for m in record['observed_edit']['changed_modules']}
    actions = {t['module_id']: t['action'] for t in record.get('requested_tasks', [])}
    modules = []
    for mid in dict.fromkeys([*old, *new]):
        a, b = old.get(mid), new.get(mid)
        diff = diffs.get(mid, {})
        modules.append({'module_id': mid, 'requested_action': actions.get(mid),
            'entry_text_changed': mid not in old or mid not in new or bool(
                diff.get('added_entry_ids') or diff.get('removed_entry_ids') or diff.get('rewritten_entry_ids')),
            'actual_edit': deepcopy(diff), 'before': _facts(a), 'after': _facts(b),
            'word_change': _direction((a or {}).get('current_words'), (b or {}).get('current_words'), 0),
            'text_height_change': _direction(((a or {}).get('text_budget') or {}).get('current_text_height_inches'),
                ((b or {}).get('text_budget') or {}).get('current_text_height_inches'), 1e-6),
            'overflow_change': _direction((a or {}).get('overage_inches'), (b or {}).get('overage_inches'), .01)})
    def geometry(row):
        budget = (row or {}).get('text_budget') or {}
        return {key: (row or {}).get(key) for key in ('zone_id', 'width_inches', 'allocated_height')}, {
            key: budget.get(key) for key in ('module_y_inches', 'before_text_height_inches',
                'text_width_inches', 'available_text_height_inches', 'visual_height_inches',
                'parallel_visual_height_inches', 'body_layout', 'font_size', 'font_family')}
    return {'version': RESULT_VERSION, 'modules': modules,
        'geometry_changed': (before.get('geometry_fingerprint') != after.get('geometry_fingerprint') or
            any(geometry(old.get(mid)) != geometry(new.get(mid)) for mid in dict.fromkeys([*old, *new]))),
        'total_overflow_change': _direction(before.get('total_overflow_inches'), after.get('total_overflow_inches'), .01),
        'new_overflow_module_ids': [mid for mid, b in new.items() if b.get('overage_inches', 0) > .01
                                  and old.get(mid, {}).get('overage_inches', 0) <= .01],
        'preflight_before': deepcopy(before.get('preflight')),
        'preflight_after': deepcopy(after.get('preflight')),
        'target_met': after.get('passed') is True and after.get('all_modules_90_percent') is True}


def record_measured_edit(history, candidate, report):
    """Attach the real fit only to its authored candidate, including no-ops."""
    if history and history[-1]['to'] == candidate['candidate_id']:
        if report.get('candidate_id') != candidate['candidate_id']:
            raise ValueError('Capacity measurement belongs to a different candidate')
        record = history[-1]
        record['measurements_after'] = capacity_guidance(report)
        record['measured_result'] = _result(record)


def last_edit_feedback(state, report):
    candidate_id = state['editorial_candidate']['candidate_id']
    if report.get('candidate_id') != candidate_id:
        raise ValueError('Capacity request has no matching candidate measurement')
    history = state.get('editorial_history') or []
    if not history:
        return None
    record = history[-1]
    after = record.get('measurements_after') or {}
    if (record['to'] != candidate_id or not record.get('measured_result') or
            after.get('candidate_id') != candidate_id or report.get('candidate_id') != candidate_id or
            after.get('geometry_fingerprint') != report.get('geometry_fingerprint')):
        raise ValueError('Latest capacity feedback has no matching final measurement')
    # Full before/after records remain local. Send small comparisons and refer
    # to the one current measurement instead of embedding it a second time.
    measured = record['measured_result']
    modules = []
    for row in measured['modules']:
        a, b = row['before'] or {}, row['after'] or {}
        pairs = {key: {'before': a.get(key), 'after': b.get(key)} for key in
                 ('current_words', 'utilization', 'overage_inches', 'width_inches', 'allocated_height')}
        for key in ('current_text_height_inches', 'available_text_height_inches', 'text_width_inches'):
            pairs[key] = {'before': (a.get('text_budget') or {}).get(key),
                          'after': (b.get('text_budget') or {}).get(key)}
        modules.append({key: deepcopy(row[key]) for key in
            ('module_id', 'requested_action', 'entry_text_changed', 'actual_edit',
             'word_change', 'text_height_change', 'overflow_change')})
        modules[-1].update(measurement_pairs=pairs,
            current_measurement_ref={'field': 'capacity_guidance.modules', 'module_id': row['module_id']})
    preflight = {}
    for phase in ('before', 'after'):
        value = measured.get('preflight_' + phase)
        preflight[phase] = (None if value is None else
            {'passed': value.get('passed'), 'issue_count': len(value.get('issues') or [])})
    # Actual differences, not the previous reason or its predicted success.
    return {'version': RESULT_VERSION, 'from_candidate_id': record['from'],
            'to_candidate_id': record['to'], 'geometry_fingerprint': after.get('geometry_fingerprint'),
            'candidate_changed': record['changed'], 'modules': modules,
            'observed_structure': {key: deepcopy(record['observed_edit'][key]) for key in
                ('added_module_ids', 'removed_module_ids', 'module_order_changed', 'narrative_changed')},
            **{key: deepcopy(measured[key]) for key in ('geometry_changed', 'total_overflow_change',
                'new_overflow_module_ids', 'target_met')},
            'preflight_summary': preflight, 'current_preflight_ref': 'capacity_guidance.preflight'}
