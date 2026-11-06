"""Measured writing guidance and observed edits, never model-certified quality."""
from copy import deepcopy


def capacity_tasks(result):
    """One task per measured module, with only the actual BODY word reference."""
    from src.layout.editorial_body_budget import measured_body_budgets
    budgets = {row['module_id']: row for row in measured_body_budgets(result)['modules']}
    tasks = []
    for row in capacity_guidance(result['report'])['modules']:
        task = {key: value for key, value in row.items() if key != 'suggested_words'}
        task.update(deepcopy(budgets[row['module_id']]))
        task['action'] = task.pop('suggested_action')
        task['requires_prose_rewrite'] = task['action'] in {'compress', 'expand'}
        current, reference = task['current_words'], task['reference_words']
        if task['action'] == 'compress' and (reference == 0 or
                task['available_body_height_inches'] <= 0 or task['fixed_content_overflow_inches'] > 0):
            task['rewrite_instruction'] = (
                'This frame has no reliable prose allowance or its fixed content already overflows. '
                'Coordinate legal space within the frozen constraints and retain essential explanation. '
                'Do not return empty prose or claim that a shorter body alone solves fixed-content '
                'overflow. Identify any remaining incompatible constraint in reason.')
        elif task['action'] == 'compress':
            task['rewrite_instruction'] = (
                f'Replace the current {current}-word body with a fresh, coherent body of about '
                f'{reference} words TOTAL across all entries. Write the replacement text, not a '
                'description of planned cuts. Merge entries and omit optional derivations/examples; '
                'do not repeat every number already legible in the selected visual. Preserve the '
                'essential mechanism, interpretation and scientific conditions. If fixed content '
                'or essential conditions make this estimate infeasible, identify that specific '
                'constraint; do not claim the unchanged body satisfies this task.')
        elif task['action'] == 'expand':
            task['rewrite_instruction'] = (
                f'Expand this {current}-word body toward about {reference} words with relevant '
                'paper-supported explanation. Return the expanded entries; avoid filler and '
                'duplicating other modules. This estimate is not a requirement to add unsupported detail.')
        else:
            task['rewrite_instruction'] = 'Keep this fitting body; the word reference is not an editing target.'
        tasks.append(task)
    return {'version': 'editorial_capacity_tasks_v1', 'ideal_band': [.9, 1.0],
            'modules': tasks}


def capacity_measurements(report):
    """Final poster-level facts only; module facts live once in capacity_tasks.

    Search trials and intermediate measurements remain in the local fit report.
    An allowlist also prevents new nested search diagnostics leaking into prompts.
    """
    return {key: deepcopy(report[key]) for key in (
        'version', 'status', 'passed', 'total_overflow_inches', 'total_underfill_inches',
        'all_modules_90_percent', 'geometry_fingerprint') if key in report}


def prose_changes(before, after):
    """Ignore IDs, model reasons and whitespace-only rewrites of visible prose."""
    from src.workflow.editorial_contract import make_board
    from src.layout.body_presentation import paragraphs
    def texts(candidate):
        # Reuse renderer label visibility/dedup rules; bullet numbering and
        # indentation alone are presentation changes, not rewritten prose.
        return {s['section_id']: ' '.join(' '.join(
            (p['label'] + ': ' if p['label'] else '') + p['text']
            for p in paragraphs(s)).split())
            for s in make_board(candidate)['spatial_content_plan']['sections']}
    old_text, new_text = texts(before), texts(after)
    old = {m['module_id']: m for m in before['modules']}
    new = {m['module_id']: m for m in after['modules']}
    rows = []
    for mid in dict.fromkeys([*old, *new]):
        a, b = old.get(mid), new.get(mid)
        rows.append({'module_id': mid, 'prose_changed': a is None or b is None or old_text[mid] != new_text[mid],
                     'words_before': sum(len(e['text'].split()) for e in a['entries']) if a else 0,
                     'words_after': sum(len(e['text'].split()) for e in b['entries']) if b else 0})
    return rows


def record_capacity_result(history, candidate, report):
    """Report final measured outcomes, including any later CPU height transfer.

    This is diagnostic, not a new request, scientific verdict or admission gate.
    """
    edit = next((h for h in reversed(history) if h.get('phase') == 'capacity'), None)
    if edit is None:
        return
    changes = {r['module_id']: r for r in edit['prose_changes']}
    after = {r['module_id']: r for r in capacity_guidance(report)['modules']}
    rows = []
    for before in edit['measurements_before']['modules']:
        mid = before['module_id']
        change = changes[mid]
        current = after.get(mid)
        action = before['suggested_action']
        if current is None:
            outcome = 'module_removed'
        elif current['overage_inches'] > 0:
            if action != 'compress':
                outcome = 'introduced_overflow'
            elif not change['prose_changed']:
                outcome = 'rewrite_not_executed'
            elif current['overage_inches'] < before['overage_inches']:
                outcome = 'improved_overflow_remaining'
            else:
                outcome = 'rewrite_did_not_reduce_overflow'
        elif current['utilization'] >= .9:
            outcome = 'target_met'
        elif action == 'expand':
            if not change['prose_changed']:
                outcome = 'rewrite_not_executed'
            elif current['missing_height_inches'] < before['missing_height_inches']:
                outcome = 'improved_underfill_remaining'
            else:
                outcome = 'rewrite_did_not_reduce_underfill'
        else:
            outcome = 'underfill_remaining'
        rows.append({**change, 'action': action, 'outcome': outcome,
                     'before': deepcopy(before), 'after': deepcopy(current)})
    edit['capacity_result'] = {
        'version': 'editorial_capacity_result_v1', 'candidate_id': candidate['candidate_id'],
        'measurement_scope': 'final_fit_including_cpu_geometry',
        'status': 'layout_defects_remain' if not report['passed'] else
                  'target_met' if report['all_modules_90_percent'] else 'underfill_remaining',
        'total_overflow_inches': report['total_overflow_inches'],
        'total_underfill_inches': report['total_underfill_inches'],
        'modules': rows,
        'added_module_ids': [mid for mid in after if mid not in {r['module_id'] for r in rows}],
        'science_verified': False}


def capacity_guidance(report):
    modules = []
    for row in report.get('modules', []):
        usage = row['utilization']
        action = 'compress' if usage > 1 else 'expand' if usage < .9 else 'keep'
        modules.append({**{key: deepcopy(row[key]) for key in (
            'module_id', 'zone_id', 'utilization', 'allocated_height', 'intrinsic_height',
            'overage_inches', 'missing_height_inches', 'current_words', 'suggested_words',
            'body_layout', 'composition_locked') if key in row},
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
