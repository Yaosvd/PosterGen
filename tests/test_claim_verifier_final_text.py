"""The final published wording must pass semantic verification itself."""

import json
from types import SimpleNamespace

import src.agents.claim_verifier as verifier_module


def test_model_correction_is_rejected_when_final_text_is_not_supported(monkeypatch, tmp_path):
    responses = iter([
        {"supported": False, "corrected_text": "Method A reaches 90%.",
         "error_types": ["entity_mismatch"], "reason": "wrong method/value pairing"},
        {"supported": False, "corrected_text": "", "reason": "qualification missing"},
        {"supported": True, "corrected_text": "", "reason": "supported"},
    ])
    seen_prompts = []

    class FakeAgent:
        def __init__(self, *_args):
            pass

        def reset(self):
            pass

        def step(self, prompt):
            seen_prompts.append(prompt)
            return SimpleNamespace(
                content=json.dumps(next(responses)),
                input_tokens=1, output_tokens=1,
            )

    monkeypatch.setattr(verifier_module, "LangGraphAgent", FakeAgent)
    monkeypatch.setattr(verifier_module, "apply_agent_policy", lambda config, _name: config)
    state = {
        "text_model": object(),
        "tokens": SimpleNamespace(add_text=lambda *_args: None),
        "output_dir": str(tmp_path),
        "errors": [],
        "evidence_bank": {"items": [{
            "evidence_id": "e1", "source_excerpt": "Method A reaches 90%; Method B reaches 85%."
        }]},
        "poster_claims": {"claims": [
            {"claim_id": "c1", "text": "Method A reaches 85%.", "evidence_ids": ["e1"]},
            {"claim_id": "c2", "text": "Method A reaches 90%.", "evidence_ids": ["e1"]},
        ]},
    }

    result = verifier_module.ClaimVerifier()(state)

    assert result["errors"] == []
    assert len(seen_prompts) == 3
    assert result["verified_claims"]["claims"][0]["claim_id"] == "c2"
    assert len(result["verified_claims"]["claims"]) == 1
    assert result["verification_report"]["details"][0]["error_types"] == [
        "corrected_text_not_verified"
    ]
