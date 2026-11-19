"""Shared model-authored formatting and legacy display cues."""

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


# A step delimiter or a standalone step heading distinguishes it from a decimal, year,
# equation reference or a sentence such as "Step 2 improved recall".
_STEP_NUMBER = r'[0-9]{1,3}'
_STEP_MARKER = re.compile(
    rf'^(?:'
    rf'(?:Step[ \t]+)?{_STEP_NUMBER}[.)](?:\s+|$)|'
    rf'\({_STEP_NUMBER}\)(?:\s+|$)(?![=+*/^×÷<>≤≥−-])|'
    rf'Step[ \t]+{_STEP_NUMBER}[ \t]*(?:[:：]\s*|[-–—]\s+|(?=\r?\n|$)\s*)|'
    rf'(?:第[ \t]*{_STEP_NUMBER}[ \t]*步|步骤[ \t]*{_STEP_NUMBER})[ \t]*[:：]\s*|'
    rf'{_STEP_NUMBER}、\s*'
    r')(?=\S|$)', re.IGNORECASE)
_BULLETS = re.compile(r'^(?:[•◦]\s+)+(?=\S)')


def split_step_marker(text):
    """Return the visible leading marker, its number and the remaining prose."""
    text = _BULLETS.sub('', text.strip())
    # Models sometimes bold just the marker. Unwrap it only when recognition
    # consumes the entire bold span, keeping scientific stars in prose literal.
    bold = re.match(r'^\*\*([^*\n]{1,32})\*\*', text)
    if bold:
        plain = bold[1] + text[bold.end():]
        marker = _STEP_MARKER.match(plain)
        if marker and marker.end() >= len(bold[1]):
            text = plain
    marker = _STEP_MARKER.match(text)
    if not marker:
        return '', None, text
    prefix = marker[0]
    number = int(re.search(r'[0-9]+', prefix)[0])
    rest = text[marker.end():]
    # "1) Step 1: Collect" has two spellings of the same step. Keep one.
    duplicate = _STEP_MARKER.match(rest)
    # A parenthesized number inside an already labeled step may cite an equation.
    while duplicate and not duplicate[0].startswith('('):
        if int(re.search(r'[0-9]+', duplicate[0])[0]) == number and duplicate[0][0].isalpha():
            prefix = duplicate[0]
        rest = rest[duplicate.end():]
        duplicate = _STEP_MARKER.match(rest)
    return prefix, number, rest


def _fill_missing_step_numbers(items):
    main = [(p, split_step_marker(p['text'])) for p in items if not p['indent_inches']]
    reserved = {number for _, (_, number, _) in main if number is not None}
    next_number = 1
    for item, (prefix, number, body) in main:
        if number is None:
            while next_number in reserved:
                next_number += 1
            number = next_number
            prefix = f'{number}) '
        item.update(prefix=prefix, text=body)
        next_number = max(next_number, number + 1)


def paragraphs(section):
    """One shared description for display, mixed-face measurement and styling."""
    from utils.model_body import FORMAT, paragraphs as model_paragraphs
    if section.get('body_format') == FORMAT:
        ids = section.get('claim_ids', [])
        return [p for i, text in enumerate(section.get('text_content') or [])
                for p in model_paragraphs(text, ids[i] if i < len(ids) else '')]
    meta = section.get('editorial') or {}
    active = bool(meta.get('active') and meta.get('body_style') != 'flat')
    hints = {h['claim_id']: h for h in meta.get('items', []) if isinstance(h, dict) and h.get('claim_id')}
    ids = section.get('claim_ids', [])
    legacy = not section.get('editorial_version') and meta.get('version') in {'poster_editorial_v1', 'poster_editorial_v2', 'poster_editorial_v3'}
    ordered = active and meta.get('presentation_style') == 'steps' and bool(ids) and all(
        hints.get(cid, {}).get('step_index') == i for i, cid in enumerate(ids, 1))
    authored = bool(section.get('editorial_version'))
    seen_labels, seen_kinds, result = set(), set(), []
    preserve_numbers = ordered and meta.get('preserve_step_numbers', False)
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
        if authored and active:
            # A Writer can still echo an explicit list prefix. Keep decimal
            # quantities, negative numbers and formula operators as prose.
            marker = r'(?:[•◦]|[0-9]{1,2}[.)])' if ordered and (not preserve_numbers or nested) else r'[•◦]'
            text = re.sub(rf'^(?:{marker}\s+)+(?=\S)', '', text)
        if label.casefold() in seen_labels:
            label = ''
        seen_labels.add(label.casefold())
        step = main_step if authored else i + 1
        prefix = ('◦ ' if nested else f'{step}) ' if ordered else '• ') if active else ''
        result.append({'claim_id': cid, 'prefix': prefix, 'label': label,
                       'text': text, 'indent_inches': .30 if nested else 0.0})
    if preserve_numbers:
        _fill_missing_step_numbers(result)
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
