"""Explicit per-round inputs and crash-recoverable 20 × 20 sample reservations."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid

from utils.persistence import digest, file_hash, read_json, _atomic_json
from src.rubrics.library import LibraryStore
from src.rubrics.providers import ExternalModels, configuration, check_glm_endpoints
from src.rubrics.storage import IntegrityError, immutable, read, write


def inputs(folder):
    folder = Path(folder).resolve(strict=True)
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
            'logos':{name:file_hash(path.parent/name) if (path.parent/name).is_file() else None for name in ('logo.png','aff.png')}})
    if len(papers)!=20:
        raise ValueError('Specify a folder containing exactly 20 distinct readable PDFs')
    return papers


def create(folder, storage_root, *, seed=20261116, generate_only=False):
    from rubrics_poster.batch import fingerprint
    config = configuration()
    papers = inputs(folder)
    storage_root = Path(storage_root).resolve()
    maximum=config.get('limits',{}).get('max_rounds')
    if maximum is not None and len(list((storage_root/'iterations').glob('round_*/manifest.json')))>=maximum:
        from src.rubrics.storage import BudgetExceeded
        raise BudgetExceeded('ROUND_LIMIT_REACHED')
    library = LibraryStore(storage_root/'rubrics').active(required=True)
    check_glm_endpoints()
    if not generate_only:
        ExternalModels(config).check()
    rid = 'round_'+uuid.uuid4().hex[:20]
    root = storage_root/'iterations'/rid
    root.mkdir(parents=True,exist_ok=False)
    for i,paper in enumerate(papers):
        target = root/'inputs'/f'{i:02d}'
        target.mkdir(parents=True)
        shutil.copy2(paper['source'],target/'paper.pdf')
        for name,expected in paper['logos'].items():
            if expected:
                shutil.copy2(Path(paper['source']).parent/name,target/name)
                if file_hash(target/name)!=expected:
                    raise IntegrityError('Logo changed during input snapshot')
        if file_hash(target/'paper.pdf')!=paper['sha256']:
            raise IntegrityError('PDF changed during input snapshot')
        paper['paper_path'] = str(target/'paper.pdf')
    manifest = {'schema_version':1,'round_id':rid,'input_folder':str(Path(folder).resolve()),
        'storage_root':str(storage_root),'papers':papers,'library':library,'seed':seed,
        'config':config,'fingerprint':fingerprint(),'poster_output':str(root/'posters'),
        'route':'rubric-refine-score','generate_only':generate_only}
    immutable(root/'manifest.json',manifest)
    write(root/'state.json',{'manifest_digest':digest(manifest),'status':'PLANNED','attempts':[],
                            'next_input_status':'WAITING_NEXT_INPUT'})
    return root


def reserve(state, manifest, families):
    """Coordinator owns the lease. Reserve quota and family BEFORE launching a worker."""
    batch = manifest['config']['batch']
    attempts = state['attempts']
    for index,paper in enumerate(manifest['papers']):
        if state.get('cooldowns',{}).get(str(index),0)>time.time():
            continue
        rows = [a for a in attempts if a['paper_index']==index]
        success = sum(bool(a.get('result',{}).get('complete_score')) for a in rows)
        inflight = sum(not a.get('finished') for a in rows)
        if success+inflight>=batch['target'] or len(rows)>=batch['max_attempts']:
            continue
        counts = Counter(a['family'] for a in rows)
        family = min(families,key=lambda f:(counts[f],families.index(f)))
        number = len(rows)+1
        attempt = {'paper_index':index,'number':number,'path':f'jobs/{index:02d}_{number:03d}',
                   'family':family,'family_counts':dict(counts),'finished':False,
                   'seed':manifest['seed']+index*1000000+number}
        attempts.append(attempt)
        return attempt
    return None


def _spec(root,manifest,attempt,gpu):
    paper = manifest['papers'][attempt['paper_index']]
    return {'paper_path':paper['paper_path'],'paper_sha256':paper['sha256'],'title':paper['title'],
        'logos':paper['logos'],'storage_root':manifest['storage_root'],'gpu_uuid':gpu,
        'poster_output':manifest['poster_output'],'seed':attempt['seed'],'family_counts':attempt['family_counts'],
        'forced_family':attempt['family'],'mode':manifest['route'],'rubrics_snapshot':manifest['library'],
        'round_identity':{'round_id':manifest['round_id'],'manifest_digest':digest(manifest)},
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
    value = {'schema_version':1,'round_id':manifest['round_id'],'route':manifest['route'],
             'library_version':manifest['library']['version'],'paper_hashes':[p['sha256'] for p in manifest['papers']],
             'samples':samples,'manifest_digest':digest(manifest)}
    list(verified_samples(value))
    immutable(root/'seal.json',value)
    return value


def run(root):
    from rubrics_poster.batch import PROJECT, fingerprint, gpu_uuid, exclusive, inspect_attempt
    from src.workflow.exploration_store import ExplorationStore
    from src.layout.families import LayoutFamilyRegistry
    root = Path(root).resolve()
    manifest = read(root/'manifest.json')
    if manifest['fingerprint']!=fingerprint():
        raise IntegrityError('Round source/prompts/configuration changed; cannot resume generation')
    config = manifest['config']; batch = config['batch']
    check_glm_endpoints()
    if batch['papers']!=20 or batch['target']!=20 or batch['max_attempts']!=60 or not 1<=batch['workers']<=30:
        raise ValueError('Round contract requires 20 × 20, maximum 60 attempts/paper and 30 workers')
    if not manifest['generate_only']:
        ExternalModels(config).check()
    store_root = Path(manifest['storage_root'])
    gpu = gpu_uuid(batch['gpu_index'])
    storage = ExplorationStore(store_root,poster_output=manifest['poster_output'])
    families = LayoutFamilyRegistry().ids()
    with exclusive(store_root/'concurrency/coordinator.lock') as lease:
        state = read(root/'state.json')
        if state['manifest_digest']!=digest(manifest):
            raise IntegrityError('Round journal belongs to another manifest')
        if state.get('gpu_uuid',gpu)!=gpu:
            raise IntegrityError('Round GPU identity changed')
        state['gpu_uuid'] = gpu
        def save(): write(root/'state.json',state)
        if (root/'seal.json').exists():
            from src.rubrics.mining import verified_samples
            list(verified_samples(read(root/'seal.json')))
            state['postprocess_trigger']='manual'; save()
            return root/'seal.json'
        stop_file = root/'STOP'
        stop_file.unlink(missing_ok=True)
        policy = root/'resources.json'
        _atomic_json(policy,{'root':str(store_root/'concurrency'),'marker_timeout_seconds':1800,
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
                successes = Counter(a['paper_index'] for a in state['attempts'] if a.get('result',{}).get('complete_score'))
                complete = all(successes[i]==20 for i in range(20))
                exhausted = all(successes[i]==20 or sum(a['paper_index']==i for a in state['attempts'])>=60 for i in range(20))
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
