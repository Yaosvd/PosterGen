"""Prose-independent module geometry shared by planning and compilation."""
from copy import deepcopy
import math

from src.layout.editorial_composition import HORIZONTAL, VERTICAL
from src.layout.editorial_body_budget import _density, _reference

VERSION = 'editorial_authoring_geometry_v7'
HORIZONTAL_SINGLE_IMAGE_WIDTH_FRACTION = .40
HORIZONTAL_MULTI_IMAGE_WIDTH_FRACTION = .60
VERTICAL_IMAGE_HEIGHT_FRACTION = .40
VERTICAL_GROUP_HEIGHT_FRACTION = .60
VERTICAL_ROW_TRIGGER_WIDTH_FRACTION = .60
VERTICAL_ROW_HEIGHT_FRACTION = .40
MIN_HORIZONTAL_BOARD_WIDTH_FRACTION = .40
MIN_HORIZONTAL_ASPECT = 2.0
MIN_IMAGE_LINEAR_GAIN = 1.20
MIN_BODY_CAPACITY_RETENTION = .90


def image_rules():
    """One model-facing policy, derived from the actual sizing/selection constants.

    These limits describe allocation constraints, not proposed or minimum printed
    image sizes. Return fresh data so separate requests cannot mutate the policy.
    """
    height_basis = 'module_height_minus_actual_title_and_title_to_content_gap'
    return {
        'preserve_aspect_ratio': True,
        'space_weight_applies_to': 'whole_module_height',
        'vertical': {
            'height_basis': height_basis,
            'maximum_individual_height_fraction': VERTICAL_IMAGE_HEIGHT_FRACTION,
            'maximum_multi_image_group_height_fraction': VERTICAL_GROUP_HEIGHT_FRACTION,
            'group_includes_inter_image_gaps': True,
            'final_gap_before_prose_is_additional': True,
            'group_shrink': 'uniform_image_scaling_with_fixed_gaps',
            'width_limit': 'module_inner_width',
            'multi_image_row': {
                'try_when_stack_width_fraction_below': VERTICAL_ROW_TRIGGER_WIDTH_FRACTION,
                'stack_width_basis': 'widest_stacked_image_over_module_inner_width',
                'maximum_group_height_fraction': VERTICAL_ROW_HEIGHT_FRACTION,
                'sizing': 'uniform_scale_from_stacked_sizes_fit_width_then_cap_height',
                'requires_every_image_strictly_larger': True,
                'requires_body_space_not_reduced': True,
                'group_horizontal_alignment': 'center',
                'image_vertical_alignment': 'center_within_tallest_image_height',
                'recomputed_for_each_module_size': True}},
        'horizontal': {
            'image_width_basis': 'module_inner_width',
            'maximum_single_image_width_fraction': HORIZONTAL_SINGLE_IMAGE_WIDTH_FRACTION,
            'maximum_multi_image_group_width_fraction': HORIZONTAL_MULTI_IMAGE_WIDTH_FRACTION,
            'sizing_order': 'fit_stack_height_then_cap_width',
            'multi_image_layout': 'vertical_stack_with_common_width',
            'stack_height_basis': height_basis,
            'stack_includes_inter_image_gaps': True},
        'direction': {
            'default': VERTICAL,
            'selected_by': 'program_before_writer',
            'minimum_board_width_fraction': MIN_HORIZONTAL_BOARD_WIDTH_FRACTION,
            'minimum_module_aspect': MIN_HORIZONTAL_ASPECT,
            'requires_each_image_not_smaller_than_vertical': True,
            'minimum_image_linear_gain': MIN_IMAGE_LINEAR_GAIN,
            'minimum_body_capacity_retention': MIN_BODY_CAPACITY_RETENTION,
            'alternative_benefit': 'restore_infeasible_vertical_body_space',
            'frozen_during_later_fitting': True}}


def horizontal_candidate_eligible(width, height, content_width):
    """Only wide, shallow bands may compete with the default vertical layout."""
    return (width / content_width >= MIN_HORIZONTAL_BOARD_WIDTH_FRACTION and
            width / height >= MIN_HORIZONTAL_ASPECT)


def title_cost(agent, section, width, state):
    if section.get('_reserve_single_line_title'):
        # Measure one nonwrapping line with the real title font/template, including
        # its accent block. This probe is local geometry, never authored content.
        section = {**section, 'section_title': 'M'}
        width = max(width, 1000.0)
    if not section.get('section_title'):
        return 0.0
    elements = agent._create_section_title_design(section, 0, 0, width, state)
    return max(e['y'] + e['height'] for e in elements) + float(agent.config['layout']['title_to_content_spacing'])


def vertical_visuals(agent, section, inner_width, content_height, state):
    """Aspect-fit each image, then fit the whole stack below the actual title.

    Inter-image gaps count towards the group cap; the final prose gap does not.
    Keep positive boxes for infeasible trials, whose cap violation is reported
    by problems(), rather than hiding impossible fixed spacing or title overflow.
    """
    assets = section.get('visual_assets') or []
    below = float(agent.config['layout']['visual_spacing']['below_visual'])
    rows = []
    for asset in assets:
        w, h, scale = agent._calculate_visual_height(
            asset['visual_id'], inner_width, state, content_height if content_height > 0 else .01,
            max_height_fraction=VERTICAL_IMAGE_HEIGHT_FRACTION)
        if not all(math.isfinite(v) and v > 0 for v in (w, h)):
            raise ValueError('Invalid planned image aspect')
        rows.append({'visual_id': asset['visual_id'], 'width': w, 'height': h, 'scale': scale})
    if len(rows) > 1:
        room = content_height * VERTICAL_GROUP_HEIGHT_FRACTION - below * (len(rows)-1)
        shrink = min(1.0, (room if room > 0 else .01) / sum(r['height'] for r in rows))
        for row in rows:
            for key in ('width', 'height', 'scale'):
                row[key] *= shrink
    y = 0.0
    for row in rows:
        row.update(x=(inner_width-row['width'])/2, y=y)
        y += row['height'] + below
    return rows


def vertical_visual_plan(agent, section, inner_width, content_height, state):
    """Try one centered image row only when it improves the capped stack.

    Scale the existing stacked sizes uniformly, retaining their relative sizes
    and source order. Each image is vertically centered within the tallest one.
    Reevaluate for every module size; this never changes the image/text direction.
    """
    stacked = vertical_visuals(agent, section, inner_width, content_height, state)
    stack_height = max((r['y']+r['height'] for r in stacked), default=0.0)
    stack_width = max((r['width'] for r in stacked), default=0.0)
    decision = {'attempted': False, 'reason': 'fewer_than_two_images',
                'stack_height': stack_height, 'stack_width': stack_width,
                'stack_width_fraction': stack_width/inner_width if inner_width > 0 else None}
    plan = {'visuals': stacked, 'visual_height': stack_height,
            'image_group_layout': 'vertical_stack' if len(stacked) > 1 else 'single' if stacked else None,
            'image_group_decision': decision}
    if len(stacked) < 2:
        return plan
    if (inner_width <= 0 or content_height <= 0 or
            stack_height > content_height*VERTICAL_GROUP_HEIGHT_FRACTION+1e-9):
        decision['reason'] = 'infeasible_stack_geometry'
        return plan
    if stack_width >= inner_width*VERTICAL_ROW_TRIGGER_WIDTH_FRACTION-1e-9:
        decision['reason'] = 'stack_width_at_or_above_threshold'
        return plan
    decision['attempted'] = True
    gap = float(agent.config['layout']['visual_spacing']['below_visual'])
    width_room = inner_width-gap*(len(stacked)-1)
    if width_room <= 0:
        decision['reason'] = 'row_gaps_exceed_width'
        return plan
    scale = min(width_room/sum(r['width'] for r in stacked),
                content_height*VERTICAL_ROW_HEIGHT_FRACTION/max(r['height'] for r in stacked))
    row_height = max(r['height'] for r in stacked)*scale
    row_width = sum(r['width'] for r in stacked)*scale+gap*(len(stacked)-1)
    decision.update(uniform_scale=scale, row_height=row_height, row_width=row_width,
                    stack_body_height=content_height-stack_height-gap,
                    row_body_height=content_height-row_height-gap)
    if scale <= 1.0+1e-9:
        decision['reason'] = 'not_every_image_larger'
        return plan
    if row_height > stack_height+1e-9 or content_height-row_height-gap <= 0:
        decision['reason'] = 'body_space_reduced_or_nonpositive'
        return plan
    rows = deepcopy(stacked)
    x = (inner_width-row_width)/2
    for row in rows:
        for key in ('width', 'height', 'scale'):
            row[key] *= scale
        row.update(x=x, y=(row_height-row['height'])/2)
        x += row['width']+gap
    decision['reason'] = 'every_image_larger_with_body_space'
    plan.update(visuals=rows, visual_height=row_height, image_group_layout='horizontal_row')
    return plan


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
    group_layout, group_decision = None, None
    if mode == HORIZONTAL and assets:
        aspects = []
        for asset in assets:
            w, h, _ = agent._calculate_visual_height(asset['visual_id'], 1, state, 1e6, max_height_fraction=1)
            if not all(math.isfinite(v) and v > 0 for v in (w, h)):
                raise ValueError('Invalid planned image aspect')
            aspects.append(w / h)
        stack_room = available - below * (len(aspects) - 1)
        width_fraction = (HORIZONTAL_SINGLE_IMAGE_WIDTH_FRACTION if len(aspects) == 1
                          else HORIZONTAL_MULTI_IMAGE_WIDTH_FRACTION)
        # Once direction is frozen, preserve positive renderable boxes even in a
        # later undersized trial. Its overflow remains visible in exact metrics.
        height_fitted_width = max(.01, stack_room) / sum(1 / a for a in aspects)
        image_width = min(height_fitted_width, inner * width_fraction)
        y = 0.0
        for asset, aspect in zip(assets, aspects):
            h = image_width / aspect
            rows.append({'visual_id': asset['visual_id'], 'x': 0.0, 'y': y,
                         'width': image_width, 'height': h, 'scale': image_width / inner})
            y += h + below
        visual_height = y - below
        group_layout = 'vertical_stack' if len(rows) > 1 else 'single'
        text_x, text_width, text_y = image_width + gap, inner - image_width - gap, title
    else:
        visual_plan = vertical_visual_plan(agent, section, inner, available, state)
        rows, visual_height = visual_plan['visuals'], visual_plan['visual_height']
        group_layout, group_decision = visual_plan['image_group_layout'], visual_plan['image_group_decision']
        y = title + visual_height + (below if rows else 0.0)
        text_x, text_width, text_y = 0.0, inner, y
    return {'mode': mode if assets else None, 'title_height': title,
            'visuals': rows, 'visual_height': visual_height,
            'image_group_layout': group_layout, 'image_group_decision': group_decision,
            'text_x': text_x, 'text_y': text_y, 'text_width': text_width,
            'text_height_available': height-text_y, 'content_height': available,
            'padding': padding}


def problems(box):
    """Require real positive body space, not an estimated minimum writing capacity."""
    issues = []
    if not math.isfinite(box['text_width']) or box['text_width'] <= 0:
        issues.append('invalid_body_width')
    if not math.isfinite(box['text_height_available']) or box['text_height_available'] <= 0:
        issues.append('invalid_body_height')
    if box['title_height'] + box['visual_height'] > box['text_y'] + box['text_height_available'] + 1e-6:
        issues.append('fixed_content_overflow')
    if box['mode'] == VERTICAL and box['visuals']:
        available = box['text_y'] + box['text_height_available'] - box['title_height']
        if (any(r['height'] > available * VERTICAL_IMAGE_HEIGHT_FRACTION + 1e-9
                for r in box['visuals']) or
                (len(box['visuals']) > 1 and
                 box['visual_height'] > available * VERTICAL_GROUP_HEIGHT_FRACTION + 1e-9)):
            issues.append('vertical_visual_height_limit_exceeded')
        if (box.get('image_group_layout') == 'horizontal_row' and
                box['visual_height'] > available*VERTICAL_ROW_HEIGHT_FRACTION+1e-9):
            issues.append('vertical_image_row_height_limit_exceeded')
    return issues


def select_direction(agent, section, width, height, content_width, state, density):
    """Compare prewrite geometry, never use authored prose or certify readability.

    In a band, horizontal must either rescue an infeasible vertical body without
    shrinking any image, or enlarge at least one image by 20% while retaining
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
                'issues': problems(box), 'visuals': deepcopy(box['visuals']),
                'image_group_layout': box.get('image_group_layout'),
                'image_group_decision': deepcopy(box.get('image_group_decision'))}
    decision = {'eligible': eligible, 'module_width_fraction': width/content_width,
                'module_aspect': width/height, 'selected_mode': vertical['mode'],
                'reason': 'outside_horizontal_band' if section.get('visual_assets') else 'text_only',
                'candidates': {VERTICAL: evidence(vertical)},
                'vertical_height_capped_visual_ids': [r['visual_id'] for r in vertical['visuals']
                    if r['width'] < width-2*vertical['padding']-1e-9]}
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
    # Compare capacities directly: zero is a rounded reference, not proof that
    # a positive body frame is unusable. The ratio remains diagnostic only.
    required_words = MIN_BODY_CAPACITY_RETENTION * v['reference_words']
    capacity_preserved = h['reference_words'] >= required_words
    decision['body_capacity_retention'] = retention
    decision['body_capacity_comparison'] = {
        'vertical_reference_words': v['reference_words'],
        'horizontal_reference_words': h['reference_words'],
        'minimum_horizontal_reference_words': required_words,
        'passed': capacity_preserved,
        'zero_vertical_reference': v['reference_words'] == 0}
    images_preserved = all(r >= 1.0-1e-9 for r in ratios.values())
    if h['issues']:
        decision['reason'] = 'horizontal_infeasible'
    elif not images_preserved:
        decision['reason'] = 'horizontal_shrinks_image'
    elif v['issues']:
        decision['reason'] = 'horizontal_restores_body_space'
        decision['selected_mode'] = HORIZONTAL
    elif (max(ratios.values()) >= MIN_IMAGE_LINEAR_GAIN-1e-9 and
          capacity_preserved):
        decision['reason'] = 'larger_images_with_body_capacity'
        decision['selected_mode'] = HORIZONTAL
    else:
        decision['reason'] = 'vertical_preferred_no_clear_gain'
    return (horizontal if decision['selected_mode'] == HORIZONTAL else vertical), decision


def prepare_geometry(state, candidate, zones, *, reserve_title_line=False, frozen_modes=None):
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
            if reserve_title_line:
                section['_reserve_single_line_title'] = True
            if frozen_modes is None:
                box, decisions[mid] = select_direction(agent, section, w, allocated, width, state, density)
            else:
                mode = frozen_modes.get(mid, VERTICAL)
                if section['visual_assets'] and mid not in frozen_modes:
                    raise ValueError('Written module missing its prewrite direction')
                box = dimensions(agent, section, w, allocated, state, mode)
                decisions[mid] = {'selected_mode': box['mode'], 'reason': 'prewrite_direction_frozen'}
            issues = problems(box)
            x = agent.poster_margin+width*zone['x']
            reference = _reference(density, box['text_width'], box['text_height_available'])
            frame = {'module_id': mid, 'zone_id': zone['zone_id'],
                     'module_frame': {'x': x, 'y': y, 'width': w, 'height': allocated},
                     'body_frame': {'x': x+box['padding']+box['text_x'], 'y': y+box['text_y'],
                                    'width': box['text_width'], 'height': box['text_height_available']},
                     'body_layout': box['mode'], 'title_and_gap_height': box['title_height'],
                     'image_group_layout': box['image_group_layout'],
                     'image_group_decision': deepcopy(box['image_group_decision']),
                     'visuals': deepcopy(box['visuals']), 'reference': reference, 'issues': issues}
            frames.append(frame)
            if section['visual_assets']:
                modes[mid] = box['mode']
            if issues:
                failures.append({'module_id': mid, 'issues': issues, 'body_frame': frame['body_frame']})
            y += allocated+gap
    return {'version': VERSION,
            'title_basis': 'single_line_reservation' if reserve_title_line else 'actual_title',
            'horizontal_image_policy': image_rules()['horizontal'],
            'vertical_image_policy': {'height_basis': 'module_minus_title_and_gap',
                'maximum_individual_height_fraction': VERTICAL_IMAGE_HEIGHT_FRACTION,
                'maximum_group_height_fraction': VERTICAL_GROUP_HEIGHT_FRACTION,
                'group_includes_inter_image_gaps': True,
                'multi_image_row': image_rules()['vertical']['multi_image_row']},
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
            if row['body_layout'] == VERTICAL:
                position = {'x': row['body_frame']['x']+planned['x'],
                            'y': row['module_frame']['y']+row['title_and_gap_height']+planned['y']}
                if any(not math.isclose(visual[k], v, abs_tol=1e-7) for k, v in position.items()):
                    raise ValueError('Initial image positions differ from writing budget: '+mid)
