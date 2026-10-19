"""Bounded joint panel/ink selection, without model calls or state mutation."""

import re


EMPHASIS_POLICY_VERSION = 'panel_ink_v1'


def _rgb(color):
    if not isinstance(color, str) or not re.fullmatch(r'#[\da-fA-F]{6}', color):
        return None
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _mix(color, target, fraction):
    return '#' + ''.join(f'{round(a + (b - a) * fraction):02x}' for a, b in zip(_rgb(color), _rgb(target)))


def resolve_emphasis(colors, config=None):
    from src.critic.quality import _contrast
    config = config or {}
    threshold = float(((config.get('evaluators') or {}).get('color_quality') or {}).get('minimum_contrast_ratio', 4.5))
    settings = config.get('poster_editorial') or {}
    visibility = float(settings.get('minimum_panel_canvas_contrast', 1.12))
    report = {'version': EMPHASIS_POLICY_VERSION, 'status': 'unavailable',
              'minimum_panel_canvas_contrast': visibility, 'minimum_text_contrast': threshold}
    if any(_rgb(colors.get(k)) is None for k in ('mono_light', 'text', 'contrast')):
        return None, report
    candidates = [colors['mono_light']]
    if _rgb(colors.get('theme')):
        candidates.extend(_mix(colors['theme'], '#ffffff', f) for f in (.86, .89, .92))
    candidates.extend(_mix(colors['mono_light'], '#ffffff', f) for f in (.25, .5))
    for background in dict.fromkeys(candidates):
        panel_ratio = _contrast(background, '#ffffff')
        # This is a configurable design heuristic, not a WCAG requirement.
        if not visibility <= panel_ratio <= 1.65:
            continue
        resolved = {}
        for role in ('text', 'contrast'):
            for i in range(21):
                ink = _mix(colors[role], '#000000', i / 20)
                if all((_contrast(ink, bg) or 0) >= threshold for bg in (background, '#ffffff')):
                    resolved[role] = ink
                    break
        if len(resolved) == 2:
            report.update(status='resolved', background=background,
                          panel_canvas_contrast=round(panel_ratio, 4),
                          text_color=resolved['text'], accent_color=resolved['contrast'])
            return {'background': background, 'text_color': resolved['text'],
                    'accent_color': resolved['contrast']}, report
    report['reason'] = 'no_visible_accessible_pair'
    return None, report
