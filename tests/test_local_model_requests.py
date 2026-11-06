"""Verify local request flags in serialized SDK bodies without network access."""
import json

import httpx
import pytest
from langchain_core.messages import HumanMessage

from src.state.poster_state import ModelConfig
from utils.agent_policy import apply_agent_policy
import utils.langgraph_utils as language


@pytest.fixture
def local_requests(monkeypatch):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'offline-completion', 'object': 'chat.completion', 'created': 0,
            'model': 'glm5.3-flash',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': '{"result":"ok"}'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
        })

    for prefix in ('LOCAL_TEXT', 'LOCAL_VISION'):
        monkeypatch.setenv(f'{prefix}_BASE_URL', 'http://offline.invalid/v1')
        monkeypatch.setenv(f'{prefix}_API_KEY', 'EMPTY')
        monkeypatch.delenv(f'{prefix}_ENABLE_THINKING', raising=False)
    constructor = language.ChatOpenAI
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(language, 'ChatOpenAI',
                            lambda **kwargs: constructor(http_client=client, **kwargs))
        yield requests


@pytest.mark.parametrize('role,provider,limit,structured', [
    ('critic_visual', 'local_vision', 12000, True),
    ('color_agent', 'local_vision', 8192, False),
    ('source_balancer', 'local_text', 12000, True),
])
def test_role_policy_reaches_json_and_structured_sdk_requests(
        monkeypatch, local_requests, role, provider, limit, structured):
    # The explicit role policy must override a conflicting global default.
    prefix = 'LOCAL_VISION' if provider == 'local_vision' else 'LOCAL_TEXT'
    monkeypatch.setenv(f'{prefix}_ENABLE_THINKING', 'true')
    config = apply_agent_policy(ModelConfig('glm5.3-flash', provider, max_tokens=32768), role)
    model = language.create_model(config)
    if structured:
        schema = {'title': 'OfflineResult', 'type': 'object',
                  'properties': {'result': {'type': 'string'}},
                  'required': ['result'], 'additionalProperties': False}
        model = model.with_structured_output(schema, method='json_schema', strict=True)
    else:
        model = model.bind(response_format={'type': 'json_object'})
    content = [{'type': 'text', 'text': 'Return a JSON result.'}]
    if provider == 'local_vision':
        content.append({'type': 'image_url',
                        'image_url': {'url': 'data:image/png;base64,AA=='}})
    model.invoke([HumanMessage(content=content)])
    assert len(local_requests) == 1
    body = local_requests[0]
    assert body['chat_template_kwargs']['enable_thinking'] is False
    assert body['max_completion_tokens'] == limit
    assert body['response_format']['type'] == ('json_schema' if structured else 'json_object')
    assert body['messages'][0]['content'] == content


@pytest.mark.parametrize('provider', ['local_text', 'local_vision'])
@pytest.mark.parametrize('explicit,environment,expected', [
    (None, None, False),
    (None, 'true', True),
    (True, 'false', True),
])
def test_provider_default_and_explicit_override_in_sdk_body(
        monkeypatch, local_requests, provider, explicit, environment, expected):
    prefix = 'LOCAL_VISION' if provider == 'local_vision' else 'LOCAL_TEXT'
    if environment is not None:
        monkeypatch.setenv(f'{prefix}_ENABLE_THINKING', environment)
    # Text and vision defaults must remain independent.
    other = 'LOCAL_TEXT' if provider == 'local_vision' else 'LOCAL_VISION'
    monkeypatch.setenv(f'{other}_ENABLE_THINKING', 'true')
    model = language.create_model(ModelConfig('glm5.3-flash', provider,
                                              enable_thinking=explicit))
    model.invoke('Return JSON.')
    assert local_requests[0]['chat_template_kwargs']['enable_thinking'] is expected
