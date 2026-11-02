"""Finite original-source editorial loop, actual-family fitting and coherent freeze."""
from copy import deepcopy
from pathlib import Path
import json
import time

from src.workflow.source_document import (VERSION, SourceOutputError, SourceProtocolError, SourceInterrupted,
                                        check_stop, source_material)
from src.workflow.source_editorial import (normalize_candidate, install_candidate,
    make_board, family_material, load_prompt, agent_for, missing_obligations)
from src.workflow.source_reading import (READING_SCHEMA, READING_INSTRUCTIONS, draft_preview,
                                        reading_context, check_reading_review)
from src.workflow.source_requests import SourceRequests, object_schema, STRING, STRINGS, save, read
from src.workflow.source_verification import verify_candidate, assert_verified
from src.layout.repair_budget import sample_ledger, charge_round
from utils.persistence import digest, _atomic_json

from src.workflow.source_edits import edit_schema, merge_patch, bound_reading, edit_task
from src.workflow.source_space import editorial_space


def clone(state):
    # Scientific drafts are isolated; accounting and stop channels are shared.
    result = deepcopy(state)
    for key in ('tokens', 'timing_metrics', '_force_stop_requested'):
        if key in state:
            result[key] = state[key]
    return result


def _fit(state, *, draft, physical_baseline=None):
    from src.agents.layout_agent import LayoutAgent
    from src.agents.color_agent import ColorAgent
    from src.agents.section_title_designer import SectionTitleDesigner
    from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError
    from src.layout.attempt_inputs import save_layout_inputs
    from src.layout.families import LayoutFamilyRegistry
    view = dict(state)
    view['draft_layout_mode'] = draft
    if draft:
        view['poster_claims'] = deepcopy(state['poster_claims'])
        for entry in view['poster_claims']['claims']:
            entry['verified'] = False
    view['styling_interfaces'] = view.get('styling_interfaces') or {}
    board = make_board(view)
    view['story_board'] = board
    config = deepcopy(state['critic_config'])
    config.setdefault('explore_layout', {})['minimum_sections'] = 1
    view['critic_config'] = config
    if not view.get('color_scheme'):
        color = ColorAgent()
        view['color_scheme'] = color._add_contrast_color(color._generate_color_scheme('#1E3A8A'))
    view['section_title_design'] = SectionTitleDesigner()._generate_colorblock_design(board, view['color_scheme'])
    layout_request = state.get('source_layout_requests') or {'section_to_zone': [], 'variant_id': ''}
    view['layout_revision_constraints'] = {'must_retain_claim_ids': [c['claim_id'] for c in state['poster_claims']['claims']],
        'section_to_zone': {r['module_id']: r['zone_id'] for r in layout_request['section_to_zone']}}
    options = family_material(state)['variants']
    selected_variant = next((v for v in options if v['variant_id'] == layout_request['variant_id']), None)
    fixed_zones = deepcopy(selected_variant['zones']) if selected_variant else None
    if physical_baseline is not None:
        fixed_zones = deepcopy(physical_baseline[1]['zones'])
        view['layout_revision_constraints'].update(
            section_to_zone={sid:z['zone_id'] for z in fixed_zones for sid in z.get('section_ids', [])},
            must_retain_visual_ids=[v for m in state['source_candidate']['modules'] for v in m['visual_ids']])
    key = digest({'candidate': state['source_candidate'], 'draft': draft,
                  'family': state['sample_family'], 'layout_request': layout_request,
                  'physical_baseline_spec': physical_baseline[1] if physical_baseline is not None else None})
    root = Path(state['sample_preparation_dir'])/'source/fits'/key
    view['iteration_context'] = {**state['iteration_context'], 'attempt_diagnostics_dir': str(root)}
    save_layout_inputs(view, board, LayoutFamilyRegistry().get(state['sample_family']['family']))
    try:
        result = fit_family_layout(LayoutAgent(), board, view, state['sample_family']['family'],
                                  config=config, fixed_zones=fixed_zones)
        # Fitting can select geometry; it cannot silently edit authored text/labels/titles.
        expected = {s['section_id']: s for s in board['spatial_content_plan']['sections']}
        actual = result[0]['spatial_content_plan']['sections']
        if len(actual) != len(expected) or {s['section_id'] for s in actual} != expected.keys():
            raise SourceOutputError('Physical fit silently omitted an authored module')
        for section in actual:
            before = expected[section['section_id']]
            if any(section.get(k) != before.get(k) for k in ('section_title', 'claim_ids', 'text_content')):
                raise SourceOutputError('Physical fit changed authored scientific text')
        save(root/'result.json', {'input_digest': key, 'draft_only': draft, 'result': tuple(result)})
        return result, None
    except LayoutFeasibilityError as exc:
        save(root/'failure.json', {'input_digest': key, 'report': exc.report, 'draft_only': draft})
        return None, exc.report


def feedback_for(result=None, failure=None):
    from src.workflow.joint_preparation import _feedback
    if failure:
        return _feedback(failure)
    report = result[2]
    return {'zone_utilization': report.get('zone_utilization'), 'exact_bottom_gaps': report.get('exact_bottom_gaps'),
        'composition_whitespace': report.get('composition_whitespace'),
        'module_diagnostics': (report.get('content_quality_hints') or {}).get('module_diagnostics'),
        'completion_targets': (report.get('content_quality_hints') or {}).get('completion_targets')}


def _layout_requests(raw, state, candidate, before, revision):
    brief = family_material(state)
    variants = {v['variant_id']: v for v in brief['variants']}
    if raw['variant_id'] and raw['variant_id'] not in variants:
        raise SourceOutputError('Requested geometry is not a generated legal family variant')
    ids = {m['module_id'] for m in candidate['modules']}
    allowed_zones = {z['zone_id'] for v in brief['variants'] for z in v['zones']}
    requests = raw['section_to_zone']
    if (len(requests) > 2 or len({r['module_id'] for r in requests}) != len(requests) or
            any(r['module_id'] not in ids or r['zone_id'] not in allowed_zones for r in requests)):
        raise SourceOutputError('Invalid or excessive local module placement request')
    before_requests = state.get('source_layout_requests') or {'section_to_zone': [], 'variant_id': ''}
    old_pins = {r['module_id']:r['zone_id'] for r in before_requests['section_to_zone']}
    new_pins = {r['module_id']:r['zone_id'] for r in requests}
    changed = {mid for mid in old_pins.keys()|new_pins.keys() if old_pins.get(mid) != new_pins.get(mid)}
    old_ids = {m['module_id'] for m in before['modules']}
    if (len(set(revision['old_modules']) | (changed & old_ids)) > 2 or
            len(set(revision['new_modules']) | (changed & ids)) > 2):
        raise SourceOutputError('Placement and prose jointly exceed two-module edit scope')
    return deepcopy(raw)


def edit_candidate(state, feedback, phase, result=None):
    check_stop(state)
    if result is not None and state.get('vision_model') is None:
        raise SourceOutputError('Actual visual reading requires a configured vision-capable model')
    preview = draft_preview(state, result) if result else None
    board = result[0] if result else make_board({**state, 'draft_layout_mode': not bool(state.get('verification_passed'))})
    visual_context = (preview['reading_context'] if preview else
        reading_context(state, board, {}, [], None, state['source_candidate']['candidate_id']))
    brief = family_material(state)
    space = editorial_space(state,brief,result)
    payload = {'phase': phase, 'original': source_material(state), 'story': state['source_narrative_plan'],
        'whole_candidate': state['source_candidate'], 'family': family_material(state),
        'actual_layout': result[1] if result else None, 'feedback': feedback,
        'editing_space': space,
        'reading_input': visual_context, 'previous_layout_requests': state.get('source_layout_requests') or
            {'section_to_zone': [], 'variant_id': ''},
        'limits': {'affected_old_modules': 2, 'affected_new_modules': 2}}
    from src.workflow.source_document import paragraph_hints
    reading_instructions = (READING_INSTRUCTIONS if preview else
        'No image is supplied. Edit measured capacity or source defects now. Do not output a reading review.')
    task = edit_task(state,feedback,phase,space)
    prompt = (load_prompt('source_balancer.txt')+'\n'+reading_instructions+'\nINPUT:\n'+
        json.dumps(paragraph_hints(payload, state['source_document']), ensure_ascii=False, sort_keys=True)+
        '\nCURRENT EDIT TASK (execute on the visible poster, not the paper):\n'+json.dumps(task,ensure_ascii=False,sort_keys=True))
    key = digest(prompt)
    journal = SourceRequests(state, f'source/edits/{key}', prompt, edit_schema(preview is not None,phase),
        vision=preview is not None, images=[preview['png']] if preview else [])
    path, ledger = sample_ledger(state)
    if path is None:
        raise ValueError('Source editorial work requires the durable sample-wide budget')
    kind = 'source_edit:'+key
    charged = any(e.get('kind') == kind for e in ledger['charges'])
    if charged:
        if not (journal.root/'request_00.json').exists():
            raise ValueError('Source edit charged but request is missing; refusing automatic resubmission')
    elif not charge_round(state, phase, state['critic_config'].get('capacity_repair', {}), kind=kind):
        raise SourceOutputError('Sample-wide content/layout editing allowance exhausted')
    def validate(value):
        candidate,revision = merge_patch(value,state)
        layout = _layout_requests(value['layout_requests'],state,candidate,state['source_candidate'],revision)
        check_reading_review(bound_reading(value,visual_context),visual_context)
        if phase=='capacity' and candidate==state['source_candidate'] and layout==payload['previous_layout_requests']:
            raise SourceOutputError('Capacity edit returned no actionable content/layout change')
    def before_schema(value):
        if phase=='capacity' and isinstance(value,dict) and value.get('modules')==[]:
            raise SourceOutputError('Capacity edit returned an empty patch; this is no content action, not a format retry')
    raw = journal.call(agent_for(state, 'source_balancer', vision=preview is not None),
        validator=validate,before_schema=before_schema)
    before = deepcopy(state['source_candidate'])
    normalizations = []
    candidate,revision = merge_patch(raw,state,normalizations=normalizations)
    layout = _layout_requests(raw['layout_requests'], state, candidate, before, revision)
    state['source_reading_review'] = {**bound_reading(raw,visual_context), 'version': 'visual_natural_reading_v1',
        'input_context': visual_context, 'preview_png': preview['png'] if preview else None}
    changed = candidate != before or layout != (state.get('source_layout_requests') or {'section_to_zone': [], 'variant_id': ''})
    state['source_reading_review']['applies_to_reviewed_draft_candidate'] = not changed
    state['source_reading_review']['final_image_assessed'] = False
    state['source_candidate_lineage'] = [*(state.get('source_candidate_lineage') or []),
        {'from_candidate': before['candidate_id'], 'to_candidate': candidate['candidate_id'],
         'phase': phase, **revision, 'layout_requests': layout, 'changed': changed}]
    save(journal.root/'normalized.json', {'input_digest': journal.identity, 'candidate': candidate,
        'revision': revision, 'layout_requests': layout, 'reading_review': state['source_reading_review'],
        'presentation_normalizations': normalizations,'editing_space':space,'edit_task':task})
    state['source_layout_requests'] = layout
    if changed:
        install_candidate(state, candidate)
    return state, changed


def align_selected_visuals(state, result):
    owners = {s['section_id']: [v['visual_id'] for v in s['visual_assets']]
              for s in result[0]['spatial_content_plan']['sections']}
    candidate = deepcopy(state['source_candidate'])
    changed = False
    for module in candidate['modules']:
        actual = owners[module['module_id']]
        if not set(actual) <= set(module['visual_ids']):
            raise ValueError('Solver introduced an unauthored original visual')
        if actual != module['visual_ids']:
            removed = [v for v in module['visual_ids'] if v not in actual]
            module['reserve_visual_ids'] = list(dict.fromkeys(module['reserve_visual_ids']+removed))
            module['visual_ids'] = actual
            changed = True
    if changed:
        before = state['source_candidate']['candidate_id']
        candidate = normalize_candidate({'modules': candidate['modules']}, state)
        install_candidate(state, candidate)
        state['source_candidate_lineage'] = [*(state.get('source_candidate_lineage') or []),
            {'phase': 'bounded_physical_visual_selection', 'from_candidate': before,
             'to_candidate': candidate['candidate_id'], 'scientific_status': 'requires_direct_verification'}]
    return state


def converge(state, previous=None):
    # Initial candidate plus at most three charged capacity opportunities. Existing
    # journals replay, so interruption cannot reset budgets or resubmit a response.
    previous = deepcopy(previous if previous is not None else state['source_candidate'])
    for index in range(4):
        check_stop(state)
        state['draft_layout_mode'] = True
        missing = missing_obligations(state['source_candidate'], state)
        if missing:
            candidate = state['source_candidate']
            save(Path(state['sample_preparation_dir'])/'source/completeness'/
                 (candidate['candidate_id']+'.json'), {'input_digest': digest(candidate),
                 'status': 'unverified_incomplete', 'missing_obligations': missing})
            if index == 3:
                raise SourceOutputError('Indispensable meanings still unassigned within finite content edits: '+
                                        json.dumps(missing, ensure_ascii=False))
            state, changed = edit_candidate(state, {'missing_indispensable_meanings': missing,
                'instruction': 'Map an already expressed meaning to its actual module, or add the missing '
                'original-supported explanation. Use existing content-edit limits; keep valid neighbors. '
                'New modules are allowed within this family, not required. Assignment is not semantic approval.'}, 'capacity')
            if not changed:
                raise SourceOutputError('No actionable change for missing indispensable meanings')
            continue
        result, failure = _fit(state, draft=True)
        if failure:
            if index == 3:
                raise SourceOutputError('No physical fit within finite single-family edits')
            state, changed = edit_candidate(state, feedback_for(failure=failure), 'capacity')
            if not changed:
                raise SourceOutputError('No actionable content/layout change for failed fit')
            continue
        state = align_selected_visuals(state, result)
        try:
            proof = verify_candidate(state, state['source_candidate'], previous=previous)
        except SourceProtocolError:
            raise
        except SourceOutputError as exc:
            if index == 3:
                raise
            state['draft_layout_mode'] = True
            state, changed = edit_candidate(state, {'scientific_diagnostic': str(exc)}, 'capacity', result)
            if not changed:
                raise SourceOutputError('Scientific rejection was not corrected') from exc
            continue
        install_candidate(state, state['source_candidate'], verified=proof)
        state['draft_layout_mode'] = False
        result, failure = _fit(state, draft=False, physical_baseline=result)
        if failure:
            if index == 3:
                raise SourceOutputError('Verified final wording did not fit')
            state, changed = edit_candidate(state, feedback_for(failure=failure), 'capacity')
            if not changed:
                raise SourceOutputError('No actionable change after verified fit failure')
            continue
        assert_verified(state, result[0])
        return state, result
    raise SourceOutputError('Editorial preparation did not converge')


def snapshot_identity(state):
    return digest({'version': VERSION, 'source': state['source_document']['digest'],
        'story': state['source_narrative_plan'], 'candidate': state['source_candidate'],
        'proof': state['source_verification_report'], 'claims': state['verified_claims']})


def source_joint_preparation_node(state):
    from src.layout.measurement_context import measurement_scope
    from utils.model_requests import SampleRequestFailure
    from src.workflow.content_contracts import science_fields
    root = Path(state['sample_preparation_dir'])/'source/joint'
    identity = digest({'version': VERSION, 'paper': state['paper_foundation_digest'],
        'candidate': state['source_candidate'], 'story': state['source_narrative_plan'], 'family': state['sample_family']})
    ready = root/'READY.json'
    if ready.exists():
        state.update(deepcopy(read(ready, identity)['fields']))
        assert_verified(state, state['joint_candidate']['board'])
        return state
    try:
        with measurement_scope(state['critic_config'].get('layout_performance')) as measured:
            state, result = converge(state)
            from src.workflow.source_visuals import restore_source_visuals
            state, result = restore_source_visuals(state, result)
            baseline, baseline_result = clone(state), deepcopy(tuple(result))
            audit = {'version': VERSION, 'status': 'reviewed_no_change', 'baseline_candidate': state['source_candidate']['candidate_id']}
            try:
                trial, changed = edit_candidate(clone(state), feedback_for(result), 'quality', result)
                audit['reading_review'] = deepcopy(trial.get('source_reading_review'))
                audit['targets'] = deepcopy((trial.get('source_candidate_lineage') or [{}])[-1])
                if changed:
                    trial, fitted = converge(trial, previous=baseline['source_candidate'])
                    from src.layout.module_repair import space_preserved
                    old_visuals = {v['visual_id'] for s in baseline_result[0]['spatial_content_plan']['sections'] for v in s['visual_assets']}
                    new_visuals = {v['visual_id'] for s in fitted[0]['spatial_content_plan']['sections'] for v in s['visual_assets']}
                    if not old_visuals <= new_visuals or not space_preserved(baseline_result[2], fitted[2]):
                        raise SourceOutputError('Quality trial regressed visible assets or measured space')
                    from src.layout.region_merges import geometry_record
                    if geometry_record(baseline_result[1]['zones']) != geometry_record(fitted[1]['zones']):
                        from src.layout.whitespace import no_added_whitespace
                        if not no_added_whitespace(baseline_result[2]['composition_whitespace'],
                                                   fitted[2]['composition_whitespace']):
                            raise SourceOutputError('Quality geometry edit increased measured whitespace')
                    def surface(candidate):
                        return [(m['title'], m['presentation_style'], m['visual_ids'],
                            [(e['text'],e['display_label'],e['step_index'],bool(e['parent_item_id'])) for e in m['entries']])
                            for m in candidate['modules']]
                    visible_change = surface(baseline['source_candidate']) != surface(trial['source_candidate'])
                    before_gaps,after_gaps = baseline_result[2].get('exact_bottom_gaps') or {},fitted[2].get('exact_bottom_gaps') or {}
                    space_gain = any(after_gaps.get(z,gap) < gap-.05 for z,gap in before_gaps.items())
                    route_change = (trial.get('source_reading_review') or {}).get('status') in {'needs_revision','ambiguous'} and fitted[1] != baseline_result[1]
                    if not (visible_change or space_gain or route_change):
                        raise SourceOutputError('Quality trial changed only citations/identities or had no observable gain')
                    audit['gain_basis'] = {'visible_content_or_hierarchy_change':visible_change,
                        'measured_space_gain':space_gain,'reading_change_requires_final_review':route_change}
                    state, result = trial, fitted
                    audit['status'] = 'adopted'
                else:
                    state = trial
            except SourceOutputError as exc:
                # A rejected quality edit never replaces the scientifically/physically
                # valid baseline. The charge and full raw trial remain durable.
                audit.update(status='rejected', reason=str(exc))
                state, result = baseline, baseline_result
            board, spec, report = result
            state['verified_module_board'] = deepcopy(board)
            state['draft_layout_mode'] = False
            state['source_quality_report'] = audit
            state['module_body_report'] = {'version': 'sample_body_source_v1', 'visible_claim_ids': [
                c for s in board['spatial_content_plan']['sections'] for c in s['claim_ids']],
                'visible_words': sum(len(c['text'].split()) for c in state['verified_claims']['claims']),
                'covered_obligation_ids': state['source_verification_report']['covered_obligation_ids']}
            state['visual_curation_report'] = {'version': VERSION,
                'available_visual_ids': sorted(state['source_document']['assets']),
                'curator_selected_visual_ids': sorted(v for m in state['source_candidate']['modules'] for v in m['visual_ids']),
                'final_visible_visual_ids': sorted(v['visual_id'] for s in board['spatial_content_plan']['sections'] for v in s['visual_assets'])}
            assert_verified(state, board)
            state['joint_candidate'] = {'version': VERSION, 'status': 'verified_feasible',
                'family_id': state['sample_family']['family'], 'science_digest': snapshot_identity(state),
                'board': deepcopy(board), 'layout_spec': deepcopy(spec), 'fit_report': deepcopy(report),
                'edit_budget_digest': digest(sample_ledger(state)[1]),
                'visual_curation_report': deepcopy(state['visual_curation_report'])}
            state['joint_candidate']['digest'] = digest(state['joint_candidate'])
            state['layout_performance_report'] = measured.report('completed')
            save(ready, {'input_digest': identity, 'fields': science_fields(state)})
            for key in ('source_candidate','source_verification_report','source_reading_review','source_quality_report',
                        'source_candidate_lineage','module_body_report','verified_claims','joint_candidate'):
                _atomic_json(Path(state['output_dir'])/'content'/(key+'.json'), state.get(key))
    except SourceInterrupted:
        state['_joint_interrupted'] = True
    except (SourceOutputError, SampleRequestFailure) as exc:
        from src.workflow.sample_errors import record_sample_error
        record_sample_error(state, exc, 'source_editorial_preparation_failed', output_error=isinstance(exc, SourceOutputError))
        state['verification_passed'] = False
        state.setdefault('errors', []).append(str(exc))
        state.setdefault('sample_failure', {'kind': 'source_editorial_preparation_failed', 'reason': str(exc)})
        _atomic_json(root/'failure.json', {'error': str(exc), 'kind': type(exc).__name__})
    return state


def install_source_candidate_node(state):
    assert_verified(state)
    candidate = deepcopy(state.get('joint_candidate') or {})
    expected = candidate.pop('digest', None)
    if (state.get('draft_layout_mode') or expected != digest(candidate) or
            candidate.get('science_digest') != snapshot_identity(state) or
            candidate.get('edit_budget_digest') != digest(sample_ledger(state)[1]) or
            candidate.get('status') != 'verified_feasible' or
            candidate.get('family_id') != state['sample_family']['family'] or
            state['iteration_context'].get('layout_family') != candidate['family_id']):
        raise ValueError('Source candidate freeze identity mismatch')
    assert_verified(state, candidate['board'])
    state.update(story_board=deepcopy(candidate['board']), optimized_story_board=deepcopy(candidate['board']),
        layout_spec=deepcopy(candidate['layout_spec']), layout_feasibility_report=deepcopy(candidate['fit_report']),
        visual_curation_report=deepcopy(candidate['visual_curation_report']))
    return state


def compile_source_layout_node(state):
    from src.agents.layout_agent import LayoutAgent
    from src.layout.editorial import _emphasize
    from src.layout.feasibility import validate_compiled_layout
    state = install_source_candidate_node(state)
    _emphasize(state['optimized_story_board'], state, state['layout_spec'])
    assert_verified(state, state['optimized_story_board'])
    state['story_board'] = deepcopy(state['optimized_story_board'])
    state['source_reading_status'] = {'status': 'awaiting_final_image_review',
        'preview_is_not_final_review': True}
    agent = LayoutAgent()
    state = agent(state, mode='final')
    report = validate_compiled_layout(state.get('design_layout') or [], state['layout_spec'], state,
        poster_margin=agent.poster_margin, title_height_fraction=agent.title_height_fraction)
    state['layout_preflight_report'] = report
    state['layout_preflight_failed'] = not report['passed']
    if not report['passed']:
        state.setdefault('errors', []).append('Frozen source candidate failed final physical preflight')
    return state
