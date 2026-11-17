"""Byte-exact prompt whitelist and the actual two outgoing evaluator requests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from critic_fixtures import content_reply, visual_reply, content_wire_reply, reference_wire_reply
from src.workflow.editorial_critic import make_critic
from src.workflow.poster_grouping import complete_score
from test_editorial_model_scoring import context

BASELINE = json.loads((Path(__file__).parent/'fixtures/discrete_scoring_prompt_baseline.json').read_text())


def restored(text, path):
    for change in reversed(BASELINE['changes']):
        if change['file'] != path:
            continue
        if change['operation'] == 'replace_once':
            assert text.count(change['new']) == 1
            text = text.replace(change['new'], change['old'], 1)
        else:
            inserted = change['text']+'\n\n'+change['anchor']
            assert text.count(inserted) == 1
            text = text.replace(inserted, change['anchor'], 1)
    return text


def test_all_43_prompts_preserve_every_byte_outside_approved_scoring_edits():
    paths = {str(p) for p in Path('config/prompts').glob('*.txt')}
    assert paths == set(BASELINE['sha256'])
    assert len(paths) == 43
    changed = []
    for path, expected in BASELINE['sha256'].items():
        data = Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            changed.append(path)
        original = restored(data.decode('utf-8'), path).encode('utf-8')
        assert hashlib.sha256(original).hexdigest() == expected, path
    assert set(changed) == {'config/prompts/editorial_content_critic.txt',
                           'config/prompts/editorial_visual_critic.txt'}


def test_actual_outgoing_requests_preserve_whole_templates_and_evidence(context, monkeypatch, tmp_path):
    import utils.langgraph_utils as language
    from src.critic.scoring import current_policy
    captures = []
    class OfflineAgent:
        def __init__(self, system, config, state, policy):
            assert system == 'Compose and evaluate academic poster material from the supplied paper.'
            self.policy, self.state = policy, state
        def reset(self):
            pass
        def step(self, message):
            is_visual = self.policy == 'critic_visual'
            parts = json.loads(message) if is_visual else None
            prompt = parts[0]['text'] if parts else message
            if parts:
                assert len(parts) == 2 and parts[1]['type'] == 'image_url'
                assert parts[1]['image_url']['url'].startswith('data:image/png;base64,')
            template, rest = prompt.split('\nINPUT:\n', 1)
            encoded, schema_text = rest.split('\nCOMPLETE OUTPUT JSON SCHEMA:\n', 1)
            payload, schema = json.loads(encoded), json.loads(schema_text)
            kind = 'editorial_visual_critic' if is_visual else 'editorial_content_critic'
            path = 'config/prompts/'+kind+'.txt'
            assert template == Path(path).read_text()
            assert hashlib.sha256(restored(template, path).encode()).hexdigest() == BASELINE['sha256'][path]
            assert schema['$comment'] == 'scoring_policy_sha256:'+current_policy()['digest']
            assert 'high_score_threshold' not in payload and 'scoring_policy' not in payload
            assert payload['final_poster'] == context.state['editorial_candidate']
            assert payload['renderer_visible_text'] and payload['actual_geometry']
            if is_visual:
                assert payload['content_dependencies'] == content['content_dependencies']
                assert 'assessments' not in payload
                raw = reference_wire_reply(visual_reply(payload['final_poster']['modules']), self.state)
            else:
                assert payload['paper']['original_text'] == context.state['raw_text']
                raw = content_wire_reply(content, self.state)
            captures.append((kind, prompt, schema))
            return SimpleNamespace(content=json.dumps(raw), input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', OfflineAgent)
    content = content_reply(context.state['editorial_candidate']['modules'])
    make_critic(context.config)(context.state)
    assert complete_score(context.state['critic_report'])
    assert [kind for kind, _, _ in captures] == ['editorial_content_critic', 'editorial_visual_critic']
    for kind, prompt, schema in captures:
        directory = 'final_visual' if kind.endswith('visual_critic') else 'final_content'
        receipt = Path(context.state.get('sample_preparation_dir') or context.state['output_dir'])/'editorial'/directory/'identity.json'
        journal = json.loads(receipt.read_text())['payload']
        assert journal['prompt'] == prompt and journal['schema'] == schema
    # Both calls are durably cached; a repeated evaluation does not request again.
    make_critic(context.config)(context.state)
    assert len(captures) == 2
