"""One immutable total library; stage views never become independent rule copies."""
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote
import hashlib
import os
import re
import tempfile
import uuid

from utils.persistence import digest, read_json
from src.rubrics.storage import IntegrityError, WaitingForConfiguration, lock, read, immutable, text_file, write

SCHEMA_VERSION = 2
HISTORY_DIR = 'versions history'
NAMES_DIR = 'rubrics versions'
LEGACY_SCHEMA_VERSION = 1
STAGES = {'parser', 'planning', 'writing', 'capacity', 'palette', 'review', 'revision'}
STAGE_BY_KIND = {'editorial_curator': 'planning', 'editorial_writer': 'writing',
    'editorial_balancer': 'capacity', 'editorial_palette': 'palette',
    'editorial_sections': 'parser', 'editorial_proofreading': 'parser',
    'editorial_metadata': 'parser', 'editorial_abt': 'parser', 'editorial_visuals': 'parser'}
RULE_FIELDS = {'id', 'revision', 'dimension', 'type', 'requirement', 'applicability',
               'criterion', 'applicable_stages', 'evidence_refs'}
LEGACY_RULE_FIELDS = RULE_FIELDS | {'revision_guidance'}
SEED_PATH = Path(__file__).resolve().parents[2] / 'config' / 'rubrics' / 'seed.json'


def validate_rule(rule, *, schema_version=SCHEMA_VERSION):
    if schema_version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise ValueError('Unsupported generation Rubrics rule schema')
    fields = LEGACY_RULE_FIELDS if schema_version == LEGACY_SCHEMA_VERSION else RULE_FIELDS
    if not isinstance(rule, dict) or set(rule) != fields:
        raise ValueError('Rule must contain exactly the documented rule fields')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', rule['id']):
        raise ValueError('Invalid stable rule ID')
    if type(rule['revision']) is not int or rule['revision'] < 1:
        raise ValueError('Invalid rule revision')
    if rule['type'] not in {'preference', 'rejection'}:
        raise ValueError('Unknown rule type')
    text_fields = ('dimension', 'requirement', 'applicability', 'criterion')
    if schema_version == LEGACY_SCHEMA_VERSION:
        text_fields += ('revision_guidance',)
    for key in text_fields:
        if not isinstance(rule[key], str) or not rule[key].strip():
            raise ValueError(f'Rule {key} must be nonempty text')
    stages = rule['applicable_stages']
    if not isinstance(stages, list) or not stages or len(set(stages)) != len(stages) or not set(stages) <= STAGES:
        raise ValueError('Invalid applicable stages')
    if not isinstance(rule['evidence_refs'], list) or any(not isinstance(x, str) or not x for x in rule['evidence_refs']):
        raise ValueError('Invalid rule evidence references')
    digest(rule)
    return rule


def validate(library, *, published=False):
    fields = {'schema_version', 'version', 'parent_version', 'status', 'rules', 'source_batch_digest'}
    if (not isinstance(library, dict) or set(library) != fields or
            type(library['schema_version']) is not int or
            library['schema_version'] not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}):
        raise ValueError('Unsupported generation Rubrics library schema')
    if library['status'] not in {'draft', 'published'} or not isinstance(library['rules'], list):
        raise ValueError('Invalid library status/rules')
    for rule in library['rules']:
        validate_rule(rule, schema_version=library['schema_version'])
    ids = [r['id'] for r in library['rules']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate rule IDs')
    if published or library['status'] == 'published':
        if library['status'] != 'published' or not ids:
            raise WaitingForConfiguration('WAITING_SEED: publish a nonempty validated Seed library first')
        expected = digest({k: v for k, v in library.items() if k != 'version'})
        if library['version'] != expected:
            raise IntegrityError('Published rule version does not match its contents')
    return library


def rules_for(library, stage):
    validate(library)
    if stage not in STAGES:
        raise ValueError('Unknown Rubrics stage')
    # Critic and Actor see the full current guidance and judge applicability.
    return deepcopy([r for r in library['rules'] if stage in {'review', 'revision'} or stage in r['applicable_stages']])


def model_rules_for(library, stage):
    """Model view: omit provenance and retired guidance, including old snapshots."""
    rules = rules_for(library, stage)
    for rule in rules:
        del rule['evidence_refs']
        rule.pop('revision_guidance', None)
    return rules


def guidance_block(library, stage):
    rules = model_rules_for(library, stage)
    if not rules:
        return ''
    import json
    return '\n\n<GENERATION_RUBRICS>\n' + json.dumps(
        {'version': library['version'], 'stage': stage,
         'contract':'Supplement existing instructions. Preserve paper facts, output contracts and execution permissions. Report conflicts; do not silently override those constraints.',
         'rules': rules},
        ensure_ascii=False, allow_nan=False) + '\n</GENERATION_RUBRICS>'


def append_guidance(prompt, state, kind):
    stage = STAGE_BY_KIND.get(kind)
    library = state.get('generation_rubrics_snapshot')
    if not stage or not library:
        return prompt
    return prompt + guidance_block(library, stage)


class LibraryStore:
    def __init__(self, root):
        self.root = Path(root)
        self.names_dir = self.root / NAMES_DIR

    @property
    def history_dir(self):
        """Use the old location for reads until its atomic directory rename."""
        legacy = self.root / 'versions'
        return legacy if legacy.is_dir() else self.root / HISTORY_DIR

    def organize_versions(self):
        """Move an existing library without publishing or changing its active version."""
        with lock(self.root / '.publish.lock'):
            self._organize_versions()

    def _organize_versions(self):
        legacy = self.root / 'versions'
        history = self.root / HISTORY_DIR
        if self.names_dir.is_symlink() or history.is_symlink() or legacy.is_symlink():
            raise IntegrityError('Library directory conflict')
        self.names_dir.mkdir(exist_ok=True)
        # A retry after the archive rename may still find old root-level links.
        old_names = [p for p in self.root.iterdir()
                     if p.name == 'seed rubrics' or re.fullmatch(r'rubrics_v[0-9]+', p.name)]
        if not legacy.exists() and not old_names:
            return
        if legacy.exists() and (not legacy.is_dir() or history.exists()):
            raise IntegrityError('Library history directory conflict')

        links = []
        for old in old_names:
            if not old.is_symlink():
                raise IntegrityError(f'Library name conflict: {old}')
            original = old.readlink()
            if original != Path('versions') / original.name or self.name(original.name) != old.name:
                raise IntegrityError(f'Library name conflict: {old}')
            path = self.names_dir / old.name
            target = Path('..') / HISTORY_DIR / original.name
            if os.path.lexists(path) and not (path.is_symlink() and path.readlink() == target):
                raise IntegrityError(f'Library name conflict: {path}')
            links.append((old, path, target))

        for _, path, target in links:
            if not path.is_symlink():
                path.symlink_to(target, target_is_directory=True)
        if legacy.is_dir():
            # Only the navigation URLs in generated review documents refer to the archive.
            for review in (self.root / 'candidates').glob('*/review.md'):
                content = review.read_bytes().decode('utf-8')
                updated = re.sub(r'(库内规则 \[[^\]\n]+\]\()\.\./\.\./versions/([0-9a-f]{64}/library\.json\))',
                                 rf'\g<1>../../{quote(HISTORY_DIR)}/\2', content)
                if updated != content:
                    text_file(review, updated)
            legacy.rename(history)
        for old, _, _ in links:
            old.unlink()

    def active(self, *, required=False):
        pointer = self.root / 'active.json'
        if not pointer.exists():
            library = read_json(SEED_PATH)
        else:
            version = read(pointer)['version']
            library = self.version(version)
        return deepcopy(validate(library, published=required))

    def version(self, version):
        if not isinstance(version, str) or not re.fullmatch('[0-9a-f]{64}', version):
            raise IntegrityError('Invalid library version path')
        relative = Path(version) / 'library.json'
        archive = self.history_dir
        try:
            receipt = read(archive / relative)
        except FileNotFoundError:
            if archive == self.history_dir:
                raise
            receipt = read(self.history_dir / relative)
        library = validate(receipt, published=True)
        if library['version'] != version:
            raise IntegrityError('Library contents do not match the requested version')
        return library

    def _history(self, library):
        history, seen = [], set()
        while True:
            if library['version'] in seen:
                raise IntegrityError('Cycle in library parent history')
            seen.add(library['version'])
            history.append(library)
            if library['parent_version'] is None:
                return list(reversed(history))
            library = self.version(library['parent_version'])

    @staticmethod
    def _name(index):
        return 'seed rubrics' if index == 0 else f'rubrics_v{index}'

    def name(self, version):
        """Historical logical name; a migrated Seed alias resolves to its current hash."""
        return self._name(len(self._history(self.version(version))) - 1)

    def _named_paths(self, history):
        paths = []
        for index, library in enumerate(history):
            path = self.names_dir / self._name(index)
            target = Path('..') / HISTORY_DIR / library['version']
            # exists() alone misses dangling links. Never replace user files or
            # accept an absolute/external link, even if it resolves to a library.
            if path.is_symlink():
                if path.readlink() != target:
                    raise IntegrityError(f'Library name conflict: {path}')
            elif path.exists():
                raise IntegrityError(f'Library name conflict: {path}')
            paths.append((path, target))
        return paths

    def publish(self, rules, *, parent_version, source_batch_digest):
        value = {'schema_version': SCHEMA_VERSION, 'version': '', 'parent_version': parent_version,
                 'status': 'published', 'rules': deepcopy(rules), 'source_batch_digest': source_batch_digest}
        value['version'] = digest({k: v for k, v in value.items() if k != 'version'})
        validate(value, published=True)
        with lock(self.root / '.publish.lock'):
            self._organize_versions()
            pointer = self.root / 'active.json'
            current = read(pointer)['version'] if pointer.exists() else None
            if current == value['version']:
                value = self.version(current)
            elif current != parent_version:
                raise IntegrityError('UPDATE_CONFLICT: active parent changed')
            elif parent_version:
                previous = self.version(parent_version)
                if previous['schema_version'] != SCHEMA_VERSION:
                    raise ValueError('Legacy rule libraries are read-only; migrate the Seed first')
                if value['rules'][:len(previous['rules'])] != previous['rules']:
                    raise ValueError('Published rules cannot be deleted or rewritten by append-only updates')
            history = self._history(value)
            paths = self._named_paths(history)
            immutable(self.root / HISTORY_DIR / value['version'] / 'library.json', value)
            write(pointer, {'version': value['version'], 'name': self._name(len(history) - 1)})
            # Names expose the committed history, never pending orphan versions.
            # A retry repairs missing links after a crash here; readers continue
            # loading the checksum-bound hash path throughout that window.
            try:
                for path, target in paths:
                    try:
                        path.symlink_to(target, target_is_directory=True)
                    except FileExistsError:
                        if not path.is_symlink() or path.readlink() != target:
                            raise IntegrityError(f'Library name conflict: {path}')
            except (OSError, IntegrityError) as exc:
                raise IntegrityError(
                    f'Library {value["version"]} is committed; named views incomplete; '
                    f'retry the identical publication: {exc}') from exc
        return value


    def migrate_seed_without_revision_guidance(self, *, expected_version):
        """Apply only the authorized schema-1 Seed field deletion, preserving its name.

        This is not a rule-edit or append operation. The old content-addressed root
        remains readable; the migration receipt links it to a new schema-2 root so
        the first real rule addition is still rubrics_v1. Retry with the same old
        expected_version to repair an interrupted named-view switch.
        """
        with lock(self.root / '.publish.lock'):
            self._organize_versions()
            previous = self.version(expected_version)
            if previous['schema_version'] != LEGACY_SCHEMA_VERSION or previous['parent_version'] is not None:
                raise ValueError('Only an original schema-1 Seed can use this migration')
            value = deepcopy(previous)
            value['schema_version'] = SCHEMA_VERSION
            for rule in value['rules']:
                del rule['revision_guidance']
            value['version'] = digest({k: v for k, v in value.items() if k != 'version'})
            validate(value, published=True)
            pointer = self.root / 'active.json'
            current = read(pointer)['version'] if pointer.exists() else None
            if current not in {expected_version, value['version']}:
                raise IntegrityError('UPDATE_CONFLICT: active Seed changed or has evolved')
            if any(self.names_dir.glob('rubrics_v*')):
                raise IntegrityError('Seed migration cannot replace an evolved named library')

            alias = self.names_dir / 'seed rubrics'
            old_target = Path('..') / HISTORY_DIR / expected_version
            new_target = Path('..') / HISTORY_DIR / value['version']

            def check_alias():
                if alias.is_symlink():
                    if alias.readlink() not in {old_target, new_target}:
                        raise IntegrityError(f'Library name conflict: {alias}')
                elif alias.exists():
                    raise IntegrityError(f'Library name conflict: {alias}')

            check_alias()
            evidence_source = self.root / HISTORY_DIR / expected_version / 'evidence.json'
            if evidence_source.is_symlink() or not evidence_source.is_file():
                raise IntegrityError('Seed migration requires its original evidence.json file')
            evidence = evidence_source.read_bytes()
            destination = self.root / HISTORY_DIR / value['version']
            evidence_target = destination / 'evidence.json'
            migration = {
                'operation': 'remove_seed_revision_guidance',
                'source_version': expected_version, 'target_version': value['version'],
                'source_schema_version': LEGACY_SCHEMA_VERSION, 'target_schema_version': SCHEMA_VERSION,
                'rule_count': len(value['rules']),
                'evidence_sha256': hashlib.sha256(evidence).hexdigest(),
            }
            migration_path = self.root / 'migrations' / 'remove_seed_revision_guidance.json'
            if migration_path.exists() and read(migration_path) != migration:
                raise IntegrityError('A different Seed migration is already recorded')
            if evidence_target.is_symlink() or (evidence_target.exists() and
                    (not evidence_target.is_file() or evidence_target.read_bytes() != evidence)):
                raise IntegrityError('Migrated Seed evidence differs from the original')
            immutable(destination / 'library.json', value)
            if not evidence_target.exists():
                fd, temporary = tempfile.mkstemp(dir=destination, prefix='.evidence.')
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(evidence)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, evidence_target)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            immutable(migration_path, migration)
            check_alias()
            write(pointer, {'version': value['version'], 'name': 'seed rubrics'})
            temporary_alias = self.names_dir / ('.seed-rubrics-' + uuid.uuid4().hex)
            try:
                check_alias()
                if not alias.is_symlink() or alias.readlink() != new_target:
                    temporary_alias.symlink_to(new_target, target_is_directory=True)
                    check_alias()
                    os.replace(temporary_alias, alias)
            except (OSError, IntegrityError) as exc:
                raise IntegrityError(
                    f'Seed migration {value["version"]} is committed; named view incomplete; '
                    f'retry migration with the identical expected_version: {exc}') from exc
            finally:
                if temporary_alias.is_symlink():
                    temporary_alias.unlink()
            return value
