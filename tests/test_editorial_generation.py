"""New default editorial route: no science bank, model-owned mapping, real delivery."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from PIL import Image

from src.state.poster_state import create_state
from src.workflow.editorial_contract import (VERSION,normalize_candidate,module_limits,make_board,
    EditorialOutputError,EditorialStructureError,assert_editorial_ready)
from src.workflow import editorial_pipeline as pipeline
from src.layout.families import LayoutFamilyRegistry
from src.layout.editorial_layout import measure,fit
from src.config.critic_config import load_critic_config


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language,'create_model',lambda *a,**k:pytest.fail('Unexpected real model connection'))


def state_for(tmp_path,family='classic_three_column',text='A shared prediction model supports sequential search under limited resources.'):
    pdf=tmp_path/'paper.pdf';pdf.parent.mkdir(parents=True,exist_ok=True);pdf.write_bytes(b'offline paper')
    state=create_state(str(pdf),text_model='local-text',vision_model='local-vision',width=54,height=36,poster_name='editorial_test')
    root=tmp_path/'sample/preparation';root.mkdir(parents=True,exist_ok=True)
    state.update(editorial_version=VERSION,generation_route='optimization_family',raw_text=text,images={},tables={},
        structured_sections={'paper_sections':[{'section_name':'Method','section_type':'method','content':text,
            'key_points':[text],'importance':'high','contains_figures':[],'contains_tables':[]}]},
        narrative_content={'and':'A practical need.','but':'Resources are limited.','therefore':text,
            'poster_hook':'Efficient discovery','key_impact':'Better allocation',
            'meta':{'poster_title':'Shared Search','authors':'A. Researcher'}},classified_visuals={},
        sample_family={'family':family},sample_preparation_dir=str(root),sample_edit_budget_dir=str(root.parent),
        output_dir=str(root),paper_foundation_digest='paper',critic_config=load_critic_config(),joint_preparation=True,
        iteration_context={'run_id':'run_test','sample_id':'sample_000001','iteration':1,'random_seed':42,
                           'layout_family':family})
    return state


def draft_for(state):
    family=LayoutFamilyRegistry().get(state['sample_family']['family'])
    modules=[]
    for i,z in enumerate(family.zones):
        modules.append({'module_id':f'module_{i}','title':'Shared method','zone_id':z['zone_id'],
            'importance':1 if i==0 else 2,'space_weight':1,'presentation_style':'topics',
            'reader_question':'How does it work?',
            'entries':[{'item_id':'main','text':state['raw_text'],'display_label':'Core mechanism','parent_item_id':''},
                       {'item_id':'support','text':'The policy updates its predictions after observations.',
                        'display_label':'','parent_item_id':'main'}],
            'visual_ids':[],'visual_rationale':'Text explanation'})
    return {'modules':modules,'core_module_ids':[],
            'narrative_flow':'Down each region, then right.','reason':'Useful source material.'}


def install(state,raw=None):
    zones=deepcopy(list(LayoutFamilyRegistry().get(state['sample_family']['family']).zones))
    state['editorial_zones']=zones
    pipeline.install(state,normalize_candidate(raw or draft_for(state),state,zones))
    state['editorial_visual_selection']=pipeline.visual_selection(state['editorial_candidate'],state)
    pipeline.editorial_color_node(state);pipeline.editorial_title_node(state)
    return state


@pytest.mark.parametrize('family',LayoutFamilyRegistry().ids())
def test_fifteen_canonical_counts_and_exact_ownership(tmp_path,family):
    state=install(state_for(tmp_path,family))
    family_obj=LayoutFamilyRegistry().get(family)
    assert module_limits(family_obj.zones)==(len(family_obj.zones),sum(z['capacity'] for z in family_obj.zones))
    result=measure(state,state['editorial_candidate'],state['editorial_zones'])
    assert result['report']['passed'],result['report']
    assert [z['section_ids'] for z in result['spec']['zones']]==[[m['module_id']] for m in state['editorial_candidate']['modules']]
    assert not state.get('verification_passed') and not state.get('verified_claims')
    assert all(m['allocated_height']>0 for m in result['report']['modules'])
    # New navigation cues are authored, not restricted to a verbatim prose substring.
    from src.layout.body_presentation import paragraphs
    assert paragraphs(result['board']['spatial_content_plan']['sections'][0])[0]['label']=='Core mechanism'


def test_unknown_visual_and_parent_rejected_without_scientific_gate(tmp_path):
    state=state_for(tmp_path);raw=draft_for(state);zones=LayoutFamilyRegistry().get('classic_three_column').zones
    raw['modules'][0]['visual_ids']=['figure_missing']
    with pytest.raises(EditorialStructureError):normalize_candidate(raw,state,zones)
    raw=draft_for(state);raw['modules'][0]['entries'][0]['parent_item_id']='missing'
    with pytest.raises(EditorialStructureError):normalize_candidate(raw,state,zones)


def test_deficit_invokes_only_legal_merge_then_one_adaptation(monkeypatch,tmp_path):
    state=state_for(tmp_path,'small_multiples_matrix');calls=[]
    def response(st,kind,payload,*args,**kwargs):
        calls.append(payload)
        if payload['phase']=='curator':
            raw=draft_for(st);raw['modules']=raw['modules'][:4];return raw
        raw=draft_for(st);raw['modules']=raw['modules'][:len(payload['family']['zones'])]
        for m,z in zip(raw['modules'],payload['family']['zones']):m['zone_id']=z['zone_id']
        return raw
    # Real durable request guard expects the response journal for replay; this test
    # exercises first-time planning only with an offline response boundary.
    monkeypatch.setattr(pipeline,'request',response)
    pipeline.editorial_curator_node(state)
    assert len(calls)==2 and calls[0]['phase']=='curator' and calls[1]['phase']=='merge'
    assert len(state['editorial_zones'])==4
    assert len([z for z in state['editorial_zones'] if z.get('merged_from')])==2
    assert [e['phase'] for e in state['editorial_budget']['charges']]==['curator','merge']


def test_three_column_deficit_cannot_forge_merge(monkeypatch,tmp_path):
    state=state_for(tmp_path);raw=draft_for(state);raw['modules']=raw['modules'][:2]
    monkeypatch.setattr(pipeline,'request',lambda *a,**k:raw)
    with pytest.raises(EditorialOutputError,match='no legal'):pipeline.editorial_curator_node(state)


def test_patch_can_coordinate_more_than_two_modules_but_not_drop_regions(tmp_path):
    state=install(state_for(tmp_path));patch={'modules':deepcopy(state['editorial_candidate']['modules']),
        'remove_module_ids':[],'module_order':[],'narrative_flow':'','reason':'Clarify all three modules.'}
    for m in patch['modules']:m['entries'][0]['text']='A clearer scientific explanation.'
    result=pipeline.merge_patch(state,patch)
    assert len(result['modules'])==3
    patch['modules']=[];patch['remove_module_ids']=['module_0']
    with pytest.raises(EditorialOutputError):pipeline.merge_patch(state,patch)


def test_size_search_starts_after_measurement_and_keeps_assignment(tmp_path):
    state=install(state_for(tmp_path))
    before=deepcopy(state['editorial_candidate'])
    result=fit(state,before,state['editorial_zones'])
    assert result['report']['passed']
    assert len([t for t in result['report']['geometry_trials'] if 'fast_report' in t])<=12
    assert state['editorial_candidate']==before
    assert [z['section_ids'] for z in result['spec']['zones']]==[['module_0'],['module_1'],['module_2']]


def test_charged_missing_response_refuses_resubmission(monkeypatch,tmp_path):
    from src.workflow.editorial_requests import request,obj,STRING
    import utils.langgraph_utils as language
    state=state_for(tmp_path);calls=[]
    class Fail:
        def __init__(self,*args):pass
        def reset(self):pass
        def step(self,message):calls.append(message);raise TimeoutError('returned no response')
    monkeypatch.setattr(language,'LangGraphAgent',Fail)
    args=(state,'editorial_metadata',{'original_text':'Paper'},obj({'title':STRING}))
    with pytest.raises(TimeoutError):request(*args,directory='editorial/test')
    with pytest.raises(ValueError,match='response missing'):request(*args,directory='editorial/test')
    assert len(calls)==1


@pytest.mark.parametrize('evaluation_failure,publication_crash,layout_defects,horizontal',[
    (False,False,False,False),(True,False,False,False),(False,True,False,False),
    (False,False,True,False),(False,True,True,False),
    (False,False,False,True),(False,True,False,True)])
def test_default_runner_real_compile_render_critic_and_publication(monkeypatch,tmp_path,evaluation_failure,publication_crash,layout_defects,horizontal):
    from src.workflow.exploration_runner import PosterExplorationRunner,default_nodes
    from src.workflow.exploration_store import ExplorationStore
    from src.agents.font_agent import FontAgent
    from src.critic.visual import VisualCriticEvaluator
    import utils.langgraph_utils as language
    family='central_evidence_band' if horizontal else 'classic_three_column'
    state=state_for(tmp_path/'source',family)
    # A real PDF is retained for evaluation provenance; parser extraction is tested
    # separately from this full model-free default preparation/design integration.
    import pymupdf
    pdf=Path(state['pdf_path'])
    with pymupdf.open() as doc:
        page=doc.new_page();page.insert_text((30,30),state['raw_text']);doc.save(str(pdf)+'.new')
    Path(str(pdf)+'.new').replace(pdf)
    visual=tmp_path/'diagram.png';Image.new('RGB',(800,220),'navy').save(visual)
    state['images']={'1':{'path':str(visual),'aspect':800/220,'caption':'Shared architecture'}}
    state['classified_visuals']={'key_visual':'figure_1','method_workflow':['figure_1']}
    owner_index=2 if horizontal else 0
    visual_owner=f'module_{owner_index}'
    prototype=draft_for(state);prototype['modules'][owner_index]['visual_ids']=['figure_1']
    if layout_defects:
        # Pin base geometry here to isolate defective-output admission. The
        # pressure-driven search itself has separate family/performance tests.
        import src.layout.editorial_layout as editorial_layout
        monkeypatch.setattr(editorial_layout,'boundary_candidates',lambda *a,**k:[])
        prototype['modules'][0]['entries'][0]['text']='Limited resources.\n'*60
        extra=deepcopy(prototype['modules'][1]);extra['module_id']='extra_module'
        extra['zone_id']=prototype['modules'][0]['zone_id'];prototype['modules'].insert(1,extra)

    if horizontal:
        prototype['core_module_ids']=['module_0',visual_owner]

    def paper_node(current):
        for k in ('raw_text','structured_sections','narrative_content','images','tables','classified_visuals'):
            current[k]=deepcopy(state[k])
        return current
    calls=[]
    class Model:
        def __init__(self,system,config,current,name):self.state=current;self.name=name
        def reset(self):pass
        def step(self,message):
            calls.append(self.name)
            try:parts=json.loads(message)
            except ValueError:parts=None
            text=parts[0]['text'] if isinstance(parts,list) else message
            data=json.loads(text.split('\nINPUT:\n',1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
            if self.name in {'critic_content','critic_visual'}:
                diagnostics=data['render_diagnostics']
                assert set(diagnostics)=={'editorial_fit','layout_preflight_report','render_fit_report'}
                if layout_defects:
                    assert diagnostics['editorial_fit']['passed'] is False
                    assert diagnostics['layout_preflight_report']['passed'] is False
                    assert diagnostics['render_fit_report']['generation_blocking'] is False
                    assert 'Revision 3.' in data['final_poster']['modules'][0]['entries'][0]['text']
            if self.name=='source_curator':value=deepcopy(prototype)
            elif self.name=='source_balancer':
                assert data['phase']=='capacity'
                from src.layout.editorial_composition import HORIZONTAL, VERTICAL
                assert data['fixed_module_composition']['modules']=={visual_owner:HORIZONTAL if horizontal else VERTICAL}
                edits=[]
                if layout_defects or horizontal:
                    changed=deepcopy(data['whole_poster']['modules'][owner_index])
                    changed['entries'][0]['text']+=' Revision '+str(calls.count('source_balancer'))+'.'
                    edits=[changed]
                value={'modules':edits,'remove_module_ids':[],
                    'module_order':[],'narrative_flow':'','reason':'Offline measured edit.'}

            elif self.name=='color_agent':
                value={'theme_color':'#1C7448' if data['source'].startswith('core_') else '#224466'}
            elif self.name=='critic_content':
                assert data['paper']['original_text']==state['raw_text']
                assert data['content_status']=='not_preverified'
                if evaluation_failure:raise TimeoutError('Offline unavailable evaluation')
                value={'status':'issues','scientific_integrity':60,'content_submetrics':{k:30 for k in ('information_layering','information_coverage',
                    'information_depth','information_completeness','narrative_structure','narrative_conciseness')},
                    'issues':[{'module_id':'module_0','observation':'Synthetic review finding','original_support':'Original text',
                               'severity':'major'}],'reason':'Fixture result, not real science.'}
            elif self.name=='critic_visual':value={'scores':{k:20 for k in VisualCriticEvaluator._DIMENSIONS},
                'submetrics':{k:20 for k in VisualCriticEvaluator._SUBMETRICS},'issues':[],'positive_patterns':[],'reason':'Fixture visual review.'}
            else:raise AssertionError('Unexpected model '+self.name)
            return SimpleNamespace(content=json.dumps(value),input_tokens=7,output_tokens=4)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    monkeypatch.setattr(FontAgent,'_identify_keywords',lambda *a:{'section_keywords':{}})
    monkeypatch.setattr(LayoutFamilyRegistry,'choose_with_report',lambda self,*a,**k:(
        family,{'test':'offline','enabled_families':self.ids()}))
    runner=PosterExplorationRunner(storage=ExplorationStore(tmp_path/'store'),paper_nodes=[paper_node],samples=1,random_seed=42)
    if publication_crash:
        captured={};publish=runner.storage.publish_poster
        def interrupt_publication(current,outcome):
            captured['state']=current
            raise RuntimeError('Offline interrupted before publication')
        monkeypatch.setattr(runner.storage,'publish_poster',interrupt_publication)
        with pytest.raises(RuntimeError,match='before publication'):runner.run(state)
        calls_after_render=len(calls)
        monkeypatch.setattr(runner.storage,'publish_poster',publish)
        runner=PosterExplorationRunner(storage=runner.storage,paper_nodes=[paper_node],run_id=runner.run_id)
        recovered=runner.run(state)
        assert len(calls)==calls_after_render
        result={**captured['state'],'run_state':recovered['run_state']}
    else:
        result=runner.run(state)
    assert result['run_state']['status']=='COMPLETED',result.get('errors')
    records=runner.storage.results(runner.run_id)
    assert len(records)==1 and records[0]['poster_id'],records
    directory=runner.storage.verify_poster(records[0]['poster_id'])
    assert (directory/'poster.png').is_file() and (directory/'poster.pptx').is_file()
    if evaluation_failure:
        assert records[0]['score'] is None and records[0]['status']=='evaluation_failed'
    else:
        assert records[0]['score'] is not None and records[0]['score']<78
    assert not result.get('verification_passed') and not result.get('verified_claims')
    assert calls.count('source_curator')==1 and calls.count('source_balancer')==(3 if layout_defects or horizontal else 1)
    assert calls.count('critic_content')==1 and calls.count('critic_visual')==1
    assert not any('verifier' in name or 'narrative' in name for name in calls)
    assert_editorial_ready(result,compiled=True)
    report=json.loads((directory/'evaluation.json').read_text())
    assert report['factual_consistency_status']==('unavailable' if evaluation_failure else 'issues')
    assert not report['reference_passed']
    assert (directory/'diagnostics/final_column_analysis.json').is_file()
    assert (directory/'diagnostics/section_fit_analysis.json').is_file()
    assert result['timing_metrics'].source_balancer_time>0
    assert result['timing_metrics'].source_preview_time==0
    assert not any(e['phase']=='quality' for e in result['editorial_budget']['charges'])
    assert not any(e['phase']=='visual' for e in result['editorial_budget']['charges'])
    assert result['editorial_visual_selection']['owners']=={visual_owner:['figure_1']}
    from src.layout.editorial_composition import HORIZONTAL, VERTICAL, assert_composition
    assert result['editorial_composition']['modules']=={visual_owner:HORIZONTAL if horizontal else VERTICAL}
    assert_composition(result,layout=result['styled_layout'],durable=True)
    assert (directory/'diagnostics/editorial_composition.json').is_file()
    assert (directory/'diagnostics/editorial_emphasis.json').is_file()
    if horizontal:
        from pptx import Presentation
        from pptx.enum.dml import MSO_FILL
        panels=result['editorial_emphasis']['panels']
        assert set(panels)=={'module_0',visual_owner}
        assert panels['module_0']['source']=='global_palette'
        assert panels[visual_owner]['visual_id']=='figure_1'
        assert panels[visual_owner]['theme_color']=='#1C7448'
        assert panels['module_0']['resolved']['background']!=panels[visual_owner]['resolved']['background']
        reopened=Presentation(directory/'poster.pptx')
        colored=[s for s in reopened.slides[0].shapes if s.shape_type==1
                 and s.fill.type==MSO_FILL.SOLID and str(s.fill.fore_color.rgb).lower() in
                 {p['resolved']['background'][1:].lower() for p in panels.values()}]
        assert len(colored)==2
    assert not list(runner.storage.sample_path(runner.run_id,records[0]['sample_id']).rglob('visual_probes'))
    assert not list(runner.storage.sample_path(runner.run_id,records[0]['sample_id']).rglob('draft.pptx'))
    if layout_defects:
        assert result['editorial_fit']['passed'] is False
        assert result['editorial_fit']['completion_reason']=='repair_limit_reached'
        assert result['layout_preflight_report']['passed'] is False
        assert result['layout_preflight_report']['generation_blocking'] is False
        assert result['layout_preflight_failed'] is True and not result['errors']
        assert 'Revision 3.' in result['editorial_candidate']['modules'][0]['entries'][0]['text']
        assert (directory/'diagnostics/layout_preflight_report.json').is_file()
        assert report['dimension_scores']['layout_integrity']<100

    assert report['rubric_version']=='academic_poster_editorial_v3'
    calls_before=len(calls)
    resumed=PosterExplorationRunner(storage=runner.storage,paper_nodes=[paper_node],run_id=runner.run_id)
    again=resumed.run(state)
    assert again['run_state']['finalized_samples']==1 and len(calls)==calls_before
    result['styled_layout'][next(i for i,e in enumerate(result['styled_layout']) if e.get('type')=='text')]['content']='Changed'
    with pytest.raises(ValueError,match='Renderer-visible'):assert_editorial_ready(result,compiled=True)


def test_format_repair_preserves_valid_neighbor_and_is_shared(monkeypatch,tmp_path):
    from src.workflow.editorial_requests import request,obj,STRING
    import utils.langgraph_utils as language
    state=state_for(tmp_path);calls=[]
    values=iter([{'title':'','neighbor':'original'},{'title':'Repaired','neighbor':'original'},
                 {'title':'','neighbor':'original'}])
    class Model:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,message):
            calls.append(message)
            return SimpleNamespace(content=json.dumps(next(values)),input_tokens=3,output_tokens=2)
    def validate(value):
        if not value['title']:raise EditorialStructureError('Empty title',[('title',)])
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    schema=obj({'title':STRING,'neighbor':STRING})
    value=request(state,'editorial_metadata',{},schema,directory='editorial/first',validator=validate)
    assert value=={'title':'Repaired','neighbor':'original'} and len(calls)==2
    with pytest.raises(EditorialOutputError,match='exhausted'):
        request(state,'editorial_metadata',{'second':True},schema,directory='editorial/second',validator=validate)
    assert len(calls)==3


def test_format_repair_cannot_rewrite_valid_neighbor(monkeypatch,tmp_path):
    from src.workflow.editorial_requests import request,obj,STRING
    import utils.langgraph_utils as language
    state=state_for(tmp_path);values=iter([{'title':'','neighbor':'original'},{'title':'Fixed','neighbor':'rewritten'}])
    class Model:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,message):return SimpleNamespace(content=json.dumps(next(values)),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    def validate(v):
        if not v['title']:raise EditorialStructureError('Empty title',[('title',)])
    with pytest.raises(EditorialOutputError,match='valid editorial content'):
        request(state,'editorial_metadata',{},obj({'title':STRING,'neighbor':STRING}),
                directory='editorial/test',validator=validate)


def test_edit_budget_is_sample_wide_and_corruption_fails_closed(tmp_path):
    from src.workflow.editorial_requests import read,save
    state=state_for(tmp_path)
    for i in range(3):pipeline.charge(state,'capacity',str(i))
    with pytest.raises(EditorialOutputError,match='exhausted'):pipeline.charge(state,'capacity','fourth')
    path=Path(state['sample_edit_budget_dir'])/'editorial_budget.json'
    value=read(path,state['editorial_budget']['input_digest']);value['charges'][0]['ordinal']=8;save(path,value)
    with pytest.raises(ValueError,match='Corrupt'):pipeline.charge(state,'capacity','one')


def test_new_paper_contract_keeps_abt_but_rejects_old_cache_identity(tmp_path):
    from src.workflow.content_contracts import paper_fields
    from src.workflow.paper_cache import extraction_identity
    state=state_for(tmp_path)
    fields=paper_fields(state)
    assert fields['narrative_content']['therefore']==state['raw_text']
    assert not set(fields)&{'source_document','source_candidate','verified_claims','evidence_bank'}
    new=extraction_identity({'preparation_policy_version':'sample_editorial_v1','code_identity':{}})
    old=extraction_identity({'preparation_policy_version':'sample_source_science_v2','code_identity':{}})
    assert new!=old and new['foundation_contract']=='organized_editorial_v1'
    assert 'config/prompts/editorial_abt.txt' in new['code']


def test_unparseable_wire_response_uses_only_shared_format_allowance(monkeypatch,tmp_path):
    from src.workflow.editorial_requests import request,obj,STRING
    import utils.langgraph_utils as language
    state=state_for(tmp_path);values=iter(['broken', '{"title":"Repaired"}']);calls=[]
    original=language.extract_json
    def parse(text):
        if text=='broken':raise ValueError('malformed wire JSON')
        return original(text)
    class Model:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,message):
            calls.append(message)
            return SimpleNamespace(content=next(values),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(language,'extract_json',parse)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    assert request(state,'editorial_metadata',{},obj({'title':STRING}),directory='editorial/wire')=={'title':'Repaired'}
    assert len(calls)==2


def test_duplicate_charges_are_corrupt_even_with_valid_envelope(tmp_path):
    from src.workflow.editorial_requests import read,save
    state=state_for(tmp_path);pipeline.charge(state,'capacity','same')
    path=Path(state['sample_edit_budget_dir'])/'editorial_budget.json'
    ledger=read(path,state['editorial_budget']['input_digest'])
    ledger['charges'].append({**ledger['charges'][0],'ordinal':2});save(path,ledger)
    with pytest.raises(ValueError,match='duplicate'):pipeline.charge(state,'capacity','first')


def test_default_parser_restores_model_material_without_source_planner(monkeypatch,tmp_path):
    from src.agents.parser import Parser
    import src.agents.parser as parser_module
    import utils.source_pdf as native
    import utils.langgraph_utils as language
    state=state_for(tmp_path);original=state['raw_text'];calls=[]
    state['output_dir']=str(tmp_path/'parser')
    monkeypatch.setattr(Parser,'_extract_raw_text',lambda *a:(original+' converter',[object()]))
    monkeypatch.setattr(native,'extract_source_text',lambda *a:(original,{'native':'retained'}))
    monkeypatch.setattr(native,'bind_asset_captions',lambda *a:None)
    monkeypatch.setattr(parser_module,'create_model_dict',lambda:{})
    monkeypatch.setattr(parser_module,'PdfConverter',lambda **k:object())
    asset=tmp_path/'figure.png';Image.new('RGB',(200,100),'navy').save(asset)
    monkeypatch.setattr(Parser,'_extract_assets',lambda *a:({'1':{'caption':'Architecture','aspect':2,'path':str(asset)}},{}))
    class Model:
        def __init__(self,system,config,current,name):assert name=='parser'
        def reset(self):pass
        def step(self,message):
            data=json.loads(message.split('\nINPUT:\n',1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
            assert data['original_text']==original
            schema=json.loads(message.split('\nCOMPLETE OUTPUT JSON SCHEMA:\n',1)[1])
            keys=set(schema['properties']);calls.append(keys)
            if 'title' in keys:value={'title':'Shared Search','authors':'A. Researcher'}
            elif 'and' in keys:value={k:'Model narrative from original.' for k in keys}
            elif 'paper_sections' in keys:value=deepcopy(state['structured_sections'])
            else:value={'key_visual':'figure_1','problem_illustration':[],'method_workflow':['figure_1'],
                        'main_results':[],'comparative_results':[],'supporting':[]}
            return SimpleNamespace(content=json.dumps(value),input_tokens=2,output_tokens=3)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    result=Parser()(state)
    assert not result['errors'] and len(calls)==4
    assert result['raw_text']==original and result['source_extraction_report']=={'native':'retained'}
    assert result['narrative_content']['therefore']=='Model narrative from original.'
    assert result['structured_sections']['paper_sections'][0]['key_points']==[original]
    assert not any(result.get(key) for key in ('source_document','source_narrative','verified_claims','evidence_bank'))
