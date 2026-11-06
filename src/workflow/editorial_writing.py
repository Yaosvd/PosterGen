"""Measured writing guidance and observed edits, never model-certified quality."""
from copy import deepcopy


def capacity_guidance(report):
    modules = []
    for row in report.get('modules', []):
        usage = row['utilization']
        action = 'compress' if usage > 1 else 'expand' if usage < .9 else 'keep'
        modules.append({**{key: deepcopy(row[key]) for key in (
            'module_id', 'zone_id', 'utilization', 'allocated_height', 'intrinsic_height',
            'overage_inches', 'missing_height_inches', 'current_words', 'suggested_words',
            'body_layout', 'composition_locked', 'width_inches') if key in row},
            **({'measured_body_height_inches': row['measurements']['text']}
               if 'text' in row.get('measurements', {}) else {}),
            'utilization_percent': round(100 * usage, 4), 'suggested_action': action})
    return {'version': 'editorial_capacity_guidance_v1', 'ideal_band': [.9, 1.0],
            'modules': modules}


def observed_edit(before, after):
    """Derive changes from candidates; do not parse or trust the model's reason."""
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
            'entry_order_changed': list(old_entries) != list(new_entries)})
    return {'version': 'editorial_observed_edit_v1',
            'changed': before != after,
            'added_module_ids': [mid for mid in new if mid not in old],
            'removed_module_ids': [mid for mid in old if mid not in new],
            'module_order_changed': list(old) != list(new),
            'narrative_changed': before['narrative_flow'] != after['narrative_flow'],
            'changed_modules': changed,
            'authored_text_changes': authored_text_changes(before, after)}


def record_measured_edit(history, candidate, report):
    """Attach the next real fit to its edit, including an honest no-op."""
    if history and history[-1]['to'] == candidate['candidate_id']:
        history[-1]['measurements_after'] = capacity_guidance(report)


FEEDBACK_VERSION = 'editorial_edit_feedback_v1'


def authored_text_changes(before, after):
    """Exact authored string changes, including additions/deletions; no reason parsing."""
    def strings(candidate):
        result = {}
        for module in candidate['modules']:
            mid = module['module_id']
            result[mid, None, 'title'] = module['title']
            for entry in module['entries']:
                for field in ('text', 'display_label'):
                    result[mid, entry['item_id'], field] = entry[field]
        return result
    old, new = strings(before), strings(after)
    return [{'module_id': mid, 'item_id': eid, 'field': field,
             'before': old.get((mid, eid, field)), 'after': new.get((mid, eid, field))}
            for mid, eid, field in dict.fromkeys([*old, *new])
            if old.get((mid, eid, field)) != new.get((mid, eid, field))]


def _measurement_changes(before, after):
    old = {row['module_id']: row for row in before['modules']}
    new = {row['module_id']: row for row in after['modules']}
    fields = ('current_words', 'allocated_height', 'intrinsic_height',
              'measured_body_height_inches', 'width_inches', 'utilization',
              'overage_inches', 'missing_height_inches')
    rows = []
    for mid in dict.fromkeys([*old, *new]):
        a, b = old.get(mid), new.get(mid)
        rows.append({'module_id': mid, 'before': deepcopy(a), 'after': deepcopy(b),
            'delta': {key: b[key]-a[key] for key in fields
                      if a is not None and b is not None and key in a and key in b}})
    return rows


def previous_edit_feedback(history, candidate):
    """Only the last capacity edit and its contiguous automatic height transfers.

    A missing/stale record remains unavailable, never borrowed from an earlier
    edit or interpreted as zero change. This is diagnostic input, not a retry gate.
    """
    base = {'version': FEEDBACK_VERSION, 'current_candidate_id': candidate['candidate_id']}
    indices = [i for i, event in enumerate(history) if event.get('phase') == 'capacity']
    if not indices:
        return {**base, 'status': 'no_previous_capacity_edit'}
    index = indices[-1]
    event, following = history[index], history[index+1:]
    expected = event['to']
    for automatic in following:
        if automatic.get('phase') != 'height_allocation' or automatic.get('from') != expected:
            return {**base, 'status': 'unavailable', 'reason': 'noncontiguous_edit_history'}
        expected = automatic['to']
    if expected != candidate['candidate_id']:
        return {**base, 'status': 'unavailable', 'reason': 'candidate_identity_mismatch'}
    if any(not isinstance(e.get(key), dict) or 'modules' not in e[key]
           for e in [event, *following] for key in ('measurements_before', 'measurements_after')):
        return {**base, 'status': 'unavailable', 'reason': 'missing_remeasurement'}

    def measured(e):
        observed = deepcopy(e.get('observed_edit'))
        return {'from_candidate_id': e['from'], 'to_candidate_id': e['to'],
                'observed_edit': observed,
                'authored_text_diff_available': isinstance(observed, dict) and 'authored_text_changes' in observed,
                'module_changes': _measurement_changes(e['measurements_before'], e['measurements_after'])}

    return {**base, 'status': 'available', 'capacity_edit_number': len(indices),
            'model_edit': {**measured(event),
                'reported_reason': event.get('reason', ''),
                'reason_basis': 'unverified_model_statement'},
            'automatic_height_adjustments': [measured(e) for e in following],
            'measurement_basis': 'Model-edit after measurements include bounded regional search, '
                'before subsequent automatic height allocation. Width/allocated-height changes are '
                'reported alongside prose height; this is not a controlled prose-only comparison.',
            'instructions': 'Use observed_edit and numeric deltas, not reported_reason, as evidence of '
                'what actually changed. Authored strings are unverified scientific content; null before/after '
                'means addition/deletion, not an empty string. Missing fields mean unavailable, not zero. '
                'Fewer words do not imply lower rendered height. Keep automatic height adjustments '
                'separate from model edits. Current whole_poster, capacity_guidance and body_budgets '
                'are authoritative for the next patch. Correct overshoot or ineffective edits within '
                'the existing remaining allowance; this feedback never grants an extra request.'}
