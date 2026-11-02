"""One advisory spelling pass over Marker output, with exact, audited patches.

Marker remains the extractor. Native PDF text is only a nonblocking reference
for proposed spelling changes; it never replaces the extracted paper wholesale.
"""
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata

from utils.persistence import _atomic_json, digest, file_hash, read_json

VERSION = 'marker_spelling_review_v1'
PROMPT = 'config/prompts/editorial_proofreading.txt'
WORD = re.compile(r'[^\W\d_]+', re.UNICODE)
PROTECTED = re.compile(
    r'```[\s\S]*?```|`[^`\n]*`|\$\$[\s\S]*?\$\$|(?<!\\)\$[^$\n]+\$'
    r'|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|<[^>]*>'
    r'|https?://[^\s)]+|!?\[[^\]]*\]\([^)]*\)|[\w.+%−-]*\d[\w.+%−-]*')


def paragraphs(text):
    """Stable paragraph locators without changing whitespace or Markdown."""
    result, offset = [], 0
    for part in re.split(r'(\n[ \t]*\n)', text):
        if part.strip():
            result.append({'paragraph_id': f'p{len(result)+1:05d}',
                           'start': offset, 'text': part})
        offset += len(part)
    return result


def _joined(text):
    return re.sub(r'(?<=\w)-[ \t]*\n[ \t]*(?=\w)', '', text)


def _fold(text):
    text = re.sub(r'(?m)^[ \t]*(?:>+[ \t]*|#{1,6}[ \t]+)', '', text)
    text = re.sub(r'(\*\*|__|\*)([^\n]+?)\1', r'\2', text)
    return ' '.join(unicodedata.normalize('NFKC', _joined(text)).split())


def _spelling_only(before, after):
    a, b = _joined(before), _joined(after)
    # Preserve every number, symbol and punctuation character. Whitespace can
    # change only for a line-end hyphen or inside a damaged word.
    skeleton = lambda t: ''.join(c for c in t if not c.isalpha())
    if skeleton(a) != skeleton(b):
        return False
    wa, wb = WORD.findall(a), WORD.findall(b)
    if len(wa) != len(wb):
        return False
    changed = 0
    for x, y in zip(wa, wb):
        if x == y:
            continue
        edits = sum(max(j-i, l-k) for tag,i,j,k,l in
                    SequenceMatcher(None,x,y,autojunk=False).get_opcodes() if tag != 'equal')
        if min(len(x), len(y)) < 2 or edits > 3:
            return False
        changed += edits
    return changed <= 8 and (changed > 0 or before != after and a == b)


def _native_pages(pdf_path):
    import pymupdf
    with pymupdf.open(pdf_path) as pdf:
        return [_fold(page.get_text()) for page in pdf]


def _evidence(paragraph, start, end, nearby_edits, native_pages):
    # Include up to four neighboring words on either side. Finding just the
    # replacement word elsewhere in the paper does not support an edit here.
    text = paragraph['text']
    left = list(WORD.finditer(text[:start]))
    right = list(WORD.finditer(text[end:]))
    a = left[-4].start() if len(left) >= 4 else 0
    b = end + right[3].end() if len(right) >= 4 else len(text)
    before = _fold(text[a:b])
    corrected = text[a:b]
    for edit in sorted(nearby_edits,key=lambda e:e['start'],reverse=True):
        local_start = edit['start']-paragraph['start']
        local_end = edit['end']-paragraph['start']
        if a <= local_start and local_end <= b:
            corrected = corrected[:local_start-a] + edit['after'] + corrected[local_end-a:]
    corrected = _fold(corrected)
    # NFKC expands genuine ligatures; equal folded contexts can confirm that
    # expansion. Otherwise, preserve spelling already present in native text.
    if before != corrected and any(before in page for page in native_pages):
        return None  # Native text confirms the author's existing spelling.
    matches = [i+1 for i,page in enumerate(native_pages) if corrected and corrected in page]
    return {'pages': matches, 'context': corrected, 'method': 'native_text_context'} if matches else None


def apply_suggestions(marker, suggestions, native_pages):
    """Reject unsafe/ambiguous suggestions individually, preserving all neighbors."""
    lookup = {p['paragraph_id']: p for p in paragraphs(marker)}
    proposed, rejected = [], []
    for edit in suggestions:
        item = deepcopy(edit)
        paragraph = lookup.get(edit['paragraph_id'])
        before, after = edit['before'], edit['after']
        reason = None
        if paragraph is None or not before or paragraph['text'].count(before) != 1:
            reason = 'missing_or_ambiguous_original_span'
        elif before == after or not _spelling_only(before, after):
            reason = 'outside_spelling_scope'
        else:
            start = paragraph['text'].index(before)
            end = start + len(before)
            changes = [(start+i,start+j) for tag,i,j,k,l in
                       SequenceMatcher(None,before,after,autojunk=False).get_opcodes() if tag != 'equal']
            protected = list(PROTECTED.finditer(paragraph['text']))
            if any((a < m.end() and b > m.start()) or
                   (a == b and m.start() < a < m.end()) for a,b in changes for m in protected):
                reason = 'protected_number_formula_identifier_or_markup'
            else:
                item.update(start=paragraph['start']+start, end=paragraph['start']+end)
                proposed.append(item)
        if reason:
            rejected.append({**item, 'rejection': reason})
    accepted = []
    for i,edit in enumerate(proposed):
        if any(i != j and edit['start'] < other['end'] and other['start'] < edit['end']
               for j,other in enumerate(proposed)):
            rejected.append({**edit, 'rejection': 'overlapping_suggestions'})
        else:
            accepted.append(edit)
    # Nearby damaged words must be checked together: the native phrase may
    # contain both "after" and "affixation" while Marker loses letters in both.
    confirmed = []
    for edit in accepted:
        paragraph = lookup[edit['paragraph_id']]
        peers = [e for e in accepted if e['paragraph_id']==edit['paragraph_id']]
        evidence = _evidence(paragraph,edit['start']-paragraph['start'],
                             edit['end']-paragraph['start'],peers,native_pages)
        if evidence is None:
            rejected.append({**edit,'rejection':'no_confirming_native_context'})
        else:
            confirmed.append({**edit,'evidence':evidence})
    accepted = sorted(confirmed,key=lambda e:e['start'])
    text = marker
    for edit in reversed(accepted):
        text = text[:edit['start']] + edit['after'] + text[edit['end']:]
    return text, accepted, rejected


def validate_report(report, marker, pdf_hash, identity=None):
    body = deepcopy(report)
    expected = body.pop('digest', None)
    if (expected != digest(body) or body.get('version') != VERSION
            or body.get('marker_digest') != digest(marker) or body.get('pdf_hash') != pdf_hash
            or identity is not None and body.get('input_digest') != identity
            or body.get('status') not in {'corrected','unchanged','unavailable'}):
        raise ValueError('Marker proofreading record identity/digest mismatch')
    text, previous = marker, len(marker)
    for edit in reversed(body['edits']):
        a,b = edit['start'],edit['end']
        if not 0 <= a < b <= previous or marker[a:b] != edit['before'] or not _spelling_only(edit['before'],edit['after']):
            raise ValueError('Marker proofreading patch changed or overlaps')
        text = text[:a] + edit['after'] + text[b:]
        previous = a
    if digest(text) != body['text_digest']:
        raise ValueError('Marker proofreading text differs from recorded edits')
    return text


def quality_summary(report):
    if not report or report.get('version') != VERSION:
        return None
    return {'version':VERSION, 'status':report['status'],
            'extraction_method':'marker', 'accepted_edits':len(report['edits']),
            'rejected_edits':len(report['rejected_edits']),
            'uncertain':report['uncertain'][:50], 'warnings':report['warnings'],
            'scientific_truth_verified':False,
            'instructions':'Spelling review is advisory, not scientific verification. '
                'Unconfirmed suggestions retain the original Marker text. Original PDF spelling may be imperfect.'}


def proofread_marker(state, marker, content_dir):
    from src.workflow.editorial_requests import obj, STRING, request, save, read, stopped
    from src.workflow.editorial_contract import EditorialInterrupted
    from utils.agent_policy import apply_agent_policy
    if not marker.strip():
        raise ValueError('Marker extracted no usable paper text')
    stopped(state)
    directory = Path(content_dir)
    directory.mkdir(parents=True, exist_ok=True)
    original_path = directory/'marker_raw.md'
    if original_path.exists() and original_path.read_text(encoding='utf-8') != marker:
        raise ValueError('Saved Marker original changed during proofreading')
    original_path.write_text(marker, encoding='utf-8')
    pdf_hash = file_hash(state['pdf_path'])
    identity = digest({'version':VERSION,'pdf':pdf_hash,'marker':digest(marker),
                       'model':apply_agent_policy(state['text_model'],'parser'),
                       'prompt':file_hash(PROMPT),'review_code':file_hash(__file__)})
    audit = directory/'source_extraction.json'
    if audit.exists():
        report = read_json(audit)
        text = validate_report(report,marker,pdf_hash,identity)
        (directory/'raw.md').write_text(text, encoding='utf-8')
        return text, report
    journal = Path(state['output_dir'])/'editorial/paper/proofreading'
    own_identity = directory/'proofreading_input.json'
    if own_identity.exists():
        read(own_identity, identity)
    else:
        if journal.exists() and any(journal.iterdir()):
            raise ValueError('Proofreading input identity missing from existing request')
        save(own_identity, {'input_digest':identity})
    # Validate all envelopes before any replay/fallback. Corrupt durable history
    # is an integrity error, not a spelling uncertainty to hide.
    if journal.exists():
        request_identity = None
        for path in sorted(journal.glob('*.json')):
            envelope = read_json(path)
            payload = envelope['payload']
            if envelope.get('digest') != digest(payload):
                raise ValueError('Corrupt proofreading request receipt')
            current = payload.get('input_digest')
            if request_identity is not None and current != request_identity:
                raise ValueError('Proofreading request receipts disagree')
            request_identity = current
    report = {'version':VERSION,'input_digest':identity,'pdf_hash':pdf_hash,
              'marker_digest':digest(marker), 'extraction_method':'marker',
              'status':'unchanged','edits':[],'rejected_edits':[], 'uncertain':[], 'warnings':[]}
    text = marker
    lost = (journal/'request_00.json').exists() and not (journal/'response_00.json').exists()
    if lost:
        report['status'] = 'unavailable'
        report['warnings'].append({'kind':'proofreading_response_unavailable',
                                   'reason':'Charged request has no response; no resubmission'})
    else:
        schema = obj({'edits':{'type':'array','items':obj({k:STRING for k in
                        ('paragraph_id','before','after','reason')})},
                      'uncertain':{'type':'array','items':obj({k:STRING for k in
                        ('paragraph_id','text','reason')})}})
        # The review belongs to the paper, independently of any sample context.
        current = dict(state, raw_text=marker, paper_foundation_digest=None,
                       iteration_context={}, sample_preparation_dir=None)
        try:
            value = request(current,'editorial_proofreading',
                {'paragraphs':[{k:p[k] for k in ('paragraph_id','text')} for p in paragraphs(marker)]},
                schema, directory='editorial/paper/proofreading', correction=False)
        except EditorialInterrupted:
            raise
        except Exception as exc:
            report['status'] = 'unavailable'
            report['warnings'].append({'kind':'proofreading_unavailable',
                                       'error_type':type(exc).__name__})
        else:
            report['uncertain'] = value['uncertain']
            try:
                native = _native_pages(state['pdf_path']) if value['edits'] else []
            except Exception as exc:
                native = []
                report['warnings'].append({'kind':'native_reference_unavailable',
                                           'error_type':type(exc).__name__})
            text, report['edits'], report['rejected_edits'] = apply_suggestions(marker,value['edits'],native)
            if report['edits']:
                report['status'] = 'corrected'
    if (journal/'response_00.json').exists():
        report['response_receipt_digest'] = digest(read_json(journal/'response_00.json'))
    report['text_digest'] = digest(text)
    report['digest'] = digest(report)
    _atomic_json(audit, report)
    (directory/'raw.md').write_text(text, encoding='utf-8')
    return text, report
