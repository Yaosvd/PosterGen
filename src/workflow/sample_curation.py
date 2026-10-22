"""Immutable sample-local display plans, plus one charged, targeted revision."""
from copy import deepcopy

from src.layout.editorial_selection import required_roots
from src.layout.repair_budget import available_rounds, budget_usage, charge_round
from src.workflow.content_contracts import science_fields
from utils.persistence import _atomic_json, digest, read_json

VERSION = 'sample_curation_v1'
FIELDS = ('story_board', 'visual_curation_report', 'module_provenance', 'source_context_overlay')


class SampleCuration:
    def __init__(self, store, run_id, sample_id):
        self.root = store.sample_path(run_id, sample_id)/'curation'
        self.run_id, self.sample_id = run_id, sample_id

    def _identity(self, state):
        return digest({'version': VERSION, 'run_id': self.run_id, 'sample_id': self.sample_id,
                       'science': state['sample_science_digest']})

    def current(self, state):
        paths = sorted(self.root.glob('board_*.json'))
        if not paths:
            return None
        row = read_json(paths[-1]);payload = row['payload']
        if row['digest'] != digest(payload) or payload['input_digest'] != self._identity(state):
            raise ValueError('Sample curation identity or digest mismatch')
        return payload

    def run(self, state, node):
        saved = self.current(state)
        repair = state.get('curation_repair_context')
        if saved and not repair:
            state.update(deepcopy(saved['fields']))
            state['curation_report'] = {'version': VERSION, 'revision': saved['revision'], 'status': 'reused'}
            return state
        science_digest = digest(science_fields(state))
        state = node(state)
        if digest(science_fields(state)) != science_digest:
            raise ValueError('Curator changed immutable sample science')
        if state.get('errors') or state.get('attempt_failure_report'):
            return state
        board = state.get('story_board') or {}
        if not board.get('spatial_content_plan', {}).get('sections'):
            raise ValueError('Curator produced no display modules')
        revision = saved['revision'] + 1 if saved else 0
        if revision > 1:
            raise ValueError('Sample curation revision budget exceeded')
        if repair:
            visible = {cid for s in board['spatial_content_plan']['sections'] for cid in s.get('claim_ids', [])}
            protected = set(repair['protected_claim_ids'])
            owners = {cid: s['section_id'] for s in board['spatial_content_plan']['sections']
                      for cid in s.get('claim_ids', [])}
            edges = [(h['claim_id'], dep) for s in repair['base_board']['spatial_content_plan']['sections']
                     for h in (s.get('editorial') or {}).get('items', [])
                     for dep in h.get('requires_claim_ids', [])]
            new_edges = {(h['claim_id'], dep) for s in board['spatial_content_plan']['sections']
                         for h in (s.get('editorial') or {}).get('items', [])
                         for dep in h.get('requires_claim_ids', [])}
            # Keeping both sentences once is insufficient: downstream subsets
            # must retain the original prerequisite constraint as well.
            violated = any(a in visible and (b not in visible or owners[a] != owners[b]
                           or (a, b) not in new_edges) for a, b in edges)
            if not protected <= visible or not protected <= required_roots(board, state) or violated:
                state.update(deepcopy(saved['fields']))
                state['curation_report'] = {'version': VERSION, 'revision': saved['revision'],
                    'status': 'repair_rejected', 'reason': 'protected_content_or_dependency'}
                _atomic_json(self.root/'revision_rejection.json', state['curation_report'])
                return state
        payload = {'input_digest': self._identity(state), 'revision': revision,
                   'fields': {key: deepcopy(state.get(key)) for key in FIELDS}}
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_json(self.root/f'board_{revision:02d}.json', {'payload': payload, 'digest': digest(payload)})
        state['curation_report'] = {'version': VERSION, 'revision': revision, 'status': 'prepared'}
        return state

    def revision(self, state):
        saved = self.current(state)
        return saved['revision'] if saved else 0

    def repair_context(self, state):
        """Charge before work; an interrupted/failed revision never gets a free retry."""
        saved = self.current(state)
        if not saved or saved['revision'] >= 1:
            return None
        settings = (state.get('critic_config') or {}).get('capacity_repair') or {}
        attempt = (state.get('iteration_context') or {}).get('attempt_diagnostics_dir')
        if not attempt:
            return None
        from pathlib import Path
        for p in Path(attempt).parent.glob('*/model_repair_budget.json'):
            if any(c.get('kind') == 'curation' for c in read_json(p).get('charges', [])):
                return None
        if available_rounds(state, 'capacity', settings) < 1 or not charge_round(state, 'capacity', settings, kind='curation'):
            return None
        board = saved['fields']['story_board']
        original = {**state, **saved['fields']}
        fit = state.get('layout_feasibility_report') or {}
        pressure = fit.get('repair_pressure_candidates') or fit.get('progress_pressure_samples') or []
        feedback = {'version': VERSION, 'reason_code': fit.get('reason_code'),
                    'protected_claim_ids': sorted(required_roots(board, original)),
                    'base_board': deepcopy(board),
                    'presentation_preparation': fit.get('presentation_preparation') or {},
                    'height_pressure': [{k: row.get(k) for k in ('section_id', 'zone_id', 'estimated_used_in',
                        'zone_limit_in', 'option_claim_ids')} for row in pressure[:8]],
                    'charged_repair_usage': list(budget_usage(attempt))}
        _atomic_json(self.root/'revision_request.json', feedback)
        return feedback
