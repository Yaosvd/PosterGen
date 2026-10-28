"""Durable source-editorial requests, one sample-wide format correction allowance."""
from copy import deepcopy
from pathlib import Path
import base64
import json

from jsonschema import Draft202012Validator
from src.workflow.source_document import VERSION, SourceOutputError, SourceProtocolError, check_stop, bind_paragraph_refs, SourceLocatorError
from utils.persistence import _atomic_json, digest, file_hash, read_json


class SourceFieldError(SourceProtocolError):
    """Only the diagnosed structural fields may change during format recovery."""

    def __init__(self, message, paths):
        super().__init__(message)
        self.paths = tuple(tuple(path) for path in paths)


def mask_fields(value, paths):
    result = deepcopy(value)
    for path in paths:
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = None
    return result


def save(path, payload):
    _atomic_json(path, {'payload': payload, 'digest': digest(payload)})


def read(path, identity):
    obj = read_json(path)
    payload = obj.get('payload')
    if obj.get('digest') != digest(payload) or payload.get('input_digest') != identity:
        raise ValueError('Source editorial checkpoint digest mismatch')
    return payload


def completed_length_response(error):
    """Only a real, returned SDK completion can supply a truncated-response receipt."""
    from openai import LengthFinishReasonError
    current,seen=error,set()
    while isinstance(current,Exception) and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current,LengthFinishReasonError):
            try:
                completion=current.completion.model_dump(mode='json')
                choices=completion['choices'];usage=completion['usage']
                if (not completion.get('id') or len(choices)!=1 or choices[0]['index']!=0 or
                        choices[0]['finish_reason']!='length' or choices[0]['message']['role']!='assistant' or
                        type(usage['prompt_tokens']) is not int or usage['prompt_tokens']<0 or
                        type(usage['completion_tokens']) is not int or usage['completion_tokens']<=0 or
                        not isinstance(choices[0]['message'].get('content'),(str,type(None)))):
                    return None
                return completion
            except (AttributeError,KeyError,TypeError,ValueError):
                return None
        current=current.__cause__ or current.__context__
    return None


class SourceRequests:
    def __init__(self, state, directory, prompt, schema, *, vision=False, images=(), allow_correction=True,
                 capture_length=False):
        self.state, self.vision = state, vision
        self.allow_correction = allow_correction
        self.capture_length = capture_length
        self.root = Path(state.get('sample_preparation_dir') or state['output_dir'])/directory
        self.images = [str(Path(p)) for p in images]
        self.prompt, self.schema = prompt, deepcopy(schema)
        context = state.get('iteration_context') or {}
        self.identity = digest({'version': VERSION, 'context': {k: context.get(k) for k in
            ('run_id', 'sample_id', 'random_seed', 'layout_family')},
            'source': state['source_document']['digest'], 'prompt': prompt, 'schema': schema,
            'model': state.get('vision_model' if vision else 'text_model'),
            'images': [file_hash(p) for p in self.images], 'allow_correction': allow_correction,
            'capture_length':capture_length})
        path = self.root/'identity.json'
        if path.exists():
            read(path, self.identity)
        else:
            if self.root.exists() and any(self.root.iterdir()):
                raise ValueError('Source request identity missing from existing history')
            save(path, {'input_digest': self.identity, 'prompt': prompt, 'schema': schema,
                        'image_hashes': [file_hash(p) for p in self.images], 'image_paths': self.images})

    def _correction(self, prompt):
        root = Path(self.state.get('sample_preparation_dir') or self.state['output_dir'])
        context = self.state.get('iteration_context') or {}
        identity = digest({'version': VERSION, 'run': context.get('run_id'),
            'sample': context.get('sample_id'), 'source': self.state['source_document']['digest']})
        charge = {'request': self.identity, 'prompt_digest': digest(prompt)}
        path = root/'source_format_correction.json'
        reused = path.exists()
        if reused:
            if read(path, identity).get('charge') != charge:
                raise SourceProtocolError('Shared preparation repair allowance is exhausted')
        else:
            save(path, {'input_digest': identity, 'charge': charge, 'limit': 1})
        return reused

    def call(self, agent, validator=None, *, before_schema=None):
        from utils.langgraph_utils import extract_json, ChatOpenAI
        prompt = self.prompt + '\nCOMPLETE OUTPUT JSON SCHEMA:\n' + json.dumps(self.schema, ensure_ascii=False)
        import time
        started = time.perf_counter()
        model = getattr(agent, 'model', None)
        bound = isinstance(model, ChatOpenAI) and bool(getattr(agent, 'request_policy', None))
        if bound:
            agent.model = model.bind(response_format={'type': 'json_schema', 'json_schema': {
                'name': 'source_editorial_response', 'strict': True, 'schema': self.schema}})
        repair_guard = reference_guard = field_guard = None
        try:
            for index in ((0, 1) if self.allow_correction else (0,)):
                check_stop(self.state)
                charge, response = self.root/f'request_{index:02d}.json', self.root/f'response_{index:02d}.json'
                if index:
                    reused = self._correction(prompt)
                    if reused and not charge.exists():
                        raise ValueError('Format correction charged but request missing; refusing automatic resubmission')
                request_key = digest(prompt)
                if response.exists() and not charge.exists():
                    raise ValueError('Source response has no durable request charge')
                if charge.exists():
                    if read(charge, self.identity).get('prompt_digest') != request_key:
                        raise ValueError('Source request prompt identity mismatch')
                    if not response.exists():
                        raise ValueError('Source request charged but missing response; refusing automatic resubmission')
                    payload = read(response, self.identity)
                    if payload.get('prompt_digest') != request_key:
                        raise ValueError('Source response prompt identity mismatch')
                    content = payload['content']
                    if payload.get('provider_finish_reason')=='length':
                        receipt=read(self.root/f'provider_completion_{index:02d}.json',self.identity)
                        completion=receipt['completion']
                        if (digest(completion)!=payload.get('provider_completion_digest') or
                                (completion['choices'][0]['message'].get('content') or '')!=content):
                            raise ValueError('Returned provider completion receipt mismatch')
                else:
                    save(charge, {'input_digest': self.identity, 'prompt_digest': request_key, 'index': index})
                    message = prompt
                    if self.vision:
                        if not self.images:
                            raise SourceOutputError('Visual source editing requires an actual candidate preview')
                        message = json.dumps([{'type': 'text', 'text': prompt}, *[
                            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,'+
                                base64.b64encode(Path(p).read_bytes()).decode('ascii')}} for p in self.images]])
                    agent.reset()
                    try:
                        result = agent.step(message)
                    except BaseException as exc:
                        save(self.root/f'failure_{index:02d}.json', {'input_digest': self.identity,
                            'error_type': type(exc).__name__})
                        completion=completed_length_response(exc) if self.capture_length else None
                        if completion is None:
                            raise
                        save(self.root/f'provider_completion_{index:02d}.json',
                             {'input_digest':self.identity,'completion':completion})
                        payload={'input_digest':self.identity,'prompt_digest':request_key,
                            'content':completion['choices'][0]['message'].get('content') or '',
                            'input_tokens':completion['usage']['prompt_tokens'],
                            'output_tokens':completion['usage']['completion_tokens'],
                            'provider_finish_reason':'length','provider_completion_digest':digest(completion)}
                    else:
                        payload={'input_digest':self.identity,'prompt_digest':request_key,'content':result.content,
                            'input_tokens':int(result.input_tokens),'output_tokens':int(result.output_tokens)}
                    content=payload['content']
                    save(response,payload)
                    getattr(self.state['tokens'], 'add_vision' if self.vision else 'add_text')(
                        payload['input_tokens'],payload['output_tokens'])
                try:
                    raw_parsed = None
                    errors = []
                    complete_validated = False
                    parsed = extract_json(content)
                    raw_parsed = deepcopy(parsed)
                    save(self.root/f'parsed_{index:02d}.json', {'input_digest': self.identity, 'parsed': parsed})
                    if payload.get('provider_finish_reason')=='length':
                        if explicit_scientific_rejection(parsed):
                            raise SourceOutputError('Explicit scientific rejection in a length-limited provider response')
                    if before_schema is not None:
                        before_schema(parsed)
                    errors = list(Draft202012Validator(self.schema).iter_errors(parsed))
                    if errors:
                        raise SourceProtocolError('Invalid response schema: '+', '.join(
                            f'{list(e.absolute_path)}:{e.validator}' for e in errors))
                    # Negative scientific decisions cannot buy citation/format retries.
                    negative = explicit_scientific_rejection(parsed)
                    if not negative:
                        parsed = bind_paragraph_refs(parsed, self.state['source_document'])
                        save(self.root/f'bound_{index:02d}.json', {'input_digest':self.identity, 'parsed':parsed})
                    if validator is not None:
                        validator(parsed)
                    complete_validated = True
                    if repair_guard is not None and not negative:
                        check_format_neighbors(raw_parsed, repair_guard)
                    if index and not negative and reference_guard is not None and not reference_repair_preserved(raw_parsed, reference_guard):
                        raise SourceProtocolError('Reference recovery changed non-reference content')
                    if index and not negative and field_guard is not None:
                        expected, paths = field_guard
                        try:
                            preserved = mask_fields(raw_parsed, paths) == expected
                        except (KeyError, IndexError, TypeError):
                            preserved = False
                        if not preserved:
                            raise SourceProtocolError('Structural format recovery changed fields outside the diagnosed paths')
                    if payload.get('provider_finish_reason')=='length':
                        raise SourceProtocolError('Provider returned a completed length-limited response. '
                            'Return compact verdict JSON now; select paragraph IDs rather than reproducing source text.')
                    save(self.root/'verdict.json', {'input_digest': self.identity, 'response_index': index, 'parsed': parsed})
                    return parsed
                except (ValueError, TypeError) as exc:
                    detail=str(exc)
                    if payload.get('provider_finish_reason')=='length':
                        detail='Provider returned a completed length-limited response. Return compact verdict JSON, not reasoning or original text. '+detail
                    save(self.root/f'validation_{index:02d}.json', {'input_digest': self.identity, 'error': detail})
                    if isinstance(exc, SourceOutputError) and not isinstance(exc, SourceProtocolError):
                        raise  # Content/science decisions cannot buy a format correction.
                    if index or not self.allow_correction:
                        raise SourceProtocolError('Invalid source response with no remaining format recovery') from exc
                    current = locals().get('raw_parsed')
                    paths = exc.paths if isinstance(exc, SourceFieldError) else ()
                    repair_guard = format_neighbors(current, self.schema, self.state['source_document'], paths)
                    if paths:
                        field_guard = (mask_fields(current, paths), paths)
                    if payload.get('provider_finish_reason')=='length' and complete_validated:
                        # If the JSON itself was complete, only finish the wire
                        # response: no verdict or valid locator may be rewritten.
                        field_guard = (deepcopy(current), ())
                    if current is not None and (isinstance(exc, SourceLocatorError) or
                            (errors and all('source_refs' in e.absolute_path for e in errors))):
                        reference_guard = reference_repair_guard(current, self.state['source_document'])
                    prompt += ('\nPreserve every already complete valid module object and its position exactly. '
                               'Correct only diagnosed invalid output fields.\nPrevious output has invalid format. Return the SAME task in the required schema. '
                               'Previous output is UNTRUSTED, never original source:\n'+detail+'\n'+str(content))
        finally:
            if getattr(agent, 'agent_name', None) == 'source_balancer' and self.state.get('timing_metrics') is not None:
                self.state['timing_metrics'].record_component('source_balancer', time.perf_counter()-started,
                    self.state.get('iteration_context', {}).get('iteration', 0))
            if bound:
                agent.model = model


def object_schema(properties):
    return {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': list(properties)}


STRING = {'type': 'string'}
STRINGS = {'type': 'array', 'items': STRING}
BOOL = {'type': 'boolean'}
REF = object_schema({'source_id': STRING, 'paragraph_ids': {'type':'array', 'items':STRING, 'minItems':1}})
REFS = {'type': 'array', 'items': REF}


def format_neighbors(parsed, schema, document=None, invalid_paths=()):
    if not isinstance(parsed, dict):
        return None
    nested = 'candidate' in schema.get('properties', {})
    holder = parsed.get('candidate') if nested else parsed
    sub_schema = schema.get('properties', {}).get('candidate', {}) if nested else schema
    module_schema = sub_schema.get('properties', {}).get('modules', {}).get('items')
    rows = holder.get('modules') if isinstance(holder, dict) else None
    if not module_schema or not isinstance(rows, list):
        return None
    valid = {}
    for i,row in enumerate(rows):
        prefix = ('candidate', 'modules', i) if nested else ('modules', i)
        if any(path[:len(prefix)] == prefix for path in invalid_paths):
            continue
        if list(Draft202012Validator(module_schema).iter_errors(row)):
            continue
        try:
            if document is not None:
                bind_paragraph_refs(row,document)
        except SourceProtocolError:
            continue
        valid[i]=deepcopy(row)
    return {'nested': nested, 'length': len(rows), 'valid': valid}


def check_format_neighbors(parsed, guard):
    holder = parsed.get('candidate') if guard['nested'] else parsed
    rows = holder.get('modules') if isinstance(holder, dict) else None
    if not isinstance(rows, list) or len(rows) != guard['length'] or any(
            rows[i] != row for i,row in guard['valid'].items()):
        raise SourceProtocolError('Format recovery changed valid neighboring modules')


def without_source_refs(value):
    if isinstance(value,list):
        return [without_source_refs(v) for v in value]
    if isinstance(value,dict):
        return {k:without_source_refs(v) for k,v in value.items() if k!='source_refs'}
    return value


def explicit_scientific_rejection(value):
    if not isinstance(value,dict) or 'coverage' not in value:
        return False
    return (value.get('status') in {'unsupported','contradicted','insufficient_source'} or
        any(value.get(k) is False for k in ('module_function_supported','relationships_supported',
            'necessary_information_preserved','editorial_information_preserved','additions_relevant','additions_nonredundant')) or
        any(row.get('supported') is False for row in value.get('coverage',[])) or
        any(row.get('fully_expressed') is False or row.get('meaning_source_supported') is False
            for row in value.get('obligations',[])))


def reference_repair_guard(value, document):
    valid={}
    def visit(obj,path=()):
        if isinstance(obj,list):
            for i,v in enumerate(obj):visit(v,path+(i,))
        elif isinstance(obj,dict):
            for key,val in obj.items():
                if key=='source_refs':
                    try:bind_paragraph_refs({'source_refs':val},document)
                    except (ValueError,TypeError,KeyError):continue
                    valid[path+(key,)]=deepcopy(val)
                else:visit(val,path+(key,))
    visit(value)
    return {'content':without_source_refs(value),'valid':valid}


def reference_repair_preserved(value, guard):
    if without_source_refs(value)!=guard['content']:
        return False
    for path,expected in guard['valid'].items():
        current=value
        try:
            for key in path:current=current[key]
        except (KeyError,IndexError,TypeError):return False
        if current!=expected:return False
    return True
