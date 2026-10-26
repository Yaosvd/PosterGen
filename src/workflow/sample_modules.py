"""Sample-only module prose contracts; source units never become display IDs."""
from copy import deepcopy
from pathlib import Path
import re

from utils.persistence import _atomic_json

BODY_VERSION = 'sample_body_v2'


def source_units(claim):
    values = claim.get('source_plan_unit_ids')
    if values is not None:
        return list(dict.fromkeys(str(s) for s in values if s))
    return [str(claim['section_id'])] if claim.get('section_id') else []


def support_coverage(text, rows, evidence_ids):
    """Every visible word needs an exact, supported span, not a partial verdict."""
    text = ' '.join(str(text).split())
    covered = [False] * len(text)
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict) or row.get('supported') is not True:
            return False
        quote = ' '.join(str(row.get('quote') or '').split())
        ids = row.get('evidence_ids')
        if not quote or not isinstance(ids, list) or not ids or not set(ids) <= set(evidence_ids):
            return False
        starts = [m.start() for m in re.finditer(re.escape(quote), text)]
        if len(starts) != 1:
            return False
        start = starts[0]
        covered[start:start + len(quote)] = [True] * len(quote)
    return any(c.isalnum() for c in text) and all(flag or char.isspace() for char, flag in zip(text, covered))


class ModulePlanValidationError(ValueError):
    """Model-output defects, with actionable module-local diagnostics."""

    def __init__(self, issues, normalizations=()):
        self.issues = deepcopy(issues)
        self.normalizations = deepcopy(list(normalizations))
        summary = '; '.join(
            f"module {i.get('module_index', 'plan')}: {i['code']}"
            + (f" ({', '.join(i['ids'])})" if i.get('ids') else '')
            for i in issues)
        super().__init__(summary)


def module_evidence_owners(state):
    """Original Planner assignments, never display IDs or guessed relationships."""
    owners = {}
    for unit in state['narrative_plan']['sections']:
        for eid in unit['evidence_ids']:
            if unit['section_id'] not in owners.setdefault(eid, []):
                owners[eid].append(unit['section_id'])
    return owners


def normalize_module_plan(raw, state):
    units = {s['section_id']: s for s in state['narrative_plan']['sections']}
    evidence_index = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    bank = set(evidence_index)
    owners = module_evidence_owners(state)
    available = {f'{prefix}_{k}' for prefix, field in [('figure', 'images'), ('table', 'tables')]
                 for k in (state.get(field) or {})}
    required = {e for s in units.values() for e in s.get('required_evidence_ids', [])}
    if not isinstance(raw, dict) or not isinstance(raw.get('modules'), list):
        raise ModulePlanValidationError([{'code': 'invalid_modules_format'}])
    if not raw['modules']:
        raise ModulePlanValidationError([{'code': 'empty_modules'}])
    result, visuals, represented, issues, normalizations = [], set(), set(), [], []
    responsibility_owners, module_ids = {}, set()
    for index, row in enumerate(raw['modules'], 1):
        local = []
        title = row.get('title') if isinstance(row, dict) else None
        def issue(code, ids=(), **details):
            local.append({'code': code, 'module_index': index,
                          'module_title': title if isinstance(title, str) else '',
                          'ids': list(ids), **details})
        if not isinstance(row, dict) or row.get('_invalid_module'):
            issue('invalid_module_format')
            issues.extend(local)
            continue
        module_id = row.get('module_id', f'display_{index:03d}')
        if (not isinstance(module_id, str) or not re.fullmatch(r'display_[0-9]{3,}', module_id) or module_id in module_ids):
            issue('invalid_or_duplicate_module_id')
        else:
            module_ids.add(module_id)
        responsibilities = row.get('required_unit_ids', [])
        assigned = row.get('required_evidence_ids', [])
        if (not isinstance(responsibilities, list) or
                any(not isinstance(s, str) or s not in units for s in responsibilities)):
            issue('invalid_required_unit_ids')
            responsibilities = []
        if (not isinstance(assigned, list) or any(not isinstance(e, str) or e not in required for e in assigned)):
            issue('invalid_required_evidence_ids')
            assigned = []
        obligations = set(assigned)
        for sid in responsibilities:
            obligations.update(units[sid].get('required_evidence_ids', []))
        for eid in sorted(obligations):
            if eid in responsibility_owners and responsibility_owners[eid] != index:
                issue('duplicate_required_responsibility', [eid], other_module_index=responsibility_owners[eid])
            responsibility_owners[eid] = index
        evidence = row.get('evidence_ids', [])
        if isinstance(evidence, list) and all(isinstance(e, str) for e in evidence):
            added = sorted(obligations - set(evidence))
            evidence = list(evidence) + added
            if added:
                normalizations.append({'module_index': index, 'module_title': title,
                    'code': 'declared_responsibility_materialized', 'added_evidence_ids': added,
                    'required_unit_ids': list(responsibilities)})
        if not isinstance(evidence, list) or any(not isinstance(e, str) or not e for e in evidence):
            issue('invalid_evidence_ids_format')
        elif not evidence:
            issue('empty_evidence_ids')
        else:
            evidence = list(dict.fromkeys(evidence))
            unknown = [e for e in evidence if e not in bank]
            unplanned = [e for e in evidence if e in bank and e not in owners]
            if unknown:
                issue('unknown_evidence_ids', unknown)
            if unplanned:
                issue('unplanned_evidence_ids', unplanned)
        origins = row.get('source_plan_unit_ids', [])
        if not isinstance(origins, list) or any(not isinstance(s, str) or not s for s in origins):
            issue('invalid_source_plan_unit_ids_format')
        else:
            origins = list(dict.fromkeys([*origins, *responsibilities]))
            unknown = [s for s in origins if s not in units]
            if unknown:
                issue('unknown_source_plan_unit_ids', unknown)
        if not local:
            original_origins = list(origins)
            for eid in evidence:
                candidates = owners[eid]
                if set(candidates) & set(original_origins):
                    continue
                if len(candidates) == 1:
                    if candidates[0] not in origins:
                        origins.append(candidates[0])
                else:
                    issue('ambiguous_evidence_origin', [eid], candidate_source_plan_unit_ids=candidates)
            unrelated = [sid for sid in original_origins
                         if not set(units[sid]['evidence_ids']) & set(evidence)]
            if unrelated:
                issue('unrelated_source_plan_unit_ids', unrelated)
            if origins != original_origins:
                normalizations.append({'module_index': index, 'module_title': title,
                    'code': 'unique_evidence_origin_completed', 'declared_source_plan_unit_ids': original_origins,
                    'normalized_source_plan_unit_ids': list(origins),
                    'evidence_ids': list(evidence)})
            represented.update(evidence)
        brief = row.get('writing_brief')
        if not isinstance(title, str) or not title.strip():
            issue('missing_module_title')
        if not isinstance(brief, str) or not brief.strip():
            issue('missing_writing_brief')
        selected_visuals = row.get('visual_ids', [])
        reserve_visuals = row.get('reserve_visual_ids', [])
        rationales = row.get('visual_rationales', {})
        if (not isinstance(reserve_visuals, list) or any(not isinstance(v, str) or v not in available for v in reserve_visuals)):
            issue('invalid_reserve_visual_ids')
            reserve_visuals = []
        if (not isinstance(rationales, dict) or any(k not in available or not isinstance(v, str) for k,v in rationales.items())):
            issue('invalid_visual_rationales')
        for field in ('research_question', 'communication_goal', 'selection_rationale'):
            if not isinstance(row.get(field, ''), str):
                issue('invalid_editorial_brief', field=field)
        if not isinstance(selected_visuals, list) or any(not isinstance(v, str) or not v for v in selected_visuals):
            issue('invalid_visual_ids_format')
        else:
            offered = selected_visuals + reserve_visuals
            unknown = [v for v in selected_visuals if v not in available]
            repeated = [v for v in dict.fromkeys(offered)
                        if offered.count(v) > 1 or v in visuals]
            if unknown:
                issue('unknown_visual_ids', unknown)
            if repeated:
                issue('duplicate_visual_ids', repeated)
            visuals.update(offered)
        issues.extend(local)
        if local:
            continue
        support = sorted({e for sid in origins for e in units[sid]['evidence_ids']} & bank - set(evidence))
        result.append({'module_id': module_id, 'title': title.strip(),
                       'writing_brief': brief.strip(), 'source_plan_unit_ids': origins,
                       'evidence_ids': evidence, 'required_evidence_ids': sorted(required & set(evidence)),
                       'required_unit_ids': list(responsibilities), 'support_evidence_ids': support,
                       'available_evidence_ids': list(dict.fromkeys([*evidence, *support])),
                       'visual_ids': list(selected_visuals),
                       'reserve_visual_ids': list(reserve_visuals), 'visual_rationales': deepcopy(rationales),
                       **{field: row.get(field, '').strip() for field in ('research_question', 'communication_goal', 'selection_rationale')},
                       'presentation_style': row.get('presentation_style')
                           if row.get('presentation_style') in ('plain', 'topics', 'steps') else 'plain',
                       'module_purpose': row.get('module_purpose')
                           if row.get('module_purpose') in ('primary', 'context', 'supporting') else 'primary'})
    missing = sorted(required - represented)
    if missing:
        issues.append({'code': 'missing_indispensable_evidence', 'ids': missing})
    if issues:
        raise ModulePlanValidationError(issues, normalizations)
    # An explicitly assigned obligation has one owner; other modules may use it as context.
    for index, module in enumerate(result, 1):
        module['required_evidence_ids'] = [eid for eid in module['required_evidence_ids']
                                           if responsibility_owners.get(eid, index) == index]
        module['required_assertions'] = [{'evidence_id': eid, 'claim': evidence_index[eid].get('claim', '')}
                                          for eid in module['required_evidence_ids']]
        for assertion in module['required_assertions']:
            reasons = [u.get('required_evidence_rationales', {}).get(assertion['evidence_id']) for u in units.values()]
            assertion['preservation_reasons'] = list(dict.fromkeys(r for r in reasons if isinstance(r, str) and r))
    from src.config.poster_config import load_config
    font = load_config()['typography']['sizes']['body_text']
    scale = float(state['poster_width'])/54 * float(state['poster_height'])/36 * (44/float(font))**2
    for module in result:
        module['soft_word_range'] = [round(280*scale/len(result)), round(420*scale/len(result))]
    decisions = {v: {'decision': 'reserve', 'reason': 'Not selected by the sample Curator', 'module_id': None} for v in sorted(available)}
    for module in result:
        for field, decision in [('visual_ids', 'selected'), ('reserve_visual_ids', 'optional_same_module_probe')]:
            for vid in module[field]:
                decisions[vid] = {'decision': decision, 'module_id': module['module_id'],
                    'reason': module['visual_rationales'].get(vid, 'No rationale supplied')}
    return {'version': BODY_VERSION, 'assembly_version': 'module_assignment_v2',
            'modules': result, 'source_normalizations': normalizations,
            'visual_decisions': decisions,
            'editorial_focus': state['narrative_plan'].get('editorial_focus', ''),
            'required_evidence_ids': sorted(required), 'narrative_summary': state['narrative_plan'].get('narrative_summary', '')}


def finalize_modules(state):
    """Install exact verified prose; fail rather than publish a critical empty module."""
    plan = state['sample_module_plan']
    claims = (state.get('verified_claims') or {}).get('claims', [])
    candidates = (state.get('poster_claims') or {}).get('claims', [])
    index = {c['claim_id']: c for c in claims}
    mandatory = {c['claim_id'] for c in candidates if c.get('essential') and not state.get('joint_preparation')}
    if not mandatory <= index.keys():
        raise ValueError('An essential module expression failed scientific verification')
    def covered_required(claim):
        supported = {e for row in claim.get('support_map', []) for e in row['evidence_ids']}
        return set(claim.get('covered_required_evidence_ids', [])) & supported
    represented = {e for c in claims for e in covered_required(c)}
    if not set(plan['required_evidence_ids']) <= represented:
        raise ValueError('Verified module prose is missing indispensable evidence')
    protected = set(mandatory)
    # Protect one supported expression per indispensable source, not every
    # expression that happens to cite the same evidence.
    for eid in plan['required_evidence_ids']:
        owners = [c for c in claims if eid in covered_required(c)]
        owner = min(owners, key=lambda c: (c['claim_id'] not in protected, len(c['text'])))
        protected.add(owner['claim_id'])
    board = build_module_board(state, claims, protected)
    sections = board['spatial_content_plan']['sections']
    state['verified_module_board'] = deepcopy(board)
    state['module_body_report'] = {'version': BODY_VERSION, 'modules': len(sections),
                                   'verified_items': len(claims), 'words': sum(len(c['text'].split()) for c in claims),
                                   'module_coverage': [{'module_id': m['module_id'], 'required_evidence_ids': m['required_evidence_ids']}
                                                       for m in plan['modules']],
                                   'required_claim_ids': sorted(i['claim_id'] for i in board['editorial_selection']['items']
                                                                if i['disposition'] == 'required')}
    _atomic_json(Path(state['output_dir'])/'content/verified_module_board.json', board)


def build_module_board(state, claims, protected):
    """Build display data; callers explicitly supply draft or verified claims."""
    plan = state['sample_module_plan']
    index = {c['claim_id']: c for c in claims}
    sections = []
    for module in plan['modules']:
        body = [c for c in claims if c.get('display_module_id') == module['module_id']]
        if not body:
            if state.get('joint_preparation') and not module['required_evidence_ids']:
                continue
            raise ValueError('A planned display module has no verified body')
        local = {c['claim_id'] for c in body}
        if any(not set(c.get('requires_claim_ids', [])) <= local for c in body):
            raise ValueError('Verified prose lost a local prerequisite')
        core = sorted(body, key=lambda c: (
            c.get('discourse_kind') not in {'definition', 'goal', 'method', 'result', 'interpretation'},
            c['claim_id'] not in protected))[:3]
        sections.append({'section_id': module['module_id'], 'section_title': module['title'],
                         'title_candidates': [module['title']], 'vertical_priority': 'middle',
                         'claim_ids': [c['claim_id'] for c in body], 'text_content': [c['text'] for c in body],
                         'core_claim_ids': [c['claim_id'] for c in core],
                         'visual_assets': [{'visual_id': v} for v in module['visual_ids']],
                         'narrative_style': 'explanatory', 'module_purpose': module['module_purpose'],
                         'presentation_style': module['presentation_style'],
                         'claim_layout': [{'claim_id': c['claim_id'], 'kind': c.get('discourse_kind', ''),
                                           'requires_claim_ids': c.get('requires_claim_ids', []),
                                           'parent_claim_id': c.get('parent_claim_id'),
                                           'display_label': c.get('display_label', ''),
                                           'step_index': c.get('step_index')} for c in body]})
    from src.layout.editorial_selection import sanitize_selection
    board = {'spatial_content_plan': {'sections': sections}}
    edges = [(c['claim_id'], dep) for c in claims for dep in c.get('requires_claim_ids', [])]
    board['editorial_selection'] = sanitize_selection(None, index, visible=index, required=protected, dependencies=edges)
    from src.layout.editorial import prepare_board
    board = prepare_board(board, state, raw_sections=sections)
    for section in board['spatial_content_plan']['sections']:
        section['editorial']['module_prose_order'] = True
        section['editorial']['active'] = True
    return board


def sample_claim_verifier_node(state):
    from src.agents.claim_verifier import claim_verifier_node
    if state.get('joint_preparation'):
        from src.workflow.joint_preparation import verify_selected_science
        state = verify_selected_science(state)
    else:
        state = claim_verifier_node(state)
    if state.get('errors') or state.get('_joint_interrupted'):
        return state
    try:
        from src.workflow.sample_module_writing import module_coverage_feedback, repair_verified_modules
        if any('verification_failure' in d.get('error_types', [])
               for d in (state.get('verification_report') or {}).get('details', [])):
            raise ValueError('Scientific verification request/format failed; editorial repair is not a retry')
        feedback = module_coverage_feedback(state)
        if feedback and state.get('joint_preparation'):
            state['joint_verification_feedback'] = feedback
            state['verification_passed'] = False
            return state
        if feedback:
            state = repair_verified_modules(state, feedback)
            state = claim_verifier_node(state)
            if state.get('errors'):
                return state
            if module_coverage_feedback(state):
                raise ValueError('Repaired module prose still lacks verified indispensable information')
        # Corrections/rejections can change the context that was supplied when
        # another expression's local relationship was verified. Recheck only
        # affected modules, once, against the actual remaining final wording.
        current = (state.get('verified_claims') or {}).get('claims', [])
        contexts = {}
        for claim in current:
            contexts.setdefault(claim['display_module_id'], []).append(
                {'claim_id': claim['claim_id'], 'text': claim['text']})
        affected = [c for c in current if (c.get('module_context') or {}).get('items') != contexts[c['display_module_id']]]
        if affected:
            isolated = dict(state)
            refreshed = deepcopy(affected)
            for claim in refreshed:
                claim.setdefault('module_context', {})['items'] = contexts[claim['display_module_id']]
            isolated['poster_claims'] = {'claims': refreshed}
            isolated['errors'] = []
            isolated['output_dir'] = str(Path(state['output_dir'])/'context_verification')
            isolated = claim_verifier_node(isolated)
            if isolated.get('_joint_interrupted'):
                state['_joint_interrupted'] = True
                return state
            if isolated.get('fatal_generation_error'):
                state['fatal_generation_error'] = True
            checked = (isolated.get('verified_claims') or {}).get('claims', [])
            expected = {c['claim_id']: c['text'] for c in refreshed}
            if (isolated.get('errors') or {c['claim_id']: c['text'] for c in checked} != expected):
                if state.get('joint_preparation') and not isolated.get('errors'):
                    state['joint_verification_feedback'] = {c['display_module_id']: {
                        'reason': 'final_context_changed', 'module_id': c['display_module_id']}
                        for c in refreshed}
                    state['verification_passed'] = False
                    return state
                raise ValueError('Final module context could not be verified without another rewrite')
            by_id = {c['claim_id']: c for c in checked}
            state['verified_claims'] = {'claims': [by_id.get(c['claim_id'], c) for c in current]}
            state['verification_report']['final_context_verification'] = isolated['verification_report']
            _atomic_json(Path(state['output_dir'])/'content/verification_report.json', state['verification_report'])
            _atomic_json(Path(state['output_dir'])/'content/verified_claims.json', state['verified_claims'])
        finalize_modules(state)
    except (ValueError, KeyError, TypeError) as exc:
        if state.get('joint_preparation'):
            from src.workflow.sample_errors import record_sample_error
            record_sample_error(state, exc, 'module_finalization_failed', output_error=isinstance(exc, ValueError))
        state['verification_passed'] = False
        state.setdefault('errors', []).append(f'sample_claim_verifier: {exc}')
    return state
