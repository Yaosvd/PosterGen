"""Offline publication, recovery and integrity checks for human library names."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import os
import threading

import pytest

from src.rubrics import library as library_module
from src.rubrics.library import LibraryStore, validate
from src.rubrics.storage import IntegrityError, read, write
from utils.persistence import digest


def rule(name):
    return {
        'id': name, 'revision': 1, 'dimension': 'readability',
        'type': 'preference', 'requirement': 'Keep necessary text readable',
        'applicability': 'Text modules', 'criterion': 'Required text is readable',
        'applicable_stages': ['writing', 'review'], 'evidence_refs': [],
    }


def published(rules, parent=None, source='fixture'):
    """Produce a current-schema receipt without the optional named views."""
    value = {
        'schema_version': 2, 'version': '', 'parent_version': parent,
        'status': 'published', 'rules': deepcopy(rules),
        'source_batch_digest': source,
    }
    value['version'] = digest({k: v for k, v in value.items() if k != 'version'})
    return validate(value, published=True)


def hash_only_chain(root):
    seed = published([rule('seed')], source='old-seed')
    first = published(seed['rules'] + [rule('old_update')], seed['version'], 'old-round')
    for value in (seed, first):
        write(root / 'versions' / value['version'] / 'library.json', value)
    write(root / 'active.json', {'version': first['version']})
    return seed, first


def assert_alias(root, name, value):
    alias = root / name
    canonical = root / 'versions' / value['version'] / 'library.json'
    assert alias.is_symlink()
    assert alias.readlink() == Path('versions') / value['version']
    assert not alias.readlink().is_absolute()
    assert (alias / 'library.json').samefile(canonical)
    assert read(alias / 'library.json') == value


def test_names_follow_parent_chain_and_each_version_contains_all_rules(tmp_path):
    store = LibraryStore(tmp_path)
    expected_fields = {
        'schema_version', 'version', 'parent_version', 'status', 'rules',
        'source_batch_digest',
    }
    versions = []
    canonical_bytes = {}
    parent = None
    for index in range(4):
        rules = [rule(f'rule_{i}') for i in range(index + 1)]
        value = store.publish(rules, parent_version=parent, source_batch_digest=f'round-{index}')
        name = 'seed rubrics' if index == 0 else f'rubrics_v{index}'
        assert set(value) == expected_fields
        assert value['rules'] == rules
        assert value['version'] == published(rules, parent, f'round-{index}')['version']
        assert store.name(value['version']) == name
        assert read(tmp_path / 'active.json') == {'version': value['version'], 'name': name}
        assert store.active(required=True) == value
        assert_alias(tmp_path, name, value)
        for previous, previous_bytes in canonical_bytes.items():
            assert (tmp_path / 'versions' / previous / 'library.json').read_bytes() == previous_bytes
        canonical_bytes[value['version']] = (tmp_path / 'versions' / value['version'] / 'library.json').read_bytes()
        versions.append(value)
        parent = value['version']
    assert [len(store.version(v['version'])['rules']) for v in versions] == [1, 2, 3, 4]
    assert len(list((tmp_path / 'versions').glob('*/library.json'))) == 4


def test_stale_cas_and_rewritten_prefix_leave_names_and_active_unchanged(tmp_path):
    store = LibraryStore(tmp_path)
    seed = store.publish([rule('seed')], parent_version=None, source_batch_digest='seed')
    first = store.publish(seed['rules'] + [rule('added')], parent_version=seed['version'], source_batch_digest='first')
    pointer_before = (tmp_path / 'active.json').read_bytes()
    versions_before = set((tmp_path / 'versions').iterdir())
    with pytest.raises(IntegrityError, match='UPDATE_CONFLICT'):
        store.publish(seed['rules'] + [rule('stale')], parent_version=seed['version'], source_batch_digest='stale')
    with pytest.raises(ValueError, match='append-only'):
        store.publish([rule('replacement')], parent_version=first['version'], source_batch_digest='rewrite')
    assert (tmp_path / 'active.json').read_bytes() == pointer_before
    assert set((tmp_path / 'versions').iterdir()) == versions_before
    assert not os.path.lexists(tmp_path / 'rubrics_v2')
    assert_alias(tmp_path, 'seed rubrics', seed)
    assert_alias(tmp_path, 'rubrics_v1', first)


def test_concurrent_different_updates_have_one_winner_and_no_number_gap(tmp_path):
    store = LibraryStore(tmp_path)
    seed = store.publish([rule('seed')], parent_version=None, source_batch_digest='seed')
    barrier = threading.Barrier(2)

    def attempt(index):
        barrier.wait(timeout=10)
        try:
            return LibraryStore(tmp_path).publish(
                seed['rules'] + [rule(f'branch_{index}')],
                parent_version=seed['version'], source_batch_digest=f'branch-{index}')
        except IntegrityError as exc:
            assert 'UPDATE_CONFLICT' in str(exc)
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    winners = [value for value in outcomes if value is not None]
    assert len(winners) == 1
    winner = winners[0]
    assert store.active(required=True) == winner
    assert_alias(tmp_path, 'rubrics_v1', winner)
    assert len(list((tmp_path / 'versions').iterdir())) == 2
    next_value = store.publish(winner['rules'] + [rule('after_race')], parent_version=winner['version'], source_batch_digest='next')
    assert_alias(tmp_path, 'rubrics_v2', next_value)
    assert store.name(next_value['version']) == 'rubrics_v2'


def test_concurrent_identical_publications_share_one_name(tmp_path):
    barrier = threading.Barrier(4)

    def attempt(_):
        barrier.wait(timeout=10)
        return LibraryStore(tmp_path).publish([rule('seed')], parent_version=None, source_batch_digest='same')

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(attempt, range(4)))
    assert all(value == values[0] for value in values)
    assert_alias(tmp_path, 'seed rubrics', values[0])
    assert len(list((tmp_path / 'versions').iterdir())) == 1
    assert not os.path.lexists(tmp_path / 'rubrics_v1')


def test_hash_only_history_reads_and_next_publication_backfills_names(tmp_path):
    seed, first = hash_only_chain(tmp_path)
    store = LibraryStore(tmp_path)
    old_bytes = {v['version']: (tmp_path / 'versions' / v['version'] / 'library.json').read_bytes() for v in (seed, first)}
    assert store.active(required=True) == first
    assert store.version(seed['version']) == seed
    assert store.name(seed['version']) == 'seed rubrics'
    assert store.name(first['version']) == 'rubrics_v1'
    second = store.publish(first['rules'] + [rule('new')], parent_version=first['version'], source_batch_digest='new-round')
    for name, value in [('seed rubrics', seed), ('rubrics_v1', first), ('rubrics_v2', second)]:
        assert_alias(tmp_path, name, value)
    assert read(tmp_path / 'active.json') == {'version': second['version'], 'name': 'rubrics_v2'}
    for version, original in old_bytes.items():
        assert (tmp_path / 'versions' / version / 'library.json').read_bytes() == original


def test_republishing_unnamed_active_value_repairs_all_names_without_new_version(tmp_path):
    seed, first = hash_only_chain(tmp_path)
    store = LibraryStore(tmp_path)
    assert store.publish(first['rules'], parent_version=seed['version'], source_batch_digest=first['source_batch_digest']) == first
    assert_alias(tmp_path, 'seed rubrics', seed)
    assert_alias(tmp_path, 'rubrics_v1', first)
    assert read(tmp_path / 'active.json') == {'version': first['version'], 'name': 'rubrics_v1'}
    assert len(list((tmp_path / 'versions').iterdir())) == 2


@pytest.mark.parametrize('existing_seed', [False, True])
def test_same_value_retry_recovers_symlink_failure_after_active_commit(tmp_path, monkeypatch, existing_seed):
    store = LibraryStore(tmp_path)
    parent = store.publish([rule('seed')], parent_version=None, source_batch_digest='seed') if existing_seed else None
    rules = (parent['rules'] if parent else []) + [rule('new')]
    parent_version = parent['version'] if parent else None
    expected = published(rules, parent_version, 'attempt')
    name = 'rubrics_v1' if parent else 'seed rubrics'
    original_symlink = os.symlink
    observed_commits = []

    def fail_new_alias(source, destination, *args, **kwargs):
        if Path(source) == Path('versions') / expected['version']:
            observed_commits.append(read(tmp_path / 'active.json'))
            assert observed_commits[-1] == {'version': expected['version'], 'name': name}
            raise OSError('simulated alias creation failure')
        return original_symlink(source, destination, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, 'symlink', fail_new_alias)
        with pytest.raises(IntegrityError, match='is committed; named views incomplete') as error:
            store.publish(rules, parent_version=parent_version, source_batch_digest='attempt')
        assert expected['version'] in str(error.value)
        assert 'retry the identical publication' in str(error.value)
        assert 'simulated alias creation failure' in str(error.value)
        assert isinstance(error.value.__cause__, OSError)
    assert len(observed_commits) == 1
    assert store.active(required=True) == expected
    assert not os.path.lexists(tmp_path / name)
    canonical = tmp_path / 'versions' / expected['version'] / 'library.json'
    committed_bytes = canonical.read_bytes()
    assert store.publish(rules, parent_version=parent_version, source_batch_digest='attempt') == expected
    assert canonical.read_bytes() == committed_bytes
    assert_alias(tmp_path, name, expected)
    assert len(list((tmp_path / 'versions').iterdir())) == (2 if existing_seed else 1)
    if parent:
        assert_alias(tmp_path, 'seed rubrics', parent)


@pytest.mark.parametrize('conflict_kind', ['directory', 'file', 'wrong_link', 'dangling_link', 'absolute_link'])
def test_initial_name_conflicts_never_overwrite_existing_paths(tmp_path, conflict_kind):
    store = LibraryStore(tmp_path)
    rules = [rule('seed')]
    expected = published(rules, source='seed')
    alias = tmp_path / 'seed rubrics'
    if conflict_kind == 'directory':
        alias.mkdir()
        (alias / 'keep.txt').write_text('user content')
    elif conflict_kind == 'file':
        alias.write_text('user content')
    elif conflict_kind == 'wrong_link':
        target = tmp_path / 'versions' / ('f' * 64)
        target.mkdir(parents=True)
        (target / 'keep.txt').write_text('other version')
        alias.symlink_to(Path('versions') / ('f' * 64), target_is_directory=True)
    elif conflict_kind == 'dangling_link':
        alias.symlink_to(Path('versions') / ('e' * 64), target_is_directory=True)
    else:
        alias.symlink_to(tmp_path / 'versions' / expected['version'], target_is_directory=True)
    old_link = alias.readlink() if alias.is_symlink() else None
    with pytest.raises(IntegrityError, match='Library name conflict'):
        store.publish(rules, parent_version=None, source_batch_digest='seed')
    assert not (tmp_path / 'active.json').exists()
    assert not (tmp_path / 'versions' / expected['version'] / 'library.json').exists()
    if old_link is not None:
        assert alias.is_symlink() and alias.readlink() == old_link
    elif conflict_kind == 'directory':
        assert (alias / 'keep.txt').read_text() == 'user content'
    else:
        assert alias.read_text() == 'user content'


@pytest.mark.parametrize('blocked_name', ['seed rubrics', 'rubrics_v1', 'rubrics_v2'])
def test_all_hash_only_chain_name_conflicts_are_checked_before_new_commit(tmp_path, blocked_name):
    seed, first = hash_only_chain(tmp_path)
    store = LibraryStore(tmp_path)
    blocker = tmp_path / blocked_name
    blocker.mkdir()
    (blocker / 'keep.txt').write_text('do not replace')
    pointer_before = (tmp_path / 'active.json').read_bytes()
    expected = published(first['rules'] + [rule('new')], first['version'], 'new')
    with pytest.raises(IntegrityError, match='Library name conflict'):
        store.publish(expected['rules'], parent_version=first['version'], source_batch_digest='new')
    assert (tmp_path / 'active.json').read_bytes() == pointer_before
    assert not (tmp_path / 'versions' / expected['version']).exists()
    assert (blocker / 'keep.txt').read_text() == 'do not replace'
    for name in {'seed rubrics', 'rubrics_v1', 'rubrics_v2'} - {blocked_name}:
        assert not os.path.lexists(tmp_path / name)
    assert store.version(seed['version']) == seed


@pytest.mark.parametrize('reader', ['version', 'name', 'active'])
def test_requested_hash_must_match_valid_library_stored_in_that_directory(tmp_path, reader):
    value = published([rule('seed')])
    wrong_hash = 'a' * 64
    assert value['version'] != wrong_hash
    write(tmp_path / 'versions' / wrong_hash / 'library.json', value)
    store = LibraryStore(tmp_path)
    if reader == 'active':
        write(tmp_path / 'active.json', {'version': wrong_hash, 'name': 'seed rubrics'})
    with pytest.raises(IntegrityError, match='requested version'):
        store.active(required=True) if reader == 'active' else getattr(store, reader)(wrong_hash)
    assert not os.path.lexists(tmp_path / 'seed rubrics')


def test_orphan_hash_versions_do_not_allocate_or_skip_human_names(tmp_path):
    orphan_seed = published([rule('unpublished_seed')], source='orphan-seed')
    write(tmp_path / 'versions' / orphan_seed['version'] / 'library.json', orphan_seed)
    store = LibraryStore(tmp_path)
    seed = store.publish([rule('seed')], parent_version=None, source_batch_digest='actual-seed')
    orphan_update = published(seed['rules'] + [rule('orphan_update')], seed['version'], 'orphan-round')
    write(tmp_path / 'versions' / orphan_update['version'] / 'library.json', orphan_update)
    first = store.publish(seed['rules'] + [rule('actual_update')], parent_version=seed['version'], source_batch_digest='actual-round')
    assert store.name(seed['version']) == 'seed rubrics'
    assert store.name(first['version']) == 'rubrics_v1'
    assert_alias(tmp_path, 'seed rubrics', seed)
    assert_alias(tmp_path, 'rubrics_v1', first)
    assert not os.path.lexists(tmp_path / 'rubrics_v2')
    assert store.version(orphan_seed['version']) == orphan_seed
    assert store.version(orphan_update['version']) == orphan_update
    assert len(list((tmp_path / 'versions').iterdir())) == 4


def test_wrong_link_inserted_after_preflight_is_preserved_and_reported_as_committed(tmp_path, monkeypatch):
    store = LibraryStore(tmp_path)
    seed = store.publish([rule('seed')], parent_version=None, source_batch_digest='seed')
    rules = seed['rules'] + [rule('new')]
    expected = published(rules, seed['version'], 'round')
    original_immutable = library_module.immutable
    alias = tmp_path / 'rubrics_v1'
    wrong_target = Path('versions') / ('f' * 64)
    injected = []

    def insert_external_link(path, value):
        original_immutable(path, value)
        if value['version'] == expected['version']:
            assert not os.path.lexists(alias)
            alias.symlink_to(wrong_target, target_is_directory=True)
            injected.append(str(alias))

    with monkeypatch.context() as patch:
        patch.setattr(library_module, 'immutable', insert_external_link)
        with pytest.raises(IntegrityError, match='is committed; named views incomplete') as error:
            store.publish(rules, parent_version=seed['version'], source_batch_digest='round')
    assert injected == [str(alias)]
    assert expected['version'] in str(error.value)
    assert 'retry the identical publication' in str(error.value)
    assert 'Library name conflict' in str(error.value)
    assert isinstance(error.value.__cause__, IntegrityError)
    assert alias.is_symlink() and alias.readlink() == wrong_target
    assert store.active(required=True) == expected
    assert read(tmp_path / 'active.json') == {'version': expected['version'], 'name': 'rubrics_v1'}
    assert_alias(tmp_path, 'seed rubrics', seed)
    # Resolving the external collision permits an identical retry, not a new number.
    alias.unlink()
    assert store.publish(rules, parent_version=seed['version'], source_batch_digest='round') == expected
    assert_alias(tmp_path, 'rubrics_v1', expected)
    assert len(list((tmp_path / 'versions').iterdir())) == 2
    assert not os.path.lexists(tmp_path / 'rubrics_v2')


@pytest.mark.parametrize('next_candidate', ['identical', 'different'])
def test_active_write_failure_leaves_orphan_without_allocating_name(tmp_path, monkeypatch, next_candidate):
    store = LibraryStore(tmp_path)
    seed = store.publish([rule('seed')], parent_version=None, source_batch_digest='seed')
    rules = seed['rules'] + [rule('pending')]
    pending = published(rules, seed['version'], 'pending')
    canonical = tmp_path / 'versions' / pending['version'] / 'library.json'
    pointer_before = (tmp_path / 'active.json').read_bytes()
    original_write = library_module.write
    attempted_commits = []

    def fail_active_write(path, value):
        if Path(path) == tmp_path / 'active.json':
            assert read(canonical) == pending
            attempted_commits.append(value)
            raise OSError('simulated active pointer write failure')
        return original_write(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(library_module, 'write', fail_active_write)
        with pytest.raises(OSError, match='simulated active pointer write failure'):
            store.publish(rules, parent_version=seed['version'], source_batch_digest='pending')
    assert attempted_commits == [{'version': pending['version'], 'name': 'rubrics_v1'}]
    assert (tmp_path / 'active.json').read_bytes() == pointer_before
    assert store.active(required=True) == seed
    assert store.version(pending['version']) == pending
    assert not os.path.lexists(tmp_path / 'rubrics_v1')
    assert_alias(tmp_path, 'seed rubrics', seed)
    orphan_bytes = canonical.read_bytes()
    if next_candidate == 'identical':
        first = store.publish(rules, parent_version=seed['version'], source_batch_digest='pending')
        assert first == pending
    else:
        first = store.publish(seed['rules'] + [rule('replacement')], parent_version=seed['version'], source_batch_digest='replacement')
        assert first['version'] != pending['version']
    assert canonical.read_bytes() == orphan_bytes
    assert store.name(first['version']) == 'rubrics_v1'
    assert_alias(tmp_path, 'rubrics_v1', first)
    assert read(tmp_path / 'active.json') == {'version': first['version'], 'name': 'rubrics_v1'}
    assert len(list((tmp_path / 'versions').iterdir())) == (2 if next_candidate == 'identical' else 3)
    assert not os.path.lexists(tmp_path / 'rubrics_v2')
