"""Verdict recovery cannot fabricate science or add an independent retry budget."""
import json
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from src.workflow.sample_module_writing import verifier_response
from src.workflow.sample_verification import verdict_schema
from src.workflow.module_planning_requests import charge_preparation_repair
from utils.persistence import read_json
from test_sample_module_body import module_state, expression


def state_for_protocol(tmp_path):
    state = module_state(tmp_path)
    state.update(joint_preparation=True, sample_preparation_dir=str(tmp_path))
    return state


def verdict(claim, supported=True):
    result = {'supported': supported, 'error_types': [] if supported else ['entity_mismatch'],
              'reason': 'Checked the cited source.', 'corrected_text': '',
              'coverage': [{'quote': claim['text'], 'evidence_ids': claim['evidence_ids'], 'supported': supported}],
              'relationships_supported': supported, 'covered_required_evidence_ids': claim['required_evidence_ids'] if supported else [],
              'necessary_information_preserved': supported}
    if claim.get('editorial_revision'): result['editorial_information_preserved'] = supported
    if claim.get('completion_origin'):
        result.update(completion_relevant=supported, completion_non_redundant=supported)
    return result


class Agent:
    def __init__(self, *responses): self.responses = list(responses); self.calls = []
    def reset(self): pass
    def step(self, prompt):
        assert self.response_json_schema
        self.calls.append(prompt)
        value = self.responses.pop(0)
        return SimpleNamespace(content=value if isinstance(value, str) else json.dumps(value), input_tokens=1, output_tokens=1)


@pytest.mark.parametrize('bad', [
    {'claim_id': 'pc_display_002_001', 'text': 'The corrected claim.', 'evidence_ids': ['e1'],
     'required_evidence_ids': ['e1'], 'original_expression': 'The original claim.'},
    {'supported': 'true'}, {'supported': 1}, {}, 'not json',
])
def test_non_verdict_recovery_is_charged_archived_and_replayed_without_calls(tmp_path, bad):
    state = state_for_protocol(tmp_path); claim = expression(); good = verdict(claim)
    agent = Agent(bad, good)
    response = verifier_response(state, agent, 'Verify this frozen input', claim['claim_id'], claim=claim)
    assert json.loads(response.content) == good and len(agent.calls) == 2
    assert not hasattr(agent, 'response_json_schema')
    budget = read_json(tmp_path/'preparation_repair_budget.json')['payload']
    assert budget['limit'] == 1 and budget['charge']['kind'] == 'verification_format_correction'
    replay = Agent()
    assert verifier_response(state, replay, 'Verify this frozen input', claim['claim_id'], claim=claim).content == response.content
    assert not replay.calls
    assert len(list(tmp_path.rglob('response_01.json'))) == 1


def test_recovery_does_not_steal_spent_writer_allowance_or_capacity_quality_rounds(tmp_path):
    state = state_for_protocol(tmp_path); claim = expression()
    charge_preparation_repair(state, 'joint_writer_format_correction', 'poster', 'old-prompt')
    agent = Agent({'text': claim['text']}, verdict(claim))
    with pytest.raises(ValueError, match='allowance is exhausted'):
        verifier_response(state, agent, 'Verify', claim['claim_id'], claim=claim)
    assert len(agent.calls) == 1
    assert not list(tmp_path.rglob('request_01.json'))
    assert not list(tmp_path.rglob('content_edit_budget.json'))


def test_interrupted_charged_format_repair_is_never_resubmitted(tmp_path):
    state = state_for_protocol(tmp_path); claim = expression()
    class Interrupted(Agent):
        def step(self, prompt):
            if self.calls: raise RuntimeError('interrupted')
            return super().step(prompt)
    with pytest.raises(RuntimeError, match='interrupted'):
        verifier_response(state, Interrupted({}), 'Verify', claim['claim_id'], claim=claim)
    replay = Agent(verdict(claim))
    with pytest.raises(ValueError, match='charged but has no saved response'):
        verifier_response(state, replay, 'Verify', claim['claim_id'], claim=claim)
    assert not replay.calls


def test_second_invalid_response_stops_without_fabricated_verdict(tmp_path):
    state = state_for_protocol(tmp_path); claim = expression(); agent = Agent({}, {'supported': 'true'})
    with pytest.raises(ValueError, match='Invalid sample verification verdict'):
        verifier_response(state, agent, 'Verify', claim['claim_id'], claim=claim)
    assert len(agent.calls) == 2 and not list(tmp_path.rglob('verdict.json'))


def test_stop_after_invalid_response_does_not_charge_or_submit_format_repair(tmp_path):
    from src.workflow.sample_verification import VerificationInterrupted
    state = state_for_protocol(tmp_path); claim = expression(); agent = Agent({})
    state['_force_stop_requested'] = lambda: bool(agent.calls)
    with pytest.raises(VerificationInterrupted):
        verifier_response(state, agent, 'Verify', claim['claim_id'], claim=claim)
    assert len(agent.calls) == 1 and not (tmp_path/'preparation_repair_budget.json').exists()


def test_isolated_verification_preserves_interruption_on_parent_state(monkeypatch, tmp_path):
    import src.agents.claim_verifier as verifier
    from src.workflow.joint_preparation import verify_selected_science
    state = state_for_protocol(tmp_path); state['poster_claims'] = {'claims': [expression()]}
    def interrupt(current):
        current['_joint_interrupted'] = True
        return current
    monkeypatch.setattr(verifier, 'claim_verifier_node', interrupt)
    result = verify_selected_science(state)
    assert result['_joint_interrupted'] and not result['verification_passed']


def test_valid_negative_is_not_a_format_retry(tmp_path):
    state = state_for_protocol(tmp_path); claim = expression(); negative = verdict(claim, False)
    agent = Agent(negative)
    response = verifier_response(state, agent, 'Verify', claim['claim_id'], claim=claim)
    assert json.loads(response.content)['supported'] is False
    assert len(agent.calls) == 1 and not (tmp_path/'preparation_repair_budget.json').exists()


@pytest.mark.parametrize('kind', ['editorial_revision', 'completion_origin'])
def test_required_preservation_and_completion_verdicts_remain_explicit(tmp_path, kind):
    claim = expression(); claim[kind] = {'phase': 'quality'}
    result = verdict(claim)
    field = 'editorial_information_preserved' if kind == 'editorial_revision' else 'completion_non_redundant'
    del result[field]
    assert list(Draft202012Validator(verdict_schema(claim)).iter_errors(result))
    negative = verdict(claim); negative[field] = False
    assert not list(Draft202012Validator(verdict_schema(claim)).iter_errors(negative))


@pytest.mark.parametrize('sample_policy', [True, False])
def test_schema_binding_is_scoped_and_legacy_keeps_json_object(monkeypatch, tmp_path, sample_policy):
    import utils.langgraph_utils as language
    from src.state.poster_state import ModelConfig
    seen = []
    class Bound:
        def __init__(self, kwargs): self.kwargs = kwargs
    class Model:
        def bind(self, **kwargs): seen.append(kwargs); return Bound(kwargs)
    monkeypatch.setattr(language, 'ChatOpenAI', Model)
    agent = language.LangGraphAgent.__new__(language.LangGraphAgent)
    agent.model = Model(); agent.config = ModelConfig('local', 'local_text')
    agent.history = []; agent.system_msg = 'Verify against the supplied evidence.'
    agent.request_policy = {'response_timeout_seconds': 900} if sample_policy else None
    agent._invoke_model = lambda *args: SimpleNamespace(content=json.dumps(verdict(expression())))
    agent._record_api_call = lambda *args, **kwargs: None
    state = state_for_protocol(tmp_path); claim = expression()
    original = agent.model
    verifier_response(state, agent, 'Verify', claim['claim_id'], claim=claim)
    assert agent.model is original and not hasattr(agent, 'response_json_schema')
    actual = seen[0]['response_format']
    assert actual['type'] == ('json_schema' if sample_policy else 'json_object')
    if sample_policy: assert actual['json_schema']['strict'] is True


@pytest.mark.parametrize('final_support', [True, False])
def test_correction_review_keeps_prior_reason_without_treating_it_as_support(monkeypatch, tmp_path, final_support):
    import src.agents.claim_verifier as verifier
    state = state_for_protocol(tmp_path); claim = expression(); state['poster_claims'] = {'claims': [claim]}
    prompts = []
    class Verifier(Agent):
        def __init__(self, *args): pass
        def step(self, prompt):
            prompts.append(prompt)
            current = json.loads(prompt.split('CLAIM:\n', 1)[1].split('\n\nEVIDENCE:', 1)[0])
            result = verdict(current, final_support if current.get('correction_review') else False)
            if not current.get('correction_review'):
                result['corrected_text'] = 'The model uses neural signals and predicts behavior.'
                result['reason'] = 'Use the source-supported entity name.'
            else:
                assert current['correction_review']['previous_verdict']['reason'] == 'Use the source-supported entity name.'
                assert current['original_expression'] == claim['text']
            return SimpleNamespace(content=json.dumps(result), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(verifier, 'LangGraphAgent', Verifier)
    monkeypatch.setattr(verifier, 'apply_agent_policy', lambda config, _: config)
    verifier.claim_verifier_node(state)
    assert len(prompts) == 2
    accepted = state['verified_claims']['claims']
    assert bool(accepted) is final_support
    if accepted: assert 'correction_review' not in accepted[0] and accepted[0]['verified']


def test_schema_conformance_cannot_bypass_numeric_evidence_gate(monkeypatch, tmp_path):
    import src.agents.claim_verifier as verifier
    state = state_for_protocol(tmp_path); claim = expression('The model predicts 999999 outcomes.')
    state['poster_claims'] = {'claims': [claim]}
    monkeypatch.setattr(verifier, 'LangGraphAgent', lambda *args: Agent(verdict(claim)))
    monkeypatch.setattr(verifier, 'apply_agent_policy', lambda config, _: config)
    verifier.claim_verifier_node(state)
    assert not state['verified_claims']['claims'] and not state['verification_passed']
