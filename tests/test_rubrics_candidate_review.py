"""Human publication boundary, full semantic coverage and stage permission checks."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from src.rubrics import candidates, constraints, mining
from src.rubrics.library import LibraryStore
from src.rubrics.providers import configuration
from src.rubrics.storage import IntegrityError, read, write
from test_rubrics_framework import Models, rule, semantic_response
from utils.persistence import digest, file_hash


def review_package(tmp_path, *, cap=3, blocked=False, with_sources=False):
    library = tmp_path/'library'
    parent = LibraryStore(library).publish([rule()],parent_version=None,source_batch_digest='seed')
    contract = constraints.snapshot()
    observations = [{'id':'o1','type':'preference','observation':'Small legend','evidence':'Visible legend'},
                    {'id':'o2','type':'preference','observation':'Aligned headings','evidence':'Visible heading'}]
    sources=[]
    if with_sources:
        bundle=tmp_path/'poster evidence';bundle.mkdir()
        (bundle/'poster.png').write_bytes(b'Frozen fixture image')
        sources=[{'poster_id':'poster1','paper_sha256':'paperhash','bundle_path':str(bundle),
                  'files':{'poster.png':file_hash(bundle/'poster.png')}}]
        for observation in observations:observation.update(poster_id='poster1',paper_sha256='paperhash')
    rules = [dict(rule('one','Explain legend symbols'),evidence_refs=['o1']),
             dict(rule('two','Align headings'),evidence_refs=['o2'])]
    assessments = []
    existing = list(parent['rules'])
    for index, r in enumerate(rules):
        response = semantic_response({'candidate':r,'existing':existing})
        if blocked and index == 1:
            response['engineering_review']['stage_actions'][0]['actions'] = ['resize_arbitrarily']
        review = mining.validate_comparison(r,existing,response,contract)
        assessments.append({'candidate_id':r['id'],'rule_digest':digest(r),
                            'decision':review['decision'],'reviews':[review]})
        if review['decision'] == 'novel':existing.append(r)
    identity = {'seal':'fixture_seal','publication_policy':'human_review_v1','engineering_contract':contract}
    root = candidates.prepare(library,parent,rules,assessments,observations,contract,identity,tmp_path/'job',cap,sources=sources)
    return root, parent


def decision_file(root, *, action='approve', ids=None):
    value = json.loads((root/'decision.template.json').read_text())
    value.update(decision=action, approved_ids=['one'] if ids is None else ids,
                 reviewer='test human',comment='Explicit fixture approval')
    path = root/'human-input.json'
    path.write_text(json.dumps(value))
    return path


@pytest.mark.parametrize('defect', ['missing_id','duplicate_id','unknown_id','missing_stage','duplicate_stage','unsupported_quote'])
def test_review_requires_full_rule_and_stage_coverage(defect):
    candidate = rule('new');existing = [rule('old'),rule('other')]
    response = semantic_response({'candidate':candidate,'existing':existing})
    if defect == 'missing_id':response['comparisons'].pop()
    elif defect == 'duplicate_id':response['comparisons'][1]['existing_id'] = 'old'
    elif defect == 'unknown_id':response['comparisons'][1]['existing_id'] = 'unknown'
    elif defect == 'missing_stage':response['engineering_review']['stage_actions'].pop()
    elif defect == 'duplicate_stage':response['engineering_review']['stage_actions'][1]['stage']='writing'
    else:response['engineering_review']['violations']=[{'constraint_id':'family','rule_quote':'not in candidate','reason':'fixture'}]
    with pytest.raises(ValueError):
        mining.validate_comparison(candidate,existing,response,constraints.snapshot())


def test_local_forbidden_action_overrides_model_compliant_and_duplicate():
    candidate = rule('new');existing=[rule('old')]
    response=semantic_response({'candidate':candidate,'existing':existing},'duplicate')
    response['engineering_review']['stage_actions'][0]['actions']=['allocate_frames']
    reviewed=mining.validate_comparison(candidate,existing,response,constraints.snapshot())
    assert reviewed['decision']=='conflict'
    assert reviewed['engineering']['local_violations']==[{'stage':'writing','forbidden_actions':['allocate_frames']}]


def test_empty_library_still_gets_engineering_review(tmp_path):
    model=Models()
    value=mining.reconcile(rule(),[],model,tmp_path,configuration()['mining'])
    assert model.calls==['reconciler'] and len(value['reviews'])==1


def test_engineering_quote_can_identify_serialized_stage_scope():
    candidate=rule('new', 'Every applicable stage must resize the type to fit.')
    response=semantic_response({'candidate':candidate,'existing':[]})
    response['engineering_review']['status']='conflict'
    response['engineering_review']['violations']=[{'constraint_id':'stages',
        'rule_quote':'"applicable_stages": ["writing", "capacity"]','reason':'Writer and capacity cannot resize the type.'}]
    assert mining.validate_comparison(candidate,[],response,constraints.snapshot())['decision']=='conflict'


def test_permissions_preserve_actor_styles_but_not_writer_or_capacity_geometry():
    contract=constraints.snapshot()
    assert 'change_font_size' in contract['allowed_actions']['revision']
    for stage in ('writing','capacity'):
        assert not {'allocate_frames','change_font_size','change_family'} & set(contract['allowed_actions'][stage])
    assert not any('change_family' in a or 'edit_assets' in a for a in contract['allowed_actions'].values())


def test_prepare_and_pending_template_never_publish(tmp_path):
    root,parent=review_package(tmp_path)
    store=LibraryStore(tmp_path/'library'); before=(store.root/'active.json').read_bytes()
    assert candidates.load(root)['eligible_ids']==['one','two']
    assert '尚未发布' in (root/'review.md').read_text()
    with pytest.raises(ValueError,match='explicit human'):
        candidates.publish(root,root/'decision.template.json')
    assert (store.root/'active.json').read_bytes()==before
    assert store.active()==parent and not (root/'human_decision.json').exists()
    assert not (store.root/'rubrics_v1').exists()


def test_human_selects_subset_once_and_recovery_is_idempotent(tmp_path):
    root,parent=review_package(tmp_path)
    decision=decision_file(root)
    result=candidates.publish(root,decision)
    assert result['status']=='PUBLISHED' and result['added']==1 and result['name']=='rubrics_v1'
    store=LibraryStore(tmp_path/'library')
    assert [r['id'] for r in store.active()['rules']]==['seed','one']
    assert store.active()['schema_version']==2
    assert all(len(r)==9 and 'revision_guidance' not in r for r in store.active()['rules'])
    assert store.version(parent['version'])==parent
    assert candidates.publish(root,decision)==result
    decision_file(root,ids=['two'])
    with pytest.raises(IntegrityError,match='different human decision'):
        candidates.publish(root,decision)


def test_reject_all_records_decision_without_touching_library(tmp_path):
    root,parent=review_package(tmp_path)
    decision=decision_file(root,action='reject',ids=[])
    assert candidates.publish(root,decision)['status']=='REJECTED'
    assert LibraryStore(tmp_path/'library').active()==parent
    assert not (tmp_path/'library/rubrics_v1').exists()


def test_publish_rechecks_linked_source_evidence_before_recording_approval(tmp_path):
    root,parent=review_package(tmp_path,with_sources=True)
    assert '[最终海报]' in (root/'review.md').read_text()
    (tmp_path/'poster evidence/poster.png').write_bytes(b'Changed source')
    with pytest.raises(IntegrityError,match='source evidence changed'):
        candidates.publish(root,decision_file(root))
    assert LibraryStore(tmp_path/'library').active()==parent
    assert not (root/'human_decision.json').exists()


def test_rehashed_package_still_requires_prior_eligible_candidate_comparison(tmp_path):
    root,parent=review_package(tmp_path)
    package=read(root/'package.json')
    assessment=package['assessments'][1]
    response=semantic_response({'candidate':package['candidates'][1],'existing':parent['rules']})
    assessment['reviews']=[mining.validate_comparison(package['candidates'][1],parent['rules'],
                                                    response,package['engineering_contract'])]
    new_root=root.parent/digest(package)
    write(new_root/'package.json',package)
    with pytest.raises(IntegrityError,match='coverage is incomplete'):candidates.load(new_root)


@pytest.mark.parametrize('defect',['blocked','unknown','duplicate','over_cap','review_id','parent','empty_approval'])
def test_invalid_or_overriding_approval_cannot_change_library(tmp_path,defect):
    root,parent=review_package(tmp_path,cap=2 if defect=='over_cap' else 3,blocked=defect=='blocked')
    ids={'blocked':['two'],'unknown':['absent'],'duplicate':['one','one'],'over_cap':['one','two'],
         'empty_approval':[]}.get(defect,['one'])
    path=decision_file(root,ids=ids)
    if defect in ('review_id','parent'):
        value=json.loads(path.read_text());value['review_id' if defect=='review_id' else 'parent_version']='different'
        path.write_text(json.dumps(value))
    with pytest.raises((ValueError,IntegrityError)):
        candidates.publish(root,path)
    assert LibraryStore(tmp_path/'library').active()==parent
    assert not (root/'human_decision.json').exists()


@pytest.mark.parametrize('defect',['rule','coverage','engineering','contract','parent_advanced'])
def test_changed_review_or_parent_requires_revalidation(tmp_path,monkeypatch,defect):
    root,parent=review_package(tmp_path);path=decision_file(root)
    if defect=='contract':
        changed=constraints.snapshot();changed['version']='changed'
        monkeypatch.setattr(candidates,'snapshot',lambda:changed)
    elif defect=='parent_advanced':
        LibraryStore(tmp_path/'library').publish(parent['rules']+[rule('elsewhere')],
            parent_version=parent['version'],source_batch_digest='another review')
    else:
        value=read(root/'package.json')
        if defect=='rule':value['candidates'][0]['requirement']='Changed after review'
        elif defect=='coverage':value['assessments'][0]['reviews'][0]['comparisons']=[]
        else:value['assessments'][0]['reviews'][0]['engineering']['status']='uncertain'
        write(root/'package.json',value)  # Valid envelope checksum does not bypass package binding.
    before=(tmp_path/'library/active.json').read_bytes()
    with pytest.raises(IntegrityError):candidates.publish(root,path)
    assert (tmp_path/'library/active.json').read_bytes()==before


def test_publish_recovers_crash_after_pointer_commit_without_new_version(tmp_path,monkeypatch):
    root,parent=review_package(tmp_path);path=decision_file(root)
    original=LibraryStore.publish
    def interrupted(self,*args,**kwargs):
        original(self,*args,**kwargs)
        raise OSError('Crash after committed publication')
    with monkeypatch.context() as patch:
        patch.setattr(LibraryStore,'publish',interrupted)
        with pytest.raises(OSError):candidates.publish(root,path)
    assert not (root/'publication.json').exists() and (root/'human_decision.json').exists()
    result=candidates.publish(root,path)
    assert result['name']=='rubrics_v1'
    assert len(list((tmp_path/'library/versions').iterdir()))==2


def test_cli_requires_separate_human_decision_and_supports_inspection(tmp_path,capsys):
    from rubrics_poster.iteration import main
    root,parent=review_package(tmp_path)
    assert main(['review-candidates',str(root)])==0
    assert json.loads(capsys.readouterr().out)['eligible_ids']==['one','two']
    assert main(['publish-candidates',str(root),'--decision',str(root/'decision.template.json')])==1
    capsys.readouterr()
    assert LibraryStore(tmp_path/'library').active()==parent
    assert main(['publish-candidates',str(root),'--decision',str(decision_file(root))])==0
    assert json.loads(capsys.readouterr().out)['name']=='rubrics_v1'
