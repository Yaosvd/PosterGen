"""Regression coverage for exact whole-poster whitespace and safe repair."""

from copy import deepcopy

import src.layout.capacity_repair as repair_module
from src.critic.base import CriticContext
from src.critic.quality import VisualAssetEvaluator
from src.layout.capacity_repair import (
    feasible_repair_zones,
    important_visual_omitted,
    needs_feasible_repair,
    repair_family_fit,
)
from src.layout.whitespace import (
    measure_composition_whitespace,
    no_displaced_whitespace,
)


def _composition(zone_width):
    spec = {"zones": [{
        "zone_id": "main", "x": 0.0, "y": 0.0,
        "width": zone_width, "height": 1.0,
    }]}
    layout = [{
        "type": "section_container", "section_id": "s1", "zone_id": "main",
        "x": 1.0, "y": 2.0, "width": 4.0, "height": 7.0,
    }]
    return measure_composition_whitespace(
        spec, layout, poster_width=11.0, poster_height=10.0,
        poster_margin=1.0, title_height_fraction=0.125,
    )


def test_shrinking_zone_does_not_hide_displaced_poster_whitespace():
    before = _composition(0.5)
    after = _composition(0.4)
    assert after["unallocated_body_fraction"] > before["unallocated_body_fraction"]
    assert after["largest_empty_rectangle_fraction"] == before["largest_empty_rectangle_fraction"]
    assert not no_displaced_whitespace(before, after)


def test_cross_zone_gap_is_measured_separately_from_internal_fill():
    spec = {"zones": [
        {"zone_id": "left", "x": 0, "y": 0, "width": 0.3, "height": 1},
        {"zone_id": "right", "x": 0.7, "y": 0, "width": 0.3, "height": 1},
    ]}
    layout = [
        {"type": "section_container", "section_id": "a", "zone_id": "left",
         "x": 1, "y": 2, "width": 2.7, "height": 7},
        {"type": "section_container", "section_id": "b", "zone_id": "right",
         "x": 7.3, "y": 2, "width": 2.7, "height": 7},
    ]
    report = measure_composition_whitespace(
        spec, layout, poster_width=11, poster_height=10,
        poster_margin=1, title_height_fraction=0.125,
    )
    assert report["largest_cross_zone_gap_inches"] == 3.6
    assert report["largest_within_zone_gap_inches"] == 0
    assert report["unallocated_body_fraction"] == 0.4


def test_sparse_entry_and_action_planner_use_the_same_threshold():
    settings = {"active_utilization_threshold": 0.90, "large_bottom_gap_body_lines": 2}
    report = {
        "status": "feasible", "zone_utilization": {"hero": 0.709911, "side": 0.94},
        "exact_bottom_gaps": {"hero": 4.4517, "side": 0.3},
        "body_line_height_inches": 0.61,
    }
    assert needs_feasible_repair(report, settings)
    assert feasible_repair_zones(report, settings) == ["hero"]
    report["zone_utilization"]["hero"] = 0.96
    assert feasible_repair_zones(report, settings) == ["hero"]
    report["exact_bottom_gaps"]["hero"] = 0.2
    assert not needs_feasible_repair(report, settings)


def _repair_fixture(tmp_path):
    asset = tmp_path / "figure-2.png"
    asset.write_bytes(b"approved fixture")
    board = {"spatial_content_plan": {"sections": [{
        "section_id": "s1", "section_title": "Method",
        "claim_ids": ["c1"], "text_content": ["Grounded claim"],
        "visual_assets": [{"visual_id": "figure_2"}],
    }]}}
    visible = deepcopy(board)
    visible["spatial_content_plan"]["sections"][0]["visual_assets"] = []
    whitespace = {
        "unallocated_body_fraction": 0.04,
        "largest_empty_rectangle_fraction": 0.1,
        "largest_cross_zone_gap_inches": 0.5,
        "largest_within_zone_gap_inches": 0,
    }
    report = {
        "status": "feasible", "family_id": "classic_three_column",
        "worst_zone_utilization": 0.71,
        "zone_utilization": {"main": 0.71},
        "exact_bottom_gaps": {"main": 4.0},
        "candidate_content_selection": {"omitted_visual_ids": ["figure_2"]},
        "composition_whitespace": whitespace,
    }
    state = {
        "generation_route": "optimization_family",
        "iteration_context": {"portfolio_mode": "explore", "visual_restore_remaining": 2},
        "critic_config": {"capacity_repair": {"max_rounds_per_family": 1}},
        "classified_visuals": {"key_visual": "figure_2"},
        "layout_visual_source_manifest": {"s1": ["figure_2"]},
        "images": {"2": {"path": str(asset)}}, "tables": {},
    }
    return board, visible, report, state


def test_important_source_visual_triggers_repair_even_if_zone_is_full(tmp_path):
    _, _, report, state = _repair_fixture(tmp_path)
    report["zone_utilization"] = {"main": 0.96}
    report["exact_bottom_gaps"] = {"main": 0.1}
    assert important_visual_omitted(report, state)


def test_visual_recovery_preserves_source_section_and_fixed_topology(tmp_path, monkeypatch):
    original, visible, report, state = _repair_fixture(tmp_path)
    fixed_zones = [{"zone_id": "main", "x": 0, "y": 0, "width": 1, "height": 1}]
    calls = []

    def fake_fit(_agent, candidate, trial_state, _family, *, config, fixed_zones):
        calls.append((deepcopy(candidate), trial_state["layout_required_visual_ids"], fixed_zones))
        return candidate, {"zones": fixed_zones}, deepcopy(report)

    monkeypatch.setattr(repair_module, "fit_family_layout", fake_fit)
    result, audit = repair_family_fit(
        object(), state, original, "classic_three_column",
        initial_report=report,
        initial_result=(visible, {"zones": fixed_zones}, report),
        fixed_zones=fixed_zones,
    )
    assert result[0]["spatial_content_plan"]["sections"][0]["visual_assets"] == [
        {"visual_id": "figure_2"}
    ]
    assert calls[0][1:] == (["figure_2"], fixed_zones)
    assert audit["visual_restoration"][0]["status"] == "restored"
    assert audit["status"] == "applied"


def test_visual_recovery_rejects_displaced_whitespace(tmp_path, monkeypatch):
    original, visible, report, state = _repair_fixture(tmp_path)

    def fake_fit(_agent, candidate, _state, _family, *, config, fixed_zones):
        worse = deepcopy(report)
        worse["composition_whitespace"] = {
            **report["composition_whitespace"], "unallocated_body_fraction": 0.25,
        }
        return candidate, {"zones": []}, worse

    monkeypatch.setattr(repair_module, "fit_family_layout", fake_fit)
    result, audit = repair_family_fit(
        object(), state, original, "classic_three_column",
        initial_report=report, initial_result=(visible, {"zones": []}, report),
    )
    assert result[0] == visible
    assert audit["visual_restoration"][0]["status"] == "content_or_whitespace_regression"


def test_visual_recovery_cannot_trade_existing_claim_for_visual(tmp_path, monkeypatch):
    original, visible, report, state = _repair_fixture(tmp_path)

    def fake_fit(_agent, candidate, _state, _family, *, config, fixed_zones):
        candidate["spatial_content_plan"]["sections"][0]["claim_ids"] = []
        return candidate, {"zones": []}, deepcopy(report)

    monkeypatch.setattr(repair_module, "fit_family_layout", fake_fit)
    result, audit = repair_family_fit(
        object(), state, original, "classic_three_column",
        initial_report=report, initial_result=(visible, {"zones": []}, report),
    )
    assert result[0] == visible
    assert audit["visual_restoration"][0]["status"] == "content_or_whitespace_regression"


def test_critic_audits_missing_source_key_visual_without_changing_score(tmp_path):
    _, visible, _, state = _repair_fixture(tmp_path)
    state["optimized_story_board"] = visible
    result = VisualAssetEvaluator().evaluate(CriticContext(
        state, {"evaluators": {"visual_assets": {"hard_gate": True}}}
    ))
    selection = result.metadata["source_visual_selection"]
    assert selection["omitted_source_visual_ids"] == ["figure_2"]
    assert selection["key_visual_omitted"] is True
    assert result.scores["aesthetics"] == 100.0
    assert result.passed is True
