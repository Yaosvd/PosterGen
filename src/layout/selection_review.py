"""One charged, ID-only necessity review inside existing content optimization."""

from copy import deepcopy
from pathlib import Path

from src.layout.editorial import locked, prepare_board, sections
from src.layout.editorial_selection import (
    SELECTION_VERSION, sanitize_selection, selection_audit, dependency_edges, required_roots, dispositions,
)
from src.layout.repair_budget import available_rounds, family_rounds_used, charge_round, purpose_used
from utils.grounded_content import all_publishable_claims, claim_root_id


def hard_required(board, state):
    claims = all_publishable_claims(state)
    evidence = {e for s in (state.get('narrative_plan') or {}).get('sections', [])
                for e in s.get('required_evidence_ids', [])}
    pinned = set((state.get('layout_revision_constraints') or {}).get('must_retain_claim_ids', []))
    pinned.update((board.get('editorial_selection') or {}).get('planner_required_claim_ids', []))
    pinned.update(cid for cid, c in claims.items() if evidence.intersection(c.get('evidence_ids', [])))
    roots = {claim_root_id(claims.get(c, {'claim_id': c})) for c in pinned}
    return pinned | {c for s in sections(board) for c in s.get('claim_ids', [])
                     if claim_root_id(claims.get(c, {'claim_id': c})) in roots}


def apply_review(board, state, raw):
    """Validate only selection metadata; science, assets and ownership stay exact."""
    if not isinstance(raw, dict) or raw.get('status') != 'resolved' or not isinstance(raw.get('items'), list):
        return None, 'review_unresolved'
    claims = all_publishable_claims(state)
    visible = {cid for s in sections(board) for cid in s.get('claim_ids', [])}
    old = {i['claim_id']: i for i in (board.get('editorial_selection') or {}).get('items', [])}
    incoming = raw['items']
    if (len(incoming) != len(visible) or any(not isinstance(i, dict) or not isinstance(i.get('claim_id'), str) for i in incoming)
            or {i['claim_id'] for i in incoming} != visible):
        return None, 'review_ids_invalid'
    by_id = {i['claim_id']: i for i in incoming}
    root = lambda cid: claim_root_id(claims.get(cid, {'claim_id': cid}))
    old_roots = dispositions(board, state)
    for cid, i in by_id.items():
        if i.get('disposition') not in ('required', 'optional'):
            return None, 'review_disposition_invalid'
        if not isinstance(i.get('reason'), str) or i['reason'] not in ({'core', 'condition'} if i['disposition'] == 'required' else {'useful', 'secondary', 'redundant'}):
            return None, 'review_reason_invalid'
        scope = i.get('required_for_claim_ids') or []
        if not isinstance(scope, list) or any(not isinstance(c, str) or c not in visible or root(c) == root(cid) for c in scope):
            return None, 'review_context_invalid'
        if scope and i.get('reason') != 'condition':
            return None, 'review_context_invalid'
    for cid in visible:
        prior = old_roots.get(root(cid), {})
        if prior.get('disposition') == 'omit':
            return None, 'explicit_omission_protected'
        if (prior.get('disposition') == 'required'
                and not prior.get('required_for_claim_ids')
                and (by_id[cid]['disposition'] != 'required' or by_id[cid].get('required_for_claim_ids'))):
            owner = next(s for s in sections(board) if cid in s.get('claim_ids', []))
            anchors = by_id[cid].get('retained_anchor_claim_ids') or []
            if (not isinstance(anchors, list) or not anchors or any(
                    not isinstance(c, str) or root(c) == root(cid) or c not in owner.get('claim_ids', [])
                    or by_id[c]['disposition'] != 'required' or by_id[c].get('required_for_claim_ids') for c in anchors)):
                return None, 'demotion_anchor_unresolved'
    required = hard_required(board, state)
    items = {**old, **by_id}
    root_decisions = {}
    for cid, item in by_id.items():
        decision = {k: item[k] for k in ('disposition', 'reason', 'required_for_claim_ids') if k in item}
        if root(cid) in root_decisions and root_decisions[root(cid)] != decision:
            return None, 'review_root_conflict'
        root_decisions[root(cid)] = decision
    # The review concerns scientific roots; reserve variants of the same fact
    # neither undo a demotion nor override a retained necessary explanation.
    for cid in claims:
        if root(cid) in root_decisions:
            items[cid] = {'claim_id': cid, **root_decisions[root(cid)]}
    contract = sanitize_selection({'items': list(items.values())}, claims,
        visible=visible, required=required, dependencies=dependency_edges(board))
    # A review must explicitly honor hard requirements, not rely on sanitizer
    # silently repairing contradictory model output.
    if any(c in visible and (by_id[c]['disposition'] != 'required' or by_id[c].get('required_for_claim_ids')) for c in required):
        return None, 'hard_requirement_changed'
    result = deepcopy(board)
    result['editorial_selection'] = contract
    if not selection_audit(result, state)['passed']:
        return None, 'review_inconsistent'
    from src.layout.design_content import ContentPriorities
    # Keep each available important research phase represented by a required
    # explanation, rather than merely leaving all meaningful content optional.
    priorities = ContentPriorities({**state, 'story_board': board}, sections(board))
    required_after = required_roots(result, state)
    if any(not group.intersection(required_after) for group in priorities.important_groups.values()):
        return None, 'important_phase_unprotected'
    return result, 'resolved'


def review_selection(state, board, family_id, *, measured_failure=False, optimizer=None):
    audit = selection_audit(board, state)
    needed = not audit['passed'] or (measured_failure and audit['required_root_count'] > 0)
    report = {'version': SELECTION_VERSION, 'status': 'not_needed', 'model_rounds': 0, 'before': audit}
    if not needed or not (board.get('editorial_selection') or {}).get('items'):
        return board, report
    settings = (state.get('critic_config') or {}).get('capacity_repair') or {}
    optimization = (state.get('critic_config') or {}).get('content_optimization') or {}
    overrides = (state.get('loop_config') or {}).get('content_optimization') or {}
    reason = next((r for condition, r in (
        (locked(state), 'locked'),
        (state.get('generation_route') != 'optimization_family', 'not_loop_route'),
        (not settings.get('enabled', True), 'disabled'),
        (not overrides.get('enabled', optimization.get('enabled', True)), 'disabled'),
        (purpose_used(state, 'selection_review'), 'selection_review_already_used'),
        (available_rounds(state, 'capacity', settings) < 1, 'repair_budget_exhausted'),
        (family_rounds_used(state, family_id) >= int(settings.get('max_rounds_per_family', 2)), 'family_budget_exhausted'),
        (not state.get('text_model') or not state.get('tokens'), 'model_unavailable'),
    ) if condition), None)
    if reason:
        report.update(status='unresolved' if not audit['passed'] else 'skipped', reason=reason)
        return board, report
    # Resolve input/owner failures before spending a content-model round.
    # The fitter owns their distinct visual failure route.
    from src.layout.visual_requirements import enabled, contract_for, validate_contract, attach_required
    if enabled(state):
        contract = contract_for(state, board)
        _, owner_issues = attach_required(board, state, contract)
        if (validate_contract(contract, state) or owner_issues
                or (board.get('visual_requirements') and board['visual_requirements'].get('contract_digest')
                    != contract.get('contract_digest'))):
            report.update(status='skipped', reason='visual_requirements_unresolved')
            return board, report
    from src.layout.presentation_policy import prepare_structure
    from src.layout.families import LayoutFamilyRegistry
    prepared, structure = prepare_structure(prepare_board(board, state), state, LayoutFamilyRegistry().get(family_id))
    if structure.get('unresolved_section_ids'):
        report.update(status='unresolved', reason='structure_requires_resolution')
        return board, report
    state.setdefault('iteration_context', {}).setdefault('layout_family', family_id)
    if not charge_round(state, 'capacity', settings, purpose='selection_review'):
        report.update(status='unresolved', reason='repair_budget_exhausted')
        return board, report
    report['model_rounds'] = 1
    from src.agents.content_optimizer import GroundedContentOptimizer
    from utils.langgraph_utils import load_prompt
    claims = all_publishable_claims(state)
    visible = {c for s in sections(prepared) for c in s.get('claim_ids', [])}
    payload = {'sections': [{'section_id': s['section_id'], 'claim_ids': s['claim_ids'],
                             'core_claim_ids': s.get('core_claim_ids', []),
                             'source_section_ids': (s.get('editorial') or {}).get('source_section_ids', [])}
                            for s in sections(prepared)],
               'claims': [claims[c] for c in sorted(visible) if c in claims],
               'existing_selection': board['editorial_selection'],
               'hard_required_claim_ids': sorted(hard_required(board, state)),
               'source_context': state.get('source_context_overlay') or {},
               'narrative_plan': state.get('narrative_plan') or {},
               'evidence_items': [e for field in ('evidence_bank', 'supplemental_evidence_bank')
                    for e in (state.get(field) or {}).get('items', [])
                    if e.get('evidence_id') in {eid for c in visible for eid in claims.get(c, {}).get('evidence_ids', [])}],
               'selection_audit': audit}
    worker = optimizer or GroundedContentOptimizer()
    report['status'] = 'running'
    state['selection_review_report'] = report
    directory = (state.get('iteration_context') or {}).get('attempt_diagnostics_dir')
    if directory:
        from src.workflow.campaign import _atomic_json
        _atomic_json(Path(directory) / 'selection_review_report.json', report)
    raw = worker._model_json(state, load_prompt('config/prompts/review_editorial_selection.txt'), payload)
    reviewed, reason = apply_review(prepared, state, raw)
    report.update(status='resolved' if reviewed is not None else 'unresolved', reason=reason)
    if reviewed is not None:
        report['after'] = selection_audit(reviewed, state)
        report['changed_claim_ids'] = [i['claim_id'] for i in reviewed['editorial_selection']['items']
            if i != next((old for old in board['editorial_selection']['items'] if old['claim_id'] == i['claim_id']), None)]
        # Bind replayable ID decisions to this exact board/attempt, without
        # copying another attempt's scientific content or changing its input.
        from src.layout.visual_requirements import digest
        report['input_board_digest'] = digest(board)
        report['attempt_id'] = (state.get('iteration_context') or {}).get('attempt_id')
        report['reviewed_selection'] = reviewed['editorial_selection']
    directory = (state.get('iteration_context') or {}).get('attempt_diagnostics_dir')
    if directory:
        from src.workflow.campaign import _atomic_json
        _atomic_json(Path(directory) / 'selection_review_report.json', report)
    state['selection_review_report'] = report
    return reviewed if reviewed is not None else board, report
