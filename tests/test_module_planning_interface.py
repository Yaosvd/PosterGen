"""Real-node contract, diagnostic persistence and correction restart boundaries."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agents.sample_module_planner import sample_module_planner_node
from src.workflow.module_planning_requests import ModulePlanningRequests
from src.workflow.sample_modules import ModulePlanValidationError, normalize_module_plan
from utils.persistence import read_json
from test_sample_module_body import module_state, raw_plan


def history(state):
    return Path(state['output_dir'])/'content/module_planning'


def fake_agent(monkeypatch, answers):
    import src.agents.sample_module_planner as node
    calls = []
    answers = iter(answers)
    class Agent:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, prompt):
            calls.append(prompt)
            answer = next(answers)
            if callable(answer): answer = answer()
            if isinstance(answer, BaseException): raise answer
            return SimpleNamespace(content=answer if isinstance(answer, str) else json.dumps(answer),
                                   input_tokens=3, output_tokens=4)
    monkeypatch.setattr(node, 'LangGraphAgent', Agent)
    monkeypatch.setattr(node, 'apply_agent_policy', lambda model, _: model)
    return calls


@pytest.mark.parametrize('origins', [[], ['u1'], ['u2'], 'omitted'])
def test_unique_origins_are_completed_without_changing_evidence_or_modules(tmp_path, origins):
    state = module_state(tmp_path); original = deepcopy(state); raw = raw_plan()
    if origins == 'omitted': del raw['modules'][0]['source_plan_unit_ids']
    else: raw['modules'][0]['source_plan_unit_ids'] = origins
    result = normalize_module_plan(raw, state)
    module = result['modules'][0]
    assert set(module['source_plan_unit_ids']) == {'u1', 'u2'}
    assert module['evidence_ids'] == ['e1', 'e2']
    assert module['writing_brief'] == raw['modules'][0]['writing_brief']
    assert module['required_evidence_ids'] == ['e1', 'e2']
    assert result['source_normalizations'][0]['code'] == 'unique_evidence_origin_completed'
    assert state == original


@pytest.mark.parametrize('origins', [[], ['u1'], ['u1', 'u2']])
def test_shared_evidence_needs_an_explicit_original_owner(tmp_path, origins):
    state = module_state(tmp_path)
    for unit in state['narrative_plan']['sections']:
        unit['evidence_ids'] = ['e1']; unit['required_evidence_ids'] = ['e1']
    raw = raw_plan();raw['modules'][0].update(evidence_ids=['e1'], source_plan_unit_ids=origins)
    if not origins:
        with pytest.raises(ModulePlanValidationError) as error: normalize_module_plan(raw, state)
        issue = error.value.issues[0]
        assert issue['code'] == 'ambiguous_evidence_origin' and issue['ids'] == ['e1']
        assert issue['candidate_source_plan_unit_ids'] == ['u1', 'u2']
    else:
        module = normalize_module_plan(raw, state)['modules'][0]
        assert module['source_plan_unit_ids'] == origins


@pytest.mark.parametrize('field,value,code', [
    ('evidence_ids', [], 'empty_evidence_ids'),
    ('evidence_ids', 'e1', 'invalid_evidence_ids_format'),
    ('evidence_ids', [['e1']], 'invalid_evidence_ids_format'),
    ('evidence_ids', [1], 'invalid_evidence_ids_format'),
    ('evidence_ids', ['missing'], 'unknown_evidence_ids'),
    ('evidence_ids', ['e3'], 'unplanned_evidence_ids'),
    ('source_plan_unit_ids', ['missing'], 'unknown_source_plan_unit_ids'),
    ('source_plan_unit_ids', 'u1', 'invalid_source_plan_unit_ids_format'),
    ('source_plan_unit_ids', None, 'invalid_source_plan_unit_ids_format'),
    ('source_plan_unit_ids', [['u1']], 'invalid_source_plan_unit_ids_format'),
    ('visual_ids', ['missing'], 'unknown_visual_ids'),
    ('visual_ids', [['figure_1']], 'invalid_visual_ids_format'),
    ('visual_ids', ['figure_1', 'figure_1'], 'duplicate_visual_ids'),
    ('title', None, 'missing_module_title'),
    ('writing_brief', '', 'missing_writing_brief'),
])
def test_invalid_fields_have_specific_module_diagnostics(tmp_path, field, value, code):
    state = module_state(tmp_path);state['images'] = {'1': {}}
    state['evidence_bank']['items'].append({'evidence_id': 'e3'})
    raw = raw_plan();raw['modules'][0][field] = value
    with pytest.raises(ModulePlanValidationError) as error: normalize_module_plan(raw, state)
    issue = next(i for i in error.value.issues if i['code'] == code)
    assert issue['module_index'] == 1
    if field != 'title': assert issue['module_title'] == 'Neural Modeling'


def test_unrelated_valid_origins_are_rejected_instead_of_attaching_every_unit(tmp_path):
    state = module_state(tmp_path)
    state['narrative_plan']['sections'].append({'section_id': 'u3', 'evidence_ids': ['e3']})
    state['evidence_bank']['items'].append({'evidence_id': 'e3'})
    raw = raw_plan();raw['modules'][0]['source_plan_unit_ids'].append('u3')
    with pytest.raises(ModulePlanValidationError) as error: normalize_module_plan(raw, state)
    assert error.value.issues[0]['code'] == 'unrelated_source_plan_unit_ids'
    assert error.value.issues[0]['ids'] == ['u3']


@pytest.mark.parametrize('raw,code', [([], 'invalid_modules_format'), ({}, 'invalid_modules_format'),
    ({'modules': {}}, 'invalid_modules_format'), ({'modules': []}, 'empty_modules'),
    ({'modules': [None]}, 'invalid_module_format')])
def test_bad_top_level_structure_is_a_diagnosed_model_error(tmp_path, raw, code):
    with pytest.raises(ModulePlanValidationError) as error: normalize_module_plan(raw, module_state(tmp_path))
    assert error.value.issues[0]['code'] == code


def test_missing_necessary_evidence_is_not_silently_removed(tmp_path):
    state = module_state(tmp_path);raw = raw_plan()
    raw['modules'][0].update(source_plan_unit_ids=['u1'], evidence_ids=['e1'])
    with pytest.raises(ModulePlanValidationError) as error: normalize_module_plan(raw, state)
    assert {'code': 'missing_indispensable_evidence', 'ids': ['e2']} in error.value.issues


def test_initial_raw_and_parsed_output_survive_failure_before_any_correction(monkeypatch, tmp_path):
    import src.agents.sample_module_planner as node
    state = module_state(tmp_path);bad = raw_plan();bad['modules'][0]['evidence_ids'] = ['unknown']
    def stop_after_first():
        root = history(state)
        assert read_json(root/'response_00.json')['payload']['content'] == json.dumps(bad)
        assert read_json(root/'parsed_00.json')['payload']['parsed'] == bad
        issue = read_json(root/'validation_00.json')['payload']['issues'][0]
        assert issue['code'] == 'unknown_evidence_ids' and issue['ids'] == ['unknown']
        assert (root/'request_01.json').exists()
        raise KeyboardInterrupt()
    calls = fake_agent(monkeypatch, [bad, stop_after_first])
    with pytest.raises(KeyboardInterrupt): node.sample_module_planner_node(state)
    assert len(calls) == 2
    # Charge survives interruption: retry reads the initial response but cannot resubmit correction.
    state['errors'] = []
    node.sample_module_planner_node(state)
    assert len(calls) == 2 and 'refusing automatic resubmission' in state['errors'][0]
    assert read_json(history(state)/'request_failure_01.json')['payload']['error_type'] == 'KeyboardInterrupt'


def test_bad_plan_gets_exactly_one_correction_and_keeps_both_responses(monkeypatch, tmp_path):
    state = module_state(tmp_path);bad = raw_plan();bad['modules'][0]['evidence_ids'] = []
    calls = fake_agent(monkeypatch, [bad, raw_plan()])
    sample_module_planner_node(state)
    assert not state['errors'] and len(calls) == 2
    root = history(state)
    assert 'empty_evidence_ids' in calls[1] and 'only correction' in calls[1]
    assert read_json(root/'parsed_00.json')['payload']['parsed'] == bad
    assert read_json(root/'parsed_01.json')['payload']['parsed'] == raw_plan()
    assert read_json(root/'result.json')['payload']['status'] == 'accepted'
    assert state['sample_module_plan']['planning_diagnostics']['correction_used']
    assert not (root/'request_02.json').exists()
    # A stage checkpoint interruption can replay the saved responses without model work.
    saved = deepcopy(state['sample_module_plan']);state['sample_module_plan'] = None
    sample_module_planner_node(state)
    assert len(calls) == 2 and state['sample_module_plan'] == saved


def test_two_invalid_responses_stop_without_fallback_or_third_call(monkeypatch, tmp_path):
    state = module_state(tmp_path);bad = raw_plan();bad['modules'][0]['evidence_ids'] = ['unknown']
    calls = fake_agent(monkeypatch, [bad, bad])
    sample_module_planner_node(state)
    assert len(calls) == 2 and state['errors'] and not state.get('sample_module_plan')
    assert read_json(history(state)/'validation_01.json')['payload']['status'] == 'rejected'
    assert 'unknown_evidence_ids' in state['errors'][0]
    state['errors'] = []
    sample_module_planner_node(state)
    assert len(calls) == 2 and state['errors']


def test_unique_origin_omission_needs_no_correction_call(monkeypatch, tmp_path):
    state = module_state(tmp_path);raw = raw_plan();del raw['modules'][0]['source_plan_unit_ids']
    calls = fake_agent(monkeypatch, [raw])
    sample_module_planner_node(state)
    assert len(calls) == 1 and not state['errors']
    assert state['sample_module_plan']['source_normalizations']
    assert not (history(state)/'request_01.json').exists()
    assert '"source_plan_unit_ids": ["u1"]' in calls[0]


def test_request_failure_is_not_recast_as_a_content_correction(monkeypatch, tmp_path):
    state = module_state(tmp_path);calls = fake_agent(monkeypatch, [TimeoutError('test')])
    sample_module_planner_node(state)
    assert len(calls) == 1 and state['errors']
    assert not (history(state)/'request_01.json').exists()
    state['errors'] = []
    sample_module_planner_node(state)
    assert len(calls) == 1 and 'refusing automatic resubmission' in state['errors'][0]


@pytest.mark.parametrize('change', ['sample', 'seed', 'paper', 'response', 'charge', 'identity'])
def test_planning_history_is_bound_to_sample_inputs_and_digests(monkeypatch, tmp_path, change):
    state = module_state(tmp_path)
    state['iteration_context'] = {'run_id': 'run_a', 'sample_id': 'sample_a', 'random_seed': 31}
    calls = fake_agent(monkeypatch, [raw_plan()]);sample_module_planner_node(state)
    if change == 'sample': state['iteration_context']['sample_id'] = 'sample_b'
    elif change == 'seed': state['iteration_context']['random_seed'] = 32
    elif change == 'paper': state['paper_foundation_digest'] = 'other'
    else:
        name = {'response':'response_00.json', 'charge':'request_00.json', 'identity':'identity.json'}[change]
        path = history(state)/name;data = read_json(path)
        if change == 'identity': data['input_digest'] = 'tampered'
        else: data['payload']['input_digest'] = 'tampered'
        path.write_text(json.dumps(data))
    state['sample_module_plan'] = None
    sample_module_planner_node(state)
    assert len(calls) == 1 and state['errors'] and not state.get('sample_module_plan')


def test_request_slot_bound_prevents_accidental_extra_rounds(tmp_path):
    ledger = ModulePlanningRequests(module_state(tmp_path), 'prompt')
    with pytest.raises(ValueError, match='one correction'): ledger.request(2, None, 'prompt')


@pytest.mark.parametrize('evidence_order', [['e1', 'e2'], ['e2', 'e1']])
def test_auto_added_source_does_not_guess_shared_evidence_ownership(tmp_path, evidence_order):
    state = module_state(tmp_path)
    state['narrative_plan']['sections'][0]['evidence_ids'] = ['e1', 'e2']
    state['narrative_plan']['sections'][1]['evidence_ids'] = ['e1']
    state['narrative_plan']['sections'][1]['required_evidence_ids'] = ['e1']
    raw = raw_plan();raw['modules'][0].update(evidence_ids=evidence_order, source_plan_unit_ids=[])
    with pytest.raises(ModulePlanValidationError) as error: normalize_module_plan(raw, state)
    assert any(i['code'] == 'ambiguous_evidence_origin' for i in error.value.issues)


def test_corrected_plan_reaches_existing_writer_verifier_and_publication(monkeypatch, tmp_path):
    import src.agents.sample_module_planner as planner
    from src.agents.claim_writer import claim_writer_node
    from src.workflow.sample_modules import sample_claim_verifier_node
    from src.agents.grounded_curator import grounded_curator_node
    from src.workflow.exploration_runner import PosterExplorationRunner
    from src.workflow.exploration_store import ExplorationStore
    from src.layout.repair_budget import budget_usage
    from test_sample_module_body import stub_models
    from test_exploration_samples import render_sample, critic_with_scores
    calls = stub_models(monkeypatch);base_agent = planner.LangGraphAgent
    invalid = raw_plan();invalid['modules'][0]['evidence_ids'] = []
    class Agent(base_agent):
        def step(self, prompt):
            if self.name == 'grounded_curator' and not any(name == self.name for name, _ in calls):
                calls.append((self.name, prompt))
                return SimpleNamespace(content=json.dumps(invalid), input_tokens=1, output_tokens=1)
            return super().step(prompt)
    monkeypatch.setattr(planner, 'LangGraphAgent', Agent)
    state = module_state(tmp_path);plan = deepcopy(state['narrative_plan'])
    def research(s): s['narrative_plan'] = deepcopy(plan);return s
    def design(s):
        assert s['sample_module_plan']['planning_diagnostics']['correction_used']
        assert s['verified_module_board']['spatial_content_plan']['sections'][0]['claim_ids']
        assert budget_usage(s['iteration_context']['attempt_diagnostics_dir']) == (0, 0)
        s['story_board'] = None
        return render_sample(s)
    store = ExplorationStore(tmp_path/'store')
    runner = PosterExplorationRunner(storage=store, samples=1, random_seed=31,
        paper_nodes=[], preparation_nodes=[research, sample_module_planner_node, claim_writer_node, sample_claim_verifier_node],
        design_nodes=[grounded_curator_node, design], critic=critic_with_scores([40]))
    result = runner.run(state, paper_ready=True)
    assert result['run_state']['rendered_samples'] == 1
    assert [name for name, _ in calls] == ['grounded_curator', 'grounded_curator', 'claim_writer', 'claim_verifier']
    row = result['run_state']['results'][0]
    published = read_json(store.verify_poster(row['poster_id'])/'diagnostics/sample_module_plan.json')
    assert published['planning_diagnostics']['correction_used']
    assert not list(store.run_path(runner.run_id).rglob('model_repair_budget.json'))
    assert not list(store.run_path(runner.run_id).rglob('curation_budget.json'))
