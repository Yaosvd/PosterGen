"""Exercise the round coordinator with durable CPU-only worker fixtures."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from src.rubrics import rounds
from src.rubrics.library import LibraryStore
from src.rubrics.storage import read,write
from utils.persistence import _atomic_json,read_json,file_hash
from test_rubrics_framework import rule


@pytest.mark.parametrize('infra_failure',[False,True])
def test_round_coordinator_seals_exactly_400_or_pauses_infrastructure(monkeypatch,tmp_path,infra_failure):
    import fitz
    from rubrics_poster import batch
    import src.workflow.exploration_store as stores
    monkeypatch.setattr(batch,'fingerprint',lambda:'offline-code-identity')
    monkeypatch.setattr(batch,'gpu_uuid',lambda index:'GPU-OFFLINE')
    monkeypatch.setattr(rounds,'check_glm_endpoints',lambda:None)
    folder=tmp_path/'input';folder.mkdir()
    for i in range(20):
        doc=fitz.open();page=doc.new_page();page.insert_text((30,30),str(i));doc.save(folder/f'{i}.pdf');doc.close()
    storage=tmp_path/'storage'
    LibraryStore(storage/'rubrics').publish([rule()],parent_version=None,source_batch_digest='offline')
    root=rounds.create(folder,storage,generate_only=True)
    manifest=read(root/'manifest.json')
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
        score=90 if spec['seed']%2 else 50
        _atomic_json(bundle/'evaluation.json',{'evaluation_status':'complete','overall_score':score})
        _atomic_json(bundle/'provenance.json',{'poster_id':pid,'sample_mode':spec['mode'],
            'generation_rubrics':spec['rubrics_snapshot']['version'],'round_identity':spec['round_identity'],
            'paper_id':'pdf_'+spec['paper_sha256'],'status':'scored','score':score})
        write(bundle/'refinement/paper.json',{'original_text':'fixture paper'})
        write(bundle/'refinement/selection.json',{'variant':'P0','rubrics':spec['rubrics_snapshot']['version'],
            'artifact_hashes':{k:file_hash(bundle/('poster.'+k)) for k in ('pptx','png')}})
        _atomic_json(job/'fixture_result.json',{'qualified':score>=80,'complete_score':True,
            'family':spec['forced_family'],'status':'scored','poster_id':pid})
        _atomic_json(job/'outcome.json',{'status':'COMPLETED'})
        return Child()
    monkeypatch.setattr(rounds.subprocess,'Popen',worker)
    sealed=rounds.run(root)
    state=read(root/'state.json')
    if infra_failure:
        assert sealed is None and state['status']=='PAUSED'
        assert state['pause_reason']=='infrastructure_unavailable'
        assert len(launches)<=30
        assert not (root/'seal.json').exists()
    else:
        assert len(launches)==400 and sealed==root/'seal.json'
        assert state['status']=='SEALED' and state['next_input_status']=='WAITING_NEXT_INPUT'
        assert state['postprocess_trigger']=='manual'
        assert len(read(sealed)['samples'])==400
        assert len({s['paper_path'] for s in launches})==20
        assert all(sum(s['paper_path']==p['paper_path'] for s in launches)==20 for p in manifest['papers'])
        assert rounds.run(root)==sealed and len(launches)==400
    assert all(s['round_identity']['round_id']==manifest['round_id'] for s in launches)


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
