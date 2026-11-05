"""The current post-render Critic: model quality judgments, measured evidence."""
from copy import deepcopy
import math
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from src.config.critic_config import validate_editorial_scoring
from src.critic.base import EvaluationResult, issue
from src.layout.element_identity import VERSION as ELEMENT_IDENTITY_VERSION, identified_layout
from src.workflow.editorial_contract import (paper_material, assert_editorial_ready,
    EditorialOutputError, EditorialStructureError)
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
EVIDENCE = obj({'module_id': STRING, 'element_id': STRING, 'measurement_id': STRING, 'finding_id': STRING,
                'observation': NONEMPTY, 'original_support': STRING})
ASSESSMENT = obj({'score': SCORE, 'assessment_status': {'type': 'string',
    'enum': ['assessed', 'uncertain', 'unavailable']}, 'reason': NONEMPTY,
    'evidence': {'type': 'array', 'items': EVIDENCE}, 'uncertainty': STRING})
LOCATION = obj({'zone_id': STRING, 'section_id': STRING, 'element_id': STRING})
FINDING = obj({'severity': {'type': 'string', 'enum': ['critical', 'major', 'minor', 'warning']},
    'scope': NONEMPTY, 'location': LOCATION, 'observation': NONEMPTY,
    'original_support': STRING, 'required_outcome': NONEMPTY,
    'allowed_operations': STRINGS, 'forbidden_operations': STRINGS})
REVIEW_NOTE = obj({'note_type': {'type': 'string', 'enum': ['uncertainty', 'advisory']},
    'scope': NONEMPTY, 'location': LOCATION, 'observation': NONEMPTY,
    'original_support': STRING, 'recommendation': STRING})
REVIEW_NOTES = {'type': 'array', 'items': REVIEW_NOTE}
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
CONTENT_SCHEMA = obj({'assessments': obj({k: ASSESSMENT for k in ('scientific_integrity', *CONTENT_KEYS)}),
    'content_dependencies': DEPENDENCIES, 'issues': {'type': 'array', 'items': FINDING},
    'review_notes': REVIEW_NOTES, 'positive_patterns': POSITIVES, 'reason': NONEMPTY})
VISUAL_SCHEMA = obj({'assessments': obj({k: ASSESSMENT for k in VISUAL_KEYS}),
    'reading_review': READING_REVIEW, 'issues': {'type': 'array', 'items': FINDING},
    'review_notes': REVIEW_NOTES, 'positive_patterns': POSITIVES, 'reason': NONEMPTY})


class CriticResponseError(EditorialOutputError):
    """A response-contract error with a machine-readable field location."""
    def __init__(self, message, path):
        self.paths = [tuple(path)]
        super().__init__('/' + '/'.join(map(str, path)) + ': ' + message)


def scientific_status(raw):
    """Summarize explicit model classifications, never scores or natural language."""
    status = raw['assessments']['scientific_integrity']['assessment_status']
    if status == 'unavailable':
        return 'unavailable'
    if any(f['scope'] == 'scientific_integrity' for f in raw['issues']):
        return 'issues'
    if status == 'uncertain' or any(n['scope'] == 'scientific_integrity' and
            n['note_type'] == 'uncertainty' for n in raw['review_notes']):
        return 'uncertain'
    return 'supported'


def assessment_failure(exc, stage):
    """Expose request/response failures without parsing or changing scientific prose."""
    current, seen, paths = exc, set(), []
    validation_reason = None
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (CriticResponseError, EditorialStructureError, ValidationError)):
            validation_reason = validation_reason or str(current)
            paths.extend(getattr(current, 'paths', []) or [tuple(getattr(current, 'absolute_path', ()))])
        current = current.__cause__
    field_paths = [list(p) for p in dict.fromkeys(tuple(p) for p in paths)]
    if validation_reason and field_paths:
        pointer = '/' + '/'.join(map(str, field_paths[0]))
        if not validation_reason.startswith(pointer + ':'):
            validation_reason = pointer + ': ' + validation_reason
    return {'stage': stage, 'status': 'failed',
            'error_kind': 'response_validation' if validation_reason else 'request_or_execution',
            'error_type': type(exc).__name__, 'reason': validation_reason or str(exc),
            'field_paths': field_paths}


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
            'authored_elements': deepcopy(identified_layout(state.get('styled_layout') or state.get('design_layout') or [])),
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


def _element_records(state):
    module_zones = {m['module_id']: m['zone_id'] for m in state['editorial_candidate']['modules']}
    return {e['id']: {'element_type': e.get('type', ''), 'module_id': e.get('section_id') or '',
                      'zone_id': e.get('zone_id') or module_zones.get(e.get('section_id'), '')}
            for e in identified_layout(state.get('styled_layout') or state.get('design_layout') or [])
            if e.get('id')}


def _identifiers(state):
    modules = {m['module_id'] for m in state['editorial_candidate']['modules']}
    zones = {z['zone_id'] for z in state['layout_spec'].get('zones', [])}
    elements = set(_element_records(state))
    measurements = set(state.get('critic_measurement_evidence') or {}) | {
        'editorial_fit', 'layout_preflight_report', 'render_fit_report'}
    return modules, zones, elements, measurements


def reference_catalog(state):
    """One explicit namespace: instruments own findings, never the reverse."""
    modules, zones, elements, measurements = _identifiers(state)
    instruments = state.get('critic_measurement_evidence') or {}
    return {'module_ids': sorted(modules), 'zone_ids': sorted(zones), 'element_ids': sorted(elements),
            'element_identity_version': ELEMENT_IDENTITY_VERSION, 'elements': _element_records(state),
            'measurements': {name: sorted({r['issue_id'] for r in (instruments.get(name) or {}).get('findings', [])
                                         if r.get('issue_id')}) for name in sorted(measurements)}}


def response_schema(state, schema):
    result = deepcopy(schema)
    references = reference_catalog(state)
    catalog = references['measurements']
    def identifiers(name, *, empty=True):
        return {'type': 'string', 'enum': ([''] if empty else []) + references[name]}
    for criterion in result['properties']['assessments']['properties'].values():
        fields = criterion['properties']['evidence']['items']['properties']
        fields['module_id'] = identifiers('module_ids')
        fields['element_id'] = identifiers('element_ids')
        fields['measurement_id'] = {'type': 'string', 'enum': ['', *catalog]}
        fields['finding_id'] = {'type': 'string', 'enum': ['', *sorted({f for ids in catalog.values() for f in ids})]}
    for name in ('issues', 'review_notes'):
        fields = result['properties'][name]['items']['properties']['location']['properties']
        for field, source in (('section_id', 'module_ids'), ('zone_id', 'zone_ids'), ('element_id', 'element_ids')):
            fields[field] = identifiers(source)
    if 'content_dependencies' in result['properties']:
        deps = result['properties']['content_dependencies']['properties']
        deps['modules']['items']['properties']['module_id'] = identifiers('module_ids', empty=False)
        for name in ('prerequisite_module_id', 'dependent_module_id'):
            deps['relations']['items']['properties'][name] = identifiers('module_ids', empty=False)
    if 'reading_review' in result['properties']:
        reading = result['properties']['reading_review']['properties']
        # STRINGS is shared by unrelated fields in the base schema; replace arrays
        # rather than modifying their shared items (e.g. forbidden_operations).
        reading['entry_module_ids'] = {'type': 'array', 'items': identifiers('module_ids', empty=False)}
        reading['likely_paths'] = {'type': 'array', 'items': {
            'type': 'array', 'items': identifiers('module_ids', empty=False)}}
        for name in ('ambiguous_transitions', 'dependency_conflicts'):
            for field in ('from_module_id', 'to_module_id'):
                reading[name]['items']['properties'][field] = identifiers('module_ids', empty=False)
    return result


def _validate(raw, schema, state):
    Draft202012Validator(schema).validate(raw)
    modules, zones, elements, measurements = _identifiers(state)
    owners = _element_records(state)
    catalog = reference_catalog(state)['measurements']

    def reference(value, allowed, path):
        if value and value not in allowed:
            raise CriticResponseError('Unknown identifier: ' + value, path)

    def ownership(identity, module, zone, path):
        owner = owners.get(identity)
        if owner and ((module and owner['module_id'] and module != owner['module_id']) or
                      (zone and owner['zone_id'] and zone != owner['zone_id'])):
            raise CriticResponseError('Element does not belong to the referenced module/zone: ' + identity, path)

    for key, metric in raw['assessments'].items():
        path = ('assessments', key)
        score = metric['score']
        unavailable = metric['assessment_status'] == 'unavailable'
        if unavailable != (score is None):
            raise CriticResponseError('Unavailable assessment must have a null score, and only it may be null', path)
        if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100):
            raise CriticResponseError('Critic score must be finite and within 0..100', (*path, 'score'))
        if not metric['reason'].strip() or (not unavailable and not metric['evidence']):
            raise CriticResponseError('Every assessed score needs a reason and evidence', path)
        if metric['assessment_status'] != 'assessed' and not metric['uncertainty'].strip():
            raise CriticResponseError('Uncertain/unavailable assessments must explain their limits', (*path, 'uncertainty'))
        for index, evidence in enumerate(metric['evidence']):
            for field, allowed in (('module_id', modules), ('element_id', elements), ('measurement_id', measurements)):
                reference(evidence[field], allowed, (*path, 'evidence', index, field))
            ownership(evidence['element_id'], evidence['module_id'], '', (*path, 'evidence', index, 'element_id'))
            finding = evidence['finding_id']
            if finding and finding not in catalog.get(evidence['measurement_id'], []):
                raise CriticResponseError('Finding does not belong to the referenced measurement: ' + finding,
                                          (*path, 'evidence', index, 'finding_id'))
    observations = [(field, i, f) for field in ('issues', 'review_notes') for i, f in enumerate(raw[field])]
    for field, index, finding in observations:
        path = (field, index)
        location = finding['location']
        for name, allowed in (('section_id', modules), ('zone_id', zones), ('element_id', elements)):
            reference(location[name], allowed, (*path, 'location', name))
        ownership(location['element_id'], location['section_id'], location['zone_id'], (*path, 'location', 'element_id'))
        if location['section_id'] and location['zone_id']:
            expected = next(m['zone_id'] for m in state['editorial_candidate']['modules']
                            if m['module_id'] == location['section_id'])
            if expected != location['zone_id']:
                raise CriticResponseError('Critic module and zone location contradict each other', (*path, 'location'))
        if finding['scope'] == 'scientific_integrity' and not finding['original_support'].strip():
            raise CriticResponseError('Scientific observations must state original support, conflict or uncertainty',
                                      (*path, 'original_support'))
        if not finding['observation'].strip():
            raise CriticResponseError('Review observations must not be blank', (*path, 'observation'))
        if field == 'issues' and not finding['required_outcome'].strip():
            raise CriticResponseError('Confirmed problems need a required outcome', (*path, 'required_outcome'))
    if 'content_dependencies' in raw:
        deps = raw['content_dependencies']
        ids = [m['module_id'] for m in deps['modules']]
        if len(ids) != len(set(ids)) or set(ids) != modules:
            raise CriticResponseError('Content dependencies must describe every real module exactly once',
                                      ('content_dependencies', 'modules'))
        for index, relation in enumerate(deps['relations']):
            for field in ('prerequisite_module_id', 'dependent_module_id'):
                reference(relation[field], modules, ('content_dependencies', 'relations', index, field))
    if 'reading_review' in raw:
        reading = raw['reading_review']
        for index, module in enumerate(reading['entry_module_ids']):
            reference(module, modules, ('reading_review', 'entry_module_ids', index))
            if not module:
                raise CriticResponseError('Reading paths must reference real modules', ('reading_review', 'entry_module_ids', index))
        for index, route in enumerate(reading['likely_paths']):
            for position, module in enumerate(route):
                path = ('reading_review', 'likely_paths', index, position)
                reference(module, modules, path)
                if not module:
                    raise CriticResponseError('Reading paths must reference real modules', path)
        for field in ('ambiguous_transitions', 'dependency_conflicts'):
            for index, transition in enumerate(reading[field]):
                for name in ('from_module_id', 'to_module_id'):
                    reference(transition[name], modules, ('reading_review', field, index, name))


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
        'render_diagnostics': _render_diagnostics(state), 'reference_catalog': reference_catalog(state)}
    schema = response_schema(state, CONTENT_SCHEMA)
    prompt = PROMPT_ROOT / 'editorial_content_critic.txt'
    binding = digest({'payload': payload, 'schema': schema, 'model': state['text_model'],
                      'prompt': file_hash(prompt)})
    if state.get('_editorial_content_input_digest') == binding:
        if state.get('_editorial_content_error'):
            raise EditorialOutputError(state['_editorial_content_error'])
        raw = state['_editorial_content_evaluation']
        _validate(raw, schema, state)
        return raw
    state['_editorial_content_input_digest'] = binding
    state.pop('_editorial_content_evaluation', None)
    state.pop('_editorial_content_error', None)
    try:
        raw = request(state, 'editorial_content_critic', payload, schema,
            directory='editorial/final_content', correction=False,
            validator=lambda value: _validate(value, schema, state))
        _validate(raw, schema, state)
        state['_editorial_content_evaluation'] = raw
        state['editorial_factual_status'] = scientific_status(raw)
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
        metadata={'submetric_assessments': assessments, 'reason': raw['reason'],
                  'assessment_stage': {'stage': 'visual' if name == 'visual' else 'content', 'status': 'complete'},
                  'review_notes': deepcopy([n for n in raw['review_notes'] if
                      (name == 'visual' or (n['scope'] == 'scientific_integrity') == (name == 'grounding'))])})
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
                             passed=scientific_status(raw) == 'supported' if self.name == 'grounding' else True)


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
            'measurement_evidence': measurement_evidence(state), 'render_diagnostics': _render_diagnostics(state),
            'reference_catalog': reference_catalog(state)}
        schema = response_schema(state, VISUAL_SCHEMA)
        raw = request(state, 'editorial_visual_critic', payload, schema,
            directory='editorial/final_visual', images=[state['current_candidate']['png_path']], correction=False,
            validator=lambda value: _validate(value, schema, state))
        _validate(raw, schema, state)
        state['_editorial_visual_evaluation'] = raw
        prompt = PROMPT_ROOT / 'editorial_visual_critic.txt'
        binding = digest({'payload': payload, 'schema': schema, 'model': state['vision_model'],
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
