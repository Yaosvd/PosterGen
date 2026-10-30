"""One measured display-formula plan for current editorial prose and styling."""
from utils.display_formula import (
    CONTENT_BLOCK_GAP, FORMULA_VERTICAL_PADDING, extract_display_formula, measure_formula,
)
from utils.text_formatting import tokenize_styling


def _prefix(segments, count):
    """Retain cue/keyword styles on exactly the formula's editable prefix."""
    pieces = []
    for segment in segments:
        text = segment['text'][:count]
        count -= len(text)
        text = text.replace('\\', '\\\\').replace('*', '\\*')
        if segment['color']:
            text = '<color:' + segment['color'] + '>' + text + '</color>'
        elif segment['bold']:
            text = '**' + text + '**'
        elif segment['italic']:
            text = '*' + text + '*'
        pieces.append(text)
        if count <= 0:
            break
    return ''.join(pieces)


def formula_plan(text, width, font_name, font_size, line_spacing=1.0, description=None, *, styled=False):
    """Return None for ordinary prose, otherwise exact text/formula block boxes.

    The same plan is used before and after FontAgent. Scientific characters are
    neither rewritten nor inferred. The existing display-formula grammar applies.
    """
    from src.layout.body_presentation import paragraph_text
    from src.layout.editorial import presentation_line_count
    from src.layout.text_height_measurement import measure_text_height
    blocks, pending = [], []

    def flush():
        if pending:
            blocks.append({'kind': 'text', 'text': '\n'.join(pending)})
            pending.clear()

    for line in text.split('\n'):
        segments = (tokenize_styling(line.strip()) if styled else
                    [{'text': line.strip(), 'bold': False, 'italic': False, 'color': None}])
        plain = ''.join(s['text'] for s in segments)
        formula = extract_display_formula(plain)
        if formula is None:
            if line.strip():
                pending.append(line)
            continue
        flush()
        if formula.prefix:
            blocks.append({'kind': 'text', 'text': _prefix(segments, len(formula.prefix)),
                           'formula_prefix': True})
        blocks.append({'kind': 'formula', 'formula': formula,
                       'indent_inches': .30 if plain.startswith('◦ ') else 0.0})
    flush()
    if not any(b['kind'] == 'formula' for b in blocks):
        return None
    cues = {paragraph_text(p): p for p in description or []}
    total = 0.0
    for index, block in enumerate(blocks):
        if index and not (block['kind'] == 'formula' and blocks[index - 1].get('formula_prefix')):
            total += CONTENT_BLOCK_GAP
        block['y'] = total
        if block['kind'] == 'text':
            # Prefix blocks have been re-encoded by _prefix even before styling.
            formatted = styled or block.get('formula_prefix')
            lines = [(''.join(s['text'] for s in tokenize_styling(line)) if formatted else line)
                     for line in block['text'].split('\n')]
            plain = '\n'.join(lines)
            items, measured_lines = [], []
            for line in lines:
                # Formula extraction leaves the original prefix; match that
                # prefix to its authored entry to retain mixed-face measurement.
                cue = next((p for authored, p in cues.items()
                            if authored == line or authored.startswith(line + ' ')), None)
                item = {'prefix': '', 'label': '', 'indent_inches': 0, 'text': line}
                if cue:
                    lead = cue['prefix'] + (cue['label'] + ': ' if cue['label'] else '')
                    if line.startswith(lead):
                        item = {**cue, 'text': line[len(lead):]}
                    elif line == lead.rstrip():
                        item = {**cue, 'text': ''}
                items.append(item)
                measured_lines.append(paragraph_text(item))
            ordinary = measure_text_height(plain, width, font_name, font_size, line_spacing,
                margins={'left': .10, 'right': .10, 'top': .05, 'bottom': .05})['optimal_height']
            count = presentation_line_count('\n'.join(measured_lines), width, font_name, font_size, items)
            block['height'] = max(ordinary, count * font_size / 72 * 1.20 + .10)
        else:
            limit = max(.1, width - .20 - block['indent_inches'])
            w, h = measure_formula(block['formula'].mathtext, font_size, limit)
            block.update(width=w, height=h + 2 * FORMULA_VERTICAL_PADDING,
                         x=.10 + block['indent_inches'] + (limit - w) / 2)
        total += block['height']
    return {'blocks': blocks, 'height': total}
