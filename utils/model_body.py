"""Model-authored list markers and bold spans, shared by all body consumers.

Only **bold** outside math is styling. Single stars, backslashes and unsupported
markup are literal scientific text. No list marker or label is ever generated.
"""
import re

FORMAT = 'model_body_v1'
_MATH = re.compile(r'\$\$.*?\$\$|\$[^$\n]+\$|\\\[.*?\\\]|\\\(.*?\\\)')
_BOLD = re.compile(r'(?<![\w\\])\*\*(?=\S)(.+?)\*\*(?![\w*])')
_MARKER = re.compile(r'^(?:[•◦\-*]|\d+[.)])\s+')


def escape(text):
    return text.replace('\\', '\\\\').replace('*', '\\*').replace('<', '\\<')


def encode_line(text):
    """Encode the limited author grammar for the existing renderer tokenizer."""
    def prose(value):
        parts, start = [], 0
        for match in _BOLD.finditer(value):
            if not match[1].endswith((' ', '\t')):
                parts += [escape(value[start:match.start()]), '**' + escape(match[1]) + '**']
                start = match.end()
        return ''.join(parts) + escape(value[start:])
    parts, start = [], 0
    for match in _MATH.finditer(text):
        parts += [prose(text[start:match.start()]), escape(match[0])]
        start = match.end()
    return ''.join(parts) + prose(text[start:])


def indentation(line):
    """Two authored spaces per level; an explicit sub-bullet also denotes support."""
    spaces = len(line) - len(line.lstrip(' '))
    return .30 * max(spaces // 2, int(line.lstrip().startswith('◦ ')))


def paragraphs(text, claim_id=''):
    return [{'claim_id': claim_id, 'prefix': '', 'label': '',
             'text': encode_line(line.strip()), 'indent_inches': indentation(line),
             'model_authored': True}
            for line in text.splitlines() if line.strip()]


def visible(text):
    from utils.text_formatting import tokenize_styling
    return '\n'.join(''.join(s['text'] for s in tokenize_styling(p['text']))
                     for p in paragraphs(text))


def prose(text):
    """Diagnostic comparison only; never used to transform displayed content."""
    return ' '.join(_MARKER.sub('', line).strip() for line in visible(text).splitlines())


def measured_lines(text, width, fonts, description, glyph_width=None):
    """Count wraps from the same decoded bold runs and indents as the renderer."""
    from utils.text_formatting import tokenize_formatting
    total = 0
    for index, line in enumerate(text.split('\n')):
        item = description[index] if index < len(description) else {}
        available = max(1, (width - .20 - item.get('indent_inches', 0)) * 72 * .98)
        # Collect words across run boundaries (bold need not end at a word edge).
        words, word, gap = [], 0.0, 0.0
        for run in tokenize_formatting(line):
            face = int(run['bold'])
            def length(part):
                return (glyph_width(face, part) if glyph_width else
                        float(fonts[face].getlength(part))) * 1.03
            for part in re.findall(r'\s+|\S+', run['text']):
                if part.isspace():
                    if word:
                        words.append((gap, word)); word = 0.0
                        gap = 0.0
                    gap += length(part)
                else:
                    word += length(part)
        if word:
            words.append((gap, word))
        used, count = 0.0, 1
        for gap, word in words:
            if used and used + gap + word > available:
                count += 1; used = 0.0
            used += (gap if used else 0) + word
            # The shared fitting backend wraps long tokens instead of clipping.
            while used > available:
                count += 1; used -= available
        total += count
    return total


def formatting_errors(entries, style):
    """Diagnose explicit doubled markers and numbered-step gaps, never strip digits."""
    errors, expected, has_main = [], 1, False
    for index, entry in enumerate(entries):
        for line in entry['text'].splitlines():
            stripped = visible(line).strip()
            if not stripped:
                continue
            marker = _MARKER.match(stripped)
            if marker and _MARKER.match(stripped[marker.end():]):
                errors.append((index, 'Repeated list marker'))
            nested = indentation(line) > 0
            if nested and not has_main:
                errors.append((index, 'Supporting paragraph must follow a main paragraph'))
            if stripped and not nested:
                has_main = True
            number = re.match(r'^(\d+)[.)]\s+(?=\S)', stripped)
            if style == 'steps' and number and not nested:
                if int(number[1]) != expected:
                    errors.append((index, 'Number main steps consecutively from 1'))
                expected += 1
    return errors
