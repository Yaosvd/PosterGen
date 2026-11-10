"""Digest-bound editorial requests with one shared, field-scoped format repair."""
from copy import deepcopy
from pathlib import Path
import base64
import json

from jsonschema import Draft202012Validator
from utils.persistence import _atomic_json, digest, read_json, file_hash
from src.workflow.editorial_contract import (VERSION, EditorialOutputError, EditorialStructureError, EditorialInterrupted)
from src.workflow.editorial_format import VERSION as REPAIR_VERSION, repair_plan, apply_repair, repair_prompt
from src.workflow.editorial_planning import EditorialPlanningError

STRING = {'type': 'string'}
STRINGS = {'type': 'array', 'items': STRING}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def wire_schema(schema, provider):
    """Keep local validation complete while avoiding a local server grammar error.

    The local vLLM endpoint rejects uniqueItems before generating any text. Only
    omit it from the generation constraint; prompts, journals and validators use
    the original schema. Walk schema positions, never property names or enum data.
    """
    result = deepcopy(schema)
    if provider not in ('local_text', 'local_vision'):
        return result

    def visit(node):
        if not isinstance(node, dict):
            return
        node.pop('uniqueItems', None)
        for key in ('properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'):
            for child in node.get(key, {}).values():
                visit(child)
        for key in ('items', 'additionalItems', 'additionalProperties', 'unevaluatedItems',
                    'unevaluatedProperties', 'contains', 'propertyNames', 'not', 'if', 'then', 'else',
                    'allOf', 'anyOf', 'oneOf', 'prefixItems'):
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    visit(item)
            else:
                visit(child)

    visit(result)
    return result


def save(path, value):
    _atomic_json(Path(path), {'payload': value, 'digest': digest(value)})


def read(path, identity):
    envelope = read_json(Path(path)); value = envelope['payload']
    if envelope.get('digest') != digest(value) or value.get('input_digest') != identity:
        raise ValueError('Editorial journal identity/digest mismatch')
    return value


def stopped(state):
    if (state.get('_force_stop_requested') or (lambda: False))():
        raise EditorialInterrupted()


def masked(value, paths):
    value = deepcopy(value)
    for path in paths:
        if not path:
            return None
        parent = value
        try:
            for key in path[:-1]: parent = parent[key]
            if isinstance(parent, dict): parent.pop(path[-1], None)
            else: parent[path[-1]] = None
        except (KeyError, IndexError, TypeError):
            pass
    return value


def _curator_repair_context(payload, original):
    paper = payload['paper']
    modules = original.get('modules', []) if isinstance(original, dict) else []
    if not isinstance(modules, list):
        modules = []
    return {
        'available_visual_ids': list(paper['visuals']),
        'key_visual': (paper.get('classified_visuals') or {}).get('key_visual'),
        'current_ownership': [
            {'module_index': i, 'module_id': module.get('module_id'),
             'visual_ids': module.get('visual_ids', [])}
            for i, module in enumerate(modules) if isinstance(module, dict)],
        'rules': [
            'Use only available_visual_ids, exactly as listed. A caption subpanel (a)/(b) '
            'is not a separate asset: do not invent IDs, rename, split or crop visuals.',
            'Each selected visual has exactly one module owner across the entire draft, '
            'with no repeats inside an array. Resolve duplicated owners jointly across the diagnosed fields.',
            'A diagnosed visual_ids array may be [] when its module does not own a visual. '
            'If key_visual is non-null, keep it in exactly one module.',
            'Undiagnosed fields and owners remain fixed. Return only the diagnosed repair slots; '
            'do not rewrite prose, labels, module order or rationale.'],
    }


def _request(state, kind, payload, schema, *, directory, validator=None, images=(), correction=True, parse_response=None,
             pre_validator=None):
    from utils.langgraph_utils import LangGraphAgent, ChatOpenAI, extract_json, load_prompt
    from utils.agent_policy import apply_agent_policy
    stopped(state)
    prompt = load_prompt('config/prompts/'+kind+'.txt')+'\nINPUT:\n'+json.dumps(payload, ensure_ascii=False)
    prompt += '\nCOMPLETE OUTPUT JSON SCHEMA:\n'+json.dumps(schema, ensure_ascii=False)
    context = state.get('iteration_context') or {}
    model_key = 'vision_model' if images else 'text_model'
    policy = {'editorial_curator':'source_curator', 'editorial_writer':'source_curator', 'editorial_balancer':'source_balancer',
              'editorial_content_critic':'critic_content', 'editorial_visual_critic':'critic_visual',
              'editorial_palette':'color_agent'}.get(kind, 'parser')
    config = apply_agent_policy(state[model_key], policy)
    identity = digest({'version': VERSION, 'paper': state.get('paper_foundation_digest') or digest(state.get('raw_text')),
        'context': {k:context.get(k) for k in ('run_id','sample_id','random_seed','layout_family')},
        'prompt':prompt, 'model':config, 'images':[file_hash(p) for p in images], 'correction':correction,
        'format_repair':REPAIR_VERSION if correction else None})
    root = Path(state.get('sample_preparation_dir') or state['output_dir'])/directory
    if (root/'identity.json').exists():
        read(root/'identity.json', identity)
    else:
        if root.exists() and any(root.iterdir()):
            raise ValueError('Editorial request identity missing from existing history')
        save(root/'identity.json', {'input_digest':identity, 'prompt':prompt, 'schema':schema})
    guard = paths = original = plan = None
    original_prompt = prompt
    agent = None
    for index in range(2 if correction else 1):
        stopped(state)
        if index:
            scope = Path(state.get('sample_preparation_dir') or state['output_dir'])
            repair_identity = digest({'version':VERSION,'paper':state.get('paper_foundation_digest'),
                                      'sample':context.get('sample_id')})
            charge = {'request':identity, 'prompt_digest':digest(prompt)}
            path = scope/'editorial_format_correction.json'
            if path.exists():
                if read(path, repair_identity).get('charge') != charge:
                    raise EditorialOutputError('Shared editorial format correction exhausted')
                if not (root/'request_01.json').exists():
                    raise ValueError('Format repair charged but request missing')
            else:
                save(path, {'input_digest':repair_identity,'charge':charge})
        charged, returned = root/f'request_{index:02d}.json', root/f'response_{index:02d}.json'
        key = digest(prompt)
        if returned.exists() and not charged.exists():
            raise ValueError('Editorial response has no durable charge')
        if charged.exists():
            if read(charged, identity)['prompt_digest'] != key:
                raise ValueError('Editorial charged prompt changed')
            if not returned.exists():
                raise ValueError('Editorial request charged but response missing; refusing resubmission')
            content = read(returned, identity)['content']
        else:
            save(charged, {'input_digest':identity, 'prompt_digest':key})
            agent = agent or LangGraphAgent('Compose and evaluate academic poster material from the supplied paper.',
                                           config, state, policy)
            message = prompt
            if images:
                message = json.dumps([{'type':'text','text':prompt}, *[
                    {'type':'image_url','image_url':{'url':'data:image/png;base64,'+
                        base64.b64encode(Path(p).read_bytes()).decode('ascii')}} for p in images]])
            agent.reset()
            original_model = getattr(agent, 'model', None)
            bound = isinstance(original_model, ChatOpenAI) and bool(getattr(agent, 'request_policy', None))
            if bound:
                agent.model = original_model.bind(response_format={'type':'json_schema','json_schema':{
                    'name':'editorial_response','strict':True,
                    'schema':wire_schema(plan['schema'] if index else schema, config.provider)}})
            try:
                response = agent.step(message)
            except BaseException as exc:
                save(root/f'failure_{index:02d}.json', {'input_digest':identity,'error_type':type(exc).__name__})
                raise
            finally:
                if bound:
                    agent.model = original_model
            content = response.content
            save(returned, {'input_digest':identity,'content':content,'input_tokens':response.input_tokens,
                            'output_tokens':response.output_tokens})
            getattr(state['tokens'], 'add_vision' if images else 'add_text')(response.input_tokens,response.output_tokens)
        value = None
        try:
            try:
                value = (parse_response or extract_json)(content)
            except EditorialStructureError:
                raise
            except ValueError as exc:
                raise EditorialStructureError("Response is not parseable JSON", [()]) from exc
            if index:
                value = apply_repair(original,value,plan)
            if pre_validator:
                pre_validator(value)
            errors = list(Draft202012Validator(schema).iter_errors(value))
            if errors:
                # Exceeding the family capacity is a content failure. A new
                # schema bound must not turn it into a whole-modules rewrite.
                if kind == 'editorial_curator':
                    for error in errors:
                        if error.validator == 'maxItems' and tuple(error.absolute_path) == ('modules',):
                            raise EditorialOutputError(f'Editorial module count must be in 1..{error.validator_value}')
                paths = []
                for error in errors:
                    path = tuple(error.absolute_path)
                    # Correct the selection array, so a nonexistent asset can be
                    # removed rather than forcing a replacement for one item.
                    if (kind == 'editorial_curator' and len(path) >= 3
                            and path[0] == 'modules' and isinstance(path[1], int)
                            and path[2] == 'visual_ids'):
                        paths.append(path[:3])
                        continue
                    if error.validator == 'required' and isinstance(error.instance, dict):
                        paths.extend(path+(k,) for k in error.validator_value if k not in error.instance)
                    elif error.validator == 'additionalProperties' and isinstance(error.instance, dict):
                        paths.extend(path+(k,) for k in error.instance if k not in error.schema.get('properties', {}))
                    else:
                        paths.append(path)
                raise EditorialStructureError('; '.join(e.message for e in errors), paths)
            if guard is not None and masked(value, paths) != guard:
                raise EditorialOutputError('Format repair changed valid editorial content')
            if validator: validator(value)
        except EditorialPlanningError as exc:
            # Preserve the rejected full plan, never accept it or turn it into
            # a whole-array format patch. Only the planner owns its adjustment.
            record = {'input_digest': identity, 'draft': exc.draft, 'feedback': exc.feedback}
            location = root/f'planning_rejection_{index:02d}.json'
            if location.exists():
                if read(location, identity) != record:
                    raise ValueError('Editorial planning rejection changed')
            else:
                save(location, record)
            save(root/f'invalid_{index:02d}.json', {'input_digest':identity,'reason':str(exc)})
            raise
        except (json.JSONDecodeError, EditorialStructureError) as exc:
            save(root/f'invalid_{index:02d}.json', {'input_digest':identity,'reason':str(exc)})
            if index or not correction:
                raise EditorialOutputError('Invalid editorial response after finite format allowance') from exc
            paths = exc.paths if isinstance(exc, EditorialStructureError) else [()]
            original = deepcopy(value)
            guard = masked(value, paths)
            plan = repair_plan(original,schema,paths)
            record = {'input_digest':identity,'original_digest':digest(original),'plan':plan}
            location = root/'repair_plan.json'
            if location.exists():
                if read(location,identity) != record:
                    raise ValueError('Editorial field repair plan changed')
            else:
                if (root/'request_01.json').exists():
                    raise ValueError('Editorial field repair plan missing from charged history')
                save(location,record)
            repair_context = _curator_repair_context(payload,original) if kind == 'editorial_curator' else None
            prompt = repair_prompt(original_prompt,original,content,exc,plan,context=repair_context)
            continue
        save(root/'accepted.json', {'input_digest':identity,'value':value})
        return value
    raise EditorialOutputError('Editorial response unavailable')


def request(state, kind, payload, schema, *, directory, validator=None, images=(), correction=True, parse_response=None,
            pre_validator=None):
    import time
    started=time.perf_counter()
    try:
        from utils.src.logging_utils import progress_operation
        with progress_operation(kind):
            return _request(state,kind,payload,schema,directory=directory,validator=validator,images=images,
                            correction=correction,parse_response=parse_response,pre_validator=pre_validator)
    finally:
        if kind=='editorial_balancer' and state.get('timing_metrics') is not None:
            state['timing_metrics'].record_component('source_balancer',time.perf_counter()-started,
                (state.get('iteration_context') or {}).get('iteration',0))
