"""Nine-field rules and the narrow, recoverable Seed schema migration."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import hashlib
import os
import threading

import pytest

from src.rubrics import library as library_module
from src.rubrics.library import LibraryStore, RULE_FIELDS, model_rules_for, validate, validate_rule
from src.rubrics.storage import IntegrityError, read, write
from utils.persistence import digest


def rule(identifier='seed_04', *, legacy=False):
    value = {'id': identifier, 'revision': 1, 'dimension': 'Contribution support',
             'type': 'preference', 'requirement': 'Support the main contribution with evidence',
             'applicability': 'Research posters', 'criterion': 'Representative evidence is visible',
             'applicable_stages': ['planning', 'writing'], 'evidence_refs': ['OBS-1']}
    if legacy:
        value['revision_guidance'] = 'Writer must retain the planned module purpose'
    return value


def snapshot(rules, *, schema_version=1, parent=None, source='original-evidence'):
    value = {'schema_version': schema_version, 'version': '', 'parent_version': parent,
             'status': 'published', 'rules': deepcopy(rules), 'source_batch_digest': source}
    value['version'] = digest({key: val for key, val in value.items() if key != 'version'})
    return validate(value, published=True)


def historical_seed(root):
    previous = snapshot([rule(legacy=True), rule('seed_05', legacy=True)])
    directory = root / 'versions' / previous['version']
    write(directory / 'library.json', previous)
    (directory / 'evidence.json').write_bytes(b'{"OBS-1": "source evidence"}\n')
    write(root / 'active.json', {'version': previous['version'], 'name': 'seed rubrics'})
    (root / 'seed rubrics').symlink_to(Path('versions') / previous['version'], target_is_directory=True)
    return previous


def expected_migration(previous):
    rules = [{key: val for key, val in item.items() if key != 'revision_guidance'}
             for item in previous['rules']]
    return snapshot(rules, schema_version=2, source=previous['source_batch_digest'])


def test_new_rules_reject_retired_field_while_legacy_snapshots_validate():
    current = rule()
    assert len(RULE_FIELDS) == 9
    assert validate_rule(current) == current
    with pytest.raises(ValueError, match='documented rule fields'):
        validate_rule(rule(legacy=True))
    with pytest.raises(ValueError, match='documented rule fields'):
        validate_rule(current, schema_version=1)
    legacy = snapshot([rule(legacy=True)])
    assert validate(legacy, published=True) == legacy
    invalid = deepcopy(legacy)
    invalid['schema_version'] = 2
    with pytest.raises(ValueError, match='documented rule fields'):
        validate(invalid)


@pytest.mark.parametrize('stage', ['planning', 'writing', 'review', 'revision'])
def test_legacy_model_views_cannot_reintroduce_retired_guidance(stage):
    previous = snapshot([rule(legacy=True)])
    before = deepcopy(previous)
    view = model_rules_for(previous, stage)
    assert view == [{key: val for key, val in previous['rules'][0].items()
                     if key not in {'evidence_refs', 'revision_guidance'}}]
    view[0]['applicable_stages'].append('capacity')
    assert previous == before


def test_seed_migration_keeps_name_evidence_other_fields_and_first_update_number(tmp_path):
    previous = historical_seed(tmp_path)
    store = LibraryStore(tmp_path)
    old_path = tmp_path / 'versions' / previous['version']
    originals = {p.name: p.read_bytes() for p in old_path.iterdir()}
    migrated = store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
    assert migrated == expected_migration(previous)
    assert migrated['parent_version'] is None
    assert store.active(required=True) == migrated
    assert store.name(migrated['version']) == 'seed rubrics'
    assert store.name(previous['version']) == 'seed rubrics'  # Historical logical name.
    assert (tmp_path / 'seed rubrics').readlink() == Path('versions') / migrated['version']
    assert read(tmp_path / 'seed rubrics' / 'library.json') == migrated
    assert (tmp_path / 'seed rubrics' / 'evidence.json').read_bytes() == originals['evidence.json']
    assert not os.path.lexists(tmp_path / 'rubrics_v1')
    assert store.version(previous['version']) == previous
    assert {p.name: p.read_bytes() for p in old_path.iterdir()} == originals
    receipt = read(tmp_path / 'migrations' / 'remove_seed_revision_guidance.json')
    assert receipt['source_version'] == previous['version']
    assert receipt['target_version'] == migrated['version']
    assert receipt['evidence_sha256'] == hashlib.sha256(originals['evidence.json']).hexdigest()
    assert store.migrate_seed_without_revision_guidance(expected_version=previous['version']) == migrated
    assert len(list((tmp_path / 'versions').iterdir())) == 2
    first = store.publish(migrated['rules'] + [rule('round_1')],
                          parent_version=migrated['version'], source_batch_digest='round-1')
    assert store.name(first['version']) == 'rubrics_v1'
    assert first['rules'][:len(migrated['rules'])] == migrated['rules']
    assert (tmp_path / 'rubrics_v1').readlink() == Path('versions') / first['version']
    with pytest.raises(ValueError, match='append-only'):
        store.publish([rule('replacement')], parent_version=first['version'], source_batch_digest='rewrite')
    with pytest.raises(IntegrityError, match='UPDATE_CONFLICT'):
        store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
    assert store.active(required=True) == first


def test_legacy_parent_cannot_accept_new_rules_without_explicit_migration(tmp_path):
    previous = historical_seed(tmp_path)
    with pytest.raises(ValueError, match='read-only'):
        LibraryStore(tmp_path).publish([rule(), rule('new')], parent_version=previous['version'],
                                       source_batch_digest='attempt')
    assert LibraryStore(tmp_path).active(required=True) == previous
    assert len(list((tmp_path / 'versions').iterdir())) == 1


@pytest.mark.parametrize('failure_point', ['active', 'alias'])
def test_interrupted_seed_migration_retries_without_new_version_or_evidence_loss(tmp_path, monkeypatch, failure_point):
    previous = historical_seed(tmp_path)
    expected = expected_migration(previous)
    store = LibraryStore(tmp_path)
    real_write, real_replace = library_module.write, os.replace

    def fail_active(path, value):
        if Path(path) == tmp_path / 'active.json':
            raise OSError('simulated active failure')
        return real_write(path, value)

    def fail_alias(source, destination):
        if Path(destination) == tmp_path / 'seed rubrics':
            raise OSError('simulated alias failure')
        return real_replace(source, destination)

    with monkeypatch.context() as patch:
        if failure_point == 'active':
            patch.setattr(library_module, 'write', fail_active)
            with pytest.raises(OSError, match='simulated active failure'):
                store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
        else:
            patch.setattr(os, 'replace', fail_alias)
            with pytest.raises(IntegrityError, match='is committed; named view incomplete'):
                store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
    assert store.active(required=True) == (previous if failure_point == 'active' else expected)
    assert (tmp_path / 'seed rubrics').readlink() == Path('versions') / previous['version']
    assert not list(tmp_path.glob('.seed-rubrics-*'))
    assert store.migrate_seed_without_revision_guidance(expected_version=previous['version']) == expected
    assert (tmp_path / 'seed rubrics').readlink() == Path('versions') / expected['version']
    assert (tmp_path / 'seed rubrics' / 'evidence.json').read_bytes() == (
        tmp_path / 'versions' / previous['version'] / 'evidence.json').read_bytes()
    assert len(list((tmp_path / 'versions').iterdir())) == 2
    assert not os.path.lexists(tmp_path / 'rubrics_v1')


@pytest.mark.parametrize('collision', ['file', 'directory', 'wrong_link', 'absolute_link', 'evolved_name'])
def test_seed_migration_preserves_conflicting_user_paths(tmp_path, collision):
    previous = historical_seed(tmp_path)
    alias = tmp_path / 'seed rubrics'
    if collision == 'evolved_name':
        (tmp_path / 'rubrics_v1').symlink_to('missing-version')
    else:
        alias.unlink()
        if collision == 'file':
            alias.write_text('user data')
        elif collision == 'directory':
            alias.mkdir()
            (alias / 'keep').write_text('user data')
        elif collision == 'wrong_link':
            alias.symlink_to('not-our-library')
        else:
            alias.symlink_to(tmp_path / 'versions' / previous['version'])
    before = (tmp_path / 'active.json').read_bytes()
    with pytest.raises(IntegrityError, match='conflict|evolved named'):
        LibraryStore(tmp_path).migrate_seed_without_revision_guidance(expected_version=previous['version'])
    assert (tmp_path / 'active.json').read_bytes() == before
    assert len(list((tmp_path / 'versions').iterdir())) == 1
    assert not (tmp_path / 'migrations').exists()
    if collision == 'file':
        assert alias.read_text() == 'user data'
    elif collision == 'directory':
        assert (alias / 'keep').read_text() == 'user data'
    elif collision == 'wrong_link':
        assert alias.readlink() == Path('not-our-library')
    elif collision == 'absolute_link':
        assert alias.readlink().is_absolute()
    else:
        assert (tmp_path / 'rubrics_v1').readlink() == Path('missing-version')


def test_seed_migration_rejects_missing_or_changed_evidence(tmp_path):
    previous = historical_seed(tmp_path)
    store = LibraryStore(tmp_path)
    evidence = tmp_path / 'versions' / previous['version'] / 'evidence.json'
    original = evidence.read_bytes()
    evidence.unlink()
    with pytest.raises(IntegrityError, match='requires its original evidence'):
        store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
    evidence.write_bytes(original)
    migrated = store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
    evidence.write_bytes(b'changed historical evidence')
    with pytest.raises(IntegrityError, match='different Seed migration'):
        store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
    assert (tmp_path / 'versions' / migrated['version'] / 'evidence.json').read_bytes() == original


def test_seed_migration_cannot_replace_nonseed_history_or_changed_active(tmp_path):
    previous = historical_seed(tmp_path)
    evolved = snapshot(previous['rules'] + [rule('later', legacy=True)], parent=previous['version'])
    write(tmp_path / 'versions' / evolved['version'] / 'library.json', evolved)
    write(tmp_path / 'active.json', {'version': evolved['version'], 'name': 'rubrics_v1'})
    store = LibraryStore(tmp_path)
    with pytest.raises(ValueError, match='Only an original'):
        store.migrate_seed_without_revision_guidance(expected_version=evolved['version'])
    with pytest.raises(IntegrityError, match='UPDATE_CONFLICT'):
        store.migrate_seed_without_revision_guidance(expected_version=previous['version'])
    assert store.active(required=True) == evolved
    assert len(list((tmp_path / 'versions').iterdir())) == 2


def test_concurrent_identical_seed_migrations_share_the_same_root(tmp_path):
    previous = historical_seed(tmp_path)
    barrier = threading.Barrier(3)

    def migrate(_):
        barrier.wait(timeout=10)
        return LibraryStore(tmp_path).migrate_seed_without_revision_guidance(expected_version=previous['version'])

    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = list(pool.map(migrate, range(3)))
    assert all(value == expected_migration(previous) for value in outcomes)
    assert len(list((tmp_path / 'versions').iterdir())) == 2
    assert not os.path.lexists(tmp_path / 'rubrics_v1')
