from pathlib import Path

from PIL import Image

from src.agents.revision_planner import RevisionPlanner
from src.agents.revision_operations import normalize_revision_operation
from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext, EvaluationResult
from src.critic.engine import PosterCritic
from src.critic.quality import (
    ColorQualityEvaluator,
    InformationNarrativeEvaluator,
    VisualAssetEvaluator,
)
from src.critic.section_fit import SectionFitEvaluator
from src.workflow.portfolio import PortfolioScheduler


def _result(name, scores, *, hard=False):
    return EvaluationResult(
        evaluator=name,
        version="test",
        hard_gate=hard,
        passed=True,
        scores=scores,
        issues=[],
        metadata={"submetrics": {f"{name}_detail": next(iter(scores.values()))}},
    )


def test_v4_report_uses_explicit_source_weights_and_nested_schema(tmp_path):
    config = load_critic_config()
    critic = PosterCritic(config=config, evaluators=[])
    results = [
        _result("render_artifacts", {"layout_integrity": 0}, hard=True),
        _result("grounding", {"scientific_integrity": 100}, hard=True),
        _result("information_narrative", {"content_quality": 80}),
        _result("content_adequacy", {"content_quality": 100}),
        _result("geometry", {"layout_integrity": 100}, hard=True),
        _result("column_balance", {"layout_integrity": 100, "visual_balance": 100}, hard=True),
        _result("section_fit", {"layout_integrity": 100, "visual_balance": 100}, hard=True),
        _result("layout_family", {"layout_integrity": 100, "visual_hierarchy": 100}, hard=True),
        _result("typography", {"readability": 100, "visual_hierarchy": 100, "aesthetics": 100}, hard=True),
        _result("color_quality", {"readability": 100, "aesthetics": 100}, hard=True),
        _result("visual_assets", {"aesthetics": 100}, hard=True),
        _result("visual", {"readability": 100, "visual_hierarchy": 100, "visual_balance": 100, "aesthetics": 100}, hard=True),
    ]
    state = {
        "current_candidate": {"candidate_id": "c1"},
        "iteration_context": {"iteration": 4, "strategy": "revise"},
        "section_fit_analysis": {"all_sections_ideal": True, "gaps_acceptable": True},
        "layout_spec": {"family_id": "asymmetric_two_column"},
    }

    report = critic._build_report(state, results)

    assert report["schema_version"] == 3
    assert report["rubric_version"] == "academic_poster_multifamily_v4"
    assert report["dimension_scores"]["content_quality"] == 85.0
    assert report["dimension_scores"]["layout_integrity"] == 100.0
    assert report["overall_score"] == 97.75
    assert report["poster_evaluation"]["archive_eligible"] is True
    assert report["task_evaluation"]["status"] == "not_applicable"
    assert report["template_eligible"] is True
    assert report["presentation_quality_score"] < report["overall_score"]
    config["templates"]["minimum_overall_score"] = 99
    lower_potential = critic._build_report(state, results)
    assert lower_potential["archive_eligible"] is True
    assert lower_potential["template_eligible"] is True
    assert lower_potential["high_potential_template"] is False
    layout_sources = {
        item["evaluator"]
        for item in report["poster_evaluation"]["dimension_source_contributions"]["layout_integrity"]
    }
    assert "render_artifacts" not in layout_sources

    missing_information = critic._build_report(
        state,
        [item for item in results if item.evaluator != "information_narrative"],
    )
    assert missing_information["dimension_scores"]["content_quality"] == 25.0
    assert missing_information["poster_evaluation"]["missing_score_sources"][
        "content_quality"
    ] == ["information_narrative"]
    assert missing_information["archive_eligible"] is False

    state["iteration_context"]["portfolio_mode"] = "validate"
    zone = {"zone_id": "z", "role": "support", "x": 0, "y": 0,
            "width": 1, "height": 1}
    state["validation_template_id"] = "T1"
    state["template_validation_topology"] = {
        "family_id": "asymmetric_two_column", "primary_anchor_zone": None,
        "zones": [dict(zone)],
    }
    state["layout_spec"]["zones"] = [dict(zone)]
    strict = critic._build_report(state, results)
    assert strict["task_evaluation"]["status"] == "strict_transfer_passed"
    assert strict["strict_template_transfer_passed"] is True
    state["layout_spec"]["zones"][0]["width"] = .5
    drifted = critic._build_report(state, results)
    assert drifted["task_evaluation"]["status"] == "strict_transfer_failed"
    assert drifted["archive_eligible"] is True


def test_information_color_and_visual_asset_submetrics_are_deterministic(tmp_path):
    config = load_critic_config()
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (800, 400), "navy").save(image_path)
    state = {
        "optimized_story_board": {"spatial_content_plan": {"sections": [{
            "section_id": "results",
            "importance_level": 1,
            "claim_ids": ["c1"],
            "text_content": ["The method improves accuracy."],
            "visual_assets": [{"visual_id": "figure_1"}],
        }]}},
        "verified_claims": {"claims": [{
            "claim_id": "c1",
            "text": "The method improves accuracy.",
            "evidence_ids": ["e1"],
        }]},
        "narrative_plan": {"sections": [{
            "section_id": "results",
            "importance": 1,
            "narrative_role": "results",
            "evidence_ids": ["e1"],
        }]},
        "evidence_bank": {"items": [{"evidence_id": "e1", "claim_type": "result"}]},
        "layout_spec": {
            "family_id": "top_hero_bottom_grid",
            "primary_anchor_zone": "hero",
            "reading_order": ["results"],
            "zones": [{"zone_id": "hero", "section_ids": ["results"]}],
        },
        "images": {"1": {"path": str(image_path)}},
        "tables": {},
        "styled_layout": [{
            "type": "visual", "visual_id": "figure_1", "width": 8, "height": 4,
        }],
        "color_scheme": {
            "theme": "#1E3A8A",
            "mono_light": "#F1F5F9",
            "mono_dark": "#172554",
            "text": "#000000",
            "text_on_theme": "#FFFFFF",
            "contrast": "#000000",
        },
        "color_provenance": {"source": "configured_fallback"},
    }
    context = CriticContext(state=state, config=config)

    information = InformationNarrativeEvaluator().evaluate(context)
    color = ColorQualityEvaluator().evaluate(context)
    visual = VisualAssetEvaluator().evaluate(context)

    assert set(information.metadata["submetrics"]) == {
        "information_layering", "information_coverage", "information_depth",
        "information_completeness", "narrative_structure", "narrative_flow",
        "narrative_conciseness",
    }
    assert information.metadata["semantic_model_completed"] is False
    assert color.passed is True
    assert color.metadata["submetrics"]["color_contrast"] == 100.0
    assert visual.passed is True
    assert visual.metadata["assets"]["figure_1"]["aspect_deviation"] == 0.0


def test_section_fit_uses_zone_height_for_nonclassic_family():
    config = load_critic_config()
    state = {
        "poster_width": 54,
        "poster_height": 36,
        "layout_spec": {
            "family_id": "top_hero_bottom_grid",
            "zones": [{"zone_id": "hero", "section_ids": ["results"]}],
        },
        "story_board": {"spatial_content_plan": {"sections": [{
            "section_id": "results", "importance_level": 2, "visual_assets": [],
        }]}},
        "styled_layout": [
            {
                "type": "section_container", "section_id": "results",
                "zone_id": "hero", "x": 1, "y": 5, "width": 20,
                "height": 9.75, "planned_zone_height": 10,
            },
            {"type": "text", "font_size": 44},
        ],
    }

    result = SectionFitEvaluator().evaluate(CriticContext(state=state, config=config))

    metric = state["section_fit_analysis"]["sections"]["results"]
    assert state["section_fit_analysis"]["region_kind"] == "zone"
    assert metric["layout_region"] == "hero"
    assert metric["utilization"] == 0.975
    assert result.passed is True


def test_revision_layout_protocol_rejects_columns_and_swaps_zones():
    assert normalize_revision_operation({
        "operation": "move_section",
        "section_id": "a",
        "column": "middle",
    }) is None
    swap = normalize_revision_operation({
        "operation": "swap_sections",
        "first_section_id": "a",
        "second_section_id": "b",
    })
    assert swap["operation"] == "swap_section_zones"
    spec = {
        "zones": [
            {"zone_id": "left", "section_ids": ["a"]},
            {"zone_id": "right", "section_ids": ["b"]},
        ],
        "reading_order": ["a", "b"],
    }
    board = {"spatial_content_plan": {"sections": [
        {"section_id": "a"}, {"section_id": "b"},
    ]}}
    revised, accepted = RevisionPlanner.apply_layout_operations(
        spec, board, [swap]
    )
    assert accepted[0]["operation"] == "swap_section_zones"
    assert revised["zones"][0]["section_ids"] == ["b"]
    assert revised["zones"][1]["section_ids"] == ["a"]


def test_planner_style_presets_reject_raw_values_and_visuals_are_allowlisted():
    overrides, accepted = RevisionPlanner.apply_style_operations({}, [
        {"operation": "repair_text_contrast", "reason": "low contrast"},
        {"operation": "normalize_typography_hierarchy", "font_size": 12},
    ])
    assert overrides == {"contrast_mode": "wcag_aa"}
    assert [item["operation"] for item in accepted] == ["repair_text_contrast"]
    assert RevisionPlanner._approved_visual_ids({
        "images": {"1": {}}, "tables": {"2": {}}
    }) == {"figure_1", "table_2"}

    board = {"spatial_content_plan": {"sections": [{
        "section_id": "results",
        "column_assignment": "left",
        "vertical_priority": "top",
        "claim_ids": ["c1"],
        "text_content": ["Verified"],
        "visual_assets": [{"visual_id": "figure_1"}],
    }]}}
    claims = {"c1": {"claim_id": "c1", "text": "Verified"}}
    revised, accepted = RevisionPlanner().apply_operations(
        board,
        [{
            "operation": "replace_visual",
            "visual_id": "figure_1",
            "replacement_visual_id": "figure_2",
        }],
        claims,
        approved_visual_ids={"figure_1", "figure_2"},
    )
    assert revised["spatial_content_plan"]["sections"][0]["visual_assets"][0]["visual_id"] == "figure_2"
    assert accepted[0]["operation"] == "replace_visual"


def test_portfolio_resets_score_comparison_when_rubric_changes():
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=1)
    old = {
        "schema_version": 1,
        "rubric_version": "old_rubric",
        "lineages": {
            "lin": {
                "lineage_id": "lin", "family_id": "classic_three_column",
                "status": "accepted_poster", "best_score": 99,
                "best_candidate_id": "old", "best_accepted_score": 99,
                "best_accepted_candidate_id": "old",
            }
        },
        "mode_counts": {}, "family_counts": {},
        "family_exploration_debt": {}, "recent_lineage_ids": [],
    }

    migrated = scheduler.normalize(old)
    lineage = migrated["lineages"]["lin"]

    assert migrated["rubric_version"] == config["rubric_version"]
    assert lineage["best_score"] == -1.0
    assert lineage["best_by_rubric"]["old_rubric"]["best_candidate_id"] == "old"
