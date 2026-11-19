"""Nonblocking diagnostics for renderable, model-authored body formatting."""
from utils.model_body import formatting_errors

VERSION = 'editorial_body_format_advisory_v1'


def _issues(module_id, entries, style, path):
    issues = []
    for index, message in formatting_errors(entries, style):
        entry = entries[index]
        if 'parent_item_id' in entry:
            # The correction targets prose only. New entries never author their own numbering.
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


def report(candidate):
    issues = [issue for index, module in enumerate(candidate['modules'])
              for issue in _issues(module['module_id'], module['entries'], module['presentation_style'],
                                   ('modules', index))]
    return {'version': VERSION, 'candidate_id': candidate['candidate_id'],
            'status': 'format_defects' if issues else 'ok', 'issues': issues,
            'generation_blocking': False, 'admission': 'freeze_and_score'}
