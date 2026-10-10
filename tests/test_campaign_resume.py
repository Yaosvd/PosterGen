import json
import zipfile
from copy import deepcopy
from pathlib import Path

from PIL import Image

from src.config.critic_config import load_critic_config
from src.layout.families import LayoutFamilyRegistry
from src.templates.library import LoopStorage, TemplateLibrary
from src.workflow.campaign import CampaignManager
from src.workflow.optimization_loop import PosterOptimizationLoop


def _state(output: Path):
    return {
        "output_dir": str(output),
        "poster_name": "paper",
        "poster_width": 54,
        "poster_height": 36,
        "verification_passed": True,
        "errors": [],
        "raw_text": "same paper identity",
        "page_records": [],
        "section_chunks": [],
        "images": {},
        "tables": {},
        "classified_visuals": {},
        "evidence_bank": {"version": 1, "items": []},
        "academic_entities": {},
        "narrative_plan": {"sections": []},
        "poster_claims": {},
        "verified_claims": {
            "claims": [{"claim_id": "c1", "text": "One", "evidence_ids": []}]
        },
        "verification_report": {},
    }


def test_incomplete_iteration_retries_same_number(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    state = _state(tmp_path / "run")
    handle = manager.open_campaign(state, resume_mode="new")
    manager.open_batch(handle, target_iterations=100)

    first = manager.begin_iteration(
        handle,
        iteration=1,
        session_id="session-a",
        candidate={"candidate_id": "c-1", "candidate_dir": str(tmp_path / "c1")},
    )
    manager.commit_iteration(
        handle,
        first,
        state=state,
        report={"candidate_id": "c-1", "decision": "discard"},
        outcome={"accepted": False},
        loop_state={"session_id": "session-a", "last_completed_iteration": 0},
    )

    candidate_dir = tmp_path / "c2"
    candidate_dir.mkdir()
    pptx = candidate_dir / "paper.pptx"
    png = candidate_dir / "paper.png"
    pptx.write_bytes(b"partial")
    png.write_bytes(b"partial")
    interrupted = manager.begin_iteration(
        handle,
        iteration=2,
        session_id="session-a",
        candidate={
            "candidate_id": "c-2-partial",
            "candidate_dir": str(candidate_dir),
            "pptx_path": str(pptx),
            "png_path": str(png),
        },
    )

    reopened = manager.open_campaign(state, resume_mode="latest")
    assert reopened.campaign_id == handle.campaign_id
    assert manager.recover_incomplete(reopened) == 1
    status = json.loads((interrupted.path / "status.json").read_text())
    assert status["status"] == "ABANDONED"
    assert not pptx.exists()
    assert not png.exists()

    manager.open_batch(
        reopened, target_iterations=100, batch_id="batch_0001"
    )
    retry = manager.begin_iteration(
        reopened,
        iteration=2,
        session_id="session-b",
        candidate={"candidate_id": "c-2-retry", "candidate_dir": str(tmp_path / "retry")},
    )
    assert retry.iteration == 2
    assert retry.attempt_number == 2


def test_committed_capacity_report_is_kept_in_its_attempt_directory(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    state = _state(tmp_path / "run")
    handle = manager.open_campaign(state, resume_mode="new")
    manager.open_batch(handle, target_iterations=100)
    attempt = manager.begin_iteration(
        handle, iteration=1, session_id="session-a",
        candidate={"candidate_id": "c-1", "candidate_dir": str(tmp_path / "c1")},
    )
    state["capacity_repair_report"] = {
        "schema_version": 2, "status": "skipped",
        "skip_reason": "no_near_miss", "rounds_attempted": 0,
    }
    manager.commit_iteration(
        handle, attempt, state=state,
        report={"candidate_id": "c-1", "decision": "discard"},
        outcome={"accepted": False},
        loop_state={"session_id": "session-a", "last_completed_iteration": 0},
    )
    assert json.loads((attempt.path / "capacity_repair_report.json").read_text()) == (
        state["capacity_repair_report"]
    )
    assert (attempt.path.parent.parent / "COMPLETED.json").exists()


def test_attempt_status_without_iteration_marker_is_not_committed(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    state = _state(tmp_path / "run")
    handle = manager.open_campaign(state, resume_mode="new")
    manager.open_batch(handle, target_iterations=100)
    candidate_dir = tmp_path / "partial"
    candidate_dir.mkdir()
    png = candidate_dir / "paper.png"
    png.write_bytes(b"partial")
    attempt = manager.begin_iteration(
        handle,
        iteration=1,
        session_id="session-a",
        candidate={
            "candidate_id": "partial-complete-status",
            "candidate_dir": str(candidate_dir),
            "png_path": str(png),
        },
    )
    status_path = attempt.path / "status.json"
    status = json.loads(status_path.read_text())
    status["status"] = "COMPLETED"
    status_path.write_text(json.dumps(status))

    assert manager.recover_incomplete(handle) == 0
    recovered = json.loads(status_path.read_text())
    assert recovered["status"] == "ABANDONED"
    assert recovered["reason"] == "interrupted_before_commit"
    assert not png.exists()


class _AlwaysAcceptCritic:
    def __call__(self, state):
        iteration = state["iteration_context"]["iteration"]
        state["critic_report"] = {
            "candidate_id": state["current_candidate"]["candidate_id"],
            "iteration": iteration,
            "strategy": state["iteration_context"]["strategy"],
            "decision": "archive",
            "archive_eligible": True,
            "template_eligible": False,
            "overall_score": 80 + iteration,
            "dimension_scores": {"readability": 90},
            "issues": [],
            "rejection_summary": "",
            "critic_system_version": "test",
            "rubric_version": "test",
        }
        return state


def _render_candidate(state):
    candidate = state["current_candidate"]
    pptx = Path(candidate["pptx_path"])
    pptx.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pptx, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
    Image.new("RGB", (20, 10), "white").save(candidate["png_path"])
    board = {"spatial_content_plan": {"sections": [{
        "section_id": "one",
        "column_assignment": "left",
        "vertical_priority": "top",
        "claim_ids": ["c1"],
        "text_content": ["One"],
        "visual_assets": [],
    }]}}
    state["story_board"] = deepcopy(board)
    state["optimized_story_board"] = deepcopy(board)
    state["styled_layout"] = [
        {
            "type": "section_container",
            "section_id": "one",
            "x": 1,
            "y": 5,
            "width": 15,
            "height": 29.25,
        }
    ]
    return state


def test_second_launch_continues_after_last_completed_iteration(tmp_path):
    config = load_critic_config()
    storage = LoopStorage(tmp_path / "store", config)

    first = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=_AlwaysAcceptCritic(),
        random_seed=7,
        fresh_design_nodes=[_render_candidate],
        revision_design_nodes=[_render_candidate],
    ).run(_state(tmp_path / "output-a"), foundation_ready=True, max_iterations_for_test=2)

    second = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=_AlwaysAcceptCritic(),
        random_seed=999,
        fresh_design_nodes=[_render_candidate],
        revision_design_nodes=[_render_candidate],
    ).run(_state(tmp_path / "output-b"), foundation_ready=True, max_iterations_for_test=1)

    assert first["loop_state"]["last_completed_iteration"] == 2
    assert second["loop_state"]["resumed"] is True
    assert second["loop_state"]["last_completed_iteration"] == 3
    assert second["loop_state"]["accepted_count"] == 3
    assert second["iteration_context"]["iteration"] == 3
    assert second["loop_state"]["campaign_id"] == first["loop_state"]["campaign_id"]
    assert (tmp_path / "output-b" / "paper.png").is_file()

def test_interleaved_batches_refresh_campaign_knowledge_without_changing_policy(
    tmp_path,
):
    config = load_critic_config()
    storage = LoopStorage(tmp_path / "store", config)
    observed_before_third = {}

    def render_with_content(state):
        iteration = state["iteration_context"]["iteration"]
        bank = state.setdefault(
            "verified_content_bank", {"schema_version": 1, "claims": []}
        )
        if iteration == 3:
            observed_before_third["claim_ids"] = {
                item["claim_id"] for item in bank["claims"]
            }
            observed_before_third["selection"] = deepcopy(
                state.get("content_selection") or {}
            )
        claim_id = f"variant-{iteration}"
        if not any(item.get("claim_id") == claim_id for item in bank["claims"]):
            bank["claims"].append({
                "claim_id": claim_id,
                "root_claim_id": "c1",
                "text": f"Verified variant {iteration}.",
                "evidence_ids": [],
                "verified": True,
                "outcomes": [],
            })
        state.setdefault(
            "supplemental_evidence_bank",
            {"schema_version": 1, "items": []},
        )
        selection = state.setdefault("content_selection", {
            "schema_version": 1,
            "replacements": {},
            "active_supplemental_claim_ids": [],
            "disabled_claim_ids": [],
            "last_changed_iteration": {},
        })
        selection["replacements"] = {"c1": claim_id}
        selection["last_changed_iteration"] = {"c1": iteration}
        return _render_candidate(state)

    first = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=_AlwaysAcceptCritic(),
        random_seed=7,
        resume_mode="new",
        new_batch=True,
        batch_iterations=2,
        fresh_design_nodes=[render_with_content],
        revision_design_nodes=[render_with_content],
    ).run(
        _state(tmp_path / "output-a"),
        foundation_ready=True,
        max_iterations_for_test=1,
    )
    batch_1_id = first["loop_state"]["batch"]["batch_id"]
    assert first["loop_state"]["status"] == "PAUSED"

    second = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=_AlwaysAcceptCritic(),
        random_seed=7,
        new_batch=True,
        batch_mode="explore",
        batch_iterations=1,
        fresh_design_nodes=[render_with_content],
        revision_design_nodes=[render_with_content],
    ).run(_state(tmp_path / "output-b"), foundation_ready=True)
    batch_2_id = second["loop_state"]["batch"]["batch_id"]
    assert second["loop_state"]["status"] == "COMPLETED"

    third = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=_AlwaysAcceptCritic(),
        random_seed=7,
        batch_id=batch_1_id,
        batch_iterations=999,
        fresh_design_nodes=[render_with_content],
        revision_design_nodes=[render_with_content],
    ).run(
        _state(tmp_path / "output-c"),
        foundation_ready=True,
        max_iterations_for_test=1,
    )

    assert observed_before_third["claim_ids"] == {"variant-1", "variant-2"}
    # This resumed mixed Batch scheduled a fresh exploration, so it correctly
    # starts from the latest Campaign selection. The manager-level regression
    # separately proves that an explicitly loaded old Lineage restores only
    # its local selection while preserving the shared content-bank union.
    assert observed_before_third["selection"]["replacements"] == {
        "c1": "variant-2"
    }
    manager = CampaignManager(storage.root, config)
    handle = manager.load_existing_campaign(third["loop_state"]["campaign_id"])
    stored_1 = manager.load_batch(handle, batch_1_id)
    stored_2 = manager.load_batch(handle, batch_2_id)
    assert stored_1["committed_iteration_ids"] == [1, 3]
    assert stored_2["committed_iteration_ids"] == [2]
    assert stored_1["schedule_policy"]["mode"] == "mixed"
    assert stored_2["schedule_policy"]["mode"] == "explore"
    assert stored_1["target_iterations"] == 2
    assert stored_1["knowledge_watermarks"]["last_resumed_snapshot"][
        "campaign_content"
    ]["verified_variant_count"] == 2

    restored = _state(tmp_path / "restored")
    manager.load_campaign_content_memory(handle, restored)
    assert {
        item["claim_id"]
        for item in restored["verified_content_bank"]["claims"]
    } == {"variant-1", "variant-2", "variant-3"}



def test_preflight_failures_retry_without_consuming_batch_budget(tmp_path):
    config = deepcopy(load_critic_config())
    config["explore_layout"]["max_family_attempts_per_iteration"] = 2
    storage = LoopStorage(tmp_path / "store", config)
    calls = {"critic": 0, "layout": 0}

    class CountingCritic:
        def __call__(self, state):
            calls["critic"] += 1
            return _AlwaysAcceptCritic()(state)

    def reject_before_render(state):
        calls["layout"] += 1
        family = state["iteration_context"]["layout_family"]
        state["layout_feasibility_report"] = {
            "status": "infeasible",
            "family_id": family,
        }
        state["layout_preflight_report"] = {
            "passed": False,
            "issue_count": 1,
            "issues": [{"code": "PREFLIGHT_TEST"}],
        }
        state["layout_preflight_failed"] = True
        state["capacity_repair_report"] = {
            "schema_version": 2, "status": "skipped",
            "skip_reason": f"attempt-{calls['layout']}",
            "rounds_attempted": 0,
        }
        state["errors"].append(
            f"layout_preflight: {family} infeasible"
        )
        return state

    result = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=CountingCritic(),
        random_seed=7,
        resume_mode="new",
        new_batch=True,
        batch_mode="explore",
        batch_iterations=1,
        fresh_design_nodes=[reject_before_render],
        revision_design_nodes=[reject_before_render],
    ).run(_state(tmp_path / "output"), foundation_ready=True)

    batch = result["loop_state"]["batch"]
    assert calls["critic"] == 0
    assert batch["completed_iterations"] == 0
    assert batch["status"] == "FAILED_REQUIRES_USER"
    assert batch["stop_reason"] == "layout_family_search_exhausted"

    campaign = storage.root / "campaigns" / result["loop_state"]["campaign_id"]
    attempts = list(
        (campaign / "iterations" / "000001" / "attempts").glob(
            "*/status.json"
        )
    )
    assert len(attempts) == 2
    assert all(
        json.loads(path.read_text())["status"] == "ABANDONED"
        for path in attempts
    )
    assert {
        json.loads((path.parent / "capacity_repair_report.json").read_text())[
            "skip_reason"
        ]
        for path in attempts
    } == {"attempt-1", "attempt-2"}


def test_validate_preflight_failures_commit_three_unscored_attempts(tmp_path):
    config = deepcopy(load_critic_config())
    storage = LoopStorage(tmp_path / "store", config)
    library = TemplateLibrary(storage.root, config)
    assert library.register({
        "template_id": "validate-template",
        "status": "paper_specific",
        "family": "classic_three_column",
        "fingerprint": "validate-template-fingerprint",
        "source_paper_id": "different-paper",
        "source_profile": "balanced:medium",
        "overall_score": 91,
        "signature_vector": [0.2, 0.4],
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": ["clear hierarchy"],
        "normalized_blueprint": [],
        "zone_topology": {
            "family_id": "classic_three_column",
            "primary_anchor_zone": None,
            "zones": [dict(zone) for zone in
                      LayoutFamilyRegistry().get("classic_three_column").zones],
        },
        "usage": {
            "times_retrieved": 0,
            "successful_papers": ["different-paper"],
            "successful_profiles": ["balanced:medium"],
        },
    })["registered"]

    critic_calls = {"count": 0}

    class CriticMustNotRun:
        def __call__(self, state):
            critic_calls["count"] += 1
            raise AssertionError("Critic must not run after failed preflight")

    def fail_preflight(state):
        state["layout_feasibility_report"] = {
            "status": "infeasible",
            "family_id": state["iteration_context"]["layout_family"],
        }
        state["layout_preflight_report"] = {
            "passed": False,
            "issue_count": 1,
            "issues": [{"code": "PREFLIGHT_TEST"}],
        }
        state["layout_preflight_failed"] = True
        state["errors"].append("layout preflight failed in test")
        return state

    result = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=CriticMustNotRun(),
        random_seed=11,
        resume_mode="new",
        new_batch=True,
        batch_mode="validate",
        batch_iterations=10,
        fresh_design_nodes=[fail_preflight],
        revision_design_nodes=[fail_preflight],
    ).run(_state(tmp_path / "output"), foundation_ready=True)

    loop = result["loop_state"]
    batch = loop["batch"]
    assert critic_calls["count"] == 0
    assert batch["status"] == "EXHAUSTED"
    assert batch["completed_iterations"] == 3
    assert batch["validation_preflight_failures"] == 3
    assert batch["accepted_count"] == 0
    assert batch["rejected_count"] == 0
    assert batch["validation_counts"]["attempts"] == 3
    assert batch["validation_counts"]["final_failures"] == 1

    campaign = storage.root / "campaigns" / loop["campaign_id"]
    for iteration in (1, 2, 3):
        iteration_dir = campaign / "iterations" / f"{iteration:06d}"
        marker = json.loads((iteration_dir / "COMPLETED.json").read_text())
        attempt = iteration_dir / "attempts" / marker["attempt_id"]
        report = json.loads((attempt / "critic_report.json").read_text())
        outcome = json.loads((attempt / "outcome.json").read_text())
        assert report["report_kind"] == "validation_preflight_failure"
        assert report["overall_score"] is None
        assert report["poster_evaluation"]["evaluated"] is False
        assert outcome["validation_failure_reason"] == "layout_preflight_failed"
        assert outcome["poster_evaluated"] is False

    template = library._load()["templates"][0]
    trial = template["validation"]["paper_trials"][
        result["loop_state"]["paper_id"]
    ]
    assert trial["status"] == "failed_final"
    assert [item["poster_score"] for item in trial["attempts"]] == [
        None, None, None
    ]
    event_root = storage.root / "design_memory" / "global_knowledge" / "events"
    assert not list(event_root.glob("*.json"))


def test_improve_preflight_retries_then_commits_safe_parent_fallback(tmp_path):
    config = deepcopy(load_critic_config())
    config["improve_layout"]["max_preflight_recovery_attempts"] = 3
    storage = LoopStorage(tmp_path / "store", config)

    class CountingAcceptCritic(_AlwaysAcceptCritic):
        def __init__(self):
            self.calls = 0

        def __call__(self, state):
            self.calls += 1
            return super().__call__(state)

    critic = CountingAcceptCritic()
    first = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=critic,
        random_seed=17,
        resume_mode="new",
        new_batch=True,
        batch_mode="explore",
        batch_iterations=1,
        fresh_design_nodes=[_render_candidate],
        revision_design_nodes=[_render_candidate],
    ).run(_state(tmp_path / "first"), foundation_ready=True)
    assert first["loop_state"]["status"] == "COMPLETED"

    def planner_stub(state):
        state["revision_plan"] = {
            "schema_version": 3,
            "operations": [{"operation": "test_change"}],
            "content_actions": [],
        }
        return state

    def content_stub(state):
        state["content_revision"] = {
            "schema_version": 1,
            "accepted_actions": [],
        }
        return state

    def fail_until_parent_fallback(state):
        if not state.get("improve_safe_fallback"):
            state["layout_feasibility_report"] = {"status": "infeasible"}
            state["layout_preflight_report"] = {
                "passed": False,
                "issue_count": 1,
                "issues": [{"code": "PREFLIGHT_TEST"}],
            }
            state["layout_preflight_failed"] = True
            state["errors"].append("Improve preflight failed in test")
            return state
        state["layout_preflight_failed"] = False
        return _render_candidate(state)

    second = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=critic,
        random_seed=17,
        resume_mode="latest",
        new_batch=True,
        batch_mode="improve",
        batch_iterations=1,
        fresh_design_nodes=[_render_candidate],
        revision_design_nodes=[
            planner_stub,
            content_stub,
            fail_until_parent_fallback,
        ],
    ).run(_state(tmp_path / "second"), foundation_ready=True)

    loop = second["loop_state"]
    assert loop["status"] == "COMPLETED"
    assert loop["batch"]["completed_iterations"] == 1
    assert critic.calls == 2
    assert second["revision_plan"]["safe_parent_fallback"] is True
    assert second["revision_plan"]["operations"] == []
    assert second["content_revision"]["reason"] == "safe_parent_fallback"
    assert loop["accepted_count"] == 1
    assert loop["rejected_count"] == 0
    assert loop["last_decision"] == "no_change_safe_fallback"

    campaign = storage.root / "campaigns" / loop["campaign_id"]
    attempts = sorted(
        (campaign / "iterations" / "000002" / "attempts").glob("*/status.json")
    )
    assert len(attempts) == 3
    assert [
        json.loads(path.read_text())["status"] for path in attempts
    ] == ["ABANDONED", "ABANDONED", "COMPLETED"]
    marker = json.loads(
        (campaign / "iterations" / "000002" / "COMPLETED.json").read_text()
    )
    completed_attempt = (
        campaign / "iterations" / "000002" / "attempts"
        / marker["attempt_id"]
    )
    outcome = json.loads(
        (completed_attempt / "outcome.json").read_text()
    )
    assert outcome["accepted"] is False
    assert outcome["critic_accepted"] is True
    assert outcome["no_change_safe_fallback"] is True
    assert outcome["archive"] is None
    assert outcome["template_registration"]["reason"] == (
        "no_change_safe_fallback"
    )
    accepted_bundles = [
        path for path in (storage.root / "accepted_posters").iterdir()
        if path.is_dir() and path.name != ".pending"
    ]
    assert len(accepted_bundles) == 1
    templates = TemplateLibrary(storage.root, config)._load()["templates"]
    assert len(templates) == 1
    lineage = next(iter(loop["portfolio_state"]["lineages"].values()))
    assert lineage["latest_feedback"]["no_change"] is True
    assert lineage["stagnation_count"] >= 1

def test_safety_veto_commits_evidence_without_archive_or_promising_parent(tmp_path):
    config = deepcopy(load_critic_config())
    storage = LoopStorage(tmp_path / "store", config)
    common = dict(config=config, storage=storage, critic=_AlwaysAcceptCritic(),
                  random_seed=17, new_batch=True, batch_iterations=1,
                  fresh_design_nodes=[_render_candidate])
    first = PosterOptimizationLoop(
        **common, resume_mode="new", batch_mode="explore",
        revision_design_nodes=[_render_candidate],
    ).run(_state(tmp_path / "first"), foundation_ready=True)
    best_id = next(iter(first["loop_state"]["portfolio_state"]["lineages"].values()))["best_candidate_id"]

    def failed_safety_candidate(state):
        state = _render_candidate(state)
        state["revision_safety_report"] = {"passed": False, "reasons": ["whole_poster_whitespace_regression"]}
        return state

    second = PosterOptimizationLoop(
        **common, resume_mode="latest", batch_mode="improve",
        revision_design_nodes=[failed_safety_candidate],
    ).run(_state(tmp_path / "second"), foundation_ready=True)
    loop = second["loop_state"]
    assert loop["status"] == "COMPLETED"
    assert loop["batch"]["completed_iterations"] == 1
    assert loop["accepted_count"] == 1 and loop["rejected_count"] == 1
    assert loop["last_decision"] == "revision_safety_rejected"
    assert len(TemplateLibrary(storage.root, config)._load()["templates"]) == 1
    lineage = next(iter(loop["portfolio_state"]["lineages"].values()))
    assert lineage["best_candidate_id"] == best_id
    assert not lineage["best_promising_candidate_id"]
    iteration = storage.root / "campaigns" / loop["campaign_id"] / "iterations" / "000002"
    marker = json.loads((iteration / "COMPLETED.json").read_text())
    attempt = iteration / "attempts" / marker["attempt_id"]
    outcome = json.loads((attempt / "outcome.json").read_text())
    report = json.loads((attempt / "critic_report.json").read_text())
    assert outcome["critic_accepted"] is True and outcome["accepted"] is False
    assert outcome["archive"] is None
    assert report["revision_admission"]["critic_archive_eligible"] is True
    assert (attempt / "revision_safety_report.json").is_file()
    assert not report["promising_evaluation"]["eligible"]
    snapshot = json.loads((attempt / "state_snapshot.json").read_text())
    assert snapshot["fields"]["revision_safety_report"]["passed"] is False
    diagnostics = list((storage.root / "rejected_posters").glob("*/*/*/revision_safety_report.json"))
    assert len(diagnostics) == 1


def test_mixed_batch_isolates_unrecoverable_improve_lineage(tmp_path):
    config = deepcopy(load_critic_config())
    config["loop"]["session_template_free_warmup"] = 0
    config["improve_layout"]["max_preflight_recovery_attempts"] = 3
    storage = LoopStorage(tmp_path / "store", config)

    first = PosterOptimizationLoop(
        config=config, storage=storage, critic=_AlwaysAcceptCritic(),
        random_seed=31, resume_mode="new", new_batch=True,
        batch_mode="explore", batch_iterations=1,
        fresh_design_nodes=[_render_candidate],
        revision_design_nodes=[_render_candidate],
    ).run(_state(tmp_path / "first"), foundation_ready=True)
    assert first["loop_state"]["status"] == "COMPLETED"
    source_lineage = next(iter(
        first["loop_state"]["portfolio_state"]["lineages"]
    ))

    def planner_stub(state):
        state["revision_plan"] = {
            "schema_version": 3, "operations": [], "content_actions": []
        }
        return state

    def content_stub(state):
        state["content_revision"] = {
            "schema_version": 1, "accepted_actions": []
        }
        return state

    def always_fail_improve(state):
        state["layout_feasibility_report"] = {
            "status": "infeasible",
            "family_id": state["iteration_context"]["layout_family"],
        }
        state["layout_preflight_report"] = {
            "status": "not_run", "passed": False,
            "issue_count": 0, "issues": [],
            "blocked_by": "layout_feasibility",
        }
        state["layout_preflight_failed"] = True
        state["errors"].append("forced Improve layout failure")
        return state

    second = PosterOptimizationLoop(
        config=config, storage=storage, critic=_AlwaysAcceptCritic(),
        random_seed=31, resume_mode="latest", new_batch=True,
        batch_mode="mixed", batch_iterations=1,
        fresh_design_nodes=[_render_candidate],
        revision_design_nodes=[
            planner_stub, content_stub, always_fail_improve,
        ],
    ).run(_state(tmp_path / "second"), foundation_ready=True)

    batch = second["loop_state"]["batch"]
    assert second["loop_state"]["status"] == "COMPLETED"
    assert batch["completed_iterations"] == 1
    assert batch["executed_mode_counts"] == {"explore": 1}
    assert source_lineage in batch["layout_recovery_blocks"]
    block = batch["layout_recovery_blocks"][source_lineage]
    assert block["blocked_at_iteration"] == 2
    assert len(block["attempt_ids"]) == 3
    assert second["iteration_context"]["iteration"] == 2
    assert second["iteration_context"]["portfolio_mode"] == "explore"
