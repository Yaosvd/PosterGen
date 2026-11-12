"""Reference selection is structural, never an automatic repair of old judgments."""
from copy import deepcopy
import json

import pytest
from jsonschema import ValidationError

from critic_fixtures import content_reply, content_wire_reply, finding, reference_wire_reply, visual_reply
from src.workflow import editorial_critic as critic, critic_references as refs
from src.workflow.editorial_contract import EditorialStructureError
from src.workflow.editorial_requests import save


@pytest.fixture
def state(tmp_path):
    return {'sample_preparation_dir': str(tmp_path),
            'editorial_candidate': {'modules': [
                {'module_id': 'a', 'zone_id': 'left'}, {'module_id': 'b', 'zone_id': 'right'}]},
            'layout_spec': {'zones': [{'zone_id': 'left'}, {'zone_id': 'right'}]},
            'design_layout': [
                {'id': 'a_title', 'type': 'section_title', 'section_id': 'a'},
                {'id': 'b_title', 'type': 'section_title', 'section_id': 'b'},
                {'id': 'poster_title', 'type': 'title'}],
            'critic_measurement_evidence': {
                'geometry': {'findings': [{'issue_id': 'bounds'}, {'issue_id': 'shared'}]},
                'section_fit': {'findings': [{'issue_id': 'underfill'}, {'issue_id': 'shared'}]}}}


def schemas(state, content=False):
    report = critic.response_schema(state, critic.CONTENT_SCHEMA if content else critic.VISUAL_SCHEMA)
    schema = critic.content_request_schema(state, report) if content else report
    return refs.request_schema(schema, critic.request_reference_catalog(state)), report


def select(catalog, **fields):
    return next(k for k, v in catalog.items() if all(v[f] == x for f, x in fields.items()))


def test_catalog_deterministic_and_owners_explicit(state):
    before = deepcopy(state)
    catalog = critic.request_reference_catalog(state)
    assert catalog == critic.request_reference_catalog(state) and state == before
    duplicates = [v for v in catalog['evidence_refs'].values() if v['finding_id'] == 'shared']
    assert len(duplicates) == 2  # Same text across instruments still has two distinct choices.
    element = select(catalog['location_refs'], element_id='a_title')
    assert catalog['location_types'][element] == 'section_title'
    assert catalog['location_types']['L000'] == 'global'
    assert catalog['location_refs'][element] == {
        'section_id': 'a', 'zone_id': 'left', 'element_id': 'a_title'}


@pytest.mark.parametrize('content', [False, True])
@pytest.mark.parametrize('kind', ['global', 'report', 'finding', 'element', 'module', 'zone', 'cross_module'])
def test_expand_preserves_all_judgments_and_target_scope(state, content, kind):
    raw = (content_reply if content else visual_reply)(state['editorial_candidate']['modules'])
    raw['issues'] = [finding(scope='layout_structure')]
    wire = (content_wire_reply if content else reference_wire_reply)(raw, state)
    catalog = critic.request_reference_catalog(state)
    metric = next(iter(wire['assessments'].values()))
    evidence = metric['evidence'][0]
    if kind in ('report', 'finding'):
        evidence['evidence_ref'] = select(catalog['evidence_refs'], measurement_id='geometry',
                                         finding_id='bounds' if kind == 'finding' else '')
    if kind in ('element', 'module', 'zone', 'cross_module'):
        targets = {'element': [{'element_id': 'a_title'}],
                   'module': [{'section_id': 'a', 'element_id': ''}],
                   'zone': [{'zone_id': 'left', 'section_id': '', 'element_id': ''}],
                   'cross_module': [{'element_id': 'a_title'}, {'element_id': 'b_title'}]}[kind]
        chosen = [select(catalog['location_refs'], **t) for t in targets]
        evidence['location_refs'] = chosen
        wire['issues'][0]['location_refs'] = chosen
    original = deepcopy(wire)
    schema, report = schemas(state, content)
    expanded = critic.normalize_reference_response(wire, schema, report, state, content=content)
    assert wire == original
    for key, metric in raw['assessments'].items():
        assert {k: v for k, v in metric.items() if k != 'evidence'} == {
            k: v for k, v in expanded['assessments'][key].items() if k != 'evidence'}
        for field in ('observation', 'original_support'):
            assert expanded['assessments'][key]['evidence'][0][field] == metric['evidence'][0][field]
    if kind == 'cross_module':
        assert expanded['issues'][0]['location'] == refs.EMPTY_LOCATION
        assert len(expanded['issues'][0]['locations']) == 2
        assert len(next(iter(expanded['assessments'].values()))['evidence']) == 1
        from types import SimpleNamespace
        ctx = SimpleNamespace(state=state, config={'evaluators': {'visual': {}}})
        result = critic._model_result(ctx, 'visual', expanded, list(expanded['assessments']))
        assert result.issues[0]['evidence']['locations'] == expanded['issues'][0]['locations']
    if kind == 'zone':
        assert next(iter(expanded['assessments'].values()))['evidence'][0]['locations'][0]['zone_id'] == 'left'


@pytest.mark.parametrize('fault', ['unknown', 'empty', 'duplicate', 'global_mix', 'old_pair', 'old_location'])
def test_invalid_wire_never_repaired_or_interpreted(state, fault):
    raw = visual_reply(state['editorial_candidate']['modules'])
    wire = reference_wire_reply(raw, state)
    row = wire['assessments']['layout_structure']['evidence'][0]
    if fault == 'unknown': row['evidence_ref'] = 'invented'
    elif fault == 'empty': row['location_refs'] = []
    elif fault == 'duplicate': row['location_refs'] = ['L001', 'L001']
    elif fault == 'global_mix': row['location_refs'] = ['L000', 'L001']
    elif fault == 'old_pair': row.update(measurement_id='editorial_fit', finding_id='underfill')
    else: row.update(module_id='b', element_id='a_title')
    schema, report = schemas(state)
    with pytest.raises((ValidationError, EditorialStructureError)):
        critic.normalize_reference_response(wire, schema, report, state)


def test_expanded_locations_still_have_strict_ownership(state):
    raw = visual_reply(state['editorial_candidate']['modules'])
    row = raw['assessments']['layout_structure']['evidence'][0]
    row['locations'] = [{'section_id': 'b', 'zone_id': 'right', 'element_id': 'a_title'}]
    with pytest.raises(critic.CriticResponseError, match='does not belong'):
        critic._validate(raw, critic.VISUAL_SCHEMA, state)


def test_normalized_journal_preserves_wire_and_rejects_tampering(state):
    from pathlib import Path
    directory = 'editorial/final_visual'
    root = Path(state['sample_preparation_dir']) / directory
    raw = visual_reply(state['editorial_candidate']['modules'])
    wire = reference_wire_reply(raw, state)
    schema, report = schemas(state)
    expanded = critic.normalize_reference_response(wire, schema, report, state)
    save(root / 'identity.json', {'input_digest': 'fixture'})
    save(root / 'response_00.json', {'input_digest': 'fixture', 'content': json.dumps(wire)})
    before = (root / 'response_00.json').read_bytes()
    critic.save_normalized_response(state, directory, wire, expanded)
    critic.save_normalized_response(state, directory, wire, expanded)
    assert (root / 'response_00.json').read_bytes() == before
    payload = json.loads((root / 'normalized.json').read_text())['payload']
    assert payload['value'] == raw
    payload['value']['reason'] = 'tampered'
    save(root / 'normalized.json', payload)
    with pytest.raises(ValueError, match='normalized response changed'):
        critic.save_normalized_response(state, directory, wire, expanded)
