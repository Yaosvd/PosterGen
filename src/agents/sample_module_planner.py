"""Sample-local module planning, with one durable correction for invalid output."""
import json
from pathlib import Path

from jinja2 import Template
from utils.agent_policy import apply_agent_policy
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from utils.persistence import _atomic_json
from src.workflow.module_planning_requests import ModulePlanningRequests, VERSION
from src.workflow.sample_modules import (
    ModulePlanValidationError, module_evidence_owners, normalize_module_plan,
)


def sample_module_planner_node(state):
    history = None
    try:
        plan = state['narrative_plan']
        owners = module_evidence_owners(state)
        evidence = [{**e, 'source_plan_unit_ids': owners[e['evidence_id']]}
                    for e in state['evidence_bank']['items'] if e['evidence_id'] in owners]
        visuals = [{'visual_id': f'{prefix}_{k}', 'caption': v.get('caption', ''), 'aspect': v.get('aspect')}
                   for prefix, field in [('figure', 'images'), ('table', 'tables')]
                   for k, v in (state.get(field) or {}).items()]
        template = Template(load_prompt('config/prompts/plan_sample_modules.txt'))
        inputs = dict(plan=json.dumps(plan, ensure_ascii=False), evidence=json.dumps(evidence, ensure_ascii=False),
                      visuals=json.dumps(visuals, ensure_ascii=False), width=state['poster_width'], height=state['poster_height'])
        prompt = template.render(**inputs)
        history = ModulePlanningRequests(state, prompt)
        agent = LangGraphAgent('Plan coherent evidence-grounded display modules. Do not write scientific prose.',
                               apply_agent_policy(state['text_model'], 'curator'), state, 'grounded_curator')
        for index in range(2):
            content = history.request(index, agent, prompt)
            try:
                if not isinstance(content, str):
                    raise ModulePlanValidationError([{'code': 'invalid_response_content_format'}])
                try:
                    parsed = extract_json(content)
                except (ValueError, TypeError) as exc:
                    raise ModulePlanValidationError([{'code': 'invalid_json', 'error_type': type(exc).__name__}]) from exc
                history.write(f'parsed_{index:02d}.json', parsed=parsed)
                normalized = normalize_module_plan(parsed, state)
            except ModulePlanValidationError as exc:
                history.write(f'validation_{index:02d}.json', status='rejected', issues=exc.issues,
                              source_normalizations=exc.normalizations)
                if index == 1:
                    raise
                # Reset conversation: authoritative inputs plus exact defects and archived draft.
                prompt = template.render(**inputs, correction=json.dumps({
                    'issues': exc.issues, 'previous_response': content}, ensure_ascii=False))
                continue
            history.write(f'validation_{index:02d}.json', status='accepted', issues=[],
                          source_normalizations=normalized['source_normalizations'])
            normalized['planning_diagnostics'] = {'version': VERSION, 'input_digest': history.input_digest,
                                                 'accepted_attempt': index, 'correction_used': index == 1}
            state['sample_module_plan'] = normalized
            _atomic_json(Path(state['output_dir'])/'content/sample_module_plan.json', normalized)
            history.write('result.json', status='accepted', accepted_attempt=index)
            state['current_agent'] = 'curator'
            return state
    except Exception as exc:
        if history is not None:
            history.write('result.json', status='failed', error_type=type(exc).__name__,
                          issues=getattr(exc, 'issues', []))
        state.setdefault('errors', []).append(f'sample_module_planner: {exc}')
    return state
