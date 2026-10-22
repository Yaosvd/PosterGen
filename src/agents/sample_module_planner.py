"""One sample-local Curator call before module prose is written."""
import json
from pathlib import Path

from jinja2 import Template
from utils.agent_policy import apply_agent_policy
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from utils.persistence import _atomic_json
from src.workflow.sample_modules import normalize_module_plan


def sample_module_planner_node(state):
    try:
        plan = state['narrative_plan']
        ids = {e for s in plan['sections'] for e in s['evidence_ids']}
        evidence = [e for e in state['evidence_bank']['items'] if e['evidence_id'] in ids]
        visuals = [{'visual_id': f'{prefix}_{k}', 'caption': v.get('caption', ''), 'aspect': v.get('aspect')}
                   for prefix, field in [('figure', 'images'), ('table', 'tables')]
                   for k, v in (state.get(field) or {}).items()]
        agent = LangGraphAgent('Plan coherent evidence-grounded display modules. Do not write scientific prose.',
                               apply_agent_policy(state['text_model'], 'curator'), state, 'grounded_curator')
        prompt = Template(load_prompt('config/prompts/plan_sample_modules.txt')).render(
            plan=json.dumps(plan, ensure_ascii=False), evidence=json.dumps(evidence, ensure_ascii=False),
            visuals=json.dumps(visuals, ensure_ascii=False), width=state['poster_width'], height=state['poster_height'])
        agent.reset()
        response = agent.step(prompt)
        state['tokens'].add_text(int(response.input_tokens), int(response.output_tokens))
        state['sample_module_plan'] = normalize_module_plan(extract_json(response.content), state)
        _atomic_json(Path(state['output_dir'])/'content/sample_module_plan.json', state['sample_module_plan'])
        state['current_agent'] = 'curator'
    except Exception as exc:
        state.setdefault('errors', []).append(f'sample_module_planner: {exc}')
    return state
