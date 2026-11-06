"""Exact module coverage at generation time, with unchanged downstream reviews."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from critic_fixtures import content_reply, content_wire_reply
from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_critic as critic
from src.workflow.editorial_requests import wire_schema
from test_curator_schema import fake_model
from test_editorial_model_scoring import context


@pytest.mark.parametrize('family_id', LayoutFamilyRegistry().ids())
def test_dependency_slots_follow_real_modules_without_mutating_shared_schema(family_id):
    zones = LayoutFamilyRegistry().get(family_id).zones
    modules = [{'module_id': f'actual_{i}', 'zone_id': z['zone_id']} for i, z in enumerate(zones)]
    state = {'editorial_candidate': {'modules': modules}, 'layout_spec': {'zones': zones}}
    original = deepcopy(critic.CONTENT_SCHEMA)
    schema = critic.content_request_schema(state, critic.response_schema(state, critic.CONTENT_SCHEMA))
    Draft202012Validator.check_schema(schema)
    slots = schema['properties']['content_dependencies']['properties']['modules']
    assert slots['required'] == [m['module_id'] for m in modules]
    assert set(slots['properties']) == set(slots['required'])
    assert slots['additionalProperties'] is False
    assert wire_schema(schema, 'local_text') == schema  # No unsupported uniqueness keyword.
    assert critic.CONTENT_SCHEMA == original


def test_real_request_preserves_wire_journal_and_normalizes_for_replay(context, monkeypatch):
    original = content_reply(context.state['editorial_candidate']['modules'])
    wire = content_wire_reply(original)
    # JSON member order must not change the authored module order downstream.
    wire['content_dependencies']['modules'] = dict(reversed(list(wire['content_dependencies']['modules'].items())))
    before = deepcopy(wire)
    bindings = []
    calls = fake_model(monkeypatch, [wire], bindings)
    result = critic.content_evaluation(context)
    assert result == original and wire == before
    root = Path(context.state['sample_preparation_dir']) / 'editorial/final_content'
    def saved(name):
        return json.loads((root / name).read_text())['payload']
    schema = saved('identity.json')['schema']
    assert schema == bindings[0]['response_format']['json_schema']['schema']
    assert schema['properties']['content_dependencies']['properties']['modules']['type'] == 'object'
    assert json.loads(saved('response_00.json')['content']) == before
    assert saved('accepted.json')['value'] == before
    assert len(calls) == 1 and not (root / 'request_01.json').exists()
    assert not (root.parents[1] / 'editorial_format_correction.json').exists()
    # Re-read the durable original response, rather than relying only on memory.
    for key in ('_editorial_content_input_digest', '_editorial_content_evaluation'):
        context.state.pop(key, None)
    assert critic.content_evaluation(context) == original
    assert len(calls) == 1


@pytest.mark.parametrize('fault', ['missing', 'extra', 'inner_id', 'old_duplicate_array',
                                   'duplicate_slot_key', 'duplicate_root_key', 'malformed'])
def test_invalid_dependency_response_never_silently_repairs_or_spends_another_call(context, monkeypatch, fault):
    original = content_reply(context.state['editorial_candidate']['modules'])
    wire = content_wire_reply(original)
    slots = wire['content_dependencies']['modules']
    first = next(iter(slots))
    if fault == 'missing':
        slots.pop(first)
    elif fault == 'extra':
        slots['invented'] = deepcopy(slots[first])
    elif fault == 'inner_id':
        slots[first]['module_id'] = first
    elif fault == 'old_duplicate_array':
        wire['content_dependencies']['modules'] = original['content_dependencies']['modules'] + [
            {'module_id': first, 'meaning': '(duplicate guard — see above)', 'prerequisites': []}]
    content = json.dumps(wire)
    if fault == 'duplicate_slot_key':
        # This is not a duplicate array object: default json.loads would overwrite it.
        needle = json.dumps(first) + ': '
        content = content.replace(needle, needle + json.dumps(slots[first]) + ', ' + needle, 1)
    elif fault == 'duplicate_root_key':
        content = '{"reason":"must not be overwritten",' + content[1:]
    elif fault == 'malformed':
        content = content[:-1]
    calls = []
    class Model:
        def __init__(self, system, config, state, name):
            assert name == 'critic_content'
        def reset(self):
            pass
        def step(self, message):
            calls.append(message)
            return SimpleNamespace(content=content, input_tokens=1, output_tokens=1)
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    for _ in range(2):
        with pytest.raises(ValueError):
            critic.content_evaluation(context)
    root = Path(context.state['sample_preparation_dir']) / 'editorial/final_content'
    assert len(calls) == 1
    assert not (root / 'accepted.json').exists()
    assert not (root / 'request_01.json').exists()
    assert not (root.parents[1] / 'editorial_format_correction.json').exists()
    assert not (root.parent / 'final_visual').exists()
    assert json.loads((root / 'response_00.json').read_text())['payload']['content'] == content
    if fault.startswith('duplicate_'):
        invalid = json.loads((root / 'invalid_00.json').read_text())['payload']
        assert 'Duplicate JSON property' in invalid['reason']
