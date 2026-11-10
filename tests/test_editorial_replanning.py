"""Whole-plan correction shares the one merge/geometry allowance and durable calls."""
from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest
from jsonschema import Draft202012Validator

from src.layout.families import LayoutFamilyRegistry
from src.layout.region_merges import merge_candidates
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_authoring import plan_schema
from src.workflow.editorial_contract import EditorialOutputError
from src.workflow.editorial_planning import check_plan, EditorialPlanningError
from test_editorial_field_repair import model
from test_editorial_generation import state_for, draft_for, plan_for, prose_for


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('No network'))


def payload(prompt):
    return json.loads(prompt.split('\nINPUT:\n', 1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:\n', 1)[0])


def journal(state, relative):
    return json.loads((Path(state['sample_preparation_dir'])/'editorial'/relative).read_text())['payload']


def setup(tmp_path):
    state = state_for(tmp_path, 'central_evidence_band')
    state['images'] = {'1': {'aspect': 2}, '2': {'aspect': 2}}
    state['classified_visuals'] = {'key_visual': 'figure_2'}
    good = draft_for(state)
    good['modules'][2]['visual_ids'] = ['figure_2']
    good['core_module_ids'] = ['module_2']
    bad = plan_for(good)
    bad['modules'] = bad['modules'][:1]
    bad['core_module_ids'] = ['absent_method', 'absent_results']
    bad['reason'] = 'Claims a full plan, but the actual array contains background only.'
    return state, bad, good


@pytest.mark.parametrize('family_id', LayoutFamilyRegistry().ids())
def test_joint_diagnosis_uses_each_actual_family_and_preserves_input(tmp_path, family_id):
    state = state_for(tmp_path, family_id)
    family = LayoutFamilyRegistry().get(family_id)
    # Include every supported merged topology, not just base family names.
    for zones in [family.zones, *[v[1] for v in merge_candidates(family, family.zones)]]:
        schema = plan_schema(pipeline.curator_schema(zones, []))
        raw = plan_for(draft_for(state))
        raw['modules'] = raw['modules'][:len(zones)]
        for m, z in zip(raw['modules'], zones):
            m['zone_id'] = z['zone_id']
        assert check_plan(raw, state, zones, schema, allow_underfull=False) is None
        raw['modules'][-1]['zone_id'] = 'not_a_region'
        raw['core_module_ids'] = ['missing']
        original = deepcopy((raw, schema, zones))
        with pytest.raises(EditorialPlanningError) as error:
            check_plan(raw, state, zones, schema, allow_underfull=False)
        feedback = error.value.feedback
        assert {'unknown_regions', 'empty_region', 'invalid_core_references'} <= {i['code'] for i in feedback['issues']}
        assert [(r['zone_id'], r['capacity']) for r in feedback['region_occupancy']] == [(z['zone_id'], z['capacity']) for z in zones]
        assert (raw, schema, zones) == original


def test_incomplete_plan_reorganized_as_full_plan_then_frozen_and_replayed(monkeypatch, tmp_path):
    state, bad, good = setup(tmp_path)
    original = deepcopy(state)
    good['modules'][0]['title'] = 'Reorganized question'
    good['modules'][1]['entries'][0]['text'] = 'A changed outline supported by the offline fixture.'
    good['modules'][1]['visual_ids'] = ['figure_1']
    good['narrative_flow'] = 'Question, mechanism, evidence and scope.'
    calls = model(monkeypatch, [bad, plan_for(good), prose_for(good)])
    pipeline.editorial_curator_node(state)
    pipeline.editorial_curator_node(original)
    assert len(calls) == 3
    first, adjusted = payload(calls[0]), payload(calls[1])
    assert adjusted['phase'] == 'merge' and adjusted['previous_draft'] == bad
    assert adjusted['family'] == first['family'] and adjusted['paper'] == first['paper']
    assert 'geometry_feedback' not in adjusted
    assert {'invalid_core_references', 'missing_key_visual'} <= {i['code'] for i in adjusted['planning_feedback']['issues']}
    assert state['editorial_plan'] == plan_for(good)
    assert original['editorial_candidate'] == state['editorial_candidate']
    assert state['editorial_visual_selection']['owners'] == {'module_1': ['figure_1'], 'module_2': ['figure_2']}
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge', 'writer']
    root = Path(state['sample_preparation_dir'])
    assert not (root/'editorial_format_correction.json').exists()
    assert not (root/'editorial/curator/accepted.json').exists()
    assert journal(state, 'curator/planning_rejection_00.json')['draft'] == bad
    changes = journal(state, 'merge/adjustment.json')['observed_changes']
    assert len(changes['added_module_ids']) == 5
    assert 'title' in changes['changed_module_fields']['module_0']
    assert changes['scientific_coverage_verified'] is False


@pytest.mark.parametrize('fault', ['core', 'key', 'allocation', 'empty', 'too_many', 'no_core_content'])
def test_invalid_adjustment_stops_without_another_planning_or_format_call(monkeypatch, tmp_path, fault):
    state, bad, good = setup(tmp_path)
    wrong = plan_for(good)
    if fault == 'core': wrong['core_module_ids'] = ['missing']
    elif fault == 'key': wrong['modules'][2]['visual_ids'] = []
    elif fault == 'allocation': wrong['modules'][-1]['zone_id'] = wrong['modules'][0]['zone_id']
    elif fault == 'empty': wrong['modules'] = []
    elif fault == 'too_many': wrong['modules'].append(deepcopy(wrong['modules'][0]))
    else:
        for point in wrong['modules'][0]['content_outline']: point['priority'] = 'optional'
    calls = model(monkeypatch, [bad, wrong])
    for _ in range(2):
        with pytest.raises(EditorialPlanningError):
            pipeline.editorial_curator_node(state)
    assert len(calls) == 2
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge']
    assert journal(state, 'merge/planning_rejection_00.json')['draft'] == wrong
    root = Path(state['sample_preparation_dir'])
    assert not (root/'editorial/writer').exists()
    assert not (root/'editorial_format_correction.json').exists()
    assert 'editorial_visual_selection' not in state


def test_planning_correction_uses_up_geometry_adjustment(monkeypatch, tmp_path):
    state, bad, good = setup(tmp_path)
    good['modules'][0]['title'] = 'A\n' * 60
    calls = model(monkeypatch, [bad, plan_for(good)])
    with pytest.raises(EditorialOutputError, match='infeasible after one adjustment'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2
    assert journal(state, 'failed_geometry.json')['failures']
    assert not (Path(state['sample_preparation_dir'])/'editorial/writer').exists()


@pytest.mark.parametrize('trigger', ['geometry', 'legal_merge'])
def test_other_adjustment_cannot_buy_followup_for_invalid_plan(monkeypatch, tmp_path, trigger):
    state = state_for(tmp_path, 'small_multiples_matrix')
    initial = draft_for(state)
    if trigger == 'geometry': initial['modules'][0]['title'] = 'A\n' * 60
    else: initial['modules'] = initial['modules'][:4]
    invalid = plan_for(initial); invalid['core_module_ids'] = ['missing']
    calls = model(monkeypatch, [plan_for(initial), invalid])
    with pytest.raises(EditorialPlanningError):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge']


def test_invalid_plan_after_spent_field_repair_can_still_use_planning_allowance(monkeypatch, tmp_path):
    state, bad, good = setup(tmp_path)
    malformed = deepcopy(bad); malformed['core_module_ids'] = None
    calls = model(monkeypatch, [malformed, {'repairs': {'field_0': bad['core_module_ids']}},
                               plan_for(good), prose_for(good)])
    pipeline.editorial_curator_node(state)
    assert len(calls) == 4
    assert journal(state, 'curator/planning_rejection_01.json')['draft'] == bad
    assert (Path(state['sample_preparation_dir'])/'editorial_format_correction.json').exists()
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator', 'merge', 'writer']


def test_visual_field_repair_dropping_key_gets_full_replan_not_another_field_repair(monkeypatch, tmp_path):
    from test_curator_visual_repair import visual_draft
    state, raw = visual_draft(tmp_path)
    good = deepcopy(raw); good['modules'][2]['visual_ids'] = []
    calls = model(monkeypatch, [plan_for(raw), {'repairs': {'field_0': [], 'field_1': []}},
                               plan_for(good), prose_for(good)])
    pipeline.editorial_curator_node(state)
    assert len(calls) == 4
    assert payload(calls[2])['planning_feedback']['issues'][0]['code'] == 'missing_key_visual'
    assert state['editorial_visual_selection']['owners']['module_1'] == ['figure_2']


def test_replanned_writer_can_spend_unused_shared_field_repair(monkeypatch, tmp_path):
    state, bad, good = setup(tmp_path)
    prose = prose_for(good)
    prose['modules']['module_0']['entries'][1]['parent_item_id'] = 'absent'
    calls = model(monkeypatch, [bad, plan_for(good), prose, {'repairs': {'field_0': 'main'}}])
    pipeline.editorial_curator_node(state)
    assert len(calls) == 4
    assert journal(state, 'writer/repair_plan.json')['plan']['targets'][0]['path'][-1] == 'parent_item_id'


@pytest.mark.parametrize('exception', [TimeoutError('transport'), KeyboardInterrupt()])
def test_charged_adjustment_without_reply_is_never_resubmitted(monkeypatch, tmp_path, exception):
    state, bad, good = setup(tmp_path)
    calls = model(monkeypatch, [bad, exception])
    with pytest.raises(type(exception)):
        pipeline.editorial_curator_node(state)
    with pytest.raises(ValueError, match='response missing'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 2


def test_returned_adjustment_recovers_after_interruption_before_acceptance(monkeypatch, tmp_path):
    import src.workflow.editorial_requests as requests
    state, bad, good = setup(tmp_path)
    original = deepcopy(state)
    calls = model(monkeypatch, [bad, plan_for(good), prose_for(good)])
    save = requests.save
    def stop(path, value):
        if path.parent.name == 'merge' and path.name == 'accepted.json': raise KeyboardInterrupt()
        save(path, value)
    monkeypatch.setattr(requests, 'save', stop)
    with pytest.raises(KeyboardInterrupt): pipeline.editorial_curator_node(state)
    monkeypatch.setattr(requests, 'save', save)
    pipeline.editorial_curator_node(original)
    assert len(calls) == 3
    assert original['editorial_plan'] == plan_for(good)


@pytest.mark.parametrize('damage', ['alter_rejection', 'alter_adjustment', 'missing_merge_request'])
def test_durable_replanning_cannot_bypass_corrupted_history(monkeypatch, tmp_path, damage):
    state, bad, good = setup(tmp_path)
    original = deepcopy(state)
    calls = model(monkeypatch, [bad, plan_for(good), prose_for(good)])
    pipeline.editorial_curator_node(state)
    relative = {'alter_rejection': 'curator/planning_rejection_00.json',
                'alter_adjustment': 'merge/adjustment.json', 'missing_merge_request': 'merge/request_00.json'}[damage]
    path = Path(state['sample_preparation_dir'])/'editorial'/relative
    if damage.startswith('alter'):
        record = json.loads(path.read_text()); record['payload']['tampered'] = True
        path.write_text(json.dumps(record))
    else: path.unlink()
    with pytest.raises(ValueError): pipeline.editorial_curator_node(original)
    assert len(calls) == 3


def test_bad_upstream_key_is_not_replanned(monkeypatch, tmp_path):
    state, bad, good = setup(tmp_path)
    state['classified_visuals']['key_visual'] = 'not_an_asset'
    calls = model(monkeypatch, [plan_for(good)])
    with pytest.raises(ValueError, match='actual paper asset'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 1
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator']


@pytest.mark.parametrize('error', [EditorialOutputError('unrelated failure'), RuntimeError('backend bug')])
def test_unrelated_validation_errors_do_not_purchase_replanning(monkeypatch, tmp_path, error):
    import src.workflow.editorial_authoring as authoring
    state, bad, good = setup(tmp_path)
    calls = model(monkeypatch, [plan_for(good)])
    def reject(*args, **kwargs): raise error
    monkeypatch.setattr(authoring, 'normalize_plan', reject)
    with pytest.raises(type(error), match=str(error)):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 1
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['curator']


def test_exhausted_planning_ledger_prevents_any_second_adjustment(monkeypatch, tmp_path):
    state, bad, good = setup(tmp_path)
    pipeline.charge(state, 'merge', 'previously_spent')
    calls = model(monkeypatch, [bad])
    with pytest.raises(EditorialOutputError, match='merge allowance exhausted'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 1
    assert [c['phase'] for c in state['editorial_budget']['charges']] == ['merge', 'curator']


def test_malformed_fields_do_not_open_an_unbounded_whole_plan_format_patch(monkeypatch, tmp_path):
    state, bad, good = setup(tmp_path)
    malformed = plan_for(good)
    malformed['modules'].append(deepcopy(malformed['modules'][0]))
    malformed['modules'][0]['title'] = None
    calls = model(monkeypatch, [malformed])
    with pytest.raises(EditorialOutputError, match='module count must be'):
        pipeline.editorial_curator_node(state)
    assert len(calls) == 1
    assert not (Path(state['sample_preparation_dir'])/'editorial_format_correction.json').exists()


def test_genuine_deficit_is_not_fabricated_into_a_planning_error(tmp_path):
    state = state_for(tmp_path, 'small_multiples_matrix')
    zones = LayoutFamilyRegistry().get('small_multiples_matrix').zones
    schema = plan_schema(pipeline.curator_schema(zones, []))
    raw = plan_for(draft_for(state)); raw['modules'] = raw['modules'][:4]
    assert check_plan(raw, state, zones, schema, allow_underfull=True) is None
    # In the adjustment, underfull is no longer a way to buy a second merge.
    with pytest.raises(EditorialPlanningError): check_plan(raw, state, zones, schema, allow_underfull=False)
    assert Draft202012Validator(schema).is_valid(raw)
