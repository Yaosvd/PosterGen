"""Final observations, derived status and failure attribution; offline only."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from critic_fixtures import content_reply, visual_reply, finding
from test_editorial_model_scoring import context, responses
from src.critic.base import EvaluationResult, issue
from src.workflow import editorial_critic as critic


def note(kind='advisory', scope='scientific_integrity'):
    return {'note_type': kind, 'scope': scope,
            'location': {'section_id': '', 'zone_id': '', 'element_id': ''},
            'observation': 'OFFLINE optional explanation or unresolved question.',
            'original_support': 'OFFLINE source support or uncertainty basis.',
            'recommendation': 'Review if relevant; this is not a confirmed error.'}


def test_retracted_comparator_suspicion_has_no_duplicate_status_to_contradict(context):
    content, _ = responses(context, science=95)
    verified = 'Checked 0.9889 > 0.9856; the comparator statement is correct. No change needed.'
    content['assessments']['scientific_integrity']['evidence'][0]['observation'] = verified
    content['issues'] = [finding(scope='information_coverage', severity='minor')]
    content['review_notes'] = [note('advisory')]
    content['review_notes'][0]['observation'] = 'Optional emphasis on the verified zero-error result.'
    assert 'status' not in content
    critic._validate(content, critic.CONTENT_SCHEMA, context.state)
    assert critic.scientific_status(content) == 'supported'
    assert content['assessments']['scientific_integrity']['score'] == 95


def test_program_never_reclassifies_or_deletes_scientific_prose_by_keywords(context):
    content, _ = responses(context, science=95)
    content['issues'] = [finding(severity='warning')]
    content['issues'][0]['observation'] = 'No change needed. This is fine. The model still classified this as an issue.'
    original = deepcopy(content)
    critic._validate(content, critic.CONTENT_SCHEMA, context.state)
    assert critic.scientific_status(content) == 'issues'
    assert content == original


@pytest.mark.parametrize('availability,confirmed,kind,scope,expected', [
    ('assessed', False, None, 'scientific_integrity', 'supported'),
    ('assessed', False, 'advisory', 'scientific_integrity', 'supported'),
    ('assessed', False, 'uncertainty', 'scientific_integrity', 'uncertain'),
    ('assessed', False, 'uncertainty', 'information_coverage', 'supported'),
    ('assessed', True, 'advisory', 'scientific_integrity', 'issues'),
    ('uncertain', False, None, 'scientific_integrity', 'uncertain'),
    ('uncertain', True, 'uncertainty', 'scientific_integrity', 'issues'),
    ('unavailable', False, None, 'scientific_integrity', 'unavailable'),
    ('unavailable', True, 'uncertainty', 'scientific_integrity', 'unavailable'),
])
def test_status_summarizes_model_categories_without_prose_or_score_rules(
        context, availability, confirmed, kind, scope, expected):
    content, _ = responses(context, science=95)
    metric = content['assessments']['scientific_integrity']
    metric.update(assessment_status=availability, uncertainty='OFFLINE interpretation limit.')
    if availability == 'unavailable':
        metric['score'] = None
    if confirmed:
        content['issues'] = [finding(severity='warning')]
    if kind:
        content['review_notes'] = [note(kind, scope)]
    before = deepcopy(content)
    critic._validate(content, critic.CONTENT_SCHEMA, context.state)
    assert critic.scientific_status(content) == expected
    if availability != 'unavailable':
        # Neither a high nor low scientific score controls this display label.
        metric['score'] = 0
        assert critic.scientific_status(content) == expected
        metric['score'] = 95
    assert content == before


@pytest.mark.parametrize('category,expected', [
    ('advisory', 'supported'), ('uncertainty', 'uncertain'), ('confirmed', 'issues')])
def test_classified_observations_preserve_all_scores_and_complete_both_stages(
        context, monkeypatch, category, expected):
    content, visual = responses(context, science=95, score=80)
    if category == 'confirmed':
        content['issues'] = [finding(severity='warning')]
    else:
        content['review_notes'] = [note(category)]
    content['review_notes'].append(note('advisory', 'information_depth'))
    visual['review_notes'] = [note('advisory', 'reading_order_quality')]
    originals = deepcopy((content, visual))
    calls = []
    def reply(state, kind, payload, schema, **kwargs):
        calls.append(kind)
        assert kwargs['correction'] is False
        raw = content if kind == 'editorial_content_critic' else visual
        critic._validate(raw, schema, state)
        return deepcopy(raw)
    monkeypatch.setattr(critic, 'request', reply)
    critic.make_critic(context.config)(context.state)
    report = context.state['critic_report']
    assert calls == ['editorial_content_critic', 'editorial_visual_critic']
    assert report['evaluation_status'] == 'complete'
    assert report['overall_score'] == 83.75  # 95*.25 + 80*.75; no issue/notes penalty.
    assert report['factual_consistency_status'] == expected
    assert len(report['submetric_scores']) == 23
    assert all(s['status'] == 'complete' for s in report['assessment_stages'].values())
    assert report['review_notes'] == [dict(source='content', **n) for n in content['review_notes']] + [
        dict(source='visual', **n) for n in visual['review_notes']]
    assert (content, visual) == originals
    if category != 'confirmed':
        assert not any(i['issue_id'].startswith('EDITORIAL-') for i in report['issues'])
    for name, scopes in (('grounding', {'scientific_integrity'}),
                         ('information_narrative', {'information_depth'}),
                         ('visual', {'reading_order_quality'})):
        result = next(r for r in report['evaluations'] if r['evaluator'] == name)
        assert {n['scope'] for n in result['metadata']['review_notes']} <= scopes


@pytest.mark.parametrize('fault', ['missing_notes', 'bad_type', 'extra_status', 'unknown_module',
    'unknown_element', 'wrong_zone', 'no_scientific_basis', 'blank_observation'])
def test_notes_do_not_bypass_contract_and_reference_checks(context, fault):
    content, _ = responses(context)
    content['review_notes'] = [note()]
    n = content['review_notes'][0]
    if fault == 'missing_notes':del content['review_notes']
    elif fault == 'bad_type':n['note_type'] = 'confirmed'
    elif fault == 'extra_status':content['status'] = 'supported'
    elif fault == 'unknown_module':n['location']['section_id'] = 'invented'
    elif fault == 'unknown_element':n['location']['element_id'] = 'invented'
    elif fault == 'wrong_zone':
        modules = context.state['editorial_candidate']['modules']
        n['location'].update(section_id=modules[0]['module_id'], zone_id=modules[1]['zone_id'])
    elif fault == 'no_scientific_basis':n['original_support'] = ' '
    elif fault == 'blank_observation':n['observation'] = ' '
    with pytest.raises(Exception):
        critic._validate(content, critic.CONTENT_SCHEMA, context.state)


@pytest.mark.parametrize('stage', ['content', 'visual'])
@pytest.mark.parametrize('fault', ['timeout', 'invalid_reference', 'missing_field'])
def test_actual_request_failures_prioritize_root_cause_and_mark_dependencies_skipped(
        context, monkeypatch, stage, fault):
    import utils.langgraph_utils as language
    calls = []
    class Model:
        def __init__(self, system, config, state, name):self.state, self.name = state, name
        def reset(self):pass
        def step(self, message):
            current = 'content' if self.name == 'critic_content' else 'visual'
            calls.append(current)
            raw = (content_reply if current == 'content' else visual_reply)(
                self.state['editorial_candidate']['modules'])
            if current == stage:
                if fault == 'timeout':raise TimeoutError('OFFLINE response unavailable')
                if fault == 'invalid_reference':
                    raw['review_notes'] = [note()]
                    raw['review_notes'][0]['location']['element_id'] = 'invented'
                else:raw.pop('review_notes')
            return SimpleNamespace(content=json.dumps(raw), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    class Defect:
        name = 'geometry'
        def evaluate(self, _):
            return EvaluationResult(self.name, 'offline', True, False,
                issues=[issue('OFFLINE-COLLISION', severity='critical', scope='layout',
                    observation='Physical collision must not hide the scoring failure.', required_outcome='Reflow')])
    current = critic.make_critic(context.config)
    current.register_evaluator(Defect())
    current(context.state)
    report = context.state['critic_report']
    assert calls == (['content'] if stage == 'content' else ['content', 'visual'])
    assert report['overall_score'] is None and report['evaluation_status'] == 'failed'
    failure = report['assessment_stages'][stage]
    assert failure['status'] == 'failed'
    assert failure['error_kind'] == ('request_or_execution' if fault == 'timeout' else 'response_validation')
    assert report['rejection_summary'].startswith(stage + ' assessment failed')
    assert 'Physical collision' not in report['rejection_summary']
    assert len([i for i in report['issues'] if i['scope'] == 'critic']) == 1
    if fault == 'invalid_reference':
        assert failure['field_paths'] == [['review_notes', 0, 'location', 'element_id']]
        assert '/review_notes/0/location/element_id' in report['rejection_summary']
    elif fault == 'missing_field':
        assert failure['field_paths'] == [['review_notes']]
        assert 'review_notes' in report['rejection_summary']
    if stage == 'content':
        assert report['assessment_stages']['visual']['status'] == 'skipped'
        assert report['assessment_stages']['visual']['blocked_by'] == 'content'
        assert 'visual assessment not run' in report['rejection_summary']
        assert not report['submetric_scores']
    else:
        assert report['assessment_stages']['content']['status'] == 'complete'
        assert len(report['submetric_scores']) == 7
        assert report['factual_consistency_status'] == 'supported'


def test_unavailable_content_is_reported_without_an_invented_visual_request_failure(context, monkeypatch):
    content, _ = responses(context)
    content['assessments']['scientific_integrity'].update(
        score=None, assessment_status='unavailable', uncertainty='OFFLINE missing evidence.')
    calls = []
    def reply(state, kind, payload, schema, **kwargs):
        calls.append(kind)
        assert kind == 'editorial_content_critic'
        critic._validate(content, schema, state)
        return deepcopy(content)
    monkeypatch.setattr(critic, 'request', reply)
    critic.make_critic(context.config)(context.state)
    report = context.state['critic_report']
    assert calls == ['editorial_content_critic']
    assert report['overall_score'] is None and report['factual_consistency_status'] == 'unavailable'
    assert report['assessment_stages']['content']['status'] == 'complete'
    assert report['assessment_stages']['visual']['status'] == 'skipped'
    assert 'Required content assessment unavailable' in report['rejection_summary']
    assert not any(i['scope'] == 'critic' for i in report['issues'])
