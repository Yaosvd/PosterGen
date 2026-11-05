"""Measured compilation with Curator-owned positions and finite boundary search.

No evidence bank, section reassignment, text subset selection or semantic sorting.
"""
from copy import deepcopy
import math

from src.layout.families import LAYOUT_ENGINE_SCHEMA_VERSION
from src.layout.region_merges import geometry_record
from src.layout.measurement_context import measurement_origin
from src.layout.text_height_measurement import TextMeasurementError
from src.layout.element_identity import identified_layout
from src.workflow.editorial_contract import make_board, validate_zones, module_limits
from utils.persistence import digest


def text_budget(children, *, module_y, allocated_height, module_width, geometry_fingerprint):
    """Describe the actual text lane without changing a rendered box.

    The text origin already incorporates title, padding and stacked visuals.
    A parallel image does not consume height a second time. Values refer only
    to this geometry; word estimates never certify a rewritten paragraph fits.
    """
    result = {'version': 'editorial_text_budget_v2', 'status': 'unavailable',
              'geometry_fingerprint': geometry_fingerprint}
    texts = [e for e in children if e.get('type') == 'text']
    if len(texts) != 1:
        return {**result, 'reason': 'Expected one complete measured body text box'}
    text = texts[0]
    try:
        values = [float(v) for v in (module_y, allocated_height, module_width,
                  text['y'], text['width'], text['height'], text['font_size'])]
        if not all(math.isfinite(v) for v in values) or min(values[1:3] + values[4:]) <= 0:
            raise ValueError('Invalid text geometry')
        top, allocation, width, text_top, text_width, text_height, font_size = values
        offset = text_top - top
        if offset < -1e-6:
            raise ValueError('Text starts above its allocated module')
        visuals = [e for e in children if e.get('type') == 'visual']
        visual_height = sum(float(e['height']) for e in visuals)
        title_height = sum(float(e['height']) for e in children if e.get('type') == 'section_title')
        parallel = text.get('body_layout') == 'image_left_text_right'
        visual_span = (max(float(e['y']) + float(e['height']) for e in visuals) - text_top
                       if parallel and visuals else 0.0)
        if not all(math.isfinite(v) and v >= 0 for v in (visual_height, title_height, visual_span)):
            raise ValueError('Invalid non-text geometry')
        available = allocation - offset
        return {**result, 'status': 'measured' if available > 0 else 'no_text_space',
                'module_width_inches': width, 'module_height_inches': allocation, 'module_y_inches': top,
                'text_width_inches': text_width, 'available_text_height_inches': available,
                'current_text_height_inches': text_height, 'font_size': font_size,
                'font_family': text.get('font_family'),
                'body_layout': text.get('body_layout') or 'text_only',
                'before_text_height_inches': offset, 'title_height_inches': title_height,
                'visual_height_inches': visual_height,
                'spacing_height_inches': max(0.0, offset - title_height - (0 if parallel else visual_height)),
                'parallel_visual_height_inches': visual_span,
                'layout_pressure': available <= 0 or visual_span > available + .01}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {**result, 'reason': str(exc)}


def suggested_words(words, budget):
    if budget.get('status') != 'measured':
        return None
    estimate = round(words * .95 * budget['available_text_height_inches'] /
                     budget['current_text_height_inches'])
    return estimate if estimate >= 1 else None


def layout_spec(state, candidate, zones):
    family = validate_zones(state, zones)
    spec = {'schema_version':LAYOUT_ENGINE_SCHEMA_VERSION, 'family_id':family.family_id,
            'zones':deepcopy(zones), 'reading_order':[m['module_id'] for m in candidate['modules']],
            'primary_anchor_zone':next((z['zone_id'] for z in zones if z.get('role') == 'hero'),zones[0]['zone_id'])}
    for zone in spec['zones']:
        zone['section_ids'] = [m['module_id'] for m in candidate['modules'] if m['zone_id'] == zone['zone_id']]
    spec['geometry_fingerprint'] = digest(geometry_record(zones))
    spec['variant_id'] = family.family_id+'_'+spec['geometry_fingerprint'][:16]
    return spec


def measure(state, candidate, zones, *, exact=True):
    from src.agents.layout_agent import LayoutAgent
    from src.layout.module_composition import fast_body_height, side_by_side_plan
    from src.layout.feasibility import validate_compiled_layout
    from src.layout.whitespace import measure_composition_whitespace
    from src.layout.editorial_composition import assert_composition, HORIZONTAL, VERTICAL
    if state.get('editorial_composition') is not None:
        assert_composition(state, candidate)
    agent = LayoutAgent()
    board = make_board(candidate, state.get('editorial_emphasis'))
    spec = layout_spec(state, candidate, zones)
    view = {**state, 'story_board':board,'optimized_story_board':board,'layout_spec':spec}
    width = float(state['poster_width'])-2*agent.poster_margin
    height = (float(state['poster_height'])-2*agent.poster_margin)*(1-agent.title_height_fraction)
    top = agent.poster_margin+(float(state['poster_height'])-2*agent.poster_margin)*agent.title_height_fraction
    gap = agent._inter_section_spacing(view)
    sections = {s['section_id']:s for s in board['spatial_content_plan']['sections']}
    modules = {m['module_id']:m for m in candidate['modules']}
    elements, metrics, region_use, bottom_gaps = [], [], {}, {}
    title = agent._create_title_element(view,float(state['poster_width']),top-agent.poster_margin)
    if title: elements.append(title)
    elements.extend(agent._create_logo_elements(view,float(state['poster_width']),top-agent.poster_margin))
    for zone in spec['zones']:
        ids = zone['section_ids']
        w,h = width*zone['width'],height*zone['height']
        x,y = agent.poster_margin+width*zone['x'],top+height*zone['y']
        available = h-gap*max(0,len(ids)-1)
        if available <= 0:
            raise ValueError('Region has no body space after module spacing')
        weights = sum(modules[sid]['space_weight'] for sid in ids)
        current_y, total_used = y, 0.0
        for sid in ids:
            section = deepcopy(sections[sid]);section['layout_zone_id'] = zone['zone_id']
            allocated = available*modules[sid]['space_weight']/weights
            if exact:
                with measurement_origin(candidate_id=candidate['candidate_id'], module_id=sid,
                        zone_id=zone['zone_id'], geometry_fingerprint=spec['geometry_fingerprint']):
                    children = agent._create_section_elements(section,x,current_y,w,view,allocated)
                bottom = max((e['y']+e['height'] for e in children),default=current_y)
                used = max(.1,bottom-current_y)
                elements.append({'type':'section_container','section_id':sid,'zone_id':zone['zone_id'],
                    'layout_family':spec['family_id'],'x':x,'y':current_y,'width':w,'height':used,
                    'planned_zone_height':h,'planned_module_height':allocated,
                    'module_frame':{'version':'editorial_module_frames_v1',
                                    'x':x,'y':current_y,'width':w,'height':allocated},
                    'importance_level':section['importance_level'],
                    'emphasis_background':section['editorial'].get('background'),
                    'emphasis_disabled':section['editorial']['emphasis_disabled'],'priority':.1})
                elements.extend(children)
                parts = {'title':sum(e['height'] for e in children if e.get('type')=='section_title'),
                         'text':sum(e['height'] for e in children if e.get('type')=='text')}
                body_layout = next((e.get('body_layout') for e in children if e.get('type') == 'text'), None)
                minimum_used = next((e['composition_minimum_height'] for e in children
                                     if 'composition_minimum_height' in e), used)
                if body_layout == VERTICAL:
                    # A height-capped vertical image grows when its region grows.
                    # Solve that feedback with cheap aspect calculations, reusing
                    # the already exact title/text heights; never remeasure prose.
                    visuals = [e for e in children if e.get('type') == 'visual']
                    fixed = used-sum(e['height'] for e in visuals)
                    required = max(allocated, used)
                    for _ in range(16):
                        demand = fixed+sum(agent._calculate_visual_height(
                            e['visual_id'],w-.6,view,required)[1] for e in visuals)
                        if abs(demand-required) <= .00001:
                            break
                        required = demand
                    minimum_used = max(used, demand)
            else:
                with measurement_origin(candidate_id=candidate['candidate_id'], module_id=sid,
                        zone_id=zone['zone_id'], geometry_fingerprint=spec['geometry_fingerprint']):
                    horizontal = side_by_side_plan(agent,section,w,allocated,view)
                    if horizontal:
                        used = horizontal['title_height']+horizontal['body_height']
                    else:
                        used = fast_body_height(agent,section,w-2*agent.config['layout']['text_padding']['left_right'],view)
                        if section['section_title']:
                            used += agent._measure_section_title(section['section_title'],w,view)['height']
                            used += agent.config['layout']['title_to_content_spacing']
                        for v in section['visual_assets']:
                            used += agent._calculate_visual_height(v['visual_id'],w-.6,view,allocated)[1]
                            used += agent.config['layout']['visual_spacing']['below_visual']
                    parts = {}
                    body_layout = (HORIZONTAL if horizontal else VERTICAL) if section['visual_assets'] else None
                    minimum_used = horizontal.get('minimum_height', used) if horizontal else used
            words = sum(len(t.split()) for t in section['text_content'])
            budget = (text_budget(children, module_y=current_y, allocated_height=allocated,
                        module_width=w, geometry_fingerprint=spec['geometry_fingerprint']) if exact else
                      {'version': 'editorial_text_budget_v2', 'status': 'unavailable',
                       'reason': 'Fast geometry search estimate; exact text budget not measured'})
            word_reference = suggested_words(words, budget)
            metrics.append({'module_id':sid,'zone_id':zone['zone_id'],'allocated_height':allocated,
                'intrinsic_height':used,'minimum_intrinsic_height':minimum_used,
                'utilization':used/allocated,'overage_inches':max(0,used-allocated),
                'missing_height_inches':max(0,.90*allocated-used),'current_words':words,
                'suggested_words':word_reference,
                'word_suggestion_status':'reference_only' if word_reference is not None else 'unavailable',
                'text_budget':budget,
                'width_inches':w, 'measurements':parts, 'body_layout':body_layout,
                'composition_locked':body_layout is not None and state.get('editorial_composition') is not None})
            total_used += used
            current_y += allocated+gap
        region_use[zone['zone_id']] = (total_used+gap*max(0,len(ids)-1))/h
        bottom_gaps[zone['zone_id']] = max(0,h-total_used-gap*max(0,len(ids)-1))
    elements = identified_layout(elements)
    overflow = sum(m['overage_inches'] for m in metrics)
    underfill = sum(m['missing_height_inches'] for m in metrics)
    preflight = validate_compiled_layout(elements,spec,view,poster_margin=agent.poster_margin,
        title_height_fraction=agent.title_height_fraction) if exact else None
    feasible = overflow <= .01 and (not exact or preflight['passed'])
    report = {'version':'editorial_fit_v2','module_frame_version':'editorial_module_frames_v1',
        'candidate_id':candidate['candidate_id'],
        'status':'fit' if feasible else 'overflow',
        'passed':feasible, 'modules':metrics,'zone_utilization':region_use,'exact_bottom_gaps':bottom_gaps,
        'total_overflow_inches':overflow, 'total_underfill_inches':underfill,
        'all_modules_90_percent':bool(metrics) and all(.9 <= m['utilization'] <= 1+.001 for m in metrics),
        'preflight':preflight, 'geometry_fingerprint':spec['geometry_fingerprint']}
    if exact:
        from src.layout.editorial_frames import assert_frames
        assert_frames(view, candidate, spec, elements)
        if state.get('editorial_composition') is not None:
            assert_composition(state, candidate, elements)
        report['composition_whitespace'] = measure_composition_whitespace(spec,elements,
            poster_width=state['poster_width'],poster_height=state['poster_height'],
            poster_margin=agent.poster_margin,title_height_fraction=agent.title_height_fraction)
    return {'board':board,'spec':spec,'layout':elements,'report':report}


def boundary_candidates(state, candidate, zones, baseline, maximum=12):
    """Generate sizes only after measured pressure; never move module ownership."""
    from src.layout.editorial_space import redistribute_candidates
    return redistribute_candidates(state, candidate, zones, baseline, maximum=maximum)


def fit(state, candidate, zones):
    """Base exact measurement, <=12 pressure-driven sizes, exact finalists."""
    physical_errors = {'TEXT_WIDTH_INFEASIBLE', 'TEXT_INVALID_GEOMETRY', 'TEXT_HEIGHT_LIMIT'}
    trials = []
    baseline_error = None
    try:
        baseline = measure(state,candidate,zones)
    except TextMeasurementError as exc:
        if exc.code not in physical_errors:
            raise
        baseline_error = exc
        trials.append({'geometry':geometry_record(zones), 'measurement_status':'unavailable',
                       'measurement_failure':{'code':exc.code, **exc.details}})
        # Fast figures only guide the existing bounded search; never publish
        # this estimate as a verified fit or choose it as the final candidate.
        baseline = measure(state,candidate,zones,exact=False)
    if baseline_error is None and baseline['report']['passed'] and baseline['report']['all_modules_90_percent']:
        baseline['report']['geometry_trials'] = []
        return baseline
    options = boundary_candidates(state,candidate,zones,baseline)
    ranked = []
    for geometry in options:
        try:
            trial = measure(state,candidate,geometry,exact=False)
        except TextMeasurementError as exc:
            if exc.code not in physical_errors:
                raise
            trials.append({'geometry':geometry_record(geometry),'measurement_status':'unavailable',
                           'measurement_failure':{'code':exc.code, **exc.details}})
            continue
        r = trial['report']
        trials.append({'geometry':geometry_record(geometry),'fast_report':r})
        ranked.append((r['total_overflow_inches'],r['total_underfill_inches'],geometry))
    def rank(result):
        r=result['report']
        return (not r['passed'],r['total_overflow_inches'],r['total_underfill_inches'])
    best = baseline if baseline_error is None else None
    # Exact work is bounded as well; fast estimates do not certify delivery.
    for _,_,geometry in sorted(ranked,key=lambda r:r[:2])[:4]:
        try:
            trial = measure(state,candidate,geometry)
        except TextMeasurementError as exc:
            if exc.code not in physical_errors:
                raise
            trials.append({'geometry':geometry_record(geometry),'measurement_status':'unavailable',
                           'measurement_failure':{'code':exc.code, **exc.details}})
            continue
        from src.layout.whitespace import no_added_whitespace
        nonregression = (baseline_error is not None or not baseline['report']['passed'] or no_added_whitespace(
            baseline['report']['composition_whitespace'],trial['report']['composition_whitespace']))
        trials.append({'geometry':geometry_record(geometry),'exact_report':deepcopy(trial['report']),
                       'whitespace_nonregression':nonregression})
        if nonregression and (best is None or rank(trial)<rank(best)):best=trial
    if best is None:
        baseline_error.details['attempted_geometry_count'] = len(trials)
        raise baseline_error
    best['report']['geometry_trials']=trials
    best['report']['size_candidate_limit']=12
    return best


def family_brief(state, zones):
    from src.agents.layout_agent import LayoutAgent
    from src.workflow.editorial_contract import asset_index
    agent=LayoutAgent()
    width=state['poster_width']-2*agent.poster_margin
    height=(state['poster_height']-2*agent.poster_margin)*(1-agent.title_height_fraction)
    minimum,maximum=module_limits(zones)
    return {'family_id':state['sample_family']['family'],'minimum_modules':minimum,'maximum_modules':maximum,
        'fonts':agent.config['typography'],'zones':[{**deepcopy(z),'width_inches':z['width']*width,
        'height_inches':z['height']*height,'horizontal_image_text_possible':z['width']*width/(z['height']*height/z['capacity'])>=1.6,
        'visual_heights_inches':{vid:agent._calculate_visual_height(vid,max(.1,z['width']*width-.6),state,z['height']*height)[1]
                                for vid in asset_index(state)}} for z in zones],
        'instructions':'Use this ONE geometry. Every active region needs a module. Regions can hold multiple modules '
            'up to capacity. Share space between all titles, text and images. '
            + ('Each image-owning module keeps its frozen image/text direction; adjust prose and dimensions within it. '
               if state.get('editorial_composition') is not None else
               'Wide shallow modules can use image-left/text-right after measurement. ')
            + 'Footprint estimates are guidance, never a fit certificate.'}
