"""Seed-rubric collection boundaries and migration from existing paper folders."""
from pathlib import Path
import shutil

import pytest

from src.workflow.exploration_store import ExplorationStore
from utils.persistence import read_json
from test_poster_grouping import bundle, fingerprints
from test_poster_papers import paper_receipt


def old_paper_bundle(store, pid, score=80):
    old, result = bundle(store, pid, score, group='high_score')
    paper_receipt(store, result, 'Shared paper', 'a'*64)
    folder = 'Shared_paper--pdf_' + 'a'*64
    path = store.posters/'high_score'/folder/pid
    path.parent.mkdir(exist_ok=True)
    old.rename(path)
    store.finalize('run_test', pid, result)
    return path


def test_move_old_paper_folders_into_seed_collection_preserves_bytes(tmp_path):
    store = ExplorationStore(tmp_path)
    old = old_paper_bundle(store, 'a')
    before, runs = fingerprints(old), fingerprints(store.runs)
    plan = store.regroup_posters(dry_run=True)
    row = plan['posters'][0]
    assert row['poster_collection'] == 'seed posters'
    assert Path(row['destination']).relative_to(store.posters).parts[0] == 'seed posters'
    assert old.exists() and not (store.posters/'seed posters').exists()
    # Legacy URLs/read views still work before migration, without rewriting markers.
    assert store.results('run_test')[0]['poster_collection'] == 'seed posters'
    store.regroup_posters()
    new = store.verify_poster('a')
    assert new.relative_to(store.posters).parts[:2] == ('seed posters','high_score')
    assert fingerprints(new) == before and fingerprints(store.runs) == runs
    assert not (store.posters/'high_score').exists()
    assert not any(r['moved'] for r in store.regroup_posters()['posters'])


def test_future_round_collections_are_not_scanned_or_moved(tmp_path):
    store = ExplorationStore(tmp_path)
    old = old_paper_bundle(store, 'a')
    future = store.posters/'round_1'/'high_score'/old.parent.name/'a'
    shutil.copytree(old, future)
    before = fingerprints(store.posters/'round_1')
    plan = store.regroup_posters()
    assert len(plan['posters']) == 1
    assert fingerprints(store.posters/'round_1') == before
    assert store.verify_poster('a').is_relative_to(store.posters/'seed posters')


@pytest.mark.parametrize('fault', ['collection_symlink','duplicate'])
def test_seed_collection_rejects_symlink_or_duplicate_legacy_id(tmp_path, fault):
    store = ExplorationStore(tmp_path/'store')
    old = old_paper_bundle(store, 'a')
    if fault == 'collection_symlink':
        (store.posters/'seed posters').symlink_to(tmp_path, target_is_directory=True)
    else:
        new = store.posters/'seed posters'/'high_score'/old.parent.name/'a'
        shutil.copytree(old, new)
    with pytest.raises(ValueError):store.regroup_posters()
    assert old.exists()


def test_seed_migration_resumes_after_partial_move(tmp_path, monkeypatch):
    import src.workflow.exploration_store as module
    store = ExplorationStore(tmp_path)
    old_paper_bundle(store, 'a')
    b = old_paper_bundle(store, 'b', 20)
    replace = module.os.replace
    def fail_second(source, destination):
        if Path(source).name == 'b':raise OSError('migration interrupted')
        return replace(source, destination)
    monkeypatch.setattr(module.os, 'replace', fail_second)
    with pytest.raises(OSError,match='interrupted'):store.regroup_posters()
    assert store.verify_poster('a').is_relative_to(store.posters/'seed posters')
    assert store.verify_poster('b') == b
    monkeypatch.setattr(module.os, 'replace', replace)
    assert sum(r['moved'] for r in store.regroup_posters()['posters']) == 1
    assert not (store.posters/'high_score').exists()


def test_new_generation_records_seed_purpose_and_publishes_inside_collection(tmp_path):
    from test_exploration_samples import runner, scientific, critic_with_scores
    generator = runner(tmp_path, samples=1, critic=critic_with_scores([90]))
    result = generator.run(scientific(tmp_path),paper_ready=True)['run_state']['results'][0]
    store = generator.storage
    manifest = read_json(store.run_path(generator.run_id)/'manifest.json')
    assert manifest['poster_collection'] == 'seed posters'
    assert manifest['poster_collection_purpose'] == 'seed_rubrics'
    directory = store.verify_poster(result['poster_id'])
    assert directory.relative_to(store.posters).parts[0] == 'seed posters'
    assert read_json(directory/'provenance.json')['poster_collection'] == 'seed posters'
