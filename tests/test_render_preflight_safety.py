from src.agents.layout_agent import LayoutAgent
from src.critic.visual import VisualCriticEvaluator


def test_i8_section_title_measurement_reserves_wrapped_bold_height():
    metrics = LayoutAgent()._measure_section_title(
        "Eviction Prevention Challenge",
        10.0,
        {"styling_interfaces": {"font_sizes": {"section_title": 64}}},
    )
    assert metrics["renderer_safe_lines"] >= 2
    assert metrics["height"] > (2 * 64 / 72)


def test_visual_critic_removes_mismatched_section_from_location():
    state = {
        "layout_spec": {
            "zones": [
                {"zone_id": "left", "section_ids": ["poster_sec_1"]},
                {"zone_id": "right", "section_ids": ["poster_sec_5"]},
            ]
        },
        "styled_layout": [{"id": "poster_sec_1_text"}],
        "optimized_story_board": {
            "spatial_content_plan": {
                "sections": [
                    {
                        "section_id": "poster_sec_1",
                        "section_title": "Eviction Prevention Challenge",
                    },
                    {
                        "section_id": "poster_sec_5",
                        "section_title": "Conclusion",
                    },
                ]
            }
        },
    }
    location, evidence = VisualCriticEvaluator._validated_location(
        {
            "zone_id": "left",
            "section_id": "poster_sec_5",
            "element_id": "poster_sec_1_text",
        },
        state
    )
    assert location == {
        "zone_id": "left",
        "element_id": "poster_sec_1_text",
    }
    assert evidence["location_validation"] == "invalid identifiers removed"
    assert evidence["raw_location"]["section_id"] == "poster_sec_5"
