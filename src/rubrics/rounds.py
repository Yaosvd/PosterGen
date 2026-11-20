"""Explicit per-round inputs and crash-recoverable 20 × 20 sample reservations."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

from utils.persistence import digest, file_hash, read_json, _atomic_json
from src.critic.scoring import current_policy, validate_policy_snapshot
from src.rubrics.library import LibraryStore
from src.rubrics.providers import ExternalModels, configuration, check_glm_endpoints
from src.rubrics.storage import IntegrityError, immutable, lock, read, write


def inputs(folder, *, logo_folder=None):
    folder = Path(folder).resolve(strict=True)
    shared = None
    if logo_folder is not None:
        from PIL import Image
        logo_folder = Path(logo_folder).resolve(strict=True)
        shared = {}
        for name in ('logo.png', 'aff.png'):
            path = logo_folder/name
            with Image.open(path) as image:
                image.verify()
            shared[name] = file_hash(path)
    papers, seen = [], set()
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.suffix.lower()!='.pdf':
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(folder):
            raise ValueError('Round input PDF escapes its folder')
        identity = file_hash(path)
        if identity in seen:
            raise ValueError('Duplicate PDF content in the round folder')
        import fitz
        with fitz.open(path) as doc:
            if not doc.page_count or doc.needs_pass:
                raise ValueError('Unreadable or encrypted round PDF')
        seen.add(identity)
        papers.append({'source':str(path),'sha256':identity,
            'title':path.parent.name if path.name.lower()=='paper.pdf' else path.stem,
            'logos':dict(shared) if shared is not None else {
                name:file_hash(path.parent/name) if (path.parent/name).is_file() else None
                for name in ('logo.png','aff.png')}})
    if len(papers)!=20:
        raise ValueError('Specify a folder containing exactly 20 distinct readable PDFs')
    return papers


def _numbered_output(storage_root, number, output):
    """Called under the creation lock; never assign one collection to two rounds."""
    known, destinations = set(), set()
    for path in (storage_root/'iterations').glob('round_*/manifest.json'):
        manifest = read(path)
        destination = Path(manifest['poster_output']).resolve()
        destinations.add(destination)
        legacy = re.fullmatch(r'posters round([1-9][0-9]*)', destination.name)
        value = manifest.get('round_number')
        if value is not None:
            if type(value) is not int or value < 1:
                raise IntegrityError('Invalid saved round number')
            known.add(value)
        elif legacy:
            known.add(int(legacy[1]))
    occupied = set(known)
    for path in (storage_root/'posters').glob('posters round*'):
        match = re.fullmatch(r'posters round([1-9][0-9]*)', path.name)
        if match:
            occupied.add(int(match[1]))
    if number is None:
        number = max(occupied, default=0)+1
    if type(number) is not int or number < 1:
        raise ValueError('Round number must be a positive integer')
    if number in known:
        raise ValueError('Round number already has a plan; resume that round')
    target = Path(output) if output is not None else storage_root/'posters'/f'posters round{number}'
    if target.is_symlink():
        raise ValueError('Poster output must not be a symlink')
    target = target.resolve()
    if target in destinations:
        raise ValueError('Poster output already belongs to a round')
    if target.exists() and (not target.is_dir() or any(p.is_file() for p in target.rglob('*'))):
        raise ValueError('Poster output must be an empty directory')
    return number, target


def check_round_batch(batch):
    if (batch['papers'] != 20 or batch['target'] != 20 or batch.get('target_group') != 'high_score'
            or batch['max_attempts'] != 200 or not 1 <= batch['workers'] <= 30):
        raise ValueError('Expected 20 papers × 20 high scores, up to 200 attempts per paper and 30 workers')


def create(folder, storage_root, *, seed=20261116, generate_only=False, poster_output=None,
           logo_folder=None, round_number=None):
    from rubrics_poster.batch import fingerprint
    config = configuration()
    check_round_batch(config['batch'])
    papers = inputs(folder, logo_folder=logo_folder)
    logo_folder = Path(logo_folder).resolve() if logo_folder is not None else None
    storage_root = Path(storage_root).resolve()
    with lock(storage_root/'iterations/.create.lock', blocking=False):
        maximum=config.get('limits',{}).get('max_rounds')
        if maximum is not None and len(list((storage_root/'iterations').glob('round_*/manifest.json')))>=maximum:
            from src.rubrics.storage import BudgetExceeded
            raise BudgetExceeded('ROUND_LIMIT_REACHED')
        library = LibraryStore(storage_root/'rubrics').active(required=True)
        check_glm_endpoints()
        if not generate_only:
            ExternalModels(config).check()
        round_number, output = _numbered_output(storage_root, round_number, poster_output)
        rid = 'round_'+uuid.uuid4().hex[:20]
        root = storage_root/'iterations'/rid
        root.mkdir(parents=True,exist_ok=False)
        for i,paper in enumerate(papers):
            target = root/'inputs'/f'{i:02d}'
            target.mkdir(parents=True)
            shutil.copy2(paper['source'],target/'paper.pdf')
            for name,expected in paper['logos'].items():
                if expected:
                    shutil.copy2((logo_folder if logo_folder is not None else Path(paper['source']).parent)/name,target/name)
                    if file_hash(target/name)!=expected:
                        raise IntegrityError('Logo changed during input snapshot')
            if file_hash(target/'paper.pdf')!=paper['sha256']:
                raise IntegrityError('PDF changed during input snapshot')
            paper['paper_path'] = str(target/'paper.pdf')
        manifest = {'schema_version':3,'scoring_policy':current_policy(),'round_id':rid,'input_folder':str(Path(folder).resolve()),
            'storage_root':str(storage_root),'papers':papers,'library':library,'seed':seed,
            'config':config,'fingerprint':fingerprint(),'poster_output':str(output),
            'round_number':round_number,'logo_folder':str(logo_folder) if logo_folder is not None else None,
            'route':'rubric-refine-score','generate_only':generate_only}
        immutable(root/'manifest.json',manifest)
        write(root/'state.json',{'manifest_digest':digest(manifest),'status':'PLANNED','attempts':[],
                                'next_input_status':'WAITING_NEXT_INPUT'})
        return root


def _paper_progress(attempts):
    reserved, inflight, high_scores = Counter(), Counter(), Counter()
    for attempt in attempts:
        index = attempt['paper_index']
        reserved[index] += 1
        if not attempt['finished']:
            inflight[index] += 1
        elif attempt['result'].get('qualified'):
            high_scores[index] += 1
    return reserved, inflight, high_scores


def reserve(state, manifest, families):
    """Give eligible papers with fewer concurrent jobs the next slot."""
    batch = manifest['config']['batch']
    attempts = state['attempts']
    reserved, inflight, high_scores = _paper_progress(attempts)
    now = time.time()
    eligible = (i for i in range(len(manifest['papers']))
                if state.get('cooldowns', {}).get(str(i), 0) <= now
                and reserved[i] < batch['max_attempts']
                and high_scores[i] + inflight[i] < batch['target'])
    index = min(eligible, key=lambda i: (inflight[i], reserved[i], i), default=None)
    if index is None:
        return None
    counts = Counter(a['family'] for a in attempts if a['paper_index'] == index)
    family = min(families, key=lambda f: counts[f])
    number = reserved[index] + 1
    attempt = {'paper_index':index,'number':number,'path':f'jobs/{index:02d}_{number:03d}',
               'family':family,'family_counts':dict(counts),'finished':False,
               'seed':manifest['seed']+index*1000000+number}
    attempts.append(attempt)
    return attempt


def _spec(root,manifest,attempt,gpu):
    paper = manifest['papers'][attempt['paper_index']]
    return {'paper_path':paper['paper_path'],'paper_sha256':paper['sha256'],'title':paper['title'],
        'logos':paper['logos'],'storage_root':manifest['storage_root'],'gpu_uuid':gpu,
        'poster_output':manifest['poster_output'],'seed':attempt['seed'],'family_counts':attempt['family_counts'],
        'forced_family':attempt['family'],'mode':manifest['route'],'rubrics_snapshot':manifest['library'],
        'round_identity':{'round_id':manifest['round_id'],'manifest_digest':digest(manifest)},
        'scoring_policy':manifest['scoring_policy'],
        'defaults':{'text_model':'local-text','vision_model':'local-vision','poster_width':54,'poster_height':36,'url':''}}


def seal(root, manifest, state, storage):
    from rubrics_poster.batch import inspect_attempt
    from src.rubrics.mining import verified_samples
    samples = []
    for attempt in state['attempts']:
        result = inspect_attempt(root/attempt['path'],storage)
        if not result.get('complete_score'):
            continue
        bundle = storage.verify_poster(result['poster_id'])
        samples.append({'poster_id':result['poster_id'],
            'paper_sha256':manifest['papers'][attempt['paper_index']]['sha256'],
            'bundle_path':str(bundle),'files':{str(p.relative_to(bundle)):file_hash(p) for p in bundle.rglob('*') if p.is_file()}})
    value = {'schema_version':4,'kind':'high_score_round','scoring_policy':manifest['scoring_policy'],
             'scoring_policy_digest':manifest['scoring_policy']['digest'],'round_id':manifest['round_id'],'route':manifest['route'],
             'library_version':manifest['library']['version'],'paper_hashes':[p['sha256'] for p in manifest['papers']],
             'samples':samples,'manifest_digest':digest(manifest)}
    for _ in verified_samples(value):
        pass
    immutable(root/'seal.json',value)
    return value


def run(root):
    from rubrics_poster.batch import PROJECT, fingerprint, gpu_uuid, exclusive, inspect_attempt
    from src.workflow.exploration_store import ExplorationStore
    from src.layout.families import LayoutFamilyRegistry
    root = Path(root).resolve()
    manifest = read(root/'manifest.json')
    if manifest.get('schema_version') != 3:
        raise IntegrityError('Round generation contract changed; create a new round')
    frozen_policy = validate_policy_snapshot(manifest.get('scoring_policy'))
    if frozen_policy != current_policy():
        raise IntegrityError('Round evaluator policy changed; cannot resume generation')
    if manifest['fingerprint']!=fingerprint():
        raise IntegrityError('Round source/prompts/configuration changed; cannot resume generation')
    config = manifest['config']; batch = config['batch']
    check_glm_endpoints()
    check_round_batch(batch)
    if not manifest['generate_only']:
        ExternalModels(config).check()
    store_root = Path(manifest['storage_root'])
    gpu = gpu_uuid(batch['gpu_index'])
    indices = batch.get('marker_gpu_indices', [batch['gpu_index']] * batch['marker_slots'])
    gpu_by_index = {batch['gpu_index']: gpu}
    for index in indices:
        if index not in gpu_by_index:
            gpu_by_index[index] = gpu_uuid(index)
    marker_gpus = [gpu_by_index[index] for index in indices]
    storage = ExplorationStore(store_root,poster_output=manifest['poster_output'])
    families = LayoutFamilyRegistry().ids()
    with exclusive(store_root/'concurrency/coordinator.lock') as lease:
        state = read(root/'state.json')
        if state['manifest_digest']!=digest(manifest):
            raise IntegrityError('Round journal belongs to another manifest')
        if state.get('gpu_uuid',gpu)!=gpu:
            raise IntegrityError('Round GPU identity changed')
        state['gpu_uuid'] = gpu
        if state.get('marker_gpu_uuids', marker_gpus) != marker_gpus:
            raise IntegrityError('Round Marker GPU identities changed')
        state['marker_gpu_uuids'] = marker_gpus
        def save(): write(root/'state.json',state)
        if (root/'seal.json').exists():
            from src.rubrics.mining import verified_samples
            sealed = read(root/'seal.json')
            if (sealed.get('schema_version') != 4 or sealed.get('kind') != 'high_score_round'
                    or sealed.get('manifest_digest') != digest(manifest) or sealed.get('scoring_policy') != frozen_policy):
                raise IntegrityError('Sealed round differs from its frozen manifest')
            for _ in verified_samples(sealed):
                pass
            state['postprocess_trigger']='manual'; save()
            return root/'seal.json'
        stop_file = root/'STOP'
        stop_file.unlink(missing_ok=True)
        policy = root/'resources.json'
        _atomic_json(policy,{'root':str(store_root/'concurrency'),'marker_timeout_seconds':1800,
            'marker_gpu_uuids':marker_gpus,
            'limits':{'marker':batch['marker_slots'],'model':batch['model_slots'],'render':batch['render_slots']}})
        active = {}; stopping = [False]
        def stop(*_):
            stopping[0] = True
            stop_file.touch()
            for child,_,_ in active.values():
                if child.poll() is None: child.send_signal(signal.SIGINT)
        # Verify every durable completion and retain unfinished exact reservations.
        for attempt in state['attempts']:
            job = root/attempt['path']
            if (job/'task.json').exists() and read_json(job/'task.json')!=_spec(root,manifest,attempt,gpu):
                raise IntegrityError('Reserved task changed')
            if attempt.get('finished'):
                result = inspect_attempt(job,storage)
                if result!=attempt['result']:
                    raise IntegrityError('Completed round result changed')
        state['status']='RUNNING'; save()
        old = {s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM)}
        try:
            while True:
                if stop_file.exists() and not stopping[0]:
                    stop()
                for name,(child,log,attempt) in list(active.items()):
                    if child.poll() is None: continue
                    log.close(); del active[name]
                    job = root/name
                    result = inspect_attempt(job,storage)
                    outcome = read_json(job/'outcome.json') if (job/'outcome.json').exists() else {}
                    if not result.get('status') and (stopping[0] or outcome.get('status')=='PAUSED'):
                        attempt['exit_code']=child.returncode
                    else:
                        attempt.update(finished=True,result=result,exit_code=child.returncode)
                        tail = (job/'worker.log').read_text(errors='replace')[-20000:].lower()
                        if not result.get('complete_score'):
                            if any(t in tail for t in ('cuda is not available','cuda unavailable','no cuda gpus','out of memory','no space left on device','connection refused','connecterror','apiconnectionerror')):
                                state['pause_reason']='infrastructure_unavailable'; stop()
                            else:
                                rows = [a for a in state['attempts'] if a['paper_index']==attempt['paper_index'] and a.get('finished')]
                                if len(rows)>=3 and all(not a.get('result',{}).get('complete_score') for a in rows[-3:]):
                                    state.setdefault('cooldowns',{})[str(attempt['paper_index'])]=time.time()+300
                    save()
                if shutil.disk_usage(store_root).free<batch['min_free_gib']*2**30:
                    state['pause_reason']='disk_reserve'; stop()
                while not stopping[0] and len(active)<batch['workers']:
                    pending = next((a for a in state['attempts'] if not a.get('finished') and a['path'] not in active and
                                    state.get('cooldowns',{}).get(str(a['paper_index']),0)<=time.time()),None)
                    if pending is None:
                        pending = reserve(state,manifest,families)
                        if pending: save()
                    if pending is None: break
                    if state.get('cooldowns',{}).get(str(pending['paper_index']),0)>time.time():
                        break
                    job = root/pending['path']; job.mkdir(parents=True,exist_ok=True)
                    spec = _spec(root,manifest,pending,gpu)
                    if file_hash(spec['paper_path'])!=spec['paper_sha256'] or fingerprint()!=manifest['fingerprint']:
                        raise IntegrityError('Frozen input or source changed during round')
                    if (job/'task.json').exists():
                        if read_json(job/'task.json')!=spec: raise IntegrityError('Worker task changed')
                    else: _atomic_json(job/'task.json',spec)
                    recovered = inspect_attempt(job,storage)
                    outcome = read_json(job/'outcome.json') if (job/'outcome.json').exists() else {}
                    if recovered.get('status') or outcome.get('status')=='FAILED':
                        pending.update(finished=True,result=recovered); save(); continue
                    env = {**os.environ,'CUDA_VISIBLE_DEVICES':gpu,'TORCH_DEVICE':'cuda',
                        'RUBRICS_RESOURCE_POLICY':str(policy),'RUBRICS_STOP_FILE':str(stop_file),
                        'RUBRICS_COORDINATOR_FD':str(lease.fileno()),'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
                    log = (job/'worker.log').open('a')
                    try:
                        child = subprocess.Popen([sys.executable,'-m','rubrics_poster.batch_worker',str(job)],cwd=PROJECT,
                            env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,pass_fds=(lease.fileno(),))
                    except BaseException:
                        log.close(); raise
                    active[pending['path']] = (child,log,pending)
                reserved, inflight, high_scores = _paper_progress(state['attempts'])
                papers = range(len(manifest['papers']))
                complete = all(high_scores[i] == batch['target'] for i in papers)
                exhausted = all(high_scores[i] == batch['target']
                                or reserved[i] - inflight[i] >= batch['max_attempts'] for i in papers)
                if not active and (stopping[0] or complete or exhausted):
                    state['status']='SEALED' if complete else 'PAUSED' if stopping[0] else 'INCOMPLETE'
                    if complete:
                        seal(root,manifest,state,storage)
                        state['postprocess_trigger']='manual'
                    save()
                    return root/'seal.json' if complete else None
                time.sleep(.5)
        except BaseException as exc:
            state.update(status='PAUSED',error={'type':type(exc).__name__,'message':str(exc)})
            save(); raise
        finally:
            stop()
            for child,log,_ in active.values(): child.wait(); log.close()
            for sig,handler in old.items(): signal.signal(sig,handler)
