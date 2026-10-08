import hashlib
import json
from copy import deepcopy
from pathlib import Path

from PIL import Image

from src.config.critic_config import load_critic_config
from src.layout.archetypes import LayoutArchetypeRegistry
from src.layout.feasibility import (
    fit_family_layout,
    generate_zone_variants,
    validate_compiled_layout,
)
from src.layout.families import (
    LAYOUT_ENGINE_SCHEMA_VERSION,
    LayoutFamilyRegistry,
    compile_layout,
    valid_family_topology,
)
from src.agents.layout_agent import LayoutAgent
from src.templates.library import LoopStorage
from src.workflow.campaign import CampaignManager


class _MeasuredAgent:
    poster_margin = 1.0
    title_height_fraction = 0.18
    layout_constants = {"body_render_reserve": 0.2}

    @staticmethod
    def _inter_section_spacing(_state):
        return 0.2

    @staticmethod
    def _calculate_precise_section_height(
        section, _width, _state, _available_height
    ):
        return (
            1.0
            + 0.6 * len(section.get("claim_ids") or [])
            + 2.0 * len(section.get("visual_assets") or [])
        )

    @staticmethod
    def _create_title_element(_state, _poster_width, title_height):
        return {
            "type": "title",
            "x": 1.0,
            "y": 1.0,
            "width": 30.0,
            "height": max(0.1, title_height - 1.0),
        }

    @staticmethod
    def _create_logo_elements(_state, _poster_width, _title_height):
        return []

    def _create_section_elements(
        self, section, x, y, width, state, available_height
    ):
        return [{
            "type": "text",
            "id": f"{section['section_id']}_text",
            "x": x,
            "y": y,
            "width": width,
            "height": self._calculate_precise_section_height(
                section, width, state, available_height
            ),
        }]


def _board():
    return {
        "spatial_content_plan": {
            "sections": [
                {
                    "section_id": f"s{index}",
                    "section_title": f"Section {index}",
                    "importance_level": 1 if index < 2 else 2,
                    "vertical_priority": "top" if index < 2 else "middle",
                    "claim_ids": [
                        f"c{index}_{claim}" for claim in range(4)
                    ],
                    "text_content": [
                        f"Grounded claim {index}-{claim}."
                        for claim in range(4)
                    ],
                    "visual_assets": (
                        [{"visual_id": "figure_1"}] if index == 0 else []
                    ),
                }
                for index in range(6)
            ]
        }
    }


def test_all_seed_families_generate_multiple_bounded_variants():
    registry = LayoutFamilyRegistry()
    for family in registry.all():
        variants = generate_zone_variants(
            family, random_seed=17, maximum=24
        )
        assert len(variants) >= 2, family.family_id
        assert len({
            item["geometry_fingerprint"] for item in variants
        }) == len(variants)
        for variant in variants:
            for zone in variant["zones"]:
                assert 0 <= zone["x"] < 1
                assert 0 <= zone["y"] < 1
                assert zone["x"] + zone["width"] <= 1.000001
                assert zone["y"] + zone["height"] <= 1.000001


def test_nonclassic_families_expose_auditable_topology_mutations():
    registry = LayoutFamilyRegistry()
    family = registry.get("four_column_modular")
    variants = generate_zone_variants(family, random_seed=17, maximum=24)
    changed = [
        item for item in variants
        if any(
            action in {"split_zone", "span_adjacent_zones"}
            for action in item["mutation_trace"]
        )
    ]
    assert changed
    assert any(
        len(item["zones"]) != len(family.zones) for item in changed
    )
    assert all(valid_family_topology(family, item["zones"]) for item in changed)
    classic = registry.get("classic_three_column")
    assert all(
        len(item["zones"]) == 3
        for item in generate_zone_variants(classic, random_seed=17)
    )


def test_capacity_fit_compiles_to_a_preflight_safe_candidate():
    agent = _MeasuredAgent()
    state = {
        "poster_width": 54,
        "poster_height": 36,
        "iteration_context": {
            "random_seed": 19,
            "layout_family": "top_hero_bottom_grid",
        },
        "images": {},
        "tables": {},
    }
    config = {
        "explore_layout": {
            "max_geometry_candidates_per_family": 4,
            "beam_width": 4,
            "diverse_top_k": 2,
            "minimum_sections": 5,
            "planning_target": 0.975,
            "maximum_utilization": 1.0,
        }
    }
    fitted, spec, report = fit_family_layout(
        agent,
        _board(),
        state,
        "top_hero_bottom_grid",
        config=config,
    )
    state["optimized_story_board"] = fitted
    layout = compile_layout(agent, fitted, state, spec)
    preflight = validate_compiled_layout(
        layout,
        spec,
        state,
        poster_margin=agent.poster_margin,
        title_height_fraction=agent.title_height_fraction,
    )

    assert report["status"] == "feasible"
    assert report["trial_count"] == 4
    assert report["feasible_count"] >= 1
    assert report["exact_feasible_count"] >= 1
    assert report["search_measurement"]["final_exact_compile_required"]
    assert set(report["zone_utilization"]) == {
        zone["zone_id"] for zone in spec["zones"]
    }
    state["layout_spec"] = spec
    state["optimized_story_board"] = fitted
    assert LayoutAgent._ensure_layout_spec(state, fitted) is spec
    assert len(
        fitted["spatial_content_plan"]["sections"]
    ) >= 5
    assert preflight["passed"] is True


def test_preflight_detects_canvas_and_zone_escape():
    spec = {
        "family_id": "asymmetric_two_column",
        "variant_id": "bad",
        "zones": [{
            "zone_id": "left",
            "x": 0.0,
            "y": 0.0,
            "width": 0.4,
            "height": 1.0,
            "section_ids": ["s1"],
        }],
    }
    state = {"poster_width": 54, "poster_height": 36}
    layout = [{
        "type": "section_container",
        "section_id": "s1",
        "zone_id": "left",
        "x": 1,
        "y": 8,
        "width": 30,
        "height": 40,
    }]
    result = validate_compiled_layout(
        layout, spec, state,
        poster_margin=1.0,
        title_height_fraction=0.18,
    )
    codes = {item["code"] for item in result["issues"]}
    assert result["passed"] is False
    assert "PREFLIGHT_POSTER_BOUNDS" in codes
    assert "PREFLIGHT_ZONE_BOUNDS" in codes


def test_runtime_archetype_requires_cross_paper_evidence(tmp_path):
    config = {
        "explore_layout": {
            "promote_archetype_min_distinct_papers": 2,
            "promote_archetype_min_accepted_posters": 3,
        }
    }
    registry = LayoutArchetypeRegistry(tmp_path, config)
    family = LayoutFamilyRegistry().get("asymmetric_two_column")
    spec = {
        "family_id": family.family_id,
        "primary_anchor_zone": "evidence_field",
        "zones": [dict(item) for item in family.zones],
    }
    profile = {"profile_key": "balanced"}

    first = registry.record_accepted(
        event_id="camp-a:1", paper_id="paper-a",
        paper_profile=profile, candidate_id="a1",
        layout_spec=spec, design_score=90,
    )
    replayed = registry.record_accepted(
        event_id="camp-a:1", paper_id="paper-a",
        paper_profile=profile, candidate_id="a1",
        layout_spec=spec, design_score=90,
    )
    assert first["accepted_poster_count"] == 1
    assert replayed["accepted_poster_count"] == 1
    assert registry.retrieve(
        family_id=family.family_id, paper_id="paper-b"
    ) == []
    assert registry.retrieve(
        family_id=family.family_id, paper_id="paper-a"
    )

    registry.record_accepted(
        event_id="camp-a:2", paper_id="paper-a",
        paper_profile=profile, candidate_id="a2",
        layout_spec=spec, design_score=92,
    )
    promoted = registry.record_accepted(
        event_id="camp-b:1", paper_id="paper-b",
        paper_profile={"profile_key": "visual"},
        candidate_id="b1", layout_spec=spec, design_score=94,
    )
    assert promoted["status"] == "promoted"
    foreign = registry.retrieve(
        family_id=family.family_id, paper_id="paper-c"
    )
    assert foreign[0]["generation_method"] == (
        "accepted_runtime_archetype"
    )


def test_campaign_layout_schema_migrates_without_losing_identity(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    state = {
        "output_dir": str(tmp_path / "out"),
        "poster_name": "paper",
        "poster_width": 54,
        "poster_height": 36,
        "raw_text": "same paper",
    }
    handle = manager.open_campaign(state, resume_mode="new")
    manifest_path = handle.path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["layout_engine_schema_version"] = 1
    identity = {
        key: manifest[key]
        for key in (
            "paper_sha256", "poster_width", "poster_height",
            "foundation_schema_version",
            "layout_engine_schema_version", "asset_sha256",
        )
    }
    canonical = json.dumps(
        identity, sort_keys=True, separators=(",", ":")
    )
    manifest["compatibility_fingerprint"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    resumed = manager.open_campaign(
        state, resume_mode="required", campaign_id=handle.campaign_id
    )
    assert resumed.campaign_id == handle.campaign_id
    assert (
        resumed.manifest["layout_engine_schema_version"]
        == LAYOUT_ENGINE_SCHEMA_VERSION
    )
    migration = resumed.manifest[
        "layout_engine_migration_history"
    ][-1]
    assert migration["from_version"] == 1
    assert migration["to_version"] == LAYOUT_ENGINE_SCHEMA_VERSION


def test_rejected_posters_are_complete_and_unbounded(tmp_path):
    config = deepcopy(load_critic_config())
    storage = LoopStorage(tmp_path / "store", config)

    for index in range(25):
        candidate_dir = tmp_path / f"candidate-{index}"
        candidate_dir.mkdir()
        png = candidate_dir / "poster.png"
        pptx = candidate_dir / "poster.pptx"
        Image.new("RGB", (4, 4), "white").save(png)
        pptx.write_bytes(b"editable-pptx-placeholder")
        state = {
            "poster_name": "paper",
            "iteration_context": {
                "campaign_id": "campaign_a",
                "batch_id": "batch_0001",
                "iteration": index + 1,
                "portfolio_mode": "explore",
                "layout_family": "classic_three_column",
            },
            "current_candidate": {
                "candidate_id": f"candidate_{index}",
                "candidate_dir": str(candidate_dir),
                "png_path": str(png),
                "pptx_path": str(pptx),
            },
            "story_board": {"spatial_content_plan": {"sections": []}},
            "styled_layout": [],
        }
        diagnostic = storage.record_rejection(
            "session", state,
            {
                "candidate_id": f"candidate_{index}",
                "overall_score": 50,
                "issues": [],
            },
        )
        assert not Path(diagnostic["archive_dir"]).exists()
        storage.publish_rejected_poster(diagnostic)
        assert not png.exists()
        assert not pptx.exists()

    rejected = list(
        (
            storage.root / "rejected_posters" / "campaign_a"
            / "batch_0001"
        ).iterdir()
    )
    assert len([item for item in rejected if item.is_dir()]) == 25
    for diagnostic_dir in rejected:
        assert {
            "poster.png",
            "poster.pptx",
            "critic_report.json",
            "layout_feasibility_report.json",
            "layout_preflight_report.json",
            "story_board.json",
            "styled_layout.json",
            "provenance.json",
        } <= {item.name for item in diagnostic_dir.iterdir()}


def test_improve_search_stays_parent_local_and_preserves_planner_constraints():
    agent = _MeasuredAgent()
    config = {
        "explore_layout": {
            "max_geometry_candidates_per_family": 4,
            "beam_width": 6,
            "diverse_top_k": 2,
            "minimum_sections": 5,
            "planning_target": 0.975,
            "maximum_utilization": 1.0,
        },
        "improve_layout": {
            "local_geometry_candidates": 4,
            "max_preflight_recovery_attempts": 3,
        },
    }
    base_state = {
        "poster_width": 54,
        "poster_height": 36,
        "iteration_context": {
            "random_seed": 19,
            "layout_family": "top_hero_bottom_grid",
            "portfolio_mode": "explore",
        },
        "images": {},
        "tables": {},
    }
    fitted, parent_spec, _ = fit_family_layout(
        agent, _board(), base_state, "top_hero_bottom_grid", config=config
    )
    section_to_zone = {
        str(section_id): str(zone["zone_id"])
        for zone in parent_spec["zones"]
        for section_id in zone.get("section_ids", [])
    }
    claims = {
        str(claim_id)
        for section in fitted["spatial_content_plan"]["sections"]
        for claim_id in section.get("claim_ids", [])
    }
    visuals = {
        str(visual["visual_id"])
        for section in fitted["spatial_content_plan"]["sections"]
        for visual in section.get("visual_assets", [])
    }
    improve_state = {
        **base_state,
        "iteration_context": {
            **base_state["iteration_context"],
            "random_seed": 31,
            "portfolio_mode": "improve",
        },
        "revision_parent_layout_spec": deepcopy(parent_spec),
        "layout_revision_constraints": {
            "section_to_zone": section_to_zone,
            "reading_order": list(parent_spec["reading_order"]),
            "primary_anchor_zone": parent_spec["primary_anchor_zone"],
            "must_retain_claim_ids": sorted(claims),
            "must_retain_visual_ids": sorted(visuals),
        },
    }
    revised, spec, report = fit_family_layout(
        agent, fitted, improve_state, "top_hero_bottom_grid", config=config
    )

    assert report["search_scope"] == "parent_local"
    assert report["candidate_content_selection"]["omitted_claim_ids"] == []
    assert report["candidate_content_selection"]["omitted_visual_ids"] == []
    assert spec["reading_order"] == parent_spec["reading_order"]
    assert spec["primary_anchor_zone"] == parent_spec["primary_anchor_zone"]
    assert {
        str(section_id): str(zone["zone_id"])
        for zone in spec["zones"]
        for section_id in zone.get("section_ids", [])
    } == section_to_zone
    assert {
        str(claim_id)
        for section in revised["spatial_content_plan"]["sections"]
        for claim_id in section.get("claim_ids", [])
    } == claims

def test_preflight_rejects_undersized_title_and_child_overlap():
    spec = {
        "family_id": "asymmetric_two_column",
        "variant_id": "title-check",
        "zones": [{
            "zone_id": "left", "x": 0.0, "y": 0.0,
            "width": 0.5, "height": 1.0, "section_ids": ["s1"],
        }],
    }
    state = {"poster_width": 54, "poster_height": 36}
    layout = [
        {
            "type": "section_container", "section_id": "s1",
            "zone_id": "left", "x": 1.0, "y": 7.12,
            "width": 26.0, "height": 4.0,
        },
        {
            "type": "section_title", "section_id": "s1",
            "zone_id": "left", "x": 2.0, "y": 7.12,
            "width": 10.0, "height": 0.9,
            "required_text_height": 1.8,
        },
        {
            "type": "text", "section_id": "s1",
            "zone_id": "left", "x": 2.0, "y": 7.8,
            "width": 10.0, "height": 2.0,
        },
    ]
    result = validate_compiled_layout(
        layout, spec, state, poster_margin=1.0,
        title_height_fraction=0.18,
    )
    codes = {item["code"] for item in result["issues"]}
    assert result["passed"] is False
    assert "PREFLIGHT_TITLE_HEIGHT" in codes
    assert "PREFLIGHT_SECTION_CHILD_OVERLAP" in codes
