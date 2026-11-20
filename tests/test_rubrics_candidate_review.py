"""Human publication, explicit stage assignment and complete quality comparisons."""
import json

import pytest

from src.rubrics import candidates
from src.rubrics.quality import validate_semantic
from src.rubrics.library import LibraryStore
from src.rubrics.storage import IntegrityError, read, write
from test_rubrics_framework import rule
from utils.persistence import digest, file_hash


def review_package(tmp_path, *, cap=3, first_decision='novel', earlier_decision='novel', with_sources=False):
    library = tmp_path/'library'
    parent = LibraryStore(library).publish([rule()],parent_version=None,source_batch_digest='seed')
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
        del r['applicable_stages']
        decision = first_decision if index == 0 else 'novel'
        response = {'comparisons': [
            {'existing_id': e['id'], 'decision': earlier_decision if e['id'] == 'one' else decision,
             'reason': f'Fixture reason for {e["id"]}.'} for e in existing]}
        review = validate_semantic(r,existing,response)
        assessments.append({'candidate_id':r['id'],'rule_digest':digest(r),
                            'decision':review['decision'],'reviews':[review]})
        existing.append(r)
    identity = {'seal':'fixture_seal','publication_policy':'human_review_v2'}
    root = candidates.prepare(library,parent,rules,assessments,observations,identity,tmp_path/'job',cap,sources=sources)
    return root, parent


def decision_file(root, *, action='approve', ids=None):
    value = json.loads((root/'decision.template.json').read_text())
    entries = [{'candidate_id': i, 'applicable_stages': ['review', 'palette']}
               for i in (['one'] if ids is None else ids)]
    value.update(decision=action, approved_rules=entries, reviewer='test human', comment='Explicit fixture approval')
    path = root/'human-input.json'
    path.write_text(json.dumps(value))
    return path


def test_prepare_and_pending_template_never_publish(tmp_path):
    root,parent=review_package(tmp_path)
    store=LibraryStore(tmp_path/'library'); before=(store.root/'active.json').read_bytes()
    assert candidates.load(root)['eligible_ids']==['one','two']
    package = candidates.load(root)
    assert all('applicable_stages' not in r and len(r) == 8 for r in package['candidates'])
    assert 'engineering_contract' not in package
    assert '尚未发布' in (root/'review.md').read_text()
    with pytest.raises(ValueError,match='explicit human'):
        candidates.publish(root,root/'decision.template.json')
    assert (store.root/'active.json').read_bytes()==before
    assert store.active()==parent and not (root/'human_decision.json').exists()
    assert not (store.root/'rubrics_v1').exists()


def test_review_document_groups_recommendations_and_links_comparison_reasons(tmp_path):
    root, parent = review_package(tmp_path, first_decision='duplicate', earlier_decision='partial_overlap')
    doc = (root/'review.md').read_text()
    assert '### 新颖（0）' in doc and '### 部分重叠（1）' in doc and '### 重复（1）' in doc
    assert '[two](#candidate-two)' in doc and '<a id="candidate-two"></a>' in doc
    assert f'库内规则 [seed](../../versions/{parent["version"]}/library.json)' in doc
    assert '同批候选 [one](#candidate-one)' in doc
    assert '比较理由：Fixture reason for one.' in doc and '对方规则：Explain legend symbols' in doc
    assert '<details><summary>完整语义比较记录</summary>' in doc


def test_human_selects_subset_once_and_recovery_is_idempotent(tmp_path):
    root,parent=review_package(tmp_path)
    decision=decision_file(root)
    result=candidates.publish(root,decision)
    assert result['status']=='PUBLISHED' and result['added']==1 and result['name']=='rubrics_v1'
    store=LibraryStore(tmp_path/'library')
    assert [r['id'] for r in store.active()['rules']]==['seed','one']
    assert store.active()['schema_version']==2
    assert all(len(r)==9 and 'revision_guidance' not in r for r in store.active()['rules'])
    assert store.active()['rules'][-1]['applicable_stages'] == ['review', 'palette']
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


def test_rehashed_package_still_requires_prior_duplicate_candidate_comparison(tmp_path):
    root,parent=review_package(tmp_path, first_decision='duplicate')
    package=read(root/'package.json')
    assessment=package['assessments'][1]
    response = {'comparisons': [c for c in assessment['reviews'][0]['comparisons'] if c['existing_id'] != 'one']}
    assessment['reviews'] = [validate_semantic(package['candidates'][1], parent['rules'], response)]
    new_root=root.parent/digest(package)
    write(new_root/'package.json',package)
    with pytest.raises(IntegrityError,match='coverage is incomplete'):candidates.load(new_root)


@pytest.mark.parametrize('defect',['unknown','duplicate','over_cap','review_id','parent','empty_approval'])
def test_invalid_or_overriding_approval_cannot_change_library(tmp_path,defect):
    root,parent=review_package(tmp_path,cap=2 if defect=='over_cap' else 3)
    ids={'unknown':['absent'],'duplicate':['one','one'],'over_cap':['one','two'],
         'empty_approval':[]}.get(defect,['one'])
    path=decision_file(root,ids=ids)
    if defect in ('review_id','parent'):
        value=json.loads(path.read_text());value['review_id' if defect=='review_id' else 'parent_version']='different'
        path.write_text(json.dumps(value))
    with pytest.raises((ValueError,IntegrityError)):
        candidates.publish(root,path)
    assert LibraryStore(tmp_path/'library').active()==parent
    assert not (root/'human_decision.json').exists()


@pytest.mark.parametrize('defect',['rule','coverage','recommendation','parent_advanced'])
def test_changed_review_or_parent_requires_revalidation(tmp_path,defect):
    root,parent=review_package(tmp_path);path=decision_file(root)
    if defect=='parent_advanced':
        LibraryStore(tmp_path/'library').publish(parent['rules']+[rule('elsewhere')],
            parent_version=parent['version'],source_batch_digest='another review')
    else:
        value=read(root/'package.json')
        if defect=='rule':value['candidates'][0]['requirement']='Changed after review'
        elif defect=='coverage':value['assessments'][0]['reviews'][0]['comparisons']=[]
        else:value['assessments'][0]['reviews'][0]['decision']='uncertain'
        write(root/'package.json',value)  # Valid envelope checksum does not bypass package binding.
    before=(tmp_path/'library/active.json').read_bytes()
    with pytest.raises(IntegrityError):candidates.publish(root,path)
    assert (tmp_path/'library/active.json').read_bytes()==before


@pytest.mark.parametrize('recommendation', ['duplicate', 'partial_overlap', 'conflict', 'uncertain'])
def test_user_can_select_quality_candidate_with_any_complete_recommendation(tmp_path, recommendation):
    root, _ = review_package(tmp_path, first_decision=recommendation)
    assert read(root/'package.json')['assessments'][0]['decision'] == recommendation
    assert candidates.publish(root, decision_file(root))['approved_ids'] == ['one']


@pytest.mark.parametrize('stages', [None, [], ['review','review'], ['unknown'], [dict(invalid=True)]])
def test_invalid_human_stage_assignment_is_refused_before_recording(tmp_path, stages):
    root, parent = review_package(tmp_path)
    path = decision_file(root)
    decision = json.loads(path.read_text())
    decision['approved_rules'][0]['applicable_stages'] = stages
    path.write_text(json.dumps(decision))
    with pytest.raises(ValueError):
        candidates.publish(root,path)
    assert not (root/'human_decision.json').exists()
    assert LibraryStore(tmp_path/'library').active() == parent


def test_same_selected_ids_with_changed_stages_are_a_different_decision(tmp_path):
    root, _ = review_package(tmp_path)
    path = decision_file(root)
    candidates.publish(root,path)
    decision = json.loads(path.read_text())
    decision['approved_rules'][0]['applicable_stages'] = ['planning']
    path.write_text(json.dumps(decision))
    with pytest.raises(IntegrityError, match='different human decision'):
        candidates.publish(root,path)


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
