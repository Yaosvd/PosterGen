import pytest

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
        files={k:('Win-Win: A 360° Study.pdf' if k=='pdf_file' else 'logo.png',b'synthetic') for k in ('pdf_file','logo_file','aff_logo_file')})
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
            assert item['poster_collection'] == 'seed posters'
            prefix=f"posters/seed posters/{item['grouping']}/{item['paper_directory']}/{item['poster_id']}/"
            assert prefix+'poster.png' in deck.namelist()
            assert prefix+'template.pptx' in deck.namelist()
        assert len({item['paper_id'] for item in job['results']}) == 1
        assert all(item['paper_title'] == item['paper_directory'] == 'Win-Win: A 360° Study'
                   for item in job['results'])
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


@pytest.mark.parametrize("family_id", ["timeline_stage_narrative", "result_dashboard_cards"])
def test_removed_family_saved_results_remain_readable(tmp_path, monkeypatch, family_id):
    from src.workflow.exploration_store import ExplorationStore
    from test_poster_grouping import bundle, fingerprints
    from utils.persistence import _atomic_json, file_hash

    storage = ExplorationStore(tmp_path / "samples")
    monkeypatch.setattr(api, "store", lambda: storage)
    directory, result = bundle(storage, "historical")
    result["layout_family"] = family_id
    _atomic_json(directory / "provenance.json", result)
    _atomic_json(directory / "bundle.json", {"files": {
        p.name: file_hash(p) for p in directory.iterdir()
        if p.is_file() and p.name != "bundle.json"}})
    storage.finalize("run_test", "historical", result)
    _atomic_json(storage.run_path("run_test") / "manifest.json", {"historical": True})
    _atomic_json(storage.run_path("run_test") / "run_state.json", {"status": "COMPLETED"})
    before = fingerprints(directory)

    client = TestClient(api.app)
    response = client.get("/runs/run_test")
    assert response.status_code == 200
    assert response.json()["results"][0]["layout_family"] == family_id
    for filename in ("poster.png", "poster.pptx", "template.json", "evaluation.json", "provenance.json"):
        response = client.get(f"/runs/run_test/posters/historical/{filename}")
        assert response.status_code == 200
        assert response.content == (directory / filename).read_bytes()
    assert fingerprints(directory) == before


def test_current_scoring_policy_endpoint_reports_derived_scale():
    from src.critic.scoring import current_policy, report_policy_metadata

    response = TestClient(api.app).get('/scoring-policy')
    assert response.status_code == 200
    assert response.json() == report_policy_metadata(current_policy())
    assert response.json()['score_maximum'] == 96
    assert response.json()['high_score_threshold'] == 82


def test_mixed_scoring_versions_keep_api_and_zip_groups_and_bytes(tmp_path, monkeypatch):
    import io
    import json
    import zipfile
    from discrete_score_fixtures import grade_report
    from src.critic.scoring import current_policy, report_policy_metadata
    from src.workflow.exploration_store import ExplorationStore
    from src.workflow.poster_grouping import complete_score
    from test_poster_grouping import bundle, fingerprints
    from utils.persistence import _atomic_json, file_hash

    storage = ExplorationStore(tmp_path / 'samples')
    monkeypatch.setattr(api, 'store', lambda: storage)
    policy = current_policy()

    def discrete_report(low=False):
        overrides = {key: criterion['target_grade'] for key, criterion in policy['criteria'].items()}
        if low:
            overrides['font_legibility'] = 1
        report = grade_report(**overrides)
        assert complete_score(report)
        return report

    reports = [('historical80', None), ('current81', discrete_report(low=True)),
               ('current82', discrete_report())]
    before = {}
    for poster_id, report in reports:
        directory, result = bundle(storage, poster_id)
        if report is not None:
            result.update(report_policy_metadata(policy), score=report['overall_score'])
            _atomic_json(directory / 'evaluation.json', report)
            _atomic_json(directory / 'provenance.json', result)
            _atomic_json(directory / 'bundle.json', {'files': {
                p.name: file_hash(p) for p in directory.iterdir()
                if p.is_file() and p.name != 'bundle.json'}})
        storage.finalize('run_test', poster_id, result)
        before[poster_id] = fingerprints(directory)
    _atomic_json(storage.run_path('run_test') / 'manifest.json', {'historical': True})
    _atomic_json(storage.run_path('run_test') / 'run_state.json', {'status': 'COMPLETED'})

    class SavedResultsRunner:
        def run(self, state):
            run = {'run_id': 'run_test', 'status': 'COMPLETED', 'planned_samples': 3,
                   'finalized_samples': 3, 'rendered_samples': 3, 'scored_samples': 3,
                   'failed_samples': 0, 'results': storage.results('run_test')}
            return {'run_state': run, 'output_dir': str(tmp_path),
                    'timing_metrics': state['timing_metrics']}

    monkeypatch.setattr(api, 'PosterExplorationRunner', lambda **kwargs: SavedResultsRunner())
    monkeypatch.setattr(api, 'save_timing_log', lambda result: None)
    client = TestClient(api.app)
    response = client.post('/generate', data={
        'text_model': 'gpt-4o-2024-08-06', 'vision_model': 'gpt-4o-2024-08-06',
        'poster_width': 54, 'poster_height': 36, 'samples': 3},
        files={key: ('test.pdf' if key == 'pdf_file' else 'logo.png', b'synthetic')
               for key in ('pdf_file', 'logo_file', 'aff_logo_file')})
    job_id = response.json()['job_id']
    job = client.get('/status/' + job_id).json()
    assert job['status'] == 'completed', job
    expected = {'historical80': (80, 100, 80, 'high_score'),
                'current81': (81, 96, 82, 'low_score'),
                'current82': (82, 96, 82, 'high_score')}
    for records in (job['results'], client.get('/runs/run_test').json()['results']):
        for result in records:
            assert (result['score'], result['score_maximum'], result['high_score_threshold'],
                    result['grouping']) == expected[result['poster_id']]
    with zipfile.ZipFile(io.BytesIO(client.get('/download/' + job_id).content)) as archive:
        archived = json.loads(archive.read('run_state.json'))['results']
        assert archived == job['results']
        for result in archived:
            prefix = (f"posters/{result['poster_collection']}/{result['grouping']}/"
                      f"{result['paper_directory']}/{result['poster_id']}/")
            directory = storage.verify_poster(result['poster_id'])
            for filename in ('evaluation.json', 'provenance.json', 'poster.png'):
                assert archive.read(prefix + filename) == (directory / filename).read_bytes()
    for poster_id, original in before.items():
        assert fingerprints(storage.verify_poster(poster_id)) == original
