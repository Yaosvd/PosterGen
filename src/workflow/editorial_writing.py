"""Measured writing guidance and observed edits, never model-certified quality."""
from copy import deepcopy


def capacity_tasks(result, plan=None):
    """One task per measured module, with only the actual BODY word reference."""
    from src.workflow.editorial_authoring import content_guidance
    tasks = []
    for row in writing_assessment(result)['modules']:
        task = {key: deepcopy(value) for key, value in row.items() if key != 'suggested_words'}
        task['action'] = task.pop('suggested_action')
        task['requires_prose_rewrite'] = task['action'] in {'compress', 'expand'}
        task['content_guidance'] = content_guidance(plan, task['module_id'])
        current, reference = task['current_words'], task['reference_words']
        # Display exact integer limits; the measured reference and action stay unchanged.
        minimum_words = maximum_words = None
        if reference is not None and reference > 0:
            minimum_words = (95 * reference + 99) // 100
            maximum_words = (105 * reference) // 100
        if task['action'] == 'compress' and (reference is None or reference <= 0 or
                task['available_body_height_inches'] <= 0 or task['fixed_content_overflow_inches'] > 0):
            task['rewrite_instruction'] = (
                'This frame has no reliable prose allowance or its fixed content already overflows. Include this '
                'module with its complete body candidate; do not omit it because the frame is problematic. Make '
                'any useful, accurate prose reduction available while preserving the complete core message. Do '
                'not invent a usable word allowance from a missing or nonpositive reference_words value. If a '
                'valid positive reference is supplied, pursue the specified 95%-105% total-word range without '
                'using predicted noncompliance as a reason to skip the edit. Fixed title or visual overflow '
                'cannot be solved by shortening prose alone; legal geometry coordination belongs to the program '
                'under the frozen constraints. Return the complete candidate and identify the remaining '
                'fixed-content overflow or unavailable allowance in reason. Do not return empty prose, alter '
                'scientific facts or claim that the fixed-content defect has been repaired by a body rewrite.')
        elif task['action'] == 'compress':
            task['rewrite_instruction'] = (
                f'Shorten the current {current}-word body. Use {reference} words as the normal target; the '
                f'complete replacement must contain {minimum_words}-{maximum_words} words TOTAL across all entries'
                f' (95%-105% of reference_words) AND strictly fewer than {current} words. Compression MUST NOT '
                'become expansion. Aim for 90%-100% utilization, with 85% as the minimum: BODY utilization for '
                'image_left_text_right, whole-module utilization otherwise. Use the measured space deficit to '
                'choose the reduction without unnecessary over-compression. Preserve useful existing '
                'explanations; remove repetition and low-value detail, and omit optional points when necessary to'
                ' meet the limits. Adequately explain the core content and retain qualifications needed for the '
                'accuracy of retained statements. Return the revised text, not a description of planned cuts. '
                'Execute the compression and return this module with its COMPLETE revised entries even if you '
                'expect some constraints to remain unresolved. Return an accurate revision toward the supplied '
                'word and utilization targets while preserving the necessary core explanation. Identify specific '
                'remaining constraints in reason; the program will measure the actual result. Do not omit this '
                'module, substitute a plan for the text, or claim that a remaining defect has been resolved.')
        elif task['action'] == 'expand':
            word_target = (
                f'Use {reference} words as the normal target; return '
                f'{minimum_words}-{maximum_words} words TOTAL across all entries '
                '(95%-105% of reference_words). '
                if minimum_words is not None else
                'No reliable positive reference_words allowance is available; do not invent '
                'a numeric word range. Use the supplied measurements and paper material '
                'to guide useful expansion and report the unavailable allowance in reason. ')
            task['rewrite_instruction'] = (
                f'Expand the current {current}-word body with useful paper-supported explanation. '
                f'{word_target}Return the COMPLETE expanded entries, not a description of planned additions. '
                'Complete missing explanations in existing entries; if they are already clear, add another '
                "distinct useful point about the same module's core content as a new main entry. An independent "
                'relevant point is not filler. Avoid duplication of other modules and exhaustive repetition of '
                'table values. Follow the body-underfill action even when an image fills the module. Aim for '
                '90%-100% utilization, with 85% as the minimum; use BODY utilization for image_left_text_right '
                'and whole-module utilization otherwise. Continue toward 90% or higher while useful additions fit'
                ' the applicable word guidance and the physical frame. Execute useful expansion by enriching existing '
                'entries or adding a distinct relevant main entry, and return this module with its COMPLETE '
                'revised entries. Do not omit it merely because you expect the fill target may still be missed. '
                'Return the best accurate, source-supported expansion you can produce, identify any specific '
                'remaining source or space constraint in reason, and leave the actual utilization judgment to the'
                ' program. Do not invent content, add filler or claim that remaining underfill has been resolved.')
        elif task.get('action_reason') == 'body_measurement_unavailable':
            task['rewrite_instruction'] = 'Body measurement unavailable; do not expand blindly or claim a measured fit.'
        else:
            task['rewrite_instruction'] = 'Keep this body under the stated action rule; the word reference is not an editing target.'
        tasks.append(task)
    return {'version': 'editorial_capacity_tasks_v2', 'ideal_band': [.9, 1.0],
            'modules': tasks}


def writing_assessment(result):
    """One decision for tasks, stopping and outcomes; physical metrics stay intact."""
    from src.layout.editorial_body_budget import measured_body_budgets, BODY_FILL_TARGET
    from src.layout.editorial_composition import HORIZONTAL
    report = result['report']
    budgets = {r['module_id']: r for r in measured_body_budgets(result)['modules']}
    # Never reuse an attached assessment after the geometry or prose changes.
    rows = capacity_guidance({k: v for k, v in report.items() if k != 'writing_fit'})['modules']
    for row in rows:
        row.update(budgets[row['module_id']])
        row['action_reason'] = 'whole_module_utilization'
        if row.get('body_layout') != HORIZONTAL:
            continue
        overflow = max(row.get('overage_inches', 0), row.get('body_overflow_inches') or 0,
                       row.get('fixed_content_overflow_inches') or 0)
        if overflow > 0 or row['utilization'] > 1:
            row.update(suggested_action='compress', action_reason='physical_overflow')
        elif row['body_measurement_status'] != 'measured':
            row.update(suggested_action='keep', action_reason='body_measurement_unavailable')
        elif row['body_utilization'] < BODY_FILL_TARGET:
            if row['body_spare_height_inches'] >= row['body_line_height_inches']:
                row.update(suggested_action='expand', action_reason='horizontal_body_underfill')
            else:
                row.update(suggested_action='keep', action_reason='below_one_line_exemption')
        else:
            row.update(suggested_action='keep', action_reason='horizontal_body_target_met')
    unknown = any(r.get('body_layout') == HORIZONTAL and
                  r['body_measurement_status'] != 'measured' for r in rows)
    needs_edit = any(r['suggested_action'] != 'keep' for r in rows)
    target_met = bool(rows) and bool(report.get('passed')) and not needs_edit and not unknown
    return {'version': 'editorial_writing_fit_v1', 'body_fill_target': BODY_FILL_TARGET,
            'minimum_spare_body_lines': 1, 'needs_edit': needs_edit, 'target_met': target_met,
            'status': ('layout_defects_remain' if not report.get('passed') else
                       'measurement_unavailable' if unknown else
                       'underfill_remaining' if needs_edit else 'target_met'),
            'modules': rows, 'science_verified': False}


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
    from src.layout.body_presentation import paragraphs
    from src.workflow.editorial_contract import make_board
    from utils.model_body import prose

    def texts(candidate):
        visible = {}
        for section in make_board(candidate)['spatial_content_plan']['sections']:
            if section.get('body_format'):
                lines = [prose(text) for text in section['text_content']]
            else:
                lines = [(p['label'] + ': ' if p['label'] else '') + p['text']
                         for p in paragraphs(section)]
            visible[section['section_id']] = ' '.join(' '.join(lines).split())
        return visible
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


def _underfill_gap(row):
    from src.layout.editorial_composition import HORIZONTAL
    if row.get('body_layout') == HORIZONTAL and row.get('body_missing_height_inches') is not None:
        return row['body_missing_height_inches']
    return row['missing_height_inches']


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
        elif current.get('action_reason') == 'body_measurement_unavailable':
            outcome = 'measurement_unavailable'
        elif current['suggested_action'] == 'keep':
            outcome = ('below_one_line_exemption' if current.get('action_reason') ==
                       'below_one_line_exemption' else 'target_met')
        elif action == 'expand':
            if not change['prose_changed']:
                outcome = 'rewrite_not_executed'
            elif _underfill_gap(current) < _underfill_gap(before):
                outcome = 'improved_underfill_remaining'
            else:
                outcome = 'rewrite_did_not_reduce_underfill'
        else:
            outcome = 'underfill_remaining'
        rows.append({**change, 'action': action, 'outcome': outcome,
                     'before': deepcopy(before), 'after': deepcopy(current)})
    edit['capacity_result'] = {
        'version': 'editorial_capacity_result_v2', 'candidate_id': candidate['candidate_id'],
        'measurement_scope': 'final_fit_including_cpu_geometry',
        'status': report['writing_fit']['status'] if 'writing_fit' in report else
                  'layout_defects_remain' if not report['passed'] else
                  'target_met' if report['all_modules_90_percent'] else 'underfill_remaining',
        'total_overflow_inches': report['total_overflow_inches'],
        'total_underfill_inches': report['total_underfill_inches'],
        'modules': rows,
        'added_module_ids': [mid for mid in after if mid not in {r['module_id'] for r in rows}],
        'science_verified': False}


def capacity_guidance(report):
    if 'writing_fit' in report:
        return {'version': 'editorial_capacity_guidance_v2', 'ideal_band': [.9, 1.0],
                'modules': deepcopy(report['writing_fit']['modules'])}
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
    from utils.model_body import prose
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
                if eid in old_entries and (any(entry.get(k) != old_entries[eid].get(k)
                    for k in ('parent_item_id', 'display_label')) or
                    ('parent_item_id' not in entry and entry['text'] != old_entries[eid]['text'] and
                     prose(entry['text']) == prose(old_entries[eid]['text'])))],
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
