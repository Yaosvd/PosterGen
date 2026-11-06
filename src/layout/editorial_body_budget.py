"""Space-derived writing references; never truncate prose or certify its fit."""
from math import floor

from PIL import ImageFont

from src.layout.measurement_context import measurement_scope
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


def authoring_body_budgets(state, zones):
    """Conditional budgets before the model chooses titles, images and weights.

    Stacked rows reserve the largest possible images for each image count.
    Single-image horizontal alternatives use the existing selector with short
    probe prose. Multiple-image horizontal fits remain for actual first fitting;
    no image subset is selected or excluded here.
    """
    from src.agents.layout_agent import LayoutAgent
    from src.layout.module_composition import side_by_side_plan
    from src.workflow.editorial_contract import asset_index, make_board
    agent = LayoutAgent()
    density = _density(agent, state)
    padding = float(agent.config['layout']['text_padding']['left_right'])
    below = float(agent.config['layout']['visual_spacing']['below_visual'])
    gap = agent._inter_section_spacing(state)
    width = float(state['poster_width']) - 2 * agent.poster_margin
    height = (float(state['poster_height']) - 2 * agent.poster_margin) * (1 - agent.title_height_fraction)
    assets = list(asset_index(state))
    result = []
    with measurement_scope((state.get('critic_config') or {}).get('layout_performance')):
        for zone in zones:
            w, h = width * zone['width'], height * zone['height']
            # A two-line title is an explicit reserve, not a fabricated exact
            # measurement of the future authored title.
            title = agent._measure_section_title('Method\nResults', w, state)['height']
            title += float(agent.config['layout']['title_to_content_spacing'])
            cases = []
            for count in range(1, zone['capacity'] + 1):
                allocated = (h - gap * (count - 1)) / count
                costs = {vid: agent._calculate_visual_height(vid, w - 2 * padding, state, allocated)[1] + below
                         for vid in assets}
                ordered_costs = sorted(costs.values(), reverse=True)
                stacked = []
                for n in range(len(assets) + 1):
                    remaining = allocated - title - sum(ordered_costs[:n])
                    stacked.append({'visual_count': n, **_reference(density, w - 2 * padding, remaining)})
                horizontal = {}
                if w / allocated >= 1.6:
                    for vid in assets:
                        module = {'module_id': 'budget_probe', 'title': 'Method\nResults',
                            'zone_id': zone['zone_id'], 'importance': 2, 'space_weight': 1,
                            'presentation_style': 'plain', 'reader_question': '',
                            'entries': [{'item_id': 'probe', 'text': 'Evidence supports the finding.',
                                         'display_label': '', 'parent_item_id': ''}],
                            'visual_ids': [vid], 'visual_rationale': ''}
                        section = make_board({'modules': [module]})['spatial_content_plan']['sections'][0]
                        plan = side_by_side_plan(agent, section, w, allocated, state)
                        if plan:
                            horizontal[vid] = _reference(density, plan['text_column_width'] - 2 * padding,
                                                         allocated - plan['title_height'])
                cases.append({'modules_in_zone': count, 'assumed_equal_space_weights': True,
                    'allocated_module_height_inches': round(allocated, 4),
                    'title_and_gap_reserve_inches': round(title, 4),
                    'stacked_visual_cost_inches': {k: round(v, 4) for k, v in costs.items()},
                    'stacked_conservative_by_visual_count': stacked,
                    'single_visual_horizontal_reference': horizontal})
            result.append({'zone_id': zone['zone_id'], 'width_inches': round(w, 4),
                           'height_inches': round(h, 4), 'allocation_cases': cases})
    return {'version': VERSION, 'basis': 'conditional_before_authoring', 'calibration': density,
            'inter_module_gap_inches': gap, 'zones': result,
            'instructions': 'Use the case for the ACTUAL number of modules in each zone, not its capacity. '
                'Cases assume equal space_weight; unequal weights allocate (zone_height - gaps) * '
                'module_weight / sum_weights. Subtract title and selected image costs BEFORE estimating prose. '
                'Stacked rows conservatively reserve the largest images at the chosen count; individual '
                'image costs include their following gap. Horizontal references apply ONLY to the named '
                'single image and a two-line title, not to image combinations. Unlisted horizontal '
                'combinations may still fit at actual measurement. These are writing estimates, not '
                'chosen directions, mandatory word totals, image-selection rules or fit certificates. '
                'Labels, more entries, longer titles and display formulas consume additional space. '
                'A zero budget means this assumed composition leaves no safe prose allowance; reconsider '
                'the legal initial allocation/selection rather than omit essential explanation or force one word.'}


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
