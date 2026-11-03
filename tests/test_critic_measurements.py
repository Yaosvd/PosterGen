from PIL import Image

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.quality import (
    ColorQualityEvaluator,
    VisualAssetEvaluator,
)
from src.critic.section_fit import SectionFitEvaluator


def test_color_and_visual_asset_measurements_preserve_actual_contrast_and_aspect(tmp_path):
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

    color = ColorQualityEvaluator().evaluate(context)
    visual = VisualAssetEvaluator().evaluate(context)

    assert color.passed is True
    assert min(color.metadata["contrast_ratios"].values()) >= 4.5
    assert "scores" not in color.to_dict() and "submetrics" not in color.metadata
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
