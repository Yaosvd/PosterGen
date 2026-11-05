"""Canonical object IDs across compilation, rendering, audit and Critic; offline."""
from copy import deepcopy

import pytest
from jsonschema import ValidationError

from critic_fixtures import content_reply, visual_reply, finding
from src.layout.element_identity import element_id, identified_layout
from src.layout.render_fit import evaluate_rendered_boxes
from src.workflow import editorial_critic as critic


@pytest.mark.parametrize('kind,extra,expected', [
    ('section_title', {}, 'mod_1_title'), ('section_container', {}, 'mod_1_container'),
    ('title_accent_block', {}, 'mod_1_title_accent_block'),
    ('title_accent_line', {}, 'mod_1_title_accent_line'),
    ('text', {}, 'mod_1'), ('visual', {'visual_id': 'figure_1'}, 'mod_1_figure_1'),
    ('mixed', {}, 'mod_1_mixed'), ('title', {}, 'poster_title'),
    ('aff_logo', {}, 'aff_logo'), ('conf_logo', {}, 'conf_logo'), ('qr_code', {}, 'qr_code'),
])
def test_role_ids_and_explicit_ids_are_stable(kind, extra, expected):
    original = {'type': kind, 'section_id': 'mod_1', **extra}
    assert element_id(original) == expected
    assert element_id({**original, 'id': 'explicit_existing_id'}) == 'explicit_existing_id'
    assert 'id' not in original


def test_identity_assignment_changes_only_id_and_is_order_independent():
    layout = [{'type': 'section_title', 'section_id': 'mod_1', 'content': '**Exact title**', 'x': 1.234},
              {'type': 'text', 'id': 'body', 'section_id': 'mod_1', 'content': 'Exact text.\n', 'y': 2.345},
              {'type': 'title', 'content': 'Main title', 'font_size': 100}]
    before = deepcopy(layout)
    identified = identified_layout(layout)
    assert layout == before
    assert identified_layout(identified) == identified
    assert identified_layout(layout[::-1]) == identified[::-1]
    for old, new in zip(layout, identified):
        assert {k: v for k, v in new.items() if k != 'id'} == {k: v for k, v in old.items() if k != 'id'}
    assert element_id({'type': 'unknown_role'}) is None


@pytest.mark.parametrize('second', [
    {'type': 'text', 'id': 'mod_1_title'}, {'type': 'section_title', 'section_id': 'mod_1'}])
def test_conflicting_explicit_or_derived_ids_are_rejected(second):
    with pytest.raises(ValueError, match='Duplicate layout element id'):
        identified_layout([{'type': 'section_title', 'section_id': 'mod_1'}, second])


@pytest.mark.parametrize('identity', [' ', 7, False])
def test_invalid_explicit_id_is_not_silently_replaced(identity):
    with pytest.raises(ValueError, match='nonblank string'):
        identified_layout([{'type': 'section_title', 'section_id': 'mod_1', 'id': identity}])


def test_renderer_dispatch_uses_the_same_identity_without_changing_source(monkeypatch):
    from src.agents.renderer import Renderer
    renderer = object.__new__(Renderer)
    captured = {}
    monkeypatch.setattr(renderer, '_render_section_title', lambda slide, element, state: captured.update(element))
    original = {'type': 'section_title', 'section_id': 'mod_1', 'zone_id': 'band_1',
                'section_title': 'Exact title', 'x': 1.234, 'font_size': 64}
    before = deepcopy(original)
    renderer._render_element(None, original, {}, None)
    assert captured == {**before, 'id': 'mod_1_title'}
    assert original == before


@pytest.fixture
def state():
    return {'editorial_candidate': {'modules': [
                {'module_id': 'mod_1', 'zone_id': 'band_1'}, {'module_id': 'mod_2', 'zone_id': 'band_2'}]},
            'layout_spec': {'zones': [{'zone_id': 'band_1'}, {'zone_id': 'band_2'}]},
            'critic_measurement_evidence': {'geometry': {'findings': []}},
            'styled_layout': [
                {'type': 'section_title', 'section_id': 'mod_1', 'zone_id': 'band_1',
                 'section_title': 'The Discrete Gap', 'x': 1, 'y': 1, 'width': 6, 'height': .6},
                {'type': 'text', 'section_id': 'mod_1', 'zone_id': 'band_1', 'id': 'mod_1_text',
                 'content': 'Complete scientific body text.', 'x': 1, 'y': 2, 'width': 6, 'height': 1},
                {'type': 'section_title', 'section_id': 'mod_2', 'zone_id': 'band_2',
                 'section_title': 'Method Design', 'x': 1, 'y': 4, 'width': 6, 'height': .6},
                {'type': 'title', 'content': 'Poster title', 'font_size': 100},
                {'type': 'aff_logo', 'path': '/unused/logo.png'}]}


def test_missing_title_id_agrees_between_renderfit_input_and_critic_without_mutation(state):
    before = deepcopy(state)
    body = state['styled_layout'][:2]
    blocks = [(72, 72, 360, 105, 'The Discrete Gap', 0, 0),
              (72, 144, 400, 180, 'Complete scientific body text.', 1, 0)]
    audit = evaluate_rendered_boxes(body, blocks, poster_width=10, poster_height=10)
    assigned_audit = evaluate_rendered_boxes(identified_layout(body), blocks, poster_width=10, poster_height=10)
    assert audit['passed'] and audit['matched_text_count'] == 2
    assert audit['matched_text_boxes'] == assigned_audit['matched_text_boxes']
    assert audit['issues'] == assigned_audit['issues']
    title = next(e for e in audit['matched_text_boxes'] if e['element_type'] == 'section_title')
    assert title['element_id'] == 'mod_1_title'
    catalog = critic.reference_catalog(state)
    assert catalog['elements']['mod_1_title'] == {
        'element_type': 'section_title', 'module_id': 'mod_1', 'zone_id': 'band_1'}
    assert {'mod_1_title', 'mod_2_title', 'poster_title', 'aff_logo'} <= set(catalog['element_ids'])
    assert critic.measurement_evidence(state)['authored_elements'] == identified_layout(state['styled_layout'])
    raw = visual_reply(state['editorial_candidate']['modules'])
    raw['assessments']['element_alignment']['evidence'][0].update(
        module_id='mod_1', element_id=title['element_id'], measurement_id='geometry')
    critic._validate(raw, critic.response_schema(state, critic.VISUAL_SCHEMA), state)
    assert state == before


def test_catalog_never_trusts_arbitrary_ids_from_diagnostic_text(state):
    state['render_fit_report'] = {'matched_text_boxes': [{'element_id': 'invented_title'}]}
    assert 'invented_title' not in critic.reference_catalog(state)['element_ids']
    raw = visual_reply(state['editorial_candidate']['modules'])
    raw['assessments']['element_alignment']['evidence'][0]['element_id'] = 'invented_title'
    with pytest.raises(ValidationError):
        critic._validate(raw, critic.response_schema(state, critic.VISUAL_SCHEMA), state)
    with pytest.raises(critic.CriticResponseError, match='Unknown identifier'):
        critic._validate(raw, critic.VISUAL_SCHEMA, state)


@pytest.mark.parametrize('where', ['evidence', 'issue', 'note', 'zone_only'])
def test_known_id_cannot_be_attached_to_a_different_module_or_zone(state, where):
    raw = visual_reply(state['editorial_candidate']['modules'])
    if where == 'evidence':
        raw['assessments']['element_alignment']['evidence'][0].update(
            module_id='mod_2', element_id='mod_1_title')
    else:
        f = finding('mod_2' if where != 'zone_only' else '', scope='layout', severity='warning')
        f['location'].update(element_id='mod_1_title', zone_id='band_2')
        if where == 'note':
            raw['review_notes'] = [{'note_type': 'advisory', 'scope': f['scope'],
                'location': f['location'], 'observation': f['observation'],
                'original_support': '', 'recommendation': 'Optional review.'}]
        else:raw['issues'] = [f]
    with pytest.raises(critic.CriticResponseError, match='does not belong'):
        critic._validate(raw, critic.response_schema(state, critic.VISUAL_SCHEMA), state)


def test_dynamic_enums_cover_all_model_reference_fields_and_leave_global_observations_legal(state):
    modules = state['editorial_candidate']['modules']
    for base, raw in ((critic.CONTENT_SCHEMA, content_reply(modules)),
                      (critic.VISUAL_SCHEMA, visual_reply(modules))):
        original = deepcopy(base)
        schema = critic.response_schema(state, base)
        props = schema['properties']
        first = next(iter(props['assessments']['properties'].values()))
        fields = first['properties']['evidence']['items']['properties']
        assert fields['module_id']['enum'] == ['', 'mod_1', 'mod_2']
        assert 'mod_1_title' in fields['element_id']['enum'] and '' in fields['element_id']['enum']
        for name in ('issues', 'review_notes'):
            location = props[name]['items']['properties']['location']['properties']
            assert 'band_1' in location['zone_id']['enum']
            assert 'mod_1_title' in location['element_id']['enum']
        assert props['issues']['items']['properties']['forbidden_operations'] == original['properties']['issues']['items']['properties']['forbidden_operations']
        assert props['issues']['items']['properties']['allowed_operations'] == original['properties']['issues']['items']['properties']['allowed_operations']
        if 'content_dependencies' in props:
            deps = props['content_dependencies']['properties']
            assert deps['modules']['items']['properties']['module_id']['enum'] == ['mod_1', 'mod_2']
            assert 'mod_2' in deps['relations']['items']['properties']['dependent_module_id']['enum']
        else:
            review = props['reading_review']['properties']
            assert review['entry_module_ids']['items']['enum'] == ['mod_1', 'mod_2']
            assert review['likely_paths']['items']['items']['enum'] == ['mod_1', 'mod_2']
            assert review['ambiguous_transitions']['items']['properties']['from_module_id']['enum'] == ['mod_1', 'mod_2']
        critic._validate(raw, schema, state)
        next(iter(raw['assessments'].values()))['evidence'][0]['element_id'] = 'poster_title'
        critic._validate(raw, schema, state)
        raw['issues'] = [finding('mod_1', scope='layout', severity='minor')]
        critic._validate(raw, schema, state)  # Ordinary operation strings remain unconstrained.
        assert base == original
