"""One immutable total library; stage views never become independent rule copies."""
from copy import deepcopy
from pathlib import Path
import re

from utils.persistence import digest, read_json
from src.rubrics.storage import IntegrityError, WaitingForConfiguration, lock, read, immutable, write

SCHEMA_VERSION = 1
STAGES = {'parser', 'planning', 'writing', 'capacity', 'palette', 'review', 'revision'}
STAGE_BY_KIND = {'editorial_curator': 'planning', 'editorial_writer': 'writing',
    'editorial_balancer': 'capacity', 'editorial_palette': 'palette',
    'editorial_sections': 'parser', 'editorial_proofreading': 'parser',
    'editorial_metadata': 'parser', 'editorial_abt': 'parser', 'editorial_visuals': 'parser'}
RULE_FIELDS = {'id', 'revision', 'dimension', 'type', 'requirement', 'applicability',
               'criterion', 'revision_guidance', 'applicable_stages', 'evidence_refs'}
SEED_PATH = Path(__file__).resolve().parents[2] / 'config' / 'rubrics' / 'seed.json'


def validate_rule(rule):
    if not isinstance(rule, dict) or set(rule) != RULE_FIELDS:
        raise ValueError('Rule must contain exactly the documented rule fields')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', rule['id']):
        raise ValueError('Invalid stable rule ID')
    if type(rule['revision']) is not int or rule['revision'] < 1:
        raise ValueError('Invalid rule revision')
    if rule['type'] not in {'preference', 'rejection'}:
        raise ValueError('Unknown rule type')
    for key in ('dimension', 'requirement', 'applicability', 'criterion', 'revision_guidance'):
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
    if not isinstance(library, dict) or set(library) != fields or library['schema_version'] != SCHEMA_VERSION:
        raise ValueError('Unsupported generation Rubrics library schema')
    if library['status'] not in {'draft', 'published'} or not isinstance(library['rules'], list):
        raise ValueError('Invalid library status/rules')
    for rule in library['rules']:
        validate_rule(rule)
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


def guidance_block(library, stage):
    rules = rules_for(library, stage)
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
        return validate(read(self.root / 'versions' / version / 'library.json'), published=True)

    def publish(self, rules, *, parent_version, source_batch_digest):
        value = {'schema_version': SCHEMA_VERSION, 'version': '', 'parent_version': parent_version,
                 'status': 'published', 'rules': deepcopy(rules), 'source_batch_digest': source_batch_digest}
        value['version'] = digest({k: v for k, v in value.items() if k != 'version'})
        validate(value, published=True)
        with lock(self.root / '.publish.lock'):
            pointer = self.root / 'active.json'
            current = read(pointer)['version'] if pointer.exists() else None
            if current == value['version']:
                return self.version(current)
            if current != parent_version:
                raise IntegrityError('UPDATE_CONFLICT: active parent changed')
            if parent_version:
                previous = self.version(parent_version)
                if value['rules'][:len(previous['rules'])] != previous['rules']:
                    raise ValueError('Published rules cannot be deleted or rewritten by append-only updates')
            immutable(self.root / 'versions' / value['version'] / 'library.json', value)
            write(pointer, {'version': value['version']})
        return value
