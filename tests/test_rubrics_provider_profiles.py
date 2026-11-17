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
