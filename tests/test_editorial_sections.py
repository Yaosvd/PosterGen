"""Three section types preserve material and use the existing finite repair path."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.workflow import editorial_parser
from src.workflow.editorial_contract import EditorialOutputError
from src.workflow.editorial_requests import request
from src.workflow.paper_cache import copy_paper_cache
from src.workflow.exploration_store import ExplorationStore
from test_editorial_generation import state_for
from test_editorial_field_repair import model as model_replies


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No live model'))


def material(kind='evaluation'):
    return {'paper_sections': [{'section_name': 'Discussion', 'section_type': kind,
        'content': 'Under setting X:\n- Accuracy is 0.80 versus 0.75.\n- The rate is tau/n.',
        'key_points': ['Accuracy increases by 0.05 under setting X.'], 'importance': 'high',
        'contains_figures': ['figure_1'], 'contains_tables': ['table_1']}]}


def parts(message):
    prompt, rest = message.split('\nINPUT:\n', 1)
    payload, schema = rest.split('\nCOMPLETE OUTPUT JSON SCHEMA:\n', 1)
    return prompt, json.loads(payload), json.loads(schema)


@pytest.mark.parametrize('kind', ['foundation', 'method', 'evaluation'])
def test_section_name_is_independent_of_type_and_full_material_replays(monkeypatch, tmp_path, kind):
    state = state_for(tmp_path)
    original = material(kind)
    calls = model_replies(monkeypatch, [original])
    source = 'Beginning\n' + 'source paragraph\n' * 1200 + 'End of paper'
    assert editorial_parser.sections(state, source) == original
    assert editorial_parser.sections(state, source) == original
    assert len(calls) == 1
    _, payload, schema = parts(calls[0])
    assert payload['original_text'] == source
    assert set(payload) == {'original_text', 'extraction_quality'}
    assert set(schema['properties']) == {'paper_sections'}
    section_schema = schema['properties']['paper_sections']['items']
    assert set(section_schema['required']) == set(original['paper_sections'][0])
    assert section_schema['properties']['section_type']['enum'] == ['foundation', 'method', 'evaluation']
    assert schema['properties']['paper_sections']['minItems'] == 1


def test_outbound_guidance_and_json_example_match_actual_schema(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    calls = model_replies(monkeypatch, [material()])
    editorial_parser.sections(state, state['raw_text'])
    prompt, _, schema = parts(calls[0])
    for guidance in (
        'Focus on sections that would be relevant for an academic poster.',
        'Preserve key technical details, formulas, and findings',
        'Maintain important bullet points and lists',
        'Remove excessive citations and references',
        'Keep section content under 1000 words',
        'Keep each section under 1000 words',
        'Discussion/Analysis',
        'not a fixed output template or an exhaustive list',
        'Do not invent fallback sections or silently drop the latter half of the paper',
    ):
        assert guidance in prompt
    assert 'experimental conditions' not in prompt and 'limitations' not in prompt
    assert 'Aim for fewer' not in prompt and 'just to meet a quota' not in prompt
    example = json.loads(prompt.split('```json\n', 1)[1].split('```', 1)[0])
    assert 'max 1000 words' in example['paper_sections'][0]['content']
    Draft202012Validator(schema).validate(example)


@pytest.mark.parametrize('old_kind', ['discussion', 'other'])
def test_removed_type_repairs_only_the_label_and_replays(monkeypatch, tmp_path, old_kind):
    state = state_for(tmp_path)
    original = material(old_kind)
    calls = model_replies(monkeypatch, [original, {'repairs': {'field_0': 'evaluation'}}])
    expected = material()
    assert editorial_parser.sections(state, state['raw_text']) == expected
    assert editorial_parser.sections(state, state['raw_text']) == expected
    assert len(calls) == 2
    repair_schema = json.loads(calls[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:\n')[-1])
    assert list(repair_schema['properties']['repairs']['properties']) == ['field_0']
    assert repair_schema['properties']['repairs']['properties']['field_0']['enum'] == [
        'foundation', 'method', 'evaluation']
    root = Path(state['sample_preparation_dir'])/'editorial/paper/sections'
    plan = json.loads((root/'repair_plan.json').read_text())['payload']['plan']
    assert plan['targets'] == [{'path': ['paper_sections', 0, 'section_type'],
                               'action': 'replace', 'field': 'field_0'}]
    assert json.loads(json.loads((root/'response_00.json').read_text())['payload']['content']) == original
    assert json.loads((root/'accepted.json').read_text())['payload']['value'] == expected


@pytest.mark.parametrize('repair', [
    {'repairs': {'field_0': 'discussion'}},
    {'repairs': {'field_0': 'other'}},
    {'repairs': {'field_0': 'evaluation'}, 'content': 'Changed science'},
])
def test_invalid_or_expanded_type_repair_is_not_accepted_or_retried(monkeypatch, tmp_path, repair):
    state = state_for(tmp_path)
    calls = model_replies(monkeypatch, [material('discussion'), repair])
    for _ in range(2):
        with pytest.raises(EditorialOutputError):
            editorial_parser.sections(state, state['raw_text'])
    root = Path(state['sample_preparation_dir'])/'editorial/paper/sections'
    assert len(calls) == 2
    assert not (root/'accepted.json').exists()
    assert not (root/'request_02.json').exists()


def test_word_limit_is_guidance_without_a_new_truncation_or_retry(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    original = material()
    original['paper_sections'][0]['content'] = ' '.join(['word'] * 1001)
    calls = model_replies(monkeypatch, [original])
    assert editorial_parser.sections(state, state['raw_text']) == original
    assert len(calls) == 1


def test_old_five_type_request_history_is_rejected_before_any_new_call(monkeypatch, tmp_path):
    state = state_for(tmp_path)
    calls = model_replies(monkeypatch, [material('discussion')])
    def old_request(st, kind, payload, schema, **kwargs):
        schema = deepcopy(schema)
        schema['properties']['paper_sections']['items']['properties']['section_type']['enum'].extend([
            'discussion', 'other'])
        return request(st, kind, payload, schema, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(editorial_parser, 'request', old_request)
        assert editorial_parser.sections(state, state['raw_text']) == material('discussion')
    root = Path(state['sample_preparation_dir'])/'editorial/paper/sections'
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises(ValueError, match='identity/digest mismatch'):
        editorial_parser.sections(state, state['raw_text'])
    assert len(calls) == 1
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


@pytest.mark.parametrize('changed_path', [
    'config/prompts/editorial_sections.txt', 'src/workflow/editorial_parser.py'])
def test_section_prompt_or_schema_change_invalidates_explicit_paper_cache(tmp_path, changed_path):
    store = ExplorationStore(tmp_path/'store')
    state = state_for(tmp_path/'paper')
    settings = {'preparation_policy_version': 'sample_editorial_v1',
                'code_identity': {changed_path: 'old'}}
    identity = {'paper': 'same'}
    source, _ = store.open_run(identity, settings, seed=1, samples=1)
    target, _ = store.open_run(identity, settings, seed=2, samples=1)
    store.save_paper_foundation(source, state)
    copied = copy_paper_cache(store, source, target, identity, settings)
    assert copied['structured_sections'] == state['structured_sections']
    changed = deepcopy(settings)
    changed['code_identity'][changed_path] = 'new'
    with pytest.raises(ValueError, match='extraction identity changed'):
        copy_paper_cache(store, source, target, identity, changed)
