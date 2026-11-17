"""Offline preparation: shared logos, numbered collections and immutable snapshots."""
import json
from pathlib import Path

import pytest
from PIL import Image

from src.rubrics import rounds
from src.rubrics.library import LibraryStore
from src.rubrics.storage import lock, read, write
from utils.persistence import _atomic_json, file_hash
from test_rubrics_framework import rule


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    import pymupdf
    from rubrics_poster import batch
    monkeypatch.setattr(batch, 'fingerprint', lambda: 'offline-assets')
    monkeypatch.setattr(rounds, 'check_glm_endpoints', lambda: None)
    folder = tmp_path/'papers'
    folder.mkdir()
    for i in range(20):
        path = folder/f'Paper {i}'
        path.mkdir()
        with pymupdf.open() as doc:
            doc.new_page().insert_text((30, 30), str(i))
            doc.save(path/'paper.pdf')
    logos = tmp_path/'shared logos'
    logos.mkdir()
    for name, color in [('logo.png', 'red'), ('aff.png', 'blue')]:
        Image.new('RGB', (8, 6), color).save(logos/name)
    # A paper-local logo must not override an explicitly selected shared one.
    Image.new('RGB', (8, 6), 'green').save(folder/'Paper 0'/'logo.png')
    storage = tmp_path/'storage'
    LibraryStore(storage/'rubrics').publish([rule()], parent_version=None, source_batch_digest='offline')
    return folder, logos, storage


def test_cli_shared_logos_numbering_and_snapshot_isolation(prepared, monkeypatch, capsys):
    from rubrics_poster.iteration import main
    folder, logos, storage = prepared
    def forbidden(*args, **kwargs):
        pytest.fail('Preparing a round must not start workers')
    monkeypatch.setattr(rounds.subprocess, 'Popen', forbidden)
    assert main(['--storage-root', str(storage), 'create', '--input-folder', str(folder),
                 '--logo-folder', str(logos), '--round-number', '1', '--generate-only']) == 0
    root = Path(json.loads(capsys.readouterr().out)['round'])
    manifest = read(root/'manifest.json')
    expected = {name: file_hash(logos/name) for name in ('logo.png', 'aff.png')}
    assert manifest['round_number'] == 1
    assert manifest['poster_output'] == str(storage/'posters'/'posters round1')
    assert manifest['logo_folder'] == str(logos)
    assert len(manifest['papers']) == 20
    for paper in manifest['papers']:
        assert paper['logos'] == expected
        for name, identity in expected.items():
            assert file_hash(Path(paper['paper_path']).parent/name) == identity
    assert not (folder/'Paper 1'/'logo.png').exists()
    Image.new('RGB', (8, 6), 'black').save(logos/'logo.png')
    assert file_hash(Path(manifest['papers'][0]['paper_path']).parent/'logo.png') == expected['logo.png']
    state = read(root/'state.json')
    assert state['status'] == 'PLANNED' and state['attempts'] == []
    assert not (root/'jobs').exists()
    spec = rounds._spec(root, manifest, {'paper_index': 0, 'seed': 17, 'family_counts': {}, 'family': 'fixture'}, 'GPU-OFFLINE')
    assert spec['logos'] == expected and spec['poster_output'] == manifest['poster_output']
    second = rounds.create(folder, storage, generate_only=True)
    assert read(second/'manifest.json')['round_number'] == 2
    assert read(second/'manifest.json')['poster_output'] == str(storage/'posters'/'posters round2')
    assert read(root/'state.json') == state


def test_number_collisions_and_creation_lock(prepared):
    folder, logos, storage = prepared
    first = rounds.create(folder, storage, generate_only=True, round_number=7)
    output = read(first/'manifest.json')['poster_output']
    with pytest.raises(ValueError, match='already has a plan'):
        rounds.create(folder, storage, generate_only=True, round_number=7)
    with pytest.raises(ValueError, match='already belongs'):
        rounds.create(folder, storage, generate_only=True, poster_output=output)
    with lock(storage/'iterations/.create.lock'):
        with pytest.raises(RuntimeError, match='Another operation'):
            rounds.create(folder, storage, generate_only=True)
    assert len(list((storage/'iterations').glob('round_*/manifest.json'))) == 1
    second = rounds.create(folder, storage, generate_only=True)
    assert read(second/'manifest.json')['round_number'] == 8


@pytest.mark.parametrize('number', [0, -1, True, 1.5])
def test_invalid_round_numbers(tmp_path, number):
    with pytest.raises(ValueError, match='positive integer'):
        rounds._numbered_output(tmp_path, number, None)


def test_legacy_names_existing_outputs_and_symlinks(tmp_path):
    write(tmp_path/'iterations/round_legacy/manifest.json',
          {'poster_output': str(tmp_path/'posters'/'posters round3')})
    assert rounds._numbered_output(tmp_path, None, None)[0] == 4
    target = tmp_path/'posters'/'posters round5'
    target.mkdir(parents=True)
    (target/'poster.png').write_bytes(b'historical')
    assert rounds._numbered_output(tmp_path, None, None)[0] == 6
    with pytest.raises(ValueError, match='empty directory'):
        rounds._numbered_output(tmp_path, 5, None)
    link = tmp_path/'alias'
    link.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        rounds._numbered_output(tmp_path, 6, link)


@pytest.mark.parametrize('corrupt', [False, True])
def test_shared_logos_require_both_readable_images(prepared, corrupt):
    folder, logos, storage = prepared
    if corrupt:
        (logos/'aff.png').write_bytes(b'not an image')
    else:
        (logos/'aff.png').unlink()
    with pytest.raises(OSError):
        rounds.create(folder, storage, logo_folder=logos, generate_only=True)
    assert not list((storage/'iterations').glob('round_*'))


def test_worker_rejects_tampered_frozen_logo_before_loading_models(prepared, monkeypatch, tmp_path):
    import sys
    from rubrics_poster import batch_worker
    folder, logos, storage = prepared
    root = rounds.create(folder, storage, logo_folder=logos, generate_only=True)
    manifest = read(root/'manifest.json')
    spec = rounds._spec(root, manifest, {'paper_index': 0, 'seed': 17, 'family_counts': {}, 'family': 'fixture'}, 'GPU-OFFLINE')
    (Path(spec['paper_path']).parent/'aff.png').write_bytes(b'changed')
    job = tmp_path/'job'
    job.mkdir()
    _atomic_json(job/'task.json', spec)
    monkeypatch.setattr(sys, 'argv', ['batch_worker', str(job)])
    with pytest.raises(ValueError, match='Logo changed'):
        batch_worker.main()
