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
        text = text.replace('\\', '\\\\').replace('*', '\\*').replace('<', '\\<')
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
    blocks, pending, pending_cues = [], [], []

    def flush():
        if pending:
            block = {'kind': 'text', 'text': '\n'.join(pending)}
            if model_formatted:
                block['paragraphs'] = list(pending_cues)
            blocks.append(block)
            pending.clear()
            pending_cues.clear()

    model_formatted = bool(description and description[0].get('model_authored'))
    for line_index, line in enumerate(text.split('\n')):
        cue = description[line_index] if model_formatted and line_index < len(description) else None
        segments = (tokenize_styling(line.strip()) if styled else
                    [{'text': line.strip(), 'bold': False, 'italic': False, 'color': None}])
        plain = ''.join(s['text'] for s in segments)
        formula = extract_display_formula(plain)
        if formula is None:
            if line.strip():
                pending.append(line)
                pending_cues.append(cue)
            continue
        flush()
        if formula.prefix:
            block = {'kind': 'text', 'text': _prefix(segments, len(formula.prefix)),
                     'formula_prefix': True}
            if model_formatted:
                block['paragraphs'] = [cue]
            blocks.append(block)
        blocks.append({'kind': 'formula', 'formula': formula,
                       'indent_inches': (description[line_index]['indent_inches']
                           if model_formatted and line_index < len(description) else
                           .30 if plain.startswith('◦ ') else 0.0)})
    flush()
    if not any(b['kind'] == 'formula' for b in blocks):
        return None
    def visible_line(line):
        return ''.join(s['text'] for s in tokenize_styling(line))
    cues = {(visible_line(paragraph_text(p)) if model_formatted else paragraph_text(p)): p
            for p in description or []}
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
            encoded_lines = block['text'].split('\n')
            for line_index, line in enumerate(lines):
                # Formula extraction leaves the original prefix; match that
                # prefix to its authored entry to retain mixed-face measurement.
                cue = (block['paragraphs'][line_index] if model_formatted else
                       next((p for authored, p in cues.items()
                             if authored == line or authored.startswith(line + ' ')), None))
                item = {'prefix': '', 'label': '', 'indent_inches': 0, 'text': line}
                if cue:
                    lead = cue['prefix'] + (cue['label'] + ': ' if cue['label'] else '')
                    if line.startswith(lead):
                        item = {**cue, 'text': line[len(lead):]}
                    elif line == lead.rstrip():
                        item = {**cue, 'text': ''}
                if model_formatted:
                    item = {**item, 'model_authored': True, 'prefix': '', 'label': '',
                            'text': encoded_lines[line_index],
                            'indent_inches': cue['indent_inches'] if cue else 0}
                items.append(item)
                measured_lines.append(paragraph_text(item))
            ordinary = measure_text_height(plain, width, font_name, font_size, line_spacing,
                margins={'left': .10, 'right': .10, 'top': .05, 'bottom': .05})['optimal_height']
            count = presentation_line_count('\n'.join(measured_lines), width, font_name, font_size, items)
            block['height'] = max(ordinary, count * font_size / 72 * 1.20 + .10)
            if model_formatted:
                block['paragraphs'] = items
        else:
            limit = max(.1, width - .20 - block['indent_inches'])
            w, h = measure_formula(block['formula'].mathtext, font_size, limit)
            block.update(width=w, height=h + 2 * FORMULA_VERTICAL_PADDING,
                         x=.10 + block['indent_inches'] + (limit - w) / 2)
        total += block['height']
    return {'blocks': blocks, 'height': total}
