"""Whole-module writing with explicit obligations and reusable raw responses."""
from copy import deepcopy
import json
import re
from pathlib import Path

from jinja2 import Template
from utils.persistence import _atomic_json
from utils.evidence_utils import (
    normalize_formula_multiplication, validate_claim_numbers,
    extract_numbers, contains_comparison_language, normalize_space,
)
from utils.langgraph_utils import extract_json
from src.workflow.module_planning_requests import ModulePlanningRequests
from src.workflow.sample_modules import BODY_VERSION, ModulePlanValidationError


def verification_source_context(state, evidence):
    """Resolve cited excerpts to their exact original chunk, never by topic."""
    sections = state.get('section_chunks') or (state.get('structured_sections') or {}).get('paper_sections', [])
    chunks, unavailable = {}, []
    for item in evidence:
        source = item.get('source') or {}
        sid, index = source.get('section_id'), source.get('chunk_index', 0)
        matches = [s for s in sections if s.get('section_id') == sid and
                   s.get('chunk_index', 0) == index] if sid is not None else []
        excerpt = normalize_space(item.get('source_excerpt', ''))
        if (len(matches) != 1 or not excerpt or
                excerpt not in normalize_space(matches[0].get('content', ''))):
            unavailable.append(item['evidence_id'])
            continue
        key = (sid, index)
        if key not in chunks:
            row = matches[0]
            chunks[key] = {'section_id': sid, 'chunk_index': index,
                           'section_name': row.get('section_name', ''),
                           'content': row['content'], 'evidence_ids': []}
        if item['evidence_id'] not in chunks[key]['evidence_ids']:
            chunks[key]['evidence_ids'].append(item['evidence_id'])
    return {'chunks': list(chunks.values()), 'unavailable_evidence_ids': unavailable}


def clean_internal_evidence_markers(text, ids, evidence):
    """Remove only machine citation annotations, never scientific parentheses."""
    notes = []
    def replace(match):
        marked = re.findall(r'ev_\d+', match.group())
        if any(eid in evidence[cid].get('source_excerpt', '') for eid in marked for cid in ids):
            return match.group()
        if not set(marked) <= set(ids):
            raise ValueError('Visible evidence annotation contains an undeclared citation')
        notes.append({'kind': 'internal_evidence_annotation', 'removed': match.group(), 'evidence_ids': marked})
        return ' ' if (match.start() and match.end() < len(text) and
                       text[match.start()-1].isalnum() and text[match.end()].isalnum()) else ''
    result = re.sub(r'\s*\(\s*ev_\d+(?:\s*[,;]\s*ev_\d+)*\s*\)', replace, text)
    return result, notes


def normalize_verifier_coverage(text, result):
    """Canonicalize separating commas only after a positive whole-text verdict."""
    if result.get('supported') is not True or result.get('relationships_supported') is not True:
        return result, []
    text = ' '.join(str(text).split())
    rows = result.get('coverage')
    if not isinstance(rows, list) or not rows:
        return result, []
    spans, covered = [], [False] * len(text)
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get('supported') is not True:
            return result, []
        quote = ' '.join(str(row.get('quote') or '').split())
        starts = [m.start() for m in re.finditer(re.escape(quote), text)] if quote else []
        if len(starts) != 1:
            return result, []
        start = starts[0];end = start + len(quote)
        spans.append([start, end, index]);covered[start:end] = [True] * len(quote)
    missing = [i for i, c in enumerate(text) if not covered[i] and not c.isspace()]
    if not missing or any(text[i] != ',' for i in missing):
        return result, []
    normalized, notes = deepcopy(result), []
    for position in missing:
        if position + 1 >= len(text) or not text[position+1].isspace():
            return result, []
        nesting = 0
        for char in text[:position]:
            if char in '([{': nesting += 1
            elif char in ')]}': nesting = max(0, nesting - 1)
        if nesting:
            return result, []
        before = [s for s in spans if s[1] <= position and not text[s[1]:position].strip()]
        after = [s for s in spans if s[0] > position and not text[position+1:s[0]].strip()]
        if not before or not after:
            return result, []
        left, right = max(before, key=lambda s:s[1]), min(after, key=lambda s:s[0])
        if len(text[left[0]:left[1]].split()) < 2 or len(text[right[0]:right[1]].split()) < 2:
            return result, []
        if text[:position].rstrip()[-1:].isdigit() and text[position+1:].lstrip()[:1].isdigit():
            return result, []
        old = normalized['coverage'][left[2]]['quote']
        normalized['coverage'][left[2]]['quote'] = text[left[0]:position+1]
        notes.append({'kind':'separating_comma', 'row':left[2], 'before':old,
                      'after':normalized['coverage'][left[2]]['quote']})
        left[1] = position + 1
    normalized['coverage_format_normalizations'] = notes
    return normalized, notes


def normalize_body(raw, module, state):
    rows = raw.get('claims') if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{module['module_id']}: empty/invalid module body")
    evidence = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    allowed = set(module.get('available_evidence_ids', module['evidence_ids']))
    units = {u['section_id']: u for u in state['narrative_plan']['sections']}
    body, local = [], {}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict): raise ValueError('Invalid module body item')
        item = row.get('item_id')
        if not isinstance(item, str) or not item or item in local:
            raise ValueError('Module writer returned missing or duplicate item identities')
        text = row.get('text')
        ids = row.get('evidence_ids')
        if (not isinstance(text, str) or not text.strip() or not isinstance(ids, list) or not ids or
                any(not isinstance(e, str) or e not in allowed for e in ids)):
            raise ValueError(f'{module["module_id"]}/{item}: invalid text or foreign evidence')
        ids = list(dict.fromkeys(ids))
        text, annotations = clean_internal_evidence_markers(text.strip(), ids, evidence)
        text = normalize_formula_multiplication(text)
        if not text.strip():
            raise ValueError('Module prose is empty after removing internal evidence annotations')
        ok, unsupported = validate_claim_numbers(text, ids, evidence)
        if not ok: raise ValueError(f'{module["module_id"]}/{item}: unsupported numbers {unsupported}')
        origins = [sid for sid in module['source_plan_unit_ids'] if set(units[sid]['evidence_ids']) & set(ids)]
        cid = f"pc_{module['module_id']}_{index:03d}"
        local[item] = cid
        refs = row.get('requires_item_ids', [])
        parent = row.get('parent_item_id')
        if not isinstance(refs, list) or any(not isinstance(r, str) for r in refs) or (parent is not None and not isinstance(parent, str)):
            raise ValueError('Invalid module dependency format')
        body.append({'claim_id': cid, 'text': text, 'evidence_ids': ids,
            'section_id': origins[0] if len(origins) == 1 else '', 'source_plan_unit_ids': origins,
            'body_contract': BODY_VERSION, 'display_module_id': module['module_id'],
            'required_evidence_ids': sorted(set(module['required_evidence_ids']) & set(ids)),
            'essential': row.get('essential') is True, 'discourse_kind': row.get('kind', ''),
            'display_label': row.get('display_label', ''), 'step_index': row.get('step_index'),
            'claim_type': row.get('claim_type', 'descriptive'),
            'risk_level': 'high' if extract_numbers(text) or contains_comparison_language(text) else row.get('risk_level', 'low'),
            '_item': item, '_refs': refs, '_parent': parent})
        if annotations:
            body[-1]['display_normalizations'] = annotations
    for claim in body:
        refs = [*claim['_refs'], *([claim['_parent']] if claim['_parent'] else [])]
        if any(r not in local or r == claim['_item'] for r in refs):
            raise ValueError('Module writer returned foreign or self prerequisite')
        claim['requires_claim_ids'] = list(dict.fromkeys(local[r] for r in refs))
        claim['parent_claim_id'] = local.get(claim['_parent'])
        claim['module_context'] = {'task': module['writing_brief'],
                                  'items': [{'claim_id': c['claim_id'], 'text': c['text']} for c in body]}
    for claim in body:
        for key in ('_item', '_refs', '_parent'): claim.pop(key)
    return body


def write_modules(state, agent, template):
    if state.get('joint_preparation'):
        return write_joint_poster(state, agent)
    plan = state['sample_module_plan']
    index = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    claims = []
    for module in plan['modules']:
        prompt = Template(template).render(
            narrative_summary=plan.get('narrative_summary', state['narrative_plan'].get('narrative_summary', '')),
            module_context=json.dumps([{'title': m['title'], 'writing_brief': m['writing_brief']} for m in plan['modules']], ensure_ascii=False),
            section=json.dumps(module, ensure_ascii=False),
            source_context=json.dumps(verification_source_context(state,
                [index[e] for e in module.get('available_evidence_ids', module['evidence_ids'])]), ensure_ascii=False),
            evidence=json.dumps([index[e] for e in module.get('available_evidence_ids', module['evidence_ids'])], ensure_ascii=False))
        journal = ModulePlanningRequests(state, prompt, directory=f"content/module_writing/{module['module_id']}",
                                         kind='module_body_correction', scope=module['module_id'])
        content = journal.request(0, agent, prompt)
        try:
            raw = extract_json(content)
            journal.write('parsed_00.json', parsed=raw)
            body = normalize_body(raw, module, state)
        except (ValueError, TypeError) as exc:
            journal.write('validation_00.json', status='rejected', error=str(exc))
            repair_prompt = prompt + '\nCorrect ONLY this module body. All evidence/conditions remain required.\nERROR: '+str(exc)+'\nDRAFT: '+str(content)
            content = journal.request(1, agent, repair_prompt)
            raw = extract_json(content);journal.write('parsed_01.json', parsed=raw)
            body = normalize_body(raw, module, state)
        journal.write('body.json', claims=body, status='candidate')
        claims.extend(body)
    state['poster_claims'] = {'claims': claims}
    _atomic_json(Path(state['output_dir'])/'content/poster_claims.json', state['poster_claims'])
    state['current_agent'] = 'claim_writer'
    return state


def normalize_joint_body(raw, state):
    modules = state['sample_module_plan']['modules']
    rows = raw.get('modules') if isinstance(raw, dict) else None
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows) or
            [r.get('module_id') for r in rows] != [m['module_id'] for m in modules]):
        raise ValueError('Global Writer must return each planned module once in order')
    claims = [c for row, module in zip(rows, modules) for c in normalize_body(row, module, state)]
    for claim in claims:
        claim['essential_suggestion'] = claim.pop('essential', False)
        claim['essential'] = False  # Mandatory source obligations are finalized by actual verification.
        claim['verified'] = False
    return claims


def write_joint_poster(state, agent):
    from utils.langgraph_utils import load_prompt
    modules = state['sample_module_plan']['modules']
    index = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    evidence = {m['module_id']: [index[e] for e in m['available_evidence_ids']] for m in modules}
    selected = list(dict.fromkeys(e for m in modules for e in m['available_evidence_ids']))
    prompt = Template(load_prompt('config/prompts/write_joint_poster.txt')).render(
        capacity=json.dumps(state['family_capacity'], ensure_ascii=False),
        narrative_summary=state['sample_module_plan'].get('narrative_summary', ''),
        modules=json.dumps(modules, ensure_ascii=False), evidence=json.dumps(evidence, ensure_ascii=False),
        source_context=json.dumps(verification_source_context(state, [index[e] for e in selected]), ensure_ascii=False))
    history = ModulePlanningRequests(state, prompt, directory='content/joint_writing',
                                     kind='joint_writer_format_correction', scope='poster')
    content = history.request(0, agent, prompt)
    raw = None
    try:
        raw = extract_json(content)
        history.write('parsed_00.json', parsed=raw)
        claims = normalize_joint_body(raw, state)
    except (ValueError, TypeError) as exc:
        history.write('validation_00.json', status='rejected', error=str(exc))
        valid = {}
        rows = raw.get('modules', []) if isinstance(raw, dict) else []
        if isinstance(rows, list):
            for module in modules:
                matches = [r for r in rows if isinstance(r, dict) and r.get('module_id') == module['module_id']]
                if len(matches) == 1:
                    try:
                        valid[module['module_id']] = normalize_body(matches[0], module, state)
                    except (ValueError, TypeError):
                        pass
        correction = prompt+'\nCorrect only the diagnosed output defect; preserve valid neighboring modules.\n'+str(exc)+'\nVALID MODULES TO PRESERVE: '+json.dumps(list(valid))+'\nDRAFT DATA:\n'+str(content)+'\nReturn only the modules/claims output JSON.'
        corrected = history.request(1, agent, correction)
        try:
            raw = extract_json(corrected)
            history.write('parsed_01.json', parsed=raw)
            claims = normalize_joint_body(raw, state)
            by_module = {r['module_id']: r for r in raw['modules']}
            for module in modules:
                mid = module['module_id']
                if mid in valid and normalize_body(by_module[mid], module, state) != valid[mid]:
                    raise ValueError('Global Writer correction changed a valid neighboring module')
        except (ValueError, TypeError) as bad:
            from src.workflow.joint_preparation import JointContentFailure
            raise JointContentFailure(str(bad)) from bad
    history.write('body.json', claims=claims, status='unverified_draft')
    state['poster_claims'] = {'claims': claims}
    _atomic_json(Path(state['output_dir'])/'content/poster_claims.json', state['poster_claims'])
    state['current_agent'] = 'claim_writer'
    return state


def repair_verified_modules(state, feedback):
    """One shared editorial request; every resulting expression is reverified."""
    from src.agents.claim_writer import LangGraphAgent, apply_agent_policy, load_prompt
    ids = set(feedback)
    modules = [m for m in state['sample_module_plan']['modules'] if m['module_id'] in ids]
    bank = {e['evidence_id']: e for e in state['evidence_bank']['items']}
    payload = {'modules': modules, 'feedback': feedback,
               'draft': [c for c in state['poster_claims']['claims'] if c['display_module_id'] in ids],
               'evidence': {m['module_id']: [bank[e] for e in m.get('available_evidence_ids', m['evidence_ids'])] for m in modules}}
    payload['source_context'] = {m['module_id']: verification_source_context(state, payload['evidence'][m['module_id']]) for m in modules}
    prompt = ('Correct only the affected module bodies below. Return {"modules":[{"module_id":"...","claims":[...]}]}. '
              'Use each module original evidence; fully express every required_evidence_id. Preserve mechanisms, conditions, '
              'metrics and scope. Each claim uses local item_id, text, evidence_ids, essential, kind, requires_item_ids, '
              'parent_item_id, display_label and step_index. Each new entry must list replaces_claim_ids from the draft; '
              'preserve the necessary information of every essential old entry and its prerequisites. '
              'Each protected old claim must be replaced exactly once, merging is allowed. '
              'Do not change modules or write other modules.\n'+json.dumps(payload, ensure_ascii=False))
    journal = ModulePlanningRequests(state, prompt, directory='content/module_body_repair', kind='module_body_correction', scope=sorted(ids))
    agent = LangGraphAgent('Repair grounded module prose without losing indispensable information.',
        apply_agent_policy(state['text_model'], 'claim_writer'), state, 'claim_writer')
    raw = extract_json(journal.request(1, agent, prompt))
    journal.write('parsed_01.json', parsed=raw)
    rows = raw.get('modules') if isinstance(raw, dict) else None
    if (not isinstance(rows, list) or len(rows) != len(ids) or any(not isinstance(r, dict) for r in rows) or
            {r.get('module_id') for r in rows} != ids):
        raise ValueError('Module body repair must replace exactly the affected modules')
    by_id = {m['module_id']: m for m in modules}
    replacement = {r['module_id']: normalize_body(r, by_id[r['module_id']], state) for r in rows}
    for row in rows:
        old = {c['claim_id']: c for c in state['poster_claims']['claims'] if c['display_module_id'] == row['module_id']}
        protected = {cid for cid, c in old.items() if c.get('essential')}
        while True:
            closed = protected | {dep for cid in protected for dep in old[cid].get('requires_claim_ids', [])}
            if not closed <= old.keys(): raise ValueError('Original module prerequisite is missing')
            if closed == protected: break
            protected = closed
        replaced = []
        for source, claim in zip(row['claims'], replacement[row['module_id']]):
            refs = source.get('replaces_claim_ids', [])
            if not isinstance(refs, list) or any(not isinstance(cid, str) or cid not in old for cid in refs):
                raise ValueError('Module body repair has invalid replacement origins')
            replaced.extend(refs)
            if refs:
                claim['original_expression'] = ' '.join(old[cid]['text'] for cid in refs)
                claim['replaces_claim_ids'] = refs
                if set(refs) & protected: claim['essential'] = True
        if any(replaced.count(cid) != 1 for cid in protected):
            raise ValueError('Module body repair lost or duplicated an essential original expression')
    state['poster_claims'] = {'claims': [c for m in state['sample_module_plan']['modules']
        for c in (replacement[m['module_id']] if m['module_id'] in replacement else
                  [deepcopy(c) for c in state['poster_claims']['claims'] if c['display_module_id'] == m['module_id']])]}
    journal.write('candidate.json', claims=state['poster_claims']['claims'])
    _atomic_json(Path(state['output_dir'])/'content/poster_claims.json', state['poster_claims'])
    return state


def verifier_response(state, agent, prompt, claim_id, *, claim=None):
    """Archive sample verification before parsing; exact input changes get new records."""
    from types import SimpleNamespace
    from utils.persistence import digest
    scope = str(claim_id)
    if not scope or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in scope):
        raise ValueError('Unsafe verification claim identity')
    local = dict(state)
    local['output_dir'] = state.get('sample_preparation_dir') or state['output_dir']
    journal = ModulePlanningRequests(local, prompt,
        directory=f'content/module_verification/{scope}/{digest(prompt)[:16]}')
    content = journal.request(0, agent, prompt)
    parsed = extract_json(content)
    journal.write('parsed_00.json', parsed=parsed)
    if not isinstance(parsed, dict) or type(parsed.get('supported')) is not bool:
        raise ValueError('Sample verifier response lacks a boolean supported verdict')
    if (claim and claim.get('original_expression') and parsed.get('supported') is True
            and type(parsed.get('necessary_information_preserved')) is not bool):
        raise ValueError('Sample correction verdict lacks necessary_information_preserved')
    if claim and claim.get('editorial_revision') and parsed.get('supported') is True and type(parsed.get('editorial_information_preserved')) is not bool:
        raise ValueError('Selective editorial verdict lacks editorial_information_preserved')
    if claim:
        normalized, notes = normalize_verifier_coverage(claim['text'], parsed)
        if notes:
            journal.write('normalized_00.json', normalized=normalized, normalizations=notes)
            content = json.dumps(normalized, ensure_ascii=False)
    return SimpleNamespace(content=content)


def module_coverage_feedback(state):
    verified = (state.get('verified_claims') or {}).get('claims', [])
    candidates = (state.get('poster_claims') or {}).get('claims', [])
    feedback = {}
    reports = []
    for module in state['sample_module_plan']['modules']:
        mid = module['module_id']
        body = [c for c in verified if c.get('display_module_id') == mid]
        accepted = {c['claim_id'] for c in body}
        covered = {e for c in body for e in c.get('covered_required_evidence_ids', [])
                   if any(e in row.get('evidence_ids', []) for row in c.get('support_map', []))}
        missing = sorted(set(module['required_evidence_ids']) - covered)
        rejected = [c['claim_id'] for c in candidates
                    if c.get('display_module_id') == mid and c.get('essential') and c['claim_id'] not in accepted]
        row = {'module_id': mid, 'missing_required_evidence_ids': missing,
               'rejected_essential_claim_ids': rejected, 'empty_verified_module': not bool(body),
               'covered_required_evidence_ids': sorted(covered)}
        reports.append(row)
        if missing or rejected or (not body and not state.get('joint_preparation')): feedback[mid] = row
    _atomic_json(Path(state['output_dir'])/'content/module_coverage_report.json', {'modules': reports})
    return feedback
