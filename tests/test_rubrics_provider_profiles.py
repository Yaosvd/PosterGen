"""Offline wire checks for reasoning models and the legacy compatible profile."""
import base64

import pytest

from src.rubrics.providers import OpenAICompatible, configuration, validate_configuration


@pytest.mark.parametrize('effort', [None, 'medium'])
def test_generation_profile_keeps_schema_and_images_without_unsupported_sampling(tmp_path, monkeypatch, effort):
    settings = {'model': 'fixture', 'max_tokens': 12000}
    if effort is not None:
        settings['reasoning_effort'] = effort
    adapter = OpenAICompatible(settings)
    schema = {'type': 'object', 'properties': {}, 'additionalProperties': False}
    poster = tmp_path / 'poster.png'
    poster.write_bytes(b'offline image payload')
    sent = []

    def post(endpoint, payload):
        sent.append((endpoint, payload))
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}

    monkeypatch.setattr(adapter, '_post', post)
    assert adapter.generate('unchanged prompt', schema, [poster])['value'] == '{}'
    endpoint, payload = sent[0]
    assert endpoint == 'chat/completions'
    assert payload['response_format']['json_schema'] == {
        'name': 'rubrics_response', 'strict': True, 'schema': schema}
    content = payload['messages'][0]['content']
    assert content[0] == {'type': 'text', 'text': 'unchanged prompt'}
    assert base64.b64decode(content[1]['image_url']['url'].split(',', 1)[1]) == poster.read_bytes()
    if effort is None:
        assert payload['temperature'] == 0 and payload['max_tokens'] == 12000
        assert 'reasoning_effort' not in payload and 'max_completion_tokens' not in payload
    else:
        assert payload['reasoning_effort'] == effort and payload['max_completion_tokens'] == 12000
        assert 'temperature' not in payload and 'max_tokens' not in payload


@pytest.mark.parametrize('effort', ['none', True, None, 'automatic'])
def test_invalid_reasoning_effort_rejected_before_requests(effort):
    config = configuration()
    config['external_models']['extractor']['reasoning_effort'] = effort
    with pytest.raises(ValueError, match='reasoning_effort'):
        validate_configuration(config)


def test_explicit_null_temperature_omits_only_sampling_parameter(monkeypatch):
    config = configuration()
    settings = config['external_models']['summarizer']
    settings.update(model='fixture', temperature=None)
    settings.pop('reasoning_effort', None)
    validate_configuration(config)
    sent = []
    adapter = OpenAICompatible(settings)
    monkeypatch.setattr(adapter, '_post', lambda endpoint, payload: sent.append(payload) or {
        'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    schema = {'type': 'object'}
    adapter.generate('original instructions', schema, [])
    payload = sent[0]
    assert 'temperature' not in payload and 'reasoning_effort' not in payload
    assert payload['max_tokens'] == settings['max_tokens']
    assert payload['messages'] == [{'role': 'user', 'content': 'original instructions'}]
    assert payload['response_format']['json_schema']['schema'] == schema


@pytest.mark.parametrize('temperature', [True, '0', -1, 3, float('nan'), float('inf')])
def test_invalid_external_temperature_is_rejected(temperature):
    config = configuration()
    config['external_models']['extractor']['temperature'] = temperature
    with pytest.raises(ValueError, match='temperature'):
        validate_configuration(config)


@pytest.mark.parametrize('text', ['{"answer":"same"}', '```json\n{"answer":"same"}\n```', '```\n{"answer":"same"}\n```'])
def test_complete_json_fence_is_losslessly_unwrapped(text):
    from src.rubrics.providers import parse_response
    assert parse_response(text)=={'answer':'same'}


@pytest.mark.parametrize('text', ['Explanation: {"a":1}', '```json\n{"a":1}\n```\nExtra prose',
                                '```json\n{"a":\n```', '{"decision":"conflict","decision":"novel"}'])
def test_parser_never_repairs_or_extracts_partial_json(text):
    from src.rubrics.providers import parse_response
    with pytest.raises(ValueError):parse_response(text)


def test_local_batch_roles_use_project_endpoints_and_single_send(tmp_path, monkeypatch):
    import json
    import httpx
    from src.rubrics import providers
    from src.rubrics.storage import read

    config = configuration()
    monkeypatch.setattr(providers, 'CONFIG_PATH', tmp_path / 'config/rubrics_iteration.json')
    prompts = tmp_path / 'config/prompts'
    prompts.mkdir(parents=True)
    for role in providers.ROLES:
        (prompts / ('rubrics_' + role + '.txt')).write_text('Original instructions')
    (tmp_path / '.env').write_text(
        'LOCAL_TEXT_BASE_URL=http://text.fixture/v1\n'
        'LOCAL_VISION_BASE_URL=http://vision.fixture/v1\n'
        'LOCAL_TEXT_API_KEY=text-secret\n'
        'LOCAL_VISION_API_KEY=vision-secret\n')
    monkeypatch.setenv('LOCAL_TEXT_BASE_URL', 'https://wrong.fixture/v1')
    monkeypatch.setenv('LOCAL_VISION_BASE_URL', 'https://wrong.fixture/v1')
    poster = tmp_path / 'poster.png'
    poster.write_bytes(b'original poster')
    requests = []

    def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        visual = request.url.host == 'vision.fixture'
        assert request.url.host in {'vision.fixture', 'text.fixture'}
        assert request.headers['authorization'] == ('Bearer vision-secret' if visual else 'Bearer text-secret')
        assert payload['model'] == 'glm5.3-flash'
        assert payload['temperature'] == 0 and payload['max_tokens'] == 12000
        assert payload['chat_template_kwargs'] == {'enable_thinking': False, 'reasoning_effort': 'low'}
        assert 'reasoning_effort' not in payload and 'max_completion_tokens' not in payload
        assert payload['response_format']['json_schema']['strict'] is True
        content = payload['messages'][0]['content']
        if visual:
            assert base64.b64decode(content[1]['image_url']['url'].split(',', 1)[1]) == poster.read_bytes()
        else:
            assert isinstance(content, str)
        return httpx.Response(200, json={
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]})

    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))
    models = providers.ExternalModels(config)
    models.check()
    schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}
    for role in sorted(providers.ROLES):
        root = tmp_path / 'receipts' / role
        for _ in range(2):
            assert models.generate(role, {'evidence': 'same'}, schema, root,
                                   images=(poster,) if role == 'extractor' else ()) == {'ok': True}
        settings = read(root / 'identity.json')['settings']
        assert settings['base_url'] == ('http://vision.fixture/v1' if role == 'extractor' else 'http://text.fixture/v1')
        assert 'secret' not in (root / 'identity.json').read_text()
    assert len(requests) == 3


def test_empty_project_local_endpoint_blocks_before_transport(tmp_path, monkeypatch):
    from src.rubrics import providers
    from src.rubrics.storage import WaitingForConfiguration

    config = configuration()
    monkeypatch.setattr(providers, 'CONFIG_PATH', tmp_path / 'config/rubrics_iteration.json')
    (tmp_path / '.env').write_text('LOCAL_VISION_BASE_URL=\n')
    monkeypatch.setenv('LOCAL_VISION_BASE_URL', 'https://wrong.fixture/v1')
    with pytest.raises(WaitingForConfiguration, match='LOCAL_VISION_BASE_URL'):
        providers.ExternalModels(config).check(('extractor',))
