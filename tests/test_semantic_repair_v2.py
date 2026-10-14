"""Correct arbitrary module associations, then use ordinary poster admission."""
from copy import deepcopy
from pathlib import Path

import pytest

import src.agents.module_consistency as repair
from src.agents.revision_contract import board_identity, check_contract, operation_audit
from src.config.critic_config import load_critic_config
from src.layout.feasibility import LayoutFeasibilityError
from src.semantic.consistency import sections, audit_board, visible_board
from src.templates.library import LoopStorage
from src.workflow.optimization_loop import PosterOptimizationLoop
from src.workflow.campaign_runner import _reset_attempt_diagnostics
from test_module_consistency import fixture, answer, fake_model, compiled, fit_report


def wrong_visual(state, kind="figure"):
    modules = sections(state["story_board"])
    # Both are custom subtopics, not a method/results dispatch table.
    modules[0].update(section_id="cohort_a", section_title="First Cohort Analysis")
    modules[1].update(section_id="cohort_b", section_title="Second Cohort Analysis")
    if kind == "table":
        state["tables"]["1"] = state["images"].pop("1")
        state["tables"]["1"]["caption"] = "Table 7. Experimental comparison with baseline approaches."
        state["raw_text"] += "\n" + state["tables"]["1"]["caption"]
    vid = kind + "_1"
    modules[0]["visual_assets"] = [{"visual_id": vid}]
    modules[1]["visual_assets"] = []
    proposal = {"operation": "move_visual", "section_id": "cohort_a", "target_section_id": "cohort_b",
                "visual_id": vid, "issue_kind": "visual", "issue_id": vid}
    return proposal


def review(proposal):
    def response(payload):
        wrong = payload["section_id"] == proposal["section_id"] and any(
            v["visual_id"] == proposal["visual_id"] for v in payload["visuals"])
        result = answer(payload, fail=("visual", proposal["visual_id"]) if wrong else None)
        if wrong:
            result["repair_proposals"] = [proposal]
        return result
    return response


def fake_fit(monkeypatch, callback=None):
    import src.agents.layout_agent as layout
    import src.agents.font_agent as font
    import src.agents.layout_preflight as preflight
    import src.layout.feasibility as feasibility
    calls = []
    class Layout:
        def __call__(self, state, mode="final"):
            compiled(state)
            state["design_layout"] = deepcopy(state["styled_layout"])
            return state
    def fit(agent, board, state, family_id, **kwargs):
        calls.append(deepcopy(state["semantic_refit_constraints"]))
        if callback:
            return callback(board, state, len(calls))
        return deepcopy(board), deepcopy(state["layout_spec"]), {**fit_report(), "status": "feasible"}
    monkeypatch.setattr(layout, "LayoutAgent", Layout)
    monkeypatch.setattr(feasibility, "fit_family_layout", fit)
    monkeypatch.setattr(font.FontAgent, "_apply_styling", lambda self, design, *args: deepcopy(design))
    def passed(state, **kwargs):
        state["layout_preflight_report"] = {"passed": True, "status": "passed"}
        return state
    monkeypatch.setattr(preflight, "layout_preflight_node", passed)
    return calls


def add_spec(state):
    state["layout_spec"] = {"family_id": "asymmetric_two_column", "zones": [
        {"zone_id": "a", "section_ids": [sections(state["story_board"])[0]["section_id"]]},
        {"zone_id": "b", "section_ids": [sections(state["story_board"])[1]["section_id"]]}]}
    state["layout_feasibility_report"] = fit_report()


@pytest.mark.parametrize("kind", ["figure", "table"])
@pytest.mark.parametrize("mode", ["explore", "improve"])
def test_arbitrary_module_move_has_no_old_render_or_relative_quality_gate(tmp_path, monkeypatch, kind, mode):
    state = fixture(tmp_path)
    proposal = wrong_visual(state, kind)
    state["iteration_context"]["portfolio_mode"] = mode
    state["module_semantic_repair_baseline"] = {"dimension_scores": {"aesthetics": 100}}
    add_spec(state)
    compiled(state)
    if mode == "improve":
        state["revision_contract"] = {"desired_board": board_identity(state["story_board"])}
    fake_model(monkeypatch, review(proposal))
    calls = fake_fit(monkeypatch)
    monkeypatch.setattr(repair, "_content_actions", lambda *_: [])
    monkeypatch.setattr("src.agents.renderer.renderer_node", lambda *_: pytest.fail("No baseline render allowed"))
    monkeypatch.setattr("src.critic.engine.PosterCritic.__call__", lambda *_: pytest.fail("No baseline Critic allowed"))
    repair.module_semantic_finalize_node(state)
    assert not state["module_semantic_blocked"]
    modules = sections(visible_board(state))
    assert modules[0]["visual_assets"] == []
    assert modules[1]["visual_assets"] == [{"visual_id": proposal["visual_id"]}]
    assert state["layout_visual_source_manifest"] == {"cohort_b": [proposal["visual_id"]]}
    assert "module_semantic_repair_baseline" not in state
    assert len(calls) == 1 and len(calls[0]["must_retain_claim_ids"]) == 3
    assert calls[0]["must_retain_visual_ids"] == [proposal["visual_id"]]
    assert state["module_semantic_repair_report"]["status"] == "repaired"
    assert check_contract(state, visible_board(state))["passed"]


@pytest.mark.parametrize("violation", ["unrelated_title", "excluded_target", "unusable", "missing_confirmation"])
def test_contract_amendment_does_not_waive_unrelated_or_excluded_content(tmp_path, monkeypatch, violation):
    state = fixture(tmp_path)
    proposal = wrong_visual(state)
    before = deepcopy(state["story_board"])
    fake_model(monkeypatch, review(proposal))
    state["module_consistency_report"] = audit_board(state, before)
    after = repair.apply_semantic_proposal(before, state["module_consistency_report"], proposal, state)
    state["revision_contract"] = {"desired_board": board_identity(before)}
    if violation == "unrelated_title":
        sections(after)[1]["section_title"] = "Unapproved title"
    elif violation == "excluded_target":
        state["revision_recovery_policy"] = {"excluded_visual_occurrences": [["cohort_b", "figure_1"]]}
    elif violation == "unusable":
        state["revision_recovery_policy"] = {"unusable_visual_ids": ["figure_1"]}
    else:
        state["module_consistency_report"] = {"modules": []}
    assert not repair._amend_contract(state, before, after, [proposal])


def test_superseded_planner_effect_is_explained_not_reported_applied(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    proposal = wrong_visual(state)
    proposal["policy"] = "untrusted_model_metadata"
    before = deepcopy(state["story_board"])
    state["revision_parent_story_board"] = deepcopy(before)
    state["revision_plan"] = {"operations": [{"operation": "move_visual", "operation_id": "old_move",
        "section_id": "cohort_b", "target_section_id": "cohort_a", "visual_id": "figure_1"}]}
    fake_model(monkeypatch, review(proposal))
    state["module_consistency_report"] = audit_board(state, before)
    after = repair.apply_semantic_proposal(before, state["module_consistency_report"], proposal, state)
    state["revision_contract"] = {"desired_board": board_identity(before)}
    assert repair._amend_contract(state, before, after, [proposal])
    assert state["revision_contract"]["semantic_amendments"][0]["policy"] == repair.REPAIR_POLICY
    entry = operation_audit(state, after, [{}])[0]
    assert entry["status"] == "superseded"
    assert "source-confirmed semantic repair" in entry["detail"]


@pytest.mark.parametrize("bad", ["lost_root", "wrong_owner", "unverified_wording", "unapproved_addition", "dropped_visual"])
def test_content_adjustment_inventory_is_strict(tmp_path, bad):
    state = fixture(tmp_path)
    before = deepcopy(state["story_board"])
    after = deepcopy(before)
    module = sections(after)[0]
    variant = {"claim_id": "short", "root_claim_id": "c1", "text": "Related graph observations.", "verified": True}
    state["verified_content_bank"]["claims"] = [variant]
    module["claim_ids"][1] = "short"
    module["text_content"][1] = variant["text"]
    actions = [{"operation": "use_claim_variant", "section_id": "method", "claim_id": "c1", "variant_id": "short", "result_claim_ids": ["c0", "short"]}]
    assert repair._content_changes_safe(before, after, state, actions, {"method"})
    if bad == "lost_root":
        variant["root_claim_id"] = "other_root"
    elif bad == "wrong_owner":
        sections(after)[1]["claim_ids"].append(module["claim_ids"].pop())
        sections(after)[1]["text_content"].append(module["text_content"].pop())
    elif bad == "unverified_wording":
        module["text_content"][1] = "Invented scientific result"
    elif bad == "unapproved_addition":
        module["claim_ids"].append("c2")
        module["text_content"].append(state["verified_claims"]["claims"][2]["text"])
    else:
        sections(after)[1]["visual_assets"] = []
    assert not repair._content_changes_safe(before, after, state, actions, {"method"})


@pytest.mark.parametrize("fail_second", [False, True])
def test_bounded_compaction_uses_corrected_board_and_never_leaks_staged_bank(tmp_path, monkeypatch, fail_second):
    state = fixture(tmp_path)
    proposal = wrong_visual(state)
    add_spec(state)
    fake_model(monkeypatch, review(proposal))
    state["module_consistency_report"] = audit_board(state, state["story_board"])
    proposed = repair.apply_semantic_proposal(state["story_board"], state["module_consistency_report"], proposal, state)
    original_bank = deepcopy(state["verified_content_bank"])
    def fit(board, trial, number):
        if number == 1 or fail_second:
            raise LayoutFeasibilityError("measured capacity", {"reason_code": "NO_FAST_FEASIBLE_VARIANT"})
        return deepcopy(board), deepcopy(trial["layout_spec"]), {**fit_report(), "status": "feasible"}
    calls = fake_fit(monkeypatch, fit)
    monkeypatch.setattr(repair, "_content_actions", lambda *_: [{"operation": "create_compact_variant", "section_id": "cohort_a", "claim_id": "c1"}])
    def optimize(self, trial, **kwargs):
        assert sections(kwargs["board_override"])[1]["visual_assets"] == [{"visual_id": "figure_1"}]
        variant = {"claim_id": "compact", "root_claim_id": "c1", "text": "Related graph observations.", "verified": True}
        trial["verified_content_bank"]["claims"].append(variant)
        trial["story_board"] = deepcopy(kwargs["board_override"])
        section = sections(trial["story_board"])[0]
        section["claim_ids"][1] = "compact"
        section["text_content"][1] = variant["text"]
        trial["content_revision"] = {"accepted_actions": [{"operation": "create_compact_variant", "section_id": "cohort_a", "claim_id": "c1", "result_claim_ids": ["c0", "compact"]}]}
        return trial
    monkeypatch.setattr("src.agents.content_optimizer.GroundedContentOptimizer.__call__", optimize)
    audit = {}
    result, reason = repair._refit(state, proposed, proposals=[proposal], audit=audit)
    assert len(calls) == 2 and audit["content_rounds_attempted"] == 1
    assert state["verified_content_bank"] == original_bank
    if fail_second:
        assert result is None and reason == "corrected_association_layout_infeasible"
    else:
        assert result["verified_content_bank"]["claims"][-1]["claim_id"] == "compact"
        assert calls[1]["must_retain_claim_ids"] == ["c0", "compact", "c2"]
        assert "semantic_refit_constraints" not in result


def test_shared_content_budget_exhaustion_skips_optimizer(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    proposal = wrong_visual(state)
    add_spec(state)
    fake_model(monkeypatch, review(proposal))
    state["module_consistency_report"] = audit_board(state, state["story_board"])
    proposed = repair.apply_semantic_proposal(state["story_board"], state["module_consistency_report"], proposal, state)
    state["iteration_context"]["capacity_repair_remaining"] = 2
    state["capacity_repair_report"] = {"rounds_attempted": 2}
    calls = fake_fit(monkeypatch)
    monkeypatch.setattr(repair, "_content_actions", lambda *_: pytest.fail("Existing layout work spent the remaining budget"))
    result, reason = repair._refit(state, proposed, proposals=[proposal])
    assert result is not None and reason == "passed" and len(calls) == 1


@pytest.mark.parametrize("unavailable", ["disabled", "no_text_model"])
def test_optional_text_work_skips_when_unavailable(tmp_path, monkeypatch, unavailable):
    state = fixture(tmp_path)
    proposal = wrong_visual(state)
    add_spec(state)
    fake_model(monkeypatch, review(proposal))
    state["module_consistency_report"] = audit_board(state, state["story_board"])
    proposed = repair.apply_semantic_proposal(state["story_board"], state["module_consistency_report"], proposal, state)
    if unavailable == "disabled":
        state["critic_config"]["content_optimization"]["enabled"] = False
    else:
        state["text_model"] = None
    calls = fake_fit(monkeypatch)
    monkeypatch.setattr(repair, "_content_actions", lambda *_: pytest.fail("Unavailable optional work must be skipped"))
    result, reason = repair._refit(state, proposed, proposals=[proposal])
    assert result is not None and reason == "passed" and len(calls) == 1


@pytest.mark.parametrize("accepted", [True, False])
def test_normal_loop_admission_ignores_old_baseline_and_keeps_quality_rejection(tmp_path, accepted):
    from test_campaign_resume import _state, _render_candidate
    config = load_critic_config()
    def render(state):
        _render_candidate(state)
        # Simulate a historical field; the active runner must not apply it.
        state["module_semantic_repair_baseline"] = {"dimension_scores": {"aesthetics": 100}}
        state["module_consistency_report"] = {"status": "passed"}
        state["module_semantic_repair_report"] = {"policy": repair.REPAIR_POLICY, "status": "repaired"}
        return state
    def critic(state):
        state["critic_report"] = {"candidate_id": state["current_candidate"]["candidate_id"],
            "iteration": state["iteration_context"]["iteration"], "decision": "archive" if accepted else "discard",
            "archive_eligible": accepted, "template_eligible": accepted, "overall_score": 90 if accepted else 70,
            "dimension_scores": {"aesthetics": 88, "scientific_integrity": 100}, "issues": [],
            "rubric_version": config["rubric_version"], "critic_system_version": config["critic_system_version"],
            "rejection_summary": "", "module_consistency": {"status": "passed"}}
        return state
    loop = PosterOptimizationLoop(config=config, batch_iterations=1, batch_mode="explore",
        fresh_design_nodes=[render], critic=critic, storage=LoopStorage(tmp_path / "store", config))
    summary = loop.run(_state(tmp_path / "run"), foundation_ready=True)["loop_state"]
    assert summary["status"] == "COMPLETED"
    assert summary["accepted_count"] == summary["template_count"] == int(accepted)
    assert summary["rejected_count"] == int(not accepted)
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    assert len(list(campaign.glob("iterations/*/COMPLETED.json"))) == 1


def test_retired_runtime_fields_are_cleared():
    state = {"module_semantic_repair_baseline": {"dimension_scores": {}}, "semantic_refit_constraints": {"policy": repair.REPAIR_POLICY}}
    _reset_attempt_diagnostics(state)
    assert "module_semantic_repair_baseline" not in state and "semantic_refit_constraints" not in state


def test_sparse_action_selection_supports_custom_modules_and_true_evidence(tmp_path):
    state = fixture(tmp_path)
    proposal = wrong_visual(state)
    add_spec(state)
    report = {"status": "feasible", "zone_utilization": {"a": 0.5, "b": 0.98},
              "exact_bottom_gaps": {"a": 4, "b": 0.1}, "selected_layout_spec": state["layout_spec"]}
    actions = repair._content_actions(state, state["story_board"], report, {"cohort_a", "cohort_b"})
    assert len(actions) == 1 and actions[0]["operation"] == "add_claim_from_evidence"
    assert actions[0]["evidence_ids"] == ["e0", "e1"]
    state["verified_content_bank"]["claims"].append({"claim_id": "detail", "text": "Supported detail",
                                                    "evidence_ids": ["e0"], "verified": True})
    actions = repair._content_actions(state, state["story_board"], report, {"cohort_a"})
    assert actions[0]["operation"] == "add_existing_claim" and actions[0]["claim_id"] == "detail"
    assert repair._content_actions(state, state["story_board"], report, {"cohort_b"}) == []


@pytest.mark.parametrize("reject_text", [False, True])
def test_optional_addition_failure_retains_feasible_corrected_fit(tmp_path, monkeypatch, reject_text):
    state = fixture(tmp_path)
    proposal = wrong_visual(state)
    add_spec(state)
    fake_model(monkeypatch, review(proposal))
    state["module_consistency_report"] = audit_board(state, state["story_board"])
    proposed = repair.apply_semantic_proposal(state["story_board"], state["module_consistency_report"], proposal, state)
    def fit(board, trial, number):
        if number == 2:
            raise LayoutFeasibilityError("supplement did not fit", {})
        return deepcopy(board), deepcopy(trial["layout_spec"]), {**fit_report(), "status": "feasible"}
    calls = fake_fit(monkeypatch, fit)
    monkeypatch.setattr(repair, "_content_actions", lambda *_: [{"operation": "add_claim_from_evidence", "section_id": "cohort_a"}])
    def optimize(self, trial, **kwargs):
        trial["story_board"] = deepcopy(kwargs["board_override"])
        variant = {"claim_id": "detail", "root_claim_id": "detail", "text": "Verified additional detail", "verified": True}
        trial["verified_content_bank"]["claims"].append(variant)
        trial["supplemental_evidence_bank"]["items"].append({"evidence_id": "new_source"})
        module = sections(trial["story_board"])[0]
        module["claim_ids"].append("detail")
        module["text_content"].append(variant["text"])
        trial["content_revision"] = {"accepted_actions": [] if reject_text else [{
            "operation": "add_claim_from_evidence", "section_id": "cohort_a", "result_claim_ids": module["claim_ids"]}]}
        return trial
    monkeypatch.setattr("src.agents.content_optimizer.GroundedContentOptimizer.__call__", optimize)
    audit = {}
    result, reason = repair._refit(state, proposed, proposals=[proposal], audit=audit)
    assert reason == "passed" and result is not None
    assert len(calls) == (1 if reject_text else 2)
    assert visible_board(result) == proposed
    assert result["verified_content_bank"]["claims"] == []
    assert result["supplemental_evidence_bank"]["items"] == []
    assert state["verified_content_bank"]["claims"] == []
    assert audit["content_status"] in {"not_adopted", "rolled_back_to_corrected_fit"}


def test_corrected_candidate_still_requires_preflight(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    add_spec(state)
    fake_fit(monkeypatch)
    def failed(trial, **kwargs):
        trial["layout_preflight_failed"] = True
        trial["layout_preflight_report"] = {"passed": False, "issues": [{"code": "OVERFLOW"}]}
    monkeypatch.setattr("src.agents.layout_preflight.layout_preflight_node", failed)
    result, reason = repair._refit(state, state["story_board"])
    assert result is None and reason == "repair_preflight_failed"
    assert not state.get("layout_preflight_failed")


def test_unexpected_refit_failure_propagates_without_rejection(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    add_spec(state)
    def bug(*args):
        raise TypeError("injected layout programming error")
    fake_fit(monkeypatch, bug)
    with pytest.raises(TypeError, match="programming error"):
        repair._refit(state, state["story_board"])
    assert state["verified_content_bank"]["claims"] == []


def test_verified_additions_preserve_all_existing_roots(tmp_path):
    state = fixture(tmp_path)
    before = deepcopy(state["story_board"])
    after = deepcopy(before)
    extra = {"claim_id": "detail", "root_claim_id": "detail", "text": "Verified detail", "verified": True}
    state["verified_content_bank"]["claims"].append(extra)
    section = sections(after)[0]
    section["claim_ids"].append("detail")
    section["text_content"].append(extra["text"])
    actions = [{"operation": "add_claim_from_evidence", "section_id": "method", "result_claim_ids": section["claim_ids"]}]
    assert repair._content_changes_safe(before, after, state, actions, {"method"})
    section["claim_ids"].pop(0)
    section["text_content"].pop(0)
    assert not repair._content_changes_safe(before, after, state, actions, {"method"})


def test_sparse_fill_cannot_reintroduce_visible_root_variant_or_excluded_claim(tmp_path):
    state = fixture(tmp_path)
    wrong_visual(state)
    add_spec(state)
    state["verified_content_bank"]["claims"].append({"claim_id": "duplicate_variant", "root_claim_id": "c0",
        "text": "Same scientific claim", "evidence_ids": ["e0"], "verified": True})
    report = {"status": "feasible", "zone_utilization": {"a": 0.5}, "exact_bottom_gaps": {"a": 4},
              "selected_layout_spec": state["layout_spec"]}
    actions = repair._content_actions(state, state["story_board"], report, {"cohort_a"})
    assert actions[0]["operation"] == "add_claim_from_evidence"
    state["verified_content_bank"]["claims"].append({"claim_id": "excluded_detail", "text": "Excluded detail",
        "evidence_ids": ["e0"], "verified": True})
    state["revision_recovery_policy"] = {"excluded_claim_roots": [["cohort_a", "excluded_detail"]]}
    assert repair._content_actions(state, state["story_board"], report, {"cohort_a"})[0]["operation"] == "add_claim_from_evidence"
    before = deepcopy(state["story_board"])
    after = deepcopy(before)
    sections(after)[0]["claim_ids"].append("duplicate_variant")
    sections(after)[0]["text_content"].append("Same scientific claim")
    assert not repair._content_changes_safe(before, after, state, [{"operation": "add_existing_claim", "section_id": "cohort_a",
        "result_claim_ids": sections(after)[0]["claim_ids"]}], {"cohort_a"})
