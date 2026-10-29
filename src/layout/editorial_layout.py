"""Measured compilation with Curator-owned positions and finite boundary search.

No evidence bank, section reassignment, text subset selection or semantic sorting.
"""
from copy import deepcopy
import math

from src.layout.families import LayoutFamilyRegistry, valid_family_topology, LAYOUT_ENGINE_SCHEMA_VERSION
from src.layout.region_merges import geometry_record
from src.workflow.editorial_contract import make_board, validate_zones, module_limits
from utils.persistence import digest


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
    agent = LayoutAgent()
    board = make_board(candidate)
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
                children = agent._create_section_elements(section,x,current_y,w,view,allocated)
                bottom = max((e['y']+e['height'] for e in children),default=current_y)
                used = max(.1,bottom-current_y)
                elements.append({'type':'section_container','section_id':sid,'zone_id':zone['zone_id'],
                    'layout_family':spec['family_id'],'x':x,'y':current_y,'width':w,'height':used,
                    'planned_zone_height':h,'planned_module_height':allocated,
                    'importance_level':section['importance_level'],'priority':.1})
                elements.extend(children)
                parts = {'title':sum(e['height'] for e in children if e.get('type')=='section_title'),
                         'text':sum(e['height'] for e in children if e.get('type')=='text')}
            else:
                horizontal = side_by_side_plan(agent,section,w,allocated,view)
                if horizontal:
                    used = horizontal['title_height']+horizontal['body_height']+.3
                else:
                    used = fast_body_height(agent,section,w-2*agent.config['layout']['text_padding']['left_right'],view)
                    if section['section_title']:
                        used += agent._measure_section_title(section['section_title'],w,view)['height']
                        used += agent.config['layout']['title_to_content_spacing']
                    for v in section['visual_assets']:
                        used += agent._calculate_visual_height(v['visual_id'],w-.6,view,allocated)[1]
                        used += agent.config['layout']['visual_spacing']['below_visual']
                parts = {}
            words = sum(len(t.split()) for t in section['text_content'])
            metrics.append({'module_id':sid,'zone_id':zone['zone_id'],'allocated_height':allocated,
                'intrinsic_height':used,'utilization':used/allocated,'overage_inches':max(0,used-allocated),
                'missing_height_inches':max(0,.90*allocated-used),'current_words':words,
                'suggested_words':max(1,round(words*.95*allocated/max(.01,used))),
                'width_inches':w, 'measurements':parts})
            total_used += used
            current_y += allocated+gap
        region_use[zone['zone_id']] = (total_used+gap*max(0,len(ids)-1))/h
        bottom_gaps[zone['zone_id']] = max(0,h-total_used-gap*max(0,len(ids)-1))
    overflow = sum(m['overage_inches'] for m in metrics)
    underfill = sum(m['missing_height_inches'] for m in metrics)
    preflight = validate_compiled_layout(elements,spec,view,poster_margin=agent.poster_margin,
        title_height_fraction=agent.title_height_fraction) if exact else None
    feasible = overflow <= .01 and (not exact or preflight['passed'])
    report = {'version':'editorial_fit_v1','status':'fit' if feasible else 'overflow',
        'passed':feasible, 'modules':metrics,'zone_utilization':region_use,'exact_bottom_gaps':bottom_gaps,
        'total_overflow_inches':overflow, 'total_underfill_inches':underfill,
        'all_modules_90_percent':bool(metrics) and all(.9 <= m['utilization'] <= 1+.001 for m in metrics),
        'preflight':preflight, 'geometry_fingerprint':spec['geometry_fingerprint']}
    if exact:
        report['composition_whitespace'] = measure_composition_whitespace(spec,elements,
            poster_width=state['poster_width'],poster_height=state['poster_height'],
            poster_margin=agent.poster_margin,title_height_fraction=agent.title_height_fraction)
    return {'board':board,'spec':spec,'layout':elements,'report':report}


def boundary_candidates(state, candidate, zones, baseline, maximum=12):
    """Generate sizes only after measured pressure; never move module ownership."""
    family = LayoutFamilyRegistry().get(state['sample_family']['family'])
    pressure = {z['zone_id']:sum(m['intrinsic_height']-m['allocated_height']
                for m in baseline['report']['modules'] if m['zone_id']==z['zone_id']) for z in zones}
    ranked, seen = [], {digest(geometry_record(zones))}
    # Each shared cut may meet several regions (a spanning band over cards).
    for along, extent, cross, cross_extent in (('x','width','y','height'),('y','height','x','width')):
        starts = sorted({round(z[along],6) for z in zones if z[along]>0})
        for start in starts:
            after = [z for z in zones if abs(z[along]-start)<1e-6]
            ends = sorted({round(z[along]+z[extent],6) for z in zones
                           if -.000001 <= start-z[along]-z[extent] <= .08})
            for end in ends:
                before = [z for z in zones if abs(z[along]+z[extent]-end)<1e-6 and any(
                    min(z[cross]+z[cross_extent],b[cross]+b[cross_extent]) > max(z[cross],b[cross])+1e-6 for b in after)]
                if not before or not after: continue
                before_ids, after_ids = {z['zone_id'] for z in before},{z['zone_id'] for z in after}
                direction = 1 if sum(pressure[i] for i in before_ids)>sum(pressure[i] for i in after_ids) else -1
                for amount in (.025,.05,.08,-.025,-.05,-.08):
                    delta = direction*amount
                    trial = deepcopy(zones)
                    for z in trial:
                        if z['zone_id'] in before_ids:z[extent]=round(z[extent]+delta,6)
                        if z['zone_id'] in after_ids:
                            z[along]=round(z[along]+delta,6);z[extent]=round(z[extent]-delta,6)
                    if any(z[extent]<.08 for z in trial) or not valid_family_topology(family,trial):continue
                    key = digest(geometry_record(trial))
                    if key in seen:continue
                    seen.add(key)
                    ranked.append((abs(sum(pressure[i] for i in before_ids)-sum(pressure[i] for i in after_ids)),trial))
    ranked.sort(key=lambda r:-r[0])
    return [row[1] for row in ranked[:maximum]]


def fit(state, candidate, zones):
    """Base exact measurement, <=12 pressure-driven sizes, exact finalists."""
    baseline = measure(state,candidate,zones)
    if baseline['report']['passed'] and baseline['report']['all_modules_90_percent']:
        baseline['report']['geometry_trials'] = []
        return baseline
    options = boundary_candidates(state,candidate,zones,baseline)
    trials, ranked = [], []
    for geometry in options:
        trial = measure(state,candidate,geometry,exact=False)
        r = trial['report']
        trials.append({'geometry':geometry_record(geometry),'fast_report':r})
        ranked.append((r['total_overflow_inches'],r['total_underfill_inches'],geometry))
    def rank(result):
        r=result['report']
        return (not r['passed'],r['total_overflow_inches'],r['total_underfill_inches'])
    best = baseline
    # Exact work is bounded as well; fast estimates do not certify delivery.
    for _,_,geometry in sorted(ranked,key=lambda r:r[:2])[:4]:
        trial = measure(state,candidate,geometry)
        from src.layout.whitespace import no_added_whitespace
        nonregression = (not baseline['report']['passed'] or no_added_whitespace(
            baseline['report']['composition_whitespace'],trial['report']['composition_whitespace']))
        trials.append({'geometry':geometry_record(geometry),'exact_report':deepcopy(trial['report']),
                       'whitespace_nonregression':nonregression})
        if nonregression and rank(trial)<rank(best):best=trial
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
            'up to capacity. Share space between all titles, text and images. Wide shallow modules can use image-left/'
            'text-right after measurement; footprint estimates are guidance, never a fit certificate.'}
