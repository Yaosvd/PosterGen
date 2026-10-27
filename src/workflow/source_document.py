"""Immutable original-paper material. No pre-extracted scientific permission bank."""
from copy import deepcopy
import json
import re

from utils.persistence import digest, file_hash

VERSION = 'source_editorial_v1'
DOCUMENT_VERSION = 'original_sections_v2'
MAX_SOURCE_CHARS = 240_000


class SourceOutputError(ValueError):
    """Diagnosed model/scientific/finite-fit failure, not an infrastructure failure."""


class SourceProtocolError(SourceOutputError):
    """Malformed/incomplete verdict; never a trigger for substantive prose editing."""


class SourceLocatorError(SourceProtocolError):
    """An invalid location, never a license to rewrite scientific prose."""


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
        if state.get('source_extraction_report'):
            pattern = r'\s+'.join(re.escape(token) for token in text.split())
            from itertools import islice
            raw_matches = list(islice(re.finditer(pattern,raw),65))
            if not raw_matches or len(raw_matches)>64:
                raise SourceOutputError('Original chunk PDF locations are missing or exceed the ambiguity bound')
            unit['source_location']['raw_spans']=[{'start':m.start(),'end':m.end()} for m in raw_matches]
            unit['source_location']['pdf_location_status']='located' if len(raw_matches)==1 else 'multiple_matches'
            unit['source_location']['pdf_regions'] = [
                {'page': b['page'], 'region_id': b['region_id'], 'bbox': b['pdf_bbox'],
                 'raw_start': max(match.start(), b['start']), 'raw_end': min(match.end(), b['end'])}
                for match in raw_matches for b in state['source_extraction_report']['blocks']
                if b['start'] < match.end() and match.start() < b['end']]
            pages={r['page'] for r in unit['source_location']['pdf_regions']}
            unit['page']=next(iter(pages)) if len(pages)==1 else None
        units.append(unit)
    extraction = state.get('source_extraction_report')
    if state.get('pdf_path'):
        from utils.source_pdf import validate_extraction
        validate_extraction(extraction, raw, file_hash(state['pdf_path']))
    assets = {}
    for prefix, field in (('figure', 'images'), ('table', 'tables')):
        for key, asset in (state.get(field) or {}).items():
            assets[f'{prefix}_{key}'] = {'caption': asset.get('caption', ''),
                'caption_source':deepcopy(asset.get('caption_source')),
                'source_path': asset.get('path'), 'source_hash': file_hash(asset['path']) if asset.get('path') else None,
                'aspect': asset.get('aspect'), 'source_role': next((role for role, ids in
                    (state.get('classified_visuals') or {}).items() if isinstance(ids, list) and f'{prefix}_{key}' in ids), None)}
    doc = {'version': DOCUMENT_VERSION, 'raw_text': raw, 'raw_digest': digest(raw),
           'paper_pdf_hash': file_hash(state['pdf_path']) if state.get('pdf_path') else None,
           'units': units, 'assets': assets, 'normalization': 'whitespace_only_v1',
           'extraction': deepcopy(extraction)}
    doc['digest'] = digest(doc)
    return doc


def validate_document(document, *, pdf_path=None):
    doc = deepcopy(document or {})
    expected = doc.pop('digest', None)
    if (doc.get('version') != DOCUMENT_VERSION or expected != digest(doc) or
            doc.get('raw_digest') != digest(doc.get('raw_text')) or not doc.get('units')):
        raise ValueError('Original source document digest mismatch')
    if pdf_path and file_hash(pdf_path) != doc.get('paper_pdf_hash'):
        raise ValueError('Original PDF changed after extraction')
    if doc.get('paper_pdf_hash'):
        from utils.source_pdf import validate_extraction
        validate_extraction(doc.get('extraction'), doc['raw_text'], doc['paper_pdf_hash'])
    ids = [u['source_id'] for u in doc['units']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate original source identity')
    for asset in doc.get('assets', {}).values():
        if asset.get('source_path') and file_hash(asset['source_path']) != asset.get('source_hash'):
            raise ValueError('Original source asset digest mismatch')
    return document


def source_material(state):
    """Complete continuous sections; explicitly refuse an overlarge context."""
    doc = validate_document(state['source_document'],pdf_path=state.get('pdf_path'))
    units = [{k: deepcopy(v) for k, v in u.items() if k != 'paragraphs'} for u in doc['units']]
    for unit, original in zip(units, doc['units']):
        unit['text'] = '\n\n'.join('['+p['paragraph_id']+']\n'+p['text'] for p in original['paragraphs'])
        region_ids={(r['page'],r['region_id']) for r in unit['source_location'].get('pdf_regions',[])}
        unit['pdf_layout']=[{'page':b['page'],'region_id':b['region_id'],'kind':b['kind'],
            'lines':deepcopy(b['native_lines'])} for b in (doc.get('extraction') or {}).get('blocks',[])
            if (b['page'],b['region_id']) in region_ids and b['kind'] in {'Table','Equation'}]
    # IDs are annotations around continuous verbatim paragraphs, not facts.

    if sum(len(u['text']) for u in units) > MAX_SOURCE_CHARS:
        raise SourceOutputError('Complete original sections exceed bounded context; no silent truncation')
    material = {'units': units, 'assets': {key: {k: v for k, v in value.items()
            if k not in {'source_path'}} for key, value in doc['assets'].items()},
            'source_digest': doc['digest'], 'authority': 'original_text_only'}
    if len(json.dumps(material,ensure_ascii=False)) > MAX_SOURCE_CHARS:
        raise SourceOutputError('Complete original source/context exceeds bounded context; no silent truncation')
    return material


def validate_refs(refs, document, *, required=True):
    if not isinstance(refs, list) or (required and not refs):
        raise SourceOutputError('Original source references are required')
    units = {u['source_id']: u for u in document['units']}
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) not in ({'source_id', 'quote'}, {'source_id', 'quote', 'paragraph_ids'}) or
                ref['source_id'] not in units or not isinstance(ref['quote'], str) or
                not ref['quote'].strip() or normalized(ref['quote']) not in normalized(units[ref['source_id']]['text'])):
            raise SourceOutputError('Invalid original source locator or nonexact excerpt')
        if 'paragraph_ids' in ref:
            ids = ref['paragraph_ids']
            paragraphs = {p['paragraph_id']: p for p in units[ref['source_id']]['paragraphs']}
            if (not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or
                    ids[0] not in paragraphs or ref['quote'] != paragraphs[ids[0]]['text']):
                raise SourceOutputError('Original paragraph binding does not match its exact source span')
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
        if ref.get('paragraph_ids'):
            paragraph = next(p for p in unit['paragraphs'] if p['paragraph_id'] == ref['paragraph_ids'][0])
            spans = [m for m in re.finditer(re.escape(paragraph['text']), unit['text']) if m.start() == paragraph['start'] and m.end() == paragraph['end']]
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
            'pdf_regions': deepcopy(unit['source_location'].get('pdf_regions',[])),
            'pdf_region_scope': 'original_chunk_regions',
            'location_status': 'ambiguous_many_matches' if truncated else 'located' if len(matches)==1 else 'multiple_matches',
            'matches_truncated': truncated, 'match_limit': 64, 'matches': matches})
    return result


def bind_paragraph_refs(value, document):
    """Resolve model-selected paragraph IDs to program-copied original text.

    This is location binding, never scientific acceptance. References may cover
    several passages; the unchanged semantic verifier must establish support.
    """
    units = {u['source_id']: u for u in document['units']}
    def walk(obj, path='$'):
        if isinstance(obj, list):
            return [walk(v, f'{path}[{i}]') for i,v in enumerate(obj)]
        if not isinstance(obj, dict):
            return deepcopy(obj)
        result = {}
        for key, val in obj.items():
            if key != 'source_refs':
                result[key] = walk(val, path+'.'+key)
                continue
            if not isinstance(val, list) or not val:
                raise SourceLocatorError(path+'.source_refs: select at least one original paragraph')
            resolved = []
            seen = set()
            for i, ref in enumerate(val):
                here = f'{path}.source_refs[{i}]'
                if not isinstance(ref, dict) or set(ref) != {'source_id', 'paragraph_ids'}:
                    raise SourceLocatorError(here+': expected source_id and paragraph_ids, not a rewritten quote')
                unit = units.get(ref['source_id'])
                ids = ref['paragraph_ids']
                if unit is None or not isinstance(ids,list) or not ids or any(not isinstance(p,str) for p in ids) or len(set(ids)) != len(ids):
                    raise SourceLocatorError(here+': invalid source/paragraph IDs')
                paragraphs = {p['paragraph_id']:p for p in unit['paragraphs']}
                for pid in ids:
                    if pid not in paragraphs:
                        raise SourceLocatorError(here+': paragraph does not belong to source: '+pid)
                    if (ref['source_id'],pid) in seen:
                        raise SourceLocatorError(here+': repeated original paragraph: '+pid)
                    seen.add((ref['source_id'],pid))
                    paragraph = paragraphs[pid]
                    resolved.append({'source_id':ref['source_id'], 'paragraph_ids':[pid],
                                     'quote':unit['text'][paragraph['start']:paragraph['end']]})
            result[key] = resolved
        return result
    return walk(value)


def paragraph_hints(value, document):
    """Present existing canonical references in the same locator-only wire format."""
    units = {u['source_id']:u for u in document['units']}
    def walk(obj):
        if isinstance(obj,list):
            return [walk(v) for v in obj]
        if not isinstance(obj,dict):
            return deepcopy(obj)
        result={}
        for key,val in obj.items():
            if key != 'source_refs':
                result[key]=walk(val)
                continue
            rows=[]
            for ref in val:
                if 'quote' not in ref:
                    rows.append(deepcopy(ref));continue
                validate_refs([ref], document)
                ids=ref.get('paragraph_ids')
                if ids is None:
                    # Explicit diagnostic fixtures can contain old exact excerpts.
                    matches=locate_refs([ref],document)[0]['matches']
                    options={tuple(m['paragraph_ids']) for m in matches}
                    if len(options)!=1:
                        raise SourceLocatorError('Ambiguous original paragraph hint')
                    ids=list(next(iter(options)))
                rows.append({'source_id':ref['source_id'],'paragraph_ids':deepcopy(ids)})
            result[key]=rows
        return result
    return walk(value)
