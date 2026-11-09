"""Finite upstream-style writing, model-owned placement and measured editing."""
from copy import deepcopy
from pathlib import Path
import re

from src.workflow.editorial_contract import (VERSION, PREPARATION, OUTPUT_POLICY, SAMPLE_KEYS, EditorialOutputError,
    EditorialStructureError, asset_index, paper_identity, paper_material, normalize_candidate,
    make_board, module_limits, assert_editorial_ready, snapshot_payload, geometry_digest, permits_layout_defects,
    visual_selection, assert_visual_selection)
from src.workflow.editorial_requests import obj, STRING, STRINGS, request, read, save, stopped
from src.layout.families import LayoutFamilyRegistry
from src.layout.editorial_layout import family_brief, fit, measure
from src.workflow.editorial_writing import (capacity_guidance, observed_edit, record_measured_edit,
    capacity_tasks, capacity_measurements, prose_changes, record_capacity_result)
from src.workflow.editorial_coverage import authoring_coverage
from utils.persistence import digest

ENTRY = obj({'item_id':STRING,'text':STRING,'display_label':STRING,'parent_item_id':STRING})
MODULE = obj({'module_id':STRING,'title':STRING,'zone_id':STRING,
    'importance':{'type':'integer','minimum':1,'maximum':3},
    'space_weight':{'type':'number','minimum':1,'maximum':3},
    'presentation_style':{'type':'string','enum':['plain','topics','steps']},
    'reader_question':STRING,'entries':{'type':'array','items':ENTRY,'minItems':1},
    'visual_ids':STRINGS,'visual_rationale':STRING})
CANDIDATE = obj({'modules':{'type':'array','items':MODULE,'minItems':1},
    'core_module_ids':{'type':'array','items':STRING,'maxItems':2},
    'narrative_flow':STRING,'reason':STRING})
PATCH = obj({'modules':{'type':'array','items':MODULE},'remove_module_ids':STRINGS,
             'module_order':STRINGS,'narrative_flow':STRING,'reason':STRING})
LIMITS = {'curator':1,'merge':1,'writer':1,'capacity':1}


def charge(state, phase, key, request_root=None):
    if phase not in LIMITS:
        raise ValueError('Unsupported editorial budget phase: '+phase)
    path = Path(state['sample_edit_budget_dir'])/'editorial_budget.json'
    context = state['iteration_context']
    identity = digest({'version':PREPARATION,'run':context.get('run_id'),'sample':context.get('sample_id'),
        'paper':state['paper_foundation_digest'],'family':state['sample_family']})
    if path.exists():
        ledger = read(path,identity)
    else:
        root = Path(state['sample_preparation_dir'])/'editorial'
        if root.exists() and any(root.rglob('request_00.json')):
            raise ValueError('Editorial budget missing from charged request history')
        ledger = {'input_digest':identity,'charges':[]}
    counts = {p:0 for p in LIMITS}
    seen = set()
    for i,entry in enumerate(ledger['charges']):
        if entry.get('phase') not in LIMITS or entry.get('ordinal') != i+1:
            raise ValueError('Corrupt editorial budget history')
        pair = (entry['phase'], entry.get('key'))
        if not isinstance(pair[1], str) or pair in seen:
            raise ValueError('Corrupt editorial budget duplicate/invalid charge')
        seen.add(pair)
        counts[entry['phase']] += 1
    if any(counts[p]>LIMITS[p] for p in LIMITS):
        raise ValueError('Editorial budget exceeds frozen limits')
    if any(e['phase']==phase and e['key']==key for e in ledger['charges']):
        if request_root and not (Path(request_root)/'request_00.json').exists():
            raise ValueError('Editorial edit charged but request missing')
    else:
        if counts[phase]>=LIMITS[phase]:
            raise EditorialOutputError('Editorial '+phase+' allowance exhausted')
        entry={'phase':phase,'key':key,'ordinal':len(ledger['charges'])+1}
        if request_root:
            entry['request_directory']=str(Path(request_root).relative_to(Path(state['sample_preparation_dir'])))
        ledger['charges'].append(entry)
        save(path,ledger)
    state['editorial_budget']=ledger


def install(state, candidate):
    state['editorial_candidate']=candidate
    board=make_board(candidate,state.get('editorial_emphasis'))
    state['story_board']=deepcopy(board);state['optimized_story_board']=board
    state.pop('editorial_snapshot',None)
    if state.get('color_scheme'):
        from src.agents.section_title_designer import SectionTitleDesigner
        state['section_title_design'] = SectionTitleDesigner()._generate_colorblock_design(board,state['color_scheme'])
    return state


def curator_schema(zones, visual_ids):
    """Bind authoring to the actual geometry and assets, without shared mutation."""
    schema = deepcopy(CANDIDATE)
    modules = schema['properties']['modules']
    _, modules['maxItems'] = module_limits(zones)
    # Replace the shared STRING node instead of modifying it in place.
    modules['items']['properties']['zone_id'] = {
        'type': 'string', 'enum': [zone['zone_id'] for zone in zones]}
    visuals = {'type': 'array', 'items': {'type': 'string'}, 'uniqueItems': True}
    if visual_ids:
        visuals['items']['enum'] = list(visual_ids)
    else:
        # An empty enum is invalid JSON Schema; no assets means empty arrays.
        visuals['maxItems'] = 0
    modules['items']['properties']['visual_ids'] = visuals
    return schema


def _curate(state, zones, phase, previous=None, feedback=None):
    from src.workflow.editorial_authoring import plan_schema, normalize_plan
    paper = paper_material(state)
    payload={'research_coverage':authoring_coverage(paper),
             'paper':paper,'family':family_brief(state,zones),
             'previous_draft':previous,'phase':phase,'geometry_feedback':feedback,
             'poster_inches':[state['poster_width'],state['poster_height']],
             'image_rules':{'horizontal_max_content_width_fraction':.4,
                            'vertical_max_module_height_fraction':.3,
                            'space_weight_applies_to':'whole_module_height'}}
    directory='editorial/'+phase
    charge(state,'curator' if phase=='curator' else 'merge',digest(payload),
           Path(state['sample_preparation_dir'])/directory)
    raw=request(state,'editorial_curator',payload,
        plan_schema(curator_schema(zones,payload['paper']['visuals'])),directory=directory,
        validator=lambda value:normalize_plan(value,state,zones,allow_underfull=phase=='curator'))
    return normalize_plan(raw,state,zones,allow_underfull=phase=='curator')


def editorial_curator_node(state):
    from src.workflow.editorial_authoring import setup_geometry_style, skeleton, persist_geometry, write
    from src.layout.authoring_geometry import prepare_geometry
    from src.layout.measurement_context import measurement_scope
    family=LayoutFamilyRegistry().get(state['sample_family']['family'])
    zones=deepcopy(list(family.zones))
    plan=_curate(state,zones,'curator')
    minimum,_=module_limits(zones)
    feedback = None
    if len(plan['modules'])<minimum:
        from src.layout.region_merges import merge_candidates
        count=len(plan['modules'])
        options=[r for r in merge_candidates(family,zones) if len(r[1])<=count<=module_limits(r[1])[1]]
        if not options:
            raise EditorialOutputError('Meaningful module deficit has no legal same-family merge')
        options.sort(key=lambda r:(len(zones)-len(r[1]),-max(z['width'] for z in r[1]),r[0]))
        label,zones,trace=options[0]
        state['editorial_merge_report']={'reason':'meaningful_module_deficit','initial_modules':count,
            'base_minimum':minimum,'selected':label,'merge_trace':trace,'legal_options':len(options)}
        feedback = {'reason': 'meaningful_module_deficit', 'merged_geometry': label}
    with measurement_scope((state.get('critic_config') or {}).get('layout_performance')):
        setup_geometry_style(state, plan)
        geometry = None if feedback else prepare_geometry(state, skeleton(plan), zones)
        if feedback is None and geometry['failures']:
            feedback = geometry
        if feedback is not None:
            # A legal region merge and geometric replanning share ONE request.
            plan = _curate(state, zones, 'merge', plan, feedback)
            setup_geometry_style(state, plan)
            geometry = prepare_geometry(state, skeleton(plan), zones)
        if geometry['failures']:
            save(Path(state['sample_preparation_dir'])/'editorial/failed_geometry.json', geometry)
            raise EditorialOutputError('Planned body frames remain infeasible after one adjustment: '+
                                       str(geometry['failures']))
        persist_geometry(state, plan, geometry)
        candidate = write(state, plan, geometry, zones, request, charge, ENTRY)
    state['editorial_zones']=zones
    state['editorial_visual_selection']=visual_selection(candidate,state)
    return install(state,candidate)


def editorial_color_node(state):
    from src.agents.color_agent import ColorAgent
    from utils.model_requests import SampleRequestFailure
    agent=ColorAgent()
    def extract(path, source):
        field='extracted_color' if source=='affiliation_logo' else 'theme_color'
        local=source.startswith('core_')
        def validate(value):
            if local and value[field] is None:return
            if not re.fullmatch(r'#[0-9a-fA-F]{6}',value[field]):
                raise EditorialStructureError('Theme color must be #RRGGBB',[(field,)])
        instructions=agent.logo_extraction_prompt if source=='affiliation_logo' else agent.figure_color_prompt
        if local:
            instructions+='\nUse ONLY this module-owned image. Return theme_color=null if it has no suitable chromatic accent; do not invent a default navy or borrow a logo color.'
        raw=request(state,'editorial_palette',{'source':source,'instructions':instructions},
            obj({field:{'type':['string','null']} if local else STRING}),
            directory='editorial/palette/'+source,images=[path],validator=validate,correction=False)
        return raw[field]
    theme=agent.color_config['fallback_theme'];source='configured_fallback';failures=[]
    logo=state.get('aff_logo_path')
    options=[('affiliation_logo',logo)] if logo and Path(logo).is_file() else []
    # Match the previous ColorAgent: only the classified key FIGURE is a fallback.
    key=(state.get('classified_visuals') or {}).get('key_visual')
    visual=(asset_index(state).get(key) or {}).get('path')
    if key and key.startswith('figure_') and visual and Path(visual).is_file():
        options.append(('key_visual',visual))
    for candidate,path in options:
        try:
            theme=extract(path,candidate);source=candidate;break
        except (SampleRequestFailure,TimeoutError,EditorialOutputError) as exc:
            failures.append({'source':candidate,'error_type':type(exc).__name__})
    scheme=agent._add_contrast_color(agent._generate_color_scheme(theme))
    scheme,variant=agent._apply_style_overrides(scheme,state)
    emphasis_report=None
    from src.layout.editorial import locked
    if (state.get('generation_route')=='optimization_family' and not locked(state)
            and ((state.get('critic_config') or {}).get('poster_editorial') or {}).get('enabled',True)):
        from src.layout.emphasis import resolve_emphasis
        resolved,emphasis_report=resolve_emphasis(scheme,state.get('critic_config'))
        if resolved:scheme.update(mono_light=resolved['background'],text=resolved['text_color'],contrast=resolved['accent_color'])
    state['color_scheme']=scheme
    state['color_provenance']={'source':source,'theme_color':theme,'variant':variant}
    if failures:state['color_provenance']['extraction_failures']=failures
    if emphasis_report is not None:state['color_provenance']['emphasis_resolution']=emphasis_report
    from src.workflow.editorial_emphasis import prepare
    if state.get('editorial_candidate') is not None:
        prepare(state,agent,extract)
        install(state,state['editorial_candidate'])
    agent._save_color_scheme(state)
    from src.agents.font_agent import FontAgent
    state['styling_interfaces']=FontAgent().get_styling_interfaces()
    return state


def editorial_title_node(state):
    from src.agents.section_title_designer import SectionTitleDesigner
    designer=SectionTitleDesigner()
    state['section_title_design']=designer._generate_colorblock_design(state['story_board'],state['color_scheme'])
    designer._save_title_design(state)
    return state


def merge_patch(state, raw):
    before=state['editorial_candidate'];old={m['module_id']:m for m in before['modules']}
    assert_visual_selection(before,state)
    changed_ids=[m['module_id'] for m in raw['modules']]
    removed=raw['remove_module_ids']
    if len(changed_ids)!=len(set(changed_ids)) or len(removed)!=len(set(removed)) or not set(removed)<=old.keys():
        raise EditorialStructureError('Invalid patch module IDs',[('modules',),('remove_module_ids',)])
    if set(removed)&set(changed_ids):
        raise EditorialOutputError('A patch cannot remove and replace the same module')
    replacements={m['module_id']:m for m in raw['modules']}
    modules=[deepcopy(replacements.get(m['module_id'],m)) for m in before['modules'] if m['module_id'] not in removed]
    modules.extend(deepcopy(m) for m in raw['modules'] if m['module_id'] not in old)
    ids=[m['module_id'] for m in modules]
    if raw['module_order']:
        if len(raw['module_order'])!=len(ids) or set(raw['module_order'])!=set(ids):
            raise EditorialStructureError('Explicit module_order must name all final modules once',[('module_order',)])
        by_id={m['module_id']:m for m in modules};modules=[by_id[mid] for mid in raw['module_order']]
    try:
        return normalize_candidate({'modules':modules,'narrative_flow':raw['narrative_flow'] or before['narrative_flow'],
                                    'core_module_ids':before['core_module_ids']},
                                   state,state['editorial_zones'])
    except EditorialStructureError as exc:
        # normalize_candidate diagnoses the merged poster, while the wire
        # response is a sparse module patch, possibly in a different order.
        indices = {m['module_id']:i for i,m in enumerate(raw['modules'])}
        paths = []
        for path in exc.paths:
            if len(path)>=2 and path[0]=='modules' and isinstance(path[1],int):
                mid = modules[path[1]]['module_id']
                if mid not in indices:
                    raise EditorialOutputError('Format error belongs to an unchanged module') from exc
                paths.append(('modules',indices[mid],*path[2:]))
            elif path and path[0] in raw:
                paths.append(path)
            else:
                raise EditorialOutputError('Format error belongs to a frozen field') from exc
        raise EditorialStructureError(str(exc),paths) from exc


def capacity_payload(state, result):
    """One final measured worklist, ahead of source material and the old body."""
    return {'phase':'capacity','capacity_tasks':capacity_tasks(result, state.get('editorial_plan')),
             'paper':paper_material(state),'whole_poster':state['editorial_candidate'],
             'fixed_visual_selection':state['editorial_visual_selection'],
             'fixed_module_composition':state['editorial_composition'],
             'fixed_core_panels':state['editorial_emphasis'],
             'family':family_brief(state,state['editorial_zones']),
             'measurements':capacity_measurements(result['report']),
             'actual_layout':result['spec'],'content_status':'not_preverified'}


def edit(state, result, phase):
    if phase!='capacity':raise ValueError('Only measured capacity edits are supported')
    assert_visual_selection(state['editorial_candidate'],state)
    from src.layout.editorial_composition import assert_composition
    assert_composition(state, durable=True)
    from src.workflow.editorial_emphasis import assert_emphasis
    assert_emphasis(state, durable=True)
    payload=capacity_payload(state,result)
    key=digest(payload);directory='editorial/edits/'+key
    charge(state,phase,key,Path(state['sample_preparation_dir'])/directory)
    raw=request(state,'editorial_balancer',payload,PATCH,directory=directory,
                validator=lambda value:merge_patch(state,value))
    candidate=merge_patch(state,raw)
    changed=candidate!=state['editorial_candidate']
    state.setdefault('editorial_history',[]).append({'phase':phase,'from':state['editorial_candidate']['candidate_id'],
        'to':candidate['candidate_id'],'reason':raw['reason'],'changed':changed,
        'observed_edit':observed_edit(state['editorial_candidate'],candidate),
        'prose_changes':prose_changes(state['editorial_candidate'],candidate),
        'measurements_before':capacity_guidance(result['report'])})
    if changed:install(state,candidate)
    else:record_measured_edit(state['editorial_history'],candidate,result['report'])
    return changed


def editorial_joint_node(state):
    from src.agents.section_title_designer import SectionTitleDesigner
    from src.layout.measurement_context import measurement_scope
    assert_visual_selection(state['editorial_candidate'],state)
    from src.layout.editorial_composition import initial_fit
    state['editorial_output_policy']=OUTPUT_POLICY
    with measurement_scope(state['critic_config'].get('layout_performance')) as measured:
        result=None
        completion='repair_limit_reached'
        # One global patch, with a baseline fit and a final fit if content changed.
        for round_index in range(LIMITS['capacity'] + 1):
            stopped(state)
            state['section_title_design']=SectionTitleDesigner()._generate_colorblock_design(state['story_board'],state['color_scheme'])
            result=(initial_fit(state, fitter=fit) if round_index == 0 else
                    fit(state,state['editorial_candidate'],state['editorial_zones']))
            before = state['editorial_candidate']
            record_measured_edit(state.get('editorial_history',[]), before,
                                 result.get('allocation_baseline_report', result['report']))
            coordinated = result.get('candidate', before)
            if coordinated != before:
                state.setdefault('editorial_history', []).append({
                    'phase': 'height_allocation', 'from': before['candidate_id'],
                    'to': coordinated['candidate_id'], 'changed': True,
                    'reason': 'Measured height transfer within regions; authored text and visuals unchanged.',
                    'observed_edit': observed_edit(before, coordinated),
                    'measurements_before': capacity_guidance(result['allocation_baseline_report']),
                    'measurements_after': capacity_guidance(result['report'])})
                install(state, coordinated)
            state['editorial_zones']=deepcopy(result['spec']['zones'])
            key=digest({'candidate':state['editorial_candidate'],'spec':result['spec']})
            save(Path(state['sample_preparation_dir'])/'editorial/fits'/(key+'.json'),
                 {'input_digest':key,'result':result})
            if result['report']['passed'] and result['report']['all_modules_90_percent']:
                completion='target_met';break
            if round_index==LIMITS['capacity']:break
            changed=edit(state,result,'capacity')
            if not changed:
                completion='no_useful_edit';break
        record_capacity_result(state.get('editorial_history', []), state['editorial_candidate'], result['report'])
        state['editorial_fit']=result['report']
        state['editorial_fit']['status']=('layout_defects' if not result['report']['passed'] else
            'fit' if result['report']['all_modules_90_percent'] else 'underfilled')
        state['editorial_fit'].update(completion_reason=completion,admission='freeze_and_score',
            generation_blocking=False)
        state['layout_feasibility_report']=result['report']
        state['layout_spec']=result['spec']
        state['story_board']=deepcopy(result['board']);state['optimized_story_board']=deepcopy(result['board'])
        state['draft_layout_mode']=False
        state['joint_candidate']={'version':VERSION,'status':'render_ready','board':result['board'],
            'layout_spec':result['spec'],'fit_report':result['report'],
            'compiled_geometry':geometry_digest(result['layout'])}
        state['joint_candidate']['digest']=digest(state['joint_candidate'])
        state['layout_performance_report']=measured.report('completed')
        SectionTitleDesigner()._save_title_design(state)
        state['editorial_snapshot']={'version':VERSION,'digest':digest(snapshot_payload(state))}
        assert_editorial_ready(state)
    return state


def editorial_compile_node(state):
    from src.layout.measurement_context import measurement_scope
    assert_editorial_ready(state)
    # Reuse measurements only within this compilation; all freeze checks remain.
    with measurement_scope((state.get('critic_config') or {}).get('layout_performance')):
        result=measure(state,state['editorial_candidate'],state['layout_spec']['zones'])
    if not result['report']['passed'] and not permits_layout_defects(state):
        raise EditorialOutputError('Frozen editorial layout no longer fits')
    state['design_layout']=result['layout']
    from src.agents.layout_agent import LayoutAgent
    agent=LayoutAgent()
    state['final_column_analysis']=agent._generate_column_analysis(result['layout'],state)
    state['layout_family_analysis']=state['final_column_analysis']
    agent._save_final_layout(state)
    state['layout_preflight_report']=result['report']['preflight']
    state['layout_preflight_failed']=False
    assert_editorial_ready(state,compiled=True)
    return state


class EditorialPreparation:
    """Per-stage checkpoints without a source-document or verified-claim contract."""
    def __init__(self,storage,run_id,nodes):
        self.storage,self.run_id,self.nodes=storage,run_id,list(nodes)

    def run(self,state,task,execute,control,after_planner=None):
        root=self.storage.sample_path(self.run_id,task['sample_id'])/'preparation'
        root.mkdir(parents=True,exist_ok=True)
        state.update(output_dir=str(root),sample_preparation_dir=str(root),sample_edit_budget_dir=str(root.parent))
        state['iteration_context']={'run_id':self.run_id,'sample_id':task['sample_id'],'iteration':task['number'],
            'random_seed':task['seed'],'generation_purpose':'editorial','preparation_policy_version':PREPARATION}
        if after_planner:after_planner(state)
        identity=digest({'version':PREPARATION,'run':self.run_id,'task':task,'paper':state['paper_foundation_digest'],
                         'family':state['sample_family']})
        paper=paper_identity(state)
        ready=root/'READY.json'
        if ready.exists():
            value=read(ready,identity)
            if read(root/'editorial_sample.json',identity)!=value:
                raise ValueError('Editorial ready checkpoint differs from sample snapshot')
            state.update(deepcopy(value['fields']));assert_editorial_ready(state)
            state['sample_science_digest']=digest(value)
            return state
        previous=identity
        for i,node in enumerate(self.nodes):
            stopped(state)
            key=digest({'previous':previous,'node':node.__name__})
            path=root/f'stage_{i+1:02d}.json'
            if path.exists():
                value=read(path,key);state.update(deepcopy(value['fields']))
            else:
                state=execute(state,[node],stage='sample_preparation')
                if state.get('errors') or state.get('_joint_interrupted'):return state
                if paper_identity(state)!=paper:
                    raise ValueError('Editorial sample changed shared paper material')
                value={'input_digest':key,'fields':{k:deepcopy(state.get(k)) for k in SAMPLE_KEYS}}
                save(path,value)
            previous=digest(value)
            if control.force_stop_requested:return state
        assert_editorial_ready(state)
        value={'input_digest':identity,'fields':{k:deepcopy(state.get(k)) for k in SAMPLE_KEYS},'stage_chain_digest':previous}
        save(root/'editorial_sample.json',value);save(ready,value)
        state['sample_science_digest']=digest(value)
        return state
