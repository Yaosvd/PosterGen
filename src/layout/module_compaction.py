"""Sample-local coordinated wording variants; never change scientific ownership."""
from copy import deepcopy
import json
from pathlib import Path

from utils.evidence_utils import evidence_by_id, validate_claim_numbers
from utils.grounded_content import claim_root_id, merge_evidence_banks, rematerialize_board
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from utils.agent_policy import apply_agent_policy
from utils.persistence import digest
from src.workflow.module_planning_requests import ModulePlanningRequests
from src.workflow.sample_module_writing import verification_source_context

VERSION = 'sample_module_compaction_v1'
# This bounds repair work, not scientific admission or the size of a valid module.
MAX_CLAIMS = 8


def _preserves_required_coverage(source, checked):
    if checked is None:
        return False
    supported = {e for row in checked.get('support_map', []) if isinstance(row, dict) and row.get('supported') is True
                 for e in row.get('evidence_ids', [])}
    return set(source.get('covered_required_evidence_ids', [])) <= (
        set(checked.get('covered_required_evidence_ids', [])) & supported)


def eligible_sources(state, section, claims):
    from src.layout.editorial import locked
    ids = section.get('claim_ids') or []
    if (state.get('generation_route') != 'optimization_family' or
            not state.get('sample_module_plan') or locked(state) or
            not 2 <= len(ids) <= MAX_CLAIMS or len(ids) != len(set(ids))):
        return []
    sources = [claims.get(cid) for cid in ids]
    if any(not c or c.get('verified') is not True or c.get('body_contract') != 'sample_body_v2'
           or c.get('display_module_id') != section['section_id'] for c in sources):
        return []
    roots = [claim_root_id(c) for c in sources]
    return sources if len(roots) == len(set(roots)) else []


def plan_module_actions(state, board, report, claims, maximum):
    """An early failed beam must not hide the largest remaining module loads."""
    if (report.get('reason_code') != 'NO_FAST_FEASIBLE_VARIANT' or
            not (report.get('observed_blockers') or {}).get('estimated_height')):
        return []
    from src.layout.content_guards import claim_recovery_allowed
    candidates = []
    for section in board['spatial_content_plan']['sections']:
        sources = eligible_sources(state, section, claims)
        if not sources or any(not claim_recovery_allowed(state, section['section_id'], c) for c in sources):
            continue
        words = sum(len(c['text'].split()) for c in sources)
        if words < 40:
            continue
        # First give untouched modules a turn; repeated wording work is bounded
        # by the same family/sample capacity ledger as ordinary claim variants.
        previous = max(int(c.get('module_compaction_count', 0)) for c in sources)
        candidates.append((previous, -words, section['section_id']))
    return [{'operation': 'create_compact_module', 'section_id': sid,
             'reason': 'reduce complete verified module load after diagnosed height failure'}
            for _, _, sid in sorted(candidates)[:maximum]]


def _request(state, journal, name, prompt):
    scoped = ModulePlanningRequests(state, prompt, directory=str(journal.root.relative_to(state['output_dir'])/name))
    role = ('Audit the supplied candidate against original evidence and return only an audit verdict; never copy the input.'
            if name.startswith('preservation_') else
            'Preserve all grounded information while coordinating module prose.')
    agent = LangGraphAgent(role,
                           apply_agent_policy(state['text_model'], 'content_optimizer'), state, 'content_optimizer')
    raw = scoped.request(0, agent, prompt)
    if not isinstance(raw, str):
        scoped.write('validation.json', status='invalid_response_content')
        return None
    try:
        parsed = extract_json(raw)
    except (ValueError, TypeError):
        scoped.write('validation.json', status='invalid_json')
        return None
    scoped.write('parsed_00.json', parsed=parsed)
    return parsed


def compact_module(optimizer, state, board, action, claims, supplemental_bank):
    """Return an entirely verified batch, or nothing. Caller owns the round charge."""
    section = next((s for s in board['spatial_content_plan']['sections']
                    if s['section_id'] == action['section_id']), {})
    sources = eligible_sources(state, section, claims)
    if not sources:
        return None, [], {'status': 'ineligible_module'}
    from src.layout.content_guards import claim_recovery_allowed
    if any(not claim_recovery_allowed(state, section['section_id'], c) for c in sources):
        return None, [], {'status': 'excluded_module_root'}
    evidence = evidence_by_id(merge_evidence_banks({**state, 'supplemental_evidence_bank': supplemental_bank}))
    ids = list(dict.fromkeys(e for c in sources for e in c.get('evidence_ids', [])))
    if not ids or any(e not in evidence for e in ids):
        return None, [], {'status': 'missing_source_evidence'}
    payload = {'version': VERSION, 'section_title': section.get('section_title'),
               'claims': sources, 'evidence': [evidence[e] for e in ids],
               'source_context': verification_source_context(state, [evidence[e] for e in ids]),
               'target_total_characters': round(sum(len(c['text']) for c in sources)*0.65),
               'neighbor_tasks': state['sample_module_plan'].get('modules', [])}
    prompt = load_prompt('config/prompts/compact_sample_module.txt')+'\nINPUT DATA:\n'+json.dumps(payload, ensure_ascii=False)
    journal = ModulePlanningRequests(state, prompt,
        directory=f'content/module_compaction/{digest(section["section_id"])[:12]}/{digest(prompt)[:16]}')
    report = {'version': VERSION, 'status': 'rejected', 'source_claim_ids': [c['claim_id'] for c in sources],
              'root_claim_ids': [claim_root_id(c) for c in sources], 'claim_limit': MAX_CLAIMS,
              'request_directory': str(journal.root.relative_to(state['output_dir'])),
              'before_characters': sum(len(c['text']) for c in sources)}

    def reject(reason):
        report['reason'] = reason
        journal.write('result.json', **report)
        return None, [], report

    draft = _request(state, journal, 'draft', prompt)
    rows = draft.get('claims') if isinstance(draft, dict) else None
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows) or
            [r.get('source_claim_id') for r in rows] != report['source_claim_ids']):
        return reject('missing_duplicate_foreign_or_reordered_sources')
    candidates = []
    for source, row in zip(sources, rows):
        text, cites = row.get('text'), row.get('evidence_ids')
        # Merely citing an indispensable excerpt did not make its whole assertion
        # this expression's responsibility. Preserve the original verified verdict.
        required = set(source.get('covered_required_evidence_ids', []))
        if (not isinstance(text, str) or not text.strip() or not isinstance(cites, list) or not cites or
                any(not isinstance(e, str) or e not in source.get('evidence_ids', []) for e in cites) or
                not required <= set(cites) or len(text.strip()) > len(source['text']) or
                not validate_claim_numbers(text, cites, evidence)[0]):
            return reject('invalid_text_evidence_or_required_information')
        candidate = deepcopy(source)
        for key in ('support_map', 'covered_required_evidence_ids', 'verification_report', 'repaired'):
            candidate.pop(key, None)
        candidate.update(claim_id='cv_module_'+digest([journal.input_digest, source['claim_id'], text.strip()])[:20],
                         text=text.strip(), evidence_ids=list(dict.fromkeys(cites)),
                         original_expression=source['text'],
                         required_evidence_ids=sorted((set(source.get('required_evidence_ids', [])) & set(cites)) | required),
                         root_claim_id=claim_root_id(source), verified=False,
                         module_compaction_count=int(source.get('module_compaction_count', 0))+1)
        candidates.append(candidate)
    if sum(len(c['text']) for c in candidates) >= report['before_characters']:
        return reject('no_net_compaction')
    mapping = {s['claim_id']: c['claim_id'] for s, c in zip(sources, candidates)}
    # Dependencies refer to current variants, but keep their original records too.
    root_mapping = {claim_root_id(s): c['claim_id'] for s, c in zip(sources, candidates)}
    for c, source in zip(candidates, sources):
        c['original_dependency_records'] = {key: deepcopy(source.get(key))
                                            for key in ('requires_claim_ids', 'parent_claim_id')}
        dependencies = source.get('requires_claim_ids', [])
        if any(d not in mapping and d not in root_mapping for d in dependencies):
            return reject('nonlocal_prerequisite')
        c['requires_claim_ids'] = [mapping.get(d, root_mapping.get(d)) for d in dependencies]
        parent = source.get('parent_claim_id')
        if parent and parent not in mapping and parent not in root_mapping:
            return reject('nonlocal_parent')
        c['parent_claim_id'] = mapping.get(parent, root_mapping.get(parent)) if parent else None
    context = [{'claim_id': c['claim_id'], 'text': c['text']} for c in candidates]
    for c in candidates:
        c.setdefault('module_context', {})['items'] = deepcopy(context)
    journal.write('candidate.json', claims=candidates)
    verified = []
    for candidate in candidates:
        checked, details = optimizer._verify_candidate(state, candidate, supplemental_bank)
        journal.write(f'verification_{len(verified):02d}.json', report=details)
        source = sources[len(verified)]
        if (checked is None or checked.get('verified') is not True or
                checked.get('claim_id') != candidate['claim_id'] or
                not _preserves_required_coverage(source, checked)):
            return reject('scientific_verification_failed')
        verified.append(checked)
    final_context = [{'claim_id': c['claim_id'], 'text': c['text']} for c in verified]
    if final_context != context:
        # One bounded recheck against actual final wording; never another rewrite loop.
        for c in verified:
            c.setdefault('module_context', {})['items'] = deepcopy(final_context)
        rechecked = []
        for source, c in zip(sources, verified):
            checked, details = optimizer._verify_candidate(state, c, supplemental_bank)
            journal.write(f'context_verification_{len(rechecked):02d}.json', report=details)
            if (checked is None or checked.get('verified') is not True or checked.get('claim_id') != c['claim_id'] or
                    checked.get('text') != c['text'] or
                    not _preserves_required_coverage(source, checked)):
                return reject('final_context_verification_failed')
            rechecked.append(checked)
        verified = rechecked
    for index, (source, candidate) in enumerate(zip(sources, verified)):
        if len(candidate['text']) > len(source['text']):
            return reject('verified_text_expanded')
        # Same existing editorial-preservation audit, now archived per batch item.
        audit = {'operation': 'create_compact_variant', 'source_claim': source,
                 'candidate_text': candidate['text'], 'section_title': section.get('section_title'),
                 'current_section_text': [c['text'] for c in verified],
                 'other_visible_text': [t for s in board['spatial_content_plan']['sections']
                                        if s['section_id'] != section['section_id'] for t in s.get('text_content', [])],
                 'excluded_module_claims': [c.get('text', '') for c in claims.values()
                     if not claim_recovery_allowed(state, section['section_id'], c)],
                 'original_paper_excerpts': [evidence[e] for e in candidate['evidence_ids']]}
        prompt = (optimizer.editorial_prompt+'\nINPUT DATA:\n'+json.dumps(audit, ensure_ascii=False)+
                  '\nEND INPUT DATA. Return only the audit verdict below, with boolean values based on your assessment. '
                  'Do not return source_claim, candidate_text, excerpts or any other input fields.\n'
                  '{"grounded":false,"meaning_preserved":false,"relevant":false,'
                  '"non_redundant":false,"style_improved":false,"reason":"brief explanation"}')
        verdict = _request(state, journal, f'preservation_{index:02d}', prompt)
        if (not isinstance(verdict, dict) or
                any(type(verdict.get(key)) is not bool for key in ('grounded', 'meaning_preserved'))):
            return reject('editorial_preservation_invalid_response')
        if verdict['grounded'] is not True or verdict['meaning_preserved'] is not True:
            return reject('editorial_preservation_failed')
        candidate.update(variant_kind='module_compact', created_iteration=int((state.get('iteration_context') or {}).get('iteration', 0)),
                         created_candidate_id=(state.get('current_candidate') or {}).get('candidate_id'), outcomes=[])
    report['after_characters'] = sum(len(c['text']) for c in verified)
    if report['after_characters'] >= report['before_characters']:
        return reject('verification_removed_compaction')
    result = deepcopy(board)
    target = next(s for s in result['spatial_content_plan']['sections'] if s['section_id'] == section['section_id'])
    target['claim_ids'] = [c['claim_id'] for c in verified]
    # Explicit layout hints follow the same roots instead of disappearing on replacement.
    for field in ('core_claim_ids',):
        if field in target: target[field] = [mapping.get(cid, cid) for cid in target[field]]
    hints = list(target.get('claim_layout', [])) + list((target.get('editorial') or {}).get('items', []))
    for row in hints:
        row['claim_id'] = mapping.get(row.get('claim_id'), row.get('claim_id'))
        row['requires_claim_ids'] = [mapping.get(cid, root_mapping.get(cid, cid)) for cid in row.get('requires_claim_ids', [])]
        row['parent_claim_id'] = mapping.get(row.get('parent_claim_id'), root_mapping.get(row.get('parent_claim_id'), row.get('parent_claim_id')))
    rematerialize_board(result, {**claims, **{c['claim_id']: c for c in verified}})
    report.update(status='verified_pending_exact_fit', result_claim_ids=[c['claim_id'] for c in verified])
    journal.write('result.json', **report)
    return result, verified, report


def measure_module_progress(agent, before_state, after_state, before, after, family_id, actions, *, fixed_zones=None):
    """Local exact-height probes permit another charged round, never admit a fit."""
    ids = {a['section_id'] for a in actions if a.get('operation') == 'create_compact_module'}
    if not ids:
        return None
    from src.layout.families import LayoutFamilyRegistry
    zones = fixed_zones if fixed_zones is not None else LayoutFamilyRegistry().get(family_id).zones
    width = float(after_state['poster_width'])-2*agent.poster_margin
    effective = float(after_state['poster_height'])-2*agent.poster_margin
    body_height = effective*(1-agent.title_height_fraction)
    dimensions = sorted({(round(float(z['width'])*width, 5), round(float(z['height'])*body_height, 5)) for z in zones})
    old_state = {**before_state, 'styling_interfaces': before_state.get('styling_interfaces') or {}}
    new_state = {**after_state, 'styling_interfaces': after_state.get('styling_interfaces') or {}}
    # The final fitter normalizes extractive labels and current-root dependency
    # hints too. Probes must not obtain apparent savings by losing those styles.
    from src.layout.editorial import prepare_board
    previous = {s['section_id']: s for s in prepare_board(before, old_state)['spatial_content_plan']['sections']}
    current = {s['section_id']: s for s in prepare_board(after, new_state)['spatial_content_plan']['sections']}
    rows = []
    for sid in sorted(ids):
        for w, h in dimensions:
            old = float(agent._calculate_precise_section_height(previous[sid], w, old_state, h))
            new = float(agent._calculate_precise_section_height(current[sid], w, new_state, h))
            rows.append({'section_id': sid, 'width_inches': w, 'height_limit_inches': h,
                         'before_height_inches': round(old, 5), 'after_height_inches': round(new, 5),
                         'reduction_inches': round(old-new, 5)})
    return {'scope': 'canonical_family_zone_probes_only', 'certifies_feasible_layout': False,
            'improved': bool(rows) and all(r['reduction_inches'] >= -0.005 for r in rows)
                        and any(r['reduction_inches'] >= 0.05 for r in rows), 'measurements': rows}
