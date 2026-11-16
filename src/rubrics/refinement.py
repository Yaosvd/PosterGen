"""One GLM review, one isolated program revision, then the unchanged evaluator G."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import difflib
import json
import shutil

from jsonschema import Draft202012Validator
from utils.persistence import digest, file_hash
from src.rubrics import program
from src.rubrics.library import validate, rules_for
from src.rubrics.providers import configuration, image_block
from src.rubrics.storage import IntegrityError, immutable, read, text_file, request_once

MODES = ('generate-score', 'rubric-refine-score')
FIELDS = ('editorial_candidate','optimized_story_board','story_board','styled_layout','design_layout',
          'layout_spec','current_candidate','render_diagnostics','render_fit_report',
          'layout_preflight_report','layout_preflight_failed','layout_feasibility_report',
          'final_column_analysis','layout_family_analysis','section_fit_analysis',
          'editorial_format_report','editorial_fit','joint_candidate','refinement_execution')


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


TEXT = {'type':'string','minLength':1}
REVIEW_SCHEMA = obj({'checks': {'type':'array','items':obj({'rule_id': TEXT,
    'status':{'type':'string','enum':['satisfied','violated','not_applicable','uncertain']},
    'evidence':TEXT, 'locations':{'type':'array','items':obj({'module_id':{'type':'string'},'element_id':{'type':'string'}})},
    'action':{'type':'string'}})}})
ACTOR_SCHEMA = obj({'program': TEXT, 'change_summary': TEXT})


def preflight_internal(state):
    import os
    for field,prefix in (('text_model','LOCAL_TEXT'),('vision_model','LOCAL_VISION')):
        if state[field].provider not in ('local_text','local_vision') or not os.environ.get(prefix+'_BASE_URL'):
            raise ValueError('Refinement requires the configured GLM text and vision endpoints before generation')
    configuration()


def glm_request(state, role, payload, schema, root, images=()):
    from utils.langgraph_utils import LangGraphAgent, extract_json
    from src.workflow.editorial_requests import wire_schema
    from langchain_openai import ChatOpenAI
    settings = configuration()[role]
    # GLM stays on the project's explicit local route; there is no GPT fallback.
    base = state['vision_model' if images else 'text_model']
    if base.provider not in ('local_text','local_vision'):
        raise ValueError('Internal review/revision requires the project GLM endpoint')
    config = replace(base, model_name=settings['model'], temperature=settings['temperature'],
                     max_tokens=settings['max_tokens'], enable_thinking=False, json_mode=True)
    template = Path(__file__).resolve().parents[2]/'config/prompts'/('rubrics_'+role+'.txt')
    prompt = template.read_text()+'\nINPUT:\n'+json.dumps(payload,ensure_ascii=False,allow_nan=False)
    prompt += '\nOUTPUT SCHEMA:\n'+json.dumps(schema)
    identity = {'role':role,'settings':settings,'provider':config.provider,'prompt':prompt,
                'schema':schema,'images':[file_hash(p) for p in images]}
    def invoke():
        request_state = dict(state)
        request_state['critic_config'] = deepcopy(state.get('critic_config') or {})
        request_state['critic_config'].setdefault('sample_execution', {})['max_transient_retries'] = 0
        agent = LangGraphAgent('Follow the Rubrics poster '+role+' contract and return its JSON object.',
                               config, request_state, 'rubrics_'+role)
        if isinstance(agent.model, ChatOpenAI):
            agent.model = agent.model.bind(response_format={'type':'json_schema','json_schema':{
                'name':'rubrics_'+role,'strict':True,'schema':wire_schema(schema,config.provider)}})
        message = json.dumps([{'type':'text','text':prompt},*[image_block(p) for p in images]]) if images else prompt
        response = agent.step(message)
        getattr(state['tokens'], 'add_vision' if images else 'add_text')(response.input_tokens,response.output_tokens)
        return {'content':response.content,'input_tokens':response.input_tokens,'output_tokens':response.output_tokens}
    raw = request_once(root, identity, invoke)
    value = extract_json(raw['content'])
    Draft202012Validator(schema).validate(value)
    return value


def _binding(state):
    from src.workflow.editorial_contract import asset_index
    return {'fields':{k:state.get(k) for k in ('editorial_candidate','optimized_story_board','story_board','styled_layout',
            'design_layout','layout_spec','current_candidate','editorial_format_report')},
            'paper':file_hash(state['pdf_path']), 'dimensions':[state['poster_width'],state['poster_height']],
            'palette':state.get('color_scheme'),'title_style':state.get('section_title_design'),
            'assets':{k:file_hash(v['path']) for k,v in asset_index(state).items()},
            'logos':{k:file_hash(state[k]) if state.get(k) else None for k in ('logo_path','aff_logo_path')}}


def assert_evaluation_ready(state, *, compiled=False):
    receipt = state.get('refinement_execution')
    if receipt is None:
        from src.workflow.editorial_contract import assert_editorial_ready
        return assert_editorial_ready(state, compiled=compiled)
    root = Path(state['refinement_directory']).resolve()
    if not root.is_relative_to(Path(state['output_dir']).resolve()):
        raise IntegrityError('Refinement receipt is outside its attempt')
    durable = read(root/'execution.json')
    if durable != receipt or digest(_binding(state)) != receipt['state_digest']:
        raise IntegrityError('Revised content/geometry differs from executed program')
    if file_hash(root/'C1.py') != receipt['script_hash']:
        raise IntegrityError('Revised program changed after execution')
    if file_hash(root/'C0.py') != receipt['initial_script_hash'] or read(root/'identity.json') != receipt['initial_identity']:
        raise IntegrityError('Revised program lost its initial provenance')
    for kind in ('pptx','png'):
        if file_hash(state['current_candidate'][kind+'_path']) != receipt['artifact_hashes'][kind]:
            raise IntegrityError('Revised rendered artifact changed')
    return True


def render(state, destination):
    from src.agents.renderer import Renderer
    destination = Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    renderer = Renderer()
    renderer.styling_interfaces = renderer._load_styling_interfaces(state)
    pptx = destination/'poster.pptx'
    renderer._render_presentation(state,pptx)
    png = renderer._convert_to_png(pptx)
    if not png or not Path(png).is_file():
        raise ValueError('Revised poster preview could not be rendered')
    state['current_candidate'] = {**state['current_candidate'],'status':'rendered',
        'pptx_path':str(pptx),'png_path':str(png)}
    state['render_diagnostics'] = {'pptx_created':True,'png_created':True,
                                 'pptx_path':str(pptx),'png_path':str(png),'source':'rubrics_program_v1'}
    return state


def _remeasure(state):
    """Discard stale diagnostics; measure the actual revised bodies and artifacts."""
    from src.layout.text_height_measurement import measure_text_height
    from src.layout.editorial_text import formula_plan
    from src.layout.editorial import presentation_line_count
    for e in state['styled_layout']:
        if e['type'] != 'text':
            continue
        font = e.get('font_family','Arial'); size = e.get('font_size',24)
        plan = formula_plan(e['content'],e['width'],font,size,1.0,e['editorial_paragraphs'],styled=True)
        if plan:
            height = plan['height']
        else:
            height = max(measure_text_height(e['content'],e['width'],font,size,1.0)['optimal_height'],
                         presentation_line_count(e['content'],e['width'],font,size,e['editorial_paragraphs'])*size/72*1.2+.1)
        e['required_text_height'] = float(height)
    # Intrinsic bottom is recomputed; allocated module_frame is never enlarged to hide overflow.
    for e in state['styled_layout']:
        if e['type'] == 'section_container':
            children = [c for c in state['styled_layout'] if c.get('section_id')==e['section_id'] and c['type'] in {'text','visual','section_title'}]
            e['height'] = float(max(c['y']+max(c['height'],c.get('required_text_height',0)) for c in children)-e['y'])
    state['design_layout'] = deepcopy(state['styled_layout'])
    for key in ('critic_report','_editorial_content_evaluation','_editorial_visual_evaluation','critic_measurement_evidence',
                'section_fit_analysis','final_column_analysis','layout_family_analysis','layout_feasibility_report',
                'layout_preflight_report','render_fit_report','editorial_fit'):
        state.pop(key,None)
    from src.layout.feasibility import validate_compiled_layout
    from src.config.poster_config import load_config
    config = load_config()['layout']
    report = validate_compiled_layout(state['styled_layout'],state['layout_spec'],state,
        poster_margin=config['poster_margin'],title_height_fraction=config['title_height_fraction'])
    report.update(status='passed' if report['passed'] else 'failed', admission='record_and_score',generation_blocking=False)
    state['layout_preflight_report'] = report
    state['layout_preflight_failed'] = not report['passed']
    from src.workflow.editorial_body_format import report
    state['editorial_format_report'] = report(state['editorial_candidate'])
    return state


def refine_once(initial, *, request=glm_request, renderer=render, measure=_remeasure, control=None):
    library = validate(initial['generation_rubrics_snapshot'],published=True)
    root = Path(initial['output_dir'])/'refinement'
    initial['refinement_directory'] = str(root)
    root.mkdir(parents=True,exist_ok=True)
    identity = {'candidate':initial['current_candidate']['candidate_id'],'rubrics':library['version'],
                'initial':digest(_binding(initial))}
    immutable(root/'identity.json',identity)
    if (root/'selection.json').exists():
        selected = read(root/'selection.json')
        if selected['variant']=='P1':
            initial.update(read(root/'selected_state.json'))
            assert_evaluation_ready(initial,compiled=True)
        for kind,expected in selected['artifact_hashes'].items():
            if file_hash(initial['current_candidate'][kind+'_path'])!=expected:
                raise IntegrityError('Selected final artifact changed')
        initial['refinement_result'] = selected
        return initial
    for kind in ('pptx','png'):
        target = root/('P0.'+kind)
        if target.exists() and file_hash(target)!=file_hash(initial['current_candidate'][kind+'_path']):
            raise IntegrityError('Initial artifact snapshot changed')
        if not target.exists():
            shutil.copy2(initial['current_candidate'][kind+'_path'],target)
    from src.workflow.editorial_contract import paper_material
    immutable(root/'paper.json',paper_material(initial,original=True))
    # A portable, immutable resource pack accompanies each editable sample script.
    from src.workflow.editorial_contract import asset_index
    resources = {}
    for key,item in asset_index(initial).items():
        original = Path(item['path'])
        relative = 'assets/'+digest(key)[:24]+original.suffix.lower()
        target = root/relative
        target.parent.mkdir(exist_ok=True)
        if target.exists() and file_hash(target)!=file_hash(original):
            raise IntegrityError('Saved script resource changed')
        if not target.exists(): shutil.copy2(original,target)
        resources[key] = {'path':relative,'sha256':file_hash(target)}
    immutable(root/'resources.json',resources)
    immutable(root/'drawing_context.json',{k:deepcopy(initial.get(k)) for k in
        ('poster_width','poster_height','layout_spec','color_scheme','section_title_design','font_sizes',
         'narrative_content','sample_family','style_overrides','url')})
    stage = 'export'
    try:
        source = program.export(initial)
        text_file(root/'C0.py',source)
        replay = program.materialize(program.execute_isolated(source),initial)
        if replay['styled_layout'] != initial['styled_layout']:
            raise ValueError('C0 replay does not reproduce initial drawing data')
        # Compare the actual replay raster as well as the executable drawing representation.
        replay = renderer(replay,root/'replay')
        from PIL import Image, ImageChops
        with Image.open(root/'P0.png') as a, Image.open(replay['current_candidate']['png_path']) as b:
            if a.size != b.size or ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox():
                raise ValueError('C0 replay differs from initial rendered poster')
        if control and control.force_stop_requested:
            from utils.concurrency import WorkStopped
            raise WorkStopped()
        stage = 'review'
        from src.layout.element_identity import identified_layout
        payload = {'rules':rules_for(library,'review'),'paper':paper_material(initial,original=True),
                   'candidate':initial['editorial_candidate'],'layout':identified_layout(initial['styled_layout']),
                   'measurements':{k:initial.get(k) for k in ('render_fit_report','layout_preflight_report','section_fit_analysis')}}
        review = request(initial,'review',payload,REVIEW_SCHEMA,root/'review',images=(root/'P0.png',))
        Draft202012Validator(REVIEW_SCHEMA).validate(review)
        checks = review['checks']
        if len(checks)!=len(library['rules']) or {c['rule_id'] for c in checks}!={r['id'] for r in library['rules']}:
            raise ValueError('Critic must judge every rule exactly once')
        if any(c['status']=='violated' and not c['action'].strip() for c in checks):
            raise ValueError('Violated rules require executable revision advice')
        ids={e['id']:e.get('section_id') for e in identified_layout(initial['styled_layout'])}
        mids={m['module_id'] for m in initial['editorial_candidate']['modules']}
        for check in checks:
            for location in check['locations']:
                mid,eid=location['module_id'],location['element_id']
                if (mid and mid not in mids) or (eid and eid not in ids) or (mid and eid and ids[eid]!=mid):
                    raise ValueError('Critic location does not identify an actual initial element')
        immutable(root/'review.json',review)
        stage = 'revision'
        actor = request(initial,'revision',{**payload,'review':review,'program':source,
            'family':initial['layout_spec'],'allowed_visual_ids':list(asset_index(initial))},
            ACTOR_SCHEMA,root/'actor',images=(root/'P0.png',))
        Draft202012Validator(ACTOR_SCHEMA).validate(actor)
        text_file(root/'C1.py',actor['program'])
        text_file(root/'changes.diff',''.join(difflib.unified_diff(source.splitlines(True),actor['program'].splitlines(True),fromfile='C0.py',tofile='C1.py')))
        immutable(root/'actor.json',actor)
        if control and control.force_stop_requested:
            from utils.concurrency import WorkStopped
            raise WorkStopped()
        stage = 'execution'
        if digest(_binding(initial))!=identity['initial']:
            raise IntegrityError('Initial source or assets changed during revision')
        revised = program.materialize(program.execute_isolated(actor['program']),initial)
        revised = measure(revised)
        revised = renderer(revised,root/'P1')
        if measure is _remeasure:
            from src.layout.render_fit import audit_rendered_text
            revised['render_fit_report'] = audit_rendered_text(revised)
        receipt = {'schema_version':1,'script_hash':file_hash(root/'C1.py'),
            'initial_script_hash':file_hash(root/'C0.py'),'initial_identity':identity,
            'state_digest':digest(_binding(revised)), 'artifact_hashes':{
                k:file_hash(revised['current_candidate'][k+'_path']) for k in ('pptx','png')}}
        immutable(root/'execution.json',receipt)
        revised['refinement_execution'] = receipt
        assert_evaluation_ready(revised,compiled=True)
        immutable(root/'selected_state.json',{k:deepcopy(revised.get(k)) for k in FIELDS})
        selected = {'variant':'P1','status':'revised','rubrics':library['version'],
                    'artifact_hashes':receipt['artifact_hashes']}
        immutable(root/'selection.json',selected)
        revised['refinement_result'] = selected
        return revised
    except IntegrityError:
        raise
    except Exception as exc:
        from src.workflow.editorial_contract import EditorialInterrupted
        if isinstance(exc,EditorialInterrupted) or (control and control.force_stop_requested):
            from utils.concurrency import WorkStopped
            raise WorkStopped() from exc
        selected = {'variant':'P0','status':stage+'_failed','error_type':type(exc).__name__,
                    'reason':str(exc),'rubrics':library['version'],
                    'artifact_hashes':{k:file_hash(initial['current_candidate'][k+'_path']) for k in ('pptx','png')}}
        immutable(root/'selection.json',selected)
        initial['refinement_result'] = selected
        return initial
