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


def test_all_thirteen_are_reachable_with_no_semantic_flags():
    registry = LayoutFamilyRegistry()
    profile = build_paper_profile({})
    assert len(registry.compatible_ids(profile)) == 13
    observed = {registry.choose(profile, {}, random_seed=seed) for seed in range(1000)}
    assert observed == set(registry.ids())


def test_coverage_precedes_semantics_and_first_cycle_covers_all():
    registry = LayoutFamilyRegistry()
    profile = build_paper_profile(_profile_state())
    counts = {}
    seen = []
    for iteration in range(1, len(registry.ids()) + 1):
        family, report = registry.choose_with_report(profile, counts, random_seed=33 + iteration)
        seen.append(family)
        assert report["family_use_counts"][family] == 0
        assert all(1 <= v["weight"] <= 1.5 for v in report["semantic_scores"].values())
        counts[family] = counts.get(family, 0) + 1
    assert set(seen) == set(registry.ids()) and len(set(seen)) == 13
    counts = {family: 5 for family in registry.ids()}
    counts["four_column_modular"] = 0
    assert registry.choose(profile, counts, random_seed=5) == "four_column_modular"


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






def test_family_geometry_does_not_bind_scientific_stages_to_regions():
    state = {"narrative_plan": {"sections": [
        {"section_id": "m", "narrative_role": "methods"},
        {"section_id": "r", "narrative_role": "results"},
    ]}}
    sections = [{"section_id": "m"}, {"section_id": "r"}]
    assert _semantic_role(sections[0], state) == "method"
    for family in ('method_flow_spine', 'modular_editorial_mosaic', 'top_hero_bottom_grid'):
        assert _active_zone_roles(family, sections, state) == {}
    assert _active_zone_roles("classic_three_column", sections, state) == {}
    assert _active_zone_roles("method_flow_spine", [{"section_id": "unknown"}], {}) == {}
    # A scientific stage is not inferred from the internal layout ID.
    assert _semantic_role({"section_id": "stage_1"}, {}) == "supporting"


@pytest.mark.parametrize("family_id", ["timeline_stage_narrative", "result_dashboard_cards"])
def test_removed_families_cannot_be_selected_or_reenabled(tmp_path, family_id):
    registry = LayoutFamilyRegistry()
    with pytest.raises(ValueError, match="unknown layout family"):
        registry.get(family_id)
    config = load_critic_config()
    config["layout_families"]["enabled"][-1] = family_id
    path = tmp_path / "critic.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="registered IDs"):
        load_critic_config(path, use_cache=False)
    with pytest.raises(ValueError, match="registered IDs"):
        registry.choose(build_paper_profile({}), {}, random_seed=1,
                        policy={**make_family_selection_policy({}, registry.ids()),
                                "enabled_families": ["classic_three_column", family_id]})
