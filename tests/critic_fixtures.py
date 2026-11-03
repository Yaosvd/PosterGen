"""Offline model responses, never scientific or aesthetic acceptance evidence."""
from src.workflow.editorial_critic import CONTENT_KEYS, VISUAL_KEYS


def assessment(score=80, *, module_id='', original_support=''):
    return {'score': score, 'assessment_status': 'assessed', 'reason': 'OFFLINE criterion observation.',
            'evidence': [{'module_id': module_id, 'element_id': '', 'measurement_id': '',
                          'observation': 'OFFLINE evidence only.', 'original_support': original_support}],
            'uncertainty': ''}


def finding(module_id='', *, scope='scientific_integrity', severity='major'):
    return {'severity': severity, 'scope': scope,
            'location': {'section_id': module_id, 'zone_id': '', 'element_id': ''},
            'observation': 'OFFLINE review finding.', 'original_support': 'OFFLINE original text.',
            'required_outcome': 'Review the identified explanation.',
            'allowed_operations': [], 'forbidden_operations': ['invent_claim']}


def content_reply(modules, *, science=100, score=80, status='supported'):
    ids = [m['module_id'] for m in modules]
    return {'status': status, 'assessments': {
        'scientific_integrity': assessment(science, original_support='OFFLINE paper support.'),
        **{k: assessment(score) for k in CONTENT_KEYS}},
        'content_dependencies': {
            'modules': [{'module_id': mid, 'meaning': 'OFFLINE module explanation.',
                         'prerequisites': []} for mid in ids],
            'relations': [], 'reason': 'OFFLINE independent modules, not a required role order.'},
        'issues': [finding(ids[0])] if status == 'issues' else [],
        'positive_patterns': [{'scope': 'content', 'observation': 'OFFLINE content observation.'}],
        'reason': 'OFFLINE response, not real scientific validation.'}


def visual_reply(modules, *, score=80):
    ids = [m['module_id'] for m in modules]
    return {'assessments': {k: assessment(score) for k in VISUAL_KEYS},
        'reading_review': {'entry_module_ids': ids[:1], 'likely_paths': [ids],
                           'ambiguous_transitions': [], 'dependency_conflicts': [],
                           'reason': 'OFFLINE observed path, not a fixed family rule.'},
        'issues': [], 'positive_patterns': [{'scope': 'visual', 'observation': 'OFFLINE clear figure.'}],
        'reason': 'OFFLINE final image evaluation.'}
