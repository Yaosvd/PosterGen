"""Sample-local communication diagnostics, never a scientific admission judge."""
from copy import deepcopy
from difflib import SequenceMatcher


def module_roles(module, state):
    units = {u['section_id']: u for u in state['narrative_plan']['sections']}
    aliases = {'result': 'results', 'interpretation': 'discussion', 'research_insight': 'insight'}
    return {aliases.get(value, value) for sid in module['source_plan_unit_ids']
            for value in (units[sid].get('presentation_function'), units[sid].get('narrative_role')) if value}


def visual_context(state, brief):
    """Existing caption/role metadata plus physical footprints; no pixel judgment."""
    from PIL import Image
    classified = state.get('classified_visuals') or {}
    result = []
    for prefix, field in [('figure', 'images'), ('table', 'tables')]:
        for key, asset in (state.get(field) or {}).items():
            vid = f'{prefix}_{key}'
            roles = [role for role, ids in classified.items() if isinstance(ids, list) and vid in ids]
            pixels = None
            if asset.get('path'):
                with Image.open(asset['path']) as picture:
                    pixels = picture.size[0]
            aspect = max(.01, float(asset.get('aspect') or 1))
            result.append({'visual_id': vid, 'caption': asset.get('caption', ''), 'aspect': aspect,
                'source_roles': roles, 'key_visual': classified.get('key_visual') == vid,
                'family_footprints': [{'zone_id': z['zone_id'], 'width_inches': round(max(.1, z['width_inches']-.6), 3),
                    'height_inches': round(max(.1, z['width_inches']-.6)/aspect, 3),
                    'effective_dpi': round(pixels/max(.1, z['width_inches']-.6), 1) if pixels else None}
                    for z in brief.get('zones', [])],
                'interpretation': 'Caption and existing source role only; footprint is an estimate, not a readability certificate.'})
    return result


def prose_diagnostics(state, report=None):
    """Observable copy/structure/space signals, not semantic quality verdicts."""
    evidence = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    claims = (state.get('verified_claims') or state.get('poster_claims') or {}).get('claims', [])
    report = report or {}
    from src.layout.body_presentation import wording_issues
    visible = (report.get('candidate_content_selection') or {}).get('visible_claim_ids')
    if visible is not None:
        claims = [c for c in claims if c['claim_id'] in set(visible)]
    space = {t['section_id']: t for t in (report.get('content_quality_hints') or {}).get('completion_targets', [])}
    rows = []
    for module in state['sample_module_plan']['modules']:
        body = [c for c in claims if c['display_module_id'] == module['module_id']]
        copied = sum(any(c['text'] == evidence[e].get('claim') for e in c['evidence_ids']) for c in body)
        near = sum(any(SequenceMatcher(None, c['text'], evidence[e].get('claim', '')).ratio() >= .85
                       for e in c['evidence_ids']) for c in body)
        indirect = sum(bool(wording_issues(c['text'])) for c in body)
        used = {e for c in body for support in c.get('support_map', [])
                for e in support.get('evidence_ids', [])}
        reasons = []
        if len(body) >= 2 and near >= 2 and near/len(body) >= .5:
            reasons.append('evidence_summary_list')
        if any(len(c['text'].split()) > 35 for c in body):
            reasons.append('long_display_expression')
        if indirect:
            reasons.append('indirect_poster_voice')
        if module['module_id'] in space:
            reasons.append('unused_zone_capacity')
        rows.append({'section_id': module['module_id'], 'expression_count': len(body),
            'words': sum(len(c['text'].split()) for c in body), 'copied_expressions': copied,
            'near_copy_expressions': near, 'long_expressions': sum(len(c['text'].split()) > 35 for c in body),
            'indirect_expressions': indirect,
            'supported_evidence_ids': sorted(used),
            'available_unused_evidence_ids': sorted(set(module['available_evidence_ids'])-used),
            'reasons': reasons, 'bottom_gap': float(space.get(module['module_id'], {}).get('bottom_gap', 0)),
            'utilization': float(space.get(module['module_id'], {}).get('utilization', 1)),
            'research_question': module.get('research_question', ''),
            'communication_goal': module.get('communication_goal', '')})
    return {'version': 'sample_editorial_v1', 'signals_are_not_semantic_verdicts': True, 'modules': rows}


def quality_feedback(state, result):
    diagnostic = prose_diagnostics(state, result[2])
    targets = [r for r in diagnostic['modules'] if r['reasons']]
    return {'quality_targets': targets,
            'completion_targets': (result[2].get('content_quality_hints') or {}).get('completion_targets', []),
            'actual_layout_spec': deepcopy(result[1]), 'editorial_diagnostics': diagnostic}


def quality_gain(before_state, before, after_state, after, targets):
    """Require an observed improvement, as well as all existing safety guards."""
    from src.layout.module_repair import space_preserved
    if not space_preserved(before[2], after[2]):
        return False, 'space_regression'
    before_sections = {s['section_id']: s for s in before[0]['spatial_content_plan']['sections']}
    after_sections = {s['section_id']: s for s in after[0]['spatial_content_plan']['sections']}
    omitted = set(after_state.get('_joint_omitted_claim_ids') or [])
    for sid, section in before_sections.items():
        if sid not in after_sections:
            return False, 'visible_module_lost'
        actual = set(after_sections[sid]['claim_ids'])
        if not (set(section['claim_ids'])-omitted) <= actual:
            return False, 'visible_root_lost'
        if not {v['visual_id'] for v in section['visual_assets']} <= {v['visual_id'] for v in after_sections[sid]['visual_assets']}:
            return False, 'visible_visual_lost'
    old = {r['section_id']: r for r in prose_diagnostics(before_state, before[2])['modules']}
    new = {r['section_id']: r for r in prose_diagnostics(after_state, after[2])['modules']}
    for sid in targets:
        if sid not in old or sid not in new:
            continue
        a, b = old[sid], new[sid]
        if (b['near_copy_expressions'] < a['near_copy_expressions'] or b['long_expressions'] < a['long_expressions']
                or b['indirect_expressions'] < a['indirect_expressions']):
            return True, 'display_expression_improved'
        if (set(b['supported_evidence_ids'])-set(a['supported_evidence_ids']) and
                after_sections[sid]['text_content'] != before_sections[sid]['text_content']):
            return True, 'verified_explanation_added'
        from src.layout.body_presentation import paragraphs
        hierarchy = lambda section: sum(bool(row['label']) or row['indent_inches'] > 0 for row in paragraphs(section))
        if hierarchy(after_sections[sid]) > hierarchy(before_sections[sid]):
            return True, 'display_hierarchy_improved'
        if float(a['bottom_gap'])-float(b['bottom_gap']) > .1:
            return True, 'target_space_improved'
    return False, 'no_measured_quality_gain'
