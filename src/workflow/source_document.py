"""Immutable original-paper material. No pre-extracted scientific permission bank."""
from copy import deepcopy
import re

from utils.persistence import digest, file_hash

VERSION = 'source_editorial_v1'
DOCUMENT_VERSION = 'original_sections_v1'
MAX_SOURCE_CHARS = 240_000


class SourceOutputError(ValueError):
    """Diagnosed model/scientific/finite-fit failure, not an infrastructure failure."""


class SourceProtocolError(SourceOutputError):
    """Malformed/incomplete verdict; never a trigger for substantive prose editing."""


class SourceInterrupted(Exception):
    """Cooperative stop at a durable boundary."""


def source_mode(state):
    return state.get('source_editorial_version') == VERSION


def check_stop(state):
    stop = state.get('_force_stop_requested')
    if stop and stop():
        raise SourceInterrupted()


def normalized(text):
    return ' '.join(str(text).split())


def build_document(state):
    """Index complete, verbatim parser chunks, retaining exact raw-paper identity."""
    raw = state.get('raw_text')
    if not isinstance(raw, str) or not raw.strip():
        raise SourceOutputError('Original paper text is missing')
    chunks = state.get('section_chunks') or []
    if not chunks:
        from utils.section_utils import build_section_chunks
        chunks = build_section_chunks(raw, max_chars=12000)
    units = []
    for i, chunk in enumerate(chunks):
        text = chunk.get('content')
        if not isinstance(text, str) or not text.strip():
            raise SourceOutputError('Original section chunk is empty')
        if normalized(text) not in normalized(raw):
            raise SourceOutputError('Original section chunk does not occur in parsed paper')
        # Chunks are original continuous text, not model-generated summaries.
        unit = {'source_id': f'src_{i+1:05d}', 'section_id': str(chunk.get('section_id', '')),
                'heading': chunk.get('section_name', ''), 'level': chunk.get('level', 1),
                'chunk_index': chunk.get('chunk_index', 0), 'text': text,
                'source_location': deepcopy(chunk.get('source') or {
                    'start_char': chunk.get('start_char'), 'end_char': chunk.get('end_char')}),
                'page': chunk.get('page'), 'paragraphs': []}
        for j, match in enumerate(re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', text)):
            unit['paragraphs'].append({'paragraph_id': f'{unit["source_id"]}:p{j+1}',
                'start': match.start(), 'end': match.end(), 'text': match.group()})
        units.append(unit)
    assets = {}
    for prefix, field in (('figure', 'images'), ('table', 'tables')):
        for key, asset in (state.get(field) or {}).items():
            assets[f'{prefix}_{key}'] = {'caption': asset.get('caption', ''),
                'source_path': asset.get('path'), 'source_hash': file_hash(asset['path']) if asset.get('path') else None,
                'aspect': asset.get('aspect'), 'source_role': next((role for role, ids in
                    (state.get('classified_visuals') or {}).items() if isinstance(ids, list) and f'{prefix}_{key}' in ids), None)}
    doc = {'version': DOCUMENT_VERSION, 'raw_text': raw, 'raw_digest': digest(raw),
           'paper_pdf_hash': file_hash(state['pdf_path']) if state.get('pdf_path') else None,
           'units': units, 'assets': assets, 'normalization': 'whitespace_only_v1'}
    doc['digest'] = digest(doc)
    return doc


def validate_document(document):
    doc = deepcopy(document or {})
    expected = doc.pop('digest', None)
    if (doc.get('version') != DOCUMENT_VERSION or expected != digest(doc) or
            doc.get('raw_digest') != digest(doc.get('raw_text')) or not doc.get('units')):
        raise ValueError('Original source document digest mismatch')
    ids = [u['source_id'] for u in doc['units']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate original source identity')
    for asset in doc.get('assets', {}).values():
        if asset.get('source_path') and file_hash(asset['source_path']) != asset.get('source_hash'):
            raise ValueError('Original source asset digest mismatch')
    return document


def source_material(state):
    """Complete continuous sections; explicitly refuse an overlarge context."""
    doc = validate_document(state['source_document'])
    units = [{k: deepcopy(v) for k, v in u.items() if k != 'paragraphs'} for u in doc['units']]
    if sum(len(u['text']) for u in units) > MAX_SOURCE_CHARS:
        raise SourceOutputError('Complete original sections exceed bounded context; no silent truncation')
    return {'units': units, 'assets': {key: {k: v for k, v in value.items()
            if k not in {'source_path'}} for key, value in doc['assets'].items()},
            'source_digest': doc['digest'], 'authority': 'original_text_only'}


def validate_refs(refs, document, *, required=True):
    if not isinstance(refs, list) or (required and not refs):
        raise SourceOutputError('Original source references are required')
    units = {u['source_id']: u for u in document['units']}
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) != {'source_id', 'quote'} or
                ref['source_id'] not in units or not isinstance(ref['quote'], str) or
                not ref['quote'].strip() or normalized(ref['quote']) not in normalized(units[ref['source_id']]['text'])):
            raise SourceOutputError('Invalid or fabricated original source excerpt')
    return deepcopy(refs)


def source_document_node(state):
    state['source_editorial_version'] = VERSION
    state['source_document'] = build_document(state)
    from pathlib import Path
    from utils.persistence import _atomic_json
    _atomic_json(Path(state['output_dir'])/'content/source_document.json', state['source_document'])
    return state


def locate_refs(refs, document):
    """Map normalized whitespace quotes back to exact original chunk/paragraph spans."""
    validate_refs(refs, document)
    units = {u['source_id']: u for u in document['units']}
    result = []
    for ref in refs:
        unit = units[ref['source_id']]
        pattern = r'\s+'.join(re.escape(token) for token in ref['quote'].split())
        from itertools import islice
        spans = list(islice(re.finditer(pattern, unit['text']), 65))
        truncated = len(spans) > 64
        matches = [{'start': match.start(), 'end': match.end(),
                    'original_quote': unit['text'][match.start():match.end()],
                    'paragraph_ids': [p['paragraph_id'] for p in unit['paragraphs']
                        if p['start'] < match.end() and match.start() < p['end']]}
                   for match in spans[:64]]
        if not matches:
            raise SourceOutputError('Original excerpt normalization has no exact span mapping')
        result.append({**deepcopy(ref), 'section_id': unit['section_id'],
            'chunk_index': unit['chunk_index'], 'page': unit['page'],
            'location_status': 'ambiguous_many_matches' if truncated else 'located' if len(matches)==1 else 'multiple_matches',
            'matches_truncated': truncated, 'match_limit': 64, 'matches': matches})
    return result
