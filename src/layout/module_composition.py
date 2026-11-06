"""Measured image-left/text-right composition for wide, shallow family modules."""

from src.layout.text_height_measurement import estimate_wrapped_line_count


def fast_body_height(agent, section, text_width, state):
    """Use the family fitter's conservative wrapping and paragraph reserves."""
    from src.layout.editorial import presentation_lines, presentation_line_count
    from src.layout.body_presentation import paragraphs
    content = '\n'.join(presentation_lines(section))
    if not content:
        return 0.0
    sizes = (state.get('styling_interfaces') or {}).get('font_sizes') or {}
    size = float(sizes.get('body_text', agent.config['typography']['sizes']['body_text']))
    lines = estimate_wrapped_line_count(
        content, text_width, agent.body_text_font_family, size,
        margins={'left': .10, 'right': .10, 'top': .05, 'bottom': .05},
        font_width_factor=1.03, render_width_factor=.98)
    meta = section.get('editorial') or {}
    if meta.get('active') and meta.get('body_style') != 'flat':
        lines = max(lines, presentation_line_count(
            content, text_width, agent.body_text_font_family, size, paragraphs(section)))
    height = lines * size / 72 * 1.25 + content.count('\n') * size / 72 * .10 + .50
    if state.get('editorial_version') == 'poster_editorial_v1' and section.get('editorial_version'):
        from src.layout.editorial_text import formula_plan
        plan = formula_plan(content, text_width, agent.body_text_font_family, size,
                            description=paragraphs(section))
        if plan:
            height = max(height, plan['height'] + .10)
    return height


def side_by_side_plan(agent, section, width, height, state):
    """Respect a frozen editorial direction while retaining adaptive dimensions."""
    from src.layout.editorial_composition import frozen_mode, HORIZONTAL, VERTICAL
    mode = frozen_mode(state, section.get('section_id'))
    if (state.get('editorial_version') == 'poster_editorial_v1' and
            state.get('generation_route') == 'optimization_family' and
            state.get('editorial_composition') is not None and section.get('visual_assets') and mode is None):
        raise ValueError('Image-owning module has no frozen editorial composition')
    if mode == VERTICAL:
        return None
    if (state.get('editorial_version') == 'poster_editorial_v1' and section.get('editorial_version')
            and state.get('generation_route') == 'optimization_family'):
        plan = _editorial_side_by_side_plan(agent, section, width, height, state)
        if plan is not None or mode != HORIZONTAL:
            return plan
        return _editorial_side_by_side_plan(agent, section, width, height, state, locked=True)
    plan = _adaptive_side_by_side_plan(agent, section, width, height, state)
    if plan is not None or mode != HORIZONTAL:
        return plan
    return _fixed_side_by_side_plan(agent, section, width, height, state)


def _editorial_side_by_side_plan(agent, section, width, height, state, *, locked=False):
    """Measure three distinct actual image widths before freezing a direction.

    Widths follow the original image aspects and available stack height. This
    avoids three nominal splits collapsing to the same height-capped image.
    Prefer readable image area among fitting plans; never shrink below the
    existing vertical image area just to claim a horizontal fit.
    """
    import math
    from src.layout.body_presentation import paragraphs
    from src.layout.editorial import presentation_lines
    visuals = section.get('visual_assets') or []
    if not visuals or not section.get('text_content') or not height:
        if locked:
            raise ValueError('Frozen horizontal composition lost its image, prose or dimensions')
        return None
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError('Editorial composition has non-renderable dimensions')
    if not locked and width / height < 1.6:
        return None
    padding = float(agent.config['layout']['text_padding']['left_right'])
    gap = max(.3, float(agent.config['layout']['element_spacing']))
    below = float(agent.config['layout']['visual_spacing']['below_visual'])
    inner = width - 2 * padding
    usable = inner - gap
    if usable <= 0:
        if locked:
            raise ValueError('Frozen horizontal composition has no drawable column width')
        return None
    title = 0.0
    if section.get('section_title'):
        title = agent._measure_section_title(section['section_title'], width, state)['height']
        title += float(agent.config['layout']['title_to_content_spacing'])
    # Final body measurement already includes wrapping, render correction and
    # safety padding. Reserving another 20% of the entire region also shrank the
    # image and left a permanent empty band below every image-dominated row.
    body_limit = height - title
    if body_limit <= 0 and not locked:
        return None
    sizes = (state.get('styling_interfaces') or {}).get('font_sizes') or {}
    size = float(sizes.get('body_text', agent.config['typography']['sizes']['body_text']))
    min_text = max(4.0, 10 * size / 72)
    if usable <= min_text and not locked:
        return None
    if locked:
        min_text = min(min_text, usable * .8)
    aspects, stacked_area, stacked_height = [], 0.0, 0.0
    for visual in visuals:
        vw, vh, _ = agent._calculate_visual_height(visual['visual_id'], 1.0, state, 1e6,
                                                   max_height_fraction=1.0)
        if not all(math.isfinite(v) and v > 0 for v in (vw, vh)):
            raise ValueError('Editorial visual has invalid aspect geometry')
        aspects.append(vw / vh)
        vw, vh, _ = agent._calculate_visual_height(visual['visual_id'], inner, state, height)
        stacked_area += vw * vh
        stacked_height += vh + below
    def text_height(text_width):
        return agent._measure_body_text(presentation_lines(section), text_width + 2*padding, state,
            editorial=True, presentation=paragraphs(section))['height']
    stacked_height += text_height(inner)
    max_width = min(usable - min_text,
                    max(.1, body_limit - below*(len(visuals)-1)) / sum(1/a for a in aspects))
    if max_width <= 0:
        return None
    candidates, seen = [], set()
    for fraction in (.6, .8, 1.0):
        image_width = max_width * fraction
        if round(image_width, 9) in seen:
            continue
        seen.add(round(image_width, 9))
        rows, y, area = [], 0.0, 0.0
        for aspect in aspects:
            image_height = image_width / aspect
            rows.append({'width': image_width, 'height': image_height, 'scale': image_width/inner,
                         'x': 0.0, 'y': y})
            y += image_height + below
            area += image_width * image_height
        visual_height = y - below
        prose_height = text_height(usable-image_width)
        body_height = max(visual_height, prose_height)
        if not locked and (body_height > body_limit + 1e-6 or area < stacked_area - .001
                or (area <= stacked_area*1.05 and body_height >= stacked_height-.05)):
            continue
        candidates.append({'title_height': title, 'body_height': body_height,
            'text_height': prose_height, 'visual_height': visual_height,
            'text_column_width': usable-image_width+2*padding,
            'text_x': image_width+gap, 'visuals': rows, 'visual_area': area,
            'measurement': 'exact', 'candidate_limit': 3})
    def rank(plan):
        overflow = max(0.0, title + plan['body_height'] - height)
        return (overflow > .001, overflow, -plan['visual_area'], plan['body_height'])
    if not candidates:
        return None
    selected = min(candidates, key=rank)
    # A region may donate space using another measured split, without dropping
    # below the vertical reference image area or changing the module direction.
    readable = [title+p['body_height'] for p in candidates if p['visual_area'] >= stacked_area-.001]
    selected['minimum_height'] = min(readable, default=title+selected['body_height'])
    # Center the entire image stack within the occupied image/text row, capped
    # at the module bottom. Do not count decorative displacement as extra
    # content height or center against overflowing prose beyond the frame.
    row_height = min(body_limit, selected['body_height'])
    visual_offset = max(0.0, row_height-selected['visual_height']) / 2
    for row in selected['visuals']:
        row['y'] += visual_offset
    return selected


def _adaptive_side_by_side_plan(agent, section, width, height, state):
    """Choose a bounded split only if it improves height and conservatively fits.

    Both fast fitting and exact compilation use this same deterministic plan.
    Standalone classic and narrow/tall modules keep their existing composition.
    Multiple visuals keep their order in the left-hand stack.
    """
    visuals = section.get('visual_assets') or []
    if (state.get('generation_route') != 'optimization_family' or not height or
            width / height < 1.6 or not visuals or not section.get('text_content') or
            not hasattr(agent, '_measure_section_title')):
        return None
    padding = float(agent.config['layout']['text_padding']['left_right'])
    gap = max(.3, float(agent.config['layout']['element_spacing']))
    below = float(agent.config['layout']['visual_spacing']['below_visual'])
    title_height = 0.0
    if section.get('section_title'):
        title_height = agent._measure_section_title(section['section_title'], width, state)['height']
        title_height += float(agent.config['layout']['title_to_content_spacing'])
    factor = float((state.get('critic_config') or {}).get('explore_layout', {}).get(
        'fast_measurement_safety_factor', 1.20))
    body_limit = height / factor - title_height
    inner_width = width - 2 * padding
    sizes = (state.get('styling_interfaces') or {}).get('font_sizes') or {}
    font_size = float(sizes.get('body_text', agent.config['typography']['sizes']['body_text']))
    min_text_width = max(4.0, 10 * font_size / 72)
    visual_limit = (body_limit - below * (len(visuals)-1)) / len(visuals)
    if visual_limit <= 0:
        return None
    stacked = fast_body_height(agent, section, inner_width, state)
    for visual in visuals:
        _, vh, _ = agent._calculate_visual_height(visual['visual_id'], inner_width, state, height)
        stacked += vh + below
    # Reserve a meaningful height improvement, rather than widening an image
    # until the horizontal row is as tall as the old vertical stack.
    visual_limit = min(visual_limit, (stacked * .85 - below * (len(visuals)-1)) / len(visuals))
    if visual_limit <= 0:
        return None
    candidates = []
    for fraction in (.4, .5, .6):
        visual_column = (inner_width - gap) * fraction
        text_width = inner_width - gap - visual_column
        if text_width < min_text_width:
            continue
        rows, y, area = [], 0.0, 0.0
        for visual in visuals:
            vw, vh, scale = agent._calculate_visual_height(
                visual['visual_id'], visual_column, state, visual_limit, max_height_fraction=1.0)
            rows.append({'width': vw, 'height': vh, 'scale': scale,
                         'x': (visual_column-vw)/2, 'y': y})
            y += vh + below
            area += vw * vh
        # Give unused visual-column width back to prose after aspect-fit.
        used_visual_width = max(row['width'] for row in rows)
        for row in rows:
            row['x'] = (used_visual_width - row['width']) / 2
        text_width = inner_width - gap - used_visual_width
        visual_height = y - below
        text_height = fast_body_height(agent, section, text_width, state)
        body_height = max(visual_height, text_height)
        if body_height > body_limit or body_height >= stacked - .05:
            continue
        candidates.append({'title_height': title_height, 'body_height': body_height,
            'text_height': text_height, 'visual_height': visual_height,
            'text_column_width': text_width + 2*padding,
            'text_x': used_visual_width + gap, 'visuals': rows, 'visual_area': area})
    return max(candidates, key=lambda p: (p['visual_area'], -p['body_height'])) if candidates else None


def _fixed_side_by_side_plan(agent, section, width, height, state):
    """Keep a horizontal row even when all bounded sizes overflow.

    Exact body measurement can rescue a conservative false negative. If no split
    fits, return the least overflowing horizontal plan for ordinary capacity
    feedback and freeze-and-score diagnostics, never an implicit vertical fallback.
    """
    import math
    from src.layout.body_presentation import paragraphs
    from src.layout.editorial import presentation_lines
    visuals = section.get('visual_assets') or []
    if not visuals or not section.get('text_content'):
        raise ValueError('Frozen horizontal composition lost its image or prose')
    if not height or not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError('Frozen horizontal composition has non-renderable dimensions')
    padding = float(agent.config['layout']['text_padding']['left_right'])
    gap = max(.3, float(agent.config['layout']['element_spacing']))
    below = float(agent.config['layout']['visual_spacing']['below_visual'])
    usable_width = width - 2 * padding - gap
    if usable_width <= 0:
        raise ValueError('Frozen horizontal composition has no drawable column width')
    title_height = 0.0
    if section.get('section_title'):
        title_height = agent._measure_section_title(section['section_title'], width, state)['height']
        title_height += float(agent.config['layout']['title_to_content_spacing'])
    factor = float((state.get('critic_config') or {}).get('explore_layout', {}).get(
        'fast_measurement_safety_factor', 1.20))
    visual_limit = max(.1, (height / factor - title_height - below * (len(visuals)-1)) / len(visuals))
    candidates = []
    for fraction in (.4, .5, .6):
        rows, y, area = [], 0.0, 0.0
        for visual in visuals:
            vw, vh, scale = agent._calculate_visual_height(
                visual['visual_id'], usable_width * fraction, state, visual_limit, max_height_fraction=1.0)
            rows.append({'width': vw, 'height': vh, 'scale': scale, 'x': 0.0, 'y': y})
            y += vh + below
            area += vw * vh
        used_width = max(row['width'] for row in rows)
        for row in rows:
            row['x'] = (used_width-row['width'])/2
        text_width = usable_width-used_width
        metrics = agent._measure_body_text(presentation_lines(section), text_width+2*padding, state,
            editorial=True, presentation=paragraphs(section))
        body_height = max(y-below, metrics['height'])
        candidates.append({'title_height': title_height, 'body_height': body_height,
            'text_height': metrics['height'], 'visual_height': y-below,
            'text_column_width': text_width+2*padding, 'text_x': used_width+gap,
            'visuals': rows, 'visual_area': area})
    def rank(plan):
        overflow = max(0.0, title_height+plan['body_height']-height)
        return (overflow > .001, overflow, -plan['visual_area'], plan['body_height'])
    return min(candidates, key=rank)
