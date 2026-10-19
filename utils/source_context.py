"""Read-only body-context overlay. Original source IDs and excerpts stay intact."""

import re
from collections import Counter

from utils.section_utils import HEADING_RE, normalize_heading, classify_section_type

SOURCE_CONTEXT_VERSION = 'body_context_v1'
_FLOAT = re.compile(r'^(?:algorithm|figure|fig\.?|table)\s+\d+[a-z]?\s*[:.\-]', re.I)


def body_context_index(text):
    """Index Markdown spans, distinguishing numbered floats from real headings.

    A numbered caption needs structural evidence (a list, code or table) to
    start a float. The first prose paragraph resumes the enclosing body heading.
    No page coordinates are invented when the parser did not supply them.
    """
    headings = {m.start(): m for m in HEADING_RE.finditer(text)}
    stack, spans = [], []
    float_kind = None
    fence = False
    blocks = list(re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*', text))
    for index, block in enumerate(blocks):
        value = block.group().strip()
        match = headings.get(block.start())
        if match:
            title = normalize_heading(match.group(2))
            following = blocks[index + 1].group().lstrip() if index + 1 < len(blocks) else ''
            caption = _FLOAT.match(title)
            structural = bool(re.match(r'(?:[-*]\s|\d+[.:]\s|```|~~~|\||<table\b)', following, re.I))
            if caption and structural:
                float_kind = title.split()[0].lower().rstrip('.')
                kind = 'float_caption'
            else:
                level = len(match.group(1))
                while stack and stack[-1]['level'] >= level:
                    stack.pop()
                stack.append({'level': level, 'title': title, 'start_char': match.start()})
                float_kind = None
                kind = 'body_heading'
        else:
            is_fence = bool(re.match(r'```|~~~', value))
            structured = bool(re.match(r'(?:[-*]\s|\d+[.:]\s|\||<table\b)', value, re.I))
            if float_kind and (structured or fence or is_fence):
                kind = 'float_body'
            else:
                float_kind = None
                kind = 'body_text'
            if is_fence and value.count('```') + value.count('~~~') == 1:
                fence = not fence
        spans.append({'start_char': block.start(), 'end_char': block.end(),
                      'kind': kind, 'float_kind': float_kind,
                      'heading_path': [entry['title'] for entry in stack],
                      'body_start_char': stack[-1]['start_char'] if stack else 0,
                      'section_type': classify_section_type(stack[-1]['title']) if stack else 'other'})
    return {'version': SOURCE_CONTEXT_VERSION, 'spans': spans}


def evidence_contexts(state):
    """Locate verbatim excerpts; ambiguous/missing matches remain unknown.

    A serialized overlay makes exact attempt replay independent of access to
    the original foundation. It contains references, never replacement prose.
    """
    saved = state.get('source_context_overlay') or {}
    if saved.get('version') == SOURCE_CONTEXT_VERSION:
        return saved
    text = state.get('raw_text') or ''
    index = body_context_index(text)
    tokens = list(re.finditer(r'\S+', text))
    normalized = ' '.join(m.group() for m in tokens)
    # Map normalized offsets back to the immutable parser output.
    offsets, cursor = [], 0
    for token in tokens:
        offsets.append((cursor, cursor + len(token.group()), token.start(), token.end()))
        cursor += len(token.group()) + 1
    result = {}
    sections = {s.get('section_id'): s for s in state.get('section_chunks') or []}
    for item in (state.get('evidence_bank') or {}).get('items', []):
        excerpt = ' '.join(str(item.get('source_excerpt') or '').split())
        hits = list(re.finditer(re.escape(excerpt), normalized)) if excerpt else []
        source = item.get('source') or {}
        section = sections.get(source.get('section_id'), {})
        section = {**(section.get('source') or {}), **section}
        positions = []
        for hit in hits:
            overlapping = [entry for entry in offsets if entry[0] < hit.end() and entry[1] > hit.start()]
            if overlapping:
                positions.append((overlapping[0][2], overlapping[-1][3]))
        local = [p for p in positions if section.get('start_char', 0) <= p[0] < section.get('end_char', len(text))]
        positions = local or positions
        record = {'status': 'unknown', 'original_source_section_id': source.get('section_id')}
        if len(positions) == 1:
            start, end = positions[0]
            spans = [s for s in index['spans'] if s['start_char'] < end and s['end_char'] > start]
            contexts = Counter((s['body_start_char'], tuple(s['heading_path']), s['section_type'])
                               for s in spans if s['kind'] == 'body_text')
            if len(contexts) == 1 and all(s['kind'] == 'body_text' for s in spans):
                anchor, path, section_type = next(iter(contexts))
                record.update(status='located_body', start_char=start, end_char=end,
                              body_start_char=anchor, heading_path=list(path), section_type=section_type,
                              page=source.get('page'), kind='body_text')
        result[str(item['evidence_id'])] = record
    return {'version': SOURCE_CONTEXT_VERSION, 'evidence': result}
