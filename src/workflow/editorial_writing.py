"""Measured writing guidance and observed edits, never model-certified quality."""
from copy import deepcopy


def capacity_guidance(report):
    modules = []
    for row in report.get('modules', []):
        usage = row['utilization']
        action = 'compress' if usage > 1 else 'expand' if usage < .9 else 'keep'
        modules.append({**{key: deepcopy(row[key]) for key in (
            'module_id', 'zone_id', 'utilization', 'allocated_height', 'intrinsic_height',
            'overage_inches', 'missing_height_inches', 'current_words', 'suggested_words') if key in row},
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
            'changed_modules': changed}


def record_measured_edit(history, candidate, report):
    """Attach the next real fit to its edit, including an honest no-op."""
    if history and history[-1]['to'] == candidate['candidate_id']:
        history[-1]['measurements_after'] = capacity_guidance(report)
