"""One same-attempt rollback if completed content fails downstream fit checks."""

from copy import deepcopy


def rollback_completion(state):
    saved = state.pop('_quality_repair_baseline', None)
    if saved is None:
        return False
    if saved['attempt_id'] != (state.get('iteration_context') or {}).get('attempt_id'):
        raise ValueError('Module completion baseline belongs to another attempt')
    failure = {
        'preflight': deepcopy(state.get('layout_preflight_report')),
        'render_fit': deepcopy(state.get('render_fit_report')),
        'editorial': deepcopy((state.get('layout_feasibility_report') or {}).get('editorial')),
    }
    audit = deepcopy(state.get('capacity_repair_report') or {})
    for key, value in saved['fields'].items():
        state[key] = deepcopy(value)
    board, spec, report = deepcopy(saved['result'])
    state.update(story_board=board, optimized_story_board=deepcopy(board),
                 layout_spec=spec, layout_feasibility_report=report,
                 layout_content_selection=deepcopy(report.get('candidate_content_selection') or {}),
                 errors=[], layout_preflight_failed=False,
                 render_fit_report=None, render_diagnostics=None,
                 layout_preflight_report=None, revision_safety_report=None,
                 styled_layout=None, design_layout=None)
    # Keep candidate identity/output ownership, but never reuse failed readiness.
    candidate = deepcopy(state.get('current_candidate') or {})
    candidate['status'] = 'pending'
    candidate.pop('render_status', None)
    candidate.pop('rendered', None)
    state['current_candidate'] = candidate
    audit['status'] = 'rolled_back_after_final_fit'
    audit['completion_rollback'] = failure
    for outcome in audit.get('module_outcomes', []):
        outcome.update(status='unresolved', reason='final_fit_rollback')
    audit['unresolved_section_ids'] = sorted({x['section_id'] for x in audit.get('module_outcomes', [])})
    state['capacity_repair_report'] = audit
    from src.agents.layout_agent import LayoutAgent
    from src.agents.layout_with_balancer import LayoutWithBalancerAgent
    LayoutAgent()(state, mode='final')
    if (state.get('iteration_context') or {}).get('portfolio_mode') == 'improve':
        state['revision_execution_report'] = LayoutWithBalancerAgent._revision_execution_report(state, board, spec)
    decisions = state.get('balancer_decisions') or {}
    if isinstance(decisions.get('content_guard'), dict):
        decisions['content_guard']['capacity_selection'] = deepcopy(state['layout_content_selection'])
    from src.agents.content_optimizer import GroundedContentOptimizer
    GroundedContentOptimizer._save(state)
    # Reuse the same deterministic emphasis choices; rollback adds no keyword
    # model call. The ordinary final typography preflight still runs next.
    if not state.get('errors'):
        from src.agents.font_agent import FontAgent
        font = FontAgent()
        state['styled_layout'] = font._apply_styling(
            state['design_layout'], state.get('color_scheme') or {}, state.get('keywords') or {}, state)
        font._save_styled_layout(state)
    LayoutWithBalancerAgent._save_family_fit_artifacts(state)
    return True
