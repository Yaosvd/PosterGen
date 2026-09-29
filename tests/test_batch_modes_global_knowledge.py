"""Regressions for finite pure-mode Batches and global abstract feedback."""
import json
from types import SimpleNamespace

import pytest

from src.config.critic_config import load_critic_config
from src.templates.library import LoopStorage, TemplateLibrary
from src.workflow.campaign import CampaignManager
from src.workflow.global_knowledge import GlobalDesignKnowledge
from src.workflow.portfolio import PortfolioScheduler, new_portfolio_state
from src.workflow.optimization_loop import PosterOptimizationLoop
from src.workflow.campaign_runner import _reconcile_template_usage


PROFILE = {"profile_key": "balanced:medium", "kind": "balanced", "visual_count": 2}


def _report(iteration, family, score=70):
    return {
        "candidate_id": f"candidate-{iteration}",
        "rubric_version": "rubric-v1",
        "layout_family": family,
        "overall_score": score,
        "archive_eligible": score >= 85,
        "template_eligible": score >= 90,
        "hard_gate_passed": True,
        "dimension_scores": {"layout_integrity": score},
        "issues": [{
            "scope": "layout",
            "observation": "Secret scientific claim with raw prose",
            "allowed_operations": ["move_section_to_zone"],
        }],
    }


def test_pure_modes_preserve_mixed_quotas_and_require_prerequisites():
    scheduler = PortfolioScheduler(load_critic_config(), random_seed=9)
    state = new_portfolio_state()
    with pytest.raises(ValueError, match="Lineage"):
        scheduler.select(
            state, iteration=1, session_iteration=1, paper_profile=PROFILE,
            validation_available=False, batch_mode="improve",
        )
    with pytest.raises(ValueError, match="pending"):
        scheduler.select(
            state, iteration=1, session_iteration=1, paper_profile=PROFILE,
            validation_available=False, batch_mode="validate",
        )
    first = scheduler.select(
        state, iteration=1, session_iteration=1, paper_profile=PROFILE,
        validation_available=False, batch_mode="explore",
    )
    state = scheduler.commit(
        state, first, _report(1, first["family_id"]), accepted=False,
        batch_mode="explore",
    )
    assert state["mode_counts"]["explore"] == 1
    assert sum(state["mixed_mode_counts"].values()) == 0
    second = scheduler.select(
        state, iteration=2, session_iteration=1, paper_profile=PROFILE,
        validation_available=True, batch_mode="improve",
    )
    assert second["mode"] == "improve"
    assert second["lineage_id"] == first["lineage_id"]
    state = scheduler.commit(
        state, second, _report(2, second["family_id"]), accepted=False,
        batch_mode="improve",
    )
    assert state["mode_counts"]["improve"] == 1
    assert sum(state["mixed_mode_counts"].values()) == 0
    mixed = scheduler.select(
        state, iteration=3, session_iteration=4, paper_profile=PROFILE,
        validation_available=True,
    )
    assert mixed["mode"] == "improve"  # Mixed quota starts at zero despite pure history.


def test_batch_policy_freezes_on_resume_and_exhaustion_advances_number(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    state = {"poster_name": "paper", "raw_text": "identity", "poster_width": 54, "poster_height": 36}
    handle = manager.open_campaign(state, resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100, mode="explore")
    assert batch["schedule_policy"]["mode"] == "explore"
    assert manager.open_batch(handle, target_iterations=50)["batch_id"] == batch["batch_id"]
    with pytest.raises(ValueError, match="frozen"):
        manager.open_batch(handle, target_iterations=100, mode="validate")
    batch["status"] = "EXHAUSTED"
    manager.save_batch(handle, batch)
    next_batch = manager.open_batch(handle, target_iterations=100, mode="mixed")
    assert next_batch["batch_number"] == 2


def test_validation_ignores_normal_reuse_cooldown(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    template = {
        "template_id": "t1", "status": "paper_specific",
        "family": "classic_three_column", "fingerprint": "t1",
        "source_paper_id": "paper-a", "source_profile": "balanced:medium",
        "overall_score": 90, "signature_vector": [0.2, 0.4],
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": ["hierarchy"], "normalized_blueprint": [],
        "zone_topology": {
            "family_id": "classic_three_column",
            "primary_anchor_zone": "main",
            "zones": [{"zone_id": "main", "role": "main", "capacity": 8,
                       "x": 0, "y": 0, "width": 1, "height": 1}],
        },
    }
    assert library.register(template)["registered"]
    library.record_usage(
        template_ids=["t1"], campaign_id="c1", paper_id="paper-a",
        profile_key="balanced:medium", iteration=1, accepted=False,
        score=60, event_id="c1:1", validation_run=False,
    )
    chosen = library.retrieve(
        strategy="validate", campaign_id="c1", paper_id="paper-a",
        paper_profile=PROFILE, iteration=2, recent_template_ids=["t1"],
        random_seed=1,
    )
    assert [item["template_id"] for item in chosen] == ["t1"]


def test_global_knowledge_is_idempotent_deidentified_and_shared(tmp_path):
    memory = GlobalDesignKnowledge(tmp_path)
    report = _report(1, "classic_three_column", 92)
    assert memory.record(
        campaign_id="campaign-a", iteration=1, paper_profile=PROFILE,
        report=report, requested_mode="explore", executed_mode="explore",
    )
    assert not memory.record(
        campaign_id="campaign-a", iteration=1, paper_profile=PROFILE,
        report=report, requested_mode="explore", executed_mode="explore",
    )
    event = json.loads(next(memory.root.glob("*.json")).read_text())
    assert "Secret scientific claim" not in json.dumps(event)
    assert event["profile_key"] == "balanced:medium"
    context = memory.retrieve(
        rubric_version="rubric-v1", paper_profile=PROFILE,
        family_id="classic_three_column", mode="improve",
    )
    assert context["sample_count"] == 1
    assert context["frequent_issue_scopes"] == ["layout"]
    assert context["safe_operation_candidates"] == ["move_section_to_zone"]
    assert "scientific claim" not in json.dumps(context)


def test_global_repair_delta_requires_comparable_rubric_and_family(tmp_path):
    memory = GlobalDesignKnowledge(tmp_path)
    previous = _report(1, "classic_three_column", 65)
    current = _report(2, "classic_three_column", 76)
    memory.record(
        campaign_id="campaign-a", iteration=2, paper_profile=PROFILE,
        report=current, requested_mode="improve", executed_mode="improve",
        previous_report=previous, operations=["move_section_to_zone"],
    )
    event = json.loads(next(memory.root.glob("*.json")).read_text())
    assert event["score_delta"] == 11
    assert event["repair_association"] == "single_operation_associated"


@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_reason"),
    [
        ("validate", "EXHAUSTED", "validation_queue_exhausted"),
        ("improve", "UNAVAILABLE", "lineage_unavailable"),
    ],
)
def test_pure_batch_without_required_work_never_falls_back(
    tmp_path, mode, expected_status, expected_reason,
):
    config = load_critic_config()
    state = {
        "output_dir": str(tmp_path / "output"),
        "poster_name": "paper",
        "poster_width": 54,
        "poster_height": 36,
        "verification_passed": True,
        "errors": [],
        "raw_text": "paper identity",
        "page_records": [],
        "section_chunks": [],
        "images": {},
        "tables": {},
        "classified_visuals": {},
        "evidence_bank": {},
        "academic_entities": {},
        "narrative_plan": {"sections": []},
        "poster_claims": {},
        "verified_claims": {"claims": [{"claim_id": "c1", "text": "One"}]},
        "verification_report": {},
    }
    result = PosterOptimizationLoop(
        config=config,
        storage=LoopStorage(tmp_path / "store", config),
        batch_mode=mode,
        batch_iterations=2,
    ).run(state, foundation_ready=True)
    loop = result["loop_state"]
    assert loop["status"] == expected_status
    assert loop["stop_reason"] == expected_reason
    assert loop["batch"]["completed_iterations"] == 0
    assert not list((tmp_path / "store" / "campaigns").glob("*/iterations/*/COMPLETED.json"))


def test_global_knowledge_replays_only_committed_attempts(tmp_path):
    memory = GlobalDesignKnowledge(tmp_path / "store")
    campaign = tmp_path / "campaign"
    committed = campaign / "iterations" / "000001"
    attempt = committed / "attempts" / "attempt_1"
    attempt.mkdir(parents=True)
    (attempt / "critic_report.json").write_text(
        json.dumps(_report(1, "classic_three_column")), encoding="utf-8",
    )
    (attempt / "outcome.json").write_text(
        json.dumps({"portfolio_task": {"mode": "explore"}}), encoding="utf-8",
    )
    assert memory.reconcile_campaign(campaign, PROFILE) == 0
    (committed / "COMPLETED.json").write_text(
        json.dumps({
            "campaign_id": "campaign-a", "iteration": 1,
            "attempt_id": "attempt_1",
        }), encoding="utf-8",
    )
    assert memory.reconcile_campaign(campaign, PROFILE) == 1
    assert memory.reconcile_campaign(campaign, PROFILE) == 0


def test_committed_validation_usage_replays_once_after_crash(tmp_path):
    config = load_critic_config()
    root = tmp_path / "store"
    manager = CampaignManager(root, config)
    state = {
        "poster_name": "paper", "raw_text": "paper identity",
        "poster_width": 54, "poster_height": 36,
    }
    handle = manager.open_campaign(state, resume_mode="new")
    paper_id = handle.manifest["paper_sha256"]
    manager.open_batch(handle, target_iterations=10, mode="validate")
    library = TemplateLibrary(root, config)
    assert library.register({
        "template_id": "t1", "status": "paper_specific",
        "family": "classic_three_column", "fingerprint": "t1",
        "source_paper_id": paper_id, "source_profile": "balanced:medium",
        "overall_score": 90, "signature_vector": [0.2, 0.4],
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": ["hierarchy"], "normalized_blueprint": [],
        "zone_topology": {
            "family_id": "classic_three_column",
            "primary_anchor_zone": "main",
            "zones": [{"zone_id": "main", "role": "main", "capacity": 8,
                       "x": 0, "y": 0, "width": 1, "height": 1}],
        },
    })["registered"]
    attempt = manager.begin_iteration(
        handle, iteration=1, session_id="session-1",
        candidate={"candidate_id": "c1", "candidate_dir": str(tmp_path / "candidate")},
    )
    manager.commit_iteration(
        handle, attempt, state=state,
        report=_report(1, "classic_three_column", 60),
        outcome={
            "selected_template_ids": ["t1"], "accepted": False,
            "portfolio_task": {"mode": "validate"},
            "validation_task": {
                "target": "source_replay", "attempt": 1, "max_attempts": 1,
            },
        },
        loop_state={"session_id": "session-1", "last_completed_iteration": 0},
    )
    owner = SimpleNamespace(library=library, campaign_manager=manager)
    _reconcile_template_usage(owner, handle, paper_id, "balanced:medium")
    _reconcile_template_usage(owner, handle, paper_id, "balanced:medium")
    stored = json.loads(library.index_path.read_text())["templates"][0]
    assert stored["validation"]["events"] == 1
    assert stored["validation"]["source_replay_completed"]
    assert stored["validation"]["paper_trials"] == {}
    assert stored["validation"]["distinct_validation_papers"] == []
    active = manager.load_campaign_state(handle)["active_batch"]
    assert active["validation_counts"]["attempts"] == 1
    assert active["validation_counts"]["source_replays"] == 1
    assert active["validation_event_ids"] == [f"{handle.campaign_id}:1"]
    assert (attempt.path.parents[1] / "TEMPLATE_USAGE_APPLIED.json").is_file()


def test_validate_commit_does_not_create_lineage_or_family_coverage():
    scheduler = PortfolioScheduler(load_critic_config(), random_seed=9)
    state = new_portfolio_state()
    task = scheduler.select(
        state,
        iteration=1,
        session_iteration=1,
        paper_profile=PROFILE,
        validation_available=True,
        batch_mode="validate",
    )
    assert task["lineage_id"] == "validation-only"
    before_families = dict(state["family_counts"])
    before_debt = dict(state["family_exploration_debt"])
    committed = scheduler.commit(
        state,
        {**task, "family_id": "classic_three_column"},
        {
            **_report(1, "classic_three_column", 94),
            "task_evaluation": {"passed": True},
        },
        accepted=True,
        selected_template_ids=["t1"],
        batch_mode="validate",
    )
    assert committed["lineages"] == {}
    assert committed["family_counts"] == before_families
    assert committed["family_exploration_debt"] == before_debt
    assert committed["recent_lineage_ids"] == []
    assert committed["mode_counts"]["validate"] == 1
    assert committed["mixed_mode_counts"]["validate"] == 0
    assert committed["validation_history"][0]["template_ids"] == ["t1"]


def test_global_knowledge_replay_skips_validation_attempts(tmp_path):
    memory = GlobalDesignKnowledge(tmp_path / "store")
    campaign = tmp_path / "campaign"
    iteration = campaign / "iterations" / "000001"
    attempt = iteration / "attempts" / "attempt_1"
    attempt.mkdir(parents=True)
    (attempt / "critic_report.json").write_text(
        json.dumps(_report(1, "classic_three_column", 94)),
        encoding="utf-8",
    )
    (attempt / "outcome.json").write_text(
        json.dumps({"portfolio_task": {"mode": "validate"}}),
        encoding="utf-8",
    )
    (iteration / "COMPLETED.json").write_text(json.dumps({
        "campaign_id": "campaign-a",
        "iteration": 1,
        "attempt_id": "attempt_1",
    }))
    assert memory.reconcile_campaign(campaign, PROFILE) == 0
    assert not list(memory.root.glob("*.json"))

def test_template_and_global_knowledge_snapshots_are_versioned_and_idempotent(
    tmp_path,
):
    config = load_critic_config()
    library = TemplateLibrary(tmp_path, config)
    empty = library.knowledge_snapshot()
    assert empty["revision"] == 0
    assert empty["template_count"] == 0

    template = {
        "template_id": "versioned-template",
        "status": "paper_specific",
        "family": "classic_three_column",
        "fingerprint": "versioned-template",
        "source_paper_id": "paper-a",
        "source_profile": "balanced:medium",
        "overall_score": 90,
        "signature_vector": [0.2, 0.4],
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": ["hierarchy"],
        "normalized_blueprint": [],
        "zone_topology": {
            "family_id": "classic_three_column",
            "primary_anchor_zone": "main",
            "zones": [{
                "zone_id": "main",
                "role": "main",
                "capacity": 8,
                "x": 0,
                "y": 0,
                "width": 1,
                "height": 1,
            }],
        },
    }
    assert library.register(template)["registered"]
    registered = library.knowledge_snapshot()
    assert registered["revision"] > empty["revision"]
    assert registered["template_count"] == 1
    assert not library.register(dict(template))["registered"]
    duplicate = library.knowledge_snapshot()
    assert duplicate["revision"] == registered["revision"]
    assert duplicate["digest"] == registered["digest"]

    contexts, retrieved = library.retrieve_with_snapshot(
        strategy="explore",
        campaign_id="campaign-a",
        paper_id="paper-a",
        paper_profile=PROFILE,
        iteration=1,
        recent_template_ids=[],
        random_seed=1,
    )
    assert contexts == []
    assert retrieved["revision"] == registered["revision"]
    assert retrieved["digest"] == registered["digest"]

    library.record_usage(
        template_ids=["versioned-template"],
        campaign_id="campaign-a",
        paper_id="paper-a",
        profile_key="balanced:medium",
        iteration=1,
        accepted=False,
        score=50,
        event_id="campaign-a:1",
    )
    used = library.knowledge_snapshot()
    assert used["revision"] > registered["revision"]
    assert used["digest"] != registered["digest"]

    memory = GlobalDesignKnowledge(tmp_path)
    before = memory.knowledge_snapshot()
    assert before["event_count"] == 0
    assert memory.record(
        campaign_id="campaign-a",
        iteration=1,
        paper_profile=PROFILE,
        report=_report(1, "classic_three_column", 90),
        requested_mode="explore",
        executed_mode="explore",
    )
    context, snapshot = memory.retrieve_with_snapshot(
        rubric_version="rubric-v1",
        paper_profile=PROFILE,
        family_id="classic_three_column",
        mode="improve",
    )
    assert context["sample_count"] == 1
    assert snapshot["event_count"] == 1
    assert snapshot["corrupt_event_count"] == 0
    assert snapshot["digest"] != before["digest"]
