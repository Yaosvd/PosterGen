"""Explicit paper-only reuse and safe metadata filtering, without model services."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from src.workflow.paper_cache import copy_paper_cache, extraction_identity
from src.workflow.exploration_store import ExplorationStore
from utils.persistence import _atomic_json, read_json
from test_exploration_samples import scientific


def cache_pair(tmp_path):
    store=ExplorationStore(tmp_path/'store')
    settings={'code_identity':{'src/agents/parser.py':'parser','src/agents/evidence_builder.py':'evidence'},
              'poster':{'size':54},'agent_policy_hash':'policy','critic':{'sample_execution':{}}}
    identity={'inputs':{'pdf':'paper'},'text_model':'model','vision_model':'model'}
    source,_=store.open_run(identity,settings,seed=1,samples=1)
    target,_=store.open_run(identity,settings,seed=2,samples=1)
    state=scientific(tmp_path)
    assets=store.run_path(source)/'paper_foundation/assets';assets.mkdir(parents=True)
    asset=assets/'figure.png';asset.write_bytes(b'original scientific image')
    state['images']={'1':{'path':str(asset),'aspect':2.0}}
    # This sample-specific field must never appear in another paper foundation.
    state['verified_module_board']={'private':'previous sample prose'}
    store.save_paper_foundation(source,state)
    return store,source,target,identity,settings


def test_paper_cache_copies_original_assets_but_no_sample_science(tmp_path):
    store,source,target,identity,settings=cache_pair(tmp_path)
    original=(store.run_path(source)/'paper_foundation/paper_state.json').read_bytes()
    fields=copy_paper_cache(store,source,target,identity,settings)
    assert not set(fields)&{'verified_claims','sample_module_plan','verified_module_board','story_board'}
    copied=Path(fields['images']['1']['path'])
    assert copied.is_relative_to(store.run_path(target)) and copied.read_bytes()==b'original scientific image'
    assert (store.run_path(source)/'paper_foundation/paper_state.json').read_bytes()==original


@pytest.mark.parametrize('change',['paper','model','code','asset','digest'])
def test_changed_or_corrupt_cache_is_rejected(tmp_path,change):
    store,source,target,identity,settings=cache_pair(tmp_path)
    identity=deepcopy(identity);settings=deepcopy(settings)
    if change=='paper':identity['inputs']['pdf']='other'
    if change=='model':identity['text_model']='other'
    if change=='code':settings['code_identity']['src/agents/evidence_builder.py']='changed'
    if change=='asset':(store.run_path(source)/'paper_foundation/assets/figure.png').write_bytes(b'changed')
    if change=='digest':_atomic_json(store.run_path(source)/'paper_foundation/identity.json',{'digest':'changed'})
    with pytest.raises(ValueError):copy_paper_cache(store,source,target,identity,settings)


def test_source_mutation_between_verification_and_copy_cannot_be_reblessed(monkeypatch,tmp_path):
    store,source,target,identity,settings=cache_pair(tmp_path)
    original=store.paper_foundation
    def read_then_mutate(run):
        fields=original(run)
        (store.run_path(source)/'paper_foundation/assets/figure.png').write_bytes(b'changed after validation')
        return fields
    monkeypatch.setattr(store,'paper_foundation',read_then_mutate)
    with pytest.raises(ValueError,match='changed during validation'):
        copy_paper_cache(store,source,target,identity,settings)


def test_metadata_filter_is_sample_only_and_keeps_appendix(monkeypatch,tmp_path):
    import src.agents.evidence_builder as module
    seen=[]
    class Agent:
        def __init__(self,*args):pass
        def reset(self):pass
        def step(self,prompt):
            seen.append(prompt)
            return SimpleNamespace(content=json.dumps({'evidence':[{
                'claim':'The model uses neural signals.', 'source_excerpt':'The model uses neural signals.',
                'claim_type':'method','entities':[],'numbers':[]}]}),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(module,'LangGraphAgent',Agent)
    monkeypatch.setattr(module,'apply_agent_policy',lambda c,_:c)
    for route,expected in [('optimization_family',1),('standalone_classic',3)]:
        seen.clear();state=scientific(tmp_path);state.update(generation_route=route,output_dir=str(tmp_path/route),errors=[])
        state['section_chunks']=[{'section_id':f's{i}','section_name':name,
            'content':'The model uses neural signals.'} for i,name in enumerate(['References','Acknowledgments','A. Method details'])]
        module.EvidenceBuilder()(state)
        assert not state['errors'] and len(seen)==expected
        if route=='optimization_family':
            assert len(state['evidence_extraction_report']['skipped_metadata_sections'])==2
            assert 'A. Method details' in seen[0]


def test_cache_validation_failure_records_failed_run_before_sample_calls(monkeypatch,tmp_path):
    import src.workflow.paper_cache as module
    from src.workflow.exploration_runner import PosterExplorationRunner
    def fail(*args):raise ValueError('extraction identity changed')
    monkeypatch.setattr(module,'copy_paper_cache',fail)
    def forbidden(s):pytest.fail('No sample or design work after cache failure')
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'new_store'),samples=1,
        paper_cache_run_id='run_source',paper_nodes=[],preparation_nodes=[forbidden],design_nodes=[forbidden])
    result=runner.run(scientific(tmp_path),paper_ready=True)
    assert result['run_state']['status']=='FAILED' and result['run_state']['finalized_samples']==0
    error=read_json(runner.storage.run_path(runner.run_id)/'paper_foundation_failure.json')
    assert error['stage']=='paper_cache' and error['error_type']=='ValueError'


def test_source_cache_is_self_contained_and_does_not_import_evidence_or_sample_science(tmp_path):
    from copy import deepcopy
    from PIL import Image
    from test_source_editorial import source_state
    from src.workflow.source_document import build_document, validate_document
    from src.workflow.exploration_store import ExplorationStore
    from src.workflow.paper_cache import copy_paper_cache
    from utils.persistence import file_hash
    store=ExplorationStore(tmp_path/'source_cache_store')
    identity={'paper':'same_original_paper'}
    settings={'preparation_policy_version':'sample_source_science_v1','code_identity':{},
        'agent_policy_hash':'source_policy','poster':{},'critic':{'sample_execution':{}}}
    source,_=store.open_run(identity,settings,seed=1,samples=1)
    target,_=store.open_run(identity,settings,seed=2,samples=1)
    material=source_state(tmp_path/'source_fixture')
    image=store.run_path(source)/'paper_foundation/assets/figure.png'
    image.parent.mkdir(parents=True);Image.new('RGB',(24,24),'navy').save(image)
    material['images']={'1':{'path':str(image),'aspect':1.0,'caption':'Original shared-policy schematic.'}}
    material['source_document']=build_document(material)
    material['evidence_bank']={'items':[{'evidence_id':'must_not_import','claim':'Old extracted fact'}]}
    store.save_paper_foundation(source,material)
    copied=copy_paper_cache(store,source,target,identity,settings)
    assert not any(key in copied for key in ('evidence_bank','source_candidate','source_verification_report','verified_claims'))
    new_image=Path(copied['images']['1']['path'])
    assert new_image.is_relative_to(store.run_path(target)) and file_hash(new_image)==file_hash(image)
    assert copied['source_document']['assets']['figure_1']['source_path']==str(new_image)
    assert copied['source_document']['raw_text']==material['raw_text']
    # Removing this private test donor must not make the copied source depend on it.
    image.unlink()
    assert validate_document(copied['source_document'])
    legacy_settings=deepcopy(settings);legacy_settings['preparation_policy_version']='sample_science_v6'
    import pytest
    with pytest.raises(ValueError,match='identity changed'):
        copy_paper_cache(store,source,target,identity,legacy_settings)
