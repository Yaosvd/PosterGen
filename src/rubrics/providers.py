"""Explicit provider adapters. An unconfigured role never falls back to another model."""
from copy import deepcopy
from pathlib import Path
import base64
import json
import math
import os
import re
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from utils.persistence import digest, file_hash, read_json
from src.rubrics.storage import WaitingForConfiguration, request_once

CONFIG_PATH = Path(__file__).resolve().parents[2] / 'config' / 'rubrics_iteration.json'
ROLES = {'extractor', 'embedding', 'summarizer', 'reconciler'}


def check_glm_endpoints():
    from dotenv import dotenv_values
    # Same effective file/environment precedence as the project's frozen batch route.
    env={**os.environ,**{k:v for k,v in dotenv_values(CONFIG_PATH.parent.parent/'.env').items() if v is not None}}
    for key in ('LOCAL_TEXT_BASE_URL','LOCAL_VISION_BASE_URL'):
        url=urlparse(env.get(key) or '')
        if url.scheme not in {'http','https'} or not url.netloc:
            raise WaitingForConfiguration('WAITING_GLM_CONFIGURATION: '+key)


def configuration(path=None):
    data = read_json(Path(path) if path else CONFIG_PATH)
    if data.get('schema_version') != 1 or set(data.get('external_models', {})) != ROLES:
        raise ValueError('Unsupported iteration model configuration')
    for role in ('review', 'revision'):
        settings = data[role]
        if settings['model'] != 'glm5.3-flash' or type(settings['max_tokens']) is not int or settings['max_tokens'] < 1:
            raise ValueError('Internal Critic and Actor must use the configured GLM contract')
        if type(settings['temperature']) not in (int,float) or not math.isfinite(settings['temperature']) or not 0<=settings['temperature']<=2:
            raise ValueError('Invalid internal role temperature')
    for name,value in data.get('limits',{}).items():
        if name not in {'max_rounds','max_postprocess_requests'} or (value is not None and (type(value) is not int or value<1)):
            raise ValueError('Invalid iteration budget')
    mining = data['mining']
    for key in ('clusters', 'max_rules', 'embedding_batch_size'):
        if type(mining[key]) is not int or mining[key] < 1:
            raise ValueError(f'Invalid mining setting: {key}')
    if not 0 < mining['similarity_threshold'] <= 1 or mining['high_score_threshold'] != 80:
        raise ValueError('Invalid similarity threshold or changed G grouping policy')
    return data


def image_block(path):
    return {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' +
            base64.b64encode(Path(path).read_bytes()).decode('ascii')}}


def validate_vectors(vectors, count):
    if not isinstance(vectors, list) or len(vectors) != count or not vectors:
        raise ValueError('Embedding response count mismatch')
    dim = len(vectors[0]) if isinstance(vectors[0], list) else 0
    if not dim or dim > 65536:
        raise ValueError('Invalid embedding dimension')
    for row in vectors:
        if (not isinstance(row, list) or len(row) != dim or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in row) or
                sum(x*x for x in row) == 0):
            raise ValueError('Embedding contains zero, nonfinite or inconsistent vectors')
    return vectors


class OpenAICompatible:
    """Bounded HTTP requests with no implicit retry; journals own recovery."""
    def __init__(self, settings):
        self.settings = deepcopy(settings)

    def _post(self, endpoint, payload):
        import httpx
        env = self.settings.get('api_key_env')
        key = os.environ.get(env) if env else None
        if env and not key:
            raise WaitingForConfiguration(f'Missing credential environment variable: {env}')
        headers = {'Authorization': 'Bearer ' + key} if key else {}
        with httpx.Client(timeout=self.settings.get('timeout', 180), follow_redirects=False) as client:
            response = client.post(self.settings['base_url'].rstrip('/') + '/' + endpoint,
                                   headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def generate(self, prompt, schema, images):
        content = [{'type': 'text', 'text': prompt}, *[image_block(p) for p in images]] if images else prompt
        raw = self._post('chat/completions', {'model': self.settings['model'],
            'messages': [{'role': 'user', 'content': content}], 'temperature': 0,
            'max_tokens': self.settings['max_tokens'],
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'rubrics_response', 'strict': True, 'schema': schema}}})
        choices=raw.get('choices') if isinstance(raw,dict) else None
        choice=choices[0] if isinstance(choices,list) and choices and isinstance(choices[0],dict) else {}
        if choice.get('finish_reason') != 'stop':
            # Return the raw response to the journal before rejecting truncation.
            return {'raw': raw, 'value': None, 'finish_reason': choice.get('finish_reason')}
        message=choice.get('message')
        return {'raw': raw, 'value': message.get('content') if isinstance(message,dict) else None, 'finish_reason': 'stop'}

    def embed(self, texts):
        raw = self._post('embeddings', {'model': self.settings['model'], 'input': texts})
        return raw


ADAPTERS = {'openai_compatible': OpenAICompatible}


def register_provider(name, factory):
    if name in ADAPTERS or not name or not callable(factory):
        raise ValueError('Provider name must be new and its factory callable')
    ADAPTERS[name] = factory


class ExternalModels:
    def __init__(self, config=None):
        self.config = deepcopy(config if config is not None else configuration())

    def check(self, roles=('extractor', 'embedding', 'summarizer')):
        for role in roles:
            if role not in ROLES:
                raise ValueError('Unknown external model role')
            c = self.config['external_models'][role]
            if not all(c.get(k) for k in ('provider', 'model', 'base_url')):
                raise WaitingForConfiguration('WAITING_MODEL_CONFIGURATION: ' + role)
            if c['provider'] not in ADAPTERS:
                raise ValueError('Unsupported provider: ' + str(c['provider']))
            url = urlparse(c['base_url'])
            if url.scheme not in {'http', 'https'} or not url.netloc or url.username or url.password or url.query or url.fragment:
                raise ValueError('Invalid provider endpoint (credentials belong in the environment)')
            if type(c.get('max_tokens')) is not int or c['max_tokens'] <= 0:
                raise ValueError('Invalid external output budget')
            if role == 'extractor' and not c.get('vision'):
                raise ValueError('Poster observation extraction requires an image-capable model')
            if type(c.get('timeout')) not in (int,float) or not 1<=c['timeout']<=1800:
                raise ValueError('External timeout must be within 1..1800 seconds')
            if c.get('api_key_env') and not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',c['api_key_env']):
                raise ValueError('Credential setting must name an environment variable')
            if c.get('api_key_env') and not os.environ.get(c['api_key_env']):
                raise WaitingForConfiguration('Missing credential environment variable: ' + c['api_key_env'])

    def generate(self, role, payload, schema, root, *, images=()):
        if role == 'embedding':
            raise ValueError('Embedding is not a generation role')
        self.check((role,))
        c = self.config['external_models'][role]
        if images and not c.get('vision'):
            raise ValueError('Provider has no declared image capability')
        template = CONFIG_PATH.parent / 'prompts' / ('rubrics_' + role + '.txt')
        prompt = template.read_text() + '\nINPUT:\n' + json.dumps(payload, ensure_ascii=False, allow_nan=False)
        prompt += '\nOUTPUT SCHEMA:\n' + json.dumps(schema, ensure_ascii=False)
        if len(prompt) > c.get('max_input_chars', 500000):
            raise ValueError('Input exceeds configured limit; refusing to truncate evidence or instructions')
        identity = {'role': role, 'settings': c, 'prompt': prompt, 'schema': schema,
                    'images': [file_hash(p) for p in images]}
        adapter = ADAPTERS[c['provider']](c)
        response = request_once(root, identity, lambda: adapter.generate(prompt, schema, images))
        if response.get('finish_reason') != 'stop':
            raise ValueError('External response incomplete; raw response retained')
        value = response['value']
        if isinstance(value, str):
            value = json.loads(value)
        Draft202012Validator(schema).validate(value)
        return value

    def embed(self, texts, root):
        if not texts or any(not isinstance(x, str) or not x.strip() for x in texts):
            raise ValueError('Embedding input must be nonempty text')
        self.check(('embedding',))
        c = self.config['external_models']['embedding']
        if sum(map(len,texts))>c.get('max_input_chars',500000):
            raise ValueError('Embedding input exceeds configured length limit')
        adapter = ADAPTERS[c['provider']](c)
        raw = request_once(root, {'role': 'embedding', 'settings': c, 'texts': texts}, lambda: adapter.embed(texts))
        rows = raw['data']
        if len(rows) != len(texts) or {r.get('index') for r in rows} != set(range(len(texts))):
            raise ValueError('Embedding response indices missing or duplicated')
        return validate_vectors([r['embedding'] for r in sorted(rows, key=lambda r: r['index'])], len(texts))
