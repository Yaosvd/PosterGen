"""The current post-render Critic: model quality judgments, measured evidence."""
from copy import deepcopy
import math
from pathlib import Path

from jsonschema import Draft202012Validator

from src.config.critic_config import validate_editorial_scoring
from src.critic.base import EvaluationResult, issue
from src.workflow.editorial_contract import paper_material, assert_editorial_ready, EditorialOutputError
from src.workflow.editorial_requests import request, obj, STRING, STRINGS
from utils.persistence import digest, file_hash, read_json

CONTENT_KEYS = ('information_layering', 'information_coverage', 'information_depth',
                'information_completeness', 'narrative_structure', 'narrative_conciseness')
VISUAL_KEYS = ('layout_structure', 'whitespace_quality', 'primary_anchor', 'compositional_balance',
               'color_palette', 'color_hierarchy', 'color_contrast', 'color_source', 'font_hierarchy',
               'font_emphasis', 'font_legibility', 'element_alignment', 'layout_robustness',
               'visual_relevance', 'reading_order_quality', 'narrative_flow')
SUBMETRIC_SOURCES = {'scientific_integrity': 'grounding',
                    **dict.fromkeys(CONTENT_KEYS, 'information_narrative'),
                    **dict.fromkeys(VISUAL_KEYS, 'visual')}
PROMPT_ROOT = Path(__file__).resolve().parents[2] / 'config' / 'prompts'
NONEMPTY = {'type': 'string', 'minLength': 1}
SCORE = {'type': ['number', 'null'], 'minimum': 0, 'maximum': 100}
EVIDENCE = obj({'module_id': STRING, 'element_id': STRING, 'measurement_id': STRING,
                'observation': NONEMPTY, 'original_support': STRING})
ASSESSMENT = obj({'score': SCORE, 'assessment_status': {'type': 'string',
    'enum': ['assessed', 'uncertain', 'unavailable']}, 'reason': NONEMPTY,
    'evidence': {'type': 'array', 'items': EVIDENCE}, 'uncertainty': STRING})
LOCATION = obj({'zone_id': STRING, 'section_id': STRING, 'element_id': STRING})
FINDING = obj({'severity': {'type': 'string', 'enum': ['critical', 'major', 'minor', 'warning']},
    'scope': NONEMPTY, 'location': LOCATION, 'observation': NONEMPTY,
    'original_support': STRING, 'required_outcome': NONEMPTY,
    'allowed_operations': STRINGS, 'forbidden_operations': STRINGS})
POSITIVES = {'type': 'array', 'items': obj({'scope': NONEMPTY, 'observation': NONEMPTY})}
DEPENDENCIES = obj({'modules': {'type': 'array', 'items': obj({
    'module_id': NONEMPTY, 'meaning': NONEMPTY, 'prerequisites': STRINGS})},
    'relations': {'type': 'array', 'items': obj({'prerequisite_module_id': NONEMPTY,
        'dependent_module_id': NONEMPTY, 'explanation': NONEMPTY})}, 'reason': NONEMPTY})
TRANSITION = obj({'from_module_id': NONEMPTY, 'to_module_id': NONEMPTY, 'observation': NONEMPTY})
READING_REVIEW = obj({'entry_module_ids': STRINGS,
    'likely_paths': {'type': 'array', 'items': STRINGS},
    'ambiguous_transitions': {'type': 'array', 'items': TRANSITION},
    'dependency_conflicts': {'type': 'array', 'items': TRANSITION}, 'reason': NONEMPTY})
CONTENT_SCHEMA = obj({'status': {'type': 'string',
    'enum': ['supported', 'issues', 'uncertain', 'unavailable']},
    'assessments': obj({k: ASSESSMENT for k in ('scientific_integrity', *CONTENT_KEYS)}),
    'content_dependencies': DEPENDENCIES, 'issues': {'type': 'array', 'items': FINDING},
    'positive_patterns': POSITIVES, 'reason': NONEMPTY})
VISUAL_SCHEMA = obj({'assessments': obj({k: ASSESSMENT for k in VISUAL_KEYS}),
    'reading_review': READING_REVIEW, 'issues': {'type': 'array', 'items': FINDING},
    'positive_patterns': POSITIVES, 'reason': NONEMPTY})


def editorial_critic_config(config):
    config = deepcopy(config)
    policy = config['editorial_scoring']
    validate_editorial_scoring(policy, config['dimensions'])
    leaves = {k for d in policy['dimensions'].values() for k in d['submetrics']}
    if leaves != set(SUBMETRIC_SOURCES):
        raise ValueError('Current Critic requires exactly its 23 model submetrics')
    config.update(schema_version=policy['schema_version'], rubric_version=policy['rubric_version'],
                  critic_system_version=policy['critic_system_version'], scoring_method=policy['method'])
    config['submetric_sources'] = deepcopy(SUBMETRIC_SOURCES)
    for name, settings in policy['dimensions'].items():
        config['dimensions'][name]['weight'] = settings['weight']
    for name in set(SUBMETRIC_SOURCES.values()):
        if not config['evaluators'][name].get('enabled', True):
            raise ValueError('All model Critic sources are required')
    return config


def _render_diagnostics(state):
    """Send final measurements, leaving search history in the saved diagnostics."""
    diagnostics = deepcopy({k: state.get(k) for k in
                            ('editorial_fit', 'layout_preflight_report', 'render_fit_report')})
    if isinstance(diagnostics['editorial_fit'], dict):
        diagnostics['editorial_fit'].pop('geometry_trials', None)
    return diagnostics


def _paper_evidence(state):
    """Reference an identical advisory copy without changing either source text."""
    paper = paper_material(state, original=True)
    if 'proofread_text' in paper and paper['proofread_text'] == paper['original_text']:
        del paper['proofread_text']
        paper['proofread_text_ref'] = 'original_text'
    return paper


def visible_text(state):
    from src.layout.editorial import presentation_lines
    return {'paper_metadata': state['narrative_content'].get('meta', {}), 'modules': [
        {'module_id': s['section_id'], 'title': s['section_title'], 'body_lines': presentation_lines(s)}
        for s in state['optimized_story_board']['spatial_content_plan']['sections']]}


def measurement_evidence(state):
    return {'measurements': deepcopy(state.get('critic_measurement_evidence') or {}),
            'authored_elements': deepcopy(state.get('styled_layout') or state.get('design_layout') or []),
            'color_scheme': deepcopy(state.get('color_scheme') or {}),
            'color_provenance': deepcopy(state.get('color_provenance') or {})}


class MeasurementEvaluator:
    """Collect measurement findings and record explicitly unavailable instruments."""
    def __init__(self, evaluator):
        self.evaluator = evaluator
        self.name = evaluator.name

    def evaluate(self, context):
        try:
            verdict = self.evaluator.evaluate(context)
            evidence = {'status': 'measured', 'metadata': deepcopy(verdict.metadata),
                        'findings': [{k: deepcopy(row[k]) for k in
                            ('issue_id', 'location', 'observation', 'evidence') if k in row}
                            for row in verdict.issues]}
        except Exception as exc:
            evidence = {'status': 'unavailable', 'reason': type(exc).__name__ + ': ' + str(exc)}
            verdict = EvaluationResult(self.name, 'measurement_v1',
                context.config['evaluators'][self.name].get('hard_gate', False), False,
                issues=[issue('MEASUREMENT-' + self.name.upper() + '-UNAVAILABLE',
                    severity='warning', scope='measurement', observation=evidence['reason'],
                    required_outcome='Record unavailable measurement; do not invent a measurement')])
        context.state.setdefault('critic_measurement_evidence', {})[self.name] = evidence
        verdict.metadata = {'measurement': evidence}
        return verdict


def _identifiers(state):
    modules = {m['module_id'] for m in state['editorial_candidate']['modules']}
    zones = {z['zone_id'] for z in state['layout_spec'].get('zones', [])}
    elements = {e['id'] for e in (state.get('styled_layout') or state.get('design_layout') or []) if e.get('id')}
    measurements = set(state.get('critic_measurement_evidence') or {}) | {
        'editorial_fit', 'layout_preflight_report', 'render_fit_report'}
    return modules, zones, elements, measurements


def _validate(raw, schema, state):
    Draft202012Validator(schema).validate(raw)
    modules, zones, elements, measurements = _identifiers(state)

    def reference(value, allowed):
        if value and value not in allowed:
            raise EditorialOutputError('Critic finding references an unknown identifier: ' + value)

    for metric in raw['assessments'].values():
        score = metric['score']
        unavailable = metric['assessment_status'] == 'unavailable'
        if unavailable != (score is None):
            raise EditorialOutputError('Unavailable assessment must have a null score, and only it may be null')
        if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100):
            raise EditorialOutputError('Critic score must be finite and within 0..100')
        if not metric['reason'].strip() or (not unavailable and not metric['evidence']):
            raise EditorialOutputError('Every assessed score needs a reason and evidence')
        if metric['assessment_status'] != 'assessed' and not metric['uncertainty'].strip():
            raise EditorialOutputError('Uncertain/unavailable assessments must explain their limits')
        for evidence in metric['evidence']:
            reference(evidence['module_id'], modules)
            reference(evidence['element_id'], elements)
            reference(evidence['measurement_id'], measurements)
    for finding in raw['issues']:
        location = finding['location']
        reference(location['section_id'], modules)
        reference(location['zone_id'], zones)
        reference(location['element_id'], elements)
        if location['section_id'] and location['zone_id']:
            expected = next(m['zone_id'] for m in state['editorial_candidate']['modules']
                            if m['module_id'] == location['section_id'])
            if expected != location['zone_id']:
                raise EditorialOutputError('Critic module and zone location contradict each other')
        if finding['scope'] == 'scientific_integrity' and not finding['original_support'].strip():
            raise EditorialOutputError('Scientific findings must state original support or conflict')
    if 'content_dependencies' in raw:
        deps = raw['content_dependencies']
        ids = [m['module_id'] for m in deps['modules']]
        if len(ids) != len(set(ids)) or set(ids) != modules:
            raise EditorialOutputError('Content dependencies must describe every real module exactly once')
        for relation in deps['relations']:
            reference(relation['prerequisite_module_id'], modules)
            reference(relation['dependent_module_id'], modules)
        scientific_findings = [f for f in raw['issues'] if f['scope'] == 'scientific_integrity']
        if raw['status'] == 'supported' and scientific_findings:
            raise EditorialOutputError('Critic scientific support contradicts scientific findings')
        scientific = raw['assessments']['scientific_integrity']
        if (raw['status'] == 'unavailable') != (scientific['assessment_status'] == 'unavailable'):
            raise EditorialOutputError('Scientific availability status contradicts its assessment')
    if 'reading_review' in raw:
        reading = raw['reading_review']
        for module in reading['entry_module_ids']:
            reference(module, modules)
            if not module:
                raise EditorialOutputError('Reading paths must reference real modules')
        for path in reading['likely_paths']:
            for module in path:
                reference(module, modules)
                if not module:
                    raise EditorialOutputError('Reading paths must reference real modules')
        for transition in reading['ambiguous_transitions'] + reading['dependency_conflicts']:
            reference(transition['from_module_id'], modules)
            reference(transition['to_module_id'], modules)


def _request_identity(state, directory, binding, model_key, prompt):
    root = Path(state.get('sample_preparation_dir') or state['output_dir']) / directory
    path = root / 'identity.json'
    # Actual requests always have a durable identity; offline test injections may not.
    identity = read_json(path)['payload']['input_digest'] if path.exists() else None
    return {'input_digest': binding, 'journal_identity': identity,
            'model_config_digest': digest(state[model_key]), 'prompt_digest': file_hash(prompt)}


def content_evaluation(context):
    state = context.state
    assert_editorial_ready(state, compiled=True)
    payload = {'paper': _paper_evidence(state), 'final_poster': state['editorial_candidate'],
        'renderer_visible_text': visible_text(state), 'actual_geometry': state['layout_spec'],
        'content_status': 'not_preverified', 'measurement_evidence': measurement_evidence(state),
        'render_diagnostics': _render_diagnostics(state)}
    prompt = PROMPT_ROOT / 'editorial_content_critic.txt'
    binding = digest({'payload': payload, 'schema': CONTENT_SCHEMA, 'model': state['text_model'],
                      'prompt': file_hash(prompt)})
    if state.get('_editorial_content_input_digest') == binding:
        if state.get('_editorial_content_error'):
            raise EditorialOutputError(state['_editorial_content_error'])
        raw = state['_editorial_content_evaluation']
        _validate(raw, CONTENT_SCHEMA, state)
        return raw
    state['_editorial_content_input_digest'] = binding
    state.pop('_editorial_content_evaluation', None)
    state.pop('_editorial_content_error', None)
    try:
        raw = request(state, 'editorial_content_critic', payload, CONTENT_SCHEMA,
            directory='editorial/final_content', correction=False,
            validator=lambda value: _validate(value, CONTENT_SCHEMA, state))
        _validate(raw, CONTENT_SCHEMA, state)
        state['_editorial_content_evaluation'] = raw
        state['editorial_factual_status'] = raw['status']
        state['critic_request_identities'] = {'content': _request_identity(
            state, 'editorial/final_content', binding, 'text_model', prompt)}
        return raw
    except Exception as exc:
        state['editorial_factual_status'] = 'unavailable'
        state['_editorial_content_error'] = type(exc).__name__ + ': ' + str(exc)
        raise


def _model_result(context, name, raw, keys, *, passed=True):
    problems = [issue('EDITORIAL-' + name.upper() + '-' + str(i), severity=f['severity'],
        scope=f['scope'], observation=f['observation'], location={k: v for k, v in f['location'].items() if v},
        evidence={'source': 'model', 'original_support': f['original_support']},
        required_outcome=f['required_outcome'], allowed_operations=f['allowed_operations'],
        forbidden_operations=f['forbidden_operations']) for i, f in enumerate(raw['issues'])
        if name != 'grounding' or f['scope'] == 'scientific_integrity']
    if name == 'information_narrative':
        problems = [p for p in problems if p['scope'] != 'scientific_integrity']
    assessments = {k: deepcopy(raw['assessments'][k]) for k in keys}
    verdict = EvaluationResult(name, 'model_submetrics_v1',
        context.config['evaluators'][name].get('hard_gate', False), passed, issues=problems,
        metadata={'submetric_assessments': assessments, 'reason': raw['reason']})
    if name != 'grounding':
        verdict.positive_patterns = deepcopy(raw['positive_patterns'])
    return verdict


class EditorialEvaluator:
    def __init__(self, name):
        self.name = name

    def evaluate(self, context):
        if self.name not in {'grounding', 'information_narrative'}:
            raise ValueError('Current Critic has no rule-based content quality evaluator')
        raw = content_evaluation(context)
        keys = ('scientific_integrity',) if self.name == 'grounding' else CONTENT_KEYS
        return _model_result(context, self.name, raw, keys,
                             passed=raw['status'] == 'supported' if self.name == 'grounding' else True)


class EditorialVisualEvaluator:
    name = 'visual'

    def evaluate(self, context):
        state = context.state
        raw_content = content_evaluation(context)
        if any(a['score'] is None for a in raw_content['assessments'].values()):
            raise EditorialOutputError('Visual evaluation not run: required content assessment unavailable')
        # Do not send content scores, scientific verdicts, or an asserted route as approval.
        payload = {'final_poster': state['editorial_candidate'], 'renderer_visible_text': visible_text(state),
            'actual_geometry': state['layout_spec'], 'poster_inches': [state['poster_width'], state['poster_height']],
            'content_dependencies': raw_content['content_dependencies'],
            'measurement_evidence': measurement_evidence(state), 'render_diagnostics': _render_diagnostics(state)}
        raw = request(state, 'editorial_visual_critic', payload, VISUAL_SCHEMA,
            directory='editorial/final_visual', images=[state['current_candidate']['png_path']], correction=False,
            validator=lambda value: _validate(value, VISUAL_SCHEMA, state))
        _validate(raw, VISUAL_SCHEMA, state)
        state['_editorial_visual_evaluation'] = raw
        prompt = PROMPT_ROOT / 'editorial_visual_critic.txt'
        binding = digest({'payload': payload, 'schema': VISUAL_SCHEMA, 'model': state['vision_model'],
            'prompt': file_hash(prompt), 'image': file_hash(state['current_candidate']['png_path'])})
        state.setdefault('critic_request_identities', {})['visual'] = _request_identity(
            state, 'editorial/final_visual', binding, 'vision_model', prompt)
        return _model_result(context, 'visual', raw, VISUAL_KEYS,
                             passed=not any(f['severity'] == 'critical' for f in raw['issues']))


def current_evaluators():
    """The single supported Critic registry: instruments, then model judgments."""
    from src.critic.evaluators import RenderArtifactEvaluator, GeometryEvaluator, TypographyEvaluator, ColumnBalanceEvaluator
    from src.critic.section_fit import SectionFitEvaluator
    from src.critic.layout_family import LayoutFamilyCriticEvaluator
    from src.critic.quality import ColorQualityEvaluator, VisualAssetEvaluator
    measurements = [RenderArtifactEvaluator(), GeometryEvaluator(), TypographyEvaluator(), ColorQualityEvaluator(),
                    VisualAssetEvaluator(), ColumnBalanceEvaluator(), SectionFitEvaluator(), LayoutFamilyCriticEvaluator()]
    evaluators = [MeasurementEvaluator(e) for e in measurements]
    evaluators += [EditorialEvaluator('grounding'), EditorialEvaluator('information_narrative'), EditorialVisualEvaluator()]
    return evaluators


def make_critic(config):
    from src.critic.engine import PosterCritic
    return PosterCritic(config)
