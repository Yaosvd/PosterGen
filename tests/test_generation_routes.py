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
from src.workflow.campaign_runner import _reconcile_lineage_artifacts


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
    zones = [dict(zone) for zone in
             LayoutFamilyRegistry().get("classic_three_column").zones]
    zones[0]["section_ids"] = ["s1"]
    state = {
        "poster_name": "paper",
        "poster_width": 54,
        "poster_height": 36,
        "raw_text": "same paper",
        "generation_route": "optimization_family",
        "layout_spec": {
            "schema_version": 3,
            "family_id": "classic_three_column",
            "geometry_fingerprint": "geometry-1",
            "zones": zones,
            "reading_order": ["s1"],
        },
        "optimized_story_board": {
            "spatial_content_plan": {"sections": [{"section_id": "s1"}]}
        },
        "layout_feasibility_report": {
            "status": "feasible",
            "family_id": "classic_three_column",
            "geometry_fingerprint": "geometry-1",
        },
        "layout_preflight_report": {"passed": True},
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
    assert saved["layout_origin"]["layout_spec_schema_version"] == 3
    assert saved["layout_origin"]["geometry_fingerprint"] == "geometry-1"
    inconsistent = deepcopy(saved)
    inconsistent["layout_origin"]["geometry_fingerprint"] = "other-geometry"
    path.write_text(json.dumps(inconsistent), encoding="utf-8")
    assert manager.lineage_parent_status(campaign, "lineage-1") == {
        "eligible": True, "snapshot_kind": "latest",
    }
    malformed = deepcopy(saved)
    malformed["fields"]["layout_spec"]["zones"][0]["section_ids"] = None
    path.write_text(json.dumps(malformed), encoding="utf-8")
    assert manager.lineage_parent_status(campaign, "lineage-1") == {
        "eligible": True, "snapshot_kind": "latest",
    }
    path.write_text(json.dumps(saved), encoding="utf-8")
    saved["layout_engine_schema_version"] = 3
    saved["fields"]["layout_spec"]["schema_version"] = 2
    saved["fields"]["layout_spec"]["geometry_fingerprint"] = ""
    saved["fields"]["layout_feasibility_report"] = None
    path.write_text(json.dumps(saved), encoding="utf-8")
    assert manager.load_lineage_snapshot(
        campaign, "lineage-1", {}
    ) is not None  # compatible latest snapshot remains available
    latest = campaign.path / "lineages" / "lineage-1" / "latest_state.json"
    latest.write_text(json.dumps(saved), encoding="utf-8")
    assert manager.load_lineage_snapshot(campaign, "lineage-1", {}) is None
    assert manager.lineage_parent_status(campaign, "lineage-1") == {
        "eligible": False, "reason": "legacy_classic_rebase_required",
    }


def test_corrupt_classic_parent_snapshot_is_skipped_safely(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    campaign = manager.open_campaign({
        "poster_name": "paper", "poster_width": 54,
        "poster_height": 36, "raw_text": "same paper",
    }, resume_mode="new")
    lineage_dir = campaign.path / "lineages" / "corrupt"
    lineage_dir.mkdir(parents=True)
    (lineage_dir / "latest_state.json").write_text(json.dumps({
        "fields": {
            "layout_spec": {
                "schema_version": 3,
                "family_id": "classic_three_column",
                "zones": ["invalid zone"],
            },
            "layout_feasibility_report": "bad report",
        },
    }), encoding="utf-8")
    assert manager.load_lineage_snapshot(campaign, "corrupt", {}) is None
    assert manager.lineage_parent_status(campaign, "corrupt")["eligible"] is False


def test_replay_does_not_promote_legacy_classic_source_version(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    campaign = manager.open_campaign({
        "poster_name": "paper", "poster_width": 54,
        "poster_height": 36, "raw_text": "same paper",
    }, resume_mode="new")
    attempt = campaign.path / "iterations" / "000008" / "attempts" / "attempt-old"
    attempt.mkdir(parents=True)
    report = {
        "candidate_id": "candidate-old", "overall_score": 83,
        "rubric_version": config["rubric_version"],
    }
    (attempt / "state_snapshot.json").write_text(json.dumps({
        "fields": {
            "layout_spec": {
                "schema_version": 2, "family_id": "classic_three_column",
                "geometry_fingerprint": "",
            },
            "layout_feasibility_report": None,
            "layout_preflight_report": {"passed": True},
        },
    }), encoding="utf-8")
    (attempt / "outcome.json").write_text(json.dumps({
        "portfolio_task": {"mode": "explore", "lineage_id": "legacy"},
        "accepted": False,
    }), encoding="utf-8")
    (attempt / "critic_report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    marker = attempt.parents[1] / "COMPLETED.json"
    marker.write_text(json.dumps({"attempt_id": "attempt-old"}), encoding="utf-8")
    marker_before = marker.read_bytes()
    portfolio = {"lineages": {"legacy": {}}}
    _reconcile_lineage_artifacts(manager, campaign, portfolio)
    _reconcile_lineage_artifacts(manager, campaign, portfolio)
    derived = json.loads((campaign.path / "lineages" / "legacy" /
                          "latest_state.json").read_text(encoding="utf-8"))
    assert derived["layout_engine_schema_version"] is None
    assert derived["layout_origin"]["provenance"] == "historical_inferred"
    assert manager.lineage_parent_status(campaign, "legacy")["reason"] == (
        "legacy_classic_rebase_required"
    )
    assert marker.read_bytes() == marker_before


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
