"""Quality-only rules retain provenance and still drive concrete Critic/Actor edits."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from src.rubrics import candidates, constraints, mining, refinement
from src.rubrics.library import LibraryStore, model_rules_for, rules_for
from src.rubrics.providers import configuration
from src.rubrics.storage import read
from src.workflow.editorial_requests import request, obj, STRING
from test_editorial_generation import state_for
from test_rubrics_candidate_review import review_package
from test_rubrics_framework import fake_render, frozen, rule, semantic_response


def mixed_library(tmp_path):
    rules = [dict(rule('planning'), applicable_stages=['planning'],
                  evidence_refs=['HISTORICAL_PLANNING_SOURCE']),
             dict(rule('body'), applicable_stages=['writing', 'capacity'],
                  evidence_refs=['HISTORICAL_BODY_SOURCE']),
             dict(rule('materials'), applicable_stages=['parser', 'palette'],
                  evidence_refs=['HISTORICAL_MATERIALS_SOURCE'])]
    store = LibraryStore(tmp_path / 'request_library')
    library = store.publish(rules, parent_version=None, source_batch_digest='offline fixture')
    return store, library


def without_refs(rules):
    return [{k: deepcopy(v) for k, v in r.items() if k != 'evidence_refs'} for r in rules]


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Real model forbidden'))


@pytest.mark.parametrize('kind,stage,expected_ids', [
    ('editorial_curator', 'planning', ['planning']),
    ('editorial_writer', 'writing', ['body']),
    ('editorial_balancer', 'capacity', ['body']),
    ('editorial_palette', 'palette', ['materials']),
    ('editorial_sections', 'parser', ['materials']),
    ('editorial_proofreading', 'parser', ['materials']),
    ('editorial_metadata', 'parser', ['materials']),
    ('editorial_abt', 'parser', ['materials']),
    ('editorial_visuals', 'parser', ['materials']),
])
def test_actual_editorial_request_omits_only_rule_evidence_refs(monkeypatch, tmp_path, kind, stage, expected_ids):
    import utils.langgraph_utils as language
    store, library = mixed_library(tmp_path)
    original = deepcopy(library)
    library_path = store.root / 'versions' / library['version'] / 'library.json'
    stored = library_path.read_bytes()
    state = state_for(tmp_path)
    state['generation_rubrics_snapshot'] = library
    messages = []

    class Model:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            messages.append(message)
            return SimpleNamespace(content='{"answer":"offline"}', input_tokens=1, output_tokens=1)

    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    payload = {'task': 'Keep the original input', 'evidence_refs': ['CURRENT_TASK_EVIDENCE']}
    assert request(state, kind, payload, obj({'answer': STRING}),
                   directory='model_view', correction=False) == {'answer': 'offline'}
    assert len(messages) == 1
    text = messages[0]
    guidance = json.loads(text.split('<GENERATION_RUBRICS>\n', 1)[1].split('\n</GENERATION_RUBRICS>', 1)[0])
    assert guidance['version'] == library['version'] and guidance['stage'] == stage
    assert [r['id'] for r in guidance['rules']] == expected_ids
    assert guidance['rules'] == without_refs(rules_for(original, stage))
    assert all(len(r) == 8 and 'revision_guidance' not in r for r in guidance['rules'])
    assert 'revision_guidance' not in text
    assert all(ref not in text for r in original['rules'] for ref in r['evidence_refs'])
    # Provenance in other task material is not recursively stripped.
    assert 'CURRENT_TASK_EVIDENCE' in text
    assert state['generation_rubrics_snapshot'] == original
    assert library_path.read_bytes() == stored and store.active() == original
    # Durable input receipts represent the exact reduced request sent to the model.
    assert read(Path(state['sample_preparation_dir']) / 'model_view/identity.json')['prompt'] == text


@pytest.mark.parametrize('missing_check', [False, True])
def test_critic_actor_wire_views_keep_full_checks_and_immutable_library(monkeypatch, tmp_path, missing_check):
    import utils.langgraph_utils as language
    state = frozen(monkeypatch, tmp_path)
    store, library = mixed_library(tmp_path)
    original = deepcopy(library)
    state['generation_rubrics_snapshot'] = library
    stored = (store.root / 'versions' / library['version'] / 'library.json').read_bytes()
    sent = []

    class Model:
        def __init__(self, system, config, current, name):
            self.name = name
            self.model = None
        def step(self, message):
            parts = json.loads(message)
            assert parts[1]['type'] == 'image_url'
            text = parts[0]['text']
            payload = json.loads(text.split('\nINPUT:\n', 1)[1].split('\nOUTPUT SCHEMA:\n', 1)[0])
            sent.append((self.name, text, payload))
            assert payload['rules'] == without_refs(original['rules'])
            assert all(len(r) == 8 and 'revision_guidance' not in r for r in payload['rules'])
            assert 'revision_guidance' not in text
            assert all(ref not in text for r in original['rules'] for ref in r['evidence_refs'])
            if self.name == 'rubrics_review':
                checked = original['rules'][:-1] if missing_check else original['rules']
                reply = {'checks': [{'rule_id': r['id'], 'status': 'violated', 'evidence': 'Visible fixture',
                                     'locations': [], 'action': 'Rename the module heading to Clear method'} for r in checked]}
            else:
                assert all(c['action'] == 'Rename the module heading to Clear method'
                           for c in payload['review']['checks'])
                reply = {'program_lines': payload['program'].replace('Shared method', 'Clear method').splitlines(),
                         'change_summary': 'Apply the concrete Critic feedback in the drawing program'}
            return SimpleNamespace(content=json.dumps(reply), input_tokens=1, output_tokens=1)

    monkeypatch.setattr(language, 'LangGraphAgent', Model)
    result = refinement.refine_once(state, request=refinement.glm_request, renderer=fake_render, measure=lambda s: s)
    assert [name for name, _, _ in sent] == (['rubrics_review'] if missing_check else ['rubrics_review', 'rubrics_revision'])
    assert result['refinement_result']['variant'] == ('P0' if missing_check else 'P1')
    if missing_check:
        assert 'every rule exactly once' in result['refinement_result']['reason']
    else:
        assert result['editorial_candidate']['modules'][0]['title'] == 'Clear method'
        assert state['editorial_candidate']['modules'][0]['title'] == 'Shared method'
    root = Path(state['refinement_directory'])
    for name, text, _ in sent:
        directory = 'review' if name == 'rubrics_review' else 'actor'
        assert read(root / directory / 'identity.json')['prompt'] == text
    assert state['generation_rubrics_snapshot'] == result['generation_rubrics_snapshot'] == original
    assert store.active() == original
    assert (store.root / 'versions' / library['version'] / 'library.json').read_bytes() == stored


def test_model_views_do_not_mutate_nested_library_or_stage_views(tmp_path):
    store, library = mixed_library(tmp_path)
    original = deepcopy(library)
    view = model_rules_for(library, 'review')
    assert view == without_refs(original['rules'])
    view[0]['applicable_stages'].append('capacity')
    view[0]['requirement'] = 'Changed in caller'
    assert library == original and store.active() == original
    assert rules_for(library, 'planning')[0]['evidence_refs'] == ['HISTORICAL_PLANNING_SOURCE']
    assert model_rules_for(library, 'revision') == without_refs(original['rules'])
    with pytest.raises(ValueError, match='Unknown Rubrics stage'):
        model_rules_for(library, 'unknown')


def test_batch_summary_reconciliation_and_human_package_keep_evidence(tmp_path):
    candidate = dict(rule('new'), evidence_refs=['NEW_OBSERVATION'])
    existing = [dict(rule('prior'), evidence_refs=['HISTORICAL_SOURCE'])]
    summary = {k: v for k, v in candidate.items() if k not in {'id', 'revision'}}
    assert len(summary) == 7 and 'revision_guidance' not in summary
    Draft202012Validator(mining.RULES).validate({'rules': [summary]})
    with pytest.raises(ValidationError):
        Draft202012Validator(mining.RULES).validate({'rules': [{**summary, 'revision_guidance': 'Legacy advice'}]})
    with pytest.raises(ValidationError):
        Draft202012Validator(mining.RULES).validate({'rules': without_refs([summary])})
    calls = []

    class Model:
        def check(self, roles): assert roles == ('reconciler',)
        def generate(self, role, payload, schema, root):
            calls.append(deepcopy(payload))
            return semantic_response(payload)

    result = mining.reconcile(candidate, existing, Model(), tmp_path / 'reconcile', configuration()['mining'],
                              contract=constraints.snapshot())
    assert result['decision'] == 'novel' and len(calls) == 1
    assert calls[0]['candidate'] == candidate and calls[0]['existing'] == existing
    assert 'revision_guidance' not in json.dumps(calls[0])
    root, parent = review_package(tmp_path / 'review')
    package = candidates.load(root)
    assert [r['evidence_refs'] for r in package['candidates']] == [['o1'], ['o2']]
    assert [o['id'] for o in package['observations']] == ['o1', 'o2']
    markdown = (root / 'review.md').read_text()
    assert '`o1`' in markdown and 'Visible legend' in markdown
    assert '`o2`' in markdown and 'Visible heading' in markdown
    assert 'revision_guidance' not in markdown
    assert all(len(r) == 9 and 'revision_guidance' not in r for r in package['candidates'])
    assert LibraryStore(root.parent.parent).active() == parent
    assert not (root.parent.parent / 'rubrics_v1').exists()
