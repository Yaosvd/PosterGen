"""WebUI for independent Rubrics poster samples."""
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.state.poster_state import create_state
from src.workflow.runtime import save_timing_log
from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.exploration_store import ExplorationStore
from src.workflow.run_control import RunControl
from src.config.exploration_config import load_exploration_config
from utils.persistence import read_json

app=FastAPI(title='Rubrics_poster WebUI API')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000'],allow_credentials=True,
                   allow_methods=['*'],allow_headers=['*'])
jobs={}
job_logs={}
loop_controls={}


class JobStatus(BaseModel):
    job_id:str
    status:str
    progress:int
    message:str
    error:Optional[str]=None
    sample_generation:bool=False
    run_id:Optional[str]=None
    planned_samples:int=0
    finalized_samples:int=0
    rendered_samples:int=0
    scored_samples:int=0
    failed_samples:int=0
    iteration:int=0
    layout_family:Optional[str]=None
    results:list[dict]=[]


def store():
    return ExplorationStore(load_exploration_config()['storage_root'])


def add_job_log(job_id,message):
    logs=job_logs.setdefault(job_id,[])
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    del logs[:-100]


def status(job_id):
    if job_id not in jobs:raise HTTPException(404,'Job not found')
    return JobStatus(job_id=job_id,**{k:v for k,v in jobs[job_id].items() if k in JobStatus.model_fields and k!='job_id'})


def get_available_models():
    models=[]
    if os.getenv('LOCAL_TEXT_BASE_URL'):models.append(os.getenv('LOCAL_TEXT_MODEL','qwen3.8-27b'))
    if os.getenv('LOCAL_VISION_BASE_URL'):models.append(os.getenv('LOCAL_VISION_MODEL','qwen3-vl-30b-a3b'))
    return models+['claude-sonnet-4-20250514','claude-opus-4.5','gpt-4o-2024-08-06',
        'gpt-4.1-2025-04-14','gpt-4.1-mini-2025-04-14','glm-4.6','glm-4.6v','glm-4.5','glm-4.5-air','glm-4.5v','glm-4','glm-4v']


def run_poster_generation(job_id,config,files):
    if not config.get('sample_generation', True):
        raise ValueError('Rubrics_poster supports independent samples only')
    job=jobs[job_id]
    job_dir=Path(tempfile.mkdtemp(prefix='rubrics_poster_upload_'))
    try:
        job.update(status='processing',progress=10,message='Preparing paper')
        paths={}
        for name,key,suffix in [('pdf','pdf','.pdf'),('logo','logo','.png'),('aff_logo','aff_logo','.png')]:
            paths[name]=job_dir/(name+suffix);paths[name].write_bytes(files[key])
        state=create_state(str(paths['pdf']),config['text_model'],config['vision_model'],
            config['poster_width'],config['poster_height'],'',str(paths['logo']),str(paths['aff_logo']),
            poster_name=Path(files['pdf_filename']).stem)
        job['poster_name']=state['poster_name']
        state['timing_metrics'].pipeline_start=time.time()
        control=RunControl();loop_controls[job_id]=control
        def update(payload):
            for key in ('run_id','planned_samples','finalized_samples','rendered_samples','scored_samples',
                        'failed_samples','iteration','layout_family','results'):
                if key in payload:job[key]=payload[key]
            job['progress']=int(100*job.get('finalized_samples',0)/max(1,job.get('planned_samples',1)))
            job['message']=payload.get('message','Generating independent sample')
            add_job_log(job_id,job['message'])
        result=PosterExplorationRunner(control=control,storage=store(),samples=config['samples'],
            run_id=config['run_id'],random_seed=config['random_seed'],status_callback=update).run(state)
        run=result['run_state'];update(run)
        job['status']={'COMPLETED':'completed','PAUSED':'paused','FAILED':'failed'}[run['status']]
        job['output_dir']=result['output_dir']
        job['message']=f"{run['rendered_samples']} posters saved; {run['scored_samples']} scored; {run['status']}"
        result['timing_metrics'].pipeline_end=time.time();save_timing_log(result)
        archive=job_dir/'posters.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
            for record in job.get('results',[]):
                if not record.get('poster_id'):continue
                directory=store().verify_poster(record['poster_id'])
                for path in directory.rglob('*'):
                    if path.is_file():output.write(path,Path('posters')/directory.name/path.relative_to(directory))
            output.writestr('run_state.json',json.dumps(result['run_state'],ensure_ascii=False,indent=2))
        job['output_file']=str(archive)
    except Exception as exc:
        job.update(status='failed',error=str(exc),message=str(exc))
        add_job_log(job_id,str(exc))
    finally:
        loop_controls.pop(job_id,None)


@app.get('/')
def root():return {'message':'Rubrics_poster WebUI API'}


@app.get('/models')
def models():
    return {'models':get_available_models(),
            'default_text_model':os.getenv('LOCAL_TEXT_MODEL','qwen3.8-27b') if os.getenv('LOCAL_TEXT_BASE_URL') else 'gpt-4o-2024-08-06',
            'default_vision_model':os.getenv('LOCAL_VISION_MODEL','qwen3-vl-30b-a3b') if os.getenv('LOCAL_VISION_BASE_URL') else 'gpt-4o-2024-08-06'}


@app.post('/generate',response_model=JobStatus)
async def generate_poster(request:Request,background_tasks:BackgroundTasks,
    text_model:str=Form(...),vision_model:str=Form(...),poster_width:float=Form(...),poster_height:float=Form(...),
    sample_generation:bool=Form(True),samples:Optional[int]=Form(None),run_id:Optional[str]=Form(None),
    random_seed:Optional[int]=Form(None),pdf_file:UploadFile=File(...),logo_file:UploadFile=File(...),aff_logo_file:UploadFile=File(...)):
    if not sample_generation:raise HTTPException(400,'Rubrics_poster supports independent samples only')
    old={'continuous_loop','resume_mode','campaign_id','batch_iterations','batch_mode','target_lineage_id','batch_id','new_batch'}
    if old.intersection(await request.form()):raise HTTPException(400,'Legacy Campaign/Batch parameters are retired; use sample_generation, samples and run_id')
    if text_model not in get_available_models() or vision_model not in get_available_models():raise HTTPException(400,'Invalid model')
    if samples is not None and samples<1:raise HTTPException(400,'samples must be positive')
    if poster_height<=0 or not 1.4<=poster_width/poster_height<=2:raise HTTPException(400,'Poster ratio must be between 1.4 and 2.0')
    if not pdf_file.filename or not pdf_file.filename.lower().endswith('.pdf'):raise HTTPException(400,'Paper must be a PDF')
    if run_id:
        try:read_json(store().run_path(run_id)/'manifest.json')
        except (OSError,ValueError):raise HTTPException(404,'Independent sample run not found')
    job_id=uuid.uuid4().hex
    jobs[job_id]={'status':'pending','progress':0,'message':'Queued', 'sample_generation':sample_generation}
    config=dict(text_model=text_model,vision_model=vision_model,poster_width=poster_width,poster_height=poster_height,
                sample_generation=sample_generation,samples=samples,run_id=run_id or None,random_seed=random_seed)
    files=dict(pdf=await pdf_file.read(),logo=await logo_file.read(),aff_logo=await aff_logo_file.read(),pdf_filename=pdf_file.filename)
    background_tasks.add_task(run_poster_generation,job_id,config,files)
    return status(job_id)


@app.get('/status/{job_id}',response_model=JobStatus)
def get_job_status(job_id:str):return status(job_id)


@app.get('/logs/{job_id}')
def get_job_logs(job_id:str):
    status(job_id);return {'logs':job_logs.get(job_id,[])}


@app.post('/control/{job_id}/{action}')
def control_loop(job_id:str,action:str):
    status(job_id)
    control=loop_controls.get(job_id)
    if control is None:raise HTTPException(400,'No active sample generation; use run_id to resume a stopped run')
    if action=='pause':control.pause();jobs[job_id]['status']='paused'
    elif action=='resume':control.resume();jobs[job_id]['status']='processing'
    elif action in {'stop','force-stop'}:control.request_stop(force=action=='force-stop');jobs[job_id]['status']='stopping'
    else:raise HTTPException(400,'Unknown control action')
    return {'job_id':job_id,'action':action,'status':jobs[job_id]['status']}


@app.get('/runs/{run_id}')
def get_run(run_id:str):
    try:
        directory=store().run_path(run_id)
        return {'manifest':read_json(directory/'manifest.json'),'state':read_json(directory/'run_state.json'),
                'results':store().results(run_id)}
    except (OSError,ValueError):raise HTTPException(404,'Independent sample run unavailable')


@app.get('/runs/{run_id}/posters/{poster_id}/{filename}')
def get_sample_artifact(run_id:str,poster_id:str,filename:str):
    if filename not in {'poster.png','poster.pptx','template.json','template.png','template.pptx','evaluation.json','provenance.json'}:
        raise HTTPException(404,'Artifact not found')
    data=get_run(run_id)
    if not any(r.get('poster_id')==poster_id for r in data['results']):raise HTTPException(404,'Poster not in this run')
    return FileResponse(store().verify_poster(poster_id)/filename)


@app.get('/poster/{job_id}')
def get_poster_image(job_id:str):
    status(job_id);job=jobs[job_id]
    if job.get('sample_generation'):
        records=[r for r in job.get('results',[]) if r.get('poster_id')]
        if not records:raise HTTPException(404,'No saved poster yet')
        return get_sample_artifact(job['run_id'],records[-1]['poster_id'],'poster.png')
    path=Path(job.get('output_dir') or '')/(job.get('poster_name','poster')+'.png')
    if not path.is_file():raise HTTPException(404,'Poster not found')
    return FileResponse(path,media_type='image/png')


@app.get('/download/{job_id}')
def download_result(job_id:str):
    status(job_id);path=jobs[job_id].get('output_file')
    if not path or not Path(path).is_file():raise HTTPException(404,'Archive not available yet')
    return FileResponse(path,media_type='application/zip',filename='posters.zip')


@app.get('/files/{job_id}')
def get_json_files(job_id:str):
    status(job_id);job=jobs[job_id]
    if job.get('sample_generation') and job.get('run_id'):return {'files':get_run(job['run_id'])}
    path=Path(job.get('output_dir') or '')/'content'
    return {'files':{p.name:read_json(p) for p in path.glob('*.json')}}
