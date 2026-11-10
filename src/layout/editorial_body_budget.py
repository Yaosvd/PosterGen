"""Space-derived writing references; never truncate prose or certify its fit."""
from math import floor, isfinite

from PIL import ImageFont

from src.layout.text_height_measurement import get_font_file_path

VERSION = 'editorial_body_budget_v2'
BODY_FILL_TARGET = .90
# Numerical tolerance in inches, matching initial-frame absolute comparisons.
# This is not a minimum body size or permission to ignore visible overflow.
FIXED_CONTENT_TOLERANCE_INCHES = 1e-7
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
    line_height = calibrated_line_height(size, agent.config)
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


def calibrated_line_height(size, config):
    """Share the existing authoring calibration, using the compiled body size."""
    return size / 72 * max(1.25, float(config['text_measurement'].get(
        'loop_rendered_line_height_factor', 1.20)))


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def measured_body_budgets(result):
    """Read exact frames without remeasurement; invalid evidence stays unknown."""
    from src.config.poster_config import load_config
    config = load_config()
    layout = result.get('layout', [])
    rows = []
    for module in result['report']['modules']:
        mid = module['module_id']
        containers = [e for e in layout if e.get('type') == 'section_container' and e.get('section_id') == mid]
        bodies = [e for e in layout if e.get('type') == 'text' and e.get('section_id') == mid]
        row = {'module_id': mid, 'body_layout': module.get('body_layout'),
               'current_words': module.get('current_words', 0), 'reference_words': None,
               'text_box_width_inches': None, 'available_body_height_inches': None,
               'measured_body_height_inches': None, 'body_overflow_inches': None,
               'fixed_content_overflow_inches': None, 'body_utilization': None,
               'body_spare_height_inches': None, 'body_missing_height_inches': None,
               'body_line_height_inches': None, 'body_measurement_status': 'unknown',
               'basis': 'exact_compiled_text_box_and_allocated_frame'}
        rows.append(row)
        if len(containers) != 1 or len(bodies) != 1:
            continue
        frame, body = containers[0].get('module_frame', {}), bodies[0]
        fixed = [e for e in layout if e.get('section_id') == mid
                 and e.get('type') in {'section_title', 'visual'}]
        values = [frame.get('y'), frame.get('height'), body.get('y'), body.get('height'), body.get('width')]
        if (not all(_finite(v) for v in values) or frame['height'] <= 0 or
                body['height'] <= 0 or body['width'] <= 0 or
                any(not _finite(e.get(k)) for e in fixed for k in ('y', 'height'))):
            continue
        available = frame['y'] + frame['height'] - body['y']
        fixed_bottom = max((e['y'] + e['height'] for e in fixed), default=frame['y'])
        fixed_overflow = fixed_bottom - (frame['y'] + frame['height'])
        if fixed_overflow <= FIXED_CONTENT_TOLERANCE_INCHES:
            fixed_overflow = 0.0
        words = row['current_words']
        reference = max(0, floor(words * BODY_FILL_TARGET * max(0, available) / max(.01, body['height'])))
        row.update(text_box_width_inches=body['width'], available_body_height_inches=available,
                   measured_body_height_inches=body['height'], reference_words=reference,
                   body_overflow_inches=max(0, body['height'] - available),
                   fixed_content_overflow_inches=fixed_overflow,
                   body_spare_height_inches=max(0, available - body['height']),
                   body_missing_height_inches=max(0, BODY_FILL_TARGET * available - body['height']))
        size = body.get('font_size')
        if available > 0 and _finite(size) and size > 0:
            row.update(body_measurement_status='measured', body_utilization=body['height'] / available,
                       body_line_height_inches=calibrated_line_height(size, config))
    return {'version': VERSION, 'modules': rows,
            'instructions': 'Use the remaining BODY space, not whole-module utilization, for prose length. '
                'reference_words is a body-only estimate, not guaranteed fit. '
                'Preserve essential mechanisms, conditions and comparison basis; reduce optional detail '
                'and repeated explanations first. Re-measure real edits. A zero budget or fixed-content '
                'overflow cannot be solved by promising shorter text alone; coordinate legal space '
                'allocation within the frozen image ownership/direction and existing edit allowance.'}
