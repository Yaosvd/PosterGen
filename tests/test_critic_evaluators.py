import zipfile
from pathlib import Path

from PIL import Image

from src.agents.revision_planner import RevisionPlanner
from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.evaluators import (
    ColumnBalanceEvaluator,
    GeometryEvaluator,
    GroundingEvaluator,
    RenderArtifactEvaluator,
    TypographyEvaluator,
)


def _config():
    config = load_critic_config()
    config["evaluators"]["visual"]["enabled"] = False
    return config


def _state(tmp_path: Path):
    pptx = tmp_path / "poster.pptx"
    with zipfile.ZipFile(pptx, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
    png = tmp_path / "poster.png"
    Image.new("RGB", (20, 10), "white").save(png)
    board = {
        "spatial_content_plan": {
            "sections": [{
                "section_id": "results",
                "column_assignment": "left",
                "vertical_priority": "top",
                "claim_ids": ["claim_1", "claim_2"],
                "text_content": ["Verified result one", "Verified result two"],
                "visual_assets": [],
            }]
        }
    }
    return {
        "poster_width": 54,
        "poster_height": 36,
        "styled_layout": [
            {"type": "title", "x": 1, "y": 1, "width": 30, "height": 3, "font_size": 100},
            {"type": "section_title", "id": "results_title", "x": 1, "y": 8, "width": 15, "height": 1, "font_size": 64},
            {"type": "text", "id": "results_text", "x": 1, "y": 10, "width": 15, "height": 5, "font_size": 44},
        ],
        "verified_claims": {"claims": [
            {"claim_id": "claim_1", "text": "Verified result one"},
            {"claim_id": "claim_2", "text": "Verified result two"},
        ]},
        "optimized_story_board": board,
        "story_board": board,
        "scientific_guard_violation": False,
        "final_column_analysis": {"columns": {
            "left": {"utilization_rate": 0.80},
            "middle": {"utilization_rate": 0.78},
            "right": {"utilization_rate": 0.76},
        }},
        "current_candidate": {
            "candidate_id": "candidate_1",
            "candidate_dir": str(tmp_path),
            "pptx_path": str(pptx),
            "png_path": str(png),
        },
    }


def test_deterministic_hard_gates_pass_grounded_candidate(tmp_path):
    context = CriticContext(state=_state(tmp_path), config=_config())
    results = [
        evaluator.evaluate(context)
        for evaluator in (
            RenderArtifactEvaluator(),
            GeometryEvaluator(),
            GroundingEvaluator(),
            TypographyEvaluator(),
            ColumnBalanceEvaluator(),
        )
    ]
    assert all(result.passed for result in results)


def test_grounding_rejects_rewrite_and_frozen_state_mutation(tmp_path):
    state = _state(tmp_path)
    state["optimized_story_board"]["spatial_content_plan"]["sections"][0]["text_content"][0] = "Invented"
    state["scientific_guard_violation"] = True
    result = GroundingEvaluator().evaluate(
        CriticContext(state=state, config=_config())
    )
    codes = {item["issue_id"] for item in result.issues}
    assert result.passed is False
    assert "GROUNDING-TEXT-claim_1" in codes
    assert "GROUNDING-FROZEN-STATE-MUTATED" in codes


def test_geometry_rejects_bounds_and_visible_overlap(tmp_path):
    state = _state(tmp_path)
    state["styled_layout"].extend([
        {"type": "text", "id": "outside", "x": 53, "y": 5, "width": 3, "height": 2, "font_size": 44},
        {"type": "visual", "id": "overlap", "x": 2, "y": 11, "width": 4, "height": 2},
    ])
    result = GeometryEvaluator().evaluate(
        CriticContext(state=state, config=_config())
    )
    codes = {item["issue_id"] for item in result.issues}
    assert result.passed is False
    assert any(code.startswith("GEOMETRY-BOUNDS") for code in codes)
    assert any(code.startswith("GEOMETRY-OVERLAP") for code in codes)


def test_revision_planner_uses_only_allow_list_and_restores_text():
    board = {"spatial_content_plan": {"sections": [
        {
            "section_id": "a", "column_assignment": "left", "vertical_priority": "top",
            "claim_ids": ["c1", "c2"], "text_content": ["wrong", "wrong"], "visual_assets": [],
        },
        {
            "section_id": "b", "column_assignment": "right", "vertical_priority": "bottom",
            "claim_ids": ["c3"], "text_content": ["wrong"], "visual_assets": [],
        },
    ]}}
    claims = {
        key: {"claim_id": key, "text": text}
        for key, text in {"c1": "One", "c2": "Two", "c3": "Three"}.items()
    }
    revised, accepted = RevisionPlanner().apply_operations(board, [
        {"operation": "move_section", "section_id": "a", "column": "middle"},
        {"operation": "remove_claim", "section_id": "a", "claim_id": "c2", "replacement_text": "Invented"},
        {"operation": "rewrite_claim", "claim_id": "c1", "replacement_text": "Invented"},
    ], claims)
    section = revised["spatial_content_plan"]["sections"][0]
    assert section["column_assignment"] == "left"
    assert section["claim_ids"] == ["c1"]
    assert section["text_content"] == ["One"]
    assert len(accepted) == 1
    assert all("replacement_text" not in operation for operation in accepted)
