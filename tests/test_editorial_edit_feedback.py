"""Actual edits and measurements, not promises; finite/replay-safe feedback."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.workflow.editorial_writing import (authored_text_changes, observed_edit,
    capacity_guidance, previous_edit_feedback)
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import EditorialInterrupted
from src.layout.editorial_layout import measure
from src.layout.measurement_context import measurement_scope
from test_editorial_generation import state_for, install
from test_editorial_height_allocation import mixed_state


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))
    with measurement_scope():
        yield


def guidance(words, body, usage, mid='m'):
    return capacity_guidance({'modules': [{'module_id': mid, 'zone_id': 'rail',
        'current_words': words, 'intrinsic_height': body+2, 'allocated_height': 10,
        'utilization': usage, 'overage_inches': max(0, (usage-1)*10),
        'missing_height_inches': max(0, (.9-usage)*10),
        'width_inches': 8, 'measurements': {'text': body}}]})


def event(before=None, after=None):
    return {'phase': 'capacity', 'from': 'a', 'to': 'b',
        'reason': 'Compressed to 79 words and fixed the layout.',
        'observed_edit': {'changed': True, 'authored_text_changes': []},
        'measurements_before': before or guidance(91, 9, 1.1),
        'measurements_after': after or guidance(88, 9, 1.1)}


def test_feedback_exposes_word_reduction_without_height_gain_or_trusting_reason():
    history = [event()]; before = deepcopy(history)
    feedback = previous_edit_feedback(history, {'candidate_id': 'b'})
    row = feedback['model_edit']['module_changes'][0]
    assert row['before']['current_words'] == 91 and row['after']['current_words'] == 88
    assert row['delta']['current_words'] == -3
    assert row['delta']['measured_body_height_inches'] == 0
    assert row['delta']['overage_inches'] == 0
    assert feedback['model_edit']['reason_basis'] == 'unverified_model_statement'
    assert feedback['model_edit']['reported_reason'] == history[0]['reason']
    row['before']['current_words'] = 1
    feedback['model_edit']['observed_edit']['authored_text_changes'].append('changed')
    assert history == before


def test_actual_expansion_overshoot_changes_expand_to_compress():
    feedback = previous_edit_feedback([event(guidance(91, 11.93, .7009),
                                             guidance(193, 20.73, 1.0039))], {'candidate_id': 'b'})
    row = feedback['model_edit']['module_changes'][0]
    assert row['delta']['current_words'] == 102
    assert row['delta']['measured_body_height_inches'] == pytest.approx(8.8)
    assert row['before']['suggested_action'] == 'expand'
    assert row['after']['suggested_action'] == 'compress'
    assert row['delta']['overage_inches'] > 0


def test_exact_text_diff_distinguishes_labels_titles_additions_deletions_and_noop(tmp_path):
    state = install(state_for(tmp_path)); before = state['editorial_candidate']
    after = deepcopy(before); module = after['modules'][0]
    module['title'] = 'Changed title'
    module['entries'][0].update(text='Different text.', display_label='')
    module['entries'].pop()
    module['entries'].append({'item_id':'new','text':'New detail.','display_label':'','parent_item_id':''})
    changes = authored_text_changes(before, after)
    assert any(c['field']=='title' and c['after']=='Changed title' for c in changes)
    assert any(c['field']=='display_label' and c['before']=='Core mechanism' and c['after']=='' for c in changes)
    assert any(c['item_id']=='support' and c['field']=='text' and c['after'] is None for c in changes)
    assert any(c['item_id']=='new' and c['field']=='text' and c['before'] is None for c in changes)
    assert authored_text_changes(before,before)==[]
    assert observed_edit(before,after)['authored_text_changes']==changes
    assert before['modules'][0]['title'] != module['title']


def test_added_removed_modules_and_missing_measurements_are_not_zero_filled():
    e = event(); e['measurements_after']['modules'][0]['module_id']='new'
    f = previous_edit_feedback([e], {'candidate_id':'b'})
    old,new=f['model_edit']['module_changes']
    assert old['after'] is None and new['before'] is None
    assert old['delta']==new['delta']=={}
    minimal=capacity_guidance({'modules':[{'module_id':'m','utilization':1}]})
    f=previous_edit_feedback([event(minimal,minimal)], {'candidate_id':'b'})
    assert 'measured_body_height_inches' not in f['model_edit']['module_changes'][0]['delta']


@pytest.mark.parametrize('condition', ['none','automatic_only','stale','missing_after','broken_chain','other_phase'])
def test_missing_or_unbound_feedback_is_explicitly_unavailable(condition):
    history=[event()]; candidate={'candidate_id':'b'}
    if condition=='none':history=[]
    elif condition=='automatic_only':history[0]['phase']='height_allocation'
    elif condition=='stale':candidate['candidate_id']='stale'
    elif condition=='missing_after':history[0].pop('measurements_after')
    else:
        automatic=deepcopy(history[0]); automatic.update(phase='height_allocation',to='c')
        automatic['from']='wrong' if condition=='broken_chain' else 'b'
        if condition=='other_phase':automatic['phase']='unknown'
        history.append(automatic);candidate['candidate_id']='c'
    f=previous_edit_feedback(history,candidate)
    assert f['status']==('no_previous_capacity_edit' if condition in ('none','automatic_only') else 'unavailable')
    assert 'model_edit' not in f


def test_only_last_capacity_edit_is_sent_and_automatic_transfer_stays_separate():
    earlier=event(); earlier['reason']='An older unrelated promise'
    latest=event();latest.update(**{'from':'b','to':'c'})
    automatic=deepcopy(latest);automatic.update(phase='height_allocation',**{'from':'c','to':'d'})
    automatic['measurements_before']=deepcopy(latest['measurements_after'])
    automatic['measurements_after']=guidance(88,9,.98)
    f=previous_edit_feedback([earlier,latest,automatic],{'candidate_id':'d'})
    assert f['capacity_edit_number']==2 and f['status']=='available'
    assert f['model_edit']['from_candidate_id']=='b'
    assert 'older unrelated' not in json.dumps(f)
    assert f['model_edit']['module_changes'][0]['delta']['overage_inches']==0
    assert f['automatic_height_adjustments'][0]['module_changes'][0]['delta']['overage_inches']<0
    assert f['model_edit']['module_changes'][0]['after']==f['automatic_height_adjustments'][0]['module_changes'][0]['before']


def respond(monkeypatch,calls,*,all_changed=False,reset_weight=False):
    import utils.langgraph_utils as language
    class Model:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,message):
            data=json.loads(message.split('\nINPUT:\n',1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
            calls.append(data)
            module=deepcopy(data['whole_poster']['modules'][0])
            module['entries'][0]['text']+=(' Locally.' if reset_weight else ' Additional mechanism.')
            if reset_weight:module['space_weight']=1
            value={'modules':[module] if all_changed or len(calls)==1 else [],
                   'remove_module_ids':[],'module_order':[],'narrative_flow':'',
                   'reason':'Compressed dramatically.'}
            return SimpleNamespace(content=json.dumps(value),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(language,'LangGraphAgent',Model)


def test_real_request_feedback_and_noop_stop_with_unchanged_quota(monkeypatch,tmp_path):
    state=install(state_for(tmp_path));calls=[];respond(monkeypatch,calls)
    monkeypatch.setattr(pipeline,'fit',lambda s,c,z:measure(s,c,z))
    pipeline.editorial_joint_node(state)
    assert len(calls)==2
    assert calls[0]['previous_edit_feedback']['status']=='no_previous_capacity_edit'
    f=calls[1]['previous_edit_feedback']; h=state['editorial_history'][0]
    assert f['status']=='available' and f['current_candidate_id']==h['to']
    assert f['model_edit']['observed_edit']==h['observed_edit']
    assert f['model_edit']['module_changes'][0]['delta']['current_words']==2
    assert f['model_edit']['observed_edit']['authored_text_changes'][0]['after'].endswith('Additional mechanism.')
    assert state['editorial_fit']['completion_reason']=='no_useful_edit'
    assert len(state['editorial_budget']['charges'])==2
    assert pipeline.LIMITS=={'curator':1,'merge':1,'capacity':3}
    assert state['editorial_history'][-1]['observed_edit']['authored_text_changes']==[]


def test_feedback_replay_after_second_response_does_not_buy_calls(monkeypatch,tmp_path):
    state=install(state_for(tmp_path));original=deepcopy(state);calls=[];respond(monkeypatch,calls)
    monkeypatch.setattr(pipeline,'fit',lambda s,c,z:measure(s,c,z))
    actual=pipeline.edit
    def interrupt(*a):
        changed=actual(*a)
        if len(a[0].get('editorial_history',[]))==2:raise EditorialInterrupted()
        return changed
    monkeypatch.setattr(pipeline,'edit',interrupt)
    with pytest.raises(EditorialInterrupted):pipeline.editorial_joint_node(state)
    assert len(calls)==2
    monkeypatch.setattr(pipeline,'edit',actual)
    pipeline.editorial_joint_node(original)
    assert len(calls)==2
    assert original['editorial_history']==state['editorial_history']
    assert len(original['editorial_budget']['charges'])==2
    records=list((Path(original['sample_preparation_dir'])/'editorial/edits').glob('*/identity.json'))
    assert len(records)==2
    assert any('editorial_edit_feedback_v1' in p.read_text() for p in records)


def test_three_changed_edits_still_use_only_original_allowance(monkeypatch,tmp_path):
    state=install(state_for(tmp_path));calls=[];respond(monkeypatch,calls,all_changed=True)
    monkeypatch.setattr(pipeline,'fit',lambda s,c,z:measure(s,c,z))
    pipeline.editorial_joint_node(state)
    assert len(calls)==len(state['editorial_budget']['charges'])==3
    assert [c['previous_edit_feedback'].get('capacity_edit_number') for c in calls]==[None,1,2]
    assert state['editorial_fit']['completion_reason']=='repair_limit_reached'
    assert all('measurements_after' in h for h in state['editorial_history'])


def test_exact_fit_chain_separates_automatic_height_from_capacity_edit(monkeypatch,tmp_path):
    state=mixed_state(tmp_path,initial=True);calls=[];respond(monkeypatch,calls,reset_weight=True)
    pipeline.editorial_joint_node(state)
    assert len(calls)==2
    assert calls[0]['previous_edit_feedback']['status']=='no_previous_capacity_edit'
    f=calls[1]['previous_edit_feedback']
    assert f['status']=='available' and len(f['automatic_height_adjustments'])==1
    a=f['automatic_height_adjustments'][0]
    assert f['model_edit']['to_candidate_id']==a['from_candidate_id']
    assert a['to_candidate_id']==calls[1]['whole_poster']['candidate_id']
    assert a['observed_edit']['authored_text_changes']==[]
    assert f['model_edit']['observed_edit']['authored_text_changes']
