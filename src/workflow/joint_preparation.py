"""Single-family draft/space/science convergence; drafts never become verified banks."""
from copy import deepcopy
from pathlib import Path
import json

from src.agents.layout_agent import LayoutAgent
from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError, validate_compiled_layout
from src.layout.repair_budget import sample_ledger, charge_round
from src.workflow.module_planning_requests import ModulePlanningRequests
from src.workflow.sample_modules import build_module_board, sample_claim_verifier_node
from src.workflow.sample_module_writing import verification_source_context
from utils.persistence import _atomic_json, digest, read_json
from utils.model_requests import SampleRequestFailure

VERSION = 'joint_preparation_v2'


class JointInterrupted(Exception):
    """Cooperative stop, never an official failed sample."""


def check_stop(state):
    callback = state.get('_force_stop_requested')
    if callback and callback():
        raise JointInterrupted()


class JointContentFailure(ValueError):
    """A bounded sample outcome, distinct from corrupt state or programming errors."""


def _save(path, payload):
    _atomic_json(path, {'payload': payload, 'digest': digest(payload)})


def _read(path, identity):
    envelope = read_json(path)
    payload = envelope['payload']
    if envelope.get('digest') != digest(payload) or payload.get('input_digest') != identity:
        raise ValueError('Joint preparation checkpoint identity/digest mismatch')
    return payload


def draft_protection(state):
    """Provisional ID selection only; citation is NEVER a scientific coverage verdict."""
    claims = state['poster_claims']['claims']
    protected = set()
    if state.get('verified_module_board'):
        from src.layout.editorial_selection import required_roots
        protected.update(required_roots(state['verified_module_board'], state))
    for module in state['sample_module_plan']['modules']:
        body = [c for c in claims if c['display_module_id'] == module['module_id']]
        for eid in module['required_evidence_ids']:
            options = [c for c in body if eid in c['evidence_ids']]
            if options:
                protected.add(min(options, key=lambda c: (len(c['text']), c['claim_id']))['claim_id'])
    return protected


def _fit(state, *, draft):
    from src.layout.measurement_context import current_context, measurement_scope
    if current_context() is None:
        with measurement_scope(state['critic_config'].get('layout_performance')) as measured:
            try:
                return _fit(state, draft=draft)
            finally:
                state['layout_performance_report'] = measured.report('completed')
    view = dict(state)
    view['draft_layout_mode'] = draft
    claims = state['poster_claims']['claims'] if draft else state['verified_claims']['claims']
    if draft:
        board = build_module_board(view, claims, draft_protection(view))
    else:
        board = deepcopy(state['verified_module_board'])
    seed_visual_candidate(board, view)
    state['visual_curation_report'] = deepcopy(view['visual_curation_report'])
    state['_joint_visual_source_board'] = deepcopy(board)
    # Only explicit same-module reserves may be probed later; they are not initial fit inputs.
    modules = {m['module_id']: m for m in state['sample_module_plan']['modules']}
    for section in state['_joint_visual_source_board']['spatial_content_plan']['sections']:
        current = {v['visual_id'] for v in section['visual_assets']}
        section['visual_assets'].extend({'visual_id': vid} for vid in modules[section['section_id']].get('reserve_visual_ids', []) if vid not in current)
    if state.get('_joint_quality_required_ids'):
        view['layout_revision_constraints'] = {**(view.get('layout_revision_constraints') or {}),
            'must_retain_claim_ids': state['_joint_quality_required_ids'],
            'must_retain_visual_ids': state.get('_joint_quality_visual_ids', [])}
    config = deepcopy(state['critic_config'])
    # The story determines its number of modules. Family capacity remains hard.
    config.setdefault('explore_layout', {})['minimum_sections'] = 1
    view['styling_interfaces'] = view.get('styling_interfaces') or {}
    if not view.get('color_scheme'):
        from src.agents.color_agent import ColorAgent
        palette = ColorAgent()
        view['color_scheme'] = palette._add_contrast_color(palette._generate_color_scheme('#1E3A8A'))
    from src.agents.section_title_designer import SectionTitleDesigner
    view['section_title_design'] = SectionTitleDesigner()._generate_colorblock_design(board, view.get('color_scheme') or {})
    view['critic_config'] = config
    key = digest({'board':board, 'draft':draft, 'claims':claims, 'family':state['sample_family'],
                  'paper':state['paper_foundation_digest'], 'seed':state['iteration_context'].get('random_seed')})
    directory = Path(state['output_dir'])/'joint/fit_inputs'/key
    view['iteration_context'] = {**state['iteration_context'], 'attempt_diagnostics_dir':str(directory)}
    from src.layout.attempt_inputs import save_layout_inputs
    from src.layout.families import LayoutFamilyRegistry
    save_layout_inputs(view, board, LayoutFamilyRegistry().get(state['sample_family']['family']))
    try:
        result = fit_family_layout(LayoutAgent(), board, view, state['sample_family']['family'], config=config)
        _save(directory/'result.json', {'input_digest':key, 'unverified_physical_draft':draft, 'result':tuple(result)})
        return result, None
    except LayoutFeasibilityError as exc:
        _save(directory/'failure.json', {'input_digest':key, 'unverified_physical_draft':draft, 'report':exc.report})
        return None, exc.report


def _feedback(report):
    """Stable substantive feedback, excluding clocks, caches and search timings."""
    from src.workflow.sample_curation import diagnostic_pressure
    return {'reason_code': report.get('reason_code'), 'failure_stage': report.get('failure_stage'),
        'pressure': [{k: r.get(k) for k in ('section_id', 'zone_id', 'estimated_used_in',
            'zone_limit_in', 'option_claim_ids')} for r in diagnostic_pressure(report)],
        'module_loads': report.get('module_loads') or [],
        'structure': report.get('presentation_preparation') or {},
        'completion_targets': (report.get('content_quality_hints') or {}).get('completion_targets') or []}


def edit_targets(state, feedback, touched):
    modules = state['sample_module_plan']['modules']
    candidates = state['poster_claims']['claims']
    loads = {m['module_id']: sum(len(c['text'].split()) for c in candidates
                                if c['display_module_id'] == m['module_id']) for m in modules}
    options = structure_merge_options(state) if feedback.get('structure', {}).get('unresolved_section_ids') else []
    if options:
        source, owner = min(options, key=lambda pair: (touched.get(pair[0],0), -loads[pair[0]], pair))
        return [source, owner]
    required = set((feedback.get('verification') or {}).keys())
    quality = {r['section_id']: r for r in feedback.get('quality_targets') or []}
    completion = {r.get('section_id'): r for r in feedback.get('completion_targets') or []}
    if quality or completion:
        # Missing explanation and actual severity take precedence over prose length.
        def rank(module):
            mid = module['module_id']; row = quality.get(mid, completion.get(mid, {}))
            return (mid not in required, mid not in quality and mid not in completion,
                touched.get(mid, 0), 'evidence_summary_list' not in row.get('reasons', []),
                -float(row.get('bottom_gap', 0)), float(row.get('utilization', 1)), mid)
        return [m['module_id'] for m in sorted(modules, key=rank)[:2]]
    # Give large untouched modules a turn, rather than following a tiny early beam miss.
    order = sorted(modules, key=lambda m: (m['module_id'] not in required,
        bool(completion) and m['module_id'] not in completion,
        touched.get(m['module_id'], 0), -loads[m['module_id']], m['module_id']))
    return [m['module_id'] for m in order[:2]]


def normalize_editorial_revision(raw, state, targets, phase='capacity'):
    """Keep roots and local dependencies; allow explicit, audited optional omission."""
    from utils.evidence_utils import validate_claim_numbers, normalize_formula_multiplication
    from src.workflow.sample_module_writing import clean_internal_evidence_markers, normalize_shared_percentage_ranges
    rows = raw.get('modules') if isinstance(raw, dict) else None
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows) or
            [r.get('module_id') for r in rows] != targets):
        raise JointContentFailure('Editorial revision must return exactly the requested modules in order')
    old = state['poster_claims']['claims']
    protected = draft_protection(state)
    evidence = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    by_module = {m['module_id']: m for m in state['sample_module_plan']['modules']}
    updated, omitted, additions = {}, [], []
    updates = {}
    merges = [(r['module_id'], r['merge_into_module_id']) for r in rows if r.get('merge_into_module_id')]
    if merges and (len(merges) != 1 or merges[0] not in structure_merge_options(state) or
                   any(mid not in targets for mid in merges[0])):
        raise JointContentFailure('Module merge needs an explicitly compatible source/owner pair within this edit')
    for row in rows:
        mid = row['module_id']; module = by_module[mid]
        update = row.get('presentation', {})
        if not isinstance(update, dict) or set(update)-{'module_purpose', 'presentation_style'}:
            raise JointContentFailure('Invalid local presentation update')
        if ('module_purpose' in update and update['module_purpose'] not in {'primary', 'context', 'supporting'} or
                'presentation_style' in update and update['presentation_style'] not in {'plain', 'topics', 'steps'}):
            raise JointContentFailure('Unknown local presentation value')
        updates[mid] = update
        original = [c for c in old if c['display_module_id'] == mid]
        entries = row.get('claims')
        if (not isinstance(entries, list) or any(not isinstance(r, dict) for r in entries) or
                [r.get('source_claim_id') for r in entries] != [c['claim_id'] for c in original]):
            raise JointContentFailure('Every original expression needs exactly one ordered revision/omission row')
        for before, entry in zip(original, entries):
            cid = before['claim_id']
            if entry.get('omit') is True:
                if cid in protected or not isinstance(entry.get('reason'), str) or not entry['reason'].strip():
                    raise JointContentFailure('Cannot omit a protected expression or omit without a reason')
                omitted.append({'claim_id': cid, 'reason': entry['reason']})
                continue
            text, ids = entry.get('text'), entry.get('evidence_ids')
            if (not isinstance(text, str) or not text.strip() or not isinstance(ids, list) or not ids or
                    any(not isinstance(e, str) or e not in module['available_evidence_ids'] for e in ids)):
                raise JointContentFailure('Revision has empty text or foreign evidence')
            original_units = set(before['source_plan_unit_ids'])
            allowed_sources = {e for u in state['narrative_plan']['sections'] if u['section_id'] in original_units for e in u['evidence_ids']}
            if not set(ids) <= allowed_sources:
                raise JointContentFailure('Revision cannot reassign an original scientific root to a different source unit')
            try:
                text, notes = clean_internal_evidence_markers(text.strip(), ids, evidence)
            except ValueError as exc:
                raise JointContentFailure(str(exc)) from exc
            text = normalize_formula_multiplication(text)
            text, range_notes = normalize_shared_percentage_ranges(text, ids, evidence)
            notes.extend(range_notes)
            if not validate_claim_numbers(text, ids, evidence)[0]:
                raise JointContentFailure('Revision contains a number absent from its cited evidence')
            claim = deepcopy(before)
            for key in ('support_map', 'covered_required_evidence_ids', 'original_expression',
                        'coverage_format_normalizations', 'repaired'):
                claim.pop(key, None)
            claim.update(text=text, evidence_ids=list(dict.fromkeys(ids)), verified=False, essential=False,
                required_evidence_ids=sorted(set(module['required_evidence_ids']) & set(ids)))
            claim['editorial_revision'] = {'version': 'selective_editorial_v1',
                'original_text': before['text'], 'original_context': before.get('module_context'),
                'required_assertions': module['required_assertions'],
                'original_requires_claim_ids': before.get('requires_claim_ids', []),
                'rule': 'Optional detail may be removed. Preserve indispensable assertions, their scope, conditions, qualifiers, comparison basis and interpretation prerequisites; do not broaden conclusions.'}
            if 'display_label' in entry:
                if not isinstance(entry['display_label'], str):
                    raise JointContentFailure('Invalid extractive display label')
                claim['display_label'] = entry['display_label']
            parent = entry.get('parent_source_claim_id', before.get('parent_claim_id'))
            if parent is not None and not isinstance(parent, str):
                raise JointContentFailure('Support parent must be a local expression ID')
            preceding = [c['claim_id'] for c in original[:original.index(before)]]
            if parent and parent not in preceding:
                raise JointContentFailure('Support parent must be a preceding original expression in this module')
            claim['parent_claim_id'] = parent
            claim['requires_claim_ids'] = list(dict.fromkeys([*before.get('requires_claim_ids', []), *([parent] if parent else [])]))
            if notes: claim['display_normalizations'] = [*claim.get('display_normalizations', []), *notes]
            updated[cid] = claim
        extra = row.get('additional_claims', [])
        if not isinstance(extra, list) or extra and phase != 'quality':
            raise JointContentFailure('Evidence completion is allowed only inside the reserved quality edit')
        if extra:
            from src.workflow.sample_module_writing import normalize_body
            try:
                fresh = normalize_body({'claims': extra}, module, state)
            except (ValueError, TypeError) as exc:
                raise JointContentFailure(str(exc)) from exc
            mapping = {c['claim_id']: f"pc_{mid}_add_{digest({'item': e['item_id'], 'text': c['text']})[:12]}"
                       for c,e in zip(fresh, extra)}
            for claim, entry in zip(fresh, extra):
                claim['claim_id'] = mapping[claim['claim_id']]
                claim['requires_claim_ids'] = [mapping[cid] for cid in claim.get('requires_claim_ids', [])]
                claim['parent_claim_id'] = mapping.get(claim.get('parent_claim_id'))
                parent = entry.get('parent_source_claim_id')
                if parent is not None and not isinstance(parent, str):
                    raise JointContentFailure('Additional explanation parent must be a local expression ID')
                if parent:
                    if parent not in {c['claim_id'] for c in original}:
                        raise JointContentFailure('Additional explanation has a foreign parent')
                    claim['parent_claim_id'] = parent
                    claim['requires_claim_ids'].append(parent)
                claim.update(verified=False, essential=False, essential_suggestion=False,
                    completion_origin={'phase': phase, 'module_id': mid, 'source_evidence_ids': claim['evidence_ids']})
            if len(set(mapping.values())) != len(fresh) or set(mapping.values()) & {c['claim_id'] for c in old}:
                raise JointContentFailure('Duplicate completion expression identity')
            additions.extend(fresh)
    omitted_ids = {r['claim_id'] for r in omitted}
    result = []
    for module in modules_in_order(state):
        result.extend(updated.get(c['claim_id'], deepcopy(c)) for c in old
                      if c['display_module_id'] == module and c['claim_id'] not in omitted_ids)
        result.extend(c for c in additions if c['display_module_id'] == module)
    visible = {c['claim_id'] for c in result}
    for claim in result:
        if not set(claim.get('requires_claim_ids', [])) <= visible:
            raise JointContentFailure('Revision removed a retained expression prerequisite')
        claim['verified'] = False
    refresh_contexts(result)
    state['_joint_omitted_claim_ids'] = sorted(set(state.get('_joint_omitted_claim_ids') or []) | omitted_ids)
    for mid, update in updates.items():
        by_module[mid].update(update)
    if merges:
        merge_module_tasks(state, result, *merges[0])
    return result, omitted


def modules_in_order(state):
    return [m['module_id'] for m in state['sample_module_plan']['modules']]


def refresh_contexts(claims):
    for claim in claims:
        claim['module_context'] = {**(claim.get('module_context') or {}), 'items': [
            {'claim_id': c['claim_id'], 'text': c['text']} for c in claims
            if c['display_module_id'] == claim['display_module_id']]}


def _edit(state, feedback, touched, phase):
    from utils.agent_policy import apply_agent_policy
    from utils.langgraph_utils import LangGraphAgent, extract_json
    if not state['critic_config'].get('capacity_repair', {}).get('enabled', True):
        raise JointContentFailure('Content/layout editing disabled by policy')
    targets = edit_targets(state, feedback, touched)
    modules = [next(m for m in state['sample_module_plan']['modules'] if m['module_id'] == mid) for mid in targets]
    bank = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    evidence = {m['module_id']: [bank[e] for e in m['available_evidence_ids']] for m in modules}
    data = {'phase': phase, 'family_capacity': state['family_capacity'], 'feedback': feedback,
        'merge_options': structure_merge_options(state),
        'modules': modules, 'whole_poster': state['poster_claims']['claims'], 'targets': targets,
        'evidence': evidence, 'context': {mid: verification_source_context(state, rows) for mid, rows in evidence.items()}}
    prompt = ('Revise the requested modules together for this single-family scientific poster. '
        'Write a small number of concise, connected, scannable ideas with necessary explanation. '
        'For capacity, shorten prose and remove only secondary/redundant optional detail; for quality, resolve the diagnosed '
        'missing explanation or whitespace using supplied evidence. Preserve every indispensable assertion, conditions, scope, '
        'metrics, comparison basis and interpretation prerequisites. Do not broaden claims or add unsupported facts. '
        'Structure defects may also update local presentation.module_purpose (primary/context/supporting) or '
        'presentation.presentation_style (plain/topics/steps); scientific source/ownership/dependencies remain unchanged. '
        'Each expression keeps its original source_plan_unit_ids: cite only evidence belonging to those original scientific units. '
        'For a diagnosed ownership/structure failure, one source module may explicitly declare merge_into_module_id '
        'from merge_options, only when source and owner are both targets. Keep every original expression row and root; '
        'the code regroups modules, never merges scientific claim identities. '
        'Existing rows preserve every scientific root. No new modules. '
        'In quality phase only, additional_claims may add useful nonredundant explanation from the target module available evidence. '
        'Each additional item uses item_id,text,evidence_ids,kind,requires_item_ids,parent_item_id,display_label. '
        'An optional parent_source_claim_id links a supporting explanation to an existing earlier local root. '
        'Return only {"modules":[{"module_id":"...","claims":[ '
        '{"source_claim_id":"original ID","text":"...","evidence_ids":["..."]}, '
        '{"source_claim_id":"optional original ID","omit":true,"reason":"..."}],"additional_claims":[]}]}. '
        'Every original expression in each target must occur exactly once, in original order. '
        'Keep the supplied targets order. Do not omit indispensable expressions or retained local prerequisites. '
        'For quality do NOT automatically shorten: synthesize an evidence-summary list into connected explanatory prose, '
        'resolve the reader question, or add missing useful explanation in actual available space. '
        'Supply a short editorial_change reason on each module. Related facts can share an expression but existing roots '
        'and their scientific responsibility remain distinct. Preserve necessary conditions, comparators and qualifiers. '
        'You may set presentation.presentation_style=topics and extractive display_label or a genuine parent_source_claim_id '
        'to create lead/support hierarchy; plain remains valid. Use no visible citation annotations. '
        'Only the requested modules change.\n'+json.dumps(data, ensure_ascii=False))
    check_stop(state)
    key = digest(prompt)
    journal = ModulePlanningRequests(state, prompt, directory=f'joint/edits/{key}')
    path, ledger = sample_ledger(state)
    kind = 'joint_edit:'+key
    charged = any(e.get('kind') == kind for e in ledger['charges'])
    if charged:
        if not (journal.root/'request_00.json').exists():
            raise ValueError('Joint edit charged without saved request; refusing resubmission')
    elif not charge_round(state, phase, state['critic_config'].get('capacity_repair', {}), kind=kind):
        raise JointContentFailure('Sample-wide content/layout editing allowance exhausted')
    agent = LangGraphAgent('Edit concise grounded poster prose within explicit source obligations.',
        apply_agent_policy(state['text_model'], 'claim_writer'), state, 'claim_writer')
    content = journal.request(0, agent, prompt)
    try:
        raw = extract_json(content)
    except (ValueError, TypeError) as exc:
        raise JointContentFailure('Invalid editorial response JSON') from exc
    journal.write('parsed_00.json', parsed=raw)
    revised, omitted = normalize_editorial_revision(raw, state, targets, phase)
    journal.write('revision.json', claims=revised, omitted=omitted, targets=targets)
    if phase == 'quality' or state.get('_joint_quality_required_ids'):
        state['_joint_quality_required_ids'] = [c['claim_id'] for c in revised]
        state['_joint_quality_visual_ids'] = [v['visual_id'] for s in (state.get('verified_module_board') or {}).get('spatial_content_plan', {}).get('sections', []) for v in s['visual_assets']]
    state['_joint_last_edit_targets'] = targets
    state['poster_claims'] = {'claims': revised}
    for mid in targets: touched[mid] = touched.get(mid, 0)+1
    return state


def candidate_identity(state):
    return digest({'version': VERSION, 'paper': state['paper_foundation_digest'],
        'family': state['sample_family'], 'plan': state['sample_module_plan'],
        'claims': state['verified_claims'], 'board': state['verified_module_board']})


def _converge(state, touched):
    for _ in range(5):  # At most three capacity edits; one final verification/refit.
        check_stop(state)
        draft = deepcopy(state)
        draft['poster_claims'] = deepcopy(state['poster_claims'])
        for c in draft['poster_claims']['claims']: c['verified'] = False
        result, failure = _fit(draft, draft=True)
        if failure:
            _atomic_json(Path(state['output_dir'])/'joint/last_fit_failure.json', failure)
            state = _edit(state, _feedback(failure), touched, 'capacity')
            continue
        # Verify the actual selected draft, not an unused candidate bank.
        selected = {cid for s in result[0]['spatial_content_plan']['sections'] for cid in s['claim_ids']}
        state['poster_claims'] = {'claims': [c for c in state['poster_claims']['claims'] if c['claim_id'] in selected]}
        for c in state['poster_claims']['claims']: c['verified'] = False
        refresh_contexts(state['poster_claims']['claims'])
        state['verified_module_board'] = None
        state['joint_verification_feedback'] = None
        previous_dir = state['output_dir']
        verify_dir = Path(previous_dir)/'joint/verification'/digest(state['poster_claims'])[:20]
        state['output_dir'] = str(verify_dir)
        verify_dir.mkdir(parents=True, exist_ok=True)
        try:
            state = sample_claim_verifier_node(state)
        finally:
            state['output_dir'] = previous_dir
        if state.get('_joint_interrupted'):
            raise JointInterrupted()
        check_stop(state)
        if state.get('fatal_generation_error'):
            raise RuntimeError('Scientific verification encountered a system/history failure')
        if state.get('errors'):
            raise JointContentFailure('Scientific verification failed; see saved expression diagnostics')
        feedback = state.get('joint_verification_feedback')
        if feedback:
            state = _edit(state, {'verification': feedback}, touched, 'capacity')
            continue
        result, failure = _fit(state, draft=False)
        if failure:
            state['poster_claims'] = deepcopy(state['verified_claims'])
            state = _edit(state, _feedback(failure), touched, 'capacity')
            continue
        return state, result
    raise JointContentFailure('Single-family preparation did not converge within its edit allowance')


def joint_preparation_node(state):
    from src.layout.measurement_context import measurement_scope
    result = state
    with measurement_scope(state['critic_config'].get('layout_performance')) as measured:
        try:
            result = _prepare_joint(state)
            return result
        finally:
            report = measured.report('failed' if result.get('errors') else 'completed')
            result['layout_performance_report'] = report
            _atomic_json(Path(result['output_dir'])/'joint/layout_performance_report.json', report)


def _prepare_joint(state):
    if state['iteration_context'].get('layout_family') != state['sample_family']['family']:
        raise ValueError('Joint preparation family differs from the frozen assignment')
    root = Path(state['output_dir'])/'joint'
    root.mkdir(parents=True, exist_ok=True)
    identity = digest({'version': VERSION, 'paper': state['paper_foundation_digest'],
        'context': state['iteration_context'], 'family': state['sample_family'],
        'draft': state['poster_claims'], 'plan': state['sample_module_plan']})
    ready = root/'READY.json'
    if ready.exists():
        state.update(deepcopy(_read(ready, identity)['fields']))
        return state
    touched = {}
    try:
        state, result = _converge(state, touched)
        from src.layout.family_capacity import plan_family_capacity
        from src.workflow.sample_editorial import quality_feedback, quality_gain, prose_diagnostics
        if result[1].get('zones'):
            plan_family_capacity(state, result[1])
        # A reserved quality edit cannot replace a feasible baseline with an unsafe candidate.
        baseline = deepcopy(state); baseline_result = deepcopy(tuple(result))
        feedback = quality_feedback(state, result)
        targets = feedback['quality_targets']
        audit = {'version': 'sample_editorial_v1', 'status': 'not_needed',
                 'baseline': feedback['editorial_diagnostics'], 'targets': [], 'reason': None}
        if targets:
            try:
                candidate = _edit(deepcopy(state), feedback, touched, 'quality')
                audit['targets'] = candidate.get('_joint_last_edit_targets', [])
                candidate, improved = _converge(candidate, touched)
                adopted, reason = quality_gain(baseline, baseline_result, candidate, improved, audit['targets'])
                audit.update(status='adopted' if adopted else 'rejected', reason=reason,
                             trial=prose_diagnostics(candidate, improved[2]))
                if adopted:
                    state, result = candidate, improved
                else:
                    state, result = baseline, baseline_result
            except JointContentFailure as exc:
                audit.update(status='rejected', reason=str(exc))
                _atomic_json(root/'quality_rejection.json', {'reason': str(exc)})
                state, result = baseline, baseline_result
        result = restore_visuals(state, result)
        state['visual_curation_report'] = state.get('visual_curation_report') or {}
        state['visual_curation_report']['final_visible_visual_ids'] = sorted({v['visual_id']
            for section in result[0]['spatial_content_plan']['sections'] for v in section['visual_assets']})
        audit['final'] = prose_diagnostics(state, result[2])
        audit['unresolved_targets'] = [r['section_id'] for r in audit['final']['modules'] if r['reasons']]
        result[2]['editorial_quality'] = deepcopy(audit)
        _atomic_json(root/'quality_report.json', audit)
        state['draft_layout_mode'] = False
        state['poster_claims'] = deepcopy(state['verified_claims'])
        board, spec, report = result
        state['verified_module_board'] = deepcopy(board)
        visible_ids = [cid for s in board['spatial_content_plan']['sections'] for cid in s['claim_ids']]
        index = {c['claim_id']: c for c in state['verified_claims']['claims']}
        state['module_body_report']['visible_claim_ids'] = visible_ids
        state['module_body_report']['visible_words'] = sum(len(index[cid]['text'].split()) for cid in visible_ids)
        state['module_body_report']['editorial_diagnostics'] = deepcopy(audit['final'])
        state['joint_candidate'] = {'version': VERSION, 'status': 'verified_feasible',
            'family_id': state['sample_family']['family'], 'science_digest': candidate_identity(state),
            'board': deepcopy(board), 'layout_spec': deepcopy(spec), 'fit_report': deepcopy(report),
            'visual_curation_report': deepcopy(state.get('visual_curation_report'))}
        state['joint_candidate']['digest'] = digest(state['joint_candidate'])
        from src.workflow.content_contracts import science_fields
        for key in ('poster_claims', 'verified_claims', 'verification_report', 'verified_module_board', 'module_body_report'):
            _atomic_json(Path(state['output_dir'])/'content'/(key+'.json'), state.get(key))
        _save(ready, {'input_digest': identity, 'fields': science_fields(state)})
    except SampleRequestFailure as exc:
        from src.workflow.sample_errors import record_sample_error
        record_sample_error(state, exc, 'joint_model_request_failed')
        state.setdefault('errors', []).append(str(exc))
        _atomic_json(root/'failure.json', {'kind': 'joint_model_request_failed', 'reason': str(exc),
            'fatal': bool(state.get('fatal_generation_error'))})
    except JointInterrupted:
        state['_joint_interrupted'] = True
    except JointContentFailure as exc:
        state['verification_passed'] = False
        state['sample_failure'] = {'kind': 'joint_preparation_failed', 'reason': str(exc),
            'family': state['sample_family']['family'], 'family_reselected': False}
        state.setdefault('errors', []).append(str(exc))
        _atomic_json(root/'failure.json', state['sample_failure'])
    return state


def install_joint_candidate_node(state):
    """Validate the frozen baseline before any downstream styling call."""
    candidate = deepcopy(state.get('joint_candidate') or {})
    expected = candidate.pop('digest', None)
    if (state.get('draft_layout_mode') or not state.get('verification_passed') or
            candidate.get('status') != 'verified_feasible' or expected != digest(candidate) or
            candidate.get('science_digest') != candidate_identity(state) or
            candidate.get('family_id') != state['sample_family']['family'] or
            state['iteration_context'].get('layout_family') != state['sample_family']['family']):
        raise ValueError('No coherent verified single-family candidate available for compilation')
    state['story_board'] = deepcopy(candidate['board'])
    state['optimized_story_board'] = deepcopy(candidate['board'])
    state['layout_spec'] = deepcopy(candidate['layout_spec'])
    state['layout_feasibility_report'] = deepcopy(candidate['fit_report'])
    state['visual_curation_report'] = deepcopy(candidate.get('visual_curation_report'))
    return state


def compile_joint_layout_node(state):
    """Compile the adopted candidate only. Never restart the family search here."""
    state = install_joint_candidate_node(state)
    from src.layout.editorial import _emphasize
    from src.layout.content_guards import board_identity
    before = board_identity(state['optimized_story_board'])
    _emphasize(state['optimized_story_board'], state, state['layout_spec'])
    after = board_identity(state['optimized_story_board'])
    for value in (before, after):
        for section in value['sections'].values(): section.pop('importance_level', None)
    if before != after:
        raise ValueError('Styling changed frozen candidate content or geometry ownership')
    state['story_board'] = deepcopy(state['optimized_story_board'])
    agent = LayoutAgent()
    state = agent(state, mode='final')
    report = validate_compiled_layout(state.get('design_layout') or [], state['layout_spec'], state,
        poster_margin=agent.poster_margin, title_height_fraction=agent.title_height_fraction)
    state['layout_preflight_report'] = report
    state['layout_preflight_failed'] = not report['passed']
    if not report['passed']:
        state.setdefault('errors', []).append('Adopted candidate failed final compiled preflight')
    for name, value in [('optimized_story_board', state['optimized_story_board']),
                        ('layout_spec', state['layout_spec']), ('layout_feasibility_report', state['layout_feasibility_report'])]:
        _atomic_json(Path(state['output_dir'])/(name+'.json'), value)
    return state


def verify_selected_science(state):
    """Reuse an unchanged, actually verified expression only with identical local context."""
    from src.agents.claim_verifier import claim_verifier_node
    ignored = {'verified', 'repaired', 'support_map', 'covered_required_evidence_ids',
               'coverage_format_normalizations', 'original_text'}
    def key(claim):
        return digest({k: v for k, v in claim.items() if k not in ignored})
    candidates = state['poster_claims']['claims']
    cached = {key(c): c for c in (state.get('verified_claims') or {}).get('claims', [])
              if c.get('verified') is True}
    pending = [c for c in candidates if key(c) not in cached]
    checked = []
    reports = []
    if pending:
        isolated = dict(state)
        isolated['poster_claims'] = {'claims': pending}
        isolated['errors'] = []
        isolated = claim_verifier_node(isolated)
        checked = (isolated.get('verified_claims') or {}).get('claims', [])
        reports = (isolated.get('verification_report') or {}).get('details', [])
        if isolated.get('errors'):
            state.update({k: isolated[k] for k in ('errors', 'fatal_generation_error', 'sample_failure') if k in isolated})
            state['verified_claims'] = {'claims': checked}
            state['verification_report'] = isolated.get('verification_report')
            state['verification_passed'] = False
            return state
    index = {c['claim_id']: c for c in checked}
    verified = [cached.get(key(c)) or index.get(c['claim_id']) for c in candidates]
    verified = [c for c in verified if c is not None]
    reused = [c['claim_id'] for c in candidates if key(c) in cached]
    state['verified_claims'] = {'claims': deepcopy(verified)}
    state['verification_report'] = {'details': [*reports, *[{'claim_id': cid, 'status': 'passed',
        'source': 'identical_verified_expression_and_context'} for cid in reused]],
        'summary': {'total_claims': len(candidates), 'verified_output_claims': len(verified),
            'reused_verified_claim_ids': reused, 'checked_claims': len(pending)}}
    state['verification_passed'] = bool(verified)
    return state


def seed_visual_candidate(board, state):
    """Retain the existing optional paper-semantic key-visual offer, without a model call."""
    from src.agents.grounded_curator import GroundedCurator
    from src.layout.presentation_policy import section_sources
    curator = GroundedCurator()
    available = curator._valid_visual_ids(state.get('images') or {}, state.get('tables') or {})
    roles = {u['section_id']: u.get('narrative_role') for u in state['narrative_plan']['sections']}
    module_roles = {s['section_id']: {roles.get(sid) for sid in section_sources(s, state)}
                    for s in board['spatial_content_plan']['sections']}
    status = curator._seed_relevant_key_visual(board, state['narrative_plan'],
        state.get('classified_visuals') or {}, available, module_source_roles=module_roles)
    selected = {v['visual_id'] for s in board['spatial_content_plan']['sections'] for v in s['visual_assets']}
    state['visual_curation_report'] = {'schema_version': 1, 'route': 'optimization_family',
        'available_visual_ids': sorted(available), 'curated_visual_ids': sorted(selected),
        'uncurated_visual_ids': sorted(available-selected), 'key_seed_status': status,
        'key_visual_id': (state.get('classified_visuals') or {}).get('key_visual'),
        'source_decisions': deepcopy(state['sample_module_plan'].get('visual_decisions', {}))}


def restore_visuals(state, result):
    """Bounded same-source exact probes, durably charged separately from model edits."""
    from src.layout.capacity_repair import _visual_recovery_candidates
    from src.layout.module_repair import space_preserved
    from src.layout.whitespace import no_displaced_whitespace
    settings = state['critic_config'].get('capacity_repair') or {}
    if not settings.get('enabled', True):
        return result
    source = state.get('_joint_visual_source_board')
    if not source:
        return result
    path = Path(state['sample_edit_budget_dir'])/'visual_restoration_budget.json'
    identity = digest({'policy': 'joint_visual_v1', 'family': state['sample_family'],
        'paper': state['paper_foundation_digest'], 'context': state['iteration_context']})
    if not path.exists() and any((Path(state['output_dir'])/'joint/visual_probes').glob('*.json')):
        raise ValueError('Visual restoration ledger missing from existing history')
    usage = _read(path, identity) if path.exists() else {'input_digest': identity, 'charges': []}
    limit = min(4, int(settings.get('max_visual_restore_attempts_per_iteration', 4)))
    if len(usage['charges']) > limit:
        raise ValueError('Visual restoration budget exceeds its frozen allowance')
    visible = lambda board: {v['visual_id'] for s in board['spatial_content_plan']['sections'] for v in s['visual_assets']}
    roots = lambda board: {cid for s in board['spatial_content_plan']['sections'] for cid in s['claim_ids']}
    candidates = _visual_recovery_candidates(state, source, visible(result[0]))[:min(2, int(settings.get('max_visual_restore_attempts', 2)))]
    audit = []
    for sid, visual_id in candidates:
        check_stop(state)
        key = digest({'board': result[0], 'spec': result[1], 'section': sid, 'visual': visual_id})
        history = Path(state['output_dir'])/'joint/visual_probes'/f'{key}.json'
        if any(c['key'] == key for c in usage['charges']):
            if not history.exists():
                raise ValueError('Visual restoration charged without saved result')
            saved = _read(history, key)
            if saved.get('result'): result = tuple(saved['result'])
            audit.append(saved['audit'])
            continue
        if history.exists():
            raise ValueError('Visual restoration result has no durable charge')
        if len(usage['charges']) >= limit: break
        usage['charges'].append({'key':key, 'section_id':sid, 'visual_id':visual_id})
        _save(path, usage)
        board = deepcopy(result[0]); entry = next((s for s in board['spatial_content_plan']['sections'] if s['section_id']==sid), None)
        row = {'section_id':sid, 'visual_id':visual_id, 'status':'not_placed'}
        adopted = None
        if entry:
            entry['visual_assets'].append({'visual_id':visual_id})
            view = {**state, 'draft_layout_mode':False, 'layout_required_visual_ids':[visual_id], 'styling_interfaces':state.get('styling_interfaces') or {}}
            from src.agents.section_title_designer import SectionTitleDesigner
            view['section_title_design'] = SectionTitleDesigner()._generate_colorblock_design(board, state.get('color_scheme') or {})
            config = deepcopy(state['critic_config']);config.setdefault('explore_layout', {})['minimum_sections']=1
            try:
                trial = fit_family_layout(LayoutAgent(), board, view, state['sample_family']['family'], config=config)
                if (visual_id in visible(trial[0]) and visible(result[0]) <= visible(trial[0]) and
                        roots(result[0]) <= roots(trial[0]) and space_preserved(result[2],trial[2]) and
                        no_displaced_whitespace(result[2].get('composition_whitespace') or {},
                            trial[2].get('composition_whitespace') or {},
                            tolerance=settings.get('max_whitespace_regression_fraction',.01),
                            gap_tolerance_inches=settings.get('max_gap_regression_inches',.35))):
                    adopted = tuple(trial);row['status']='restored'
            except LayoutFeasibilityError as exc:
                row['status']=(exc.report or {}).get('reason_code','no_fit')
        else: row['status']='source_section_not_visible'
        _save(history, {'input_digest':key, 'audit':row, 'result':adopted})
        audit.append(row)
        if adopted: result=adopted
    result[2]['visual_restoration'] = audit
    return result


def structure_merge_options(state):
    """Use existing source/function ownership rules as proposals, never automatic adoption."""
    from src.layout.families import LayoutFamilyRegistry
    from src.layout.presentation_policy import prepare_structure
    family = LayoutFamilyRegistry().get(state['sample_family']['family'])
    if not family.contract.allow_module_grouping:
        return []
    view = deepcopy(state)
    view.update(draft_layout_mode=True, _joint_structure_probe=True)
    for claim in view['poster_claims']['claims']:claim['verified']=False
    board = build_module_board(view, view['poster_claims']['claims'], draft_protection(view))
    _, report = prepare_structure(board, view, family)
    groups = {}
    for row in report['merges']:groups.setdefault(row['section_id'],set()).add(row['into_section_id'])
    unresolved = set(report['unresolved_section_ids'])
    return sorted((source,next(iter(owners))) for source,owners in groups.items()
                  if len(owners)==1 and source not in unresolved)


def merge_module_tasks(state, claims, source_id, owner_id):
    """Regroup an explicit compatible pair without rewriting any scientific root/origin."""
    plan=state['sample_module_plan'];modules=plan['modules']
    source=next(m for m in modules if m['module_id']==source_id)
    owner=next(m for m in modules if m['module_id']==owner_id)
    before={'source':deepcopy(source),'owner':deepcopy(owner)}
    for key in ('source_plan_unit_ids','evidence_ids','required_evidence_ids','required_unit_ids',
                'support_evidence_ids','available_evidence_ids','visual_ids','reserve_visual_ids'):
        owner[key]=list(dict.fromkeys([*owner.get(key,[]),*source.get(key,[])]))
    owner['visual_rationales'] = {**source.get('visual_rationales', {}), **owner.get('visual_rationales', {})}
    for decision in plan.get('visual_decisions', {}).values():
        if decision.get('module_id') == source_id:
            decision['module_id'] = owner_id
    owner['required_assertions']=[{**r} for r in {r['evidence_id']:r for r in
        [*owner['required_assertions'],*source['required_assertions']]}.values()]
    owner['writing_brief']=owner['writing_brief']+' Supporting context: '+source['writing_brief']
    owner['module_purpose']='primary'
    plan['modules']=[m for m in modules if m['module_id']!=source_id]
    plan.setdefault('structure_revisions',[]).append({'source_module_id':source_id,'owner_module_id':owner_id,
        'original_tasks':before,'scientific_roots_merged':False})
    for claim in claims:
        if claim['display_module_id']==source_id:
            claim.setdefault('original_display_module_id',source_id)
            claim['display_module_id']=owner_id
        if claim['display_module_id']==owner_id:
            claim.setdefault('module_context',{})['task']=owner['writing_brief']
    refresh_contexts(claims)
    from src.layout.family_capacity import plan_family_capacity
    plan_family_capacity(state)
