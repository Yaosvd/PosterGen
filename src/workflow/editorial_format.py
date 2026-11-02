"""Closed field patches for the single shared editorial format repair."""
from copy import deepcopy
import json

from jsonschema import Draft202012Validator
from src.workflow.editorial_contract import EditorialOutputError

VERSION = 'editorial_field_repair_v1'


def _object(properties):
    return {'type':'object','properties':properties,'required':list(properties),
            'additionalProperties':False}


def repair_plan(original, schema, paths):
    """Resolve diagnosed paths to typed slots; valid siblings are never slots."""
    unique = []
    for path in paths:
        path = tuple(path)
        if any(type(k) not in (str,int) or isinstance(k,int) and k < 0 for k in path):
            raise EditorialOutputError('Invalid format repair path')
        if path not in unique:
            unique.append(path)
    unique = [p for p in unique if not any(len(q)<len(p) and p[:len(q)]==q for q in unique)]
    if not unique:
        raise EditorialOutputError('Format repair has no diagnosed fields')
    targets, fields = [], {}
    for path in unique:
        current, shape = original, schema
        action = 'replace'
        for i,key in enumerate(path):
            last = i == len(path)-1
            if isinstance(key,str) and isinstance(current,dict):
                child = shape.get('properties',{}).get(key)
                if child is None:
                    if not last or key not in current or shape.get('additionalProperties') is not False:
                        raise EditorialOutputError('Unresolvable format repair path')
                    action = 'remove'
                elif not last and key not in current:
                    raise EditorialOutputError('Format repair parent is missing')
                current, shape = current.get(key), child
            elif isinstance(key,int) and isinstance(current,list) and key < len(current):
                current, shape = current[key], shape.get('items')
            else:
                raise EditorialOutputError('Unresolvable format repair path')
            if action != 'remove' and not isinstance(shape,dict):
                raise EditorialOutputError('Format repair field lacks a schema')
        target = {'path':list(path),'action':action}
        if action == 'replace':
            target['field'] = f'field_{len(fields)}'
            fields[target['field']] = deepcopy(shape)
        targets.append(target)
    return {'version':VERSION,'targets':targets,
            'schema':_object({'repairs':_object(fields)})}


def apply_repair(original, wire, plan):
    errors = list(Draft202012Validator(plan['schema']).iter_errors(wire))
    if errors:
        raise EditorialOutputError('Invalid field repair response: '+'; '.join(e.message for e in errors))
    result = deepcopy(original)
    for target in plan['targets']:
        path = target['path']
        value = deepcopy(wire['repairs'][target['field']]) if target['action']=='replace' else None
        if not path:
            result = value
            continue
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        if target['action']=='remove':
            del parent[path[-1]]
        else:
            parent[path[-1]] = value
    return result


def repair_prompt(original_prompt, original, content, error, plan):
    prefix = (
        'FORMAT CORRECTION: Return ONLY the repairs object in the schema below. '
        'Each field_N replaces exactly its diagnosed JSON path in the saved FIRST response. '
        'The program preserves every other field, module, order, reason and prose. '
        'Do not return a module patch or a complete response. Do not add other fields. '
        'Fix structural/identifier errors only; do not rewrite scientific content. '
        'Removal targets are removed by the program and require no output slot.\n')
    if any(not t['path'] for t in plan['targets']):
        prefix += 'The entire response was unparseable or of the wrong type. The root slot uses the original task schema.\n'
        prefix += 'ORIGINAL TASK (context only):\n'+original_prompt+'\n'
    prefix += json.dumps({'first_response':original,'unparseable_response':content if original is None else None,
                          'diagnosed_fields':plan['targets'],'error':str(error)},ensure_ascii=False)
    return prefix+'\nCOMPLETE OUTPUT JSON SCHEMA:\n'+json.dumps(plan['schema'],ensure_ascii=False)
