from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.section_fit import SectionFitEvaluator


def _state(height=29.25):
    return {
        "poster_width": 54,
        "poster_height": 36,
        "story_board": {"spatial_content_plan": {"sections": [{
            "section_id": "results",
            "column_assignment": "left",
            "importance_level": 2,
            "visual_assets": [],
        }]}},
        "styled_layout": [
            {
                "type": "section_container",
                "section_id": "results",
                "importance_level": 2,
                "x": 1,
                "y": 5,
                "width": 16,
                "height": height,
            },
            {"type": "text", "font_size": 44},
        ],
    }


def test_section_fit_accepts_ideal_95_to_100_percent_utilization():
    state = _state()
    result = SectionFitEvaluator().evaluate(
        CriticContext(state=state, config=load_critic_config())
    )

    metric = state["section_fit_analysis"]["sections"]["results"]
    assert metric["utilization"] == 0.975
    assert metric["in_ideal_band"] is True
    assert state["section_fit_analysis"]["all_sections_ideal"] is True
    assert result.passed is True


def test_section_fit_reports_underfilled_module():
    state = _state(height=20)
    result = SectionFitEvaluator().evaluate(
        CriticContext(state=state, config=load_critic_config())
    )

    assert any(
        item["issue_id"].startswith("SECTION-UNDERFILLED")
        for item in result.issues
    )
    assert state["section_fit_analysis"]["all_sections_ideal"] is False
