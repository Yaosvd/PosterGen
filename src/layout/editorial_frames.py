"""Allocated paint frames, independent of honest intrinsic content geometry."""
import math

VERSION = 'editorial_module_frames_v1'
KEYS = ('x', 'y', 'width', 'height')


def frame_box(element):
    frame = element.get('module_frame')
    if not isinstance(frame, dict) or frame.get('version') != VERSION:
        raise ValueError('Editorial module frame is missing or invalid')
    try:
        values = [float(frame[k]) for k in KEYS]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Editorial module frame is invalid') from exc
    if not all(math.isfinite(v) for v in values) or min(values[2:]) <= 0:
        raise ValueError('Editorial module frame has non-renderable geometry')
    return dict(zip(KEYS, values))


def assert_frames(state, candidate, spec, layout):
    """Check allocated frames against final regions, weights and shared gutters.

    Intrinsic content may still overflow under freeze-and-score. It never changes
    a frame, conceals a measured defect, or enlarges a painted background.
    """
    from src.agents.layout_agent import LayoutAgent
    agent = LayoutAgent()
    width = float(state['poster_width'])-2*agent.poster_margin
    usable = float(state['poster_height'])-2*agent.poster_margin
    height = usable*(1-agent.title_height_fraction)
    top = agent.poster_margin+usable*agent.title_height_fraction
    gap = agent._inter_section_spacing(state)
    modules = {m['module_id']: m for m in candidate['modules']}
    containers = [e for e in layout if e.get('type') == 'section_container']
    if len(containers) != len(modules) or {e.get('section_id') for e in containers} != set(modules):
        raise ValueError('Editorial module frame ownership changed')
    by_id = {e['section_id']: e for e in containers}
    for zone in spec['zones']:
        ids = [m['module_id'] for m in candidate['modules'] if m['zone_id'] == zone['zone_id']]
        available = height*zone['height']-gap*max(0, len(ids)-1)
        weights = sum(modules[sid]['space_weight'] for sid in ids)
        y = top+height*zone['y']
        for sid in ids:
            allocated = available*modules[sid]['space_weight']/weights
            expected = dict(x=agent.poster_margin+width*zone['x'], y=y,
                            width=width*zone['width'], height=allocated)
            frame = frame_box(by_id[sid])
            if (by_id[sid].get('zone_id') != zone['zone_id'] or
                    any(abs(frame[k]-expected[k]) > 1e-6 for k in KEYS) or
                    any(abs(float(by_id[sid][k])-frame[k]) > 1e-6 for k in ('x','y','width')) or
                    abs(float(by_id[sid]['planned_module_height'])-allocated) > 1e-6):
                raise ValueError('Editorial module frame differs from allocated geometry')
            y += allocated+gap
    frames = [frame_box(e) for e in containers]
    for i, a in enumerate(frames):
        for b in frames[i+1:]:
            if (min(a['x']+a['width'], b['x']+b['width']) > max(a['x'], b['x'])+1e-6 and
                    min(a['y']+a['height'], b['y']+b['height']) > max(a['y'], b['y'])+1e-6):
                raise ValueError('Editorial module frames overlap')
    return True
