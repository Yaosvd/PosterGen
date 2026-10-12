"""All-family reachability, bounded preference and persistent policy contracts."""

import json
from copy import deepcopy

import pytest
import yaml

from src.config.critic_config import load_critic_config
from src.layout.families import LayoutFamilyRegistry
from src.layout.family_selection import (
    FamilySelectionExhausted, make_family_selection_policy, profile_identity,
)
from src.layout.paper_profile import build_paper_profile
from src.layout.feasibility import _active_zone_roles, _semantic_role
from src.workflow.campaign import CampaignManager
from src.workflow.loop_progress import format_event
from src.workflow.portfolio import PortfolioScheduler, new_portfolio_state


def _profile_state():
    return {
        "images": {f"figure_{i}": {} for i in range(7)},
        "verified_claims": {"claims": [{} for _ in range(48)]},
        "narrative_plan": {"sections": [
            {"section_id": "s1", "title_intent": "Methodology: A grounded method",
             "narrative_role": "method"},
            {"section_id": "s2", "title_intent": "Performance vs. Baselines",
             "narrative_role": "results"},
            {"section_id": "s3", "title_intent": "Ablation Studies"},
        ]},
    }


def test_active_profile_fields_preserve_legacy_key_without_scientific_text():
    state = _profile_state()
    before = deepcopy(state)
    profile = build_paper_profile(state)
    assert state == before
    assert profile["profile_key"] == "visual_heavy:high"
    assert profile["visual_count"] == 7 and profile["claim_count"] == 48
    assert profile["design_flags"] == ["comparison", "method_heavy", "results_heavy"]
    assert profile["semantic_signals"]["method_heavy"]["strength"] == 1.0
    sources = profile["semantic_signals"]["comparison"]["sources"]
    assert {s["section_id"] for s in sources} == {"s2", "s3"}
    assert {s["field"] for s in sources} == {"title_intent"}
    assert "Ablation Studies" not in json.dumps(profile)
    assert profile_identity(profile) == profile_identity(build_paper_profile(state))


@pytest.mark.parametrize("field", ["title_intent", "title", "section_title"])
def test_legacy_titles_and_explicit_process_stage_hints(field):
    profile = build_paper_profile({"narrative_plan": {"sections": [
        {"section_id": "s1", field: "Pipeline, Stage Analysis and Timeline"}
    ]}})
    assert set(profile["design_flags"]) == {"process", "stages", "timeline"}
    assert all(s["field"] == field for v in profile["semantic_signals"].values()
               for s in v["sources"])


def test_section_ids_and_generic_results_do_not_invent_relations():
    profile = build_paper_profile({"narrative_plan": {"sections": [
        {"section_id": "method_comparison_stage_timeline"},
        {"section_id": "s2", "narrative_role": "results", "title_intent": "Database"},
    ]}})
    assert profile["design_flags"] == ["results_heavy"]
    assert profile["semantic_signals"]["timeline"]["status"] == "unobserved"


def test_all_twelve_are_reachable_with_no_semantic_flags():
    registry = LayoutFamilyRegistry()
    profile = build_paper_profile({})
    assert len(registry.compatible_ids(profile)) == 12
    observed = {registry.choose(profile, {}, random_seed=seed) for seed in range(1000)}
    assert observed == set(registry.ids())


def test_coverage_precedes_semantics_and_first_twelve_explores_cover_all():
    registry = LayoutFamilyRegistry()
    profile = build_paper_profile(_profile_state())
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=33)
    portfolio = new_portfolio_state()
    seen = []
    for iteration in range(1, 13):
        task = scheduler.select(
            portfolio, iteration=iteration, session_iteration=iteration,
            paper_profile=profile, validation_available=False, batch_mode="explore",
        )
        seen.append(task["family_id"])
        report = task["family_selection_report"]
        assert report["family_use_counts"][task["family_id"]] == 0
        assert all(1 <= v["weight"] <= 1.5 for v in report["semantic_scores"].values())
        portfolio = scheduler.commit(
            portfolio, task, {"candidate_id": f"c{iteration}", "overall_score": 65,
                              "issues": [], "decision": "discard"}, accepted=False,
        )
    assert set(seen) == set(registry.ids()) and len(set(seen)) == 12
    counts = {family: 5 for family in registry.ids()}
    counts["timeline_stage_narrative"] = 0
    assert registry.choose(profile, counts, random_seed=5) == "timeline_stage_narrative"


def test_selection_is_reproducible_and_exclusions_never_reenter():
    registry = LayoutFamilyRegistry()
    profile = build_paper_profile(_profile_state())
    first = registry.choose_with_report(profile, {}, random_seed=17)
    assert first == registry.choose_with_report(profile, {}, random_seed=17)
    family, report = registry.choose_with_report(profile, {}, random_seed=17, exclude=[first[0]])
    assert family != first[0] and first[0] not in report["available_families"]
    with pytest.raises(FamilySelectionExhausted) as error:
        registry.choose(profile, {}, random_seed=17, exclude=registry.ids())
    assert error.value.report["status"] == "exhausted"
    assert error.value.report["selected_family"] is None


def test_enabled_snapshot_and_neutral_weight_are_enforced():
    registry = LayoutFamilyRegistry()
    enabled = [x for x in registry.ids() if x != "comparison_split"]
    policy = make_family_selection_policy({"enabled": enabled, "selection": {
        "semantic_bonus_max": 0.0,
    }}, registry.ids())
    _, report = registry.choose_with_report(
        build_paper_profile(_profile_state()), {}, random_seed=5, policy=policy,
    )
    assert "comparison_split" not in report["enabled_families"]
    assert all(s["weight"] == 1 for s in report["semantic_scores"].values())


@pytest.mark.parametrize("bad_bonus", [-0.1, 0.6, float("nan"), float("inf"), True])
def test_config_rejects_unbounded_semantic_preference(tmp_path, bad_bonus):
    config = load_critic_config()
    config["layout_families"]["selection"]["semantic_bonus_max"] = bad_bonus
    path = tmp_path / "critic.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="semantic_bonus_max"):
        load_critic_config(path, use_cache=False)


def test_config_rejects_unregistered_family(tmp_path):
    config = load_critic_config()
    config["layout_families"]["enabled"][-1] = "invented_family"
    path = tmp_path / "critic.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="registered IDs"):
        load_critic_config(path, use_cache=False)


def test_batch_policy_freezes_and_legacy_upgrade_is_idempotent(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    state = {"poster_name": "paper", "raw_text": "same paper",
             "poster_width": 54, "poster_height": 36}
    handle = manager.open_campaign(state, resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100, mode="explore")
    frozen = deepcopy(batch["schedule_policy"])
    batch["status"] = "PAUSED"
    manager.save_batch(handle, batch)
    config["layout_families"]["selection"]["semantic_bonus_max"] = 0.0
    resumed = manager.open_batch(handle, target_iterations=2, batch_id=batch["batch_id"])
    assert resumed["schedule_policy"] == frozen
    assert resumed["target_iterations"] == 100
    assert "family_selection_migration" not in resumed

    # Simulate a legacy paused Batch, retaining its original mode and budget.
    resumed["schedule_policy"].pop("family_selection")
    resumed["status"] = "PAUSED"
    manager.save_batch(handle, resumed)
    upgraded = manager.open_batch(handle, target_iterations=2, batch_id=batch["batch_id"])
    migration = deepcopy(upgraded["family_selection_migration"])
    upgraded_policy = deepcopy(upgraded["schedule_policy"])
    assert upgraded_policy["family_selection"]["semantic_bonus_max"] == 0.0
    assert upgraded_policy["mode"] == "explore"
    upgraded["status"] = "PAUSED"
    manager.save_batch(handle, upgraded)
    config["layout_families"]["selection"]["semantic_bonus_max"] = 0.5
    again = manager.open_batch(handle, target_iterations=2, batch_id=batch["batch_id"])
    assert again["family_selection_migration"] == migration
    assert again["schedule_policy"] == upgraded_policy
    assert again["completed_iterations"] == 0
    assert again["target_iterations"] == 100


def test_corrupt_frozen_policy_fails_before_resuming(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign({"poster_name": "paper", "raw_text": "paper",
                                   "poster_width": 54, "poster_height": 36}, resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100)
    batch["status"] = "PAUSED"
    batch["schedule_policy"]["family_selection"]["version"] = 999
    manager.save_batch(handle, batch)
    with pytest.raises(ValueError, match="Unsupported family_selection"):
        manager.open_batch(handle, target_iterations=100, batch_id=batch["batch_id"])
    assert manager.load_batch(handle, batch["batch_id"])["status"] == "PAUSED"


def test_content_roles_remain_conditional_for_special_and_other_families():
    state = {"narrative_plan": {"sections": [
        {"section_id": "m", "narrative_role": "methods"},
        {"section_id": "r", "narrative_role": "results"},
    ]}}
    sections = [{"section_id": "m"}, {"section_id": "r"}]
    assert _semantic_role(sections[0], state) == "method"
    assert _active_zone_roles("method_flow_spine", sections, state) == {"flow_spine": {"method"}}
    assert _active_zone_roles("result_dashboard_cards", sections, state) == {
        "primary_result": {"results"}, "method": {"method"},
    }
    assert _active_zone_roles("top_hero_bottom_grid", sections, state) == {
        "top_hero": {"results", "conclusion"},
    }
    assert _active_zone_roles("classic_three_column", sections, state) == {}
    assert _active_zone_roles("method_flow_spine", [{"section_id": "unknown"}], {}) == {}
    # A scientific stage is not inferred from the internal layout ID.
    assert _semantic_role({"section_id": "stage_1"}, {}) == "supporting"


def test_selection_progress_reports_usage_not_exploration_count():
    _, report = LayoutFamilyRegistry().choose_with_report({}, {}, random_seed=1)
    text = format_event({"type": "family_selection", "iteration": 1, "report": report})
    assert "12 enabled" in text
    assert "12 least-used candidates" in text
    assert "committed design uses 0" in text
    assert "semantic weight" in text
