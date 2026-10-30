"""Extractive, optional display cues over immutable verified sentences."""

import re


BODY_PRESENTATION_VERSION = 'poster_body_v1'
LEGACY_LABELS = {'definition': 'Definition', 'goal': 'Objective', 'setup': 'Evaluation setup',
                 'method': 'Approach', 'result': 'Finding', 'interpretation': 'Implication',
                 'limitation': 'Limitation'}


def extract_label(value, text, title=''):
    """Return the actual local phrase, never a generated scientific assertion.

    Unknown cues disappear. Even an extractive phrase can overclaim when taken
    out of negation/qualification, so assertion-bearing cues are not admitted.
    """
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if not value or len(value) > 64 or len(value.split()) > 6:
        return ''
    if re.search(r'[^\w\s\-/]', value) or re.search(
            r'\b(?:guarantee\w*|causal\w*|significan\w*|superior\w*|novel\w*|optimal\w*|'
            r'robust\w*|proof|improv\w*|best|first|only|no|not)\b', value, re.I):
        return ''
    words = value.split()
    pattern = r'(?<!\w)' + r'\s+'.join(re.escape(w) for w in words) + r'(?!\w)'
    match = re.search(pattern, str(text), re.I)
    if not match or re.search(pattern, str(title), re.I):
        return ''
    # A cue duplicating the sentence opening adds no navigation information.
    if re.match(r'^(?:the\s+|a\s+|an\s+)?' + re.escape(match.group()).replace(r'\ ', r'\s+'),
                str(text), re.I):
        return ''
    return ' '.join(match.group().split())


def paragraphs(section):
    """One shared description for display, mixed-face measurement and styling."""
    meta = section.get('editorial') or {}
    active = bool(meta.get('active') and meta.get('body_style') != 'flat')
    hints = {h['claim_id']: h for h in meta.get('items', []) if isinstance(h, dict) and h.get('claim_id')}
    ids = section.get('claim_ids', [])
    legacy = not section.get('editorial_version') and meta.get('version') in {'poster_editorial_v1', 'poster_editorial_v2', 'poster_editorial_v3'}
    ordered = active and meta.get('presentation_style') == 'steps' and bool(ids) and all(
        hints.get(cid, {}).get('step_index') == i for i, cid in enumerate(ids, 1))
    authored = bool(section.get('editorial_version'))
    seen_labels, seen_kinds, result = set(), set(), []
    main_step = 0
    for i, text in enumerate(section.get('text_content') or []):
        text = str(text).strip()
        if not text:
            continue
        cid = ids[i] if i < len(ids) else ''
        hint = hints.get(cid, {})
        nested = bool(active and hint.get('parent_claim_id') in ids[:i]
                      and (authored or (not ordered and not any(
                          '$' in str(t) for t in section.get('text_content', [])))))
        if not nested:
            main_step += 1
        label = ''
        if active and legacy:
            kind = hint.get('kind')
            label = LEGACY_LABELS.get(kind, '') if kind not in seen_kinds else ''
            seen_kinds.add(kind)
        elif active and meta.get('presentation_style') == 'topics':
            label = (str(hint.get('display_label') or '').strip() if section.get('editorial_version')
                     else extract_label(hint.get('display_label'), text, section.get('section_title', '')))
        if label.casefold() in seen_labels:
            label = ''
        seen_labels.add(label.casefold())
        step = main_step if authored else i + 1
        prefix = ('◦ ' if nested else f'{step}) ' if ordered else '• ') if active else ''
        result.append({'claim_id': cid, 'prefix': prefix, 'label': label,
                       'text': text, 'indent_inches': .30 if nested else 0.0})
    return result


def paragraph_text(item):
    return item['prefix'] + (item['label'] + ': ' if item['label'] else '') + item['text']


def wording_issues(text):
    """Bounded repair hints, never proof that a scientific sentence is wrong."""
    issues = []
    if re.search(r'^(?:(?:in this (?:paper|study),?\s+)|(?:the (?:authors?|paper|study)\s+))'
                 r'(?:propose\w*|present\w*|introduce\w*|report\w*|show\w*|discuss\w*|describe\w*)\b',
                 str(text), re.I):
        issues.append('review_voice')
    if re.search(r'^(?:it is (?:important|worthwhile) to note that|'
                 r'the results (?:clearly )?(?:show|demonstrate) that)\b', str(text), re.I):
        issues.append('indirect_opening')
    return issues
