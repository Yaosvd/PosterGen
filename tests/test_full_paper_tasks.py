"""Full PDF/Logo task entry, explicit caches and same-task recovery without services."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from src.state.poster_state import create_state
from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.exploration_store import ExplorationStore
from src.workflow.run_control import RunControl
from src.workflow.task_inputs import load_task_file, VERSION
from utils.persistence import _atomic_json, digest, read_json
from test_exploration_samples import prepare_sample, render_sample, critic_with_scores


def inputs(tmp_path, name='one'):
    root = tmp_path / name
    root.mkdir(exist_ok=True)
    pdf = root / 'paper.pdf'
    pdf.write_bytes(name.encode())
    logo = root / 'logo.png'
    logo.write_bytes(('logo-' + name).encode())
    return create_state(str(pdf), width=54, height=36, logo_path=str(logo), poster_name=name)


def extractor(calls, control=None):
    def paper(state):
        sid = state['iteration_context']['sample_id']
        for key in ('raw_text', 'story_board', 'critic_report', 'editorial_candidate',
                    'sample_family', 'color_scheme', 'source_extraction_report'):
            assert not state.get(key), key
        assert not state['errors']
        calls.append(('paper', sid, Path(state['pdf_path']).read_bytes()))
        root = Path(state['output_dir']) / 'assets'
        root.mkdir(parents=True, exist_ok=True)
        asset = root / 'original.png'
        asset.write_bytes(b'paper-original-image')
        state.update(raw_text='Extraction ' + str(len(calls)),
            images={'1': {'path': str(asset), 'aspect': 1}},
            evidence_bank={'items': [{'evidence_id': 'e1', 'source_excerpt': 'Original paper'}]})
        if control is not None:
            control.request_stop(force=True)
        return state
    return paper


def runner(tmp_path, calls, **kwargs):
    return PosterExplorationRunner(storage=ExplorationStore(tmp_path / 'store'),
        paper_nodes=[extractor(calls)], preparation_nodes=[prepare_sample],
        design_nodes=[render_sample], critic=critic_with_scores([20] * 10), **kwargs)


def test_critic_save_then_next_task_restarts_at_pdf_and_isolates_material(tmp_path):
    calls = []
    gen = runner(tmp_path, calls, samples=2)
    def score(state):
        calls.append(('critic', state['iteration_context']['sample_id']))
        state['raw_text'] = 'Do not propagate a previous poster mutation'
        return critic_with_scores([4])(state)
    gen.critic = score
    def event(payload):
        if (payload.get('progress_event') or {}).get('type') == 'sample_saved':
            calls.append(('saved', payload['sample_id']))
    gen.status_callback = event
    result = gen.run(inputs(tmp_path))
    assert [(x[0], x[1]) for x in calls] == [
        ('paper','sample_000001'), ('critic','sample_000001'), ('saved','sample_000001'),
        ('paper','sample_000002'), ('critic','sample_000002'), ('saved','sample_000002')]
    assert result['run_state']['rendered_samples'] == 2
    assert not (gen.storage.run_path(gen.run_id) / 'paper_foundation').exists()
    for row in result['run_state']['results']:
        sid = row['sample_id']
        root = gen.storage.sample_path(gen.run_id, sid)
        receipt = read_json(root / 'task_inputs.json')
        assert row['task_input_digest'] == receipt['digest']
        assert row['task_entry_policy'] == VERSION
        assert (root / 'inputs/pdf_path.pdf').read_bytes() == b'one'
        paper = gen.storage.paper_foundation(gen.run_id, sid)
        assert paper['raw_text'].startswith('Extraction ')
        assert 'critic_report' not in paper and 'story_board' not in paper
        assert Path(paper['images']['1']['path']).is_relative_to(root)
        gen.storage.verify_poster(row['poster_id'])


def test_different_papers_logos_parameters_and_seeds_follow_their_own_task(tmp_path):
    calls=[]
    a, b = inputs(tmp_path, 'a'), inputs(tmp_path, 'b')
    b['poster_height'] = 30
    b['text_model'].temperature = .45
    b['task_random_seed'] = 81
    gen = runner(tmp_path,calls,input_states=[a,b],random_seed=7)
    result = gen.run(a)
    assert [x[2] for x in calls] == [b'a',b'b']
    root = gen.storage.run_path(gen.run_id)
    plan = read_json(root / 'sample_plan.json')['tasks']
    assert [task['seed'] for task in plan] == [8,81]
    receipt = read_json(root / 'samples/sample_000002/task_inputs.json')['payload']
    assert receipt['identity']['height'] == 30
    assert receipt['identity']['text_model']['temperature'] == .45
    assert Path(receipt['paths']['logo_path']).read_bytes() == b'logo-b'
    assert result['run_state']['rendered_samples'] == 2
    changed=deepcopy(b);changed['poster_height']=32
    resumed=runner(tmp_path,[],run_id=gen.run_id,input_states=[a,changed],random_seed=7)
    with pytest.raises(ValueError,match='changed'):
        resumed.run(a)


def test_stop_after_critic_skips_finished_task_but_extracts_next_pdf(tmp_path):
    calls=[];control=RunControl()
    gen=runner(tmp_path,calls,samples=2,control=control)
    def score(state):
        control.request_stop()
        return critic_with_scores([12])(state)
    gen.critic=score
    original=inputs(tmp_path)
    first=gen.run(original)
    assert first['run_state']['status']=='PAUSED'
    assert len(calls)==1
    resumed=runner(tmp_path,calls,run_id=gen.run_id)
    result=resumed.run(original)
    assert [row[1] for row in calls]==['sample_000001','sample_000002']
    assert result['run_state']['rendered_samples']==2


def test_stop_after_extraction_restores_same_task_without_new_parser_call(tmp_path):
    calls=[];control=RunControl();gen=runner(tmp_path,calls,samples=1,control=control)
    gen.paper_nodes=[extractor(calls,control)]
    original=inputs(tmp_path)
    assert gen.run(original)['run_state']['status']=='PAUSED'
    assert gen.storage.paper_foundation(gen.run_id,'sample_000001')
    resumed=runner(tmp_path,calls,run_id=gen.run_id)
    result=resumed.run(original)
    assert len(calls)==1 and result['run_state']['rendered_samples']==1


@pytest.mark.parametrize('damage',['receipt_missing','receipt_corrupt','input_changed','foundation_missing','foundation_corrupt'])
def test_damaged_same_task_history_never_buys_a_new_extraction(tmp_path,damage):
    calls=[];control=RunControl();gen=runner(tmp_path,calls,samples=1,control=control)
    gen.paper_nodes=[extractor(calls,control)]
    original=inputs(tmp_path);gen.run(original)
    root=gen.storage.sample_path(gen.run_id,'sample_000001')
    if damage=='receipt_missing':(root/'task_inputs.json').unlink()
    elif damage=='receipt_corrupt':_atomic_json(root/'task_inputs.json',{'digest':'bad','payload':{}})
    elif damage=='input_changed':(root/'inputs/pdf_path.pdf').write_bytes(b'wrong')
    elif damage=='foundation_missing':(root/'paper_foundation/paper_state.json').unlink()
    else:_atomic_json(root/'paper_foundation/identity.json',{'digest':'bad'})
    resumed=runner(tmp_path,calls,run_id=gen.run_id)
    with pytest.raises(ValueError):resumed.run(original)
    assert len(calls)==1


def test_only_explicit_cache_reuses_paper_and_each_target_owns_its_assets(tmp_path):
    calls=[];original=inputs(tmp_path)
    donor=runner(tmp_path,calls,samples=1);donor.run(original)
    cache=runner(tmp_path,calls,samples=2,paper_cache_run_id=donor.run_id)
    result=cache.run(original)
    assert result['run_state']['rendered_samples']==2 and len(calls)==1
    paths=[]
    for row in result['run_state']['results']:
        paper=cache.storage.paper_foundation(cache.run_id,row['sample_id'])
        image=Path(paper['images']['1']['path']);paths.append(image)
        assert image.is_relative_to(cache.storage.sample_path(cache.run_id,row['sample_id']))
    assert paths[0]!=paths[1] and paths[0].read_bytes()==paths[1].read_bytes()
    # Removing only the synthetic donor asset leaves both copied foundations usable.
    Path(donor.storage.paper_foundation(donor.run_id,'sample_000001')['images']['1']['path']).unlink()
    for row in result['run_state']['results']:
        assert cache.storage.paper_foundation(cache.run_id,row['sample_id'])


def test_multi_task_cache_requires_explicit_source_sample(tmp_path):
    calls=[];original=inputs(tmp_path)
    donor=runner(tmp_path,calls,samples=2);donor.run(original)
    missing=runner(tmp_path,calls,samples=1,paper_cache_run_id=donor.run_id)
    result=missing.run(original)
    assert result['run_state']['status']=='FAILED' and len(calls)==2
    selected=runner(tmp_path,calls,samples=1,paper_cache_run_id=donor.run_id,paper_cache_sample_id='sample_000002')
    assert selected.run(original)['run_state']['rendered_samples']==1 and len(calls)==2


def test_cache_rejects_mismatched_paper_without_extracting_fallback(tmp_path):
    calls=[];a,b=inputs(tmp_path,'a'),inputs(tmp_path,'b')
    donor=runner(tmp_path,calls,samples=1);donor.run(a)
    cached=runner(tmp_path,calls,samples=1,paper_cache_run_id=donor.run_id)
    result=cached.run(b)
    assert result['run_state']['status']=='FAILED' and len(calls)==1


def test_changed_rehashed_task_plan_is_rejected_before_paper_calls(tmp_path):
    calls=[];original=inputs(tmp_path);gen=runner(tmp_path,calls,samples=1);gen.run(original)
    path=gen.storage.run_path(gen.run_id)/'sample_plan.json'
    plan=read_json(path);plan['tasks'][0]['seed']+=1;plan['digest']=digest(plan['tasks']);_atomic_json(path,plan)
    resumed=runner(tmp_path,calls,run_id=gen.run_id)
    with pytest.raises(ValueError,match='task plan'):resumed.run(original)
    assert len(calls)==1


DEFAULTS={'text_model':'gpt-4.1-2025-04-14','vision_model':'gpt-4.1-2025-04-14',
          'poster_width':54,'poster_height':36,'url':'','logo':None,'aff_logo':None}


def test_task_file_resolves_each_paper_relative_to_file_and_keeps_own_parameters(tmp_path):
    inputs(tmp_path,'one');inputs(tmp_path,'two')
    path=tmp_path/'tasks.json';path.write_text(json.dumps({'schema_version':1,'tasks':[
        {'paper_path':'one/paper.pdf'}, {'paper_path':'two/paper.pdf','poster_height':30,'random_seed':19}]}))
    states=load_task_file(path,DEFAULTS,create_state)
    assert [Path(s['pdf_path']).parent.name for s in states]==['one','two']
    assert states[1]['poster_height']==30 and states[1]['task_random_seed']==19
    assert states[1]['logo_path']==str(tmp_path/'two/logo.png')


@pytest.mark.parametrize('change',['empty','unknown','missing_pdf','bad_logo','bad_seed','bad_height','bad_schema'])
def test_invalid_task_inputs_fail_before_generation(tmp_path,change):
    inputs(tmp_path)
    value={'schema_version':1,'tasks':[{'paper_path':'one/paper.pdf'}]}
    spec=value['tasks'][0]
    if change=='empty':value['tasks']=[]
    if change=='unknown':spec['samples']=3
    if change=='missing_pdf':spec['paper_path']='missing.pdf'
    if change=='bad_logo':spec['logo']='missing.png'
    if change=='bad_seed':spec['random_seed']=True
    if change=='bad_height':spec['poster_height']=0
    if change=='bad_schema':value['schema_version']=True
    path=tmp_path/'tasks.json';path.write_text(json.dumps(value))
    with pytest.raises(ValueError):load_task_file(path,DEFAULTS,create_state)
