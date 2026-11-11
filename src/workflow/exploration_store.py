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

from src.workflow.editorial_contract import SAMPLE_KEYS as EDITORIAL_FIELDS
from src.workflow.poster_grouping import GROUPS, grouping_policy, poster_group
from src.workflow.poster_papers import VERSION as PAPER_GROUPING_VERSION, folder_paper_id, paper_folder, validate_paper

SCHEMA = 2
DATASET = 'rubrics_samples_v2'
DIAGNOSTIC_FIELDS = (
    'task_input_digest', 'story_board', 'optimized_story_board', 'layout_spec', 'styled_layout',
    'layout_feasibility_report', 'layout_preflight_report', 'render_fit_report',
    'capacity_repair_report', 'layout_performance_report', 'attempt_failure_report',
    'final_column_analysis', 'layout_family_analysis', 'section_fit_analysis',
    'content_selection', 'verified_content_bank', 'supplemental_evidence_bank',
    'visual_curation_report', 'color_scheme', 'color_provenance', 'keywords',
    *SCIENCE_FIELDS, *EDITORIAL_FIELDS, 'editorial_factual_status', '_editorial_content_evaluation', 'module_provenance', 'paper_foundation_digest', 'sample_science_digest',
    '_editorial_visual_evaluation', 'critic_measurement_evidence', 'critic_request_identities',
    'curation_report', 'render_history', 'derived_candidate',
)


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Invalid run or sample identity')
    return value


class ExplorationStore:
    # Initial collection used to summarize seed rubrics. Later rounds are siblings,
    # not additional score groups or papers in this collection.
    poster_collection = 'seed posters'

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
                        grouping=grouping_policy(), paper_grouping=PAPER_GROUPING_VERSION,
                        poster_collection=self.poster_collection,
                        poster_collection_purpose='seed_rubrics')
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

    def paper_path(self, run_id, sample_id=None):
        parent = self.run_path(run_id) if sample_id is None else self.sample_path(run_id, sample_id)
        return parent / 'paper_foundation'

    def save_paper_foundation(self, run_id, state, sample_id=None):
        path = self.paper_path(run_id, sample_id) / 'paper_state.json'
        fields = paper_fields(state)
        resources = {}
        for collection in ('images', 'tables'):
            for asset in (fields.get(collection) or {}).values():
                raw = asset.get('path')
                if raw:
                    resources[str(Path(raw).resolve())] = file_hash(raw)
        payload = dict(schema_version=SCHEMA, run_id=run_id, fields=fields, resource_hashes=resources)
        if sample_id is not None:
            payload['sample_id'] = safe_id(sample_id)
        if path.exists():
            if read_json(path) != payload:
                raise ValueError('Paper foundation is immutable')
            self.paper_foundation(run_id, sample_id)
            return
        _atomic_json(path, payload)
        _atomic_json(path.with_name('identity.json'), {'digest': digest(payload)})

    def paper_foundation(self, run_id, sample_id=None):
        path = self.paper_path(run_id, sample_id) / 'paper_state.json'
        if not path.exists():
            if path.with_name('identity.json').exists():
                raise ValueError('Paper foundation state missing from existing history')
            return None
        payload = read_json(path)
        if (payload.get('schema_version') != SCHEMA or payload.get('run_id') != run_id or
                payload.get('sample_id') != sample_id or digest(payload) != read_json(path.with_name('identity.json'))['digest']):
            raise ValueError('Paper foundation digest mismatch')
        for raw, expected in payload['resource_hashes'].items():
            if file_hash(raw) != expected:
                raise ValueError('Scientific source resource changed')
        return deepcopy(payload['fields'])

    def paper_identity(self, run_id, sample_id=None):
        self.paper_foundation(run_id, sample_id)
        return read_json(self.paper_path(run_id, sample_id) / 'identity.json')['digest']

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
                directory = self.verify_poster(record['poster_id'])
                # A read view may classify old immutable records without rewriting them.
                paper = self.poster_paper(record)
                with self._poster_lease():
                    folder = self._paper_folder(paper)
                record = dict(record, **paper, paper_directory=folder,
                              poster_collection=self.poster_collection,
                              grouping=poster_group(record, read_json(directory / 'evaluation.json')))
            results.append(record)
        return results

    @contextmanager
    def _poster_lease(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / '.poster_storage.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def poster_paper(self, result):
        """Resolve immutable paper metadata, including for old published bundles.

        Use the task's frozen PDF hash without reloading/re-extracting the PDF.
        Truly old bundles with no input evidence stay isolated, never guessed by title.
        """
        if 'paper_id' in result:
            return validate_paper(result)
        receipt = self.sample_path(result['run_id'], result['sample_id']) / 'task_inputs.json'
        if receipt.exists():
            envelope = read_json(receipt)
            payload = envelope['payload']
            if (envelope.get('digest') != digest(payload)
                    or (result.get('task_input_digest') and result['task_input_digest'] != envelope['digest'])
                    or payload.get('run_id') != result['run_id']
                    or payload.get('task', {}).get('sample_id') != result['sample_id']):
                raise ValueError('Poster paper input receipt mismatch')
            identity = payload['identity']
            return validate_paper({'paper_id': 'pdf_' + str(identity['inputs']['pdf_path']),
                                   'paper_title': identity.get('poster_name') or 'Paper'})
        if result.get('task_input_digest'):
            raise ValueError('Poster paper input receipt is missing')
        return {'paper_id': 'unknown_' + digest({'poster_id': safe_id(result['poster_id'])}),
                'paper_title': 'Unknown paper'}

    def _poster_parent(self, group=None, paper=None, *, legacy=False):
        if group is not None and group not in GROUPS:
            raise ValueError('Unknown poster score group')
        root = self.posters if legacy else self.posters / self.poster_collection
        path = root if group is None else root / group
        if self.posters.is_symlink() or root.is_symlink() or path.is_symlink():
            raise ValueError('Poster storage directories must not be symlinks')
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('Poster path escapes the sample store')
        if paper is not None:
            if group is None:
                raise ValueError('A paper directory requires a score group')
            folder_paper_id(paper)
            path = path / paper
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise ValueError('Paper directory must not be a symlink or escape storage')
        return path

    def _poster_parents(self):
        # Only the initial collection and its known old locations are in scope.
        # Never recursively sweep future iteration directories into seed posters.
        return [self._poster_parent(group, legacy=legacy)
                for legacy in (True, False) for group in (None, *GROUPS)]

    def _paper_directories(self):
        for legacy in (True, False):
            for group in GROUPS:
                parent = self._poster_parent(group, legacy=legacy)
                if parent.exists():
                    for path in sorted(parent.iterdir()):
                        if path.is_symlink():
                            raise ValueError('Poster or paper directory must not be a symlink')
                        if path.is_dir() and not (path / 'bundle.json').exists():
                            yield self._poster_parent(group, path.name, legacy=legacy)

    def _paper_folder(self, paper):
        names = {path.name for path in self._paper_directories()
                 if folder_paper_id(path.name) == paper['paper_id']}
        if len(names) > 1:
            raise ValueError('Paper identity exists in multiple paper directories')
        return next(iter(names)) if names else paper_folder(paper)

    def _find_poster(self, poster_id):
        safe_id(poster_id)
        found = []
        parents = self._poster_parents()
        parents.extend(self._paper_directories())
        for parent in parents:
            path = parent / poster_id
            if path.is_symlink():
                raise ValueError('Poster directory must not be a symlink')
            if path.exists():
                found.append(path)
        if len(found) > 1:
            raise ValueError('Poster identity exists in multiple storage groups')
        return found[0] if found else None

    def _verify_poster_directory(self, directory):
        payload = read_json(directory / 'bundle.json')
        for name, expected in payload['files'].items():
            if (Path(name).name != name or (directory / name).is_symlink()
                    or file_hash(directory / name) != expected):
                raise ValueError('Saved poster bundle is missing or changed')
        return directory

    def verify_poster(self, poster_id):
        with self._poster_lease():
            directory = self._find_poster(poster_id)
            if directory is None:
                raise FileNotFoundError(f'Saved poster not found: {poster_id}')
            self._verify_poster_directory(directory)
            if directory.parent.parent.name in GROUPS:
                paper = self.poster_paper(read_json(directory / 'provenance.json'))
                if folder_paper_id(directory.parent.name) != paper['paper_id']:
                    raise ValueError('Poster is stored under another paper')
            return directory

    def regroup_posters(self, *, dry_run=False):
        """Move whole verified bundles; leave all historical bytes/receipts intact.

        Preflight every bundle before moving any. Each rename is atomic; rerunning
        after interruption continues from the already moved, uniquely located bundles.
        """
        with self._poster_lease():
            ids = set()
            paper_dirs = list(self._paper_directories())
            parents = self._poster_parents() + paper_dirs
            roots = {self.posters, self._poster_parent()}
            for parent in parents:
                if parent.exists():
                    ids.update(p.name for p in parent.iterdir()
                               if (parent not in roots or p.name not in (*GROUPS, self.poster_collection))
                               and (parent != self.posters or p.is_symlink() or (p / 'bundle.json').exists())
                               and p not in paper_dirs
                               and (p.is_dir() or p.is_symlink()))
            plan = []
            folders = {}
            for poster_id in sorted(ids):
                directory = self._verify_poster_directory(self._find_poster(poster_id))
                result = read_json(directory / 'provenance.json')
                if result.get('poster_id') != poster_id:
                    raise ValueError('Saved poster provenance identity mismatch')
                group = poster_group(result, read_json(directory / 'evaluation.json'))
                paper = self.poster_paper(result)
                folder = folders.setdefault(paper['paper_id'], self._paper_folder(paper))
                destination = self._poster_parent(group, folder) / poster_id
                if destination != directory and (destination.exists() or destination.is_symlink()):
                    raise ValueError('Refusing to replace an existing poster bundle')
                plan.append({'poster_id': poster_id, 'grouping': group, **paper, 'paper_directory': folder,
                             'poster_collection': self.poster_collection,
                             'source': str(directory), 'destination': str(destination),
                             'moved': directory != destination})
            if not dry_run:
                for row in plan:
                    if row['moved']:
                        destination = Path(row['destination'])
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if destination.exists():
                            raise ValueError('Refusing to replace an existing poster bundle')
                        os.replace(row['source'], destination)
                # Remove only the now-empty old score/paper containers. Never
                # remove unrelated files or sibling iteration collections.
                old_parents = [p for p in paper_dirs if p.parent.parent == self.posters]
                old_parents.extend(self._poster_parent(group, legacy=True) for group in GROUPS)
                for path in old_parents:
                    if path.exists() and not any(path.iterdir()):
                        path.rmdir()
            return {'policy': grouping_policy(), 'paper_grouping': PAPER_GROUPING_VERSION,
                    'poster_collection': self.poster_collection,
                    'dry_run': dry_run, 'posters': plan,
                    'counts': {group: sum(row['grouping'] == group for row in plan) for group in GROUPS}}

    def publish_poster(self, state, result):
        """Publish every final rendered poster regardless of score or validity."""
        if state.get('draft_layout_mode'):
            raise ValueError('Cannot publish an unverified layout draft')
        if state.get('source_editorial_version') == 'source_editorial_v1':
            from src.workflow.source_verification import assert_compiled_text
            assert_compiled_text(state)
        if state.get('editorial_version') == 'poster_editorial_v1':
            from src.workflow.editorial_contract import assert_editorial_ready
            assert_editorial_ready(state, compiled=True)
        poster_id = result['poster_id']
        group = poster_group(result, state.get('critic_report') or {})
        safe_id(poster_id)
        paper = self.poster_paper(result)
        with self._poster_lease():
            existing = self._find_poster(poster_id)
            if existing is not None:
                self._verify_poster_directory(existing)
                if read_json(existing / 'provenance.json') != result:
                    raise ValueError('Poster identity already belongs to another outcome')
                return existing
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
        with self._poster_lease():
            existing = self._find_poster(poster_id)
            if existing is not None:
                self._verify_poster_directory(existing)
                if read_json(existing / 'provenance.json') != result:
                    raise ValueError('Poster identity already belongs to another outcome')
                shutil.rmtree(staging)
                return existing
            parent = self._poster_parent(group, self._paper_folder(paper))
            final = parent / poster_id
            parent.mkdir(parents=True, exist_ok=True)
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
                if self._find_poster(poster_id) is not None:
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
