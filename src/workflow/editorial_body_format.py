"""Nonblocking diagnostics for renderable, model-authored body formatting."""
from utils.model_body import formatting_errors

VERSION = 'editorial_body_format_advisory_v2'
LEGACY_VERSION = 'editorial_body_format_advisory_v1'


def _issues(module_id, entries, style, path, *, preserve_step_numbers=True):
    from src.layout.body_presentation import split_step_marker
    structured_steps = (preserve_step_numbers and style == 'steps' and
                        all('parent_item_id' in e for e in entries))
    errors = formatting_errors(entries, 'plain' if structured_steps else style)
    if structured_steps:
        main = ((i, e) for i, e in enumerate(entries) if not e['parent_item_id'])
        for position, (i, entry) in enumerate(main, 1):
            _, number, _ = split_step_marker(entry['text'])
            if number is not None and number != position:
                errors.append((i, 'Number main steps consecutively from 1'))
    issues = []
    for index, message in errors:
        entry = entries[index]
        if 'parent_item_id' in entry:
            # The model is asked for plain prose only when the formatting is defective.
            message = 'Remove hand-written list markers and indentation from this entry. The program renders them.'
        issues.append({'module_id': module_id, 'item_id': entry['item_id'],
                       'path': [*path, 'entries', index, 'text'], 'message': message})
    return issues


def writer_issues(raw, plan):
    return [issue for module in plan['modules']
            for issue in _issues(module['module_id'], raw['modules'][module['module_id']]['entries'],
                                 module['presentation_style'], ('modules', module['module_id']))]


def capacity_issues(raw, candidate):
    # Only changed modules are repair slots. An unchanged module's existing
    # formatting defect remains in the final report without invalidating a patch.
    styles = {m['module_id']: m['presentation_style'] for m in candidate['modules']}
    return [issue for index, module in enumerate(raw['modules'])
            for issue in _issues(module['module_id'], module['entries'], styles[module['module_id']],
                                 ('modules', index))]


def report(candidate, *, preserve_step_numbers=True):
    issues = [issue for index, module in enumerate(candidate['modules'])
              for issue in _issues(module['module_id'], module['entries'], module['presentation_style'],
                                   ('modules', index), preserve_step_numbers=preserve_step_numbers)]
    structured = any('parent_item_id' in e for m in candidate['modules'] for e in m['entries'])
    version = VERSION if preserve_step_numbers and structured else LEGACY_VERSION
    return {'version': version, 'candidate_id': candidate['candidate_id'],
            'status': 'format_defects' if issues else 'ok', 'issues': issues,
            'generation_blocking': False, 'admission': 'freeze_and_score'}
