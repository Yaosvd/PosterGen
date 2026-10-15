"""Bounded module completion on an already feasible layout.

All families share this path. Fixed geometry is tried first; ownership stays fixed;
failed trials cannot replace the last feasible board or publish content banks.
"""

from copy import deepcopy

from src.agents.content_optimizer import content_optimizer
from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError
from src.layout.repair_budget import charge_round
from src.layout.whitespace import no_displaced_whitespace
from utils.grounded_content import all_publishable_claims, claim_root_id
from utils.module_content import existing_module_candidates, module_context


CONTENT_FIELDS = ('story_board', 'verified_content_bank', 'supplemental_evidence_bank',
                  'content_selection', 'content_revision', 'layout_revision_constraints',
                  'revision_contract', 'revision_recovery_policy')


def repair_targets(board, report, settings):
    from src.layout.capacity_repair import feasible_repair_zones
    hints = report.get('content_quality_hints') or {}
    thin = set(hints.get('thin_section_ids') or [])
    sparse = set(feasible_repair_zones(report, settings))
    sections = {str(s['section_id']): s for s in board['spatial_content_plan']['sections']}
    measured = {d['section_id']: d.get('measured_body_lines') for d in hints.get('module_diagnostics', [])}
    short = {str(s['section_id']) for s in sections.values()
             if len(s.get('claim_ids', [])) <= 1 and not s.get('visual_assets')
             and (measured[str(s['section_id'])] <= 2.5 if measured.get(str(s['section_id'])) is not None
                  else sum(len(t) for t in s.get('text_content', [])) <= 160)}
    result = []
    for zone in (report.get('selected_layout_spec') or {}).get('zones', []):
        ids = [str(s) for s in zone.get('section_ids', []) if str(s) in sections]
        consecutive = set()
        for a, b in zip(ids, ids[1:]):
            if a in short and b in short:
                consecutive.update((a, b))
        for sid in ids:
            reasons = []
            if sid in thin:
                reasons.append('original_information_reduced')
            if sid in consecutive:
                reasons.append('consecutive_short_text_modules')
            if zone['zone_id'] in sparse:
                reasons.append('unused_zone_capacity')
            if reasons:
                result.append({'section_id': sid, 'zone_id': zone['zone_id'], 'reasons': reasons})
    return sorted(result, key=lambda x: (
        'original_information_reduced' not in x['reasons'],
        'consecutive_short_text_modules' not in x['reasons']))


def space_preserved(before, after):
    """Check every zone, terminal gap and global hole, including cumulative drift."""
    old, new = before.get('zone_utilization') or {}, after.get('zone_utilization') or {}
    if any(z not in new or float(new[z]) < float(v) - 0.005 for z, v in old.items()):
        return False
    old_gaps, new_gaps = before.get('exact_bottom_gaps') or {}, after.get('exact_bottom_gaps') or {}
    if any(z not in new_gaps or float(new_gaps[z]) > float(v) + 0.05 for z, v in old_gaps.items()):
        return False
    return no_displaced_whitespace(before.get('composition_whitespace') or {},
                                   after.get('composition_whitespace') or {},
                                   tolerance=0.005, gap_tolerance_inches=0.05)


def content_preserved(before, after, state):
    """Preserve occurrences, not just global sets; allow verified same-root variants."""
    claims = all_publishable_claims(state)
    old = {s['section_id']: s for s in before['spatial_content_plan']['sections']}
    new = {s['section_id']: s for s in after['spatial_content_plan']['sections']}
    if set(old) != set(new):
        return False
    for sid, section in old.items():
        roots = lambda s: {claim_root_id(claims.get(c, {'claim_id': c})) for c in s.get('claim_ids', [])}
        visuals = lambda s: {v['visual_id'] for v in s.get('visual_assets', [])}
        if not roots(section).issubset(roots(new[sid])) or not visuals(section).issubset(visuals(new[sid])):
            return False
    return True


def _publish(state, trial, fitted):
    visible = {c for s in fitted['spatial_content_plan']['sections'] for c in s.get('claim_ids', [])}
    old_ids = {c['claim_id'] for c in (state.get('verified_content_bank') or {}).get('claims', [])}
    bank = trial.get('verified_content_bank') or {'claims': []}
    bank['claims'] = [c for c in bank.get('claims', []) if c['claim_id'] in visible | old_ids]
    old_evidence = {e['evidence_id'] for e in (state.get('supplemental_evidence_bank') or {}).get('items', [])}
    needed = {e for c in bank['claims'] for e in c.get('evidence_ids', [])}
    evidence = trial.get('supplemental_evidence_bank') or {'items': []}
    evidence['items'] = [e for e in evidence.get('items', []) if e['evidence_id'] in old_evidence | needed]
    prior = deepcopy(state.get('content_revision') or {})
    for field in CONTENT_FIELDS:
        state[field] = deepcopy(trial.get(field))
    state['story_board'] = deepcopy(fitted)
    state['verified_content_bank'] = bank
    state['supplemental_evidence_bank'] = evidence
    revision = state.get('content_revision') or {}
    revision['accepted_actions'] = prior.get('accepted_actions', []) + revision.get('accepted_actions', [])
    revision['created_claim_ids'] = list(dict.fromkeys(prior.get('created_claim_ids', []) + revision.get('created_claim_ids', [])))
    state['content_revision'] = revision


def complete_modules(agent, state, current, family_id, settings, audit, maximum_rounds, *, optimizer=None):
    optimizer = optimizer or content_optimizer
    optimization = (state.get('critic_config') or {}).get('content_optimization') or {}
    overrides = (state.get('loop_config') or {}).get('content_optimization') or {}
    if not overrides.get('enabled', optimization.get('enabled', True)):
        audit['skip_reason'] = 'content_optimization_disabled'
        audit['unresolved_section_ids'] = [t['section_id'] for t in repair_targets(
            current[0], {**current[2], 'selected_layout_spec': current[1]}, settings)]
        return current, audit
    baseline = deepcopy(current)
    baseline_fields = {k: deepcopy(state.get(k)) for k in CONTENT_FIELDS}
    attempts = []
    audit['module_attempts'] = attempts
    tried = {}
    model_stages = {}
    original_targets = {}
    geometry_trials = 0

    def targets():
        report = {**current[2], 'selected_layout_spec': current[1]}
        values = repair_targets(current[0], report, settings)
        for value in values:
            original_targets.setdefault(value['section_id'], value)
        return sorted(values, key=lambda t: len(tried.get(t['section_id'], [])))

    def apply(action, *, model_round=None):
        nonlocal current, geometry_trials
        sid = action['section_id']
        tried.setdefault(sid, []).append(action.get('claim_id') or action['operation'])
        item = {'section_id': sid, 'operation': action['operation'], 'round': model_round,
                'claim_id': action.get('claim_id'), 'search_source': bool(action.get('search_source')),
                'status': 'no_safe_content_change'}
        attempts.append(item)
        trial = dict(state)
        for field in CONTENT_FIELDS:
            trial[field] = deepcopy(state.get(field))
        trial['errors'] = []
        try:
            trial = optimizer(trial, board_override=current[0], actions_override=[action], save=False)
        except Exception as exc:
            from src.workflow.generation_failure import capture_failure
            item['status'] = 'error'
            audit['status'] = 'error'
            if audit['rounds']:
                audit['rounds'][-1]['status'] = 'error'
            capture_failure(state, exc, agent='content_optimizer', phase='capacity_repair/content_optimizer')
            raise
        accepted = (trial.get('content_revision') or {}).get('accepted_actions') or []
        if trial.get('errors') or not accepted:
            item['rejected_actions'] = (trial.get('content_revision') or {}).get('rejected_actions') or []
            return False
        changed = trial['story_board']
        constraints = deepcopy(trial.get('layout_revision_constraints'))
        pins = {str(s): str(z['zone_id']) for z in current[1]['zones'] for s in z.get('section_ids', [])}
        trial['layout_revision_constraints'] = {
            **(constraints or {}), 'section_to_zone': pins,
            'reading_order': list(current[1].get('reading_order') or pins),
            'must_retain_claim_ids': [c for s in changed['spatial_content_plan']['sections'] for c in s.get('claim_ids', [])],
            'must_retain_visual_ids': [v['visual_id'] for s in changed['spatial_content_plan']['sections'] for v in s.get('visual_assets', [])],
        }
        try:
            result = fit_family_layout(agent, changed, trial, family_id,
                                       config=state.get('critic_config') or {},
                                       fixed_zones=deepcopy(current[1]['zones']))
        except LayoutFeasibilityError:
            locked = ((state.get('iteration_context') or {}).get('portfolio_mode') == 'validate'
                      or state.get('template_validation_topology') or state.get('improve_safe_fallback'))
            if locked or geometry_trials >= 1:
                item['status'] = 'no_exact_fit'
                return False
            geometry_trials += 1
            config = deepcopy(state.get('critic_config') or {})
            for key in ('explore_layout', 'improve_layout'):
                config.setdefault(key, {}).update(max_geometry_candidates_per_family=2,
                    max_adaptive_geometry_candidates=2, max_exact_candidates=2)
            config['composition_refinement'] = {'enabled': False}
            item['geometry_fallback_attempted'] = True
            try:
                result = fit_family_layout(agent, changed, trial, family_id, config=config)
            except LayoutFeasibilityError:
                item['status'] = 'no_exact_fit'
                return False
        finally:
            trial['layout_revision_constraints'] = constraints
        # Require exact placement of the proposed content, not a solver silently
        # discarding it or moving it to another module.
        wanted = {s['section_id']: set(s.get('claim_ids', [])) for s in changed['spatial_content_plan']['sections']}
        actual = {s['section_id']: set(s.get('claim_ids', [])) for s in result[0]['spatial_content_plan']['sections']}
        placed = {str(s): str(z['zone_id']) for z in result[1].get('zones', []) for s in z.get('section_ids', [])}
        if (placed != pins
                or any(z.get('section_ids', []) != next((q.get('section_ids', []) for q in result[1].get('zones', [])
                    if q['zone_id'] == z['zone_id']), None) for z in current[1]['zones'])
                or any(not ids.issubset(actual.get(s, set())) for s, ids in wanted.items())
                or not content_preserved(current[0], result[0], trial)
                or not content_preserved(baseline[0], result[0], trial)):
            item['status'] = 'content_or_ownership_regression'
            return False
        if not space_preserved(current[2], result[2]) or not space_preserved(baseline[2], result[2]):
            item['status'] = 'space_regression'
            return False
        # Existing original roots are verified restored information; generated
        # additions have passed ClaimVerifier and the non-redundancy audit.
        _publish(state, trial, result[0])
        current = result
        item['status'] = 'adopted'
        audit['status'] = 'applied'
        if '_quality_repair_baseline' not in state:
            state['_quality_repair_baseline'] = {
                'fields': baseline_fields, 'result': baseline,
                'attempt_id': (state.get('iteration_context') or {}).get('attempt_id'),
            }
        return True

    # Free restoration is limited to immutable original-module base claims.
    # It never consumes a model round or invokes an editorial model.
    base = {c['claim_id'] for c in (state.get('verified_claims') or {}).get('claims', [])}
    for _ in range(8):
        selected = None
        for target in targets():
            sid = target['section_id']
            original = set(module_context(state, current[0], sid)['claim_ids'])
            candidates = existing_module_candidates(state, current[0], sid, excluded_ids=tried.get(sid, []))
            candidate = next((c for c in candidates if c['claim_id'] in base & original), None)
            if candidate:
                selected = {'operation': 'add_existing_claim', 'section_id': sid,
                            'claim_id': candidate['claim_id'], 'reason': 'restore original verified module detail'}
                break
        if selected is None:
            break
        apply(selected)

    for round_index in range(maximum_rounds):
        pending = targets()
        if not pending:
            break
        if not state.get('text_model') or not state.get('tokens'):
            audit['skip_reason'] = 'model_unavailable'
            break
        actions = []
        for target in pending:
            sid = target['section_id']
            stage = model_stages.get(sid, 0)
            if stage >= 2:
                continue
            candidates = existing_module_candidates(state, current[0], sid, excluded_ids=tried.get(sid, []))
            candidate = next(iter(candidates), None)
            if candidate:
                action = {'operation': 'add_existing_claim', 'claim_id': candidate['claim_id']}
            else:
                claims = all_publishable_claims(state)
                visible_roots = {claim_root_id(claims[c]) for s in current[0]['spatial_content_plan']['sections']
                                 for c in s.get('claim_ids', []) if c in claims}
                omitted = next((cid for cid in tried.get(sid, [])
                                if cid in claims and cid in module_context(state, current[0], sid)['claim_ids']
                                and claim_root_id(claims[cid]) not in visible_roots
                                and any(a.get('claim_id') == cid and a['status'] == 'no_exact_fit' for a in attempts)), None)
                if omitted and stage == 0:
                    action = {'operation': 'create_compact_variant', 'claim_id': omitted, 'restore_omitted': True}
                else:
                    action = {'operation': 'add_claim_from_evidence', 'search_source': stage > 0}
            actions.append({**action, 'section_id': sid, 'reason': 'complete useful paper-supported module detail'})
            if len(actions) >= min(2, max(1, int(settings.get('max_actions_per_round', 2)))):
                break
        if not actions:
            audit['skip_reason'] = 'bounded_source_search_exhausted'
            break
        if not charge_round(state, 'quality', settings):
            audit['skip_reason'] = 'repair_budget_exhausted'
            break
        audit['rounds_attempted'] += 1
        record = {'round': round_index + 1, 'actions': actions, 'status': 'no_safe_content_change'}
        audit['rounds'].append(record)
        for action in actions:
            sid = action['section_id']
            if action['operation'] in {'add_claim_from_evidence', 'create_compact_variant'}:
                model_stages[sid] = model_stages.get(sid, 0) + 1
            if apply(action, model_round=round_index + 1):
                record['status'] = 'fit_improved'

    unresolved = {t['section_id']: t for t in targets()}
    if unresolved and not audit.get('skip_reason'):
        audit['skip_reason'] = 'repair_budget_exhausted' if maximum_rounds == 0 or audit['rounds_attempted'] >= maximum_rounds else 'no_safe_completion'
    audit['module_outcomes'] = [
        {**t, 'status': 'unresolved' if sid in unresolved else 'resolved',
         'reason': audit.get('skip_reason') if sid in unresolved else 'diagnostic_no_longer_triggered',
         'attempt_count': len(tried.get(sid, []))}
        for sid, t in original_targets.items()]
    audit['unresolved_section_ids'] = sorted(unresolved)
    audit['final_fit'] = {'worst_zone_utilization': current[2].get('worst_zone_utilization'),
                          'composition_whitespace': current[2].get('composition_whitespace')}
    if audit['status'] != 'applied':
        audit['status'] = 'no_safe_improvement'
    return current, audit
