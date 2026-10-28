"""Physical writing estimates for source prose; never a layout or science proof."""
from math import floor


def writing_space(state, brief):
    """Show every generated legal variant, including the cost of original visuals."""
    from src.agents.layout_agent import LayoutAgent
    agent = LayoutAgent()
    width = float(state['poster_width']) - 2 * agent.poster_margin
    height = (float(state['poster_height']) - 2 * agent.poster_margin) * (1-agent.title_height_fraction)
    sizes = (state.get('styling_interfaces') or {}).get('font_sizes') or agent.config['typography']['sizes']
    body = float(sizes['body_text'])
    title = float(sizes['section_title'])
    factor = float((state.get('critic_config') or {}).get('explore_layout', {}).get('fast_measurement_safety_factor',1.20))
    padding = float(agent.config['layout']['text_padding']['left_right'])
    # An explicitly approximate six-character English word, including its space.
    # Actual authored strings always go through the ordinary fast/exact fitter.
    def words(w, h):
        lines = max(0, floor((h-.5)/(body/72*1.25)))
        return max(0, floor(lines * max(.1, w-2*padding-.2)/(body/72*.5*6)))
    variants = []
    visual_cache = {}
    for variant in brief['variants']:
        zones = []
        for zone in variant['zones']:
            w, h = zone['width']*width, zone['height']*height
            title_allowance = 2*title/72*1.25 + float(agent.config['layout']['title_to_content_spacing'])
            rows = []
            for vid in state['source_document']['assets']:
                key = (vid,w,h)
                if key not in visual_cache:
                    _, vh, _ = agent._calculate_visual_height(vid, max(.1,w-2*padding), state, h)
                    visual_cache[key] = vh + float(agent.config['layout']['visual_spacing']['below_visual'])
                vh = visual_cache[key]
                rows.append({'visual_id':vid, 'height_inches':round(vh,3),
                    'remaining_body_words_estimate':words(w,h/factor-title_allowance-vh)})
            zones.append({'zone_id':zone['zone_id'], 'width_inches':round(w,3), 'height_inches':round(h,3),
                'module_capacity':zone.get('capacity',1), 'two_line_title_allowance_inches':round(title_allowance,3),
                'text_only_words_estimate':words(w,h/factor-title_allowance), 'visual_options':rows})
        variants.append({'variant_id':variant['variant_id'],'zones':zones})
    return {'version':'source_space_v2','certifies_feasible_layout':False,
        'body_font_points':body,'section_title_font_points':title,
        'measurement_safety_factor':factor,
        'assumptions':'Approximate English word lengths and two-line titles at the actual fonts. '
            'Choose ONE variant and divide zone space among its modules. Visual options are alternatives; '
            'each additional visual and each extra module title consumes space. Estimates are not hard word quotas.',
        'variants':variants}


def writing_task(state, brief):
    """Repeat compact writing constraints after the complete original sections."""
    plan=brief['writing_space']
    options=[]
    for variant in plan['variants']:
        zones=[]
        for zone in variant['zones']:
            remaining=[r['remaining_body_words_estimate'] for r in zone['visual_options']]
            zones.append({k:zone[k] for k in ('zone_id','width_inches','height_inches',
                'module_capacity','text_only_words_estimate')})
            zones[-1]['with_one_visual_body_words_range']=[min(remaining),max(remaining)] if remaining else None
        options.append({'variant_id':variant['variant_id'],'zones':zones})
    return {'family_id':brief['family_id'],'research_story':state['source_narrative_plan']['research_story'],
        'necessary_meanings':[{'obligation_id':o['obligation_id'],'meaning':o['meaning']}
                              for o in state['source_narrative_plan']['obligations']],
        'body_font_points':plan['body_font_points'],'section_title_font_points':plan['section_title_font_points'],
        'physical_options':options,'certifies_feasible_layout':False,'pins_geometry':False,
        'instruction':'Compose the visible poster now, with concise connected explanations of every necessary meaning, '
            'not merely its name or obligation ID. Original paragraphs are source material, not ready-sized poster prose. '
            'Plan against ONE complete variant. Do not add capacities across alternative variants. Zones are not modules; '
            'share their body budget among all placed modules, titles and visuals. The one-visual range summarizes '
            'alternatives: use the actual selected visual footprint in family.writing_space, and charge every extra visual. '
            'Check your intended module word counts against those remaining body estimates before returning. '
            'These are writing estimates, not hard quotas, a fixed module count or a geometry choice. '
            'Preserve original numerical notation and all necessary conditions while writing compactly.'}


def editorial_space(state, brief, result=None):
    """Bounded unordered allocations give actionable measurements even before a fit."""
    from src.agents.layout_agent import LayoutAgent
    from src.layout.feasibility import _estimate_section_height, _active_zone_roles, _semantic_role
    from src.layout.families import LayoutFamilyRegistry
    from src.workflow.source_editorial import make_board
    agent = LayoutAgent()
    view = {**state, 'draft_layout_mode':not bool(state.get('verification_passed'))}
    sections = make_board(view)['spatial_content_plan']['sections']
    family = LayoutFamilyRegistry().get(brief['family_id'])
    roles = _active_zone_roles(brief['family_id'], sections, view)
    width = float(state['poster_width'])-2*agent.poster_margin
    height = (float(state['poster_height'])-2*agent.poster_margin)*(1-agent.title_height_fraction)
    gap = agent._inter_section_spacing(view)
    factor = float((state.get('critic_config') or {}).get('explore_layout', {}).get('fast_measurement_safety_factor',1.20))
    variants = ([{'variant_id':'adopted_geometry','zones':result[1]['zones']}] if result and result[1]['zones']
                else brief['variants'])
    best = None
    height_cache = {}
    for variant in variants:
        zones = variant['zones']
        choices = []
        for section in sections:
            options = []
            for zi,z in enumerate(zones):
                if z['zone_id'] in roles and _semantic_role(section,view) not in roles[z['zone_id']]:
                    continue
                if result and z.get('section_ids') and section['section_id'] not in z['section_ids']:
                    continue
                key = (section['section_id'],z['width'],z['height'])
                if key not in height_cache:
                    parts = {}
                    used = _estimate_section_height(agent,section,zone_width=z['width']*width,
                        zone_height=z['height']*height,state=view,components=parts)
                    height_cache[key] = used,parts
                used,parts = height_cache[key]
                options.append((zi,used,parts))
            choices.append(options)
        # This beam supplies estimates only. It neither pins order nor replaces
        # the existing source/focus/exact compiler/Preflight layout search.
        beam = [(0.0,[],[0.0]*len(zones),[0]*len(zones))]
        for options in choices:
            expanded = []
            for _,rows,loads,counts in beam:
                for zi,used,parts in options:
                    if counts[zi] >= int(zones[zi].get('capacity',1)):
                        continue
                    new_loads,new_counts = loads[:],counts[:]
                    new_loads[zi] += used+(gap if counts[zi] else 0)
                    new_counts[zi] += 1
                    score = sum(max(0,load-z['height']*height)**2 for load,z in zip(new_loads,zones))
                    expanded.append((score,rows+[(zi,used,parts)],new_loads,new_counts))
            beam = sorted(expanded,key=lambda row:(row[0],tuple(r[0] for r in row[1])))[:64]
        for score,rows,loads,counts in beam:
            missing = sum(not counts[i] for i,z in enumerate(zones) if z['zone_id'] in family.contract.required_zones)
            rank = (missing,score,sum(loads))
            if best is None or rank < best[0]:
                best = rank,variant,rows,loads,counts
    if best is None:
        return {'status':'no_provisional_assignment','certifies_feasible_layout':False,'modules':[]}
    _,variant,rows,loads,counts = best
    measurements = []
    for section,(zi,used,parts) in zip(sections,rows):
        z = variant['zones'][zi]
        limit = z['height']*height
        # Share free BODY space proportionally after all titles/visuals/gaps.
        zone_parts = [p for i,_,p in rows if i==zi]
        fixed = sum(p['title_height_in']+p['visual_height_in'] for p in zone_parts)+gap*max(0,counts[zi]-1)
        total_text = sum(p['text_height_in'] for p in zone_parts)
        share = parts['text_height_in']/max(.01,total_text)
        body_budget = max(0,limit-fixed)*share
        wc = sum(len(t.split()) for t in section['text_content'])
        target = floor(wc*min(1,body_budget/max(.01,parts['text_height_in']))*.9)
        measurements.append({'module_id':section['section_id'],'zone_id':z['zone_id'],
            'current_words':wc,'width_inches':round(z['width']*width,3),
            'zone_limit_inches':round(limit,3),'zone_used_inches':round(loads[zi],3),
            'module_used_inches':round(used,3),**parts,'available_body_inches':round(body_budget,3),
            'suggested_body_words':max(0,target),
            'overage_inches':round(max(0,loads[zi]-limit)*share,3)})
    pressure = sorted(measurements,key=lambda row:(-row['overage_inches'],-row['current_words'],row['module_id']))
    targets = [r['module_id'] for r in pressure[:2] if r['overage_inches']>0]
    return {'status':'actual_ownership' if result else 'provisional_assignment',
        'measurement_safety_factor':factor,
        'certifies_feasible_layout':False,'assignment_is_binding':False,
        'variant_id':variant['variant_id'],'modules':measurements,'suggested_target_module_ids':targets,
        'instruction':'For overflow, edit the suggested pressured modules now. Compress repetition and optional detail '
            'toward the per-module body budget; preserve necessary meaning and conditions. You may reserve optional '
            'visuals or restructure up to two old/new modules. No image is required for measured capacity editing. '
            'Word estimates guide editing; only the full ordinary fit certifies geometry.'}
