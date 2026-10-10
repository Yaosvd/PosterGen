"""CPU-only regressions for Planner -> content -> exact layout -> admission."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from PIL import Image

import src.agents.revision_planner as planner_module
import src.agents.layout_with_balancer as layout_module
from src.agents.content_optimizer import GroundedContentOptimizer
from src.agents.color_agent import ColorAgent
from src.agents.font_agent import FontAgent
from src.agents.layout_preflight import layout_preflight_node
from src.agents.layout_with_balancer import LayoutWithBalancerAgent
from src.agents.revision_contract import (
    apply_revision_admission, authorize_deletions, board_identity, build_contract,
    check_contract, compiled_contract_audit, deletion_guard, operation_audit,
    recovery_allowed, revoke_harmful_deletions,
)
from src.agents.revision_planner import RevisionPlanner
from src.layout.capacity_repair import _visual_recovery_candidates, important_visual_omitted
import src.layout.capacity_repair as repair_module
from src.layout.families import compile_layout
from src.layout.feasibility import fit_family_layout
from src.workflow.campaign import CampaignManager
from src.workflow.campaign_runner import (
    _exact_parent_restore_report, _prepare_improve_parent,
    _reset_attempt_diagnostics, _restore_exact_improve_parent,
)
from src.workflow.optimization_loop import PosterOptimizationLoop
from src.workflow.portfolio import assess_promising_candidate
from src.config.critic_config import load_critic_config


def state_fixture(tmp_path):
    assets = {}
    for number in (1, 2):
        path = tmp_path / f"figure-{number}.png"
        Image.new("RGB", (80, 40), "white").save(path)
        assets[str(number)] = {"path": str(path), "aspect_ratio": 2.0}
    claims = [{"claim_id": f"c{s}_{i}", "text": f"Verified result {s}-{i}.",
               "section_id": f"s{s}", "evidence_ids": [f"e{s}_{i}"], "verified": True}
              for s in range(6) for i in range(4)]
    board = {"spatial_content_plan": {"sections": [
        {"section_id": f"s{s}", "section_title": f"Module {s}", "importance_level": 2,
         "vertical_priority": "middle", "claim_ids": [f"c{s}_{i}" for i in range(4)],
         "text_content": [f"Verified result {s}-{i}." for i in range(4)],
         "visual_assets": [{"visual_id": "figure_1"}] if s == 0 else []}
        for s in range(6)]}}
    return {
        "output_dir": str(tmp_path / "output"), "poster_name": "fixture",
        "poster_width": 54, "poster_height": 36, "errors": [],
        "generation_route": "optimization_family", "story_board": deepcopy(board),
        "optimized_story_board": deepcopy(board), "images": assets, "tables": {},
        "verified_claims": {"claims": claims}, "classified_visuals": {},
        "verified_content_bank": {"claims": []}, "supplemental_evidence_bank": {"items": []},
        "content_selection": {}, "critic_config": {"capacity_repair": {"enabled": False}},
        "tokens": SimpleNamespace(add_text=lambda *_: None), "text_model": {},
        "iteration_context": {"iteration": 2, "portfolio_mode": "improve", "random_seed": 19,
                              "layout_family": "top_hero_bottom_grid"},
        "critic_report": {"rubric_version": "test", "issues": []},
    }


def fake_planner(monkeypatch, plan):
    monkeypatch.setattr(planner_module, "apply_agent_policy", lambda config, _: config)
    monkeypatch.setattr(planner_module, "LangGraphAgent", lambda *_: SimpleNamespace(
        step=lambda _: SimpleNamespace(content=json.dumps(plan), input_tokens=0, output_tokens=0)))


def deletion_issue(kind="visual", *, duplicate=False, unusable=False):
    return {"issue_id": "VISUAL-ASSET-DUPLICATED" if duplicate else "VISUAL-ASSET-UNREADABLE-figure_1" if unusable else "OVERFLOW",
            "location": {"section_id": "s0", f"{kind}_id": "figure_1" if kind == "visual" else "c0_3"},
            "allowed_operations": ["remove_visual", "replace_visual"] if kind == "visual" else ["remove_claim"],
            "evidence": {"visual_ids": ["figure_1"]} if duplicate else {}}


@pytest.mark.parametrize("disabled", [False, True])
def test_zero_or_disabled_content_keeps_planner_working_board(tmp_path, monkeypatch, disabled):
    state = state_fixture(tmp_path)
    state["critic_report"]["issues"] = [deletion_issue()]
    parent = deepcopy(state["story_board"])
    fake_planner(monkeypatch, {"operations": [
        {"operation": "remove_visual", "section_id": "s0", "visual_id": "figure_1", "critic_issue_ids": ["OVERFLOW"], "reason": "scoped overflow"},
        {"operation": "set_section_importance", "section_id": "s0", "importance_level": 1},
        {"operation": "set_section_gap", "gap_inches": 0.5}], "content_actions": []})
    RevisionPlanner()(state)
    working = deepcopy(state["story_board"])
    if disabled:
        state["critic_config"]["content_optimization"] = {"enabled": False}
    GroundedContentOptimizer()(state, actions_override=[], save=False)
    assert state["story_board"] == working
    assert state["revision_parent_story_board"] == parent
    assert state["optimized_story_board"] == parent
    assert not state["story_board"]["spatial_content_plan"]["sections"][0]["visual_assets"]


@pytest.mark.parametrize("override", [{}, [], {"spatial_content_plan": {"sections": []}}])
def test_invalid_explicit_override_never_falls_back(tmp_path, override):
    state = state_fixture(tmp_path)
    before = deepcopy(state["story_board"])
    GroundedContentOptimizer()(state, board_override=override, actions_override=[], save=False)
    assert state["errors"]
    assert state["story_board"] == before


def test_missing_current_board_never_reads_parent(tmp_path):
    state = state_fixture(tmp_path)
    state["revision_parent_story_board"] = deepcopy(state["story_board"])
    state["story_board"] = None
    GroundedContentOptimizer()(state, save=False)
    assert state["errors"] and state["story_board"] is None


def test_explicit_override_is_higher_priority_than_working_board(tmp_path):
    state = state_fixture(tmp_path)
    override = deepcopy(state["story_board"])
    override["spatial_content_plan"]["sections"][0]["visual_assets"] = []
    GroundedContentOptimizer()(state, board_override=override, actions_override=[], save=False)
    assert state["story_board"] == override


def test_deletion_requires_matching_actionable_evidence(tmp_path):
    state = state_fixture(tmp_path)
    issue = deletion_issue()
    state["critic_report"]["issues"] = [issue]
    operation = {"operation": "remove_visual", "section_id": "s0", "visual_id": "figure_2", "reason": "not enough", "critic_issue_ids": ["OVERFLOW"]}
    accepted, rejected = authorize_deletions([operation], state, state["story_board"])
    assert not accepted and rejected
    operation["visual_id"] = "figure_1"
    issue["forbidden_operations"] = ["remove_visual"]
    assert not authorize_deletions([operation], state, state["story_board"])[0]
    issue["forbidden_operations"] = []
    assert authorize_deletions([operation], state, state["story_board"])[0]


def test_protected_visual_needs_object_evidence_not_generic_overflow(tmp_path):
    state = state_fixture(tmp_path)
    state["classified_visuals"] = {"key_visual": "figure_1"}
    issue = deletion_issue()
    issue["location"] = {"section_id": "s0"}
    state["critic_report"]["issues"] = [issue]
    operation = {"operation": "remove_visual", "section_id": "s0", "visual_id": "figure_1", "reason": "overflow", "critic_issue_ids": ["OVERFLOW"]}
    assert not authorize_deletions([operation], state, state["story_board"])[0]
    issue["location"]["visual_id"] = "figure_1"
    assert authorize_deletions([operation], state, state["story_board"])[0]


def test_duplicate_removal_is_occurrence_scoped_and_keeps_one(tmp_path):
    state = state_fixture(tmp_path)
    board = state["story_board"]
    board["spatial_content_plan"]["sections"][1]["visual_assets"] = [{"visual_id": "figure_1"}]
    state["critic_report"]["issues"] = [deletion_issue(duplicate=True)]
    ops = [{"operation": "remove_visual", "section_id": sid, "visual_id": "figure_1", "critic_issue_ids": ["VISUAL-ASSET-DUPLICATED"], "reason": "keep one occurrence"} for sid in ("s0", "s1")]
    accepted, rejected = authorize_deletions(ops, state, board)
    assert len(accepted) == 1 and len(rejected) == 1
    revised, accepted = RevisionPlanner().apply_operations(board, accepted, {c["claim_id"]: c for c in state["verified_claims"]["claims"]})
    state["revision_contract"] = build_contract(state, board, revised, accepted)
    assert not recovery_allowed(state, "s0", "figure_1")
    assert recovery_allowed(state, "s1", "figure_1")
    assert check_contract(state, revised)["passed"]


def test_duplicate_in_one_module_removes_only_one_occurrence(tmp_path):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    parent["spatial_content_plan"]["sections"][0]["visual_assets"] *= 2
    state["critic_report"]["issues"] = [deletion_issue(duplicate=True)]
    op = {"operation": "remove_visual", "section_id": "s0", "visual_id": "figure_1", "critic_issue_ids": ["VISUAL-ASSET-DUPLICATED"], "reason": "duplicate"}
    approved, _ = authorize_deletions([op], state, parent)
    revised, ops = RevisionPlanner().apply_operations(parent, approved, {c["claim_id"]: c for c in state["verified_claims"]["claims"]})
    state["revision_parent_story_board"] = parent
    state["revision_plan"] = {"operations": ops}
    state["revision_contract"] = build_contract(state, parent, revised, ops)
    assert len(revised["spatial_content_plan"]["sections"][0]["visual_assets"]) == 1
    assert operation_audit(state, revised, [{}])[0]["status"] == "applied"
    assert check_contract(state, revised)["passed"]


def test_unusable_visual_never_restored_for_density(tmp_path):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    revised = deepcopy(parent)
    revised["spatial_content_plan"]["sections"][0]["visual_assets"] = []
    state["layout_visual_source_manifest"] = {"s0": ["figure_1"]}
    ops = [{"operation": "remove_visual", "operation_id": "remove", "section_id": "s0", "visual_id": "figure_1", "deletion_class": "unusable_asset"}]
    state["revision_plan"] = {"operations": ops}
    state["revision_parent_story_board"] = parent
    state["revision_contract"] = build_contract(state, parent, revised, ops)
    assert not _visual_recovery_candidates(state, revised, set())
    restored, changes = revoke_harmful_deletions(state, revised)
    assert not changes and restored == revised
    assert state["layout_visual_source_manifest"] == {"s0": ["figure_1"]}
    # A surviving duplicate does not silently clear an unusable-asset flag.
    revised["spatial_content_plan"]["sections"][1]["visual_assets"] = [{"visual_id": "figure_1"}]
    state["revision_contract"] = build_contract(state, parent, revised, ops)
    assert "figure_1" in state["revision_recovery_policy"]["unusable_visual_ids"]
    assert not check_contract(state, revised)["passed"]


def test_move_updates_recovery_target_without_rewriting_provenance(tmp_path):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    revised, ops = RevisionPlanner().apply_operations(parent, [{"operation": "move_visual", "visual_id": "figure_1", "target_section_id": "s1"}], {c["claim_id"]: c for c in state["verified_claims"]["claims"]})
    state["layout_visual_source_manifest"] = {"s0": ["figure_1"]}
    state["revision_contract"] = build_contract(state, parent, revised, ops)
    assert _visual_recovery_candidates(state, revised, set()) == [("s1", "figure_1")]
    state["classified_visuals"] = {"key_visual": "figure_1"}
    assert important_visual_omitted({"candidate_content_selection": {"omitted_visual_ids": ["figure_1"]}}, state)
    assert check_contract(state, parent)["passed"] is False
    assert state["layout_visual_source_manifest"] == {"s0": ["figure_1"]}


def test_deliberate_valid_removal_is_not_automatic_visual_recovery(tmp_path):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    revised = deepcopy(parent)
    revised["spatial_content_plan"]["sections"][0]["visual_assets"] = []
    state["layout_visual_source_manifest"] = {"s0": ["figure_1"]}
    state["classified_visuals"] = {"key_visual": "figure_1"}
    state["revision_contract"] = build_contract(state, parent, revised, [])
    assert not _visual_recovery_candidates(state, revised, set())
    assert not important_visual_omitted({"candidate_content_selection": {"omitted_visual_ids": ["figure_1"]}}, state)


def test_latest_same_rubric_scoped_issue_can_authorize_removal(tmp_path):
    state = state_fixture(tmp_path)
    state["lineage_feedback"] = {"critic_report": {"rubric_version": "test", "issues": [deletion_issue()]}}
    operation = {"operation": "remove_visual", "visual_id": "figure_1", "section_id": "s0", "critic_issue_ids": ["OVERFLOW"], "reason": "latest feedback"}
    assert authorize_deletions([operation], state, state["story_board"])[0]
    state["lineage_feedback"]["critic_report"]["rubric_version"] = "another-rubric"
    assert not authorize_deletions([operation], state, state["story_board"])[0]


def metrics(fill=0.97, empty=0.08, gap=0.3):
    return {"zone_utilization": {"main": fill}, "exact_bottom_gaps": {"main": gap},
            "composition_whitespace": {"unallocated_body_fraction": 0.03,
                "largest_empty_rectangle_fraction": empty,
                "largest_cross_zone_gap_inches": gap, "largest_within_zone_gap_inches": gap}}


def test_guard_checks_global_holes_not_only_local_fill(tmp_path):
    state = state_fixture(tmp_path)
    state["revision_contract"] = {"removed_visual_occurrences": [["s0", "figure_1"]]}
    state["improve_parent_snapshot"] = {"fit_report": metrics()}
    worse = metrics(fill=0.99, empty=0.20)
    assert not deletion_guard(state, worse)["passed"]
    assert deletion_guard(state, metrics())["passed"]
    state["improve_parent_snapshot"] = {}
    assert deletion_guard(state, worse)["baseline_status"] == "unavailable_absolute_critic_required"


def test_valid_deletion_can_be_explicitly_revoked_then_reconsidered(tmp_path):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    revised = deepcopy(parent)
    revised["spatial_content_plan"]["sections"][0]["visual_assets"] = []
    op = {"operation": "remove_visual", "section_id": "s0", "visual_id": "figure_1", "operation_id": "remove"}
    state["revision_plan"] = {"operations": [op]}
    state["revision_parent_story_board"] = parent
    state["revision_contract"] = build_contract(state, parent, revised, [op])
    assert not recovery_allowed(state, "s0", "figure_1")
    restored, changes = revoke_harmful_deletions(state, revised)
    assert changes == [["s0", "figure_1"]]
    assert check_contract(state, restored)["passed"]
    assert state["revision_contract"]["revoked_operation_ids"] == ["remove"]
    assert operation_audit(state, restored, [{}])[0]["status"] == "revoked"
    # A later explicit placement clears a previous candidate's exclusion.
    state["revision_contract"] = build_contract(state, revised, parent, [])
    assert recovery_allowed(state, "s0", "figure_1")


def test_same_root_claim_variant_cannot_undo_deletion(tmp_path):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    revised = deepcopy(parent)
    revised["spatial_content_plan"]["sections"][0]["claim_ids"].remove("c0_3")
    variant = {"claim_id": "variant", "root_claim_id": "c0_3", "text": "Verified shortened result.", "verified": True, "section_id": "s0", "evidence_ids": ["e0_3"]}
    state["verified_content_bank"]["claims"] = [variant]
    state["revision_contract"] = build_contract(state, parent, revised, [])
    state["story_board"] = revised
    GroundedContentOptimizer()(state, actions_override=[{"operation": "add_existing_claim", "section_id": "s0", "claim_id": "variant"}], save=False)
    assert "variant" not in state["story_board"]["spatial_content_plan"]["sections"][0]["claim_ids"]
    assert state["content_revision"]["rejected_actions"]


def test_later_planner_can_explicitly_reintroduce_original_visual(tmp_path, monkeypatch):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    revised = deepcopy(parent)
    revised["spatial_content_plan"]["sections"][0]["visual_assets"] = []
    state["layout_visual_source_manifest"] = {"s0": ["figure_1"]}
    state["revision_contract"] = build_contract(state, parent, revised, [])
    state["story_board"] = state["optimized_story_board"] = revised
    fake_planner(monkeypatch, {"operations": [{"operation": "restore_visual", "section_id": "s0", "visual_id": "figure_1", "reason": "restore useful original figure"}], "content_actions": []})
    RevisionPlanner()(state)
    GroundedContentOptimizer()(state, save=False)
    assert recovery_allowed(state, "s0", "figure_1")
    assert state["story_board"]["spatial_content_plan"]["sections"][0]["visual_assets"] == [{"visual_id": "figure_1"}]
    assert check_contract(state, state["story_board"])["passed"]


def test_later_claim_reconsideration_is_published_only_after_placement(tmp_path, monkeypatch):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    revised = deepcopy(parent)
    revised["spatial_content_plan"]["sections"][0]["claim_ids"].remove("c0_3")
    state["revision_contract"] = build_contract(state, parent, revised, [])
    state["story_board"] = state["optimized_story_board"] = revised
    fake_planner(monkeypatch, {"operations": [], "content_actions": [{"operation": "add_existing_claim", "section_id": "s0", "claim_id": "c0_3", "reason": "restore useful evidence"}]})
    RevisionPlanner()(state)
    assert ["s0", "c0_3"] in state["revision_recovery_policy"]["excluded_claim_roots"]
    GroundedContentOptimizer()(state, save=False)
    assert ["s0", "c0_3"] not in state["revision_recovery_policy"]["excluded_claim_roots"]
    assert "c0_3" in state["story_board"]["spatial_content_plan"]["sections"][0]["claim_ids"]


def test_audit_distinguishes_superseded_from_applied_and_actual_missing(tmp_path):
    state = state_fixture(tmp_path)
    board = state["story_board"]
    board["spatial_content_plan"]["sections"][0]["importance_level"] = 3
    ops = [{"operation": "set_section_importance", "section_id": "s0", "importance_level": value, "operation_id": str(value)} for value in (1, 3)]
    state["revision_plan"] = {"operations": ops}
    state["revision_contract"] = build_contract(state, state["optimized_story_board"], board, ops)
    audit = operation_audit(state, board, [{}, {}])
    assert [entry["status"] for entry in audit] == ["superseded", "applied"]
    assert not compiled_contract_audit(state, [])["passed"]
    state["improve_safe_fallback"] = True
    assert all(item["status"] == "rolled_back" for item in operation_audit(state, board, [{}, {}]))


def test_admission_veto_preserves_raw_critic_and_blocks_promising(tmp_path):
    state = state_fixture(tmp_path)
    state["revision_safety_report"] = {"passed": False, "reasons": ["whole_poster_whitespace_regression"]}
    raw = {"archive_eligible": True, "overall_score": 96, "decision": "archive"}
    report = {**raw, "poster_evaluation": deepcopy(raw)}
    apply_revision_admission(state, report)
    assert not report["archive_eligible"] and not report["template_eligible"]
    assert report["overall_score"] == 96 and report["poster_evaluation"] == raw
    assert report["loop_disposition"] == "revision_safety_rejected"
    assert not assess_promising_candidate(report)["eligible"]


def test_exact_fallback_restores_policies_styles_and_digest(tmp_path):
    state = state_fixture(tmp_path)
    state.update(style_overrides={"accent_density": "reduced"}, layout_overrides={"section_gap_inches": 0.4},
                 color_scheme={"theme": "navy"}, keywords={"section_keywords": {}},
                 revision_recovery_policy={"excluded_visual_occurrences": [["s1", "figure_1"]]})
    snapshot = _prepare_improve_parent(state, {})
    state.update(style_overrides={"wrong": True}, layout_overrides={}, revision_recovery_policy={})
    state["verified_content_bank"] = {"claims": [{"claim_id": "new-committed"}]}
    assert _restore_exact_improve_parent(state)
    assert _exact_parent_restore_report(state)["status"] == "passed"
    assert state["revision_recovery_policy"] == snapshot["branch_controls"]["revision_recovery_policy"]
    assert state["verified_content_bank"]["claims"][0]["claim_id"] == "new-committed"
    state["layout_overrides"] = {}
    assert _exact_parent_restore_report(state)["status"] == "failed"


def test_fallback_palette_and_keywords_make_no_model_calls(tmp_path, monkeypatch):
    state = state_fixture(tmp_path)
    color = ColorAgent()
    font = FontAgent()
    state["improve_safe_fallback"] = True
    state["color_scheme"] = color._generate_color_scheme("#123456")
    state["keywords"] = {"section_keywords": {"s0": {"bold": ["Verified", "result"], "italic": [], "bold_contrast": []}}}
    state["style_overrides"] = {"accent_density": "reduced"}
    state["design_layout"] = [{"type": "text", "id": "s0_text", "content": "Verified result.",
                               "section_id": "s0", "font_family": "Arial", "font_size": 44}]
    frozen_palette, frozen_keywords = deepcopy(state["color_scheme"]), deepcopy(state["keywords"])
    def unexpected(*_):
        raise AssertionError("safe fallback must not call a model")
    monkeypatch.setattr(color, "_extract_theme_from_visuals", unexpected)
    monkeypatch.setattr(font, "_identify_keywords", unexpected)
    color(state)
    font(state)
    assert not state["errors"]
    assert state["keywords"] == frozen_keywords and state["color_scheme"] == frozen_palette


def test_failed_staged_repair_does_not_mutate_contract_or_policy(tmp_path, monkeypatch):
    state = state_fixture(tmp_path)
    state["critic_config"]["capacity_repair"] = {"enabled": True, "max_rounds_per_family": 1}
    state["revision_contract"] = build_contract(state, state["story_board"], state["story_board"], [])
    before = deepcopy(state["revision_contract"])
    policy = deepcopy(state["revision_recovery_policy"])
    report = {**metrics(fill=0.6, gap=5.0), "status": "feasible", "family_id": "top_hero_bottom_grid", "worst_zone_utilization": 0.6}
    monkeypatch.setattr(repair_module.CapacityActionPlanner, "plan_with_reason", lambda *_args, **_kwargs: ([{"operation": "add_existing_claim", "section_id": "s0"}], "test"))
    def failed_optimizer(trial, **_):
        trial["revision_contract"]["desired_board"] = {"changed": True}
        trial["revision_recovery_policy"]["unusable_visual_ids"] = ["figure_1"]
        trial["errors"] = ["verification failed"]
        return trial
    monkeypatch.setattr(repair_module, "content_optimizer", failed_optimizer)
    repair_module.repair_family_fit(MeasuredCompiler(), state, state["story_board"], "top_hero_bottom_grid", initial_report=report,
                                   initial_result=(state["story_board"], {"zones": []}, report))
    assert state["revision_contract"] == before
    assert state["revision_recovery_policy"] == policy


def test_legacy_lineage_load_clears_missing_policy_fields(tmp_path, monkeypatch):
    state = state_fixture(tmp_path)
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign(state, resume_mode="new")
    snapshot = {"candidate_id": "parent", "fields": {"story_board": state["story_board"], "critic_report": {"candidate_id": "parent"}}}
    monkeypatch.setattr(manager, "_select_lineage_parent", lambda *_: ("best", snapshot))
    state["revision_recovery_policy"] = {"unusable_visual_ids": ["figure_1"]}
    state["layout_overrides"] = {"section_gap_inches": 2.0}
    assert manager.load_lineage_snapshot(handle, "old", state)
    assert state["revision_recovery_policy"] is None and state["layout_overrides"] is None


def test_optional_snapshot_fields_and_mode_reset_are_scoped():
    required = {"revision_contract", "revision_recovery_policy", "revision_safety_report", "revision_execution_report", "layout_overrides"}
    assert required <= set(CampaignManager.LINEAGE_SNAPSHOT_FIELDS)
    assert required <= set(PosterOptimizationLoop.DESIGN_FIELDS)
    state = {"revision_contract": {"old": True}, "revision_safety_report": {"passed": False}, "revision_recovery_policy": {"branch": True}}
    _reset_attempt_diagnostics(state)
    assert state["revision_contract"] is None and state["revision_safety_report"] is None
    assert state["revision_recovery_policy"] == {"branch": True}


class MeasuredCompiler:
    """Deterministic measured elements; uses the production search/compiler."""
    poster_margin = 1.0
    title_height_fraction = 0.18
    layout_constants = {"body_render_reserve": 0.2}

    def _inter_section_spacing(self, state):
        return (state.get("layout_overrides") or {}).get("section_gap_inches") or 0.2

    def _calculate_precise_section_height(self, section, *_):
        return 1.0 + 0.6 * len(section.get("claim_ids", [])) + 2.0 * len(section.get("visual_assets", []))

    def _create_title_element(self, *_):
        return {"type": "title", "x": 1.0, "y": 1.0, "width": 30.0, "height": 3.0}

    def _create_logo_elements(self, *_):
        return []

    def _create_section_elements(self, section, x, y, width, state, available_height):
        text_height = 1.0 + 0.6 * len(section.get("claim_ids", []))
        elements = [{"type": "text", "id": f"{section['section_id']}_text", "section_id": section["section_id"],
                     "zone_id": section.get("layout_zone_id"), "x": x, "y": y, "width": width,
                     "height": text_height, "content": "\n".join(section.get("text_content", []))}]
        for index, visual in enumerate(section.get("visual_assets", [])):
            elements.append({"type": "visual", "section_id": section["section_id"], "zone_id": section.get("layout_zone_id"),
                             "visual_id": visual["visual_id"], "x": x, "y": y + text_height + index * 2.0,
                             "width": width, "height": 2.0})
        return elements

    def __call__(self, state, mode="final"):
        state["design_layout"] = compile_layout(self, state["optimized_story_board"], state, state["layout_spec"])
        return state


def test_real_planner_optimizer_solver_compile_handoff(tmp_path, monkeypatch):
    state = state_fixture(tmp_path)
    compiler = MeasuredCompiler()
    config = {"explore_layout": {"max_geometry_candidates_per_family": 4, "beam_width": 6, "minimum_sections": 5}}
    state["iteration_context"]["portfolio_mode"] = "explore"
    fitted, spec, report = fit_family_layout(compiler, state["story_board"], state, "top_hero_bottom_grid", config=config)
    state["iteration_context"]["portfolio_mode"] = "improve"
    state.update(story_board=deepcopy(fitted), optimized_story_board=deepcopy(fitted), layout_spec=spec, layout_feasibility_report=report)
    _prepare_improve_parent(state, {})
    fake_planner(monkeypatch, {"operations": [
        {"operation": "move_visual", "visual_id": "figure_1", "target_section_id": "s1"},
        {"operation": "set_section_importance", "section_id": "s1", "importance_level": 1},
        {"operation": "set_section_gap", "gap_inches": 0.4}], "content_actions": []})
    RevisionPlanner()(state)
    GroundedContentOptimizer()(state, actions_override=[], save=False)
    agent = LayoutWithBalancerAgent()
    agent.layout_agent = compiler
    state["critic_config"].update(config)
    agent._run_family_constraint_engine(state, "top_hero_bottom_grid")
    assert not state["errors"]
    audit = compiled_contract_audit(state, state["design_layout"])
    assert audit["passed"], audit
    assert ("s1", "figure_1") in {(item.get("section_id"), item.get("visual_id")) for item in state["design_layout"]}
    assert all(item["status"] in {"applied", "already_satisfied"} for item in state["revision_execution_report"]["operation_results"])
    state["styled_layout"] = deepcopy(state["design_layout"])
    layout_preflight_node(state)
    assert not state["layout_preflight_failed"], state["layout_preflight_report"]
    assert state["revision_execution_report"]["compiled_contract_check"]["passed"]


def test_compiled_audit_catches_text_loss_even_with_present_container(tmp_path):
    state = state_fixture(tmp_path)
    state["revision_contract"] = build_contract(state, state["story_board"], state["story_board"], [])
    layout = [{"type": "section_container", "section_id": "s0", "importance_level": 2}]
    report = compiled_contract_audit(state, layout)
    assert not report["passed"]
    assert any(issue["code"] == "compiled_scientific_text_mismatch" for issue in report["violations"])


def test_compiled_text_audit_respects_renderer_literal_escapes(tmp_path):
    state = state_fixture(tmp_path)
    module = state["story_board"]["spatial_content_plan"]["sections"][1]
    module["text_content"] = [r"Value a*b with \alpha and **literal stars**."]
    state["story_board"]["spatial_content_plan"]["sections"] = [module]
    state["optimized_story_board"] = deepcopy(state["story_board"])
    state["revision_contract"] = build_contract(state, state["story_board"], state["story_board"], [])
    content = FontAgent._escape_formatting_literals(module["text_content"][0])
    content = content.replace("Value", "**Value**")
    layout = [{"type": "section_container", "section_id": "s1", "importance_level": 2},
              {"type": "text", "section_id": "s1", "content": content}]
    assert compiled_contract_audit(state, layout)["passed"]


def test_layout_guard_performs_one_refit_and_records_revocation(tmp_path, monkeypatch):
    state = state_fixture(tmp_path)
    parent = deepcopy(state["story_board"])
    op = {"operation": "remove_visual", "operation_id": "remove", "section_id": "s0", "visual_id": "figure_1"}
    revised = deepcopy(parent)
    revised["spatial_content_plan"]["sections"][0]["visual_assets"] = []
    state.update(story_board=revised, revision_parent_story_board=parent, revision_plan={"operations": [op]})
    state["revision_contract"] = build_contract(state, parent, revised, [op])
    state["improve_parent_snapshot"] = {"effective_board": parent, "fit_report": metrics()}
    state["layout_revision_constraints"] = {}
    calls = []

    def fake_fit(_agent, board, *_args, **_kwargs):
        calls.append(deepcopy(board))
        has_visual = bool(board["spatial_content_plan"]["sections"][0]["visual_assets"])
        return deepcopy(board), {"family_id": "top_hero_bottom_grid", "zones": []}, {
            **metrics(fill=0.97 if has_visual else 0.7, empty=0.08 if has_visual else 0.2), "status": "feasible"}

    monkeypatch.setattr(layout_module, "fit_family_layout", fake_fit)
    monkeypatch.setattr(layout_module, "needs_feasible_repair", lambda *_: False)
    monkeypatch.setattr(layout_module, "important_visual_omitted", lambda *_: False)
    monkeypatch.setattr(layout_module, "validate_compiled_layout", lambda *_args, **_kwargs: {"passed": True, "issues": []})
    agent = LayoutWithBalancerAgent()
    agent.layout_agent = type("PassThrough", (), {
        "poster_margin": 1.0, "title_height_fraction": 0.18,
        "__call__": lambda self, state, **_: state,
    })()
    agent._run_family_constraint_engine(state, "top_hero_bottom_grid")
    assert len(calls) == 2
    assert not state["errors"]
    assert state["revision_safety_report"]["rollback_status"] == "revoked_and_refitted"
    assert state["revision_execution_report"]["operation_results"][0]["status"] == "revoked"
