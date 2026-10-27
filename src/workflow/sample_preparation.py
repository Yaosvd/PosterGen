"""Crash-safe per-sample planning/writing/verification, never a shared claim cache."""
from copy import deepcopy

from src.workflow.content_contracts import PREPARATION_VERSION, paper_fields, science_fields, science_ready
from utils.persistence import _atomic_json, digest, read_json


class SamplePreparation:
    def __init__(self, store, run_id, nodes):
        self.store, self.run_id, self.nodes = store, run_id, list(nodes)

    def run(self, state, task, execute, control, after_planner=None):
        root = self.store.sample_path(self.run_id, task['sample_id']) / 'preparation'
        root.mkdir(parents=True, exist_ok=True)
        state['output_dir'] = str(root)
        state['sample_preparation_dir'] = str(root)
        state['sample_edit_budget_dir'] = str(root.parent)
        state['iteration_context'] = {
            'run_id': self.run_id, 'sample_id': task['sample_id'],
            'iteration': task['number'], 'random_seed': task['seed'],
            'generation_purpose': 'sample_preparation', 'preparation_policy_version': PREPARATION_VERSION,
        }
        expected = digest({'version': PREPARATION_VERSION, 'run_id': self.run_id,
                           'sample_id': task['sample_id'], 'seed': task['seed'],
                           'paper': state['paper_foundation_digest']})
        paper_digest = digest(paper_fields(state))
        ready = root / 'READY.json'
        if ready.exists():
            if after_planner:
                name = getattr(self.nodes[0], '__name__', type(self.nodes[0]).__name__)
                first = self._read(root/'stage_01.json', digest({'previous': expected, 'stage': 0, 'node': name}))
                state.update(deepcopy(first['fields']))
                after_planner(state)
            snapshot = self._read(ready, expected)
            if self._read(root / 'sample_science.json', expected) != snapshot:
                raise ValueError('Sample science and ready marker disagree')
            if not science_ready({**state, **snapshot['fields']}):
                raise ValueError('Saved sample science is not verified')
            if after_planner and snapshot['fields'].get('sample_family') != state.get('sample_family'):
                raise ValueError('Ready science belongs to a different frozen family')
            state.update(deepcopy(snapshot['fields']))
            state['sample_science_digest'] = digest(snapshot)
            return state
        for index, node in enumerate(self.nodes):
            name = getattr(node, '__name__', type(node).__name__)
            checkpoint = root / f'stage_{index+1:02d}.json'
            identity = digest({'previous': expected, 'stage': index, 'node': name})
            if checkpoint.exists():
                snapshot = self._read(checkpoint, identity)
                state.update(deepcopy(snapshot['fields']))
            else:
                if control.force_stop_requested:
                    return state
                # Initial preparation accounting is separate from layout repair budgets.
                ledger = root / 'model_work_ledger.json'
                usage = read_json(ledger) if ledger.exists() else {'version': 1, 'charges': []}
                usage['charges'].append({'stage': name, 'checkpoint': checkpoint.name})
                _atomic_json(ledger, usage)
                state = execute(state, [node], stage='sample_preparation')
                if state.get('_joint_interrupted') and control.force_stop_requested:
                    return state
                if digest(paper_fields(state)) != paper_digest:
                    state['fatal_generation_error'] = True
                    state.setdefault('errors', []).append(
                        f'{name}: sample preparation changed immutable paper evidence')
                if state.get('errors') or state.get('attempt_failure_report'):
                    _atomic_json(root / 'failure.json', {
                        'stage': name, 'errors': state.get('errors'),
                        'failure': state.get('attempt_failure_report')})
                    return state
                snapshot = {'input_digest': identity, 'fields': science_fields(state)}
                _atomic_json(checkpoint, {'payload': snapshot, 'digest': digest(snapshot)})
            expected = digest(snapshot)
            if index == 0 and after_planner:
                after_planner(state)
            if after_planner:
                expected = digest({'stage': expected, 'family': state.get('sample_family')})
            if control.force_stop_requested:
                return state
        if not science_ready(state):
            state.setdefault('errors', []).append('sample_preparation: no verified sample science')
            _atomic_json(root / 'failure.json', {'errors': state['errors']})
            return state
        payload = {'input_digest': digest({'version': PREPARATION_VERSION, 'run_id': self.run_id,
                    'sample_id': task['sample_id'], 'seed': task['seed'],
                    'paper': state['paper_foundation_digest']}),
                   'fields': science_fields(state), 'stage_chain_digest': expected}
        _atomic_json(root / 'sample_science.json', {'payload': payload, 'digest': digest(payload)})
        _atomic_json(ready, {'payload': payload, 'digest': digest(payload)})
        state['sample_science_digest'] = digest(payload)
        return state

    @staticmethod
    def _read(path, expected):
        envelope = read_json(path)
        payload = envelope['payload']
        if envelope['digest'] != digest(payload) or payload['input_digest'] != expected:
            raise ValueError('Sample preparation checkpoint identity or digest mismatch')
        return payload
