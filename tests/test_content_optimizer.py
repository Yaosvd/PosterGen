from copy import deepcopy

from src.agents.content_optimizer import GroundedContentOptimizer


def _base_state(tmp_path):
    claims = [
        {
            "claim_id": "c1",
            "text": "A deliberately long verified statement about the method and result.",
            "evidence_ids": ["e1"],
            "verified": True,
        },
        {
            "claim_id": "c2",
            "text": "A second useful detail from the paper.",
            "evidence_ids": ["e2"],
            "verified": True,
        },
    ]
    return {
        "output_dir": str(tmp_path),
        "story_board": {"spatial_content_plan": {"sections": [{
            "section_id": "results",
            "claim_ids": ["c1"],
            "text_content": [claims[0]["text"]],
            "visual_assets": [],
        }]}},
        "verified_claims": {"claims": deepcopy(claims)},
        "verified_content_bank": {"schema_version": 1, "claims": []},
        "supplemental_evidence_bank": {"schema_version": 1, "items": []},
        "content_selection": {
            "schema_version": 1,
            "replacements": {},
            "active_supplemental_claim_ids": [],
            "disabled_claim_ids": [],
        },
        "evidence_bank": {"version": 1, "items": [
            {"evidence_id": "e1", "source_excerpt": "method and result"},
            {"evidence_id": "e2", "source_excerpt": "second useful detail"},
        ]},
        "narrative_plan": {"sections": [{
            "section_id": "results", "evidence_ids": ["e1", "e2"]
        }]},
        "iteration_context": {"iteration": 4},
        "current_candidate": {"candidate_id": "candidate-4"},
        "loop_config": {"content_optimization": {"max_poster_actions_per_iteration": 2}},
        "critic_config": {"content_optimization": {"max_poster_actions_per_iteration": 2}},
        "errors": [],
    }


def test_underfilled_section_adds_only_existing_verified_claim(tmp_path):
    state = _base_state(tmp_path)
    state["revision_plan"] = {"content_actions": [{
        "operation": "add_existing_claim",
        "section_id": "results",
        "claim_id": "c2",
        "reason": "use grounded available detail",
    }]}

    result = GroundedContentOptimizer()(state)

    section = result["story_board"]["spatial_content_plan"]["sections"][0]
    assert section["claim_ids"] == ["c1", "c2"]
    assert section["text_content"] == [
        state["verified_claims"]["claims"][0]["text"],
        state["verified_claims"]["claims"][1]["text"],
    ]
    assert result["verified_content_bank"]["claims"] == []


def test_overfull_section_uses_new_variant_only_after_verification(tmp_path):
    state = _base_state(tmp_path)
    original_claims = deepcopy(state["verified_claims"])
    state["revision_plan"] = {"content_actions": [{
        "operation": "create_compact_variant",
        "section_id": "results",
        "claim_id": "c1",
        "target_max_characters": 45,
        "reason": "reduce measured overflow",
    }]}
    optimizer = GroundedContentOptimizer()
    optimizer._model_json = lambda *_args, **_kwargs: {
        "candidates": [{
            "text": "A concise verified method result.",
            "evidence_ids": ["e1"],
        }]
    }
    optimizer._verify_candidate = lambda _state, candidate, _bank: (
        {**candidate, "verified": True, "repaired": False},
        {"summary": {"passed": 1}},
    )

    result = optimizer(state)

    section = result["story_board"]["spatial_content_plan"]["sections"][0]
    variant = result["verified_content_bank"]["claims"][0]
    assert variant["verified"] is True
    assert section["claim_ids"] == [variant["claim_id"]]
    assert section["text_content"] == [variant["text"]]
    assert result["content_selection"]["replacements"]["c1"] == variant["claim_id"]
    assert result["verified_claims"] == original_claims
