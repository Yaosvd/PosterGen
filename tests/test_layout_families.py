from src.critic.base import CriticContext
from src.critic.layout_family import LayoutFamilyCriticEvaluator
from src.config.critic_config import load_critic_config
from src.layout.families import LayoutArchitect, LayoutFamilyRegistry


def _state():
    sections = [
        {
            "section_id": f"s{index}",
            "importance_level": 1 if index == 0 else 2,
            "claim_ids": [f"c{index}"],
            "visual_assets": [{"visual_id": "figure_1"}] if index == 0 else [],
        }
        for index in range(8)
    ]
    return {
        "story_board": {"spatial_content_plan": {"sections": sections}},
        "poster_width": 54,
        "poster_height": 36,
        "design_layout": [],
    }


def test_twelve_registered_families_build_bounded_nonoverlapping_specs():
    registry = LayoutFamilyRegistry()
    assert len(registry.ids()) == 12
    assert "classic_three_column" in registry.ids()
    architect = LayoutArchitect(registry)

    for family_id in registry.ids():
        spec = architect.build(_state(), family_id, random_seed=11)
        zones = spec["zones"]
        assigned = [
            section_id
            for zone in zones
            for section_id in zone["section_ids"]
        ]
        assert set(assigned) == {f"s{index}" for index in range(8)}
        assert len(assigned) == len(set(assigned))
        assert spec["reading_order"] == assigned
        for zone in zones:
            assert 0 <= zone["x"] < 1
            assert 0 <= zone["y"] < 1
            assert zone["width"] > 0
            assert zone["height"] > 0
            assert zone["x"] + zone["width"] <= 1.0001
            assert zone["y"] + zone["height"] <= 1.0001


def test_family_critic_rejects_raw_invalid_zone_geometry():
    state = _state()
    state["layout_spec"] = {
        "family_id": "top_hero_bottom_grid",
        "zones": [{
            "zone_id": "bad",
            "x": 0.9,
            "y": 0,
            "width": 0.2,
            "height": 1,
            "section_ids": ["s0"],
        }],
        "reading_order": ["s0"],
    }
    result = LayoutFamilyCriticEvaluator().evaluate(
        CriticContext(state=state, config=load_critic_config())
    )
    assert result.passed is False
    assert any(
        item["issue_id"] == "LAYOUT-FAMILY-ZONE-INVALID"
        for item in result.issues
    )
