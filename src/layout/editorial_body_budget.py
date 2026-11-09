"""Space-derived writing references; never truncate prose or certify its fit."""
from math import floor

from PIL import ImageFont

from src.layout.text_height_measurement import get_font_file_path

VERSION = 'editorial_body_budget_v1'
# Calibration only, never paper evidence or text to insert into a poster.
REFERENCE_WORDS = ('method measurements representation comparison experimental conditions '
                   'prediction observations mechanism results evaluation performance').split()


def _density(agent, state):
    size = float((state.get('styling_interfaces') or {}).get('font_sizes', {}).get(
        'body_text', agent.config['typography']['sizes']['body_text']))
    font = ImageFont.truetype(get_font_file_path(agent.body_text_font_family), round(size))
    # Measure glyphs at the actual face/size; the vocabulary is deliberately
    # technical. This is an English-word reference, not a tokenizer or quota.
    word_width = sum(font.getlength(word + ' ') for word in REFERENCE_WORDS) / len(REFERENCE_WORDS) / 72
    line_height = size / 72 * max(1.25, float(agent.config['text_measurement'].get(
        'loop_rendered_line_height_factor', 1.20)))
    return {'font_name': agent.body_text_font_family, 'font_size_pt': size,
            'line_height_inches': line_height, 'reference_word_width_inches': word_width,
            'assumed_entries': 3, 'body_reserve_inches': .50 + 2 * size / 72 * .10,
            'word_safety_factor': .85}


def _reference(density, width, height):
    """Width is the actual text box, including its internal 0.1in margins."""
    lines = max(0, floor((height - density['body_reserve_inches']) / density['line_height_inches']))
    # Allow one nested bullet's indent plus the visible bullet at each line.
    per_line = max(0, (width - .20 - .30 - density['font_size_pt'] / 72 * .5)
                   / density['reference_word_width_inches'])
    return {'text_box_width_inches': round(width, 4),
            'available_body_height_inches': round(height, 4),
            'estimated_lines': lines,
            'reference_words': max(0, floor(lines * per_line * density['word_safety_factor']))}


def measured_body_budgets(result):
    """Use existing exact compiled frames; no new measurement or layout mutation."""
    layout = result['layout']
    rows = []
    for module in result['report']['modules']:
        mid = module['module_id']
        container = next(e for e in layout if e.get('type') == 'section_container' and e.get('section_id') == mid)
        frame = container['module_frame']
        body = next(e for e in layout if e.get('type') == 'text' and e.get('section_id') == mid)
        available = frame['y'] + frame['height'] - body['y']
        fixed_bottom = max((e['y'] + e['height'] for e in layout
                            if e.get('section_id') == mid and e.get('type') in {'section_title', 'visual'}),
                           default=frame['y'])
        words = module['current_words']
        # This estimate scales BODY height only. In particular, a large image
        # must not make a tiny remaining text slot look like a generous budget.
        reference = max(0, floor(words * .90 * max(0, available) / max(.01, body['height'])))
        rows.append({'module_id': mid, 'body_layout': module.get('body_layout'),
            'text_box_width_inches': body['width'], 'available_body_height_inches': available,
            'measured_body_height_inches': body['height'],
            'body_overflow_inches': max(0, body['height'] - available),
            'fixed_content_overflow_inches': max(0, fixed_bottom - frame['y'] - frame['height']),
            'current_words': words, 'reference_words': reference,
            'basis': 'exact_compiled_text_box_and_allocated_frame'})
    return {'version': VERSION, 'modules': rows,
            'instructions': 'Use the remaining BODY space, not whole-module utilization, for prose length. '
                'reference_words is a conservative body-only estimate, not guaranteed fit or a fill target. '
                'Preserve essential mechanisms, conditions and comparison basis; reduce optional detail '
                'and repeated explanations first. Re-measure real edits. A zero budget or fixed-content '
                'overflow cannot be solved by promising shorter text alone; coordinate legal space '
                'allocation within the frozen image ownership/direction and existing edit allowance.'}
