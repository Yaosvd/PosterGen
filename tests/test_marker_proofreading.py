"""Marker extraction plus one advisory, replayable spelling request; no live models."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from src.state.poster_state import create_state
from src.workflow.editorial_contract import paper_material, PAPER_KEYS, SAMPLE_KEYS, EditorialInterrupted
from utils.persistence import digest, file_hash
from utils.marker_proofreading import (paragraphs, apply_suggestions, proofread_marker,
                                      validate_report, quality_summary)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language,'create_model',lambda *a,**k:pytest.fail('Unexpected live model'))


def state_for(tmp_path, native='The first finding is significantly stronger after affixation.'):
    pdf=tmp_path/'paper.pdf'
    with pymupdf.open() as document:
        page=document.new_page()
        page.insert_text((30,50),native)
        document.save(pdf)
    state=create_state(str(pdf),text_model='local-text',vision_model='local-vision')
    state['output_dir']=str(tmp_path/'foundation')
    return state


def edit(before='frst',after='first',paragraph_id='p00001'):
    return {'paragraph_id':paragraph_id,'before':before,'after':after,'reason':'Missing letter.'}


def model(monkeypatch, value):
    import utils.langgraph_utils as language
    calls=[]
    class Model:
        def __init__(self,system,config,state,name):
            assert name=='parser'
            assert config.temperature==0 and not config.enable_thinking
        def reset(self):pass
        def step(self,message):
            calls.append(message)
            if isinstance(value,BaseException):raise value
            return SimpleNamespace(content=json.dumps(value) if isinstance(value,dict) else value,
                                   input_tokens=11,output_tokens=7)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    return calls


def test_paragraph_ids_preserve_exact_original_offsets():
    text='# Title\n\nA frst result.\n \nSecond paragraph.\n'
    values=paragraphs(text)
    assert len(values)==3 and [p['paragraph_id'] for p in values]==['p00001','p00002','p00003']
    assert all(text[p['start']:p['start']+len(p['text'])]==p['text'] for p in values)


@pytest.mark.parametrize('before,after',[
    ('frst','first'),('signifcantly','significantly'),('afxation','affixation'),
    ('infectional','inflectional'),('ﬁnding','finding'),('afﬁxation','affixation'),
    ('signifi-\ncantly','significantly'),
])
def test_local_spelling_edits_need_native_context(before,after):
    original='The '+before+' result is clear.'
    expected='The '+after+' result is clear.'
    text,accepted,rejected=apply_suggestions(original,[edit(before,after)],[expected])
    assert text==expected and len(accepted)==1 and not rejected
    assert accepted[0]['evidence']['pages']==[1]


@pytest.mark.parametrize('before,after',[
    ('3%','30%'),('3','4'),('−3','3'),('3.0','3'),('m/s','km/s'),
    ('improves','declines'),('a model','a better model'),('is better','is not better'),
    ('MethodA','MethodB'),('learning rate','training size'),('first.','first!'),
])
def test_numbers_units_entities_and_semantic_rewrites_do_not_apply(before,after):
    original='The '+before+' result is clear.'
    # Native text independently confirms the current wording, even when a
    # suggested alternate also appears in another paragraph.
    text,accepted,rejected=apply_suggestions(original,[edit(before,after)],
                                           [original,'The '+after+' result is clear.'])
    assert text==original and not accepted and len(rejected)==1


@pytest.mark.parametrize('text,before,after',[
    ('The $frst$ value.', 'frst','first'),
    ('The `frst` variable.', 'frst','first'),
    ('The \\(frst\\) value.', 'frst','first'),
    ('The Method2frst result.', 'frst','first'),
    ('The [frst](https://example.com) reference.', 'frst','first'),
    ('The <span id="frst"> text.', 'frst','first'),
])
def test_protected_syntax_never_changes_even_when_native_supports_it(text,before,after):
    actual,accepted,rejected=apply_suggestions(text,[edit(before,after)],[text.replace(before,after)])
    assert actual==text and not accepted and rejected[0]['rejection'].startswith('protected_')


def test_ambiguous_span_unknown_id_and_overlaps_stay_advisory():
    original='The frst result and frst result.'
    actual,accepted,rejected=apply_suggestions(original,[edit(),edit(paragraph_id='wrong')],[])
    assert actual==original and not accepted and len(rejected)==2
    original='The frst result is clear.'
    actual,accepted,rejected=apply_suggestions(original,[edit(),edit('The frst','The first')],
                                             ['The first result is clear.'])
    assert actual==original and not accepted and len(rejected)==2
    assert all(r['rejection']=='overlapping_suggestions' for r in rejected)


def test_native_word_elsewhere_does_not_authorize_change_or_correct_author_typos():
    original='This frst result concerns spelling.'
    for pages in (['The first finding is clear.'],[original,'This first result concerns spelling.'],[]):
        text,accepted,rejected=apply_suggestions(original,[edit()],pages)
        assert text==original and not accepted and rejected


def test_markdown_quote_and_adjacent_missing_letters_use_combined_native_context():
    marker='> Cliticisation always occurs afer afxation. A derived noun carries a postposition.'
    native='Cliticisation always occurs after affixation. A derived noun carries a postposition.'
    text,accepted,rejected=apply_suggestions(marker,[edit('afer','after'),edit('afxation','affixation')],[native])
    assert text=='> '+native and len(accepted)==2 and not rejected


def test_unconfirmed_neighbor_cannot_authorize_unrelated_edit():
    marker='> The frst finding folows from the method.'
    text,accepted,rejected=apply_suggestions(marker,[edit(),edit('folows','flows')],
        ['The first finding follows from the method.'])
    assert text==marker and not accepted and len(rejected)==2


def test_one_request_exact_patch_and_durable_replay(monkeypatch,tmp_path):
    state=state_for(tmp_path)
    original='The frst finding is significantly stronger after affixation.'
    calls=model(monkeypatch,{'edits':[edit()],'uncertain':[]})
    content=Path(state['output_dir'])/'content'
    text,report=proofread_marker(state,original,content)
    assert text==original.replace('frst','first') and report['status']=='corrected'
    assert len(calls)==1 and 'FORMAT CORRECTION:' not in calls[0]
    assert (content/'marker_raw.md').read_text()==original
    assert (content/'raw.md').read_text()==text
    assert validate_report(report,original,file_hash(state['pdf_path']))==text
    state['iteration_context']={'sample_id':'different','random_seed':99}
    assert proofread_marker(state,original,content)==(text,report) and len(calls)==1
    assert quality_summary(report)['scientific_truth_verified'] is False


def test_returned_response_replays_after_interruption_before_audit(monkeypatch,tmp_path):
    state=state_for(tmp_path);content=Path(state['output_dir'])/'content'
    calls=model(monkeypatch,{'edits':[edit()],'uncertain':[]})
    import utils.marker_proofreading as review
    atomic=review._atomic_json
    def interrupt(path,value):
        if path.name=='source_extraction.json':raise KeyboardInterrupt()
        return atomic(path,value)
    monkeypatch.setattr(review,'_atomic_json',interrupt)
    marker='The frst finding is significantly stronger after affixation.'
    with pytest.raises(KeyboardInterrupt):proofread_marker(state,marker,content)
    monkeypatch.setattr(review,'_atomic_json',atomic)
    text,report=proofread_marker(state,marker,content)
    assert text==marker.replace('frst','first') and len(calls)==1 and report['status']=='corrected'


@pytest.mark.parametrize('response',[TimeoutError('offline'), 'not JSON',
    {'edits':[{'before':'frst'}],'uncertain':[]},
    {'edits':[],'uncertain':[], 'rewritten_paper':'invented'}])
def test_failed_review_keeps_marker_without_retry_or_format_charge(monkeypatch,tmp_path,response):
    state=state_for(tmp_path);original='The frst result.'
    calls=model(monkeypatch,response)
    content=Path(state['output_dir'])/'content'
    text,report=proofread_marker(state,original,content)
    assert text==original and report['status']=='unavailable' and report['warnings']
    assert len(calls)==1
    assert proofread_marker(state,original,content)==(text,report) and len(calls)==1
    assert not list(Path(state['output_dir']).rglob('editorial_format_correction.json'))


def test_uncertain_and_unconfirmed_suggestions_do_not_block(monkeypatch,tmp_path):
    state=state_for(tmp_path)
    calls=model(monkeypatch,{'edits':[edit()], 'uncertain':[
        {'paragraph_id':'p00001','text':'frst','reason':'Possible author spelling.'}]})
    marker='An unrelated frst example.'
    text,report=proofread_marker(state,marker,Path(state['output_dir'])/'content')
    assert text==marker and len(calls)==1 and report['rejected_edits'] and report['uncertain']


def test_native_reference_failure_is_nonblocking(monkeypatch,tmp_path):
    state=state_for(tmp_path)
    import utils.marker_proofreading as review
    monkeypatch.setattr(review,'_native_pages',lambda *a:(_ for _ in ()).throw(RuntimeError('bad font')))
    model(monkeypatch,{'edits':[edit()],'uncertain':[]})
    text,report=proofread_marker(state,'The frst result.',Path(state['output_dir'])/'content')
    assert text=='The frst result.' and report['warnings'][0]['kind']=='native_reference_unavailable'


def test_interrupted_charge_never_resubmits(monkeypatch,tmp_path):
    state=state_for(tmp_path);content=Path(state['output_dir'])/'content'
    calls=model(monkeypatch,KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):proofread_marker(state,'Original paper.',content)
    assert not (content/'source_extraction.json').exists()
    text,report=proofread_marker(state,'Original paper.',content)
    assert text=='Original paper.' and report['status']=='unavailable' and len(calls)==1


def test_cooperative_stop_propagates(monkeypatch,tmp_path):
    state=state_for(tmp_path);state['_force_stop_requested']=lambda:True
    with pytest.raises(EditorialInterrupted):
        proofread_marker(state,'Original paper.',Path(state['output_dir'])/'content')


def test_corrupt_or_changed_completed_review_is_an_integrity_error(monkeypatch,tmp_path):
    state=state_for(tmp_path);content=Path(state['output_dir'])/'content'
    model(monkeypatch,{'edits':[],'uncertain':[]})
    proofread_marker(state,'Original paper.',content)
    with pytest.raises(ValueError,match='original changed'):
        proofread_marker(state,'Changed paper.',content)
    report=json.loads((content/'source_extraction.json').read_text())
    report['text_digest']='tampered'
    (content/'source_extraction.json').write_text(json.dumps(report))
    with pytest.raises(ValueError,match='identity/digest'):
        proofread_marker(state,'Original paper.',content)


def test_corrupt_interrupted_receipt_refuses_silent_fallback(monkeypatch,tmp_path):
    state=state_for(tmp_path);content=Path(state['output_dir'])/'content'
    model(monkeypatch,KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):proofread_marker(state,'Original paper.',content)
    path=Path(state['output_dir'])/'editorial/paper/proofreading/request_00.json'
    payload=json.loads(path.read_text());payload['payload']['prompt_digest']='changed'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='Corrupt'):
        proofread_marker(state,'Original paper.',content)


def test_empty_marker_is_a_real_extraction_failure(monkeypatch,tmp_path):
    state=state_for(tmp_path);calls=model(monkeypatch,{'edits':[],'uncertain':[]})
    with pytest.raises(ValueError,match='no usable'):
        proofread_marker(state,' \n',Path(state['output_dir'])/'content')
    assert not calls


def test_final_critic_sees_original_and_review_separately(tmp_path):
    state=state_for(tmp_path)
    state.update(raw_text='The first result.',marker_raw_text='The frst result.',
                 structured_sections={'paper_sections':[{'content':'The first result.'}]},
                 source_extraction_report={'version':'marker_spelling_review_v1','status':'corrected',
                     'edits':[edit()],'rejected_edits':[],'uncertain':[],'warnings':[]})
    payload=paper_material(state,original=True)
    assert payload['original_text']=='The frst result.' and payload['proofread_text']=='The first result.'
    assert payload['spelling_review']['edits']==[edit()]
    assert 'marker_raw_text' in PAPER_KEYS and 'marker_raw_text' in SAMPLE_KEYS


def test_cache_identity_binds_spelling_code_and_prompt():
    from src.workflow.paper_cache import extraction_identity
    settings={'preparation_policy_version':'sample_editorial_v1','code_identity':{
        'utils/marker_proofreading.py':'one','config/prompts/editorial_proofreading.txt':'one'}}
    expected=extraction_identity(settings)
    for name in settings['code_identity']:
        changed=deepcopy(settings);changed['code_identity'][name]='two'
        assert extraction_identity(changed)!=expected


def test_paper_cache_carries_original_correction_and_audit_without_new_review(monkeypatch,tmp_path):
    from src.workflow.exploration_store import ExplorationStore
    from src.workflow.paper_cache import copy_paper_cache
    state=state_for(tmp_path)
    calls=model(monkeypatch,{'edits':[edit()],'uncertain':[]})
    store=ExplorationStore(tmp_path/'store')
    identity={'pdf':'same','model':'same'}
    settings={'preparation_policy_version':'sample_editorial_v1','code_identity':{}}
    donor,_=store.open_run(identity,settings,seed=1,samples=2)
    target,_=store.open_run(identity,settings,seed=2,samples=2)
    state['output_dir']=str(store.run_path(donor)/'paper_foundation')
    marker='The frst finding is significantly stronger after affixation.'
    text,report=proofread_marker(state,marker,Path(state['output_dir'])/'content')
    state.update(editorial_version='poster_editorial_v1',raw_text=text,marker_raw_text=marker,
                 source_extraction_report=report,images={},tables={},
                 structured_sections={'paper_sections':[{'content':text}]})
    store.save_paper_foundation(donor,state)
    copied=copy_paper_cache(store,donor,target,identity,settings)
    assert copied['raw_text']==text and copied['marker_raw_text']==marker
    assert copied['source_extraction_report']==report and len(calls)==1
    # The copied audit embeds edits/evidence and has no dependency on the donor's
    # private model response files. No old sample content is imported.
    assert validate_report(copied['source_extraction_report'],marker,file_hash(state['pdf_path']))==text
    assert 'editorial_candidate' not in copied
