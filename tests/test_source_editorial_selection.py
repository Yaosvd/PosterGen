"""Source-bound selection and attribution, independent of family identity."""
from copy import deepcopy

import pytest

from src.agents.grounded_curator import GroundedCurator
from src.layout.editorial import prepare_board, sections, source_for_fit, _merge_thin
from src.layout.editorial_selection import sanitize_selection, root_allowed
from src.layout.families import FAMILIES, LayoutFamily
from src.layout.family_contract import FamilyContract
from src.layout.presentation_policy import prepare_structure, contribution_roots, context_pair
from src.layout.composition_refinement import boundary_options
from src.layout.whitespace import selection_reference
from utils.source_context import evidence_contexts, body_context_index
from utils.module_content import existing_module_candidates
from test_presentation_policy import study, spec_for


def source_state():
    text = ('# Paper\n\n## Methods\n\nThe policy chooses a region.\n\n'
            '## Experiments\n\nData describes residential,\n\n'
            '#### Algorithm 1: Training.\n\n- Require: inputs\n- 1: Update policy.\n\n'
            'non-vacant parcels across the city.\n\n## Results\n\nThe method improves recall.')
    return {'raw_text': text, 'evidence_bank': {'items': [
        {'evidence_id': 'data', 'source_excerpt': 'non-vacant parcels across the city.',
         'source': {'section_id': 'algorithm', 'section_name': 'Algorithm 1: Training.'}},
        {'evidence_id': 'code', 'source_excerpt': 'Update policy.', 'source': {'section_id': 'algorithm'}},
        {'evidence_id': 'method', 'source_excerpt': 'The policy chooses a region.', 'source': {'section_id': 'methods'}}]}}


def test_float_resumes_parent_body_without_rewriting_sources():
    state = source_state()
    original = deepcopy(state)
    overlay = evidence_contexts(state)
    data = overlay['evidence']['data']
    assert data['status'] == 'located_body' and data['heading_path'] == ['Paper', 'Experiments']
    assert data['section_type'] == 'evaluation'
    assert state['raw_text'][data['start_char']:data['end_char']] == state['evidence_bank']['items'][0]['source_excerpt']
    assert data['page'] is None
    assert overlay['evidence']['code']['status'] == 'unknown'
    assert state == original
    assert evidence_contexts({'source_context_overlay': overlay}) == overlay


@pytest.mark.parametrize('heading', ['Algorithm Design', '3 Algorithm Design', 'Algorithm 1: Analysis'])
def test_true_algorithm_section_with_body_prose_is_not_a_float(heading):
    index = body_context_index('# Methods\n\n## ' + heading + '\n\nWe analyze convergence.')
    assert index['spans'][-1]['heading_path'][-1] == heading
    assert index['spans'][-1]['kind'] == 'body_text'


def test_ambiguous_excerpt_is_not_assigned_a_guessed_context():
    state = source_state()
    state['raw_text'] += '\n\nnon-vacant parcels across the city.'
    assert evidence_contexts(state)['evidence']['data']['status'] == 'unknown'


def test_selection_rejects_invalid_ids_reasons_and_new_prose_and_closes_context():
    claims = {c: {'claim_id': c} for c in ('r', 'condition', 'optional', 'unknown')}
    decision = sanitize_selection({'items': [
        {'claim_id': 'r', 'disposition': 'required', 'reason': 'core', 'text': 'forged'},
        {'claim_id': 'condition', 'disposition': 'omit', 'reason': 'secondary'},
        {'claim_id': 'optional', 'disposition': 'omit', 'reason': 'redundant'},
        {'claim_id': 'invented', 'disposition': 'required', 'reason': 'core'}]},
        claims, visible=['r'], dependencies=[('r', 'condition')])
    by_id = {i['claim_id']: i for i in decision['items']}
    assert by_id['condition']['disposition'] == 'required'
    assert by_id['optional']['disposition'] == 'omit'
    assert by_id['unknown'] == {'claim_id': 'unknown', 'disposition': 'optional', 'reason': 'unclassified'}
    assert 'invented' not in by_id and 'text' not in by_id['r']


def test_curator_does_not_resurrect_intentional_omissions_or_unclassified_missing_modules():
    claims = {c: {'claim_id': c, 'section_id': c, 'text': c} for c in ('main', 'dataset', 'missing')}
    raw = {'spatial_content_plan': {'sections': [{'section_id': 'main', 'claim_ids': ['main']}]},
           'editorial_selection': {'items': [{'claim_id': 'dataset', 'disposition': 'omit', 'reason': 'secondary'}]}}
    board = GroundedCurator()._materialize(raw, claims, {}, {}, family_mode=True)
    assert [s['claim_ids'] for s in sections(board)] == [['main']]
    assert {i['claim_id'] for i in board['editorial_selection']['items']} == set(claims)
    # The independent classic route retains its legacy contract.
    classic = GroundedCurator()._materialize(raw, claims, {}, {}, family_mode=False)
    assert {c for s in sections(classic) for c in s['claim_ids']} == set(claims)


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f: f.family_id)
def test_optional_data_may_be_omitted_without_completion_resurrection_for_every_family(family):
    state, board = study()
    for section in state['narrative_plan']['sections']:
        section['required_evidence_ids'] = []
    bank = {c['claim_id']: c for c in state['verified_claims']['claims']}
    board['editorial_selection'] = sanitize_selection({'items': [
        {'claim_id': cid, 'disposition': 'omit', 'reason': 'secondary'} for cid in ('d1', 'd2')]}, bank)
    result, audit = prepare_structure(board, state, family)
    assert not audit['unresolved_section_ids']
    assert all('d1' not in s['claim_ids'] and 'd2' not in s['claim_ids'] for s in sections(result))
    restored = source_for_fit(board, result, state, include_omitted_modules=True)
    assert all('d1' not in s['claim_ids'] and 'd2' not in s['claim_ids'] for s in sections(restored))
    state['story_board'] = restored
    assert all(root_allowed(restored, state, c) for s in sections(restored)
               for c in existing_module_candidates(state, restored, s['section_id']))


def test_new_dataset_mention_does_not_certify_principal_contribution():
    state, board = study()
    claim = next(c for c in state['verified_claims']['claims'] if c['claim_id'] == 'd1')
    claim['text'] = 'We introduce a new dataset.'
    assert not contribution_roots(next(s for s in sections(board) if s['section_id'] == 'd'), state)


def test_mixed_source_is_split_by_claim_function_and_refill_keeps_each_owner():
    state, board = study()
    context = {'status': 'located_body', 'section_type': 'evaluation', 'body_start_char': 100,
               'heading_path': ['Experiments']}
    state['source_context_overlay'] = {'version': 'body_context_v1', 'evidence': {'d1e': context, 'd2e': context}}
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    data['editorial']['items'][0]['kind'] = 'method'
    data['editorial']['module_purpose'] = 'supporting'
    result, audit = prepare_structure(board, state, FAMILIES[0])
    by_id = {s['section_id']: s for s in sections(result)}
    assert 'd1' in by_id['m']['claim_ids'] and 'd2' in by_id['r']['claim_ids']
    assert len(audit['attributions']) == 2
    fitted = deepcopy(result)
    by_id = {s['section_id']: s for s in sections(fitted)}
    for owner, cid in [('m', 'd1'), ('r', 'd2')]:
        index = by_id[owner]['claim_ids'].index(cid)
        by_id[owner]['claim_ids'].pop(index); by_id[owner]['text_content'].pop(index)
    restored = source_for_fit(board, fitted, state)
    by_id = {s['section_id']: s for s in sections(restored)}
    assert 'd1' in by_id['m']['claim_ids'] and 'd2' not in by_id['m']['claim_ids']
    assert 'd2' in by_id['r']['claim_ids'] and 'd1' not in by_id['r']['claim_ids']


def test_context_and_task_definition_can_combine_but_research_insight_cannot():
    state, board = study()
    problem, method = sections(board)[:2]
    method['editorial']['items'][0]['kind'] = 'definition'
    state['narrative_plan']['sections'][1].update(narrative_role='insight', presentation_function='task_definition')
    assert context_pair(problem, method, state)
    spec = spec_for(board, left=['p', 'm'], center=['r'], right=['d', 'c'])
    merged = _merge_thin(board, spec, state, FAMILIES[0])
    assert merged and sections(merged[0])[0]['section_title'] == 'Research Problem'
    state['narrative_plan']['sections'][1]['presentation_function'] = 'research_insight'
    method['editorial']['items'][0]['kind'] = 'interpretation'
    assert not context_pair(problem, method, state)


def test_future_registration_requires_explicit_grouping_decision():
    with pytest.raises(ValueError, match='explicit allow_module_grouping'):
        LayoutFamily('new', 'New', 'New', FAMILIES[0].zones, ('general',))
    for enabled in (True, False):
        family = LayoutFamily('new', 'New', 'New', FAMILIES[0].zones, ('general',),
                              contract=FamilyContract(allow_module_grouping=enabled))
        assert family.contract.allow_module_grouping is enabled


def test_shared_x_boundary_preserves_gutters_bounds_and_hero_prominence():
    zones = deepcopy(list(FAMILIES[3].zones))
    candidate = {'layout_spec': {'zones': zones}, 'exact_bottom_gaps': {},
                 'exact_utilization': {zones[0]['zone_id']: .97, zones[1]['zone_id']: .65, zones[2]['zone_id']: .95}}
    choices = boundary_options(candidate, 30)
    assert choices and len(choices) <= 4
    for _, changed, _, _ in choices:
        assert [(z['y'], z['height']) for z in changed] == [(z['y'], z['height']) for z in zones]
        assert sum(z['width'] for z in changed) == pytest.approx(sum(z['width'] for z in zones))
        assert min(z['x'] for z in changed) == 0
        assert max(z['x'] + z['width'] for z in changed) == pytest.approx(1)
        hero = next(z for z in changed if z['role'] == 'hero')
        assert hero['width'] >= max(z['width'] for z in changed)


def test_space_reference_is_not_the_highest_scalar_content_score():
    sparse = {'exact_score': 1, 'worst_zone_utilization': .65,
              'composition_whitespace': {'largest_empty_rectangle_fraction': .16, 'maximum_terminal_bottom_gap_inches': 9}}
    balanced = {'exact_score': .9, 'worst_zone_utilization': .95,
                'composition_whitespace': {'largest_empty_rectangle_fraction': .04, 'maximum_terminal_bottom_gap_inches': 1}}
    assert selection_reference([sparse, balanced]) is balanced


def test_located_intro_previews_cannot_outvote_primary_body_results():
    from src.layout.presentation_policy import ordered_plan
    text = '# Introduction\n\nPreview one.\n\nPreview two.\n\n# Methods\n\nPolicy.\n\n# Results\n\nActual finding.'
    state = {'raw_text': text, 'evidence_bank': {'items': [
        {'evidence_id': eid, 'source_excerpt': excerpt, 'source': {'section_id': sid, 'section_name': sid}}
        for eid, excerpt, sid in [('a', 'Preview one.', 'Introduction'), ('b', 'Preview two.', 'Introduction'),
                                  ('m', 'Policy.', 'Methods'), ('r', 'Actual finding.', 'Results')]]},
        'narrative_plan': {'sections': [
            {'section_id': 'r', 'narrative_role': 'results', 'evidence_ids': ['a', 'b', 'r']},
            {'section_id': 'm', 'narrative_role': 'method', 'evidence_ids': ['m']}]}}
    plan = ordered_plan(state)
    assert plan['m']['source_order'] < plan['r']['source_order']


def test_malformed_selection_labels_are_ignored_without_destroying_valid_decisions():
    decision = sanitize_selection({'items': [
        {'claim_id': 'a', 'disposition': ['omit'], 'reason': 'secondary'},
        {'claim_id': 'a', 'disposition': 'required', 'reason': 'core'},
        {'claim_id': 'b', 'disposition': 'omit', 'reason': ['secondary']}]},
        {'a': {'claim_id': 'a'}, 'b': {'claim_id': 'b'}})
    assert decision['items'][0] == {'claim_id': 'a', 'disposition': 'required', 'reason': 'core'}
    assert decision['items'][1]['disposition'] == 'optional'


def test_routine_data_with_a_table_is_still_auxiliary_and_moves_the_table_once():
    state, board = study()
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    data['visual_assets'] = [{'visual_id': 'table_1'}]
    result, audit = prepare_structure(board, state, FAMILIES[0])
    assert audit['merges'] == [{'section_id': 'd', 'into_section_id': 'm'}]
    assert [v['visual_id'] for s in sections(result) for v in s['visual_assets']] == ['table_1']


def test_ambiguous_visual_owner_does_not_duplicate_a_mixed_source_visual():
    state, board = study()
    data = next(s for s in sections(board) if s['section_id'] == 'd')
    data['visual_assets'] = [{'visual_id': 'table_1'}]
    data['editorial']['module_purpose'] = 'supporting'
    data['editorial']['items'][0]['kind'] = 'method'
    context = {'status': 'located_body', 'section_type': 'evaluation', 'body_start_char': 100, 'heading_path': ['Experiments']}
    state['source_context_overlay'] = {'version': 'body_context_v1', 'evidence': {'d1e': context, 'd2e': context}}
    result, audit = prepare_structure(board, state, FAMILIES[0])
    assert audit['unresolved_section_ids'] == ['d'] and not audit['merges']
    assert [v['visual_id'] for s in sections(result) for v in s['visual_assets']] == ['table_1']
