"""CPU-only resource/process tests; no live model or Marker loading."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from rubrics_poster import batch
from utils.concurrency import WorkStopped, slot
from utils.persistence import _atomic_json, read_json, file_hash

ROOT = Path(__file__).resolve().parents[1]


def policy(tmp_path, monkeypatch, count=2):
    path = tmp_path / 'policy.json'
    _atomic_json(path, {'root': str(tmp_path / 'locks'), 'limits': {'marker': 1, 'model': count, 'render': 2}})
    monkeypatch.setenv('RUBRICS_RESOURCE_POLICY', str(path))
    monkeypatch.delenv('RUBRICS_STOP_FILE', raising=False)
    return path


def test_real_process_slots_never_exceed_limit_and_release_on_kill(tmp_path, monkeypatch):
    policy(tmp_path, monkeypatch)
    script = '''import sys,time
from pathlib import Path
from utils.concurrency import slot
with slot('model'):
 p=Path(sys.argv[1]);p.write_text('admitted')
 time.sleep(60)
'''
    children = [subprocess.Popen([sys.executable, '-c', script, str(tmp_path / str(i))], cwd=ROOT) for i in range(3)]
    try:
        deadline = time.monotonic()+10
        while sum((tmp_path / str(i)).exists() for i in range(3)) < 2 and time.monotonic()<deadline:
            time.sleep(.05)
        admitted = [i for i in range(3) if (tmp_path / str(i)).exists()]
        assert len(admitted) == 2
        time.sleep(.3)
        assert sum((tmp_path / str(i)).exists() for i in range(3)) == 2
        children[admitted[0]].kill(); children[admitted[0]].wait()
        deadline = time.monotonic()+5
        while sum((tmp_path / str(i)).exists() for i in range(3)) < 3 and time.monotonic()<deadline:
            time.sleep(.05)
        assert all((tmp_path / str(i)).exists() for i in range(3))
    finally:
        for child in children:
            if child.poll() is None: child.kill()
            child.wait()


def test_stop_does_not_take_slot_or_spend_model_call(tmp_path, monkeypatch):
    policy(tmp_path, monkeypatch, 1)
    stop = tmp_path / 'STOP'; stop.touch()
    monkeypatch.setenv('RUBRICS_STOP_FILE', str(stop))
    with pytest.raises(WorkStopped):
        with slot('model'): pytest.fail('must not be admitted')


def test_model_queue_events_and_actual_call_timing(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from utils.model_requests import invoke
    policy(tmp_path, monkeypatch, 1)
    calls = []
    model = SimpleNamespace(invoke=lambda messages: calls.append(messages) or SimpleNamespace(response_metadata={}, usage_metadata={}))
    agent = SimpleNamespace(request_policy={'max_transient_retries': 0, 'response_timeout_seconds': 900},
                            state={'output_dir': str(tmp_path)}, agent_name='writer')
    invoke(agent, model, [])
    rows = [json.loads(s) for s in (tmp_path/'model_requests.jsonl').read_text().splitlines()]
    assert [r['event'] for r in rows] == ['request_queued', 'request_admitted', 'request_start', 'request_finished']
    assert rows[1]['queue_seconds'] >= 0 and len(calls) == 1


def paper():
    return {'scored': 7, 'family_counts': {}, 'attempts': [], 'failures': 0}


def test_failure_does_not_count_and_three_failures_yield_to_other_paper():
    a, b = paper(), paper()
    for i in range(3):
        attempt = {}; a['attempts'].append(attempt)
        batch.apply_result(a, attempt, {'qualified': False, 'family': 'classic_three_column'}, 3, 300, 100)
    assert a['scored'] == 7 and a['ready_at'] == 400
    assert a['family_counts']['classic_three_column'] == 3
    assert batch.ready_paper([a, b], {}, 20, 60, 101) == 1
    assert batch.ready_paper([a, b], {1: True}, 20, 60, 401) == 0
    batch.apply_result(a, {}, {'qualified': True, 'family': None}, 3, 300, 401)
    assert a['scored'] == 8


def test_no_duplicate_paper_and_cap_preserves_unfinished():
    a = paper()
    a['attempts'] = [{'finished': True}]*60
    assert batch.ready_paper([a], {}, 20, 60, 0) is None
    a['attempts'][-1] = {'finished': False}
    assert batch.ready_paper([a], {}, 20, 60, 0) == 0
    assert batch.ready_paper([a], {0: True}, 20, 60, 0) is None
    a['scored'] = 20
    assert batch.ready_paper([a], {}, 20, 60, 0) is None


def test_gpu_resolves_physical_index_not_ordinal(monkeypatch):
    class Result:
        stdout = '2, GPU-third\n3, GPU-fourth\n'
    monkeypatch.setattr(batch.subprocess, 'run', lambda *a, **k: Result())
    assert batch.gpu_uuid(3) == 'GPU-fourth'
    with pytest.raises(SystemExit): batch.parser().parse_args(['--gpu-index', '2'])


def test_manifest_validates_bytes_and_duplicate_pdf(tmp_path):
    pdf = tmp_path / 'Title' / 'paper.pdf'; pdf.parent.mkdir(); pdf.write_bytes(b'pdf fixture')
    manifest = tmp_path / 'manifest.json'
    row = {'pdf_path': 'Title/paper.pdf', 'pdf_sha256': file_hash(pdf)}
    _atomic_json(manifest, {'papers': [row]})
    assert batch.input_papers(manifest)[0]['title'] == 'Title'
    _atomic_json(manifest, {'papers': [row, row]})
    with pytest.raises(ValueError): batch.input_papers(manifest)
    pdf.write_bytes(b'changed')
    with pytest.raises(ValueError): batch.input_papers(manifest)


def test_real_parallel_office_profiles_and_stale_output_rejection(tmp_path, monkeypatch):
    import shutil
    if not shutil.which('libreoffice'): pytest.skip('LibreOffice unavailable')
    from pptx import Presentation
    from utils.office_conversion import convert
    from PIL import Image
    policy(tmp_path, monkeypatch)
    decks = []
    for i in range(3):
        root = tmp_path / str(i); root.mkdir()
        deck = Presentation(); slide = deck.slides.add_slide(deck.slide_layouts[6])
        slide.shapes.add_textbox(100000, 100000, 2000000, 1000000).text = f'Concurrent poster {i}'
        path = root / 'same.pptx'; deck.save(path); decks.append(path)
    with ThreadPoolExecutor(max_workers=3) as pool:
        images = list(pool.map(lambda p: convert(p, p.parent, 'png', 60), decks))
    assert len({file_hash(p) for p in images}) == 3
    for path in images:
        with Image.open(path) as im: im.verify()
    fake = tmp_path / 'fake-office'
    fake.write_text('#!/bin/sh\nexit 0\n'); fake.chmod(0o700)
    with pytest.raises(RuntimeError, match='no artifact'):
        convert(decks[0], decks[0].parent, 'png', 3, str(fake))


def test_office_timeout_kills_process_tree_and_releases_slot(tmp_path, monkeypatch):
    from utils.office_conversion import convert
    policy(tmp_path, monkeypatch)
    fake = tmp_path / 'fake-office'
    fake.write_text('#!/bin/sh\nsleep 60 &\nwait\n'); fake.chmod(0o700)
    pptx = tmp_path / 'test.pptx'; pptx.write_bytes(b'fake')
    started = time.monotonic()
    with pytest.raises(RuntimeError): convert(pptx, tmp_path, 'png', .2, str(fake))
    assert time.monotonic()-started < 10
    with slot('render') as wait: assert wait < 1


def test_scheduler_real_subprocess_failure_topup_publication_and_resume(tmp_path, monkeypatch):
    import src.config.exploration_config as config
    storage = tmp_path / 'storage'
    monkeypatch.setattr(config, 'load_exploration_config', lambda: {'storage_root': str(storage), 'default_samples': 100})
    monkeypatch.setattr(batch, 'gpu_uuid', lambda index: 'GPU-test-physical-3')
    monkeypatch.setattr(batch, 'fingerprint', lambda: 'frozen-test-code')
    manifest = tmp_path / 'inputs.json'
    entries = []
    for name in ('A', 'B'):
        pdf = tmp_path / name / 'paper.pdf'; pdf.parent.mkdir(); pdf.write_bytes(b'synthetic test paper')
        # PDFs must differ for real selection deduplication.
        pdf.write_bytes(pdf.read_bytes()+name.encode())
        entries.append({'pdf_path': str(pdf.relative_to(tmp_path)), 'pdf_sha256': file_hash(pdf)})
    _atomic_json(manifest, {'papers': entries})
    real_popen = subprocess.Popen
    launched = []
    def fixture_popen(command, **kwargs):
        assert command[1:3] == ['-m', 'rubrics_poster.batch_worker']
        assert kwargs['env']['CUDA_VISIBLE_DEVICES'] == 'GPU-test-physical-3'
        assert kwargs['env']['TORCH_DEVICE'] == 'cuda'
        launched.append(command[-1])
        return real_popen([sys.executable, str(ROOT/'tests/fixtures/batch_cpu_worker.py'), command[-1]], **kwargs)
    monkeypatch.setattr(batch.subprocess, 'Popen', fixture_popen)
    args = batch.parser().parse_args(['--manifest', str(manifest), '--target', '2', '--workers', '2',
        '--cooldown', '1', '--min-free-gib', '1', '--execute'])
    def fail_launch(*a, **k):
        raise OSError('injected process launch failure')
    monkeypatch.setattr(batch.subprocess, 'Popen', fail_launch)
    with pytest.raises(OSError, match='injected'):
        batch.run(args)
    directory = next((storage / 'batches').iterdir())
    assert read_json(directory/'batch.json')['status'] == 'PAUSED'
    monkeypatch.setattr(batch.subprocess, 'Popen', fixture_popen)
    assert batch.run(batch.parser().parse_args(['--resume', str(directory), '--execute'])) == 0
    state = read_json(directory/'batch.json')
    assert state['status'] == 'COMPLETED'
    assert [p['scored'] for p in state['papers']] == [2, 2]
    assert [len(p['attempts']) for p in state['papers']] == [3, 4]
    assert sum(state['papers'][0]['family_counts'].values()) == 3
    assert sum(state['papers'][1]['family_counts'].values()) == 3
    assert len(launched) == 7
    assert not state['papers'][0]['attempts'][1]['qualified']  # Incomplete residual 99 is excluded.
    assert state['papers'][0]['attempts'][0]['qualified']  # Low score 10 counts.
    before = list(launched)
    assert batch.run(batch.parser().parse_args(['--resume', str(directory), '--execute'])) == 0
    assert launched == before  # No repeated generation/scoring on completed resume.
    # Simulate publication completed just before the coordinator could finalize its journal.
    state = read_json(directory/'batch.json')
    state.pop('digest')
    state['papers'][0]['attempts'][-1]['finished'] = False
    _atomic_json(directory/'batch.json', {**state, 'digest': batch.digest(state)})
    assert batch.run(batch.parser().parse_args(['--resume', str(directory), '--execute'])) == 0
    assert launched == before
    # Corruption is rejected before launching anything.
    state = read_json(directory/'batch.json')
    state['papers'][0]['scored'] = 900
    _atomic_json(directory/'batch.json', state)
    with pytest.raises(ValueError, match='integrity'):
        batch.run(batch.parser().parse_args(['--resume', str(directory)]))


def test_coordinator_lease_survives_parent_until_child_exits(tmp_path):
    path = tmp_path / 'coordinator.lock'
    with batch.exclusive(path) as lease:
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], pass_fds=(lease.fileno(),))
    try:
        with pytest.raises(RuntimeError, match='already active'):
            with batch.exclusive(path): pass
    finally:
        child.kill(); child.wait()
    with batch.exclusive(path): pass


def test_same_family_history_is_required_when_resuming_runner(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT/'tests'))
    from test_exploration_samples import runner, scientific, critic_with_scores
    r = runner(tmp_path, samples=1, family_counts={'classic_three_column': 2}, critic=critic_with_scores([85]))
    result = r.run(scientific(tmp_path), paper_ready=True)
    resume = runner(tmp_path, samples=1, family_counts={'classic_three_column': 1},
                    run_id=result['run_state']['run_id'], critic=lambda s: pytest.fail('No new model calls'))
    with pytest.raises(ValueError, match='policy changed'):
        resume.run(scientific(tmp_path), paper_ready=True)


def test_waiting_process_stops_without_admission(tmp_path, monkeypatch):
    policy(tmp_path, monkeypatch, 1)
    stop = tmp_path / 'STOP'
    monkeypatch.setenv('RUBRICS_STOP_FILE', str(stop))
    script = "from utils.concurrency import slot\nwith slot('model'): raise RuntimeError('unexpected admission')"
    with slot('model'):
        child = subprocess.Popen([sys.executable, '-c', script], cwd=ROOT, stderr=subprocess.PIPE, text=True)
        time.sleep(.3)
        assert child.poll() is None
        stop.touch()
        _, stderr = child.communicate(timeout=5)
        assert child.returncode != 0 and 'WorkStopped' in stderr
        assert 'unexpected admission' not in stderr
