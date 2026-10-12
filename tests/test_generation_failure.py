"""No-model fault injection around generation and the sole iteration commit."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

import src.workflow.campaign as campaign_module
import src.layout.capacity_repair as repair_module
from src.agents.layout_with_balancer import LayoutWithBalancerAgent
from src.agents.renderer import Renderer
from src.config.critic_config import load_critic_config
from src.templates.library import LoopStorage
from src.workflow.campaign import CampaignHandle, CampaignManager
from src.workflow.optimization_loop import PosterOptimizationLoop
from src.workflow.campaign_runner import _reconcile_accepted_bundles, _reset_attempt_diagnostics
from test_campaign_resume import _state, _render_candidate, _AlwaysAcceptCritic


def read(path):
    return json.loads(path.read_text())


class RejectCritic(_AlwaysAcceptCritic):
    def __call__(self, state):
        super().__call__(state)
        state["critic_report"].update(archive_eligible=False, template_eligible=False,
                                     decision="discard", overall_score=60)
        return state


def make_loop(tmp_path, node, critic=None, **kwargs):
    config = load_critic_config()
    config["evaluators"]["visual"]["enabled"] = False
    storage = LoopStorage(tmp_path / "store", config)
    return PosterOptimizationLoop(config=config, storage=storage,
                                  critic=critic or RejectCritic(), batch_iterations=2,
                                  fresh_design_nodes=[node], revision_design_nodes=[node],
                                  **kwargs)


@pytest.mark.parametrize("failure", ["raised", "returned", "missing_png", "not_rendered", "stale"])
def test_generation_failure_never_calls_critic_or_commits(tmp_path, failure):
    def node(state):
        if failure == "raised":
            raise TypeError("injected content failure")
        if failure == "returned":
            state["errors"].append("injected agent failure")
            return state
        _render_candidate(state)
        if failure == "missing_png":
            Path(state["current_candidate"]["png_path"]).unlink()
        if failure == "not_rendered":
            state["current_candidate"]["status"] = "planned"
        if failure == "stale":
            state["current_candidate"]["candidate_id"] = "parent"
        return state

    def no_critic(_):
        pytest.fail("Generation failure cannot be evaluated as a poster")

    loop = make_loop(tmp_path, node, no_critic)
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True)
    summary = result["loop_state"]
    assert summary["status"] == "FAILED_REQUIRES_USER"
    assert summary["accepted_count"] == summary["rejected_count"] == summary["template_count"] == 0
    assert summary["batch"]["completed_iterations"] == 0
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    assert not list(campaign.glob("iterations/*/COMPLETED.json"))
    report = read(next(campaign.glob("iterations/*/attempts/*/attempt_failure_report.json")))
    assert report["budget_consumed"] is False and report["retryable"] is False
    assert report["attempt_id"] and report["family_id"] and report["batch_id"]
    assert report["exception_type"] == ("TypeError" if failure == "raised" else "GenerationFailure")
    assert not (loop.storage.root / "design_memory/rejection_memory.jsonl").exists()
    assert not list((loop.storage.root / "design_memory/global_knowledge/events").glob("*.json"))
    assert not summary["portfolio_state"]["lineages"]


@pytest.mark.parametrize("point", ["staging", "portfolio", "marker"])
@pytest.mark.parametrize("accepted", [False, True])
def test_precommit_failure_rolls_back_all_accounting(tmp_path, monkeypatch, point, accepted):
    loop = make_loop(tmp_path, _render_candidate, _AlwaysAcceptCritic() if accepted else RejectCritic())
    def fail(*_, **__):
        raise OSError("injected precommit failure")
    if point == "staging":
        method = "prepare_accepted_bundle" if accepted else "record_rejection"
        monkeypatch.setattr(loop.storage, method, fail)
    elif point == "portfolio":
        monkeypatch.setattr(loop.portfolio_scheduler, "commit", fail)
    else:
        original = campaign_module._atomic_json
        def atomic(path, payload):
            if path.name == "COMPLETED.json":
                fail()
            original(path, payload)
        monkeypatch.setattr(campaign_module, "_atomic_json", atomic)
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True)
    summary = result["loop_state"]
    assert summary["status"] == "FAILED_REQUIRES_USER"
    for key in ("accepted_count", "rejected_count", "template_count", "validation_evidence_count", "last_completed_iteration"):
        assert summary[key] == 0
    assert not summary["best_candidate"]
    assert not summary["portfolio_state"]["lineages"]
    assert not sum(loop.selector.counts.values())
    assert summary["batch"]["completed_iterations"] == 0
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    persisted = read(campaign / "campaign_state.json")
    assert persisted["accepted_count"] == persisted["rejected_count"] == persisted["template_count"] == 0
    assert not (loop.storage.root / "design_memory/rejection_memory.jsonl").exists()
    assert not list((loop.storage.root / "rejected_posters/.pending").glob("*"))
    assert not list((loop.storage.root / "accepted_posters/.pending").glob("*"))


@pytest.mark.parametrize("accepted", [False, True])
def test_postmarker_failure_keeps_commit_and_replays_once(tmp_path, monkeypatch, accepted):
    loop = make_loop(tmp_path, _render_candidate, _AlwaysAcceptCritic() if accepted else RejectCritic())
    original = loop.campaign_manager.save_batch
    injected = False
    def save(handle, batch, **kwargs):
        nonlocal injected
        if not injected and list((handle.path / "iterations").glob("*/COMPLETED.json")):
            injected = True
            raise OSError("injected after marker")
        return original(handle, batch, **kwargs)
    monkeypatch.setattr(loop.campaign_manager, "save_batch", save)
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True)
    summary = result["loop_state"]
    assert injected and summary["last_completed_iteration"] == 1
    assert summary["batch"]["completed_iterations"] == 1
    assert summary["accepted_count"] == int(accepted)
    assert summary["rejected_count"] == int(not accepted)
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    handle = CampaignHandle(summary["campaign_id"], campaign, read(campaign / "manifest.json"), True, 1)
    for _ in range(2):
        loop.campaign_manager.recover_incomplete(handle)
        _reconcile_accepted_bundles(loop, handle)
    persisted = read(campaign / "campaign_state.json")
    assert persisted["accepted_count"] == int(accepted)
    assert persisted["rejected_count"] == int(not accepted)
    assert persisted["portfolio_state"]["mode_counts"]["explore"] == 1
    if accepted:
        assert len(read(loop.storage.root / "template_library/index.json")["templates"]) == 1
    else:
        lines = (loop.storage.root / "design_memory/rejection_memory.jsonl").read_text().splitlines()
        assert len(lines) == 1 and read(campaign / "iterations/000001/REJECTED_ARTIFACT_PUBLISHED.json")
        assert json.loads(lines[0])["event_id"]


def test_layout_repair_exception_retains_measured_fit_and_root_cause(tmp_path, monkeypatch):
    state = _state(tmp_path / "run")
    state.update(generation_route="optimization_family", text_model=object(), tokens=object(),
                 critic_config=load_critic_config(),
                 iteration_context={"portfolio_mode": "explore", "layout_family": "result_dashboard_cards"})
    state["story_board"] = {"spatial_content_plan": {"sections": [{"section_id": "one", "claim_ids": ["c1"], "text_content": ["One"], "visual_assets": []}]}}
    report = {"status": "feasible", "zone_utilization": {"main": 0.7}, "worst_zone_utilization": 0.7}
    spec = {"zones": [{"zone_id": "main", "section_ids": ["one"]}]}
    monkeypatch.setattr("src.agents.layout_with_balancer.fit_family_layout", lambda *_, **__: (deepcopy(state["story_board"]), spec, report))
    def crash(*_, **__):
        raise TypeError("original repair crash")
    monkeypatch.setattr(repair_module, "content_optimizer", crash)
    result = LayoutWithBalancerAgent()(state)
    assert result["attempt_failure_report"]["phase"] == "capacity_repair/content_optimizer"
    assert "original repair crash" in result["attempt_failure_report"]["traceback"]
    assert result["layout_feasibility_report"]["status"] == "feasible"
    assert result["capacity_repair_report"]["status"] == "error"
    assert result["capacity_repair_report"]["rounds_attempted"] == 1
    assert read(tmp_path / "run/content/layout_feasibility_report.json")["status"] == "feasible"
    _reset_attempt_diagnostics(result)
    assert result["attempt_failure_report"] is None


def test_renderer_preserves_original_exception(tmp_path, monkeypatch):
    state = _state(tmp_path / "run")
    state["generation_route"] = "optimization_family"
    agent = Renderer()
    monkeypatch.setattr(agent, "_load_styling_interfaces", lambda _: {})
    def crash(*_):
        raise RuntimeError("renderer conversion failed")
    monkeypatch.setattr(agent, "_render_presentation", crash)
    agent(state)
    assert state["attempt_failure_report"]["exception_type"] == "RuntimeError"
    assert state["attempt_failure_report"]["phase"] == "renderer"


def test_historical_correction_preserves_failure_and_foundation(tmp_path):
    config = load_critic_config()
    storage = LoopStorage(tmp_path / "store", config)
    manager = CampaignManager(storage.root, config)
    state = _state(tmp_path / "run")
    handle = manager.open_campaign(state, resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100)
    manager.save_foundation(handle, state)
    foundation = (handle.path / "foundation/scientific_state.json").read_bytes()
    attempt = manager.begin_iteration(handle, iteration=1, session_id="old", candidate={"candidate_id": "broken"})
    manager.abandon_attempt(attempt, "iteration_exception")
    batch["status"] = "FAILED_REQUIRES_USER"
    manager.save_batch(handle, batch)
    summary = manager.load_campaign_state(handle)
    summary.update(status="FAILED_REQUIRES_USER", rejected_count=1)
    campaign_module._atomic_json(handle.path / "campaign_state.json", summary)
    journal = storage.root / "design_memory/rejection_memory.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(json.dumps({"candidate_id": "broken"}) + "\n")
    old_journal = journal.read_bytes()
    for _ in range(2):
        assert manager.recover_incomplete(handle) == 0
        storage.invalidate_uncommitted_rejections(handle.path)
    summary = manager.load_campaign_state(handle)
    assert summary["rejected_count"] == 0
    assert summary["status"] == "FAILED_REQUIRES_USER"
    assert manager.load_batch(handle, batch["batch_id"])["status"] == "FAILED_REQUIRES_USER"
    assert read(attempt.path / "status.json")["reason"] == "iteration_exception"
    assert (handle.path / "foundation/scientific_state.json").read_bytes() == foundation
    assert journal.read_bytes() == old_journal
    assert len(journal.with_name("rejection_memory_corrections.jsonl").read_text().splitlines()) == 1
    new_batch = manager.open_batch(handle, target_iterations=100, new_batch=True)
    assert new_batch["batch_id"] == "batch_0002"
    retry = manager.begin_iteration(handle, iteration=1, session_id="new", candidate={"candidate_id": "retry"})
    assert retry.attempt_number == 2


def test_incomplete_history_is_not_reset_to_zero(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign(_state(tmp_path / "run"), resume_mode="new")
    summary = manager.load_campaign_state(handle)
    summary.update(last_completed_iteration=5, accepted_count=4)
    campaign_module._atomic_json(handle.path / "campaign_state.json", summary)
    assert not manager.reconcile_committed_summaries(handle)
    assert manager.load_campaign_state(handle)["accepted_count"] == 4
    with pytest.raises(ValueError, match="incomplete"):
        manager.recover_incomplete(handle)
    assert manager.load_campaign_state(handle)["last_completed_iteration"] == 5


def test_rejection_journal_append_crash_is_idempotent(tmp_path, monkeypatch):
    loop = make_loop(tmp_path, _render_candidate)
    loop.run(_state(tmp_path / "run"), foundation_ready=True, max_iterations_for_test=1)
    campaign = next((loop.storage.root / "campaigns").iterdir())
    journal = loop.storage.root / "design_memory/rejection_memory.jsonl"
    # Simulate a committed iteration whose journal publication has not run yet.
    journal.unlink()
    import src.templates.library as library_module
    append = library_module._append_jsonl
    def append_then_crash(path, payload):
        append(path, payload)
        raise OSError("crash after durable append")
    monkeypatch.setattr(library_module, "_append_jsonl", append_then_crash)
    with pytest.raises(OSError, match="durable append"):
        loop.storage.publish_rejection_record(campaign, 1)
    monkeypatch.setattr(library_module, "_append_jsonl", append)
    assert not loop.storage.publish_rejection_record(campaign, 1)
    assert len(journal.read_text().splitlines()) == 1


@pytest.mark.parametrize("corrupt", [False, True])
def test_runtime_projection_integrity_fails_closed(tmp_path, corrupt):
    loop = make_loop(tmp_path, _render_candidate)
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True, max_iterations_for_test=1)
    campaign = loop.storage.root / "campaigns" / result["loop_state"]["campaign_id"]
    runtime = next(campaign.glob("iterations/*/attempts/*/commit_runtime_state.json"))
    if corrupt:
        value = read(runtime)
        value["portfolio_state"] = {}
        runtime.write_text(json.dumps(value))
    else:
        runtime.unlink()
    handle = CampaignHandle(campaign.name, campaign, read(campaign / "manifest.json"), True, 1)
    before = (campaign / "campaign_state.json").read_bytes()
    with pytest.raises(ValueError, match="digest mismatch"):
        loop.campaign_manager.reconcile_committed_summaries(handle)
    assert (campaign / "campaign_state.json").read_bytes() == before


def test_accounting_replay_preserves_archived_failed_batch_at_budget(tmp_path):
    loop = make_loop(tmp_path, _render_candidate)
    loop.batch_iterations = 1
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True)
    summary = result["loop_state"]
    campaign = loop.storage.root / "campaigns" / summary["campaign_id"]
    handle = CampaignHandle(campaign.name, campaign, read(campaign / "manifest.json"), True, 1)
    batch = loop.campaign_manager.load_batch(handle, summary["batch"]["batch_id"])
    batch["status"] = "FAILED_REQUIRES_USER"
    loop.campaign_manager.save_batch(handle, batch)
    loop.campaign_manager.archive_batch(handle, summary["batch"]["batch_id"])
    loop.campaign_manager.recover_incomplete(handle)
    assert loop.campaign_manager.load_batch(handle, summary["batch"]["batch_id"])["status"] == "ARCHIVED"
