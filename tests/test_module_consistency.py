"""Source/module contracts, conservative repairs and crash-safe loop outcomes."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import src.semantic.consistency as semantic
import src.agents.module_consistency as agent
from src.agents.grounded_curator import GroundedCurator
from src.agents.font_agent import FontAgent
from src.agents.content_optimizer import GroundedContentOptimizer
from src.critic.base import CriticContext
from src.critic.module_consistency import ModuleConsistencyEvaluator
from src.config.critic_config import load_critic_config
from src.state.poster_state import ModelConfig, TokenUsage
from src.templates.library import LoopStorage
from src.workflow.campaign import CampaignManager
from src.workflow.campaign_runner import _reset_attempt_diagnostics, _reconcile_template_usage
from src.workflow.global_knowledge import GlobalDesignKnowledge
from src.workflow.optimization_loop import PosterOptimizationLoop
from src.workflow.portfolio import assess_promising_candidate


def fixture(tmp_path):
    path = tmp_path / "figure.png"
    Image.new("RGB", (100, 50), "white").save(path)
    texts = ["The algorithm builds a graph from observed features.",
             "The method connects related observations in the graph.",
             "The experiment compares the method with baseline approaches."]
    caption = "Figure 7. Experimental comparison with baseline approaches."
    claims = [{"claim_id": f"c{i}", "text": text, "evidence_ids": [f"e{i}"],
               "section_id": "method" if i < 2 else "results", "verified": True}
              for i, text in enumerate(texts)]
    state = {"generation_route": "optimization_family", "output_dir": str(tmp_path / "out"),
             "poster_name": "semantic", "poster_width": 54, "poster_height": 36,
             "raw_text": "\n\n".join(texts + [caption]),
             "section_chunks": [{"section_id": "source-method", "content": "\n\n".join(texts[:2])},
                                {"section_id": "source-results", "content": texts[2] + "\n\n" + caption}],
             "images": {"1": {"path": str(path), "caption": caption, "caption_provenance": "grouped"}},
             "tables": {}, "verified_claims": {"claims": claims},
             "evidence_bank": {"items": [{"evidence_id": f"e{i}", "source_excerpt": text,
                                          "source": {"section_id": f"source-{i}"}} for i, text in enumerate(texts)]},
             "verified_content_bank": {"claims": []}, "supplemental_evidence_bank": {"items": []},
             "content_selection": {}, "tokens": TokenUsage(), "errors": [],
             "text_model": ModelConfig("fake", "local"), "critic_config": load_critic_config(),
             "iteration_context": {"iteration": 1, "portfolio_mode": "explore"}}
    state["story_board"] = {"spatial_content_plan": {"sections": [
        {"section_id": "method", "section_title": "Graph Construction", "claim_ids": ["c0", "c1"],
         "text_content": texts[:2], "visual_assets": []},
        {"section_id": "results", "section_title": "Baseline Comparison", "claim_ids": ["c2"],
         "text_content": texts[2:], "visual_assets": [{"visual_id": "figure_1"}]}]}}
    return state


def answer(payload, *, fail=None):
    source_id = next(sid for sid, value in payload["sources"].items() if value["kind"] == "evidence")
    def cite(sid):
        return {"source_id": sid, "quote": payload["sources"][sid]["text"]}
    checks = [{"kind": kind, "id": payload["section_id"], "status": "passed",
               "reason_code": "source_supported", "basis": [cite(source_id)]} for kind in ("title", "module")]
    checks.extend({"kind": "claim", "id": c["claim_id"], "status": "passed", "reason_code": "relevant",
                   "basis": [cite(f"evidence:{c['evidence_ids'][0]}")]} for c in payload["claims"])
    checks.extend({"kind": "visual", "id": v["visual_id"], "status": "passed", "reason_code": "same_experiment",
                   "image_examined": True,
                   "basis": [cite(v["caption_source_id"]), cite(source_id)]} for v in payload["visuals"])
    if fail:
        for check in checks:
            if (check["kind"], check["id"]) == fail:
                check.update(status="failed", reason_code="different_experiment")
    return {"theme": payload["title"], "theme_evidence_ids": [source_id.removeprefix("evidence:")],
            "checks": checks, "dependencies": [], "repair_proposals": []}


def fake_model(monkeypatch, callback=answer):
    calls = []
    def call(state, prompt, payload):
        calls.append((prompt, deepcopy(payload)))
        return callback(payload)
    monkeypatch.setattr(semantic, "_call", call)
    return calls


def compiled(state):
    font = FontAgent()
    layout = []
    for module in semantic.sections(semantic.visible_board(state)):
        sid = module["section_id"]
        layout.extend([{"type": "section_container", "section_id": sid},
                       {"type": "section_title", "section_id": sid, "section_title": module["section_title"]},
                       {"type": "text", "section_id": sid,
                        "content": font._escape_formatting_literals(font._format_bullet_points("\n".join(module["text_content"])))}])
        layout.extend({"type": "visual", "section_id": sid, "visual_id": v["visual_id"]} for v in module["visual_assets"])
    state["styled_layout"] = layout


def test_index_uses_paper_number_not_asset_sequence(tmp_path):
    state = fixture(tmp_path)
    index = semantic.build_paper_index(state)
    visual = index["visuals"]["figure_1"]
    assert visual["paper_reference"] == ("figure", "7")
    assert visual["association_status"] == "supported"
    assert visual["reference_source_ids"]
    assert all(e["verified"] for e in index["evidence"].values())


@pytest.mark.parametrize("kind", ["generic", "absent", "ambiguous", "duplicate_label", "asset_missing"])
def test_uncertain_visual_source_is_never_certified(tmp_path, monkeypatch, kind):
    state = fixture(tmp_path)
    if kind == "generic":
        state["images"]["1"]["caption"] = "Figure 1"
    elif kind == "absent":
        state["images"]["1"]["caption"] = "Figure 7. An invented caption."
    elif kind == "ambiguous":
        state["images"]["1"]["caption_provenance"] = "ambiguous"
    elif kind == "duplicate_label":
        state["images"]["2"] = deepcopy(state["images"]["1"])
    else:
        state["images"]["1"]["path"] = str(tmp_path / "missing.png")
    calls = fake_model(monkeypatch)
    report = semantic.audit_board(state, state["story_board"])
    assert report["status"] == "inconclusive"
    assert len(calls) == 1  # unrelated text-only module can still be checked


def test_coherent_cross_chapter_claims_are_not_rejected_by_origin_ids(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    state["verified_claims"]["claims"][1]["section_id"] = "another-narrative-section"
    fake_model(monkeypatch)
    assert semantic.audit_board(state, state["story_board"])["status"] == "passed"


def test_confirmed_mismatch_and_disagreement_have_distinct_status(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    raw = deepcopy(state["story_board"])
    raw["spatial_content_plan"]["sections"][0]["visual_assets"] = [{"visual_id": "figure_1"}]
    raw["spatial_content_plan"]["sections"][1]["visual_assets"] = []
    fake_model(monkeypatch, lambda p: answer(p, fail=("visual", "figure_1")))
    assert semantic.audit_board(state, raw)["status"] == "failed"
    state["module_semantic_cache"] = {}
    def disagree(state, prompt, payload):
        return answer(payload, fail=None if "confirm" in prompt else ("visual", "figure_1"))
    monkeypatch.setattr(semantic, "_call", disagree)
    report = semantic.audit_board(state, raw)
    assert report["status"] == "inconclusive"
    assert not any(c["status"] == "failed" for m in report["modules"] for c in m["checks"])


@pytest.mark.parametrize("bad", ["missing", "duplicate", "fake_quote", "wrong_claim_source", "caption_only", "bad_shape"])
def test_complete_object_scoped_source_checks_required(tmp_path, monkeypatch, bad):
    state = fixture(tmp_path)
    def invalid(payload):
        response = answer(payload)
        if bad == "missing":
            response["checks"].pop()
        elif bad == "duplicate":
            response["checks"].append(deepcopy(response["checks"][0]))
        elif bad == "fake_quote":
            response["checks"][0]["basis"][0]["quote"] = "a sentence that does not exist"
        elif bad == "wrong_claim_source" and len(payload["claims"]) > 1:
            response["checks"][3]["basis"] = response["checks"][2]["basis"]
        elif bad == "caption_only" and payload["visuals"]:
            response["checks"][-1]["basis"].pop()
        elif bad == "bad_shape":
            response["checks"] = {"status": "passed"}
        return response
    fake_model(monkeypatch, invalid)
    assert semantic.audit_board(state, state["story_board"])["status"] == "inconclusive"


def test_cache_reuses_geometry_only_and_invalidates_changed_title_source_asset(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    calls = fake_model(monkeypatch)
    semantic.audit_board(state, state["story_board"], refresh_index=True)
    assert len(calls) == 2
    state["layout_spec"] = {"zones": [{"x": 0.2}]}
    semantic.audit_board(state, state["story_board"], refresh_index=True)
    assert len(calls) == 2
    state["story_board"]["spatial_content_plan"]["sections"][0]["section_title"] = "Graph Method"
    semantic.audit_board(state, state["story_board"])
    assert len(calls) == 3
    Image.new("RGB", (100, 50), "red").save(state["images"]["1"]["path"])
    semantic.audit_board(state, state["story_board"], refresh_index=True)
    assert len(calls) == 5
    state["critic_config"]["module_consistency"]["cache_entries"] = 1
    semantic.audit_board(state, state["story_board"])
    assert len(state["module_semantic_cache"]) == 1


def test_unavailable_checks_not_cached_or_mislabeled(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    state["text_model"] = None
    report = semantic.audit_board(state, state["story_board"])
    assert report["status"] == "inconclusive"
    assert state["module_semantic_cache"] == {}
    assert semantic._call(state, "unused", {"long": "x" * 100000})["unavailable_reason"] == "payload_budget"
    state["module_semantic_runtime"]["model_calls"] = 32
    assert semantic._call(state, "unused", {})["unavailable_reason"] == "call_budget"


def test_family_curator_does_not_fill_unrelated_module_or_truncate_title(tmp_path):
    state = fixture(tmp_path)
    title = "Graph Construction Under Restricted Observation Conditions"
    raw = {"spatial_content_plan": {"sections": [{"section_id": "method", "section_title": title,
                                                "claim_ids": ["c0"], "visual_assets": []}]}}
    board = GroundedCurator()._materialize(raw, semantic.all_publishable_claims(state), {}, {}, family_mode=True)
    assert semantic.sections(board)[0]["claim_ids"] == ["c0", "c1"]
    assert board["unselected_claim_ids"] == ["c2"]
    assert semantic.sections(board)[0]["section_title"] == title
    classic = GroundedCurator()._materialize(raw, semantic.all_publishable_claims(state), {}, {})
    assert len(semantic.sections(classic)[0]["claim_ids"]) == 3
    assert len(semantic.sections(classic)[0]["section_title"].split()) == 5


def test_dependency_selection_supports_verified_short_variants(tmp_path):
    state = fixture(tmp_path)
    state["module_semantic_contracts"] = {"results": {"dependencies": [{"visual_id": "figure_1", "required_claim_ids": ["c2"]}]}}
    section = deepcopy(semantic.sections(state["story_board"])[1])
    assert semantic.dependency_safe(section, state)
    section["claim_ids"] = ["c0"]
    assert not semantic.dependency_safe(section, state)
    state["verified_content_bank"]["claims"] = [{"claim_id": "short", "root_claim_id": "c2", "verified": True}]
    section["claim_ids"] = ["short"]
    assert semantic.dependency_safe(section, state)


@pytest.mark.parametrize("change", ["title", "text", "visual", "asset", "stale_board"])
def test_critic_gate_binds_final_renderer_inputs(tmp_path, monkeypatch, change):
    state = fixture(tmp_path)
    fake_model(monkeypatch)
    state["module_consistency_report"] = semantic.audit_board(state, state["story_board"])
    compiled(state)
    context = CriticContext(state, state["critic_config"])
    assert ModuleConsistencyEvaluator().evaluate(context).passed
    if change == "title":
        state["styled_layout"][1]["section_title"] = "Unsupported Conclusion"
    elif change == "text":
        next(e for e in state["styled_layout"] if e["type"] == "text")["content"] += " Invented sentence."
    elif change == "visual":
        next(e for e in state["styled_layout"] if e["type"] == "visual")["section_id"] = "method"
    elif change == "asset":
        Image.new("RGB", (100, 50), "black").save(state["images"]["1"]["path"])
    else:
        semantic.sections(state["story_board"])[0]["section_title"] = "Changed after review"
    assert not ModuleConsistencyEvaluator().evaluate(context).passed


def test_classic_isolated_from_semantic_models(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    state["generation_route"] = "standalone_classic"
    monkeypatch.setattr(semantic, "_call", lambda *_: pytest.fail("classic must not call semantic model"))
    assert semantic.audit_board(state, state["story_board"])["status"] == "not_applicable"
    assert agent.module_semantic_finalize_node(state) is state


def test_visual_checks_use_existing_configured_vision_service_with_bounded_image_bytes(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    state["vision_model"] = ModelConfig("existing-vision-service", "local")
    index = semantic.build_paper_index(state)
    payload, problems = semantic._payload(state, semantic.sections(state["story_board"])[1], index)
    assert not problems
    captured = []
    class FakeAgent:
        def __init__(self, _system, config, _state, name, **kwargs):
            assert config.model_name == "existing-vision-service" and name == "module_consistency"
            assert kwargs["single_attempt"] is True
        def step(self, message):
            captured.extend(json.loads(message))
            return SimpleNamespace(content=json.dumps(answer(payload)), input_tokens=7, output_tokens=3)
    monkeypatch.setattr("utils.langgraph_utils.LangGraphAgent", FakeAgent)
    response = semantic._call(state, "config/prompts/module_consistency.txt", payload)
    assert response["checks"][-1]["image_examined"] is True
    assert sum(m["type"] == "image_url" for m in captured) == 1
    assert "Source visual ID: figure_1" in [m.get("text") for m in captured]
    assert state["tokens"].input_vision == 7 and state["tokens"].input_text == 0
    state["critic_config"]["module_consistency"]["max_image_bytes"] = 1
    assert semantic._call(state, "unused", payload)["unavailable_reason"] == "image_payload_unavailable_or_over_budget"
    assert state["module_semantic_runtime"]["model_calls"] == 1


def test_visual_model_missing_cannot_silently_fallback_to_caption_only_text(tmp_path):
    state = fixture(tmp_path)
    payload, _ = semantic._payload(state, semantic.sections(state["story_board"])[1], semantic.build_paper_index(state))
    assert semantic._call(state, "unused", payload)["unavailable_reason"] == "model_unavailable"


def test_visual_acknowledgment_of_pixel_inspection_is_required(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    def caption_only(payload):
        result = answer(payload)
        for check in result["checks"]:
            check.pop("image_examined", None)
        return result
    fake_model(monkeypatch, caption_only)
    assert semantic.audit_board(state, state["story_board"])["status"] == "inconclusive"


def test_model_service_failure_propagates_instead_of_becoming_content_failure(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    payload, _ = semantic._payload(state, semantic.sections(state["story_board"])[0], semantic.build_paper_index(state))
    class OfflineAgent:
        def __init__(self, *_, **__):
            pass
        def step(self, _):
            raise ConnectionError("simulated model outage")
    monkeypatch.setattr("utils.langgraph_utils.LangGraphAgent", OfflineAgent)
    with pytest.raises(RuntimeError, match="model.*call failed") as caught:
        semantic._call(state, "config/prompts/module_consistency.txt", payload)
    assert isinstance(caught.value.__cause__, ConnectionError)
    assert state["module_semantic_runtime"]["model_calls"] == 1


def test_title_numbers_must_come_from_module_original_evidence(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    semantic.sections(state["story_board"])[0]["section_title"] = "Graph Method Improves Accuracy 99%"
    fake_model(monkeypatch)
    report = semantic.audit_board(state, state["story_board"])
    assert report["status"] == "failed"
    assert any(c["reason_code"] == "unsupported_title_number" for m in report["modules"] for c in m["checks"])


@pytest.mark.parametrize("vision", [False, True])
def test_single_attempt_uses_zero_provider_retries_and_one_invocation(monkeypatch, vision):
    import utils.langgraph_utils as client
    requests = []
    factories = []
    class Model:
        def invoke(self, _):
            requests.append("invoke")
            raise ConnectionError("simulated failure")
    def create(config, **kwargs):
        factories.append(kwargs)
        return Model()
    monkeypatch.setattr(client, "create_model", create)
    instance = client.LangGraphAgent("system", ModelConfig("fake", "google"), single_attempt=True)
    message = json.dumps([{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]) if vision else "prompt"
    with pytest.raises(Exception):
        instance.step(message)
    assert factories == [{"max_retries": 0}]
    assert requests == ["invoke"]


def test_optimizer_rolls_back_verified_but_wrong_module_addition(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    state["story_board"]["spatial_content_plan"]["sections"][1]["claim_ids"] = []
    state["story_board"]["spatial_content_plan"]["sections"][1]["text_content"] = []
    state["revision_plan"] = {"content_actions": [{"operation": "add_existing_claim", "section_id": "method",
                                                  "claim_id": "c2", "evidence_ids": ["e2"]}]}
    before = deepcopy(state["story_board"])
    fake_model(monkeypatch, lambda p: answer(p, fail=("claim", "c2")))
    GroundedContentOptimizer()(state)
    assert state["story_board"] == before
    assert state["content_revision"]["accepted_actions"] == []
    assert state["content_revision"]["rejected_actions"][0]["reason"] == "module_semantics_unverified"
    assert state["verified_content_bank"]["claims"] == []


def fit_report():
    return {"composition_whitespace": {"unallocated_body_fraction": 0.1, "largest_empty_rectangle_fraction": 0.1,
                                      "largest_cross_zone_gap_inches": 0.3, "largest_within_zone_gap_inches": 0.3},
            "zone_utilization": {"a": 0.97, "b": 0.98}, "exact_bottom_gaps": {"a": 0.2, "b": 0.1}}


@pytest.mark.parametrize("regression", ["whitespace", "zone", "bottom", "missing"])
def test_semantic_refit_cannot_buy_correctness_with_worse_layout(regression):
    before = fit_report()
    after = deepcopy(before)
    assert agent.fit_nonregression(before, after)
    if regression == "whitespace":
        after["composition_whitespace"]["unallocated_body_fraction"] = 0.12
    elif regression == "zone":
        after["zone_utilization"]["a"] = 0.94
    elif regression == "bottom":
        after["exact_bottom_gaps"]["a"] = 0.4
    else:
        after.pop("composition_whitespace")
    assert not agent.fit_nonregression(before, after)


def test_rendered_repair_regression_veto_preserves_raw_scores_and_blocks_promising():
    scores = {name: 90 for name in load_critic_config()["dimensions"]}
    scores["scientific_integrity"] = 100
    state = {"module_semantic_repair_baseline": {"dimension_scores": scores, "rubric_version": "v6"}}
    report = {"archive_eligible": True, "template_eligible": True, "overall_score": 92,
              "dimension_scores": {**scores, "aesthetics": 88}, "rubric_version": "v6",
              "poster_evaluation": {"archive_eligible": True}, "evaluations": []}
    raw = deepcopy(report)
    agent.apply_semantic_repair_admission(state, report)
    assert not report["archive_eligible"] and not report["template_eligible"]
    assert report["dimension_scores"] == raw["dimension_scores"]
    assert report["poster_evaluation"] == raw["poster_evaluation"]
    assert not assess_promising_candidate(report)["eligible"]


@pytest.mark.parametrize("locked", ["validate", "exact_fallback"])
def test_locked_candidates_never_auto_repair(tmp_path, monkeypatch, locked):
    state = fixture(tmp_path)
    compiled(state)
    if locked == "validate":
        state["template_validation_topology"] = {"zones": [{"zone_id": "a"}]}
    else:
        state["improve_safe_fallback"] = True
    fake_model(monkeypatch, lambda p: answer(p, fail=("title", p["section_id"])))
    monkeypatch.setattr(agent, "_refit", lambda *_: pytest.fail("locked mode must not repair"))
    before = deepcopy(state["story_board"])
    agent.module_semantic_finalize_node(state)
    assert state["module_semantic_blocked"]
    assert state["story_board"] == before
    assert state["module_semantic_repair_report"]["rounds"] == []


def test_uncertain_candidate_does_not_edit_content(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    compiled(state)
    monkeypatch.setattr(semantic, "_call", lambda *_: {})
    before = deepcopy(state["story_board"])
    agent.module_semantic_finalize_node(state)
    assert state["module_semantic_blocked"]
    assert state["story_board"] == before


def test_blocked_semantics_commits_budget_without_posters_templates_or_global_learning(tmp_path):
    from test_campaign_resume import _state
    config = load_critic_config()
    def blocked(state):
        state["module_semantic_blocked"] = True
        state["module_consistency_report"] = {"status": "inconclusive", "modules": []}
        return state
    def forbidden(_):
        pytest.fail("Blocked candidates must not render or call Critic")
    loop = PosterOptimizationLoop(config=config, batch_iterations=2, batch_mode="explore",
                                 fresh_design_nodes=[blocked, forbidden], critic=forbidden,
                                 storage=LoopStorage(tmp_path / "store", config))
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True)
    summary = result["loop_state"]
    assert summary["batch"]["completed_iterations"] == 2
    assert summary["accepted_count"] == summary["rejected_count"] == summary["template_count"] == 0
    assert summary["batch"]["semantic_blocked_count"] == 2
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    assert len(list(campaign.glob("iterations/*/COMPLETED.json"))) == 2
    assert not list((loop.storage.root / "design_memory/global_knowledge/events").glob("*.json"))
    assert not (loop.storage.root / "design_memory/rejection_memory.jsonl").exists()
    for path in campaign.glob("iterations/*/attempts/*/critic_report.json"):
        assert json.loads(path.read_text())["overall_score"] is None
    handle = loop.campaign_manager.load_existing_campaign(summary["campaign_id"])
    loop.campaign_manager.recover_incomplete(handle)
    assert loop.campaign_manager.load_campaign_state(handle)["rejected_count"] == 0


def test_unknown_semantics_is_not_global_design_evidence(tmp_path):
    memory = GlobalDesignKnowledge(tmp_path)
    assert not memory.record(campaign_id="campaign", iteration=1, paper_profile={},
                             report={"report_kind": "module_consistency_blocked"},
                             requested_mode="explore", executed_mode="explore")
    assert memory.knowledge_snapshot()["event_count"] == 0


def test_postrender_semantic_failure_cannot_become_a_template_validation_failure_or_global_prior(tmp_path):
    from src.critic.engine import PosterCritic
    from src.critic.base import EvaluationResult
    from src.workflow.portfolio import PortfolioScheduler
    config = load_critic_config()
    results = [EvaluationResult("module_consistency", "1", True, False)]
    report = PosterCritic(config, evaluators=[])._build_report(
        {"iteration_context": {"portfolio_mode": "validate"}}, results)
    assert report["validation_content_blocked"]
    assert report["task_evaluation"]["evaluated"] is False
    memory = GlobalDesignKnowledge(tmp_path)
    assert not memory.record(campaign_id="c", iteration=1, paper_profile={}, report=report,
                             requested_mode="explore", executed_mode="explore")
    scheduler = PortfolioScheduler(config, 1)
    task = {"mode": "explore", "family_id": "asymmetric_two_column", "lineage_id": "lin_1"}
    report.update(overall_score=99, archive_eligible=False)
    portfolio = scheduler.commit({}, task, report, accepted=False)
    assert portfolio["lineages"]["lin_1"]["best_candidate_id"] is None


def test_reset_does_not_inherit_a_success_or_exhausted_budget():
    state = {"module_semantic_blocked": True, "module_consistency_report": {"status": "passed"},
             "module_semantic_runtime": {"model_calls": 32}, "module_semantic_contracts": {"old": {}}}
    _reset_attempt_diagnostics(state)
    assert not state["module_semantic_blocked"]
    assert state["module_consistency_report"] is None
    assert state["module_semantic_contracts"] == {}
    assert state["module_semantic_runtime"]["model_calls"] == 0


@pytest.mark.parametrize("two_errors", [False, True])
def test_conservative_title_repairs_adopt_only_complete_content_preserving_transaction(tmp_path, monkeypatch, two_errors):
    state = fixture(tmp_path)
    for s in semantic.sections(state["story_board"])[:2 if two_errors else 1]:
        s["section_title"] = "Unsupported Claim"
    before = deepcopy(state["story_board"])
    compiled(state)
    good_titles = {"method": "Graph Construction", "results": "Baseline Comparison"}
    def response(payload):
        bad = payload["title"] == "Unsupported Claim"
        result = answer(payload, fail=("title", payload["section_id"]) if bad else None)
        if bad:
            result["repair_proposals"] = [{"operation": "retitle_module", "section_id": payload["section_id"],
                "title": good_titles[payload["section_id"]], "issue_kind": "title", "issue_id": payload["section_id"]}]
        return result
    fake_model(monkeypatch, response)
    def refit(current, board):
        trial = deepcopy(current)
        trial["story_board"] = deepcopy(board)
        trial["optimized_story_board"] = deepcopy(board)
        compiled(trial)
        return trial, "passed"
    monkeypatch.setattr(agent, "_refit", refit)
    monkeypatch.setattr(agent, "_rendered_baseline", lambda _: {"dimension_scores": {name: 90 for name in state["critic_config"]["dimensions"]}, "rubric_version": "v6"})
    agent.module_semantic_finalize_node(state)
    assert not state["module_semantic_blocked"]
    assert semantic.preserve_content(before, semantic.visible_board(state))
    assert semantic.compiled_consistent(state, semantic.visible_board(state))
    assert len(state["module_semantic_repair_report"]["rounds"]) == (2 if two_errors else 1)
    assert all(r["status"] == "adopted" for r in state["module_semantic_repair_report"]["rounds"])
    assert state["module_semantic_repair_baseline"]


def test_failed_refit_keeps_actual_board_and_reports_aligned(tmp_path, monkeypatch):
    state = fixture(tmp_path)
    semantic.sections(state["story_board"])[0]["section_title"] = "Unsupported Claim"
    before = deepcopy(state["story_board"])
    compiled(state)
    def response(payload):
        bad = payload["title"] == "Unsupported Claim"
        result = answer(payload, fail=("title", payload["section_id"]) if bad else None)
        if bad:
            result["repair_proposals"] = [{"operation": "retitle_module", "section_id": payload["section_id"],
                "title": "Graph Construction", "issue_kind": "title", "issue_id": payload["section_id"]}]
        return result
    fake_model(monkeypatch, response)
    monkeypatch.setattr(agent, "_refit", lambda *_: (None, "repair_layout_regression"))
    monkeypatch.setattr(agent, "_rendered_baseline", lambda *_: pytest.fail("Rejected fit needs no baseline render"))
    agent.module_semantic_finalize_node(state)
    assert state["story_board"] == before
    assert state["module_semantic_blocked"]
    assert semantic.report_current(state, state["module_consistency_report"], before)
    assert state["module_semantic_repair_report"]["rounds"][0]["reason"] == "repair_layout_regression"


def test_validate_content_block_does_not_consume_template_trial_even_after_crash_replay(tmp_path):
    from test_campaign_resume import _state
    from test_template_validation import _template
    config = load_critic_config()
    def blocked(state):
        state["module_semantic_blocked"] = True
        state["module_consistency_report"] = {"status": "inconclusive", "modules": []}
        return state
    def forbidden(_):
        pytest.fail("Blocked validation must not render, score or register another template")
    loop = PosterOptimizationLoop(config=config, batch_iterations=100, batch_mode="validate",
                                 fresh_design_nodes=[blocked, forbidden], critic=forbidden,
                                 storage=LoopStorage(tmp_path / "store", config))
    loop.library.register(_template())
    before = deepcopy(loop.library._load()["templates"])
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True)
    summary = result["loop_state"]
    assert summary["status"] == "EXHAUSTED"
    assert summary["batch"]["completed_iterations"] == 1
    assert summary["batch"]["validation_content_blocks"]
    assert summary["batch"]["validation_counts"]["attempts"] == 0
    assert loop.library._load()["templates"] == before
    assert not (loop.storage.root / "template_library/usage_outcomes.jsonl").exists()
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    applied = next(campaign.glob("iterations/*/TEMPLATE_USAGE_APPLIED.json"))
    applied.unlink()  # emulate crash between the marker and its derived projection
    handle = loop.campaign_manager.load_existing_campaign(summary["campaign_id"])
    _reconcile_template_usage(loop, handle, summary["paper_id"], "balanced:medium")
    assert applied.exists()
    assert loop.library._load()["templates"] == before
    assert loop.campaign_manager.load_batch(handle, "batch_0001")["validation_counts"]["attempts"] == 0


def test_semantic_precommit_failure_rolls_back_budget_and_blocks(tmp_path, monkeypatch):
    from test_campaign_resume import _state
    import src.workflow.campaign as campaign_module
    config = load_critic_config()
    def blocked(state):
        state["module_semantic_blocked"] = True
        state["module_consistency_report"] = {"status": "inconclusive", "modules": []}
        return state
    original = campaign_module._atomic_json
    def atomic(path, payload):
        if path.name == "COMPLETED.json":
            raise OSError("injected semantic commit failure")
        return original(path, payload)
    monkeypatch.setattr(campaign_module, "_atomic_json", atomic)
    loop = PosterOptimizationLoop(config=config, batch_iterations=1, batch_mode="explore",
                                 fresh_design_nodes=[blocked], storage=LoopStorage(tmp_path / "store", config))
    summary = loop.run(_state(tmp_path / "run"), foundation_ready=True)["loop_state"]
    assert summary["status"] == "FAILED_REQUIRES_USER"
    assert summary["batch"]["completed_iterations"] == 0
    assert summary["batch"].get("semantic_blocked_count", 0) == 0
    assert summary["accepted_count"] == summary["rejected_count"] == 0
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    reports = list(campaign.glob("iterations/*/attempts/*/module_consistency_report.json"))
    assert len(reports) == 1
    assert json.loads(reports[0].read_text(encoding="utf-8"))["status"] == "inconclusive"


def test_real_same_topology_refit_keeps_scientific_content_and_passes_geometry(tmp_path):
    from src.agents.layout_agent import LayoutAgent
    from src.agents.layout_preflight import layout_preflight_node
    from src.layout.feasibility import fit_family_layout
    from src.layout.measurement_context import measurement_scope
    state = fixture(tmp_path)
    state["iteration_context"].update(layout_family="asymmetric_two_column", random_seed=17)
    state["color_scheme"] = {"theme": "#123456", "text": "#000000", "background": "#FFFFFF"}
    state["keywords"] = {}
    from src.agents.section_title_designer import SectionTitleDesigner
    SectionTitleDesigner()(state)
    layout = LayoutAgent()
    with measurement_scope(state["critic_config"]["layout_performance"]):
        board, spec, fit = fit_family_layout(layout, state["story_board"], state, "asymmetric_two_column", config=state["critic_config"])
    state.update(optimized_story_board=board, layout_spec=spec, layout_feasibility_report=fit)
    layout(state, mode="final")
    assert not state["errors"]
    state["styled_layout"] = FontAgent()._apply_styling(state["design_layout"], state["color_scheme"], {}, state)
    layout_preflight_node(state)
    assert state["layout_preflight_report"]["passed"]
    trial, reason = agent._refit(state, deepcopy(board))
    assert reason == "passed", reason
    assert semantic.preserve_content(board, semantic.visible_board(trial))
    assert trial["layout_preflight_report"]["passed"]
    assert trial["layout_spec"]["zones"] == spec["zones"]
    assert agent.fit_nonregression(fit, trial["layout_feasibility_report"])
    assert semantic.compiled_consistent(trial, semantic.visible_board(trial))


def test_legacy_parent_score_is_auditable_but_not_compared_across_rubrics(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    handle = manager.open_campaign({"poster_name": "paper", "raw_text": "identity",
                                    "poster_width": 54, "poster_height": 36}, resume_mode="new")
    manager.save_lineage_snapshot(handle, "lin_1", {
        "layout_spec": {"family_id": "asymmetric_two_column"},
        "critic_report": {"candidate_id": "old", "overall_score": 90,
                          "rubric_version": "academic_poster_multifamily_v5"}}, {}, accepted=True)
    state = {}
    loaded = manager.load_lineage_snapshot(handle, "lin_1", state)
    assert loaded["score"] is None and not loaded["score_comparable"]
    assert state["lineage_base_context"]["score"] == 90
    assert state["lineage_base_context"]["rubric_version"] == "academic_poster_multifamily_v5"
    assert not state["lineage_base_context"]["score_comparable"]
