"""Focused regression for sparse Balancer patches and field-only recovery."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.workflow.editorial_contract import EditorialStructureError, EditorialOutputError
from src.workflow.editorial_format import repair_plan, apply_repair
from src.workflow.editorial_requests import request, obj, STRING
from src.workflow import editorial_pipeline as pipeline
from test_editorial_generation import state_for, draft_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language,'create_model',lambda *a,**k:pytest.fail('No live model in regression'))


def model(monkeypatch,values):
    import utils.langgraph_utils as language
    values=iter(values);calls=[]
    class Model:
        def __init__(self,*a,**k):pass
        def reset(self):pass
        def step(self,message):
            calls.append(message);value=next(values)
            if isinstance(value,BaseException):raise value
            return SimpleNamespace(content=json.dumps(value),input_tokens=2,output_tokens=1)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    return calls


def poster_patch():
    modules=[]
    for mid in ('mod_1','mod_2','mod_3','mod_5'):
        modules.append({'module_id':mid,'entries':[{'item_id':f'e{i+1}',
            'text':f'Original {mid} sentence {i+1}, 3% under fixed conditions.'} for i in range(4)]})
    modules[2]['entries'][3]['item_id']='         '
    return {'modules':modules,'reason':'Expand three modules and compress mod_5.'}


SCHEMA=obj({'modules':{'type':'array','items':obj({'module_id':STRING,'entries':{
    'type':'array','items':obj({'item_id':STRING,'text':STRING})}})},'reason':STRING})


def validate_patch(value):
    for i,module in enumerate(value['modules']):
        for j,entry in enumerate(module['entries']):
            if not entry['item_id'].strip():
                raise EditorialStructureError('Entry IDs must be unique local identifiers',
                    [('modules',i,'entries',j,'item_id')])


def test_four_module_edit_survives_single_blank_id_repair_and_replay(monkeypatch,tmp_path):
    state=state_for(tmp_path);original=poster_patch()
    calls=model(monkeypatch,[original,{'repairs':{'field_0':'e4'}}])
    value=request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    expected=deepcopy(original);expected['modules'][2]['entries'][3]['item_id']='e4'
    assert value==expected and len(value['modules'])==4 and len(calls)==2
    assert value['reason']==original['reason']
    plan=json.loads(calls[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:\n')[-1])
    assert plan==obj({'repairs':obj({'field_0':STRING})})
    assert 'module patch or a complete response' in calls[1]
    assert request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',
                   validator=validate_patch)==expected
    assert len(calls)==2
    root=Path(state['sample_preparation_dir'])/'editorial/edit'
    assert json.loads((root/'repair_plan.json').read_text())['payload']['plan']['targets']==[
        {'path':['modules',2,'entries',3,'item_id'],'action':'replace','field':'field_0'}]


@pytest.mark.parametrize('wire',[
    {'repairs':{'field_0':'e4','text':'changed scientific assertion'}},
    {'repairs':{'field_0':'e4'},'reason':'changed reason'},
    {'modules':[poster_patch()['modules'][2]],'reason':'fixed'},
    {'repairs':{}}, {'repairs':{'field_0':42}},
])
def test_out_of_scope_or_incomplete_repair_rejects_without_another_call(monkeypatch,tmp_path,wire):
    state=state_for(tmp_path);calls=model(monkeypatch,[poster_patch(),wire])
    with pytest.raises(EditorialOutputError,match='Invalid field repair response'):
        request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    assert len(calls)==2


def test_second_invalid_id_consumes_the_only_repair(monkeypatch,tmp_path):
    state=state_for(tmp_path);calls=model(monkeypatch,[poster_patch(),{'repairs':{'field_0':' '}}])
    with pytest.raises(EditorialOutputError,match='finite format allowance'):
        request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    assert len(calls)==2


def test_returned_patch_recovers_after_interruption_before_acceptance(monkeypatch,tmp_path):
    import src.workflow.editorial_requests as module
    state=state_for(tmp_path);calls=model(monkeypatch,[poster_patch(),{'repairs':{'field_0':'e4'}}])
    original_save=module.save
    def stop(path,value):
        if path.name=='accepted.json':raise KeyboardInterrupt()
        return original_save(path,value)
    monkeypatch.setattr(module,'save',stop)
    with pytest.raises(KeyboardInterrupt):
        request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    monkeypatch.setattr(module,'save',original_save)
    value=request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    assert value['modules'][2]['entries'][3]['item_id']=='e4' and len(calls)==2


def test_interrupted_second_request_refuses_resubmission(monkeypatch,tmp_path):
    state=state_for(tmp_path);calls=model(monkeypatch,[poster_patch(),KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    with pytest.raises(ValueError,match='response missing'):
        request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    assert len(calls)==2


@pytest.mark.parametrize('corruption',['changed','missing'])
def test_repair_plan_history_is_required(monkeypatch,tmp_path,corruption):
    state=state_for(tmp_path);model(monkeypatch,[poster_patch(),{'repairs':{'field_0':'e4'}}])
    request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    path=Path(state['sample_preparation_dir'])/'editorial/edit/repair_plan.json'
    if corruption=='missing':path.unlink()
    else:
        value=json.loads(path.read_text());value['payload']['original_digest']='changed'
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)


@pytest.mark.parametrize('target,order',[(2,False),(1,True)])
def test_sparse_patch_errors_map_back_to_wire_indices(tmp_path,target,order):
    state=state_for(tmp_path);candidate=draft_for(state)
    candidate=pipeline.normalize_candidate(candidate,state,list(
        pipeline.LayoutFamilyRegistry().get(state['sample_family']['family']).zones))
    state.update(editorial_candidate=candidate,
                 editorial_zones=list(pipeline.LayoutFamilyRegistry().get(state['sample_family']['family']).zones),
                 editorial_visual_selection=pipeline.visual_selection(candidate,state))
    changed=deepcopy(candidate['modules'][target]);changed['entries'][0]['item_id']=' '
    raw={'modules':[changed],'remove_module_ids':[],
         'module_order':list(reversed([m['module_id'] for m in candidate['modules']])) if order else [],
         'narrative_flow':'','reason':'Only this module changes.'}
    with pytest.raises(EditorialStructureError) as exc:
        pipeline.merge_patch(state,raw)
    assert ('modules',0,'entries',0,'item_id') in exc.value.paths
    plan=repair_plan(raw,pipeline.PATCH,exc.value.paths)
    # The blank main ID also invalidates its child's reference; both diagnosed
    # leaf slots must be returned, while all prose stays outside the repair.
    fixed=apply_repair(raw,{'repairs':{'field_0':'main','field_1':'main'}},plan)
    result=pipeline.merge_patch(state,fixed)
    assert len(result['modules'])==3


@pytest.mark.parametrize('original,paths,wire,expected',[
    ({'neighbor':'kept'},[('title',)],{'repairs':{'field_0':'Fixed'}},{'neighbor':'kept','title':'Fixed'}),
    ({'title':'Valid','extra':'illegal'},[('extra',)],{'repairs':{}},{'title':'Valid'}),
    ({'title':13},[('title',)],{'repairs':{'field_0':'Fixed'}},{'title':'Fixed'}),
    (None,[()],{'repairs':{'field_0':{'title':'Fixed'}}},{'title':'Fixed'}),
])
def test_missing_extra_wrong_type_and_root_fields(original,paths,wire,expected):
    schema=obj({'title':STRING})
    if original and 'neighbor' in original:schema=obj({'title':STRING,'neighbor':STRING})
    plan=repair_plan(original,schema,paths)
    assert apply_repair(original,wire,plan)==expected


def test_overlapping_diagnostics_collapse_to_invalid_parent():
    schema=obj({'entries':{'type':'array','items':obj({'item_id':STRING})}})
    plan=repair_plan({'entries':[]},schema,[('entries',),('entries',0,'item_id'),('entries',)])
    assert plan['targets']==[{'path':['entries'],'action':'replace','field':'field_0'}]


def test_semantic_rejection_cannot_buy_a_format_repair(monkeypatch,tmp_path):
    state=state_for(tmp_path);calls=model(monkeypatch,[{'title':'unsupported'}])
    def reject(value):raise EditorialOutputError('Scientific/content failure')
    with pytest.raises(EditorialOutputError,match='Scientific/content'):
        request(state,'editorial_metadata',{},obj({'title':STRING}),directory='editorial/edit',validator=reject)
    assert len(calls)==1


def test_second_provider_binding_uses_only_repair_slot_schema(monkeypatch,tmp_path):
    import utils.langgraph_utils as language
    state=state_for(tmp_path);bindings=[];values=iter([poster_patch(),{'repairs':{'field_0':'e4'}}]);agents=[]
    class Base:
        def bind(self,**kwargs):bindings.append(kwargs);return object()
    class Model:
        def __init__(self,*a):
            self.model=Base();self.original=self.model;self.request_policy=object();agents.append(self)
        def reset(self):pass
        def step(self,message):
            assert self.model is not self.original
            return SimpleNamespace(content=json.dumps(next(values)),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(language,'ChatOpenAI',Base)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    result=request(state,'editorial_balancer',{},SCHEMA,directory='editorial/edit',validator=validate_patch)
    assert result['modules'][2]['entries'][3]['item_id']=='e4'
    assert bindings[0]['response_format']['json_schema']['schema']==SCHEMA
    assert bindings[1]['response_format']['json_schema']['schema']==obj({'repairs':obj({'field_0':STRING})})
    assert agents[0].model is agents[0].original
