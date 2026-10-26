"""Sample-local module planning, with one durable correction for invalid output."""
import json
from pathlib import Path

from jinja2 import Template
from utils.agent_policy import apply_agent_policy
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from utils.persistence import _atomic_json
from src.workflow.module_planning_requests import ModulePlanningRequests, VERSION
from src.workflow.module_plan_patches import identify_modules, apply_module_patch
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
        from src.workflow.sample_editorial import visual_context
        from src.layout.family_capacity import family_brief
        brief = family_brief(state) if state.get('joint_preparation') else {'zones': []}
        visuals = visual_context(state, brief)
        template = Template(load_prompt('config/prompts/plan_sample_modules.txt'))
        required_ids = {e for u in plan['sections'] for e in u.get('required_evidence_ids', [])}
        required = [{'evidence_id': e['evidence_id'], 'claim': e.get('claim', ''),
                     'source_plan_unit_ids': owners[e['evidence_id']]} for e in evidence if e['evidence_id'] in required_ids]
        inputs = dict(required=json.dumps(required), plan=json.dumps(plan, ensure_ascii=False), evidence=json.dumps(evidence, ensure_ascii=False),
                      visuals=json.dumps(visuals, ensure_ascii=False), width=state['poster_width'], height=state['poster_height'])
        if state.get('joint_preparation'):
            inputs['family_capacity'] = json.dumps(brief, ensure_ascii=False)
        prompt = template.render(**inputs)
        history = ModulePlanningRequests(state, prompt)
        agent = LangGraphAgent('Plan coherent evidence-grounded display modules. Do not write scientific prose.',
                               apply_agent_policy(state['text_model'], 'curator'), state, 'grounded_curator')
        draft = None
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
                draft = identify_modules(parsed) if index == 0 else apply_module_patch(draft, parsed)
                history.write(f'draft_{index:02d}.json', draft=draft)
                normalized = normalize_module_plan(draft, state)
            except ModulePlanValidationError as exc:
                history.write(f'validation_{index:02d}.json', status='rejected', issues=exc.issues,
                              source_normalizations=exc.normalizations)
                if index == 1:
                    raise
                # Reset conversation: authoritative inputs plus exact defects and archived draft.
                prompt = template.render(**inputs, correction=json.dumps({
                    'issues': exc.issues, 'draft': draft, 'previous_response': content}, ensure_ascii=False))
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
        from src.workflow.sample_errors import record_sample_error
        record_sample_error(state, exc, 'module_planning_failed', output_error=isinstance(exc, ModulePlanValidationError))
        state.setdefault('errors', []).append(f'sample_module_planner: {exc}')
    return state
