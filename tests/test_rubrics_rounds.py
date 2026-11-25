"""Exercise the round coordinator with durable CPU-only worker fixtures."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from src.critic.scoring import IMPORTANT
from src.rubrics import rounds
from src.rubrics.library import LibraryStore
from src.rubrics.storage import read,write
from utils.persistence import _atomic_json,read_json,file_hash
from test_rubrics_framework import rule
from discrete_score_fixtures import grade_report, scored_result


@pytest.mark.parametrize('custom_output,infra_failure,target_group,paper_count', [
    (False, False, 'high_score', 20), (True, False, 'high_score', 20),
    (False, True, 'high_score', 20), (True, True, 'high_score', 20),
    (True, False, 'complete_score', 20), (True, False, 'complete_score', 15)])
def test_round_coordinator_seals_all_scores_at_quota_or_pauses_infrastructure(monkeypatch,tmp_path,infra_failure,custom_output,capsys,target_group,paper_count):
    import fitz
    from rubrics_poster import batch
    import src.workflow.exploration_store as stores
    monkeypatch.setattr(batch,'fingerprint',lambda:'offline-code-identity')
    monkeypatch.setattr(batch,'gpu_uuid',lambda index:f'GPU-OFFLINE-{index}')
    monkeypatch.setattr(rounds,'check_glm_endpoints',lambda:None)
    folder=tmp_path/'input';folder.mkdir()
    for i in range(paper_count):
        doc=fitz.open();page=doc.new_page();page.insert_text((30,30),str(i));doc.save(folder/f'{i}.pdf');doc.close()
    storage=tmp_path/'storage'
    LibraryStore(storage/'rubrics').publish([rule()],parent_version=None,source_batch_digest='offline')
    if custom_output:
        import json
        from rubrics_poster.iteration import main
        output=storage/'posters'/'posters round1'
        assert main(['--storage-root',str(storage),'create','--input-folder',str(folder),
                     '--poster-output',str(output),'--target-group',target_group,'--paper-count',str(paper_count),'--generate-only'])==0
        planned=json.loads(capsys.readouterr().out)
        assert planned['status']=='PLANNED'
        root=Path(planned['round'])
        assert not output.exists()
    else:
        root=rounds.create(folder,storage,generate_only=True)
        output=storage/'posters'/'posters round1'
    manifest=read(root/'manifest.json')
    assert manifest['poster_output']==str(output.resolve())
    assert read(root/'state.json')['status']=='PLANNED'
    assert read(root/'state.json')['attempts']==[]
    assert not (root/'jobs').exists()
    monkeypatch.setattr(rounds.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*2**30))
    monkeypatch.setattr(rounds.time,'sleep',lambda s:None)
    class Store:
        def __init__(self,root,poster_output):self.posters=Path(poster_output)
        def verify_poster(self,pid):return self.posters/pid
    monkeypatch.setattr(stores,'ExplorationStore',Store)
    def inspect(job,storage):
        return read_json(job/'fixture_result.json') if (job/'fixture_result.json').exists() else {'qualified':False,'family':None}
    monkeypatch.setattr(batch,'inspect_attempt',inspect)
    launches=[]
    targets = {key: 3 for key in IMPORTANT}
    reports = {False: grade_report(2, **targets, element_alignment=1), True: grade_report(2, **targets)}
    assert [r['overall_score'] for r in reports.values()] == [81, 82]
    class Child:
        returncode=0
        def poll(self):return 0
        def send_signal(self,*a):pass
        def wait(self):return 0
    def worker(command,**kwargs):
        job=Path(command[-1]);spec=read_json(job/'task.json');launches.append(spec)
        if infra_failure:
            kwargs['stdout'].write('CUDA is not available\n');kwargs['stdout'].flush()
            _atomic_json(job/'outcome.json',{'status':'FAILED'})
            _atomic_json(job/'fixture_result.json',{'qualified':False,'family':None})
            return Child()
        pid='fixture_'+job.name;bundle=Path(spec['poster_output'])/pid;bundle.mkdir(parents=True)
        Image.new('RGB',(5,5),'white').save(bundle/'poster.png');(bundle/'poster.pptx').write_bytes(b'offline')
        report = reports[not job.name.endswith('_001')]
        score = report['overall_score']
        _atomic_json(bundle/'evaluation.json',report)
        _atomic_json(bundle/'provenance.json',scored_result(report, **{'poster_id':pid,'sample_mode':spec['mode'],
            'generation_rubrics':spec['rubrics_snapshot']['version'],'round_identity':spec['round_identity'],
            'paper_id':'pdf_'+spec['paper_sha256']}))
        write(bundle/'refinement/paper.json',{'original_text':'fixture paper'})
        write(bundle/'refinement/selection.json',{'variant':'P0','rubrics':spec['rubrics_snapshot']['version'],
            'artifact_hashes':{k:file_hash(bundle/('poster.'+k)) for k in ('pptx','png')}})
        _atomic_json(job/'fixture_result.json',{'qualified':score>=spec['scoring_policy']['high_score_threshold'],'complete_score':True,
            'family':spec['forced_family'],'status':'scored','poster_id':pid})
        _atomic_json(job/'outcome.json',{'status':'COMPLETED'})
        return Child()
    monkeypatch.setattr(rounds.subprocess,'Popen',worker)
    sealed=rounds.run(root)
    state=read(root/'state.json')
    resources = read_json(root/'resources.json')
    frozen_batch = manifest['config']['batch']
    assert resources['limits'] == {
        'marker': frozen_batch['marker_slots'],
        'model': frozen_batch['model_slots'],
        'render': frozen_batch['render_slots'],
    }
    assert resources['marker_gpu_uuids'] == state['marker_gpu_uuids'] == [
        'GPU-OFFLINE-3', 'GPU-OFFLINE-2', 'GPU-OFFLINE-2']
    if infra_failure:
        assert sealed is None and state['status']=='PAUSED'
        assert state['pause_reason']=='infrastructure_unavailable'
        assert len(launches)<=30
        assert not (root/'seal.json').exists()
    else:
        per_paper = 21 if target_group == 'high_score' else 20
        expected_total = paper_count * per_paper
        assert len(launches)==expected_total and sealed==root/'seal.json'
        assert state['status']=='SEALED' and state['next_input_status']=='WAITING_NEXT_INPUT'
        assert state['postprocess_trigger']=='manual'
        assert read(sealed)['schema_version'] == (5 if paper_count != 20 else 4 if target_group == 'high_score' else 2)
        assert len(read(sealed)['samples'])==expected_total
        highs = Counter(a['paper_index'] for a in state['attempts'] if a['result']['qualified'])
        assert highs == dict.fromkeys(range(paper_count), per_paper - 1)
        papers_in_first_wave = Counter(s['paper_path'] for s in launches[:30])
        assert len(papers_in_first_wave) == paper_count and max(papers_in_first_wave.values()) == 2
        assert len({s['paper_path'] for s in launches})==paper_count
        assert all(sum(s['paper_path']==p['paper_path'] for s in launches)==per_paper for p in manifest['papers'])
        assert rounds.run(root)==sealed and len(launches)==expected_total
    assert all(s['round_identity']['round_id']==manifest['round_id'] for s in launches)
    assert all(s['scoring_policy']==manifest['scoring_policy'] for s in launches)
    assert all(s['poster_output']==str(output.resolve()) for s in launches)
    if custom_output:
        assert not (root/'posters').exists()


def test_resume_settles_last_attempt_at_cap_before_marking_incomplete(monkeypatch, tmp_path):
    import fitz
    from rubrics_poster import batch

    monkeypatch.setattr(batch, 'fingerprint', lambda: 'offline')
    monkeypatch.setattr(batch, 'gpu_uuid', lambda i: f'GPU-{i}')
    monkeypatch.setattr(rounds, 'check_glm_endpoints', lambda: None)
    monkeypatch.setattr(rounds.shutil, 'disk_usage', lambda _: SimpleNamespace(free=100 * 2**30))
    papers = tmp_path / 'papers'
    papers.mkdir()
    for i in range(20):
        with fitz.open() as doc:
            doc.new_page().insert_text((30, 30), str(i))
            doc.save(papers / f'{i}.pdf')
    storage = tmp_path / 'store'
    LibraryStore(storage / 'rubrics').publish([rule()], parent_version=None, source_batch_digest='fixture')
    root = rounds.create(papers, storage, generate_only=True)
    manifest, state = read(root / 'manifest.json'), read(root / 'state.json')
    results = {}
    while (a := rounds.reserve(state, manifest, ['a'])) is not None:
        high = a['paper_index'] != 19 or a['number'] < 20
        result = {'qualified': high, 'complete_score': True, 'status': 'scored'}
        results[Path(a['path']).name] = result
        if a['number'] == 200:
            break  # The last worker has persisted its score before the coordinator paused.
        a.update(finished=True, result=result)
    assert a['paper_index'] == 19 and a['number'] == 200
    state.update(status='PAUSED', cooldowns={'19': 10})
    write(root / 'state.json', state)
    times = iter([0, 0, 0, 10])
    monkeypatch.setattr(rounds, 'time', SimpleNamespace(time=lambda: next(times, 10), sleep=lambda _: None))
    monkeypatch.setattr(batch, 'inspect_attempt', lambda job, _: results[job.name])
    monkeypatch.setattr(rounds.subprocess, 'Popen', lambda *args, **kw: pytest.fail('Attempt was already scored'))
    assert rounds.run(root) is None
    state = read(root / 'state.json')
    assert state['status'] == 'INCOMPLETE' and not (root / 'seal.json').exists()
    assert all(a['finished'] for a in state['attempts'])
    assert sum(a['paper_index'] == 19 for a in state['attempts']) == 200
    assert sum(a['result']['qualified'] for a in state['attempts']) == 399


@pytest.mark.parametrize('generate_only', [False, True])
@pytest.mark.parametrize('sealed', [False, True])
def test_iteration_run_never_starts_mining_even_on_resume(monkeypatch, tmp_path, capsys, generate_only, sealed):
    import json
    from rubrics_poster.iteration import main
    from src.rubrics import mining

    root = tmp_path/'round'
    write(root/'manifest.json', {'generate_only':generate_only, 'storage_root':str(tmp_path)})
    state = {'status':'SEALED' if sealed else 'INCOMPLETE', 'next_input_status':'WAITING_NEXT_INPUT'}
    write(root/'state.json', state)
    monkeypatch.setattr(rounds, 'run', lambda path: root/'seal.json' if sealed else None)
    def forbidden(*args, **kwargs):
        pytest.fail('run must never start batch-end processing')
    monkeypatch.setattr(mining, 'process', forbidden)
    for _ in range(2):
        assert main(['run', str(root)]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result['status'] == state['status']
        if sealed:
            assert result['postprocess_trigger'] == 'manual'
            assert result['seal'] == str(root/'seal.json')
        else:
            assert result == state


def test_iteration_postprocess_remains_an_explicit_command(monkeypatch, tmp_path, capsys):
    import json
    from rubrics_poster.iteration import main
    from src.rubrics import mining

    root = tmp_path/'round'
    write(root/'manifest.json', {'storage_root':str(tmp_path)})
    calls = []
    def process(seal_path, library_root, *, config):
        calls.append((seal_path, library_root))
        return {'status':'NO_NEW_RULES'}
    monkeypatch.setattr(mining, 'process', process)
    assert main(['postprocess', str(root)]) == 0
    assert calls == [(root/'seal.json', tmp_path/'rubrics')]
    assert json.loads(capsys.readouterr().out)['status'] == 'NO_NEW_RULES'
