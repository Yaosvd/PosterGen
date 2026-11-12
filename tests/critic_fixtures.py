"""Offline model responses, never scientific or aesthetic acceptance evidence."""
from copy import deepcopy

from src.workflow.editorial_critic import CONTENT_KEYS, VISUAL_KEYS


def assessment(score=80, *, module_id='', original_support=''):
    return {'score': score, 'assessment_status': 'assessed', 'reason': 'OFFLINE criterion observation.',
            'evidence': [{'module_id': module_id, 'element_id': '', 'measurement_id': '', 'finding_id': '',
                          'observation': 'OFFLINE evidence only.', 'original_support': original_support}],
            'uncertainty': ''}


def finding(module_id='', *, scope='scientific_integrity', severity='major'):
    return {'severity': severity, 'scope': scope,
            'location': {'section_id': module_id, 'zone_id': '', 'element_id': ''},
            'observation': 'OFFLINE review finding.', 'original_support': 'OFFLINE original text.',
            'required_outcome': 'Review the identified explanation.',
            'allowed_operations': [], 'forbidden_operations': ['invent_claim']}


def content_reply(modules, *, science=100, score=80, scientific_issues=False):
    ids = [m['module_id'] for m in modules]
    return {'assessments': {
        'scientific_integrity': assessment(science, original_support='OFFLINE paper support.'),
        **{k: assessment(score) for k in CONTENT_KEYS}},
        'content_dependencies': {
            'modules': [{'module_id': mid, 'meaning': 'OFFLINE module explanation.',
                         'prerequisites': []} for mid in ids],
            'relations': [], 'reason': 'OFFLINE independent modules, not a required role order.'},
        'issues': [finding(ids[0])] if scientific_issues else [], 'review_notes': [],
        'positive_patterns': [{'scope': 'content', 'observation': 'OFFLINE content observation.'}],
        'reason': 'OFFLINE response, not real scientific validation.'}


def visual_reply(modules, *, score=80):
    ids = [m['module_id'] for m in modules]
    return {'assessments': {k: assessment(score) for k in VISUAL_KEYS},
        'reading_review': {'entry_module_ids': ids[:1], 'likely_paths': [ids],
                           'ambiguous_transitions': [], 'dependency_conflicts': [],
                           'reason': 'OFFLINE observed path, not a fixed family rule.'},
        'issues': [], 'review_notes': [],
        'positive_patterns': [{'scope': 'visual', 'observation': 'OFFLINE clear figure.'}],
        'reason': 'OFFLINE final image evaluation.'}


def content_wire_reply(raw, state=None):
    """Encode an offline canonical fixture in the content request's keyed format."""
    result = reference_wire_reply(raw, state)
    modules = result['content_dependencies']['modules']
    assert len({m['module_id'] for m in modules}) == len(modules)
    result['content_dependencies']['modules'] = {
        m['module_id']: {k: v for k, v in m.items() if k != 'module_id'} for m in modules}
    return result


def reference_wire_reply(raw, state=None):
    """Encode VALID offline report references; never used to repair real responses."""
    from src.workflow.editorial_critic import request_reference_catalog
    from src.workflow.critic_references import EMPTY_LOCATION
    refs = request_reference_catalog(state) if state else {
        'evidence_refs': {'E000': {'measurement_id': '', 'finding_id': ''}},
        'location_refs': {'L000': dict(EMPTY_LOCATION)}}
    result = deepcopy(raw)
    def locate(target):
        nonempty = {k: v for k, v in target.items() if v}
        if not nonempty:
            return 'L000'
        matches = [(key, value) for key, value in refs['location_refs'].items()
                   if all(value[k] == v for k, v in nonempty.items())]
        # Select the exact scope (module/zone), not an arbitrary descendant.
        matches = [(k,v) for k,v in matches if bool(v['element_id']) == bool(target.get('element_id'))
                   and bool(v['section_id']) == bool(target.get('section_id'))]
        assert len(matches) == 1, target
        return matches[0][0]
    for metric in result['assessments'].values():
        for row in metric['evidence']:
            pair = {k: row.pop(k) for k in ('measurement_id', 'finding_id')}
            row['evidence_ref'] = next(k for k,v in refs['evidence_refs'].items() if v == pair)
            target = {**EMPTY_LOCATION, 'section_id': row.pop('module_id'), 'element_id': row.pop('element_id')}
            row['location_refs'] = [locate(t) for t in row.pop('locations', [target])]
    for field in ('issues', 'review_notes'):
        for row in result[field]:
            target = row.pop('location')
            row['location_refs'] = [locate(t) for t in row.pop('locations', [target])]
    return result
