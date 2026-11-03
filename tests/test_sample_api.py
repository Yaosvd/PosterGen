from fastapi.testclient import TestClient
from webui.backend import sample_api as api
from src.workflow.run_control import RunControl


def test_old_batch_parameters_are_rejected_without_starting_generation(monkeypatch):
    monkeypatch.setattr(api,'run_poster_generation',lambda *a: (_ for _ in ()).throw(AssertionError('no generation')))
    client=TestClient(api.app)
    response=client.post('/generate',data={'text_model':'gpt-4o-2024-08-06','vision_model':'gpt-4o-2024-08-06',
         'poster_width':54,'poster_height':36,'batch_mode':'improve'},
         files={k:('test.pdf' if k=='pdf_file' else 'test.png',b'test') for k in ('pdf_file','logo_file','aff_logo_file')})
    assert response.status_code==400 and 'retired' in response.text


def test_sample_configuration_reaches_new_runner_without_legacy_options(monkeypatch):
    received=[]
    monkeypatch.setattr(api,'run_poster_generation',lambda job,config,files:received.append(config))
    client=TestClient(api.app)
    response=client.post('/generate',data={'text_model':'gpt-4o-2024-08-06','vision_model':'gpt-4o-2024-08-06',
         'poster_width':54,'poster_height':36,'samples':3,'random_seed':17},
         files={k:('test.pdf' if k=='pdf_file' else 'test.png',b'test') for k in ('pdf_file','logo_file','aff_logo_file')})
    assert response.status_code==200 and received[0]['samples']==3 and received[0]['random_seed']==17
    assert 'batch_mode' not in received[0]
    assert client.get('/campaigns/old/batches').status_code==404


def test_controls_and_missing_run_are_scoped_to_new_runs():
    client=TestClient(api.app)
    api.jobs['test']={'status':'processing','progress':10,'message':'working'}
    control=RunControl();api.loop_controls['test']=control
    assert client.post('/control/test/pause').status_code==200 and control.paused
    assert client.post('/control/test/resume').status_code==200 and not control.paused
    assert client.post('/control/test/force-stop').status_code==200 and control.force_stop_requested
    assert client.get('/runs/campaign_old').status_code==404
    assert client.get('/runs/../posters/foreign/secret').status_code==404
    del api.jobs['test'];del api.loop_controls['test']


def test_all_low_score_posters_are_previewable_and_downloaded_with_templates(tmp_path,monkeypatch):
    import io
    import zipfile
    from src.workflow.exploration_runner import PosterExplorationRunner
    from src.workflow.exploration_store import ExplorationStore
    from test_exploration_samples import render_sample,critic_with_scores,prepare_sample
    storage=ExplorationStore(tmp_path/'samples')
    monkeypatch.setattr(api,'store',lambda:storage)
    def foundation(state):
        state.update(verification_passed=True,raw_text='Synthetic evidence',
            evidence_bank={'items':[{'evidence_id':'e1','source_excerpt':'Synthetic evidence'}]},
            verified_claims={'claims':[{'claim_id':'c1','text':'A verified observation.','evidence_ids':['e1']}]},
            narrative_plan={'sections':[{'section_id':'s1','narrative_role':'results','claim_ids':['c1']}]})
        return state
    def build(**kwargs):
        return PosterExplorationRunner(preparation_nodes=[prepare_sample], **kwargs,paper_nodes=[foundation],design_nodes=[render_sample],
                                       critic=critic_with_scores([8,9]))
    monkeypatch.setattr(api,'PosterExplorationRunner',build)
    client=TestClient(api.app)
    response=client.post('/generate',data={'text_model':'gpt-4o-2024-08-06','vision_model':'gpt-4o-2024-08-06',
        'poster_width':54,'poster_height':36,'samples':2},
        files={k:('paper.pdf' if k=='pdf_file' else 'logo.png',b'synthetic') for k in ('pdf_file','logo_file','aff_logo_file')})
    job_id=response.json()['job_id']
    job=client.get('/status/'+job_id).json()
    assert job['status']=='completed' and job['rendered_samples']==2
    assert client.get('/poster/'+job_id).status_code==200
    low=job['results'][0]
    root=f"/runs/{job['run_id']}/posters/{low['poster_id']}"
    assert client.get(root+'/poster.png').status_code==200
    assert client.get(root+'/template.json').json()['purpose']=='inspection_only'
    assert client.get(root+'/template.pptx').status_code==200
    archive=client.get('/download/'+job_id)
    with zipfile.ZipFile(io.BytesIO(archive.content)) as deck:
        for item in job['results']:
            prefix=f"posters/{item['poster_id']}/"
            assert prefix+'poster.png' in deck.namelist()
            assert prefix+'template.pptx' in deck.namelist()
    assert client.get(root.replace(job['run_id'],'run_other')+'/poster.png').status_code==404


def test_explicit_paper_cache_fields_reach_runner_config(monkeypatch):
    received=[]
    monkeypatch.setattr(api,'run_poster_generation',lambda job,config,files:received.append(config))
    client=TestClient(api.app)
    payload={'text_model':'gpt-4o-2024-08-06','vision_model':'gpt-4o-2024-08-06',
             'poster_width':54,'poster_height':36,'samples':2,
             'paper_cache_run_id':'run_donor','paper_cache_sample_id':'sample_000002'}
    files={k:('test.pdf' if k=='pdf_file' else 'logo.png',b'test') for k in ('pdf_file','logo_file','aff_logo_file')}
    assert client.post('/generate',data=payload,files=files).status_code==200
    assert received[0]['paper_cache_run_id']=='run_donor' and received[0]['paper_cache_sample_id']=='sample_000002'
    del payload['paper_cache_run_id']
    assert client.post('/generate',data=payload,files=files).status_code==400
