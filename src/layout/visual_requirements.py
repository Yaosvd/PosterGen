"""Paper-scoped, source-bound requirements for indispensable scientific visuals.

The contract is an ID decision, not an image/module semantic judge. It cannot
rewrite science or manufacture assets. Published requirements never depend on
the family, capacity, another attempt's board, or an optimizer's deletion plan.
"""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path


VISUAL_REQUIREMENT_VERSION = 'critical_visuals_v1'
REQUIRED_REASONS = {'core_method', 'main_result', 'essential_comparison', 'key_visual'}
OTHER_REASONS = {'supporting', 'redundant', 'out_of_scope'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def enabled(state, config=None):
    settings = config if config is not None else state.get('critic_config') or {}
    return (state.get('generation_route') == 'optimization_family'
            and (settings.get('critical_visuals') or {}).get('enabled', True))


def catalog(state):
    result = {}
    for prefix, field in (('figure', 'images'), ('table', 'tables')):
        for key, item in (state.get(field) or {}).items():
            if isinstance(item, dict):
                result[f'{prefix}_{key}'] = item
    return result


def asset_digest(record):
    path = Path(str(record.get('path') or ''))
    if not path.is_file():
        return None
    sha = hashlib.sha256()
    try:
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(chunk)
    except OSError:
        return None
    return sha.hexdigest()


def file_digest(path):
    return asset_digest({'path': path})


def readable(record):
    try:
        from PIL import Image
        with Image.open(str(record.get('path') or '')) as image:
            image.verify()
        return True
    except (OSError, ValueError, SyntaxError):
        return False


def pixel_size(record):
    try:
        from PIL import Image
        with Image.open(str(record.get('path') or '')) as image:
            return list(image.size)
    except (OSError, ValueError, SyntaxError):
        return None


def source_identity(state):
    return digest({'claims': (state.get('verified_claims') or {}).get('claims', []),
                   'evidence': (state.get('evidence_bank') or {}).get('items', []),
                   'planner_review': (state.get('narrative_plan') or {}).get('visual_requirements')})


def normalize_review(raw, state):
    """Bound model fields; unknown/missing decisions never mean optional."""
    records = catalog(state)
    evidence = {str(e['evidence_id']) for e in (state.get('evidence_bank') or {}).get('items', [])
                if isinstance(e, dict) and e.get('evidence_id')}
    sections = {str(s['section_id']) for s in (state.get('narrative_plan') or {}).get('sections', [])
                if isinstance(s, dict) and s.get('section_id')}
    items = raw.get('items', []) if isinstance(raw, dict) else []
    output, seen, invalid = [], set(), []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            invalid.append('invalid_item')
            continue
        vid = item.get('visual_id')
        disposition, reason = item.get('disposition'), item.get('reason')
        if (not isinstance(vid, str) or vid not in records or vid in seen or not isinstance(reason, str)
                or disposition not in ('required', 'optional', 'omit')
                or reason not in (REQUIRED_REASONS if disposition == 'required' else OTHER_REASONS)):
            invalid.append('invalid_or_duplicate_decision')
            continue
        refs = item.get('evidence_ids')
        refs = list(dict.fromkeys(e for e in refs if isinstance(e, str) and e in evidence)) if isinstance(refs, list) else []
        # Required decisions need paper support; the existing key pointer has a
        # separate deterministic floor in build_contract.
        if disposition == 'required' and not refs:
            invalid.append('required_support_unresolved')
            continue
        sources = item.get('source_section_ids')
        sources = [s for s in sources if isinstance(s, str) and s in sections] if isinstance(sources, list) else []
        output.append({'visual_id': vid, 'disposition': disposition, 'reason': reason,
                       'evidence_ids': refs, 'source_section_ids': list(dict.fromkeys(sources))})
        seen.add(vid)
    return {'items': output, 'invalid_decisions': invalid}


def seal(contract):
    result = deepcopy(contract)
    result.pop('contract_digest', None)
    result['contract_digest'] = digest(result)
    return result


def build_contract(state, review=None):
    records = catalog(state)
    planner = normalize_review((state.get('narrative_plan') or {}).get('visual_requirements'), state)
    current = normalize_review(review, state)
    decisions = {i['visual_id']: deepcopy(i) for i in planner['items']}
    # Planner's required decisions are a floor; Curator can add requirements,
    # never remove them because a layout looks inconvenient.
    for item in current['items']:
        if decisions.get(item['visual_id'], {}).get('disposition') != 'required':
            decisions[item['visual_id']] = deepcopy(item)
    key = (state.get('classified_visuals') or {}).get('key_visual')
    issues = []
    if key:
        if isinstance(key, str) and key in records:
            existing = decisions.get(key) or {}
            decisions[key] = {'visual_id': key, 'disposition': 'required', 'reason': 'key_visual',
                              'evidence_ids': existing.get('evidence_ids', []),
                              'source_section_ids': existing.get('source_section_ids', [])}
        else:
            issues.append({'code': 'KEY_VISUAL_SOURCE_UNKNOWN'})
    missing = sorted(set(records) - set(decisions))
    if missing:
        issues.append({'code': 'VISUAL_REVIEW_INCOMPLETE', 'visual_ids': missing})
    # A malformed Curator review is not silently replaced by an empty contract.
    invalid = current['invalid_decisions'] + planner['invalid_decisions']
    saved_review = (state.get('narrative_plan') or {}).get('visual_requirements')
    if isinstance(saved_review, dict) and isinstance(saved_review.get('invalid_decisions'), list):
        invalid += saved_review['invalid_decisions']
    if invalid:
        issues.append({'code': 'VISUAL_REVIEW_INVALID', 'reasons': invalid})
    required = sorted(v for v, item in decisions.items() if item['disposition'] == 'required')
    identities = {v: asset_digest(record) for v, record in records.items()}
    for vid in required:
        if identities[vid] is None:
            issues.append({'code': 'REQUIRED_VISUAL_SOURCE_MISSING', 'visual_id': vid})
        elif not readable(records[vid]):
            issues.append({'code': 'REQUIRED_VISUAL_SOURCE_UNREADABLE', 'visual_id': vid})
    return seal({'version': VISUAL_REQUIREMENT_VERSION, 'source_identity': source_identity(state),
                 'catalog': {v: {'sha256': identities[v], 'caption_digest': digest(str(records[v].get('caption') or '')),
                                 'pixel_size': pixel_size(records[v])}
                             for v in sorted(records)},
                 'items': [decisions[v] for v in sorted(decisions)], 'required_visual_ids': required,
                 'status': 'unresolved' if issues else 'ready', 'issues': issues})


def validate_contract(contract, state):
    issues = []
    if not isinstance(contract, dict) or contract.get('version') != VISUAL_REQUIREMENT_VERSION:
        return [{'code': 'VISUAL_REQUIREMENT_CONTRACT_MISSING'}]
    if (not isinstance(contract.get('catalog'), dict) or not isinstance(contract.get('items'), list)
            or not isinstance(contract.get('required_visual_ids'), list)
            or any(not isinstance(v, str) for v in contract.get('required_visual_ids', []))
            or any(not isinstance(i, dict) for i in contract.get('catalog', {}).values())
            or any(not isinstance(i, dict) or not isinstance(i.get('visual_id'), str) for i in contract['items'])):
        return [{'code': 'VISUAL_REQUIREMENT_SCHEMA_INVALID'}]
    if contract.get('contract_digest') != seal(contract)['contract_digest']:
        issues.append({'code': 'VISUAL_REQUIREMENT_DIGEST_MISMATCH'})
    if contract.get('source_identity') != source_identity(state):
        issues.append({'code': 'VISUAL_REQUIREMENT_FOREIGN_SOURCE'})
    records = catalog(state)
    if set(contract.get('catalog', {})) != set(records):
        issues.append({'code': 'VISUAL_REQUIREMENT_CATALOG_MISMATCH'})
    if contract.get('status') != 'ready':
        issues.extend(contract.get('issues') or [{'code': 'VISUAL_REQUIREMENT_UNRESOLVED'}])
    decisions = contract.get('items') or []
    # The deterministic key floor is allowed without a model evidence pointer.
    key = (state.get('classified_visuals') or {}).get('key_visual')
    checked = [i for i in decisions if isinstance(i, dict) and i.get('visual_id') != key]
    if normalize_review({'items': checked}, state)['invalid_decisions']:
        issues.append({'code': 'VISUAL_REQUIREMENT_DECISIONS_INVALID'})
    if len(decisions) != len(records) or {i.get('visual_id') for i in decisions if isinstance(i, dict)} != set(records):
        issues.append({'code': 'VISUAL_REQUIREMENT_DECISIONS_INCOMPLETE'})
    wanted = sorted(i['visual_id'] for i in decisions if isinstance(i, dict)
                    and isinstance(i.get('visual_id'), str) and i.get('disposition') == 'required')
    if wanted != contract.get('required_visual_ids'):
        issues.append({'code': 'VISUAL_REQUIREMENT_SET_MISMATCH'})
    if key and key not in wanted:
        issues.append({'code': 'KEY_VISUAL_NOT_REQUIRED'})
    planner_required = {i['visual_id'] for i in normalize_review(
        (state.get('narrative_plan') or {}).get('visual_requirements'), state)['items'] if i['disposition'] == 'required'}
    if not planner_required.issubset(wanted):
        issues.append({'code': 'PLANNER_REQUIRED_VISUAL_DOWNGRADED'})
    for vid in wanted:
        record = records.get(vid) or {}
        actual = asset_digest(record)
        if not actual or actual != (contract.get('catalog', {}).get(vid) or {}).get('sha256'):
            issues.append({'code': 'REQUIRED_VISUAL_SOURCE_CHANGED', 'visual_id': vid})
        elif not readable(record):
            issues.append({'code': 'REQUIRED_VISUAL_SOURCE_UNREADABLE', 'visual_id': vid})
    for vid, record in records.items():
        if digest(str(record.get('caption') or '')) != (contract.get('catalog', {}).get(vid) or {}).get('caption_digest'):
            issues.append({'code': 'VISUAL_REQUIREMENT_CAPTION_CHANGED', 'visual_id': vid})
    return issues


def contract_for(state, board=None):
    """Canonical Campaign contract takes precedence over branch-local boards."""
    return (state.get('visual_requirements') or (board or {}).get('visual_requirements')
            or build_contract(state))


def required_ids(state, board=None):
    if not enabled(state):
        return set()
    result = set(contract_for(state, board).get('required_visual_ids') or [])
    key = (state.get('classified_visuals') or {}).get('key_visual')
    if isinstance(key, str) and key in catalog(state):
        result.add(key)
    result.update(i['visual_id'] for i in normalize_review(
        (state.get('narrative_plan') or {}).get('visual_requirements'), state)['items']
                  if i['disposition'] == 'required')
    return result


def attach_required(board, state, contract):
    """Place missing requirements using existing local/source hints only."""
    result = deepcopy(board)
    result['visual_requirements'] = deepcopy(contract)
    sections = result.get('spatial_content_plan', {}).get('sections', [])
    from utils.grounded_content import all_publishable_claims
    claims = all_publishable_claims(state)
    unresolved = []
    for item in contract.get('items') or []:
        vid = item['visual_id']
        if item['disposition'] != 'required' or any(
                a.get('visual_id') == vid for s in sections for a in s.get('visual_assets') or []):
            continue
        refs, sources = set(item.get('evidence_ids') or []), set(item.get('source_section_ids') or [])
        matches = []
        for section in sections:
            owned = [claims[c] for c in section.get('claim_ids', []) if c in claims]
            if any(refs.intersection(c.get('evidence_ids') or []) or str(c.get('section_id')) in sources for c in owned):
                matches.append(section)
        if len(matches) == 1:
            matches[0].setdefault('visual_assets', []).append({'visual_id': vid})
        else:
            unresolved.append({'code': 'REQUIRED_VISUAL_OWNER_UNRESOLVED', 'visual_id': vid})
    return result, unresolved


def board_audit(state, board, layout=None, *, contract=None):
    if not enabled(state):
        return {'version': VISUAL_REQUIREMENT_VERSION, 'status': 'not_applicable', 'passed': True, 'issues': []}
    contract = contract or contract_for(state, board)
    issues = validate_contract(contract, state)
    own = board.get('visual_requirements')
    if own and own.get('contract_digest') != contract.get('contract_digest'):
        issues.append({'code': 'VISUAL_REQUIREMENT_BRANCH_MISMATCH'})
    counts = Counter(a.get('visual_id') for s in board.get('spatial_content_plan', {}).get('sections', [])
                     for a in s.get('visual_assets') or [] if isinstance(a, dict))
    compiled = Counter(e.get('visual_id') for e in layout or [] if e.get('type') == 'visual')
    for vid in contract.get('required_visual_ids') or []:
        if counts[vid] != 1:
            issues.append({'code': 'REQUIRED_VISUAL_MISSING' if not counts[vid] else 'REQUIRED_VISUAL_DUPLICATED', 'visual_id': vid})
        if layout is not None and compiled[vid] != 1:
            issues.append({'code': 'REQUIRED_VISUAL_NOT_COMPILED', 'visual_id': vid})
        if layout is not None:
            policy = (state.get('critic_config') or {}).get('critical_visuals') or {}
            for element in layout:
                if element.get('type') == 'visual' and element.get('visual_id') == vid:
                    w, h = float(element.get('width', 0)), float(element.get('height', 0))
                    floor = float(policy.get('minimum_table_width_inches' if vid.startswith('table_')
                                             else 'minimum_figure_width_inches', 3.0 if vid.startswith('table_') else 2.0))
                    if w < floor or min(w, h) < float(policy.get('minimum_short_edge_inches', 0.5)):
                        issues.append({'code': 'REQUIRED_VISUAL_TOO_SMALL', 'visual_id': vid})
    return {'version': VISUAL_REQUIREMENT_VERSION, 'contract_digest': contract.get('contract_digest'),
            'required_visual_ids': contract.get('required_visual_ids', []),
            'visible_visual_ids': sorted(v for v in counts if isinstance(v, str)),
            'status': 'passed' if not issues else 'failed', 'passed': not issues, 'issues': issues}
