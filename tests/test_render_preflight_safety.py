from src.agents.layout_agent import LayoutAgent


def test_i8_section_title_measurement_reserves_wrapped_bold_height():
    metrics = LayoutAgent()._measure_section_title(
        "Eviction Prevention Challenge",
        10.0,
        {"styling_interfaces": {"font_sizes": {"section_title": 64}}},
    )
    assert metrics["renderer_safe_lines"] >= 2
    assert metrics["height"] > (2 * 64 / 72)
