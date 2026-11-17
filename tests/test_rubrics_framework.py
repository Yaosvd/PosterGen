"""Offline contracts for versioning, executable feedback, sealed mining and quotas."""
from copy import deepcopy
from pathlib import Path
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from src.rubrics import program, refinement, mining, rounds
from src.rubrics.library import LibraryStore, append_guidance
from src.rubrics.providers import configuration, ExternalModels
from src.rubrics.storage import IntegrityError, WaitingForConfiguration, RequestUncertain, request_once, read, write
from utils.persistence import file_hash, digest, _atomic_json
from src.critic.scoring import current_policy, IMPORTANT
from discrete_score_fixtures import grade_report, scored_result


def rule(name='seed', requirement='Keep readable text'):
    return dict(id=name,revision=1,dimension='legibility',type='preference',requirement=requirement,
        applicability='Text modules',criterion='Text is legible',
        applicable_stages=['writing','capacity'],evidence_refs=[])


def library(tmp_path):
    return LibraryStore(tmp_path/'library').publish([rule()],parent_version=None,source_batch_digest='fixture')


def test_library_empty_requires_seed_but_retained_requests_are_identical(tmp_path):
    store = LibraryStore(tmp_path)
    empty = store.active()
    prompt = 'Existing\nexact prompt\twith whitespace '
    assert append_guidance(prompt,{'generation_rubrics_snapshot':empty},'editorial_writer')==prompt
    with pytest.raises(WaitingForConfiguration,match='WAITING_SEED'):store.active(required=True)
    r = library(tmp_path)
    assert append_guidance(prompt,{'generation_rubrics_snapshot':r},'editorial_content_critic')==prompt
    assert append_guidance(prompt,{'generation_rubrics_snapshot':r},'editorial_visual_critic')==prompt
    assert append_guidance(prompt,{'generation_rubrics_snapshot':r},'editorial_writer').startswith(prompt+'\n\n<GENERATION_RUBRICS>')
    assert append_guidance(prompt,{'generation_rubrics_snapshot':r},'editorial_curator')==prompt


def test_publication_compare_and_swap_and_immutable_history(tmp_path):
    old=library(tmp_path); store=LibraryStore(tmp_path/'library')
    new=store.publish(old['rules']+[rule('extra','Align modules')],parent_version=old['version'],source_batch_digest='round')
    assert store.version(old['version'])==old and store.active()==new
    assert store.publish(new['rules'],parent_version=old['version'],source_batch_digest='round')==new
    with pytest.raises(IntegrityError,match='UPDATE_CONFLICT'):
        store.publish(old['rules']+[rule('third')],parent_version=old['version'],source_batch_digest='other')
    with pytest.raises(ValueError,match='append-only'):
        store.publish([rule('replaced')],parent_version=new['version'],source_batch_digest='next')


def test_durable_model_calls_are_single_send_under_threads_and_restart(tmp_path):
    calls=[]
    def call():calls.append(1);return {'answer':'saved'}
    with ThreadPoolExecutor(max_workers=8) as pool:
        values=list(pool.map(lambda _:request_once(tmp_path,{'request':1},call),range(16)))
    assert calls==[1] and all(v=={'answer':'saved'} for v in values)
    with pytest.raises(IntegrityError):request_once(tmp_path,{'request':2},call)
    other=tmp_path/'uncertain'
    with pytest.raises(TimeoutError):request_once(other,{},lambda:(_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(RequestUncertain):request_once(other,{},call)
    assert len(calls)==1


@pytest.mark.parametrize('source',[
    'import os','open("/tmp/x", "w")','x = (1).__class__','while True: pass',
    'x = [0] * 100000000','exec("pass")','draw({**{}})','def f(): pass','draw(__import__("os"))',
    'x=2**999999','x = [n for n in [1,2]]'])
def test_program_forbids_unbounded_or_external_operations(source):
    with pytest.raises((ValueError,SyntaxError)):program.execute(source)


def test_program_has_real_bounded_calculation_and_control():
    value=program.execute("poster({'modules': []})\nx = 2 * 3\nfor y in [1,2]:\n if y > 0:\n  draw({'x': x + y})\n")
    assert value['elements']==[{'x':7},{'x':8}]


def test_program_rejects_exponential_container_expansion():
    source='x = [0]\n'+'x = [x, x]\n'*30+"poster({})\ndraw({'x':x})"
    with pytest.raises(ValueError,match='expansion'):program.execute(source)


def frozen(monkeypatch,tmp_path):
    from test_editorial_finalization import freeze
    state=freeze(monkeypatch,tmp_path)
    from src.agents.font_agent import FontAgent
    FontAgent()(state)
    state['generation_rubrics_snapshot']=library(tmp_path)
    state['current_candidate']={'candidate_id':'fixture','candidate_dir':state['output_dir'],'status':'planned'}
    return fake_render(state,Path(state['output_dir'])/'initial')


def fake_render(state,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'poster.pptx').write_bytes(b'offline deck')
    Image.new('RGB',(100,60),'white').save(directory/'poster.png')
    state['current_candidate']={**state['current_candidate'],'status':'rendered',
        'pptx_path':str(directory/'poster.pptx'),'png_path':str(directory/'poster.png')}
    return state


def model(state,role,payload,schema,root,images=()):
    if role=='review':
        return {'checks':[{'rule_id':'seed','status':'violated','evidence':'Body can improve','locations':[],
                           'action':'Clarify the explanation'}]}
    return {'program':payload['program'].replace('Shared method','Clear method'),'change_summary':'Changed module titles'}


def test_c0_replays_and_actor_can_rewrite_module_content(monkeypatch,tmp_path):
    state=frozen(monkeypatch,tmp_path)
    source=program.export(state)
    replay=program.materialize(program.execute(source),state)
    assert replay['styled_layout']==state['styled_layout']
    changed=program.materialize(program.execute(source.replace('Shared method','Updated method')),state)
    assert all(e['section_title']=='Updated method' for e in changed['styled_layout'] if e['type']=='section_title')
    assert state['editorial_candidate']['modules'][0]['title']=='Shared method'


def test_c0_preserves_all_active_family_drawing_documents(monkeypatch,tmp_path):
    from src.layout.families import LayoutFamilyRegistry
    from test_editorial_generation import state_for,install
    from src.workflow import editorial_pipeline as pipeline
    from src.layout.editorial_layout import measure
    from src.agents.font_agent import FontAgent
    monkeypatch.setattr(pipeline,'fit',lambda s,c,z:measure(s,c,z))
    monkeypatch.setattr(pipeline,'edit',lambda *a,**k:False)
    for family in LayoutFamilyRegistry().ids():
        state=install(state_for(tmp_path/family,family))
        pipeline.charge(state,'curator','offline_fixture')
        pipeline.editorial_joint_node(state);pipeline.editorial_compile_node(state);FontAgent()(state)
        rebuilt=program.materialize(program.execute_isolated(program.export(state)),state)
        assert rebuilt['styled_layout']==state['styled_layout'],family


def test_one_revision_preserves_initial_and_replays_without_model(monkeypatch,tmp_path):
    state=frozen(monkeypatch,tmp_path);original=deepcopy(state['styled_layout']);calls=[]
    def request(*args,**kwargs):calls.append(args[1]);return model(*args,**kwargs)
    final=refinement.refine_once(state,request=request,renderer=fake_render,measure=lambda s:s)
    assert final['refinement_result']['variant']=='P1',final['refinement_result']
    assert calls==['review','revision'] and state['styled_layout']==original
    refinement.assert_evaluation_ready(final,compiled=True)
    # G may add freshly computed measurement fields without changing drawing identity.
    final['section_fit_analysis']={'measured':'new'}
    refinement.assert_evaluation_ready(final,compiled=True)
    again=refinement.refine_once(state,request=lambda *a,**k:pytest.fail('Repeated charged request'),renderer=fake_render)
    assert again['refinement_result']['variant']=='P1'
    again['styled_layout'][0]['x']+=.2
    with pytest.raises(IntegrityError):refinement.assert_evaluation_ready(again,compiled=True)
    root=Path(state['refinement_directory'])
    assert all((root/name).exists() for name in ('P0.png','P0.pptx','C0.py','C1.py','changes.diff','actor.json','review.json','selection.json'))


@pytest.mark.parametrize('failure',['review','revision','execution'])
def test_technical_failures_fall_back_once_to_initial(monkeypatch,tmp_path,failure):
    state=frozen(monkeypatch,tmp_path);first=deepcopy(state['current_candidate']);calls=[]
    def request(st,role,*args,**kwargs):
        calls.append(role)
        if role==failure:raise ValueError('invalid fixture reply')
        value=model(st,role,*args,**kwargs)
        if failure=='execution' and role=='revision':value['program']='import os'
        return value
    final=refinement.refine_once(state,request=request,renderer=fake_render,measure=lambda s:s)
    assert final['current_candidate']==first and final['refinement_result']['variant']=='P0'
    assert final['refinement_result']['status']==failure+'_failed'
    assert calls==(['review'] if failure=='review' else ['review','revision'])


def test_cancel_and_corruption_never_become_low_quality_fallback(monkeypatch,tmp_path):
    from utils.concurrency import WorkStopped
    state=frozen(monkeypatch,tmp_path)
    def stop(*a,**k):raise WorkStopped()
    with pytest.raises(WorkStopped):refinement.refine_once(state,request=stop,renderer=fake_render)
    state['styled_layout'][0]['x']+=.1
    with pytest.raises(IntegrityError):refinement.refine_once(state,request=model,renderer=fake_render)


def test_real_cpu_renderer_replays_c0_and_scores_revised_artifacts(monkeypatch,tmp_path):
    state=frozen(monkeypatch,tmp_path)
    state=refinement.render(state,Path(state['output_dir'])/'actual_initial')
    final=refinement.refine_once(state,request=model)
    assert final['refinement_result']['variant']=='P1',final['refinement_result']
    refinement.assert_evaluation_ready(final,compiled=True)
    assert final['render_fit_report']['status'] in {'passed','failed','partial','unavailable'}
    from src.critic.section_fit import SectionFitEvaluator
    from src.critic.base import CriticContext
    SectionFitEvaluator().evaluate(CriticContext(final,final['critic_config']))
    refinement.assert_evaluation_ready(final,compiled=True)
    assert final['current_candidate']['png_path']!=state['current_candidate']['png_path']


def test_empty_provider_slots_never_silently_call_glm(tmp_path):
    config = configuration()
    config['external_models']['extractor'].update(provider=None, model=None, base_url=None)
    with pytest.raises(WaitingForConfiguration,match='extractor'):ExternalModels(config).check()
    assert not hasattr(ExternalModels(), 'embed')
    assert not tmp_path.joinpath('charge.json').exists()


@pytest.mark.parametrize('vectors',[[[0,0]],[[float('nan'),1]],[[1,2],[1]],[[True,1]]])
def test_invalid_clustering_vectors_rejected(vectors):
    with pytest.raises(ValueError):mining.clusters(vectors,8,17)


def test_kmeans_handles_empty_duplicate_and_singleton():
    assert mining.clusters([],8,3)==[]
    assert mining.clusters([[1,0],[1,0]],8,3)==[[0,1]]
    assert mining.clusters([[1,0]],8,3)==[[0]]
    assert mining.clusters([[1,0],[0,1],[-1,0]],2,7)==mining.clusters([[1,0],[0,1],[-1,0]],2,7)


def test_reservations_allow_30_workers_without_overfill_or_overbudget():
    manifest={'config':configuration(),'papers':[{'sha256':str(i)} for i in range(20)],'seed':7}
    state={'attempts':[]};families=['a','b','c']
    for _ in range(30):assert rounds.reserve(state,manifest,families)
    assert len(state['attempts'])==30
    assert max(sum(a['paper_index']==i for a in state['attempts']) for i in range(20))==20
    for a in state['attempts']:a.update(finished=True,result={'complete_score':True})
    while (a:=rounds.reserve(state,manifest,families)) is not None:
        a.update(finished=True,result={'complete_score':True})
    assert len(state['attempts'])==400
    failed={'attempts':[]}
    while (a:=rounds.reserve(failed,manifest,families)) is not None:
        a.update(finished=True,result={'complete_score':False})
    assert len(failed['attempts'])==1200
    assert all(sum(a['paper_index']==i for a in failed['attempts'])==60 for i in range(20))


def test_folder_requires_exact_20_and_flat_names_are_distinct(tmp_path):
    import fitz
    for i in range(20):
        doc=fitz.open();page=doc.new_page();page.insert_text((50,50),'Paper '+str(i));doc.save(tmp_path/f'Paper {i}.pdf');doc.close()
    selected=rounds.inputs(tmp_path)
    assert len(selected)==20 and len({s['title'] for s in selected})==20
    (tmp_path/'copy.pdf').write_bytes((tmp_path/'Paper 0.pdf').read_bytes())
    with pytest.raises(ValueError,match='Duplicate'):rounds.inputs(tmp_path)


def sealed(tmp_path):
    lib=library(tmp_path);samples=[]
    targets = {key:3 for key in IMPORTANT}
    reports = {False: grade_report(2, **targets, element_alignment=1),
               True: grade_report(2, **targets)}
    policy = current_policy()
    for paper in range(20):
        for i in range(20):
            pid=f'p{paper}_{i}';root=tmp_path/'bundles'/pid;root.mkdir(parents=True)
            report = reports[bool(i % 2)]
            _atomic_json(root/'evaluation.json',report)
            _atomic_json(root/'provenance.json',scored_result(report, **{'poster_id':pid,'sample_mode':'rubric-refine-score',
                'generation_rubrics':lib['version'],'round_identity':{'round_id':'round_fixture','manifest_digest':'offline-manifest'},'paper_id':'pdf_'+str(paper)}))
            write(root/'refinement/paper.json',{'original_text':'Original evidence'})
            Image.new('RGB',(8,8),'white').save(root/'poster.png')
            (root/'poster.pptx').write_bytes(b'offline deck')
            write(root/'refinement/selection.json',{'variant':'P0','rubrics':lib['version'],
                'artifact_hashes':{k:file_hash(root/('poster.'+k)) for k in ('pptx','png')}})
            samples.append({'poster_id':pid,'paper_sha256':str(paper),'bundle_path':str(root),
                'files':{str(p.relative_to(root)):file_hash(p) for p in root.rglob('*') if p.is_file()}})
    seal={'schema_version':2,'scoring_policy':policy,'scoring_policy_digest':policy['digest'],
          'manifest_digest':'offline-manifest','round_id':'round_fixture','route':'rubric-refine-score','library_version':lib['version'],
          'paper_hashes':list(map(str,range(20))),'samples':samples}
    write(tmp_path/'seal.json',seal)
    return seal


def test_seal_rejects_retained_routes_incomplete_counts_duplicates_and_tampering(tmp_path):
    value=sealed(tmp_path)
    assert len(list(mining.verified_samples(value)))==400
    for bad in ({**value,'route':'generate-score'},{**value,'samples':value['samples'][:-1]},
                {**value,'samples':[value['samples'][0]]*400}):
        with pytest.raises(ValueError):list(mining.verified_samples(bad))
    Path(value['samples'][0]['bundle_path'],'poster.png').write_bytes(b'changed')
    with pytest.raises(IntegrityError):list(mining.verified_samples(value))


def semantic_response(payload, decision='novel'):
    return {'comparisons':[{'existing_id':r['id'],'decision':decision,'reason':'Offline semantic decision'}
                           for r in payload['existing']],
            'engineering_review':{'status':'compliant','findings':[],
                'stage_actions':[{'stage':s,'actions':['inspect'],'reason':'Fixture check only'}
                                 for s in payload['candidate']['applicable_stages']]}}


class Models:
    def __init__(self):self.calls=[];self.groups=[];self.contracts={}
    def check(self,roles=()):pass
    def generate(self,role,payload,schema,root,images=()):
        self.calls.append(role)
        self.contracts.setdefault(role,set()).add(digest(payload.get('engineering_contract')))
        if role=='extractor':
            self.groups.append(payload['group'])
            return {'observations':[{'dimension':'layout','observation':'Measured gap',
                'evidence':'Visible gap','generalizable_lesson':'Balance layout'}]}
        if role=='summarizer':
            r=rule('unused','Balance '+payload['type']);r.pop('id');r.pop('revision')
            r.update(type=payload['type'],evidence_refs=[payload['observations'][0]['id']])
            return {'rules':[r]}
        return semantic_response(payload)


def test_full_400_sample_postprocess_and_resume_use_only_sealed_finals(tmp_path,monkeypatch):
    sealed(tmp_path);model=Models()
    monkeypatch.setattr(LibraryStore,'publish',lambda *a,**k:pytest.fail('Mining must never publish'))
    result=mining.process(tmp_path/'seal.json',tmp_path/'library',models=model)
    assert result['status']=='AWAITING_HUMAN_REVIEW' and result['added']==0 and result['candidate_count']==2
    assert model.calls.count('extractor')==400
    assert model.groups.count('preference') == model.groups.count('rejection') == 200
    assert model.calls.count('summarizer')==2
    calls=list(model.calls)
    assert mining.process(tmp_path/'seal.json',tmp_path/'library',models=model)==result
    assert model.calls==calls
    assert len(LibraryStore(tmp_path/'library').active()['rules'])==1
    from src.rubrics.candidates import load
    package=load(result['review_package'])
    assert len(package['sources'])==400
    assert model.contracts=={role:{digest(package['engineering_contract'])}
                            for role in ('extractor','summarizer','reconciler')}


def test_rule_cap_leaves_all_reviewed_candidates_for_human_selection(tmp_path):
    sealed(tmp_path);config=configuration();config['mining']['max_rules']=2
    result=mining.process(tmp_path/'seal.json',tmp_path/'library',models=Models(),config=config)
    assert result['status']=='AWAITING_HUMAN_REVIEW' and result['added']==0
    assert result['candidate_count']==2 and result['remaining_capacity']==1
    assert len(LibraryStore(tmp_path/'library').active()['rules'])==1


def test_missing_reconciler_is_pending_not_convergence(tmp_path):
    sealed(tmp_path)
    class Unconfigured(Models):
        def check(self,roles=()):
            if 'reconciler' in roles:raise WaitingForConfiguration('reconciler')
    result=mining.process(tmp_path/'seal.json',tmp_path/'library',models=Unconfigured())
    assert result['status']=='WAITING_REVIEW' and result['pending']
    assert len(LibraryStore(tmp_path/'library').active()['rules'])==1


def test_budget_reservations_are_durable_and_never_duplicate_on_retry(tmp_path):
    from src.rubrics.storage import BudgetExceeded
    b=mining.BudgetedModels(Models(),tmp_path,1)
    b.reserve(tmp_path/'one');b.reserve(tmp_path/'one')
    with pytest.raises(BudgetExceeded):b.reserve(tmp_path/'two')
    assert read(tmp_path/'budget.json')['requests']==['one']


def test_openai_compatible_api_preserves_raw_response_and_rejects_truncation(monkeypatch,tmp_path):
    import httpx
    config=configuration()
    config['external_models']['extractor'].update(provider='openai_compatible',model='explicit-test-model',
        base_url='https://fixture.invalid/v1',api_key_env='RUBRICS_TEST_KEY')
    monkeypatch.setenv('RUBRICS_TEST_KEY','secret-not-for-journals')
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.headers['authorization']=='Bearer secret-not-for-journals'
        data=json.loads(request.content)
        assert data['model']=='explicit-test-model'
        assert data['messages'][0]['content'][1]['type']=='image_url'
        return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'partial'}}]})
    client=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:client(transport=httpx.MockTransport(handler),**kwargs))
    image=tmp_path/'poster.png';Image.new('RGB',(4,4)).save(image)
    for _ in range(2):
        with pytest.raises(ValueError,match='incomplete'):
            ExternalModels(config).generate('extractor',{'paper':'fixture'},mining.OBSERVATIONS,tmp_path/'request',images=(image,))
    assert len(requests)==1
    assert read(tmp_path/'request/response.json')['raw']['choices'][0]['message']['content']=='partial'
    assert 'secret-not-for-journals' not in ''.join(p.read_text() for p in (tmp_path/'request').glob('*.json'))


@pytest.mark.parametrize('fault', ['report_policy','provenance_policy','round_manifest'])
def test_sealed_samples_require_same_frozen_evaluator_policy(tmp_path, fault):
    value = sealed(tmp_path)
    sample = value['samples'][0]
    root = Path(sample['bundle_path'])
    if fault == 'report_policy':
        report = json.loads((root/'evaluation.json').read_text())
        report['scoring_policy']['high_score_threshold'] = 80
        _atomic_json(root/'evaluation.json',report)
    else:
        provenance = json.loads((root/'provenance.json').read_text())
        if fault == 'provenance_policy':
            provenance['scoring_policy_digest'] = 'different-G'
        else:
            provenance['round_identity']['manifest_digest'] = 'different-round'
        _atomic_json(root/'provenance.json',provenance)
    # Rehash the bundle: provenance/policy agreement is checked independently of hashes.
    sample['files'] = {str(p.relative_to(root)):file_hash(p) for p in root.rglob('*') if p.is_file()}
    with pytest.raises(IntegrityError):list(mining.verified_samples(value))


def test_api_configuration_cannot_override_sealed_grouping_threshold(tmp_path):
    sealed(tmp_path)
    config = configuration()
    config['mining']['high_score_threshold'] = 80
    model = Models()
    with pytest.raises(ValueError,match='override'):
        mining.process(tmp_path/'seal.json',tmp_path/'library',models=model,config=config)
    assert model.calls == []
    _atomic_json(tmp_path/'api.json',config)
    with pytest.raises(ValueError,match='frozen evaluator'):
        configuration(tmp_path/'api.json')


def test_legacy_seal_cannot_be_mixed_into_new_scoring_round(tmp_path):
    value = sealed(tmp_path)
    value['schema_version'] = 1
    with pytest.raises(ValueError):list(mining.verified_samples(value))
