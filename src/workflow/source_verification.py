"""Post-writing, direct original-source verification with exact visible-text binding."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re

from src.workflow.source_document import SourceOutputError, SourceProtocolError, validate_refs, source_material, validate_document
from src.workflow.source_requests import object_schema, STRING, STRINGS, BOOL, REFS
from src.workflow.source_editorial import request
from utils.persistence import digest

VERIFICATION_VERSION = 'direct_original_verification_v1'
VERDICT_SCHEMA = object_schema({
    'status': {'type': 'string', 'enum': ['supported', 'unsupported', 'contradicted', 'insufficient_source']},
    'reason': STRING, 'module_function_supported': BOOL, 'relationships_supported': BOOL, 'necessary_information_preserved': BOOL,
    'editorial_information_preserved': BOOL, 'additions_relevant': BOOL, 'additions_nonredundant': BOOL,
    'coverage': {'type': 'array', 'items': object_schema({'target_id': STRING, 'quote': STRING,
        'supported': BOOL, 'source_refs': REFS})},
    'obligations': {'type': 'array', 'items': object_schema({'obligation_id': STRING,
        'fully_expressed': BOOL, 'meaning_source_supported': BOOL, 'target_ids': STRINGS,
        'source_refs': REFS})}})


def targets_for(module):
    mid = module['module_id']
    targets = {mid+':title': module['title']}
    for entry in module['entries']:
        key = mid+':'+entry['item_id']
        targets[key] = entry['text']
        if entry['display_label']:
            targets[key+':label'] = entry['display_label']
        # The visible ordinal is a presentation index; semantic chronology is
        # certified by relationships_supported rather than treated as a statistic.
    return targets


def quantity_tokens(text):
    """Conservative typed helper; excludes digits inside scientific identifiers.

    This helper never certifies object, unit, causal or comparison meaning; the
    full original-source verdict remains necessary even for identical numbers.
    """
    result = set()
    for m in re.finditer(r'(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?![\w.])', text):
        before = text[:m.start()]
        if re.search(r'[A-Za-z][\w-]*-$', before):
            continue
        raw = m.group().replace(',', '').replace('−', '-')
        percent = raw.endswith('%')
        try:
            value = Decimal(raw.rstrip('%'))
        except InvalidOperation:
            continue
        result.add((value, 'percent' if percent else 'number'))
    # Conventional unsigned shared-percent ranges are notation, not a unit conversion.
    # Signed subtraction and ambiguous ASCII hyphens are left to strict checks.
    for match in re.finditer(r'(?<![\w.−+-])(\d+(?:\.\d+)?)\s*(?:–|\bto\b)\s*(\d+(?:\.\d+)?)%', text):
        result.add((Decimal(match.group(1)), 'percent'))
    return result


def numeric_support(target, sources):
    """Require each quantity in its actual quoted support, never elsewhere in paper."""
    available = set().union(*(quantity_tokens(r['quote']) for r in sources))
    numbers = {v for v, _ in available}
    return all((value, kind) in available or (kind == 'number' and value in numbers)
               for value, kind in quantity_tokens(target))


def validate_verdict_protocol(module, verdict, document, all_targets):
    from jsonschema import Draft202012Validator
    if list(Draft202012Validator(VERDICT_SCHEMA).iter_errors(verdict)):
        raise SourceProtocolError('Direct-source verdict violates its closed schema')
    # Explicit negative scientific decisions are never format-recovery triggers.
    flags = ('module_function_supported','relationships_supported','necessary_information_preserved',
             'editorial_information_preserved','additions_relevant','additions_nonredundant')
    if verdict['status'] != 'supported' or any(verdict[k] is False for k in flags):
        return verdict
    if any(r['supported'] is False for r in verdict['coverage']):
        return verdict
    targets = targets_for(module)
    seen = {k:set() for k in targets}
    for row in verdict['coverage']:
        key,quote = row['target_id'],row['quote']
        if key not in targets or not quote or quote not in targets[key]:
            raise SourceProtocolError('Verdict coverage has an invalid target or nonexact quote')
        try:
            validate_refs(row['source_refs'],document)
        except SourceOutputError as exc:
            raise SourceProtocolError('Verdict has invalid original-support locators') from exc
        for match in re.finditer(re.escape(quote),targets[key]):
            seen[key].update(range(match.start(),match.end()))
    if any(not {i for i,c in enumerate(text) if not c.isspace()} <= seen[key] for key,text in targets.items()):
        raise SourceProtocolError('Positive verdict has incomplete exact visible-text coverage')
    records = verdict['obligations']
    if len({r['obligation_id'] for r in records}) != len(records) or {r['obligation_id'] for r in records} != set(module['obligation_ids']):
        raise SourceProtocolError('Verdict omits or duplicates assigned meaning fields')
    for row in records:
        if not row['target_ids'] or not set(row['target_ids']) <= all_targets.keys():
            raise SourceProtocolError('Verdict obligation locators do not name actual visible targets')
        try:
            validate_refs(row['source_refs'],document)
        except SourceOutputError as exc:
            raise SourceProtocolError('Obligation verdict has invalid original locators') from exc
    return verdict


def check_module_verdict(module, verdict, document, all_targets, obligations):
    validate_verdict_protocol(module,verdict,document,all_targets)
    if verdict['status'] != 'supported':
        raise SourceOutputError(f"{module['module_id']}: {verdict['status']}: {verdict['reason']}")
    booleans = ('module_function_supported','relationships_supported','necessary_information_preserved','editorial_information_preserved',
                'additions_relevant','additions_nonredundant')
    if any(verdict[key] is not True for key in booleans):
        raise SourceOutputError('Original-source relationships, preservation or useful additions rejected')
    targets = targets_for(module)
    coverage = {key: set() for key in targets}
    supports = {key: [] for key in targets}
    for row in verdict['coverage']:
        key, quote = row['target_id'], row['quote']
        if key not in targets or row['supported'] is not True or not quote or quote not in targets[key]:
            raise SourceOutputError('Invalid or unsupported candidate coverage slice')
        validate_refs(row['source_refs'], document)
        if not numeric_support(quote, row['source_refs']):
            raise SourceOutputError('A quantity is absent from its actual original support')
        supports[key].extend(row['source_refs'])
        for match in re.finditer(re.escape(quote), targets[key]):
            coverage[key].update(range(match.start(), match.end()))
    for key, text in targets.items():
        required = {i for i,c in enumerate(text) if not c.isspace()}
        if not required <= coverage[key]:
            raise SourceOutputError('Incomplete exact visible scientific text coverage: '+key)
        if not numeric_support(text, supports[key]):
            raise SourceOutputError('Visible target numeric support is incomplete')
    assigned = set(module['obligation_ids'])
    records = verdict['obligations']
    if (len({o['obligation_id'] for o in records}) != len(records) or
            {o['obligation_id'] for o in records} != assigned):
        raise SourceOutputError('Indispensable meaning verdict coverage is incomplete')
    for row in records:
        if (row['obligation_id'] not in obligations or row['fully_expressed'] is not True or
                row['meaning_source_supported'] is not True or not row['target_ids'] or
                not set(row['target_ids']) <= all_targets.keys()):
            raise SourceOutputError('An indispensable meaning or its necessary conditions was lost')
        validate_refs(row['source_refs'], document)
    return verdict


def verification_identity(state, candidate, previous=None):
    return digest({'version': VERIFICATION_VERSION, 'source': state['source_document']['digest'],
                   'candidate': candidate, 'previous': previous,
                   'obligations': state['source_narrative_plan']['obligations'],
                   'model': state.get('text_model'), 'schema': VERDICT_SCHEMA})


def _verify_candidate(state, candidate, *, previous=None):
    document = validate_document(state['source_document'])
    all_targets = {key: value for m in candidate['modules'] for key,value in targets_for(m).items()}
    obligations = {o['obligation_id']: o for o in state['source_narrative_plan']['obligations']}
    key = verification_identity(state, candidate, previous)
    from pathlib import Path
    from src.workflow.source_requests import save
    audit_path = Path(state.get('sample_preparation_dir') or state['output_dir'])/f'source/verification/{key}/progress.json'
    results = []
    for module in candidate['modules']:
        save(audit_path, {'input_digest': key, 'status': 'checking',
            'checked_module_ids': [r['module_id'] for r in results],
            'not_checked_module_ids': [m['module_id'] for m in candidate['modules'] if m['module_id'] not in {r['module_id'] for r in results}]})
        verdict = request(state, 'source_verifier', {'original': source_material(state),
            'module': module, 'visible_targets': targets_for(module), 'whole_candidate': candidate,
            'whole_candidate_targets': all_targets, 'indispensable_meanings': state['source_narrative_plan']['obligations'],
            'previous_candidate_unverified_audit_context': previous,
            'assigned_obligation_ids': module['obligation_ids']}, VERDICT_SCHEMA,
            directory=f'source/verification/{key}/{module["module_id"]}',
            validator=lambda value: validate_verdict_protocol(module,value,document,all_targets))
        try:
            check_module_verdict(module, verdict, document, all_targets, obligations)
        except SourceProtocolError:
            save(audit_path, {'input_digest': key, 'status': 'invalid_verdict', 'module_id': module['module_id'],
                'checked_module_ids': [r['module_id'] for r in results],
                'not_checked_module_ids': [m['module_id'] for m in candidate['modules'] if m['module_id'] not in {r['module_id'] for r in results}]})
            raise
        except SourceOutputError as exc:
            save(audit_path, {'input_digest': key, 'status': 'rejected', 'module_id': module['module_id'],
                'reason': str(exc), 'checked_module_ids': [r['module_id'] for r in results],
                'not_checked_module_ids': [m['module_id'] for m in candidate['modules'] if m['module_id'] not in {r['module_id'] for r in results}]})
            raise SourceOutputError(module['module_id']+': '+str(exc)) from exc
        from src.workflow.source_document import locate_refs
        results.append({'module_id': module['module_id'], 'verdict': verdict,
            'support_locations': [{'target_id': r['target_id'], 'quote': r['quote'],
                'sources': locate_refs(r['source_refs'], document)} for r in verdict['coverage']]})
    covered = {r['obligation_id'] for result in results for r in result['verdict']['obligations']}
    if covered != obligations.keys():
        raise SourceOutputError('Whole-poster indispensable meaning coverage is incomplete')
    report = {'version': VERIFICATION_VERSION, 'status': 'supported', 'input_digest': key,
        'candidate_digest': digest(candidate), 'source_digest': document['digest'],
        'obligations_digest': digest(state['source_narrative_plan']['obligations']),
        'results': results, 'covered_obligation_ids': sorted(covered),
        'visible_targets_digest': digest(all_targets), 'previous_candidate_digest': digest(previous)}
    report['digest'] = digest(report)
    save(audit_path, {'input_digest': key, 'status': 'supported', 'report': report, 'not_checked_module_ids': []})
    return report


def assert_verified(state, board=None):
    """Fail closed on forged, stale or partially rebound science, including titles."""
    report = deepcopy(state.get('source_verification_report') or {})
    expected = report.pop('digest', None)
    candidate = state.get('source_candidate') or {}
    if (not state.get('verification_passed') or report.get('status') != 'supported' or
            report.get('version') != VERIFICATION_VERSION or digest(report) != expected or
            report.get('candidate_digest') != digest(candidate) or
            report.get('source_digest') != validate_document(state['source_document'])['digest'] or
            report.get('obligations_digest') != digest(state['source_narrative_plan']['obligations'])):
        raise ValueError('No coherent direct-original-source verification snapshot')
    targets = {key:value for m in candidate.get('modules', []) for key,value in targets_for(m).items()}
    if report.get('visible_targets_digest') != digest(targets):
        raise ValueError('Visible original-source proof target digest mismatch')
    modules = {m['module_id']: m for m in candidate['modules']}
    claims = {c['claim_id']: c for c in (state.get('verified_claims') or {}).get('claims', [])}
    expected_claims = {m['module_id']+':'+e['item_id']: e['text'] for m in modules.values() for e in m['entries']}
    if claims.keys() != expected_claims.keys() or any(c.get('verified') is not True or
            c.get('text') != expected_claims[cid] or c.get('source_verification_digest') != expected
            for cid,c in claims.items()):
        raise ValueError('Display expressions differ from the source-verified candidate')
    rows = report.get('results') or []
    if len(rows) != len(modules) or {r['module_id'] for r in rows} != modules.keys():
        raise ValueError('Missing source verification modules')
    obligations = {o['obligation_id']: o for o in state['source_narrative_plan']['obligations']}
    for row in rows:
        check_module_verdict(modules[row['module_id']], row['verdict'], state['source_document'], targets, obligations)
    from pathlib import Path
    for visual_id, asset in state['source_document']['assets'].items():
        prefix, key = visual_id.split('_', 1)
        actual = (state.get('images' if prefix == 'figure' else 'tables') or {}).get(key)
        if actual is None or actual.get('aspect') != asset.get('aspect') or actual.get('caption', '') != asset.get('caption', ''):
            raise ValueError('Rendered source asset metadata differs from original material')
        if asset.get('source_path') and Path(actual.get('path', '')).resolve() != Path(asset['source_path']).resolve():
            raise ValueError('Rendered source asset points outside its original material')
    if board is not None:
        sections = board.get('spatial_content_plan', {}).get('sections', [])
        if len(sections) != len(modules) or {s['section_id'] for s in sections} != modules.keys():
            raise ValueError('Fitting lost or duplicated an authored display module')
        visible = []
        for s in sections:
            m = modules[s['section_id']]
            ids = [m['module_id']+':'+e['item_id'] for e in m['entries']]
            if (s.get('section_title') != m['title'] or s.get('claim_ids') != ids or
                    s.get('text_content') != [e['text'] for e in m['entries']] or
                    [v['visual_id'] for v in s.get('visual_assets', [])] != m['visual_ids']):
                raise ValueError('Fitted visible text/title differs from source-verified content')
            visible.extend(ids)
        if set(visible) != claims.keys() or len(visible) != len(set(visible)):
            raise ValueError('Final visible scientific text coverage mismatch')
    return True


def assert_compiled_text(state):
    """Match renderer-visible body/title strings, including styled scientific operators."""
    from src.layout.editorial import presentation_lines
    from src.agents.font_agent import FontAgent
    from utils.text_formatting import tokenize_styling
    board = state.get('optimized_story_board') or state.get('story_board') or {}
    assert_verified(state, board)
    layout = state.get('styled_layout') or state.get('design_layout') or []
    def plain(text):
        return ' '.join(''.join(s['text'] for s in tokenize_styling(str(text))).split())
    known = {s['section_id'] for s in board['spatial_content_plan']['sections']}
    if any(e.get('type') in {'text','section_title'} and e.get('section_id') not in known for e in layout):
        raise ValueError('Compiled layout contains an unverified scientific module')
    for section in board['spatial_content_plan']['sections']:
        sid = section['section_id']
        actual = '\n'.join(str(e.get('content','')) for e in layout if e.get('type') == 'text' and e.get('section_id') == sid)
        expected = '\n'.join(presentation_lines(section))
        escaped = FontAgent._escape_formatting_literals(expected)
        # Decode only the exact shared renderer grammar; do not strip arbitrary
        # angle brackets, stars or scientific operators as if they were tags.
        if plain(actual) != plain(escaped):
            raise ValueError('Final compiled scientific text differs from its verified snapshot: '+sid)
        titles = [e.get('section_title') for e in layout if e.get('type') == 'section_title' and e.get('section_id') == sid]
        if titles != [section['section_title']]:
            raise ValueError('Final compiled scientific title differs from its verified snapshot: '+sid)
    return True


def verify_candidate(state, candidate, *, previous=None):
    import time
    started = time.perf_counter()
    try:
        return _verify_candidate(state, candidate, previous=previous)
    finally:
        metrics = state.get('timing_metrics')
        if metrics is not None:
            metrics.record_component('claim_verifier', time.perf_counter()-started,
                                     state.get('iteration_context', {}).get('iteration', 0))
