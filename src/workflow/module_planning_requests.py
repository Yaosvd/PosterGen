"""Sample-bound raw responses and durable, at-most-once module-plan correction."""
from pathlib import Path

from utils.persistence import _atomic_json, digest, read_json

VERSION = 'module_planning_v1'


class ModulePlanningRequests:
    def __init__(self, state, prompt):
        self.state = state
        self.root = Path(state['output_dir'])/'content/module_planning'
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
                   kind='initial' if index == 0 else 'module_plan_correction', limit=1)
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
