"""The one-shot classic path and loop family path must stay independent."""

import json
from copy import deepcopy

import pytest

from src.agents.layout_with_balancer import LayoutWithBalancerAgent
from src.agents.revision_planner import RevisionPlanner
from src.config.critic_config import load_critic_config
from src.layout.families import LayoutFamilyRegistry
from src.templates.library import TemplateDistiller, TemplateLibrary
from src.workflow.campaign import CampaignManager


def test_layout_optimizer_dispatches_classic_by_explicit_route(monkeypatch):
    agent = LayoutWithBalancerAgent.__new__(LayoutWithBalancerAgent)
    agent.name = "layout_with_balancer"
    calls = []

    def family_engine(state, family_id):
        calls.append(("family", family_id))
        return state

    def old_layout(_state, *, mode):
        calls.append(("classic", mode))
        raise RuntimeError("old route reached")

    monkeypatch.setattr(agent, "_run_family_constraint_engine", family_engine)
    agent.layout_agent = old_layout
    agent.balancer_agent = None

    loop_state = {
        "generation_route": "optimization_family",
        "iteration_context": {"layout_family": "classic_three_column"},
    }
    assert agent(loop_state) is loop_state
    assert calls == [("family", "classic_three_column")]

    calls.clear()
    standalone = {
        "generation_route": "standalone_classic",
        "iteration_context": {"layout_family": "top_hero_bottom_grid"},
    }
    agent(standalone)
    assert calls == [("classic", "initial")]
    assert any("old route reached" in item for item in standalone["errors"])


def test_classic_family_is_available_for_regular_loop_selection():
    registry = LayoutFamilyRegistry()
    compatible = registry.compatible_ids({"kind": "balanced"})
    assert "classic_three_column" in compatible
    assert len(compatible) > 1


def test_legacy_loop_classic_template_kept_but_strict_transfer_blocked(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    template = {
        "family": "classic_three_column",
        "source_mode": "explore",
        "zone_topology": {
            "family_id": "classic_three_column",
            "primary_anchor_zone": None,
            "zones": [dict(zone) for zone in
                      LayoutFamilyRegistry().get("classic_three_column").zones],
        },
    }
    assert library._topology_block_reason(template) == (
        "legacy_classic_geometry_unverified"
    )
    template["source_layout_engine_schema_version"] = 3
    assert library._topology_block_reason(template) is None


def test_standalone_classic_cannot_be_distilled_into_loop_knowledge():
    with pytest.raises(ValueError, match="Standalone classic"):
        TemplateDistiller().distill(
            {"generation_route": "standalone_classic"}, {}, {}
        )


def test_legacy_classic_lineage_is_not_restored_as_exact_parent(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    state = {
        "poster_name": "paper",
        "poster_width": 54,
        "poster_height": 36,
        "raw_text": "same paper",
        "layout_spec": {"family_id": "classic_three_column"},
        "critic_report": {
            "candidate_id": "candidate-1",
            "overall_score": 85,
            "rubric_version": config["rubric_version"],
        },
    }
    campaign = manager.open_campaign(state, resume_mode="new")
    manager.save_lineage_snapshot(
        campaign, "lineage-1", state, {}, accepted=True
    )
    assert manager.load_lineage_snapshot(
        campaign, "lineage-1", {}
    ) is not None
    path = campaign.path / "lineages" / "lineage-1" / (
        f"best_state_{config['rubric_version']}.json"
    )
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["layout_engine_schema_version"] = 2
    path.write_text(json.dumps(saved), encoding="utf-8")
    assert manager.load_lineage_snapshot(
        campaign, "lineage-1", {}
    ) is None


def test_zone_budget_feedback_is_relational_and_never_accepts_coordinates():
    spec = {
        "family_id": "asymmetric_two_column",
        "zones": [{"zone_id": "narrative_rail", "section_ids": ["intro"]}],
        "reading_order": ["intro"],
    }
    board = {"spatial_content_plan": {"sections": [
        {"section_id": "intro", "claim_ids": ["claim-1"]}
    ]}}
    revised, accepted = RevisionPlanner.apply_layout_operations(
        spec, board, [
            {"operation": "adjust_zone_budget", "zone_id": "narrative_rail",
             "direction": "shrink"},
            {"operation": "adjust_zone_budget", "zone_id": "narrative_rail",
             "direction": "expand", "width": 0.5},
        ]
    )
    assert revised == spec
    assert accepted == [{
        "operation": "adjust_zone_budget",
        "zone_id": "narrative_rail",
        "direction": "shrink",
    }]
    constraints = RevisionPlanner._build_layout_revision_constraints(
        revised, board, accepted
    )
    assert constraints["zone_budget_preferences"] == [{
        "zone_id": "narrative_rail", "direction": "shrink",
    }]


def test_loop_template_similarity_uses_real_zones_not_three_column_projection():
    state = {
        "generation_route": "optimization_family",
        "poster_width": 54,
        "poster_height": 36,
        "poster_name": "paper",
        "layout_spec": {
            "family_id": "asymmetric_two_column",
            "zones": [
                {"zone_id": "narrative_rail", "x": 0, "y": 0,
                 "width": 0.30, "height": 1, "section_ids": ["intro"]},
                {"zone_id": "evidence_field", "x": 0.33, "y": 0,
                 "width": 0.67, "height": 1, "section_ids": ["results"]},
            ],
        },
        "design_layout": [
            {"type": "section_container", "x": 1, "y": 7,
             "width": 10, "height": 10},
            {"type": "section_container", "x": 20, "y": 7,
             "width": 20, "height": 10},
        ],
    }
    distiller = TemplateDistiller()
    first = distiller.distill(state, {}, {})
    changed = deepcopy(state)
    changed["layout_spec"]["zones"][0]["width"] = 0.40
    changed["layout_spec"]["zones"][1]["x"] = 0.43
    changed["layout_spec"]["zones"][1]["width"] = 0.57
    second = distiller.distill(changed, {}, {})
    assert first["signature_schema_version"] == 2
    assert second["signature_schema_version"] == 2
    assert first["signature_vector"] != second["signature_vector"]
