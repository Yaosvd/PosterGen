"""Bounded process scheduling until each paper has enough published complete scores.

Preview: python -m rubrics_poster.batch
Run:     python -m rubrics_poster.batch --execute
Resume:  python -m rubrics_poster.batch --resume /absolute/batch/directory --execute
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from utils.persistence import _atomic_json, digest, file_hash, read_json

PROJECT = Path(__file__).resolve().parents[1]


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=PROJECT / 'data/seed posters/selection_manifest.json')
    p.add_argument('--target', type=positive, default=20)
    p.add_argument('--workers', type=positive, default=10)
    p.add_argument('--gpu-index', type=int, choices=[3], default=3, help='Physical nvidia-smi index; only 3 is authorized')
    p.add_argument('--marker-timeout', type=positive, default=1800, help='Local extraction seconds, excluding slot queue')
    p.add_argument('--model-slots', type=positive, default=4)
    p.add_argument('--render-slots', type=positive, default=2)
    p.add_argument('--failure-streak', type=positive, default=3)
    p.add_argument('--cooldown', type=positive, default=300)
    p.add_argument('--max-attempts', type=positive, default=60, help='Per paper safety ceiling; never reports an incomplete paper as complete')
    p.add_argument('--min-free-gib', type=positive, default=20)
    p.add_argument('--seed', type=int, default=20261111)
    p.add_argument('--resume', type=Path)
    p.add_argument('--execute', action='store_true', help='Without this flag only validate and print the plan')
    return p


def input_papers(manifest):
    manifest = manifest.resolve()
    data = read_json(manifest)
    papers, seen = [], set()
    for entry in data['papers']:
        path = (manifest.parent / entry['pdf_path']).resolve()
        identity = file_hash(path)
        if not path.is_relative_to(manifest.parent) or identity != entry['pdf_sha256'] or identity in seen:
            raise ValueError('Invalid, changed or duplicate input PDF')
        seen.add(identity)
        papers.append({'paper_path': str(path), 'sha256': identity, 'title': path.parent.name,
                       'logos': {name: file_hash(path.parent / name) if (path.parent / name).is_file() else None
                                 for name in ('logo.png', 'aff.png')}})
    if not papers:
        raise ValueError('Empty paper selection')
    return papers


def fingerprint():
    paths = []
    for folder in ('src', 'utils', 'rubrics_poster', 'config'):
        paths.extend(p for p in (PROJECT / folder).rglob('*') if p.suffix in {'.py', '.yaml', '.txt'})
    # Freeze effective local model routes without persisting credentials.
    from dotenv import dotenv_values
    env = {**os.environ, **{k: v for k, v in dotenv_values(PROJECT / '.env').items() if v is not None}}
    routes = {k: env.get(k) for k in ('LOCAL_TEXT_BASE_URL', 'LOCAL_VISION_BASE_URL',
              'LOCAL_TEXT_MODEL', 'LOCAL_VISION_MODEL', 'LOCAL_TEXT_ENABLE_THINKING', 'LOCAL_VISION_ENABLE_THINKING')}
    return digest({'files': {str(p.relative_to(PROJECT)): file_hash(p) for p in sorted(paths)}, 'routes': routes})


def gpu_uuid(index):
    result = subprocess.run(['nvidia-smi', '--query-gpu=index,uuid', '--format=csv,noheader'],
                            check=True, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        number, identity = (part.strip() for part in line.split(',', 1))
        if int(number) == index and identity.startswith('GPU-'):
            return identity
    raise ValueError(f'Cannot resolve physical GPU {index}')


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('A batch coordinator or its workers are already active') from None
        yield stream


def inspect_attempt(directory, storage):
    """Verify committed bundles; never trust worker exit code as success."""
    receipt = directory / 'run.json'
    if not receipt.exists():
        return {'qualified': False, 'family': None}
    rid = read_json(receipt)['run_id']
    spec = read_json(directory / 'task.json')
    manifest = read_json(storage.run_path(rid) / 'manifest.json')
    identity = manifest.get('identity', {})
    if (manifest.get('settings_digest') != digest(manifest.get('settings'))
            or manifest.get('seed') != spec['seed'] or manifest.get('samples') != 1
            or identity.get('inputs', {}).get('pdf_path') != spec['paper_sha256']
            or manifest['settings'].get('initial_family_counts', {}) != spec['family_counts']):
        raise ValueError('Attempt run does not match its frozen paper/seed/coverage')
    storage.recover_published(rid)
    records = storage.results(rid)
    if len(records) > 1:
        raise ValueError('Batch attempt unexpectedly contains multiple samples')
    family = None
    assignment = storage.sample_path(rid, 'sample_000001') / 'family_assignment.json'
    if assignment.exists():
        # Read through the store's integrity validation with frozen task counts.
        plan = read_json(storage.run_path(rid) / 'sample_plan.json')['tasks'][0]
        counts = read_json(directory / 'task.json')['family_counts']
        family = storage.saved_assignment(rid, plan, counts)['family']
    if not records:
        return {'qualified': False, 'family': family, 'run_id': rid}
    record = records[0]
    qualified = False
    if record.get('poster_id'):
        from src.workflow.poster_grouping import poster_group
        bundle = storage.verify_poster(record['poster_id'])
        qualified = poster_group(record, read_json(bundle / 'evaluation.json')) in {'high_score', 'low_score'}
    return {'qualified': qualified, 'family': family, 'run_id': rid,
            'poster_id': record.get('poster_id'), 'status': record['status']}


def ready_paper(papers, active, target, ceiling, now):
    for index, paper in enumerate(papers):
        if index in active or paper['scored'] >= target:
            continue
        unfinished = bool(paper['attempts'] and not paper['attempts'][-1].get('finished'))
        if (unfinished or len(paper['attempts']) < ceiling) and paper.get('ready_at', 0) <= now:
            return index
    return None


def apply_result(paper, attempt, result, failure_streak, cooldown, now):
    attempt.update(result, finished=True)
    if result['family']:
        family = result['family']
        paper['family_counts'][family] = paper['family_counts'].get(family, 0) + 1
    if result['qualified']:
        paper['scored'] += 1
        paper['failures'] = 0
    else:
        paper['failures'] += 1
        if paper['failures'] >= failure_streak:
            paper['ready_at'] = now + cooldown
            paper['failures'] = 0


def run(args):
    os.chdir(PROJECT)
    from src.config.exploration_config import load_exploration_config
    root = Path(load_exploration_config()['storage_root']).resolve()
    resume = args.resume.resolve() if args.resume else None
    if resume:
        state = read_json(resume / 'batch.json')
        expected = state.pop('digest', None)
        if expected != digest(state):
            raise ValueError('Batch journal integrity check failed')
        config = state['config']
        manifest = Path(config['manifest'])
    else:
        config = {key: getattr(args, key) for key in ('target', 'workers', 'gpu_index', 'model_slots',
                  'render_slots', 'marker_timeout', 'failure_streak', 'cooldown', 'max_attempts', 'min_free_gib', 'seed')}
        config['manifest'] = str(args.manifest.resolve())
        manifest = args.manifest
        if config['max_attempts'] < config['target']:
            raise ValueError('max-attempts must be at least target')
    inputs = input_papers(manifest)
    current_fingerprint = fingerprint()
    if resume and (state['inputs'] != inputs or state['fingerprint'] != current_fingerprint):
        raise ValueError('Batch inputs, source, prompts, configuration or model routes changed; resume refused')
    print(json.dumps({'papers': len(inputs), 'total_complete_scores': len(inputs)*config['target'],
                      **config, 'execute': args.execute}, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        return 0
    gpu = gpu_uuid(config['gpu_index'])
    if resume and state['gpu_uuid'] != gpu:
        raise ValueError('Physical GPU 3 changed since batch creation')
    # All managed batches in this checkout share a host-wide coordinator lease.
    # Children inherit it so coordinator death cannot permit duplicate scheduling.
    with exclusive(root / 'concurrency' / 'coordinator.lock') as lease:
        directory = resume or root / 'batches' / ('batch_' + uuid.uuid4().hex[:20])
        directory.mkdir(parents=True, exist_ok=True)
        policy = {'root': str(root / 'concurrency'), 'marker_timeout_seconds': config['marker_timeout'],
                  'limits': {'marker': 1, 'model': config['model_slots'], 'render': config['render_slots']}}
        policy_path = directory / 'resources.json'
        _atomic_json(policy_path, policy)
        stop_file = directory / 'STOP'
        stop_file.unlink(missing_ok=True)
        if not resume:
            state = {'version': 1, 'config': config, 'inputs': inputs, 'fingerprint': current_fingerprint,
                     'gpu_uuid': gpu, 'papers': [{**v, 'scored': 0, 'failures': 0, 'family_counts': {},
                                                 'attempts': []} for v in inputs]}
        def save():
            _atomic_json(directory / 'batch.json', {**state, 'digest': digest(state)})
        save()
        print(f'Batch directory: {directory}', flush=True)
        from src.workflow.exploration_store import ExplorationStore
        storage = ExplorationStore(root)
        # Recompute completed counters from verified artifacts on resume.
        counted_posters = set()
        for paper in state['papers']:
            paper['scored'], paper['family_counts'] = 0, {}
            for attempt in paper['attempts']:
                job = directory / attempt['path']
                if (digest(read_json(job / 'task.json')) != attempt['task_digest']
                        or read_json(job / 'task.json')['family_counts'] != paper['family_counts']):
                    raise ValueError('Attempt task/coverage history changed')
                if attempt.get('finished'):
                    verified = inspect_attempt(directory / attempt['path'], storage)
                    attempt.update(verified)
                    if verified['qualified']:
                        if verified['poster_id'] in counted_posters:
                            raise ValueError('Duplicate published poster in batch journal')
                        counted_posters.add(verified['poster_id'])
                    paper['scored'] += int(verified['qualified'])
                    if verified['family']:
                        f = verified['family']
                        paper['family_counts'][f] = paper['family_counts'].get(f, 0) + 1
        active = {}
        stopping = False
        def stop(_signal, _frame):
            nonlocal stopping
            stopping = True
            stop_file.touch()
            for child, _, _ in active.values():
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)
        old = {s: signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
        state['status'] = 'RUNNING'
        heartbeat = 0.0
        save()
        try:
            while True:
                for index, (child, log, attempt) in list(active.items()):
                    if child.poll() is None:
                        continue
                    log.close()
                    del active[index]
                    job = directory / attempt['path']
                    outcome = read_json(job / 'outcome.json') if (job / 'outcome.json').exists() else {}
                    result = inspect_attempt(job, storage)
                    if not result['qualified'] and (stopping or outcome.get('status') == 'PAUSED'):
                        # Retain the exact task and its run receipt for checkpoint resume.
                        attempt['exit_code'] = child.returncode
                    else:
                        paper = state['papers'][index]
                        apply_result(paper, attempt, result, config['failure_streak'], config['cooldown'], time.time())
                        attempt['exit_code'] = child.returncode
                        print(f"{paper['title']}: {paper['scored']}/{config['target']} complete; "
                              f"attempt {len(paper['attempts'])}: {result.get('status', 'worker_failed')}", flush=True)
                        # OOM/service errors cool down all launches, not only this paper.
                        tail = (job / 'worker.log').read_text(errors='replace')[-16000:].lower()
                        if not result['qualified'] and any(t in tail for t in (
                                'out of memory', 'no space left on device', 'connection refused',
                                'connecterror', 'apiconnectionerror', 'readtimeout', 'ratelimiterror',
                                'serviceunavailableerror')):
                            state['backoff_until'] = time.time() + config['cooldown']
                    save()
                import shutil
                if shutil.disk_usage(root).free < config['min_free_gib'] * 2**30 and not stopping:
                    print('Free disk space below reserve; stopping safely.', flush=True)
                    stop(None, None)
                while not stopping and len(active) < config['workers'] and time.time() >= state.get('backoff_until', 0):
                    index = ready_paper(state['papers'], active, config['target'], config['max_attempts'], time.time())
                    if index is None:
                        break
                    paper = state['papers'][index]
                    if paper['attempts'] and not paper['attempts'][-1].get('finished'):
                        attempt = paper['attempts'][-1]
                    else:
                        number = len(paper['attempts']) + 1
                        attempt = {'path': f'papers/{index:03d}/attempt_{number:06d}', 'finished': False}
                        paper['attempts'].append(attempt)
                        job = directory / attempt['path']
                        job.mkdir(parents=True, exist_ok=True)
                        if (job / 'run.json').exists() or (job / 'outcome.json').exists():
                            raise ValueError('Unjournaled generation history found; refusing overwrite')
                        spec = {'paper_path': paper['paper_path'], 'paper_sha256': paper['sha256'],
                                'logos': paper['logos'], 'storage_root': str(root), 'gpu_uuid': gpu,
                                'seed': config['seed'] + index * 1000000 + number,
                                'family_counts': dict(paper['family_counts']),
                                'defaults': {'text_model': 'local-text', 'vision_model': 'local-vision',
                                             'poster_width': 54, 'poster_height': 36, 'url': ''}}
                        _atomic_json(job / 'task.json', spec)
                        attempt['task_digest'] = digest(spec)
                        save()
                    job = directory / attempt['path']
                    if digest(read_json(job / 'task.json')) != attempt['task_digest']:
                        raise ValueError('Attempt task changed')
                    # A process can die after publication but before reporting success.
                    existing = inspect_attempt(job, storage)
                    prior_outcome = read_json(job / 'outcome.json') if (job / 'outcome.json').exists() else {}
                    if existing.get('status') or prior_outcome.get('status') == 'FAILED':
                        apply_result(paper, attempt, existing, config['failure_streak'], config['cooldown'], time.time())
                        save()
                        continue
                    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': gpu, 'TORCH_DEVICE': 'cuda',
                           'RUBRICS_RESOURCE_POLICY': str(policy_path), 'RUBRICS_STOP_FILE': str(stop_file),
                           'RUBRICS_COORDINATOR_FD': str(lease.fileno()),
                           'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}
                    if (file_hash(paper['paper_path']) != paper['sha256'] or any(
                            (file_hash(Path(paper['paper_path']).parent / name)
                             if (Path(paper['paper_path']).parent / name).is_file() else None) != expected
                            for name, expected in paper['logos'].items())):
                        raise ValueError('PDF/Logo changed during batch; refusing new generation')
                    if fingerprint() != state['fingerprint']:
                        raise ValueError('Source/configuration changed during batch; refusing new generation')
                    log = (job / 'worker.log').open('a')
                    try:
                        child = subprocess.Popen([sys.executable, '-m', 'rubrics_poster.batch_worker', str(job)],
                            cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True, pass_fds=(lease.fileno(),))
                    except BaseException:
                        log.close()
                        raise
                    active[index] = (child, log, attempt)
                remaining = [p for p in state['papers'] if p['scored'] < config['target']]
                if not active and (stopping or not remaining or all(
                        len(p['attempts']) >= config['max_attempts'] and p['attempts'][-1].get('finished')
                        for p in remaining)):
                    state['status'] = 'COMPLETED' if not remaining else 'PAUSED' if stopping else 'INCOMPLETE'
                    save()
                    return 0 if not remaining else 2
                if time.monotonic() - heartbeat >= 15:
                    heartbeat = time.monotonic()
                    scored = sum(p['scored'] for p in state['papers'])
                    total = len(state['papers']) * config['target']
                    print(f'Batch progress: {scored}/{total} complete scores; '
                          f'{len(active)} active workers; {len(remaining)} papers remaining', flush=True)
                time.sleep(.5)
        except BaseException as exc:
            state['status'] = 'PAUSED'
            state['coordinator_error'] = {'type': type(exc).__name__, 'message': str(exc)}
            save()
            raise
        finally:
            # Leave no unmanaged generation workers when the coordinator raises.
            stop(None, None)
            for child, log, _ in active.values():
                child.wait()
                log.close()
            for sig, handler in old.items():
                signal.signal(sig, handler)


def main():
    args = parser().parse_args()
    try:
        return run(args)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'Batch stopped: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
