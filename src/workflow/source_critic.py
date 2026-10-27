"""Source-editorial Critic adapters; history keeps its original rubric identity."""
from copy import deepcopy
from pathlib import Path
import json
import re

from src.critic.base import EvaluationResult, issue
from src.workflow.source_document import source_material
from src.workflow.source_requests import SourceRequests, object_schema, STRING, STRINGS
from src.workflow.source_reading import (READING_SCHEMA, READING_INSTRUCTIONS, reading_context,
                                        check_reading_review)

SCORE = {'type': 'number', 'minimum': 0, 'maximum': 100}
CONTENT_KEYS = ('information_layering','information_coverage','information_depth',
                'information_completeness','narrative_structure','narrative_conciseness')


def source_critic_config(config):
    result = deepcopy(config)
    result['rubric_version'] = 'academic_poster_source_editorial_v1'
    result['critic_system_version'] = '5.0.0'
    for name in ('grounding','information_narrative','content_adequacy','visual','layout_family'):
        if name in result.get('evaluators', {}):
            result['evaluators'][name]['version'] = 'source_editorial_v1'
    return result


def _result(context, name, **kwargs):
    settings = context.config.get('evaluators', {}).get(name, {})
    return EvaluationResult(evaluator=name, version=settings.get('version', 'source_editorial_v1'),
                            hard_gate=settings.get('hard_gate', False), **kwargs)


def final_visual_payload(evaluator, context, png):
    """One existing visual-Critic request includes final natural-reading judgment."""
    from utils.langgraph_utils import LangGraphAgent
    from utils.agent_policy import apply_agent_policy
    state = context.state
    board = state.get('optimized_story_board') or state.get('story_board') or {}
    data = reading_context(state, board, state.get('layout_spec') or {},
                           state.get('styled_layout') or state.get('design_layout') or [],
                           png, (state.get('current_candidate') or {}).get('candidate_id', 'final'))
    schema = object_schema({'scores': object_schema({k:SCORE for k in evaluator._DIMENSIONS}),
        'submetrics': object_schema({k:SCORE for k in evaluator._SUBMETRICS}),
        'issues': {'type': 'array', 'items': object_schema({'severity': STRING, 'scope': STRING,
            'location': object_schema({'zone_id': STRING, 'section_id': STRING, 'element_id': STRING}),
            'observation': STRING, 'required_outcome': STRING, 'allowed_operations': STRINGS,
            'forbidden_operations': STRINGS})},
        'positive_patterns': {'type': 'array', 'items': object_schema({'scope': STRING, 'observation': STRING})},
        'reading_review': READING_SCHEMA})
    prompt = (evaluator.prompt+'\n'+READING_INSTRUCTIONS+
        '\nUse the COMPLETE schema below (including reading_review); empty location strings mean unknown.\n'
        +json.dumps(data, ensure_ascii=False, sort_keys=True))
    requests = SourceRequests(state, 'source/final_visual', prompt, schema, vision=True, images=[png], allow_correction=False)
    agent = LangGraphAgent('Evaluate the actual final academic poster neutrally, including natural reading.',
        apply_agent_policy(state['vision_model'], 'critic_visual'), state, 'critic_visual')
    raw = requests.call(agent)
    review = check_reading_review(raw['reading_review'], data)
    state['source_final_reading_review'] = {'version': 'visual_natural_reading_v1', **deepcopy(review),
                                          'input_context': data, 'png_path': str(png)}
    state['source_reading_status'] = {'status': review['status'], 'scope': 'actual_final_png',
        'image_digest': data['binding']['image_digest']}
    # The existing visual report exposes actionable reading findings too.
    for finding in review['issues']:
        raw['issues'].append({'severity': 'major', 'scope': 'reading_flow',
            'location': {'section_id': finding['module_ids'][0], 'zone_id': '', 'element_id': ''},
            'observation': finding['reason'], 'required_outcome': finding['suggestion'],
            'allowed_operations': ['reorder_sections','move_section_to_zone'],
            'forbidden_operations': ['invent_claim']})
    return raw, data


def information_result(context):
    from utils.langgraph_utils import LangGraphAgent
    from utils.agent_policy import apply_agent_policy
    state = context.state
    review = state.get('source_final_reading_review')
    scores, problems, completed = {}, [], False
    settings = context.config.get('evaluators', {}).get('information_narrative', {})
    if settings.get('semantic_enabled', True) and state.get('text_model'):
        schema = object_schema({'scores': object_schema({k:SCORE for k in CONTENT_KEYS}), 'reason': STRING})
        payload = {'original': source_material(state), 'candidate': state['source_candidate'],
            'story': state['source_narrative_plan'], 'source_verification': state['source_verification_report'],
            'actual_final_reading_review': review}
        prompt = ('Evaluate poster explanation, coverage of indispensable meaning, depth, hierarchy, completeness, '
            'coherence and concision from ORIGINAL sections and the actual candidate. '
            'No precomputed evidence IDs/counts, fixed module/figure counts or ABT requirements. '
            'Do not decide physical natural routes from role/source order; that assessment is in the actual-image review. '
            'Coverage is necessary meanings actually expressed with conditions, not number of references. '
            'Scientific verifier approval certifies support, not excellent writing.\n'+json.dumps(payload, ensure_ascii=False, sort_keys=True))
        journal = SourceRequests(state, 'source/final_content', prompt, schema, allow_correction=False)
        try:
            agent = LangGraphAgent('Evaluate source-grounded academic-poster writing quality.',
                apply_agent_policy(state['text_model'], 'critic_content'), state, 'critic_content')
            raw = journal.call(agent)
            scores.update(raw['scores']); completed = True
        except Exception as exc:
            # Preserve unavailable quality evidence; never substitute evidence-count 100.
            problems.append(issue('SOURCE-CONTENT-EVALUATION-UNAVAILABLE', severity='warning', scope='critic',
                observation=f'Original-source content quality evaluation unavailable: {type(exc).__name__}',
                required_outcome='Inspect saved evaluation diagnostics'))
    if review and review['status'] != 'incomplete':
        scores['narrative_flow'] = {'clear': 100.0, 'needs_revision': 40.0, 'ambiguous': 50.0}[review['status']]
    return _result(context, 'information_narrative', passed=True,
        scores={'content_quality': round(sum(scores.values())/len(scores),2)} if completed and scores else {},
        issues=problems, metadata={'submetrics': scores, 'semantic_model_completed': completed,
            'coverage_basis': 'direct_original_source_and_indispensable_meanings',
            'reading_flow': review or {'status': 'incomplete', 'scope': 'final_png_not_assessed'}})


def adequacy_result(context):
    state = context.state
    fit = state.get('section_fit_analysis') or {}
    modules = state['source_candidate']['modules']
    duplicates = sparse = 0
    problems = []
    for module in modules:
        texts = [' '.join(e['text'].casefold().split()) for e in module['entries']]
        duplicates += len(texts)-len(set(texts))
        metric = (fit.get('sections') or {}).get(module['module_id'], {})
        use = float(metric.get('utilization', 1.0))
        if use < float((fit.get('ideal_band') or [.95, 1])[0]):
            sparse += 1
            problems.append(issue('SOURCE-CONTENT-UNDERFILLED-'+module['module_id'], severity='major' if use < .9 else 'warning',
                scope='content_quality', location={'section_id': module['module_id']},
                observation='Measured module is underfilled; original sections remain available, usefulness of additions is unassessed',
                evidence={'utilization': use, 'original_source_ids': [r['source_id'] for r in module['source_refs']]},
                required_outcome='Explain useful source-supported material or adjust legal space without filler',
                allowed_operations=['edit_from_original_source','adjust_zone_budget'], forbidden_operations=['invent_claim']))
    return _result(context, 'content_adequacy', passed=True,
        scores={'content_quality': max(0.0, 100-25*duplicates-6*sparse)}, issues=problems,
        metadata={'coverage_basis': 'necessary_meaning_verdicts_not_evidence_counts',
                  'covered_obligation_ids': state['source_verification_report']['covered_obligation_ids'],
                  'underfilled_section_count': sparse, 'duplicate_claim_count': duplicates})
