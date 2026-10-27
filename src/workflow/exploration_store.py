"""Independent sample storage. Historical Campaigns and templates are never read."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import os
import re
import shutil
import uuid

from src.layout.template_export import export_template
from src.workflow.content_contracts import PAPER_FIELDS, SCIENCE_FIELDS, paper_fields
from utils.persistence import _atomic_json, digest, file_hash, read_json

SCHEMA = 2
DATASET = 'rubrics_samples_v2'
DIAGNOSTIC_FIELDS = (
    'story_board', 'optimized_story_board', 'layout_spec', 'styled_layout',
    'layout_feasibility_report', 'layout_preflight_report', 'render_fit_report',
    'capacity_repair_report', 'layout_performance_report', 'attempt_failure_report',
    'content_selection', 'verified_content_bank', 'supplemental_evidence_bank',
    'visual_curation_report', 'color_scheme', 'color_provenance', 'keywords',
    *SCIENCE_FIELDS, 'module_provenance', 'paper_foundation_digest', 'sample_science_digest',
    'curation_report', 'render_history', 'derived_candidate', 'source_final_reading_review', 'source_reading_status',
)


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Invalid run or sample identity')
    return value


class ExplorationStore:
    def __init__(self, root='storage/rubrics_samples'):
        self.root = Path(root).resolve()
        self.runs = self.root / 'runs'
        self.posters = self.root / 'posters'

    def run_path(self, run_id):
        path = self.runs / safe_id(run_id)
        if path.is_symlink() or not path.resolve().is_relative_to(self.runs.resolve()):
            raise ValueError('Run path escapes the sample store')
        return path

    def open_run(self, identity, settings, *, run_id=None, seed=None, samples=None):
        if run_id:
            path = self.run_path(run_id)
            manifest = read_json(path / 'manifest.json')
            if manifest.get('schema_version') != SCHEMA or manifest.get('dataset') != DATASET:
                raise ValueError('This run uses an older preparation contract; resume with its matching code version or start a new run')
            if manifest['identity'] != identity or manifest['settings_digest'] != digest(settings):
                raise ValueError('Run inputs, models, generation or evaluation policy changed')
            if samples is not None and samples != manifest['samples']:
                raise ValueError('A resumed run retains its frozen sample count')
            if seed is not None and seed != manifest['seed']:
                raise ValueError('A resumed run retains its frozen random seed')
            return run_id, manifest
        run_id = 'run_' + uuid.uuid4().hex[:20]
        path = self.run_path(run_id)
        path.mkdir(parents=True, exist_ok=False)
        manifest = dict(schema_version=SCHEMA, dataset=DATASET, run_id=run_id,
                        identity=identity, settings_digest=digest(settings), settings=deepcopy(settings),
                        samples=samples, seed=seed, created_at=now(), generation_rubrics=None,
                        grouping='unclassified')
        _atomic_json(path / 'manifest.json', manifest)
        return run_id, manifest

    @contextmanager
    def lease(self, run_id):
        path = self.run_path(run_id)
        with (path / '.lock').open('a') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('This sample run is already running') from exc
            try:
                yield path
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def save_state(self, run_id, state):
        _atomic_json(self.run_path(run_id) / 'run_state.json', state)

    def save_paper_foundation(self, run_id, state):
        path = self.run_path(run_id) / 'paper_foundation' / 'paper_state.json'
        fields = paper_fields(state)
        resources = {}
        for collection in ('images', 'tables'):
            for asset in (fields.get(collection) or {}).values():
                raw = asset.get('path')
                if raw:
                    resources[str(Path(raw).resolve())] = file_hash(raw)
        payload = dict(schema_version=SCHEMA, run_id=run_id, fields=fields, resource_hashes=resources)
        if path.exists():
            if read_json(path) != payload:
                raise ValueError('Paper foundation is immutable')
            self.paper_foundation(run_id)
            return
        _atomic_json(path, payload)
        _atomic_json(path.with_name('identity.json'), {'digest': digest(payload)})

    def paper_foundation(self, run_id):
        path = self.run_path(run_id) / 'paper_foundation' / 'paper_state.json'
        if not path.exists():
            return None
        payload = read_json(path)
        if (payload.get('schema_version') != SCHEMA or payload.get('run_id') != run_id or
                digest(payload) != read_json(path.with_name('identity.json'))['digest']):
            raise ValueError('Paper foundation digest mismatch')
        for raw, expected in payload['resource_hashes'].items():
            if file_hash(raw) != expected:
                raise ValueError('Scientific source resource changed')
        return deepcopy(payload['fields'])

    def paper_identity(self, run_id):
        self.paper_foundation(run_id)
        return read_json(self.run_path(run_id) / 'paper_foundation' / 'identity.json')['digest']

    def family_assignment(self, run_id, task, profile, counts, choose):
        path = self.sample_path(run_id, task['sample_id']) / 'family_assignment.json'
        identity = digest({'sample': task, 'profile': profile, 'counts': counts})
        if path.exists():
            envelope = read_json(path)
            payload = envelope['payload']
            if envelope['digest'] != digest(payload) or payload['input_digest'] != identity:
                raise ValueError('Frozen sample family assignment mismatch')
        else:
            sample = path.parent
            preparation = sample/'preparation'
            if (any(preparation.glob('stage_0[2-9].json')) or (preparation/'READY.json').exists() or
                    (preparation/'content/module_planning/identity.json').exists() or
                    (sample/'content_edit_budget.json').exists() or (sample/'attempts').exists()):
                raise ValueError('Frozen sample family assignment is missing from existing history')
            family, selection = choose()
            payload = {'input_digest': identity, 'run_id': run_id, 'task_digest': digest(task),
                       'family': family, 'selection': selection, 'counts': deepcopy(counts)}
            _atomic_json(path, {'payload': payload, 'digest': digest(payload)})
        return deepcopy(payload)

    def saved_assignment(self, run_id, task, counts):
        path = self.sample_path(run_id, task['sample_id']) / 'family_assignment.json'
        if not path.exists():
            return None
        envelope = read_json(path)
        payload = envelope['payload']
        if (envelope['digest'] != digest(payload) or payload.get('run_id') != run_id or
                payload.get('task_digest') != digest(task) or payload['counts'] != counts):
            raise ValueError('Saved family coverage assignment mismatch')
        return deepcopy(payload)

    def plan(self, run_id, build):
        path = self.run_path(run_id) / 'sample_plan.json'
        if path.exists():
            payload = read_json(path)
            if payload['digest'] != digest(payload['tasks']):
                raise ValueError('Sample plan digest mismatch')
            return payload['tasks']
        tasks = build()
        _atomic_json(path, {'tasks': tasks, 'digest': digest(tasks)})
        return tasks

    def sample_path(self, run_id, sample_id):
        return self.run_path(run_id) / 'samples' / safe_id(sample_id)

    def begin_attempt(self, run_id, sample_id):
        root = self.sample_path(run_id, sample_id) / 'attempts'
        root.mkdir(parents=True, exist_ok=True)
        previous = sorted(p for p in root.iterdir() if p.is_dir())
        for path in previous:
            status_file = path / 'status.json'
            if status_file.exists() and read_json(status_file).get('status') == 'running':
                _atomic_json(status_file, {'status': 'abandoned', 'reason': 'interrupted_process'})
        number = max([int(p.name.split('_')[-1]) for p in previous] or [0]) + 1
        path = root / f'attempt_{number:04d}'
        path.mkdir()
        _atomic_json(path / 'status.json', {'status': 'running', 'started_at': now()})
        return path

    def save_attempt(self, state, status, reason=None):
        path = Path(state['iteration_context']['attempt_diagnostics_dir'])
        if (state.get('render_fit_report') or {}).get('status') == 'failed':
            from src.workflow.generation_failure import retain_render_fit_preview
            retain_render_fit_preview(path, state)
        for key in DIAGNOSTIC_FIELDS:
            if state.get(key) is not None:
                _atomic_json(path / f'{key}.json', state[key])
        _atomic_json(path / 'status.json', {'status': status, 'reason': reason, 'updated_at': now()})

    def results(self, run_id):
        results = []
        root = self.run_path(run_id) / 'samples'
        for marker in sorted(root.glob('*/FINALIZED.json')):
            payload = read_json(marker)
            # Old samples remain inspectable, but open_run never resumes them.
            if payload.get('schema_version') not in {1, SCHEMA} or payload.get('run_id') != run_id:
                raise ValueError('Invalid sample finalization marker')
            record = payload['result']
            if digest(record) != payload['result_digest']:
                raise ValueError('Sample finalization digest mismatch')
            if record.get('poster_id'):
                self.verify_poster(record['poster_id'])
            results.append(record)
        return results

    def verify_poster(self, poster_id):
        directory = self.posters / safe_id(poster_id)
        if directory.is_symlink():
            raise ValueError('Poster directory must not be a symlink')
        payload = read_json(directory / 'bundle.json')
        for name, expected in payload['files'].items():
            if Path(name).name != name or file_hash(directory / name) != expected:
                raise ValueError('Saved poster bundle is missing or changed')
        return directory

    def publish_poster(self, state, result):
        """Publish every final rendered poster regardless of score or validity."""
        if state.get('draft_layout_mode'):
            raise ValueError('Cannot publish an unverified layout draft')
        if state.get('source_editorial_version') == 'source_editorial_v1':
            from src.workflow.source_verification import assert_compiled_text
            assert_compiled_text(state)
        poster_id = result['poster_id']
        final = self.posters / safe_id(poster_id)
        self.posters.mkdir(parents=True, exist_ok=True)
        if final.exists():
            self.verify_poster(poster_id)
            if read_json(final / 'provenance.json') != result:
                raise ValueError('Poster identity already belongs to another outcome')
            return final
        # A unique staging directory cannot expose an incomplete poster as a sample.
        staging = self.root / '.pending' / (poster_id + '_' + uuid.uuid4().hex[:8])
        staging.mkdir(parents=True, exist_ok=False)
        candidate = state['current_candidate']
        for kind in ('pptx', 'png'):
            shutil.copy2(candidate[f'{kind}_path'], staging / f'poster.{kind}')
        export_template(state, staging)
        _atomic_json(staging / 'evaluation.json', state.get('critic_report') or {
            'status': 'unavailable', 'overall_score': None, 'reason': result['status']})
        _atomic_json(staging / 'provenance.json', result)
        diagnostics = staging / 'diagnostics'
        diagnostics.mkdir()
        for key in DIAGNOSTIC_FIELDS:
            if state.get(key) is not None:
                _atomic_json(diagnostics / f'{key}.json', state[key])
        files = {p.name: file_hash(p) for p in staging.iterdir() if p.is_file()}
        _atomic_json(staging / 'bundle.json', {'schema_version': SCHEMA, 'files': files})
        os.replace(staging, final)
        return final

    def finalize(self, run_id, sample_id, result):
        path = self.sample_path(run_id, sample_id) / 'FINALIZED.json'
        payload = {'schema_version': SCHEMA, 'run_id': run_id, 'result': result,
                   'result_digest': digest(result)}
        if path.exists():
            if read_json(path) != payload:
                raise ValueError('A finalized sample is immutable')
        else:
            _atomic_json(path, payload)

    def recover_published(self, run_id):
        for pending in (self.run_path(run_id) / 'samples').glob('*/pending_result.json'):
            if (pending.parent / 'FINALIZED.json').exists():
                continue
            result = read_json(pending)
            if result.get('run_id') != run_id or result.get('sample_id') != pending.parent.name:
                raise ValueError('Pending sample identity mismatch')
            poster_id = result.get('poster_id')
            if poster_id:
                if (self.posters / safe_id(poster_id)).exists():
                    directory = self.verify_poster(poster_id)
                    if read_json(directory / 'provenance.json') != result:
                        raise ValueError('Published sample provenance mismatch')
                else:
                    snapshot = read_json(pending.parent / 'final_output_snapshot.json')
                    payload = snapshot['payload']
                    if digest(payload) != snapshot['digest']:
                        raise ValueError('Final sample output snapshot digest mismatch')
                    state = payload['state']
                    from src.workflow.generation_failure import require_rendered_candidate
                    candidate_dir = pending.parent / 'attempts' / safe_id(result['attempt_id']) / 'work'
                    require_rendered_candidate(state, result['candidate_id'], candidate_dir)
                    for kind, expected in payload['artifact_hashes'].items():
                        if file_hash(state['current_candidate'][f'{kind}_path']) != expected:
                            raise ValueError('Final sample artifacts changed before publication')
                    self.publish_poster(state, result)
            self.finalize(run_id, result['sample_id'], result)
