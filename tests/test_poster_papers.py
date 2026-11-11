"""Paper membership, legacy bytes, safe nested lookup and independent repeated tasks."""
from pathlib import Path
import shutil

import pytest

from src.workflow.exploration_store import ExplorationStore
from src.workflow.poster_papers import paper_folder, folder_paper_id
from utils.persistence import _atomic_json, digest, file_hash, read_json
from test_poster_grouping import bundle, fingerprints


def paper_receipt(store, result, title, pdf_hash):
    payload = {'run_id': result['run_id'], 'task': {'sample_id': result['sample_id']},
               'identity': {'poster_name': title, 'inputs': {'pdf_path': pdf_hash}}}
    _atomic_json(store.sample_path(result['run_id'], result['sample_id']) / 'task_inputs.json',
                 {'payload': payload, 'digest': digest(payload)})


def test_old_bundles_group_by_pdf_bytes_across_names_runs_and_scores(tmp_path):
    store = ExplorationStore(tmp_path)
    originals = {}
    for pid, title, pdf_hash, score in [('a', 'First paper', 'a'*64, 90),
                                        ('b', 'Renamed copy', 'a'*64, 40),
                                        ('c', 'First paper', 'b'*64, 90)]:
        directory, result = bundle(store, pid, score, group='high_score')
        paper_receipt(store, result, title, pdf_hash)
        store.finalize('run_test', pid, result)
        originals[pid] = fingerprints(directory)
    runs = fingerprints(store.runs)
    plan = store.regroup_posters(dry_run=True)
    assert all(Path(row['source']).exists() and not Path(row['destination']).exists()
               for row in plan['posters'])
    store.regroup_posters()
    a, b, c = [store.verify_poster(pid) for pid in 'abc']
    assert a.parent.name == b.parent.name != c.parent.name
    assert a.parent.name == 'First paper'
    assert c.parent.name == 'First paper (2)'
    assert b.parent.parent.name == 'low_score'
    assert c.parent.parent.name == 'high_score'
    for pid in 'abc':
        assert fingerprints(store.verify_poster(pid)) == originals[pid]
    assert fingerprints(store.runs) == runs
    records = store.results('run_test')
    assert records[0]['paper_id'] == records[1]['paper_id'] != records[2]['paper_id']
    assert records[0]['paper_directory'] == records[1]['paper_directory']
    assert not any(row['moved'] for row in store.regroup_posters()['posters'])


def test_new_runs_reuse_paper_folder_despite_different_names_and_logos(tmp_path):
    from test_exploration_samples import runner, scientific, critic_with_scores
    first = runner(tmp_path, samples=1, critic=critic_with_scores([90]))
    a = first.run(scientific(tmp_path), paper_ready=True)['run_state']['results'][0]
    state = scientific(tmp_path)
    state['poster_name'] = 'A renamed PDF'
    logo = tmp_path / 'changed-logo.png'
    logo.write_bytes(b'different logo')
    state['logo_path'] = str(logo)
    second = runner(tmp_path, samples=1, critic=critic_with_scores([40]))
    b = second.run(state, paper_ready=True)['run_state']['results'][0]
    assert a['run_id'] != b['run_id']
    assert a['paper_id'] == b['paper_id'] == 'pdf_' + file_hash(tmp_path/'paper.pdf')
    assert a['paper_directory'] == b['paper_directory']
    assert a['grouping'] != b['grouping']
    # New bundles remain self-describing even when copied away from run receipts.
    standalone = ExplorationStore(tmp_path/'standalone')
    original = first.storage.verify_poster(a['poster_id'])
    shutil.copytree(original, standalone.posters/original.name)
    standalone.regroup_posters()
    assert standalone.verify_poster(a['poster_id']).parent.name == a['paper_directory']


def test_mixed_paper_batch_separates_same_titles(tmp_path):
    from test_full_paper_tasks import inputs, runner
    a, b = inputs(tmp_path, 'a'), inputs(tmp_path, 'b')
    a['poster_name'] = b['poster_name'] = 'Same title'
    gen = runner(tmp_path, [], input_states=[a,b])
    rows = gen.run(a)['run_state']['results']
    assert len({r['paper_id'] for r in rows}) == 2
    assert len({r['paper_directory'] for r in rows}) == 2
    assert all(gen.storage.verify_poster(r['poster_id']).parent.name == r['paper_directory'] for r in rows)


@pytest.mark.parametrize('title', ['../论文/../../名称\\测试', '💡'*300, 'a'*500, '论文'*200, 'CON', '...'])
def test_directory_labels_are_safe_and_bounded(title):
    paper = {'paper_id': 'pdf_'+'a'*64, 'paper_title': title}
    name = paper_folder(paper)
    assert Path(name).name == name and '/' not in name and '\\' not in name
    assert len(name.encode('utf-8')) <= 200
    assert folder_paper_id(name) is None


@pytest.mark.parametrize('fault', ['paper_symlink', 'nested_symlink', 'duplicate', 'wrong_paper'])
def test_nested_locations_reject_links_duplicates_and_wrong_membership(tmp_path, fault):
    store = ExplorationStore(tmp_path/'store')
    directory, result = bundle(store, 'a')
    paper_receipt(store, result, 'Paper', 'a'*64)
    store.regroup_posters()
    directory = store.verify_poster('a')
    if fault == 'paper_symlink':
        link = store.posters/'low_score'/directory.parent.name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(directory.parent, target_is_directory=True)
    elif fault == 'nested_symlink':
        shutil.move(directory, tmp_path/'outside')
        directory.symlink_to(tmp_path/'outside', target_is_directory=True)
    else:
        other = store.posters/'high_score'/paper_folder({'paper_id':'pdf_'+'b'*64,'paper_title':'Other'})/'a'
        other.parent.mkdir(parents=True, exist_ok=True)
        if fault == 'duplicate': shutil.copytree(directory, other)
        else: directory.rename(other)
    with pytest.raises(ValueError): store.verify_poster('a')


def test_tampered_receipt_aborts_all_moves(tmp_path):
    store = ExplorationStore(tmp_path)
    first, result = bundle(store, 'a')
    _, last = bundle(store, 'z')
    paper_receipt(store, result, 'Paper A', 'a'*64)
    paper_receipt(store, last, 'Paper Z', 'b'*64)
    receipt = store.sample_path('run_test', 'z')/'task_inputs.json'
    bad = read_json(receipt)
    bad['payload']['identity']['inputs']['pdf_path'] = 'c'*64
    _atomic_json(receipt, bad)
    with pytest.raises(ValueError, match='receipt mismatch'): store.regroup_posters()
    assert first.exists()


def test_missing_known_receipt_fails_and_unknown_legacy_stays_isolated(tmp_path):
    store = ExplorationStore(tmp_path)
    _, a = bundle(store, 'a')
    _, b = bundle(store, 'b')
    assert store.poster_paper(a)['paper_id'] != store.poster_paper(b)['paper_id']
    a['task_input_digest'] = 'a'*64
    with pytest.raises(ValueError, match='receipt is missing'): store.poster_paper(a)


def test_full_title_and_pdf_identity_are_separate(tmp_path):
    title = 'Win-Win: A Privacy-Preserving Federated Framework for Dual-Target Cross-Domain Recommendation'
    store = ExplorationStore(tmp_path)
    _, result = bundle(store, 'a')
    paper_receipt(store, result, title, 'a'*64)
    store.regroup_posters()
    path = store.verify_poster('a')
    assert path.parent.name == title
    assert read_json(path.parent/'.paper.json')['paper_id'] == 'pdf_'+'a'*64


@pytest.mark.parametrize('title', ['论文：What Works? — A 360° Study', 'A  B: C?', 'Model--pdf_'+'b'*64])
def test_spaces_punctuation_unicode_and_legacy_looking_titles(tmp_path, title):
    store = ExplorationStore(tmp_path)
    _, result = bundle(store, 'a')
    paper_receipt(store, result, title, 'a'*64)
    store.regroup_posters()
    assert store.verify_poster('a').parent.name == title


def test_collisions_across_groups_and_reserved_suffixes(tmp_path):
    store = ExplorationStore(tmp_path)
    for pid, title, score in [('a', 'Shared', 90), ('b', 'Shared', 40),
                              ('c', 'Shared (2)', 90), ('d', 'Shared', 40)]:
        _, result = bundle(store, pid, score)
        paper_receipt(store, result, title, pid*64)
    before = fingerprints(store.posters)
    plan = store.regroup_posters(dry_run=True)
    assert fingerprints(store.posters) == before
    assert [row['paper_directory'] for row in plan['posters']] == [
        'Shared', 'Shared (2)', 'Shared (2) (2)', 'Shared (3)']
    store.regroup_posters()
    assert [store.verify_poster(pid).parent.name for pid in 'abcd'] == [
        row['paper_directory'] for row in plan['posters']]


@pytest.mark.parametrize('fault', ['missing', 'symlink', 'wrong_pdf'])
def test_title_directory_requires_matching_identity_receipt(tmp_path, fault):
    store = ExplorationStore(tmp_path)
    _, result = bundle(store, 'a')
    paper_receipt(store, result, 'Title', 'a'*64)
    store.regroup_posters()
    path = store.verify_poster('a')
    receipt = path.parent/'.paper.json'
    if fault == 'missing':
        receipt.unlink()
    elif fault == 'symlink':
        copy = tmp_path/'receipt.json'
        receipt.rename(copy)
        receipt.symlink_to(copy)
    else:
        value = read_json(receipt)
        value['paper_id'] = 'pdf_'+'b'*64
        _atomic_json(receipt, value)
    with pytest.raises(ValueError):
        store.verify_poster('a')


def test_interrupted_publication_reserves_title_for_same_pdf(tmp_path):
    store = ExplorationStore(tmp_path)
    paper = {'paper_title': 'Shared', 'paper_id': 'pdf_'+'a'*64}
    with store._poster_lease():
        parent = store._ensure_paper_directory('high_score', store._paper_folder(paper), paper)
    assert list(parent.iterdir()) == [parent/'.paper.json']
    # Simulate restart after reservation but before a bundle is published.
    restarted = ExplorationStore(tmp_path)
    with restarted._poster_lease():
        assert restarted._paper_folder(paper) == 'Shared'
        assert restarted._paper_folder(dict(paper, paper_id='pdf_'+'b'*64)) == 'Shared (2)'


def test_receipt_failure_leaves_no_unidentified_title_directory(tmp_path, monkeypatch):
    import src.workflow.exploration_store as module
    store = ExplorationStore(tmp_path)
    paper = {'paper_title': 'Title', 'paper_id': 'pdf_'+'a'*64}
    original = module._atomic_json
    monkeypatch.setattr(module, '_atomic_json', lambda *args: (_ for _ in ()).throw(OSError('disk error')))
    with store._poster_lease(), pytest.raises(OSError, match='disk error'):
        store._ensure_paper_directory('high_score', 'Title', paper)
    monkeypatch.setattr(module, '_atomic_json', original)
    with store._poster_lease():
        assert store._paper_folder(paper) == 'Title'
        store._ensure_paper_directory('high_score', 'Title', paper)


@pytest.mark.parametrize('titles', [('A/B', 'A\\B'), ('论文'*150+'A', '论文'*150+'B')])
def test_sanitized_and_truncated_titles_cannot_merge_pdfs(tmp_path, titles):
    store = ExplorationStore(tmp_path)
    for pid, title in zip('ab', titles):
        _, result = bundle(store, pid)
        paper_receipt(store, result, title, pid*64)
    store.regroup_posters()
    a, b = (store.verify_poster(pid).parent.name for pid in 'ab')
    assert a != b and b.endswith(' (2)')
    assert max(len(name.encode('utf-8')) for name in (a, b)) <= 200
