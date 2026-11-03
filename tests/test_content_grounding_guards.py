from src.agents.content_optimizer import GroundedContentOptimizer
from src.layout.capacity_repair import CapacityActionPlanner


def test_supplemental_evidence_requires_new_verbatim_source_excerpt(tmp_path):
    optimizer = GroundedContentOptimizer()
    state = {
        "section_chunks": [{
            "section_id": "source-results",
            "section_name": "Results",
            "section_type": "results",
            "chunk_index": 0,
            "content": "Existing result sentence. Unique additional source detail.",
        }],
        "evidence_bank": {"version": 1, "items": [{
            "evidence_id": "e1",
            "source_excerpt": "Existing result sentence.",
            "source": {"section_id": "source-results"},
        }]},
        "supplemental_evidence_bank": {"schema_version": 1, "items": []},
        "narrative_plan": {"sections": [{
            "section_id": "results", "evidence_ids": ["e1"]
        }]},
        "iteration_context": {"iteration": 3},
    }
    board = {"spatial_content_plan": {"sections": [{
        "section_id": "results", "text_content": ["Existing result."],
    }]}}

    optimizer._model_json = lambda *_args, **_kwargs: {"evidence": [{
        "claim": "Duplicate",
        "source_excerpt": "Existing result sentence.",
        "source_chunk_index": 0,
    }]}
    duplicate = optimizer._extract_supplemental_evidence(
        state, "results", board, 0
    )
    assert duplicate is None

    optimizer._model_json = lambda *_args, **_kwargs: {"evidence": [{
        "claim": "A new grounded detail",
        "source_excerpt": "Unique additional source detail.",
        "source_chunk_index": 0,
        "confidence": "not-a-number",
    }]}
    extracted = optimizer._extract_supplemental_evidence(
        state, "results", board, 0
    )
    assert extracted["source_excerpt"] == "Unique additional source detail."
    assert extracted["source_excerpt_verified"] is True
    assert extracted["confidence"] == 0.5


def test_supplemental_evidence_search_can_reach_later_source_chunk():
    optimizer = GroundedContentOptimizer()
    state = {
        "section_chunks": [
            {"section_id": f"s{index}", "chunk_index": index,
             "content": f"Earlier detail {index}."}
            for index in range(2)
        ] + [{"section_id": "s2", "chunk_index": 2,
              "content": "Later unique scientific result."}],
        "evidence_bank": {"items": [{
            "evidence_id": "e1", "source_excerpt": "Earlier detail 0.",
            "source": {"section_id": "s0"},
        }]},
        "supplemental_evidence_bank": {"schema_version": 1, "items": []},
        "narrative_plan": {"sections": [{
            "section_id": "results", "evidence_ids": ["e1"],
        }]},
        "iteration_context": {"iteration": 5},
    }
    board = {"spatial_content_plan": {"sections": [{
        "section_id": "results", "section_title": "Results",
        "text_content": ["An earlier claim"],
    }]}}
    optimizer._model_json = lambda *_args: {"evidence": [{
        "claim": "A later result", "source_chunk_index": 2,
        "source_excerpt": "Later unique scientific result.",
    }]}

    result = optimizer._extract_supplemental_evidence(
        state, "results", board, 0
    )
    assert result["source"]["chunk_index"] == 2
    assert result["source_excerpt"] == "Later unique scientific result."


def test_underfilled_section_can_request_strict_source_search():
    state = {
        "verified_claims": {"claims": [{
            "claim_id": "c1",
            "text": "Existing result",
            "evidence_ids": ["e1"],
        }]},
        "story_board": {"spatial_content_plan": {"sections": [{
            "section_id": "results",
            "claim_ids": ["c1"],
            "text_content": ["Existing result"],
        }]}},
        "narrative_plan": {"sections": [{
            "section_id": "results", "evidence_ids": ["e1"]
        }]},
        "section_chunks": [{"section_id": "source-results", "content": "More text"}],
        "section_fit_analysis": {
            "ideal_band": [0.95, 1.0],
            "sections": {"results": {"utilization": 0.8, "column": "left"}},
        },
    }

    actions = CapacityActionPlanner.plan(state, state['story_board'], {
        'status': 'feasible', 'zone_utilization': {'z': .8},
        'selected_layout_spec': {'zones': [{'zone_id': 'z', 'section_ids': ['results']}]},
    }, round_index=1, maximum_actions=1)
    assert len(actions) == 1
    assert actions[0]['operation'] == 'add_claim_from_evidence'
    assert actions[0]['section_id'] == 'results'


def test_optimizer_rejects_cross_root_variant_substitution(tmp_path, monkeypatch):
    board = {"spatial_content_plan": {"sections": [{
        "section_id": "results", "claim_ids": ["c1"]
    }]}}
    claims = {
        "c1": {"claim_id": "c1", "text": "One"},
        "v2": {
            "claim_id": "v2",
            "root_claim_id": "c2",
            "text": "Unrelated variant",
            "verified": True,
        },
    }
    state = {'output_dir': str(tmp_path), 'story_board': board,
             'verified_claims': {'claims': [claims['c1']]},
             'verified_content_bank': {'claims': [claims['v2']]},
             'errors': []}
    optimizer = GroundedContentOptimizer()
    monkeypatch.setattr(optimizer, '_model_json', lambda *a: (_ for _ in ()).throw(AssertionError('No model call')))
    result = optimizer(state, board_override=board, actions_override=
        [{
            "operation": "use_claim_variant",
            "section_id": "results",
            "claim_id": "c1",
            "variant_id": "v2",
        }],
        save=False)
    assert result['story_board']['spatial_content_plan']['sections'][0]['claim_ids'] == ['c1']
    assert result['content_revision']['accepted_actions'] == []
