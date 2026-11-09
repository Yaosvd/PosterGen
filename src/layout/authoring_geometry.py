"""Prose-independent module geometry shared by planning and compilation."""
from copy import deepcopy
import math

from src.layout.editorial_composition import HORIZONTAL, VERTICAL
from src.layout.editorial_body_budget import _density, _reference

VERSION = 'editorial_authoring_geometry_v2'
IMAGE_WIDTH_FRACTION = .40
MIN_HORIZONTAL_BOARD_WIDTH_FRACTION = .50
MIN_HORIZONTAL_ASPECT = 3.0
MIN_IMAGE_LINEAR_GAIN = 1.30
MIN_BODY_CAPACITY_RETENTION = .90


def horizontal_candidate_eligible(width, height, content_width):
    """Only wide, shallow bands may compete with the default vertical layout."""
    return (width / content_width >= MIN_HORIZONTAL_BOARD_WIDTH_FRACTION and
            width / height >= MIN_HORIZONTAL_ASPECT)


def title_cost(agent, section, width, state):
    if not section.get('section_title'):
        return 0.0
    elements = agent._create_section_title_design(section, 0, 0, width, state)
    return max(e['y'] + e['height'] for e in elements) + float(agent.config['layout']['title_to_content_spacing'])


def dimensions(agent, section, width, height, state, mode):
    """Return relative boxes, without reading or measuring any body prose."""
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError('Invalid planned module dimensions')
    padding = float(agent.config['layout']['text_padding']['left_right'])
    inner = width - 2 * padding
    title = title_cost(agent, section, width, state)
    available = height - title
    below = float(agent.config['layout']['visual_spacing']['below_visual'])
    gap = max(.3, float(agent.config['layout']['element_spacing']))
    assets = section.get('visual_assets') or []
    rows = []
    if mode == HORIZONTAL and assets:
        aspects = []
        for asset in assets:
            w, h, _ = agent._calculate_visual_height(asset['visual_id'], 1, state, 1e6, max_height_fraction=1)
            if not all(math.isfinite(v) and v > 0 for v in (w, h)):
                raise ValueError('Invalid planned image aspect')
            aspects.append(w / h)
        stack_room = available - below * (len(aspects) - 1)
        # Once direction is frozen, preserve positive renderable boxes even in a
        # later undersized trial. Its overflow remains visible in exact metrics.
        image_width = min(inner * IMAGE_WIDTH_FRACTION,
                          max(.01, stack_room) / sum(1 / a for a in aspects))
        y = 0.0
        for asset, aspect in zip(assets, aspects):
            h = image_width / aspect
            rows.append({'visual_id': asset['visual_id'], 'x': 0.0, 'y': y,
                         'width': image_width, 'height': h, 'scale': image_width / inner})
            y += h + below
        visual_height = y - below
        text_x, text_width, text_y = image_width + gap, inner - image_width - gap, title
    else:
        y = title
        for asset in assets:
            w, h, scale = agent._calculate_visual_height(asset['visual_id'], inner, state, height)
            rows.append({'visual_id': asset['visual_id'], 'x': (inner-w)/2, 'y': y-title,
                         'width': w, 'height': h, 'scale': scale})
            y += h + below
        visual_height = max(0.0, y-title-below) if assets else 0.0
        text_x, text_width, text_y = 0.0, inner, y
    return {'mode': mode if assets else None, 'title_height': title,
            'visuals': rows, 'visual_height': visual_height,
            'text_x': text_x, 'text_y': text_y, 'text_width': text_width,
            'text_height_available': height-text_y, 'content_height': available,
            'padding': padding}


def problems(box, density):
    issues = []
    min_width = max(4.0, 10 * density['font_size_pt'] / 72)
    min_height = density['body_reserve_inches'] + 2 * density['line_height_inches']
    if box['text_width'] < min_width:
        issues.append('body_width_below_minimum')
    if box['text_height_available'] < min_height:
        issues.append('body_height_below_two_reference_lines')
    if box['title_height'] + box['visual_height'] > box['text_y'] + box['text_height_available'] + 1e-6:
        issues.append('fixed_content_overflow')
    return issues


def select_direction(agent, section, width, height, content_width, state, density):
    """Compare prewrite geometry, never use authored prose or certify readability.

    In a band, horizontal must either rescue an infeasible vertical body without
    shrinking any image, or enlarge at least one image by 30% while retaining
    90% of the vertical word reference and not shrinking any other image.
    Outside bands, infeasibility goes to the existing bounded replanning path.
    """
    vertical = dimensions(agent, section, width, height, state, VERTICAL)
    eligible = bool(section.get('visual_assets')) and horizontal_candidate_eligible(
        width, height, content_width)
    def evidence(box):
        return {'body_width_inches': box['text_width'],
                'body_height_available_inches': box['text_height_available'],
                'reference_words': _reference(density, box['text_width'],
                                               box['text_height_available'])['reference_words'],
                'issues': problems(box, density), 'visuals': deepcopy(box['visuals'])}
    decision = {'eligible': eligible, 'module_width_fraction': width/content_width,
                'module_aspect': width/height, 'selected_mode': vertical['mode'],
                'reason': 'outside_horizontal_band' if section.get('visual_assets') else 'text_only',
                'candidates': {VERTICAL: evidence(vertical)},
                'vertical_height_capped_visual_ids': [r['visual_id'] for r in vertical['visuals']
                    if (width-2*vertical['padding'])*r['height']/r['width'] > height*.30+1e-9]}
    if not eligible:
        return vertical, decision
    horizontal = dimensions(agent, section, width, height, state, HORIZONTAL)
    v, h = decision['candidates'][VERTICAL], evidence(horizontal)
    decision['candidates'][HORIZONTAL] = h
    vertical_images = {r['visual_id']: r for r in vertical['visuals']}
    ratios = {r['visual_id']: r['width']/vertical_images[r['visual_id']]['width']
              for r in horizontal['visuals']}
    decision['image_linear_ratios'] = ratios
    retention = h['reference_words']/v['reference_words'] if v['reference_words'] > 0 else None
    decision['body_capacity_retention'] = retention
    images_preserved = all(r >= 1.0-1e-9 for r in ratios.values())
    if h['issues']:
        decision['reason'] = 'horizontal_infeasible'
    elif not images_preserved:
        decision['reason'] = 'horizontal_shrinks_image'
    elif v['issues']:
        decision['reason'] = 'horizontal_restores_body_space'
        decision['selected_mode'] = HORIZONTAL
    elif (max(ratios.values()) >= MIN_IMAGE_LINEAR_GAIN-1e-9 and
          retention is not None and retention >= MIN_BODY_CAPACITY_RETENTION):
        decision['reason'] = 'larger_images_with_body_capacity'
        decision['selected_mode'] = HORIZONTAL
    else:
        decision['reason'] = 'vertical_preferred_no_clear_gain'
    return (horizontal if decision['selected_mode'] == HORIZONTAL else vertical), decision


def prepare_geometry(state, candidate, zones):
    from src.agents.layout_agent import LayoutAgent
    from src.workflow.editorial_contract import make_board
    from src.layout.editorial_layout import layout_spec
    agent = LayoutAgent()
    density = _density(agent, state)
    sections = {s['section_id']: s for s in make_board(candidate)['spatial_content_plan']['sections']}
    modules = {m['module_id']: m for m in candidate['modules']}
    width = float(state['poster_width']) - 2*agent.poster_margin
    height = (float(state['poster_height'])-2*agent.poster_margin)*(1-agent.title_height_fraction)
    top = agent.poster_margin+(float(state['poster_height'])-2*agent.poster_margin)*agent.title_height_fraction
    gap = agent._inter_section_spacing(state)
    frames, modes, failures, decisions = [], {}, [], {}
    for zone in layout_spec(state, candidate, zones)['zones']:
        ids = zone['section_ids']
        w, h = width*zone['width'], height*zone['height']
        available = h-gap*(len(ids)-1)
        weight = sum(modules[mid]['space_weight'] for mid in ids)
        y = top+height*zone['y']
        for mid in ids:
            allocated = available*modules[mid]['space_weight']/weight
            section = sections[mid]
            box, decisions[mid] = select_direction(agent, section, w, allocated, width, state, density)
            issues = problems(box, density)
            x = agent.poster_margin+width*zone['x']
            reference = _reference(density, box['text_width'], box['text_height_available'])
            frame = {'module_id': mid, 'zone_id': zone['zone_id'],
                     'module_frame': {'x': x, 'y': y, 'width': w, 'height': allocated},
                     'body_frame': {'x': x+box['padding']+box['text_x'], 'y': y+box['text_y'],
                                    'width': box['text_width'], 'height': box['text_height_available']},
                     'body_layout': box['mode'], 'title_and_gap_height': box['title_height'],
                     'visuals': deepcopy(box['visuals']), 'reference': reference, 'issues': issues}
            frames.append(frame)
            if section['visual_assets']:
                modes[mid] = box['mode']
            if issues:
                failures.append({'module_id': mid, 'issues': issues, 'body_frame': frame['body_frame']})
            y += allocated+gap
    return {'version': VERSION, 'image_width_fraction': IMAGE_WIDTH_FRACTION,
            'direction_policy': {'minimum_board_width_fraction': MIN_HORIZONTAL_BOARD_WIDTH_FRACTION,
                'minimum_aspect': MIN_HORIZONTAL_ASPECT, 'minimum_image_linear_gain': MIN_IMAGE_LINEAR_GAIN,
                'minimum_body_capacity_retention': MIN_BODY_CAPACITY_RETENTION},
            'direction_decisions': decisions,
            'calibration': density, 'zones': deepcopy(zones), 'modules': modes,
            'frames': frames, 'failures': failures, 'scientific_verified': False,
            'image_readability_verified': False}


def horizontal_plan(agent, section, width, height, state):
    from src.layout.editorial import presentation_lines
    from src.layout.body_presentation import paragraphs
    box = dimensions(agent, section, width, height, state, HORIZONTAL)
    if box['text_width'] <= 0:
        raise ValueError('Planned horizontal composition has no text width')
    prose = agent._measure_body_text(presentation_lines(section),
        box['text_width']+2*box['padding'], state, editorial=True,
        presentation=paragraphs(section))['height']
    body = max(box['visual_height'], prose)
    shift = max(0.0, min(box['content_height'], body)-box['visual_height'])/2
    for row in box['visuals']:
        row['y'] += shift
    return {'title_height': box['title_height'], 'body_height': body,
            'text_height': prose, 'visual_height': box['visual_height'],
            'text_column_width': box['text_width']+2*box['padding'], 'text_x': box['text_x'],
            'visuals': box['visuals'], 'visual_area': sum(r['width']*r['height'] for r in box['visuals']),
            'minimum_height': box['title_height']+body, 'measurement': 'exact', 'candidate_limit': 1}


def assert_initial_frames(geometry, result):
    """Check the first authored measurement against the exact supplied boxes."""
    for row in geometry['frames']:
        mid = row['module_id']
        container = next(e for e in result['layout'] if e.get('section_id') == mid and e['type'] == 'section_container')
        body = next(e for e in result['layout'] if e.get('section_id') == mid and e['type'] == 'text')
        for key, value in row['module_frame'].items():
            if not math.isclose(container['module_frame'][key], value, abs_tol=1e-7):
                raise ValueError('Initial module frame differs from writing budget: '+mid)
        actual = {**{k: body[k] for k in ('x', 'y', 'width')},
                  'height': container['module_frame']['y']+container['module_frame']['height']-body['y']}
        if any(not math.isclose(actual[k], v, abs_tol=1e-7) for k, v in row['body_frame'].items()):
            raise ValueError('Initial body frame differs from writing budget: '+mid)
        visuals = [e for e in result['layout'] if e.get('section_id') == mid and e['type'] == 'visual']
        if [e['visual_id'] for e in visuals] != [e['visual_id'] for e in row['visuals']]:
            raise ValueError('Initial visual order differs from writing budget')
        for visual, planned in zip(visuals, row['visuals']):
            if any(not math.isclose(visual[k], planned[k], abs_tol=1e-7) for k in ('width', 'height')):
                raise ValueError('Initial image dimensions differ from writing budget: '+mid)
