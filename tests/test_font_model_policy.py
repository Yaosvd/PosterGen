"""Font temperature must reach the SDK without changing inherited request settings."""
from copy import deepcopy
import json

import httpx
import pytest

from src.agents.font_agent import FontAgent
from src.state.poster_state import ModelConfig, TokenUsage
from utils.agent_policy import load_agent_policies
import utils.langgraph_utils as language


@pytest.mark.parametrize('base_temperature,thinking,json_mode', [
    (0.2, None, True),
    (0.9, True, False),
    (0.9, False, True),
])
def test_font_role_temperature_reaches_sdk_without_other_policy_overrides(
        monkeypatch, base_temperature, thinking, json_mode):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'offline-font', 'object': 'chat.completion', 'created': 0,
            'model': 'glm5.3-flash',
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                'role': 'assistant', 'content': '{"section_keywords":{}}'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
        })

    monkeypatch.setenv('LOCAL_TEXT_BASE_URL', 'http://offline.invalid/v1')
    monkeypatch.setenv('LOCAL_TEXT_API_KEY', 'EMPTY')
    monkeypatch.setenv('LOCAL_TEXT_ENABLE_THINKING', 'true')
    base = ModelConfig('glm5.3-flash', 'local_text', temperature=base_temperature,
                       max_tokens=32768, enable_thinking=thinking, json_mode=json_mode)
    original = deepcopy(base)
    state = {'text_model': base, 'tokens': TokenUsage()}
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        class OfflineChatOpenAI(language.ChatOpenAI):
            def __init__(self, **kwargs):
                super().__init__(http_client=client, **kwargs)

        monkeypatch.setattr(language, 'ChatOpenAI', OfflineChatOpenAI)
        assert FontAgent()._identify_keywords({}, state) == {'section_keywords': {}}

    assert base == original
    assert len(requests) == 1
    body = requests[0]
    assert load_agent_policies()['font_agent']['temperature'] == 0.2
    assert body['temperature'] == 0.2
    assert body['max_completion_tokens'] == 32768
    assert body['chat_template_kwargs']['enable_thinking'] is (
        True if thinking is None else thinking)
    assert body.get('response_format') == ({'type': 'json_object'} if json_mode else None)
    assert state['tokens'].input_text == 10
    assert state['tokens'].output_text == 5
