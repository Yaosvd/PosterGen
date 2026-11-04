"""Evidence instrument/finding ownership, never inferred repairs or rule scores."""
from copy import deepcopy

import pytest
from jsonschema import ValidationError
from test_editorial_model_scoring import context, responses, aggregate
from src.workflow import editorial_critic as critic


def instrument(context):
    context.state['critic_measurement_evidence'] = {
        'geometry': {'status': 'measured', 'findings': [{'issue_id': 'GEOMETRY-BOUNDS-9',
            'location': {'element_id': 'module_0_text'}, 'observation': 'Outside canvas'}]},
        'typography': {'status': 'measured', 'findings': [{'issue_id': 'TYPOGRAPHY-SMALL-1'}]}}
    return responses(context)


def test_actual_finding_identifier_has_explicit_instrument_owner(context):
    content, visual = instrument(context)
    evidence = visual['assessments']['layout_structure']['evidence'][0]
    evidence.update(measurement_id='geometry', finding_id='GEOMETRY-BOUNDS-9')
    critic._validate(visual, critic.response_schema(context.state, critic.VISUAL_SCHEMA), context.state)
    report = aggregate(context, content, visual)
    assert report['overall_score'] == 85  # Fixed model scores; evidence adds no rule penalty.
    assert report['submetric_assessments']['layout_structure']['evidence'][0]['finding_id'] == 'GEOMETRY-BOUNDS-9'


@pytest.mark.parametrize('measurement,finding', [('', 'GEOMETRY-BOUNDS-9'),
    ('typography', 'GEOMETRY-BOUNDS-9'), ('geometry', 'invented')])
def test_missing_unknown_or_wrong_parent_reference_rejects(context, measurement, finding):
    _, visual = instrument(context)
    visual['assessments']['layout_structure']['evidence'][0].update(measurement_id=measurement, finding_id=finding)
    with pytest.raises(critic.CriticResponseError, match='does not belong'):
        critic._validate(visual, critic.VISUAL_SCHEMA, context.state)


def test_issue_id_is_not_a_measurement_name_even_when_real(context):
    _, visual = instrument(context)
    visual['assessments']['layout_structure']['evidence'][0]['measurement_id']='GEOMETRY-BOUNDS-9'
    with pytest.raises(critic.CriticResponseError, match='Unknown identifier'):
        critic._validate(visual, critic.VISUAL_SCHEMA, context.state)


def test_response_schema_and_catalog_restrict_identifiers_without_mutating_evidence(context):
    _, visual=instrument(context); original=deepcopy(context.state['critic_measurement_evidence'])
    catalog=critic.reference_catalog(context.state)
    assert catalog['measurements']['geometry']==['GEOMETRY-BOUNDS-9']
    schema=critic.response_schema(context.state, critic.VISUAL_SCHEMA)
    fields=schema['properties']['assessments']['properties']['layout_structure']['properties']['evidence']['items']['properties']
    assert 'geometry' in fields['measurement_id']['enum'] and 'GEOMETRY-BOUNDS-9' not in fields['measurement_id']['enum']
    assert 'GEOMETRY-BOUNDS-9' in fields['finding_id']['enum']
    critic._validate(visual, schema, context.state)  # Global direct observation with empty IDs is legal.
    visual['assessments']['layout_structure']['evidence'][0]['finding_id']='invented'
    with pytest.raises(ValidationError):critic._validate(visual, schema, context.state)
    assert context.state['critic_measurement_evidence']==original
    assert 'enum' not in critic.EVIDENCE['properties']['measurement_id']
