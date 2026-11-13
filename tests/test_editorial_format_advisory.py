"""Format defects remain visible through bounded repairs, replay and delivery."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_authoring import written_candidate, writer_schema
from src.workflow.editorial_body_format import writer_issues, capacity_issues, report
from src.workflow.editorial_contract import EditorialOutputError
from src.workflow.editorial_requests import request
from test_editorial_generation import state_for, draft_for, plan_for, prose_for, capacity_reply, install
from test_editorial_field_repair import model


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected live model'))


def numbered(state):
    raw = draft_for(state)
    raw['modules'][0].update(presentation_style='steps', entries=[
        {'item_id': 'first', 'text': '1) Measure 92% precision with 2% recall.'},
        {'item_id': 'last', 'text': '3) Evaluate 196 comments under the same conditions.'}])
    return raw


def writer_request(state, raw, **kwargs):
    plan = plan_for(raw)
    zones = pipeline.LayoutFamilyRegistry().get(state['sample_family']['family']).zones
    return request(state, 'editorial_writer', {}, writer_schema(plan, pipeline.ENTRY),
        directory='editorial/writer', validator=lambda value: written_candidate(value, plan, state, zones),
        format_diagnostics=lambda value: writer_issues(value, plan), **kwargs)


def admission(state, directory='editorial/writer'):
    root = Path(state['sample_preparation_dir'])/directory
    return json.loads((root/'format_admission.json').read_text())['payload']


@pytest.mark.parametrize('replacement', [
    '3) Evaluate 196 comments under the same conditions.',
    '1) 1. Evaluate 196 comments under the same conditions.',
])
def test_failed_numbering_repair_is_accepted_recorded_and_replayed(monkeypatch, tmp_path, replacement):
    state = state_for(tmp_path); raw = numbered(state); value = prose_for(raw)
    calls = model(monkeypatch, [value, {'repairs': {'field_0': replacement}}])
    result = writer_request(state, raw)
    assert result['modules']['module_0']['entries'][1]['text'] == replacement
    assert result['modules']['module_0']['entries'][0] == value['modules']['module_0']['entries'][0]
    saved = admission(state)
    assert saved['status'] == 'format_defects' and saved['generation_blocking'] is False
    assert saved['completion_reason'] == 'repair_limit_reached' and saved['correction_attempted']
    assert saved['issues'][0]['module_id'] == 'module_0' and saved['issues'][0]['item_id'] == 'last'
    assert writer_request(state, raw) == result and len(calls) == 2
    assert not state['errors']


@pytest.mark.parametrize('repair', [
    {'repairs': {'field_0': ''}},
    {'repairs': {'field_0': 42}},
    {'repairs': {'field_0': '2) Correct.'}, 'reason': 'Unrequested change'},
])
def test_unusable_optional_repair_retains_valid_original(monkeypatch, tmp_path, repair):
    state = state_for(tmp_path); raw = numbered(state); value = prose_for(raw)
    calls = model(monkeypatch, [value, repair])
    assert writer_request(state, raw) == value
    saved = admission(state)
    assert saved['completion_reason'] == 'invalid_repair_kept_original' and saved['fallback_reason']
    assert saved['issues'] and not saved['generation_blocking']
    assert writer_request(state, raw) == value and len(calls) == 2


def test_unparseable_optional_repair_retains_original_and_journals_reason(monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    state = state_for(tmp_path); raw = numbered(state); value = prose_for(raw)
    calls = model(monkeypatch, [value, {'unparseable': True}])
    parse = language.extract_json
    def broken_second(content):
        if 'unparseable' in content:
            raise ValueError('Synthetic malformed JSON')
        return parse(content)
    monkeypatch.setattr(language, 'extract_json', broken_second)
    assert writer_request(state, raw) == value
    assert 'not parseable JSON' in admission(state)['fallback_reason']
    assert len(calls) == 2


def test_interruption_before_advisory_acceptance_replays_without_request(monkeypatch, tmp_path):
    import src.workflow.editorial_requests as requests
    state = state_for(tmp_path); raw = numbered(state); value = prose_for(raw)
    calls = model(monkeypatch, [value, {'repairs': {
        'field_0': raw['modules'][0]['entries'][1]['text']}}])
    save = requests.save
    def interrupted(path, record):
        if path.name == 'accepted.json':
            raise KeyboardInterrupt()
        return save(path, record)
    monkeypatch.setattr(requests, 'save', interrupted)
    with pytest.raises(KeyboardInterrupt):
        writer_request(state, raw)
    monkeypatch.setattr(requests, 'save', save)
    assert writer_request(state, raw) == value and len(calls) == 2


def test_disabled_format_repair_accepts_without_consuming_shared_allowance(monkeypatch, tmp_path):
    state = state_for(tmp_path); raw = numbered(state); value = prose_for(raw)
    calls = model(monkeypatch, [value])
    assert writer_request(state, raw, correction=False) == value
    assert admission(state)['completion_reason'] == 'correction_disabled'
    assert len(calls) == 1
    assert not (Path(state['sample_preparation_dir'])/'editorial_format_correction.json').exists()


def test_structural_errors_still_fail_after_the_single_repair(monkeypatch, tmp_path):
    state = state_for(tmp_path); raw = numbered(state); value = prose_for(raw)
    value['modules']['module_0']['entries'][1]['item_id'] = ' '
    calls = model(monkeypatch, [value, {'repairs': {'field_0': ' '}}])
    with pytest.raises(EditorialOutputError, match='finite format allowance'):
        writer_request(state, raw)
    assert len(calls) == 2
    assert not (Path(state['sample_preparation_dir'])/'editorial/writer/accepted.json').exists()


def test_structural_repair_can_leave_nonblocking_numbering_defects(monkeypatch, tmp_path):
    state = state_for(tmp_path); raw = numbered(state); value = prose_for(raw)
    value['modules']['module_0']['entries'][1]['item_id'] = ' '
    calls = model(monkeypatch, [value, {'repairs': {'field_0': 'last'}}])
    accepted = writer_request(state, raw)
    assert accepted['modules']['module_0']['entries'] == raw['modules'][0]['entries']
    assert admission(state)['status'] == 'format_defects' and len(calls) == 2


def test_capacity_accepts_unchanged_defects_and_exhausted_repair(monkeypatch, tmp_path):
    state = state_for(tmp_path); raw = numbered(state)
    initial = prose_for(raw)
    replacement = {'repairs': {'field_0': raw['modules'][0]['entries'][1]['text']}}
    changed = deepcopy(raw['modules'][1]); changed.update(presentation_style='topics')
    changed['entries'] = [{'item_id': 'new', 'text': '• • A revised explanation with 3% improvement.'}]
    calls = model(monkeypatch, [initial, replacement, capacity_reply([changed])])
    writer_request(state, raw)
    install(state, raw)
    patch = request(state, 'editorial_balancer', {}, pipeline.PATCH, directory='editorial/capacity',
        validator=lambda p: pipeline.merge_patch(state, p),
        format_diagnostics=lambda p: capacity_issues(p, state['editorial_candidate']))
    candidate = pipeline.merge_patch(state, patch)
    assert candidate['modules'][0] == state['editorial_candidate']['modules'][0]
    assert candidate['modules'][1]['entries'] == changed['entries']
    assert len(report(candidate)['issues']) == 2
    assert admission(state, 'editorial/capacity')['completion_reason'] == 'shared_allowance_exhausted'
    assert len(calls) == 3


def test_format_repair_does_not_grant_a_second_structural_repair(monkeypatch, tmp_path):
    state = state_for(tmp_path); raw = numbered(state)
    changed = deepcopy(raw['modules'][1]); changed['entries'][0]['item_id'] = ' '
    calls = model(monkeypatch, [prose_for(raw), {'repairs': {
        'field_0': raw['modules'][0]['entries'][1]['text']}}, capacity_reply([changed])])
    writer_request(state, raw)
    install(state, raw)
    with pytest.raises(EditorialOutputError, match='Shared editorial format correction exhausted'):
        request(state, 'editorial_balancer', {}, pipeline.PATCH, directory='editorial/capacity',
            validator=lambda p: pipeline.merge_patch(state, p),
            format_diagnostics=lambda p: capacity_issues(p, state['editorial_candidate']))
    assert len(calls) == 3


def test_capacity_edit_uses_optional_repair_and_retains_defect(monkeypatch, tmp_path):
    from src.layout.editorial_layout import measure
    state = install(state_for(tmp_path))
    # Establish frozen composition/emphasis through the normal joint entry.
    pipeline.charge(state, 'curator', 'offline_format_fixture')
    monkeypatch.setattr(pipeline, 'fit', lambda s, c, z: measure(s, c, z))
    changed = deepcopy(state['editorial_candidate']['modules'][0])
    changed['entries'][0]['text'] = '• • 92% precision under fixed conditions.'
    calls = model(monkeypatch, [capacity_reply([changed]),
        {'repairs': {'field_0': '• • 92% precision under fixed conditions.'}}])
    pipeline.editorial_joint_node(state)
    pipeline.editorial_compile_node(state)
    assert state['editorial_format_report']['status'] == 'format_defects'
    assert not state['errors'] and len(calls) == 2
    from src.workflow.editorial_contract import assert_editorial_ready
    assert_editorial_ready(state, compiled=True)
    state['editorial_format_report']['issues'].clear()
    with pytest.raises(ValueError, match='snapshot'):
        assert_editorial_ready(state, compiled=True)
