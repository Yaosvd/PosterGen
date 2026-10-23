"""Sample-bound raw responses and durable, at-most-once module-plan correction."""
from pathlib import Path

from utils.persistence import _atomic_json, digest, read_json

VERSION = 'module_planning_v2'


class ModulePlanningRequests:
    def __init__(self, state, prompt, *, directory='content/module_planning', kind='module_plan_correction', scope='module_plan'):
        self.state = state
        self.root = Path(state['output_dir'])/directory
        self.kind, self.scope = kind, scope
        self.identity = {'version': VERSION, 'context': state.get('iteration_context'),
                         'paper_digest': state.get('paper_foundation_digest'),
                         'model': state.get('text_model'), 'prompt_digest': digest(prompt)}
        self.input_digest = digest(self.identity)
        path = self.root/'identity.json'
        if path.exists():
            payload = read_json(path)
            if payload.get('input_digest') != self.input_digest or digest(payload.get('identity')) != self.input_digest:
                raise ValueError('Module planning input identity mismatch')
        else:
            if self.root.exists() and any(self.root.iterdir()):
                raise ValueError('Module planning identity is missing from existing history')
            _atomic_json(path, {'input_digest': self.input_digest, 'identity': self.identity})

    def read(self, name):
        envelope = read_json(self.root/name)
        payload = envelope['payload']
        if envelope.get('digest') != digest(payload) or payload.get('input_digest') != self.input_digest:
            raise ValueError('Module planning diagnostic digest/identity mismatch')
        return payload

    def write(self, name, **fields):
        payload = {'input_digest': self.input_digest, **fields}
        _atomic_json(self.root/name, {'payload': payload, 'digest': digest(payload)})

    def request(self, index, agent, prompt):
        if type(index) is not int or index not in (0, 1):
            raise ValueError('Only an initial module plan and one correction are allowed')
        charge_name = f'request_{index:02d}.json'
        response_name = f'response_{index:02d}.json'
        charge = self.root/charge_name
        response = self.root/response_name
        prompt_digest = digest(prompt)
        if response.exists() and not charge.exists():
            raise ValueError('Module planning response has no durable request charge')
        if index == 1:
            reused = charge_preparation_repair(self.state, self.kind, self.scope, prompt_digest)
            if reused and not charge.exists():
                raise ValueError('Preparation correction was charged before interruption; refusing automatic resubmission')
        if charge.exists():
            if self.read(charge_name).get('prompt_digest') != prompt_digest:
                raise ValueError('Module planning request prompt changed')
            if not response.exists():
                raise ValueError(f'Module planning request {index} was charged but has no saved response; refusing automatic resubmission')
            saved = self.read(response_name)
            if saved.get('prompt_digest') != prompt_digest:
                raise ValueError('Module planning response prompt changed')
            return saved['content']
        # The charge precedes the physical call and is never refunded on failure/stop.
        self.write(charge_name, prompt_digest=prompt_digest,
                   kind='initial' if index == 0 else self.kind, scope=self.scope, limit=1)
        agent.reset()
        try:
            result = agent.step(prompt)
        except BaseException as exc:
            self.write(f'request_failure_{index:02d}.json', error_type=type(exc).__name__)
            raise
        # Archive raw model content before parsing or validating it.
        self.write(response_name, prompt_digest=prompt_digest, content=result.content,
                   input_tokens=int(result.input_tokens), output_tokens=int(result.output_tokens))
        self.state['tokens'].add_text(int(result.input_tokens), int(result.output_tokens))
        return result.content


def charge_preparation_repair(state, kind, scope, prompt_digest):
    """One editorial repair for the entire sample preparation, not layout work."""
    root = Path(state.get('sample_preparation_dir') or state['output_dir'])
    identity = digest({'version': VERSION, 'context': state.get('iteration_context'),
                       'paper': state.get('paper_foundation_digest'),
                       'narrative': state.get('narrative_plan')})
    path = root/'preparation_repair_budget.json'
    charge = {'kind': kind, 'scope': scope, 'prompt_digest': prompt_digest}
    if path.exists():
        envelope = read_json(path)
        payload = envelope['payload']
        if envelope.get('digest') != digest(payload) or payload.get('input_digest') != identity:
            raise ValueError('Preparation repair budget identity/digest mismatch')
        if payload.get('charge') != charge:
            raise ValueError('Shared preparation repair allowance is exhausted')
        return True
    payload = {'input_digest': identity, 'limit': 1, 'charge': charge}
    _atomic_json(path, {'payload': payload, 'digest': digest(payload)})
    return False
