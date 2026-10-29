"""Digest-bound editorial requests with one shared, field-scoped format repair."""
from copy import deepcopy
from pathlib import Path
import base64
import json

from jsonschema import Draft202012Validator
from utils.persistence import _atomic_json, digest, read_json, file_hash
from src.workflow.editorial_contract import (VERSION, EditorialOutputError, EditorialStructureError, EditorialInterrupted)

STRING = {'type': 'string'}
STRINGS = {'type': 'array', 'items': STRING}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


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


def request(state, kind, payload, schema, *, directory, validator=None, images=(), correction=True):
    from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
    from utils.agent_policy import apply_agent_policy
    stopped(state)
    prompt = load_prompt('config/prompts/'+kind+'.txt')+'\nINPUT:\n'+json.dumps(payload, ensure_ascii=False)
    prompt += '\nCOMPLETE OUTPUT JSON SCHEMA:\n'+json.dumps(schema, ensure_ascii=False)
    context = state.get('iteration_context') or {}
    model_key = 'vision_model' if images else 'text_model'
    policy = {'editorial_curator':'source_curator', 'editorial_balancer':'source_balancer',
              'editorial_content_critic':'critic_content', 'editorial_visual_critic':'critic_visual',
              'editorial_palette':'color_agent'}.get(kind, 'parser')
    config = apply_agent_policy(state[model_key], policy)
    identity = digest({'version': VERSION, 'paper': state.get('paper_foundation_digest') or digest(state.get('raw_text')),
        'context': {k:context.get(k) for k in ('run_id','sample_id','random_seed','layout_family')},
        'prompt':prompt, 'model':config, 'images':[file_hash(p) for p in images], 'correction':correction})
    root = Path(state.get('sample_preparation_dir') or state['output_dir'])/directory
    if (root/'identity.json').exists():
        read(root/'identity.json', identity)
    else:
        if root.exists() and any(root.iterdir()):
            raise ValueError('Editorial request identity missing from existing history')
        save(root/'identity.json', {'input_digest':identity, 'prompt':prompt, 'schema':schema})
    guard = paths = None
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
            try:
                response = agent.step(message)
            except BaseException as exc:
                save(root/f'failure_{index:02d}.json', {'input_digest':identity,'error_type':type(exc).__name__})
                raise
            content = response.content
            save(returned, {'input_digest':identity,'content':content,'input_tokens':response.input_tokens,
                            'output_tokens':response.output_tokens})
            getattr(state['tokens'], 'add_vision' if images else 'add_text')(response.input_tokens,response.output_tokens)
        value = None
        try:
            try:
                value = extract_json(content)
            except ValueError as exc:
                raise EditorialStructureError("Response is not parseable JSON", [()]) from exc
            errors = list(Draft202012Validator(schema).iter_errors(value))
            if errors:
                paths = []
                for error in errors:
                    path = tuple(error.absolute_path)
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
        except (json.JSONDecodeError, EditorialStructureError) as exc:
            save(root/f'invalid_{index:02d}.json', {'input_digest':identity,'reason':str(exc)})
            if index or not correction:
                raise EditorialOutputError('Invalid editorial response after finite format allowance') from exc
            paths = exc.paths if isinstance(exc, EditorialStructureError) else [()]
            guard = masked(value, paths)
            prompt += '\nFORMAT CORRECTION: Change ONLY these diagnosed fields. Preserve every other field, prose, '
            prompt += 'module and order.\n'+json.dumps({'invalid':value,'paths':paths,'error':str(exc)},ensure_ascii=False)
            continue
        save(root/'accepted.json', {'input_digest':identity,'value':value})
        return value
    raise EditorialOutputError('Editorial response unavailable')
