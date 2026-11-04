"""Regression contracts for the in-place model-scored final Critic."""
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from critic_fixtures import assessment, content_reply, visual_reply, finding
from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext, EvaluationResult
from src.critic.engine import PosterCritic
from src.workflow import editorial_critic as critic
from src.workflow.editorial_critic import (editorial_critic_config, make_critic, MeasurementEvaluator,
    EditorialEvaluator, CONTENT_KEYS, VISUAL_KEYS, CONTENT_SCHEMA, VISUAL_SCHEMA, _validate)
from test_editorial_generation import state_for, install


@pytest.fixture
def context(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected live model'))
    state = install(state_for(tmp_path))
    from src.layout.editorial_layout import measure
    physical = measure(state, state['editorial_candidate'], state['editorial_zones'])
    png = tmp_path / 'poster.png'
    Image.new('RGB', (80, 40), 'white').save(png)
    state.update(design_layout=physical['layout'], layout_spec=physical['spec'],
                 current_candidate={'candidate_id': 'offline', 'png_path': str(png)})
    state['critic_config'] = editorial_critic_config(load_critic_config())
    monkeypatch.setattr(critic, 'assert_editorial_ready', lambda *a, **k: None)
    return CriticContext(state, state['critic_config'])


def responses(context, *, score=80, science=100):
    modules = context.state['editorial_candidate']['modules']
    return content_reply(modules, score=score, science=science), visual_reply(modules, score=score)


def aggregate(context, content, visual, extras=()):
    # Every leaf is read from its declared model source.
    results = [EvaluationResult(name, 'offline', False, True,
        metadata={'submetric_assessments': {
            k: deepcopy(raw['assessments'][k]) for k in keys}})
        for name, raw, keys in [('grounding', content, ['scientific_integrity']),
                                ('information_narrative', content, CONTENT_KEYS),
                                ('visual', visual, VISUAL_KEYS)]]
    context.state['_editorial_content_evaluation'] = content
    context.state['_editorial_visual_evaluation'] = visual
    return make_critic(context.config)._build_report(context.state, [*results, *extras])


def test_exact_user_weights_and_cross_request_content_aggregation(context):
    content, visual = responses(context, score=80, science=90)
    for key, score in {'information_coverage': 60, 'information_completeness': 70,
                       'information_depth': 90, 'narrative_structure': 50,
                       'information_layering': 100, 'narrative_conciseness': 40}.items():
        content['assessments'][key]['score'] = score
    for key, score in {'narrative_flow': 30, 'reading_order_quality': 20,
                       'layout_robustness': 10, 'layout_structure': 30, 'element_alignment': 90,
                       'primary_anchor': 60, 'font_hierarchy': 100, 'font_emphasis': 40}.items():
        visual['assessments'][key]['score'] = score
    report = aggregate(context, content, visual)
    assert report['dimension_scores'] == {'scientific_integrity': 90, 'content_quality': 62.5,
        'layout_integrity': 27, 'readability': 80, 'visual_hierarchy': 41,
        'visual_balance': 80, 'aesthetics': 80}
    assert report['overall_score'] == 62.55
    assert report['presentation_quality_score'] == 53.4
    assert report['schema_version'] == 7 and report['critic_system_version'] == '7.2.0'
    assert report['evaluation_status'] == 'complete'
    assert report['dimension_scores'] == report['poster_evaluation']['dimension_scores']
    assert len(report['submetric_assessments']) == len(report['submetric_scores']) == 23
    assert report['aggregation_policy']['dimensions']['content_quality']['submetrics']['narrative_flow'] == .15
    assert report['aggregation_policy']['submetric_sources']['narrative_flow'] == 'visual'


@pytest.mark.parametrize('leaf,dimension,expected_loss',[
    ('reading_order_quality', 'visual_hierarchy', 9),
    ('narrative_flow', 'content_quality', 3),
    ('layout_robustness', 'layout_integrity', 9),
    ('layout_structure', 'layout_integrity', 9),
    ('element_alignment', 'layout_integrity', 2)])
def test_individual_leaf_effect_matches_user_weight(context, leaf, dimension, expected_loss):
    content, visual = responses(context, score=100)
    visual['assessments'][leaf]['score'] = 0
    report = aggregate(context, content, visual)
    assert report['overall_score'] == 100 - expected_loss
    assert report['dimension_scores'][dimension] < 100
    assert len([c for cs in report['poster_evaluation']['dimension_source_contributions'].values()
                for c in cs if c['submetric'] == leaf]) == 1


def test_measurement_diagnostics_and_undeclared_assessments_cannot_cap_model_score(context):
    content, visual = responses(context, score=100, science=60)
    baseline = aggregate(context, content, visual)
    extra = EvaluationResult('geometry', 'offline', True, False,
        metadata={'overlap_area': 2,
                  'submetric_assessments': {'reading_order_quality': assessment(0)}})
    report = aggregate(context, content, visual, [extra])
    assert report['overall_score'] == baseline['overall_score'] == 90
    assert report['submetric_scores']['layout_structure'] == 100
    assert report['submetric_scores']['reading_order_quality'] == 100
    assert report['hard_gate_passed'] is False and report['reference_passed'] is False
    assert report['evaluation_status'] == 'complete'
    assert 'raw_overall_score' not in report  # No forced low-score/cap mechanism.


@pytest.mark.parametrize('leaf', ['reading_order_quality', 'narrative_flow', 'scientific_integrity'])
def test_missing_leaf_never_imputes_or_renormalizes(context, leaf):
    content, visual = responses(context)
    raw = content if leaf == 'scientific_integrity' else visual
    raw['assessments'].pop(leaf)
    # Direct aggregation must fail closed even when a caller bypasses request validation.
    results = []
    for name, raw, keys in [('grounding', content, ['scientific_integrity']),
                            ('information_narrative', content, CONTENT_KEYS), ('visual', visual, VISUAL_KEYS)]:
        results.append(EvaluationResult(name, 'offline', False, True, metadata={
            'submetric_assessments': {k: v for k, v in raw['assessments'].items() if k in keys}}))
    report = make_critic(context.config)._build_report(context.state, results)
    assert report['overall_score'] is None and report['presentation_quality_score'] is None
    assert report['evaluation_status'] == 'failed' and not report['reference_passed']
    assert leaf not in report['submetric_scores']
    assert any(leaf in missing for missing in report['poster_evaluation']['missing_score_sources'].values())


@pytest.mark.parametrize('score', [-1, 101, math.nan, math.inf, True, '80', None])
def test_invalid_required_score_rejected_without_clamping(context, score):
    _, visual = responses(context)
    visual['assessments']['reading_order_quality']['score'] = score
    with pytest.raises(Exception):
        _validate(visual, VISUAL_SCHEMA, context.state)


@pytest.mark.parametrize('fault', ['missing_reading', 'missing_flow', 'unknown_module', 'wrong_zone',
    'unknown_element', 'unknown_measurement', 'no_evidence', 'blank_reason', 'unknown_path',
    'unknown_dependency', 'duplicate_module', 'missing_module', 'obsolete_top_status'])
def test_required_contract_and_evidence_references(context, fault):
    content, visual = responses(context)
    raw, schema = visual, VISUAL_SCHEMA
    metric = visual['assessments']['reading_order_quality']
    if fault == 'missing_reading':visual['assessments'].pop('reading_order_quality')
    elif fault == 'missing_flow':visual['assessments'].pop('narrative_flow')
    elif fault == 'unknown_module':metric['evidence'][0]['module_id'] = 'invented'
    elif fault == 'unknown_element':metric['evidence'][0]['element_id'] = 'invented'
    elif fault == 'unknown_measurement':metric['evidence'][0]['measurement_id'] = 'invented'
    elif fault == 'no_evidence':metric['evidence'] = []
    elif fault == 'blank_reason':metric['reason'] = ' '
    elif fault == 'unknown_path':visual['reading_review']['likely_paths'] = [['invented']]
    elif fault == 'wrong_zone':
        modules = context.state['editorial_candidate']['modules']
        visual['issues'] = [finding(modules[0]['module_id'], scope='layout')]
        visual['issues'][0]['location']['zone_id'] = modules[1]['zone_id']
    else:
        raw, schema = content, CONTENT_SCHEMA
        if fault == 'unknown_dependency':
            content['content_dependencies']['relations'] = [{'prerequisite_module_id': 'invented',
                'dependent_module_id': context.state['editorial_candidate']['modules'][0]['module_id'],
                'explanation': 'Dependency explanation.'}]
        elif fault == 'duplicate_module':content['content_dependencies']['modules'].append(
            deepcopy(content['content_dependencies']['modules'][0]))
        elif fault == 'missing_module':content['content_dependencies']['modules'].pop()
        elif fault == 'obsolete_top_status':content['status'] = 'supported'
    with pytest.raises(Exception):
        _validate(raw, schema, context.state)


def test_scientifically_supported_can_still_have_content_improvements(context):
    content, _ = responses(context)
    content['issues'] = [finding(scope='narrative_structure', severity='minor')]
    _validate(content, CONTENT_SCHEMA, context.state)
    assert critic.scientific_status(content) == 'supported'


@pytest.mark.parametrize('kind', ['uncertain', 'unavailable'])
def test_uncertainty_is_distinct_from_an_unavailable_required_leaf(context, kind):
    content, visual = responses(context)
    metric = visual['assessments']['narrative_flow']
    metric.update(assessment_status=kind, uncertainty='The figure text is difficult to decipher.')
    if kind == 'unavailable':metric['score'] = None
    _validate(visual, VISUAL_SCHEMA, context.state)
    report = aggregate(context, content, visual)
    assert (report['overall_score'] is None) == (kind == 'unavailable')
    assert report['submetric_assessments']['narrative_flow']['assessment_status'] == kind


def test_parallel_reverse_and_ambiguous_paths_are_not_forced_to_a_template(context):
    _, visual = responses(context)
    ids = [m['module_id'] for m in context.state['editorial_candidate']['modules']]
    review = visual['reading_review']
    review.update(entry_module_ids=ids[:2], likely_paths=[ids[::-1], ids[:2]])
    _validate(visual, VISUAL_SCHEMA, context.state)
    review.update(entry_module_ids=[], likely_paths=[], reason='No clear reading entrance.')
    visual['assessments']['reading_order_quality']['score'] = 10
    _validate(visual, VISUAL_SCHEMA, context.state)


def test_measurement_collector_records_raw_evidence_and_unavailability(context):
    class Measurement:
        name = 'geometry'
        def evaluate(self, ctx):
            return EvaluationResult('geometry', 'offline', True, False,
                metadata={'overlap_area': 2})
    result = MeasurementEvaluator(Measurement()).evaluate(context)
    assert "scores" not in result.to_dict() and result.positive_patterns == []
    assert result.metadata['measurement']['metadata'] == {'overlap_area': 2}
    assert 'scores' not in json.dumps(critic.measurement_evidence(context.state))
    class Unavailable:
        name = 'geometry'
        def evaluate(self, ctx):raise RuntimeError('No measurement available')
    result = MeasurementEvaluator(Unavailable()).evaluate(context)
    assert "scores" not in result.to_dict() and not result.passed
    assert context.state['critic_measurement_evidence']['geometry']['status'] == 'unavailable'
    assert not result.issues[0]['issue_id'].startswith('EVALUATOR-')


def test_content_then_visual_input_binds_text_dependencies_without_previous_scores(context, monkeypatch):
    content, visual = responses(context)
    context.state['marker_raw_text'] = context.state['raw_text']
    context.state['editorial_fit'] = {'passed': False, 'geometry_trials': [{'search_only': True}],
                                      'modules': [{'module_id': 'module_0', 'overage_inches': 4.38}]}
    context.state['render_fit_report'] = {'status': 'partial', 'conclusive': False,
                                         'unmatched_text_ids': ['m6_text'], 'issues': []}
    ids = [m['module_id'] for m in context.state['editorial_candidate']['modules']]
    content['content_dependencies']['relations'] = [{'prerequisite_module_id': ids[-1],
        'dependent_module_id': ids[0], 'explanation': 'A necessary definition precedes use.'}]
    calls = []
    def reply(st, kind, payload, schema, **kwargs):
        calls.append(kind)
        assert kwargs['correction'] is False
        assert payload['renderer_visible_text']['modules']
        assert 'render_diagnostics' not in payload['measurement_evidence']
        assert payload['render_diagnostics']['editorial_fit'] == {
            'passed': False, 'modules': [{'module_id': 'module_0', 'overage_inches': 4.38}]}
        assert payload['render_diagnostics']['render_fit_report'] == context.state['render_fit_report']
        if kind == 'editorial_content_critic':
            assert payload['paper']['original_text'] == context.state['raw_text']
            assert payload['paper']['proofread_text_ref'] == 'original_text'
            assert 'proofread_text' not in payload['paper']
            return deepcopy(content)
        assert calls == ['editorial_content_critic', 'editorial_visual_critic']
        assert payload['content_dependencies'] == content['content_dependencies']
        assert not {'assessments', 'status', 'scientific_integrity', 'scores'} & payload.keys()
        assert kwargs['images'] == [st['current_candidate']['png_path']]
        return deepcopy(visual)
    monkeypatch.setattr(critic, 'request', reply)
    current = make_critic(context.config)
    assert type(current) is PosterCritic
    current(context.state)
    report = context.state['critic_report']
    assert report['evaluation_status'] == 'complete' and len(report['submetric_scores']) == 23
    assert report['content_dependencies'] == content['content_dependencies']
    assert report['reading_review'] == visual['reading_review']
    assert context.state['editorial_factual_status'] == 'supported'
    assert context.state['editorial_fit']['geometry_trials'] == [{'search_only': True}]
    for evaluation in report['evaluations']:
        if evaluation['evaluator'] not in {'grounding', 'information_narrative', 'visual'}:
            assert 'scores' not in evaluation and 'submetrics' not in evaluation['metadata']


def test_content_failure_does_not_buy_a_visual_call_or_reuse_stale_results(context, monkeypatch):
    calls = []
    def fail(st, kind, *a, **kw):
        calls.append(kind)
        raise TimeoutError('OFFLINE request returned no response')
    monkeypatch.setattr(critic, 'request', fail)
    context.state['_editorial_visual_evaluation'] = {'reading_review': {'reason': 'STALE'}}
    make_critic(context.config)(context.state)
    assert calls == ['editorial_content_critic']
    report = context.state['critic_report']
    assert report['overall_score'] is None and report['reading_review'] is None
    assert report['evaluation_status'] == 'failed'
    assert report['factual_consistency_status'] == 'unavailable'


def test_durable_model_replay_uses_zero_new_requests_and_rejects_changed_image(context, monkeypatch):
    import base64
    import utils.langgraph_utils as language
    context.state['marker_raw_text'] = context.state['raw_text']
    context.state['editorial_fit'] = {'passed': False, 'geometry_trials': [{'search_only': True}]}
    calls = []
    class Model:
        def __init__(self, system, config, state, name):self.state, self.name = state, name
        def reset(self):pass
        def step(self, message):
            calls.append(self.name)
            if self.name == 'critic_visual':
                parts = json.loads(message)
                assert parts[1]['image_url']['url'] == 'data:image/png;base64,' + base64.b64encode(
                    Path(self.state['current_candidate']['png_path']).read_bytes()).decode('ascii')
                text = parts[0]['text']
                value = visual_reply(self.state['editorial_candidate']['modules'])
            else:
                text = message
                value = content_reply(self.state['editorial_candidate']['modules'])
            value['review_notes'] = [{'note_type': 'advisory',
                'scope': 'scientific_integrity' if self.name == 'critic_content' else 'reading_order_quality',
                'location': {'section_id': '', 'zone_id': '', 'element_id': ''},
                'observation': 'OFFLINE optional emphasis; no confirmed defect.',
                'original_support': 'OFFLINE verified source.' if self.name == 'critic_content' else '',
                'recommendation': 'Keep the verified observation available.'}]
            payload = json.loads(text.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:\n', 1)[0])
            assert 'render_diagnostics' not in payload['measurement_evidence']
            assert payload['render_diagnostics']['editorial_fit'] == {'passed': False}
            if self.name == 'critic_content':
                assert payload['paper']['original_text'] == self.state['raw_text']
                assert payload['paper']['proofread_text_ref'] == 'original_text'
                assert 'proofread_text' not in payload['paper']
            return SimpleNamespace(content=json.dumps(value), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    current = make_critic(context.config)
    current(context.state)
    first = deepcopy(context.state['critic_report'])
    assert first['evaluation_status'] == 'complete'
    assert len(first['review_notes']) == 2
    context.state['editorial_fit']['geometry_trials'].append({'search_only': 'Additional local history'})
    current(context.state)
    assert calls == ['critic_content', 'critic_visual']
    assert context.state['critic_report']['overall_score'] == first['overall_score']
    assert context.state['critic_report']['review_notes'] == first['review_notes']
    Image.new('RGB', (80, 40), 'black').save(context.state['current_candidate']['png_path'])
    current(context.state)
    assert calls == ['critic_content', 'critic_visual']
    assert context.state['critic_report']['overall_score'] is None


@pytest.mark.parametrize('fault', ['dimension_sum', 'leaf_sum', 'duplicate', 'nonfinite', 'boolean', 'missing_leaf'])
def test_invalid_weight_contract_is_rejected(fault):
    config = load_critic_config()
    dims = config['editorial_scoring']['dimensions']
    if fault == 'dimension_sum':dims['aesthetics']['weight'] = .9
    elif fault == 'leaf_sum':dims['content_quality']['submetrics']['narrative_flow'] = .9
    elif fault == 'duplicate':dims['aesthetics']['submetrics'] = {'reading_order_quality': 1}
    elif fault == 'nonfinite':dims['aesthetics']['weight'] = math.nan
    elif fault == 'boolean':dims['scientific_integrity']['submetrics']['scientific_integrity'] = True
    else:dims['aesthetics']['submetrics'] = {'invented': 1}
    with pytest.raises(ValueError):editorial_critic_config(config)


def test_explicit_paper_cache_survives_scoring_change_without_importing_evaluation(tmp_path):
    from src.workflow.exploration_store import ExplorationStore
    from src.workflow.paper_cache import copy_paper_cache, extraction_identity
    from utils.persistence import file_hash
    store = ExplorationStore(tmp_path / 'cache-store')
    baseline = load_critic_config()
    old = {'project_identity': 'rubrics_poster_v1', 'preparation_policy_version': 'sample_editorial_v1',
        'agent_policy_hash': file_hash('config/agent_policy.yaml'), 'poster': {},
        'critic': {**baseline, 'rubric_version': 'academic_poster_editorial_v3'},
        'code_identity': {'src/workflow/editorial_requests.py': file_hash('src/workflow/editorial_requests.py'),
                          'src/workflow/editorial_critic.py': 'old-critic',
                          'src/critic/engine.py': 'old-engine',
                          'config/prompts/editorial_content_critic.txt': 'old-content-prompt'}}
    new = deepcopy(old)
    new['critic'] = editorial_critic_config(baseline)
    for name in ('src/workflow/editorial_critic.py', 'src/critic/engine.py',
                 'config/prompts/editorial_content_critic.txt'):
        new['code_identity'][name] = file_hash(name)
    assert extraction_identity(old) == extraction_identity(new)
    identity = {'paper': 'same-paper-and-models'}
    donor, _ = store.open_run(identity, old, seed=1, samples=1)
    target, _ = store.open_run(identity, new, seed=2, samples=1)
    state = state_for(tmp_path / 'paper-input')
    image = store.paper_path(donor) / 'assets' / 'figure.png'
    image.parent.mkdir(parents=True)
    Image.new('RGB', (20, 20), 'blue').save(image)
    state['images'] = {'1': {'path': str(image), 'aspect': 1}}
    state['_editorial_content_evaluation'] = {'private': 'old evaluation'}
    state['critic_report'] = {'overall_score': 99}
    store.save_paper_foundation(donor, state)
    copied = copy_paper_cache(store, donor, target, identity, new)
    assert not {'critic_report', '_editorial_content_evaluation', 'critic_measurement_evidence'} & copied.keys()
    assert file_hash(copied['images']['1']['path']) == file_hash(image)
    changed = deepcopy(new)
    changed['code_identity']['src/workflow/editorial_requests.py'] = 'changed extraction request implementation'
    with pytest.raises(ValueError, match='identity changed'):
        copy_paper_cache(store, donor, target, identity, changed)
    with pytest.raises(ValueError, match='policy changed'):
        store.open_run(identity, new, run_id=donor, samples=1, seed=1)


def test_visual_failure_keeps_valid_content_assessments(context, monkeypatch):
    content, _ = responses(context)
    calls = []
    def reply(st, kind, *a, **kw):
        calls.append(kind)
        if kind == 'editorial_content_critic':return deepcopy(content)
        raise TimeoutError('OFFLINE visual request unavailable')
    monkeypatch.setattr(critic, 'request', reply)
    make_critic(context.config)(context.state)
    report = context.state['critic_report']
    assert calls == ['editorial_content_critic', 'editorial_visual_critic']
    assert report['overall_score'] is None and report['evaluation_status'] == 'failed'
    assert len(report['submetric_assessments']) == 7 and len(report['submetric_scores']) == 7
    assert report['factual_consistency_status'] == 'supported'
    assert report['content_dependencies'] == content['content_dependencies']
    assert report['reading_review'] is None
