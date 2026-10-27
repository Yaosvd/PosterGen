"""Renderer metadata and bounded field-only recovery, without remote models."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from test_source_editorial import source_state, Agent, no_remote_models
from test_source_editorial_integration import NoopBalancer, fake_fit, fake_preview
from src.workflow import source_editorial as editorial
from src.workflow import source_preparation as preparation
from src.workflow.source_document import SourceProtocolError, paragraph_hints
from src.workflow.source_requests import SourceRequests, object_schema, BOOL
from src.layout.repair_budget import sample_ledger
from utils.persistence import read_json


def wire(state):
    return paragraph_hints({'modules': state['source_candidate']['modules']}, state['source_document'])


def topics_pair(state):
    good = wire(state)
    good['modules'][0]['presentation_style'] = 'topics'
    good['modules'][0]['entries'][0]['display_label'] = 'common representation'
    bad = deepcopy(good)
    bad['modules'][0]['entries'][0]['display_label'] = 'Core Contribution'
    return bad, good


def curator(state, monkeypatch, *responses):
    agent = Agent(*(json.dumps(v) for v in responses))
    monkeypatch.setattr(editorial, 'agent_for', lambda *a, **kw: agent)
    editorial.source_curator_node(state)
    return agent


def test_saved_failure_shape_normalizes_cues_without_prose_edits_or_extra_calls(tmp_path, monkeypatch):
    state = source_state(tmp_path, count=5)
    value = wire(state)
    method = value['modules'][1]
    method['presentation_style'] = 'steps'
    for i in range(2):
        entry = deepcopy(method['entries'][0]); entry['item_id'] = f'step_{i}'
        method['entries'].append(entry)
    for m in value['modules']:
        for i, e in enumerate(m['entries']):
            e['display_label'] = f'{i+1}. Independent heading'
            e['step_index'] = i
    original = deepcopy(value)
    agent = curator(state, monkeypatch, value)
    assert len(agent.calls) == 1 and value == original
    after = state['source_candidate']['modules']
    assert [e['step_index'] for e in after[1]['entries']] == [1, 2, 3]
    for before, m in zip(original['modules'], after):
        for old, new in zip(before['entries'], m['entries']):
            assert new['text'] == old['text'] and new['item_id'] == old['item_id']
            assert new['display_label'] == ''
    root = Path(state['sample_preparation_dir'])
    assert not (root/'source_format_correction.json').exists()
    assert read_json(root/'source/curator/normalization.json')['changes']
    assert not state['verification_passed']
    changes = []
    assert editorial.normalize_candidate({'modules': after}, state, normalizations=changes) == state['source_candidate']
    assert not changes  # normalization is idempotent


@pytest.mark.parametrize('indexes', [[0, 1, 2], [1, 2, 3], [8, 8, 2]])
def test_step_ordinals_never_reorder_entries_or_certify_chronology(tmp_path, indexes):
    state = source_state(tmp_path, count=1)
    raw = {'modules': deepcopy(state['source_candidate']['modules'])}
    m = raw['modules'][0]; m['presentation_style'] = 'steps'
    m['entries'] = [{**deepcopy(m['entries'][0]), 'item_id': f'idea_{i}', 'step_index': n}
                    for i, n in enumerate(indexes)]
    normalized = editorial.normalize_candidate(raw, state)
    assert [e['item_id'] for e in normalized['modules'][0]['entries']] == ['idea_0','idea_1','idea_2']
    assert [e['step_index'] for e in normalized['modules'][0]['entries']] == [1,2,3]
    assert not state['verification_passed']


@pytest.mark.parametrize('label', ['Core Contribution', 'Common Representation',
    'A shared policy', 'level-2 learns a common representation across agents'])
def test_all_invalid_topics_labels_use_one_shared_repair(tmp_path, monkeypatch, label):
    state = source_state(tmp_path, count=2)
    bad, good = topics_pair(state)
    bad['modules'][0]['entries'][0]['display_label'] = label
    bad['modules'][0]['entries'].append({**deepcopy(bad['modules'][0]['entries'][0]), 'item_id':'other'})
    good['modules'][0]['entries'].append({**deepcopy(good['modules'][0]['entries'][0]), 'item_id':'other'})
    agent = curator(state, monkeypatch, bad, good)
    assert len(agent.calls) == 2
    root = Path(state['sample_preparation_dir'])
    errors = read_json(root/'source/curator/validation_00.json')['payload']['error']
    assert "'entries', 0" in errors and "'entries', 1" in errors
    assert read_json(root/'source/curator/verdict.json')['payload']['response_index'] == 1
    editorial.source_curator_node(state)
    assert len(agent.calls) == 2  # exact replay does not rebill or resubmit
    next_agent = Agent('{"supported":"invalid"}')
    with pytest.raises(SourceProtocolError, match='exhausted'):
        SourceRequests(state,'source/later','later',object_schema({'supported':BOOL})).call(next_agent)
    assert len(next_agent.calls) == 1


@pytest.mark.parametrize('damage', ['same_module_prose','neighbor','references','title','order','parent'])
def test_label_repair_cannot_change_any_other_field(tmp_path, monkeypatch, damage):
    state = source_state(tmp_path, count=2)
    bad, changed = topics_pair(state)
    m = changed['modules'][0]
    if damage == 'same_module_prose': m['entries'][0]['text'] += ' An extra explanation.'
    elif damage == 'neighbor': changed['modules'][1]['communication_goal'] = 'Changed goal'
    elif damage == 'references':
        m['entries'][0]['source_refs'][0]['paragraph_ids'] = [state['source_document']['units'][0]['paragraphs'][0]['paragraph_id']]
    elif damage == 'title': m['title'] = 'Another title'
    elif damage == 'order': changed['modules'].reverse()
    elif damage == 'parent': m['entries'][0]['kind'] = 'interpretation'
    agent = Agent(json.dumps(bad), json.dumps(changed))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    with pytest.raises(SourceProtocolError, match='no remaining'):
        editorial.source_curator_node(state)
    assert len(agent.calls) == 2
    assert not state['verification_passed']


def test_second_bad_label_response_exhausts_recovery(tmp_path, monkeypatch):
    state = source_state(tmp_path); bad, _ = topics_pair(state)
    agent = Agent(json.dumps(bad), json.dumps(bad))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    with pytest.raises(SourceProtocolError, match='no remaining'):
        editorial.source_curator_node(state)
    assert len(agent.calls) == 2


def test_balancer_uses_same_label_recovery_inside_one_edit_charge(tmp_path, monkeypatch):
    state = source_state(tmp_path, count=3)
    monkeypatch.setattr(preparation, 'draft_preview', fake_preview)
    class Balancer(NoopBalancer):
        def step(self, message):
            response = super().step(message)
            value = json.loads(response.content)
            m = value['candidate']['modules'][0]
            m['presentation_style'] = 'topics'
            m['entries'][0]['display_label'] = 'Core Contribution' if len(self.calls) == 1 else 'common representation'
            value['lineage'] = [{'new_module_id': m['module_id'], 'old_module_ids': [m['module_id']]}]
            value['reason'] = 'Add a navigation cue to the existing mechanism.'
            response.content = json.dumps(value)
            return response
    agent = Balancer(); monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    before = deepcopy(state['source_candidate'])
    state, changed = preparation.edit_candidate(state, {}, 'quality', fake_fit(state,draft=True)[0])
    assert changed and len(agent.calls) == 2
    assert len(sample_ledger(state)[1]['charges']) == 1
    assert state['source_candidate']['modules'][1:] == before['modules'][1:]
    assert not state['verification_passed']
    assert state['source_reading_review']['applies_to_reviewed_draft_candidate'] is False
    assert list(Path(state['sample_preparation_dir']).glob('source/edits/*/validation_00.json'))


def test_metadata_normalization_does_not_add_a_round_or_create_false_edit(tmp_path, monkeypatch):
    state = source_state(tmp_path, count=3)
    monkeypatch.setattr(preparation, 'draft_preview', fake_preview)
    class Balancer(NoopBalancer):
        def step(self, message):
            response = super().step(message); value = json.loads(response.content)
            for m in value['candidate']['modules']:
                m['entries'][0].update(display_label='Unused heading',step_index=99)
            response.content = json.dumps(value); return response
    agent = Balancer(); monkeypatch.setattr(preparation,'agent_for',lambda *a,**kw:agent)
    before = deepcopy(state['source_candidate'])
    state, changed = preparation.edit_candidate(state, {}, 'quality', fake_fit(state,draft=True)[0])
    assert not changed and state['source_candidate'] == before and len(agent.calls) == 1
    assert len(sample_ledger(state)[1]['charges']) == 1  # the no-op review still costs its opportunity
    audit = read_json(next(Path(state['sample_preparation_dir']).glob('source/edits/*/normalized.json')))['payload']
    assert len(audit['presentation_normalizations']) == 6
