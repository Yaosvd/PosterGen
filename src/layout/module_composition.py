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
