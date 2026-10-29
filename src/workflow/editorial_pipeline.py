"""Finite upstream-style writing, model-owned placement and measured editing."""
from copy import deepcopy
from pathlib import Path
import json
import re

from src.workflow.editorial_contract import (VERSION, PREPARATION, SAMPLE_KEYS, EditorialOutputError,
    EditorialStructureError, asset_index, paper_identity, paper_material, normalize_candidate,
    make_board, module_limits, assert_editorial_ready, snapshot_payload)
from src.workflow.editorial_requests import obj, STRING, STRINGS, request, read, save, stopped
from src.layout.families import LayoutFamilyRegistry
from src.layout.editorial_layout import family_brief, fit, measure
from utils.persistence import digest, file_hash

ENTRY = obj({'item_id':STRING,'text':STRING,'display_label':STRING,'parent_item_id':STRING})
MODULE = obj({'module_id':STRING,'title':STRING,'zone_id':STRING,
    'importance':{'type':'integer','minimum':1,'maximum':3},
    'space_weight':{'type':'number','minimum':1,'maximum':3},
    'presentation_style':{'type':'string','enum':['plain','topics','steps']},
    'reader_question':STRING,'entries':{'type':'array','items':ENTRY,'minItems':1},
    'visual_ids':STRINGS,'reserve_visual_ids':STRINGS,'visual_rationale':STRING})
CANDIDATE = obj({'modules':{'type':'array','items':MODULE,'minItems':1},'narrative_flow':STRING,'reason':STRING})
PATCH = obj({'modules':{'type':'array','items':MODULE},'remove_module_ids':STRINGS,
             'module_order':STRINGS,'narrative_flow':STRING,'reason':STRING})
LIMITS = {'curator':1,'merge':1,'capacity':3,'quality':1,'visual':4}


def charge(state, phase, key, request_root=None):
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
    board=make_board(candidate)
    state['story_board']=deepcopy(board);state['optimized_story_board']=board
    state.pop('editorial_snapshot',None)
    if state.get('color_scheme'):
        from src.agents.section_title_designer import SectionTitleDesigner
        state['section_title_design'] = SectionTitleDesigner()._generate_colorblock_design(board,state['color_scheme'])
    return state


def _curate(state, zones, phase, previous=None):
    payload={'paper':paper_material(state),'family':family_brief(state,zones),
             'previous_draft':previous,'phase':phase,'poster_inches':[state['poster_width'],state['poster_height']]}
    directory='editorial/'+phase
    charge(state,'curator' if phase=='curator' else 'merge',digest(payload),
           Path(state['sample_preparation_dir'])/directory)
    raw=request(state,'editorial_curator',payload,CANDIDATE,directory=directory,
        validator=lambda value:normalize_candidate(value,state,zones,allow_underfull=phase=='curator'))
    return normalize_candidate(raw,state,zones,allow_underfull=phase=='curator')


def editorial_curator_node(state):
    family=LayoutFamilyRegistry().get(state['sample_family']['family'])
    zones=deepcopy(list(family.zones))
    candidate=_curate(state,zones,'curator')
    minimum,_=module_limits(zones)
    if len(candidate['modules'])<minimum:
        from src.layout.region_merges import merge_candidates
        count=len(candidate['modules'])
        options=[r for r in merge_candidates(family,zones) if len(r[1])<=count<=module_limits(r[1])[1]]
        if not options:
            raise EditorialOutputError('Meaningful module deficit has no legal same-family merge')
        # Fewest merges first, then wider regions useful to the actual selected visuals.
        options.sort(key=lambda r:(len(zones)-len(r[1]),-max(z['width'] for z in r[1]),r[0]))
        label,zones,trace=options[0]
        state['editorial_merge_report']={'reason':'meaningful_module_deficit','initial_modules':count,
            'base_minimum':minimum,'selected':label,'merge_trace':trace,'legal_options':len(options)}
        candidate=_curate(state,zones,'merge',candidate)
    state['editorial_zones']=zones
    return install(state,candidate)


def editorial_color_node(state):
    from src.agents.color_agent import ColorAgent
    path=state.get('aff_logo_path')
    if not path or not Path(path).is_file():
        key=(state.get('classified_visuals') or {}).get('key_visual')
        path=(asset_index(state).get(key) or {}).get('path')
    theme='#1E3A8A'
    if path and Path(path).is_file():
        def validate(value):
            if not re.fullmatch(r'#[0-9a-fA-F]{6}',value['extracted_color']):
                raise EditorialStructureError('Theme color must be #RRGGBB',[('extracted_color',)])
        raw=request(state,'editorial_palette',{'task':'Choose one suitable institution/figure-derived poster theme.'},
            obj({'extracted_color':STRING}),directory='editorial/palette',images=[path],validator=validate)
        theme=raw['extracted_color']
    agent=ColorAgent()
    state['color_scheme']=agent._add_contrast_color(agent._generate_color_scheme(theme))
    state['color_provenance']={'source':'original_logo_or_visual' if path else 'configured_fallback','theme_color':theme}
    from src.agents.font_agent import FontAgent
    state['styling_interfaces']=FontAgent().get_styling_interfaces()
    return state


def editorial_title_node(state):
    from src.agents.section_title_designer import SectionTitleDesigner
    state['section_title_design']=SectionTitleDesigner()._generate_colorblock_design(state['story_board'],state['color_scheme'])
    return state


def merge_patch(state, raw):
    before=state['editorial_candidate'];old={m['module_id']:m for m in before['modules']}
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
    return normalize_candidate({'modules':modules,'narrative_flow':raw['narrative_flow'] or before['narrative_flow']},
                               state,state['editorial_zones'])


def preview(state, result):
    from src.agents.font_agent import FontAgent
    from src.agents.renderer import Renderer
    key=digest({'candidate':state['editorial_candidate'],'spec':result['spec'],'palette':state['color_scheme']})
    root=Path(state['sample_preparation_dir'])/'editorial/previews'/key
    ready=root/'READY.json'
    if ready.exists():
        value=read(ready,key)
        if file_hash(value['png'])!=value['png_hash'] or file_hash(value['pptx'])!=value['pptx_hash']:
            raise ValueError('Editorial preview changed')
        return value['png']
    if (root/'CHARGED.json').exists():
        raise ValueError('Editorial preview charged but incomplete; refusing automatic rerender')
    stopped(state)
    save(root/'CHARGED.json',{'input_digest':key})
    view={**state,'story_board':result['board'],'optimized_story_board':result['board'],
          'design_layout':result['layout'],'layout_spec':result['spec'],'output_dir':str(root)}
    font=FontAgent();view['styled_layout']=font._apply_styling(deepcopy(result['layout']),state['color_scheme'],
                                                           {'section_keywords':{}},view)
    renderer=Renderer();renderer.styling_interfaces=state['styling_interfaces']
    path=root/'draft.pptx';renderer._render_presentation(view,path)
    png=renderer._convert_to_png(path)
    if not png:raise EditorialOutputError('Could not render editorial quality preview')
    save(ready,{'input_digest':key,'png':str(png),'png_hash':file_hash(png),'pptx':str(path),'pptx_hash':file_hash(path)})
    return str(png)


def edit(state, result, phase):
    payload={'phase':phase,'paper':paper_material(state),'whole_poster':state['editorial_candidate'],
             'family':family_brief(state,state['editorial_zones']),'measurements':result['report'],
             'actual_layout':result['spec'],'content_status':'not_preverified'}
    key=digest(payload);directory='editorial/edits/'+key
    charge(state,phase,key,Path(state['sample_preparation_dir'])/directory)
    images=[preview(state,result)] if phase=='quality' else []
    raw=request(state,'editorial_balancer',payload,PATCH,directory=directory,images=images,
                validator=lambda value:merge_patch(state,value))
    candidate=merge_patch(state,raw)
    changed=candidate!=state['editorial_candidate']
    state.setdefault('editorial_history',[]).append({'phase':phase,'from':state['editorial_candidate']['candidate_id'],
        'to':candidate['candidate_id'],'reason':raw['reason'],'changed':changed})
    if changed:install(state,candidate)
    return changed


def restore_visuals(state,result):
    options=[(m['module_id'],v) for m in state['editorial_candidate']['modules'] for v in m['reserve_visual_ids']][:2]
    for mid,vid in options:
        stopped(state)
        key=digest({'candidate':state['editorial_candidate'],'spec':result['spec'],'module':mid,'visual':vid})
        path=Path(state['sample_preparation_dir'])/'editorial/visual_probes'/(key+'.json')
        already=any(e['phase']=='visual' and e['key']==key for e in state['editorial_budget']['charges'])
        charge(state,'visual',key)
        if already:
            if not path.exists():raise ValueError('Visual probe charged but result missing')
            saved=read(path,key)
            if saved['adopted']:
                install(state,saved['candidate']);result=measure(state,saved['candidate'],state['editorial_zones'])
            continue
        candidate=deepcopy(state['editorial_candidate']);module=next(m for m in candidate['modules'] if m['module_id']==mid)
        module['visual_ids'].append(vid);module['reserve_visual_ids'].remove(vid)
        candidate=normalize_candidate(candidate,state,state['editorial_zones'])
        trial=measure(state,candidate,state['editorial_zones'])
        adopted=trial['report']['passed'] and trial['report']['total_underfill_inches']<=result['report']['total_underfill_inches']+.01
        save(path,{'input_digest':key,'adopted':adopted,'candidate':candidate,'report':trial['report']})
        if adopted:install(state,candidate);result=trial
    return result


def editorial_joint_node(state):
    from src.agents.section_title_designer import SectionTitleDesigner
    from src.layout.measurement_context import measurement_scope
    with measurement_scope(state['critic_config'].get('layout_performance')):
        result=None
        for round_index in range(4):
            stopped(state)
            state['section_title_design']=SectionTitleDesigner()._generate_colorblock_design(state['story_board'],state['color_scheme'])
            result=fit(state,state['editorial_candidate'],state['editorial_zones'])
            state['editorial_zones']=deepcopy(result['spec']['zones'])
            key=digest({'candidate':state['editorial_candidate'],'spec':result['spec']})
            save(Path(state['sample_preparation_dir'])/'editorial/fits'/(key+'.json'),
                 {'input_digest':key,'result':result})
            if result['report']['passed'] and result['report']['all_modules_90_percent']:break
            if round_index==3:break
            changed=edit(state,result,'capacity')
            if not changed:
                if not result['report']['passed']:
                    raise EditorialOutputError('Unresolved overflow received no actionable edit')
                break
        if not result['report']['passed']:
            raise EditorialOutputError('No physical fit within three measured edits')
        result=restore_visuals(state,result)
        baseline=deepcopy(state);baseline_result=deepcopy(result)
        for key in ('tokens','timing_metrics','_force_stop_requested'):
            if key in state:baseline[key]=state[key]
        try:
            changed=edit(state,result,'quality')
            if changed:
                trial=fit(state,state['editorial_candidate'],state['editorial_zones'])
                from src.layout.whitespace import no_added_whitespace
                if (not trial['report']['passed'] or not no_added_whitespace(
                    result['report']['composition_whitespace'],trial['report']['composition_whitespace'])):
                    raise EditorialOutputError('Quality edit regressed physical fit/whitespace')
                result=trial;state['editorial_zones']=deepcopy(trial['spec']['zones'])
            state['editorial_quality']={'status':'adopted' if changed else 'reviewed_no_change'}
        except EditorialOutputError as exc:
            budget=state['editorial_budget'];history=state.get('editorial_history',[])
            state.clear();state.update(baseline);state['editorial_budget']=budget;state['editorial_history']=history
            result=baseline_result;state['editorial_quality']={'status':'rejected','reason':str(exc)}
        state['editorial_fit']=result['report']
        state['editorial_fit']['status']='fit' if result['report']['all_modules_90_percent'] else 'underfilled'
        state['layout_feasibility_report']=result['report']
        state['layout_spec']=result['spec']
        state['story_board']=deepcopy(result['board']);state['optimized_story_board']=deepcopy(result['board'])
        state['draft_layout_mode']=False
        state['joint_candidate']={'version':VERSION,'status':'render_ready','board':result['board'],
            'layout_spec':result['spec'],'fit_report':result['report']}
        state['joint_candidate']['digest']=digest(state['joint_candidate'])
        state['editorial_snapshot']={'version':VERSION,'digest':digest(snapshot_payload(state))}
        assert_editorial_ready(state)
    return state


def editorial_compile_node(state):
    assert_editorial_ready(state)
    result=measure(state,state['editorial_candidate'],state['layout_spec']['zones'])
    if not result['report']['passed']:
        raise EditorialOutputError('Frozen editorial layout no longer fits')
    state['design_layout']=result['layout']
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
