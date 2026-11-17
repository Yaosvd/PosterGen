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
from utils.persistence import file_hash, read_json
from src.rubrics.storage import WaitingForConfiguration, request_once

CONFIG_PATH = Path(__file__).resolve().parents[2] / 'config' / 'rubrics_iteration.json'
ROLES = {'extractor', 'summarizer', 'reconciler'}


def _credential(settings):
    """Resolve only the configured credential, with project .env precedence."""
    name = settings.get('api_key_env')
    if not name:
        return None
    from dotenv import dotenv_values
    local = dotenv_values(CONFIG_PATH.parent.parent / '.env')
    key = local[name] if local.get(name) is not None else os.environ.get(name)
    if not key:
        raise WaitingForConfiguration(f'Missing credential environment variable: {name}')
    return key


def check_glm_endpoints():
    from dotenv import dotenv_values
    # Same effective file/environment precedence as the project's frozen batch route.
    env={**os.environ,**{k:v for k,v in dotenv_values(CONFIG_PATH.parent.parent/'.env').items() if v is not None}}
    for key in ('LOCAL_TEXT_BASE_URL','LOCAL_VISION_BASE_URL'):
        url=urlparse(env.get(key) or '')
        if url.scheme not in {'http','https'} or not url.netloc:
            raise WaitingForConfiguration('WAITING_GLM_CONFIGURATION: '+key)


def configuration(path=None):
    return validate_configuration(read_json(Path(path) if path else CONFIG_PATH))


def validate_configuration(data):
    if data.get('schema_version') != 2 or set(data.get('external_models', {})) != ROLES:
        raise ValueError('Expected iteration configuration v2 with local TF-IDF and three generation roles; legacy embedding configurations must be migrated explicitly')
    for settings in data['external_models'].values():
        if 'reasoning_effort' in settings and settings['reasoning_effort'] not in ('low','medium','high','xhigh','max'):
            raise ValueError('External reasoning_effort must be low, medium, high, xhigh or max')
        temperature = settings.get('temperature', 0)
        if temperature is not None and (type(temperature) not in (int, float) or
                not math.isfinite(temperature) or not 0 <= temperature <= 2):
            raise ValueError('External temperature must be null or a finite number within 0..2')
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
    if 'high_score_threshold' in mining:
        raise ValueError('G grouping threshold belongs to the frozen evaluator policy, not API/mining configuration')
    expected = {'clusters', 'max_rules', 'random_seed', 'tfidf', 'reconcile_batch_size', 'reconcile_max_chars'}
    if set(mining) != expected:
        raise ValueError('Unsupported mining configuration; embedding thresholds/batches are no longer used')
    for key in ('clusters', 'max_rules', 'reconcile_batch_size', 'reconcile_max_chars'):
        if type(mining[key]) is not int or mining[key] < 1:
            raise ValueError(f'Invalid mining setting: {key}')
    if type(mining['random_seed']) is not int or not 0 <= mining['random_seed'] < 2**32:
        raise ValueError('Invalid KMeans random seed')
    from src.rubrics.vectorization import validate_settings
    validate_settings(mining['tfidf'])
    return data


def image_block(path):
    return {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' +
            base64.b64encode(Path(path).read_bytes()).decode('ascii')}}


def parse_response(value):
    """Accept one complete JSON value, optionally inside one exact JSON fence.

    No prose extraction, repair, extra requests or changes to durable raw replies.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    fenced = re.fullmatch(r'```(?:json)?[ \t]*\n(.*)\n```', text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON response key: ' + key)
            result[key] = item
        return result
    return json.loads(text, object_pairs_hook=unique)


class OpenAICompatible:
    """Bounded HTTP requests with no implicit retry; journals own recovery."""
    def __init__(self, settings):
        self.settings = deepcopy(settings)

    def _post(self, endpoint, payload):
        import httpx
        key = _credential(self.settings)
        headers = {'Authorization': 'Bearer ' + key} if key else {}
        with httpx.Client(timeout=self.settings.get('timeout', 180), follow_redirects=False) as client:
            response = client.post(self.settings['base_url'].rstrip('/') + '/' + endpoint,
                                   headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def generate(self, prompt, schema, images):
        content = [{'type': 'text', 'text': prompt}, *[image_block(p) for p in images]] if images else prompt
        if 'reasoning_effort' in self.settings:
            # Reasoning profiles share the completion budget with internal reasoning
            # and do not accept the legacy temperature=0 sampling parameter.
            sampling = {'reasoning_effort': self.settings['reasoning_effort'],
                        'max_completion_tokens': self.settings['max_tokens']}
        else:
            sampling = {'max_tokens': self.settings['max_tokens']}
            # Explicit null supports gateways/models that reject temperature.
            temperature = self.settings.get('temperature', 0)
            if temperature is not None:
                sampling['temperature'] = temperature
        raw = self._post('chat/completions', {'model': self.settings['model'],
            'messages': [{'role': 'user', 'content': content}], **sampling,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'rubrics_response', 'strict': True, 'schema': schema}}})
        choices=raw.get('choices') if isinstance(raw,dict) else None
        choice=choices[0] if isinstance(choices,list) and choices and isinstance(choices[0],dict) else {}
        if choice.get('finish_reason') != 'stop':
            # Return the raw response to the journal before rejecting truncation.
            return {'raw': raw, 'value': None, 'finish_reason': choice.get('finish_reason')}
        message=choice.get('message')
        return {'raw': raw, 'value': message.get('content') if isinstance(message,dict) else None, 'finish_reason': 'stop'}


ADAPTERS = {'openai_compatible': OpenAICompatible}


def register_provider(name, factory):
    if name in ADAPTERS or not name or not callable(factory):
        raise ValueError('Provider name must be new and its factory callable')
    ADAPTERS[name] = factory


class ExternalModels:
    def __init__(self, config=None):
        self.config = deepcopy(validate_configuration(config) if config is not None else configuration())

    def check(self, roles=('extractor', 'summarizer', 'reconciler')):
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
            _credential(c)

    def generate(self, role, payload, schema, root, *, images=()):
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
        value = parse_response(response['value'])
        Draft202012Validator(schema).validate(value)
        return value
