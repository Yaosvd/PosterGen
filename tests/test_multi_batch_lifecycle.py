"""Regression coverage for independently resumable Campaign Batches."""

import json
from types import SimpleNamespace

import pytest

from src.config.critic_config import load_critic_config
from src.workflow.campaign import CampaignManager
from src.workflow.campaign_runner import _finish


def _state(name="paper"):
    return {
        "poster_name": name,
        "raw_text": f"{name} identity",
        "poster_width": 54,
        "poster_height": 36,
    }


def test_multiple_paused_batches_require_explicit_selection(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign(_state(), resume_mode="new")

    batch_1 = manager.open_batch(
        handle, target_iterations=100, mode="mixed", new_batch=True,
    )
    manager.pause_batch(handle, batch_1, reason="switch_strategy")
    batch_2 = manager.open_batch(
        handle, target_iterations=100, mode="explore", new_batch=True,
    )
    manager.pause_batch(handle, batch_2, reason="switch_strategy")

    with pytest.raises(ValueError, match="selection is ambiguous"):
        manager.open_batch(handle, target_iterations=100)

    resumed = manager.open_batch(
        handle, target_iterations=999, batch_id=batch_1["batch_id"],
    )
    assert resumed["batch_id"] == "batch_0001"
    assert resumed["schedule_policy"]["mode"] == "mixed"
    assert resumed["target_iterations"] == 100
    assert resumed["status"] == "IN_PROGRESS"


def test_batch_ids_are_permanent_high_water_marks_and_campaign_scoped(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    first_campaign = manager.open_campaign(_state("paper-a"), resume_mode="new")
    first = manager.open_batch(first_campaign, target_iterations=1, new_batch=True)
    first["committed_iteration_ids"] = [1]
    manager.save_batch(first_campaign, first, complete=True)
    second = manager.open_batch(first_campaign, target_iterations=5, new_batch=True)
    manager.pause_batch(first_campaign, second, reason="later")
    manager.archive_batch(first_campaign, second["batch_id"])
    third = manager.open_batch(first_campaign, target_iterations=5, new_batch=True)

    assert [first["batch_id"], second["batch_id"], third["batch_id"]] == [
        "batch_0001", "batch_0002", "batch_0003",
    ]

    second_campaign = manager.open_campaign(_state("paper-b"), resume_mode="new")
    other = manager.open_batch(second_campaign, target_iterations=5, new_batch=True)
    assert other["batch_id"] == "batch_0001"
    assert other["campaign_id"] != first["campaign_id"]


def test_commits_are_owned_by_batch_and_resume_uses_latest_global_iteration(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    state = _state()
    handle = manager.open_campaign(state, resume_mode="new")
    batch_1 = manager.open_batch(handle, target_iterations=2, new_batch=True)
    attempt = manager.begin_iteration(
        handle,
        iteration=1,
        session_id="session-1",
        candidate={"candidate_id": "c1", "candidate_dir": str(tmp_path / "c1")},
        batch_id=batch_1["batch_id"],
    )
    loop_state = {
        "session_id": "session-1",
        "last_completed_iteration": 0,
        "batch": dict(batch_1),
    }
    manager.commit_iteration(
        handle,
        attempt,
        state=state,
        report={"candidate_id": "c1", "decision": "discard"},
        outcome={"accepted": False},
        loop_state=loop_state,
    )
    manager.pause_batch(handle, loop_state["batch"], reason="switch")

    batch_2 = manager.open_batch(handle, target_iterations=1, new_batch=True)
    second_attempt = manager.begin_iteration(
        handle,
        iteration=2,
        session_id="session-2",
        candidate={"candidate_id": "c2", "candidate_dir": str(tmp_path / "c2")},
        batch_id=batch_2["batch_id"],
    )
    second_loop = {
        "session_id": "session-2",
        "last_completed_iteration": 1,
        "batch": dict(batch_2),
    }
    manager.commit_iteration(
        handle,
        second_attempt,
        state=state,
        report={"candidate_id": "c2", "decision": "discard"},
        outcome={"accepted": False},
        loop_state=second_loop,
    )
    manager.save_batch(handle, second_loop["batch"], complete=True)

    resumed = manager.open_batch(
        handle, target_iterations=2, batch_id=batch_1["batch_id"],
    )
    assert resumed["committed_iteration_ids"] == [1]
    assert resumed["completed_iterations"] == 1
    assert resumed["knowledge_watermarks"]["last_resumed_after_iteration"] == 2

    marker_1 = json.loads(
        (handle.path / "iterations" / "000001" / "COMPLETED.json").read_text()
    )
    marker_2 = json.loads(
        (handle.path / "iterations" / "000002" / "COMPLETED.json").read_text()
    )
    assert marker_1["batch_id"] == "batch_0001"
    assert marker_2["batch_id"] == "batch_0002"


def test_recovery_turns_stale_running_batch_into_persistent_pause(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign(_state(), resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100, new_batch=True)

    assert manager.recover_incomplete(handle) == 0
    stored = manager.load_batch(handle, batch["batch_id"])
    campaign = manager.load_campaign_state(handle)
    assert stored["status"] == "PAUSED"
    assert stored["pause_reason"] == "recovered_after_process_exit"
    assert campaign["active_batch_id"] is None
    assert campaign["paused_batch_ids"] == [batch["batch_id"]]


def test_finish_persists_pause_and_failed_retry_is_explicit(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign(_state(), resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100, new_batch=True)
    loop_state = {
        "campaign_id": handle.campaign_id,
        "session_id": "session-1",
        "last_completed_iteration": 0,
        "accepted_count": 0,
        "rejected_count": 0,
        "template_count": 0,
        "validation_evidence_count": 0,
        "batch": dict(batch),
    }
    owner = SimpleNamespace(
        _active_campaign=handle,
        campaign_manager=manager,
        _checkpoint=lambda _state: None,
        _progress=lambda *_args, **_kwargs: None,
        _notify=lambda *_args, **_kwargs: None,
    )
    result = _finish(
        owner, {}, loop_state, tmp_path / "output", "user_requested"
    )
    assert result["loop_state"]["status"] == "PAUSED"
    assert manager.load_batch(handle, batch["batch_id"])["status"] == "PAUSED"

    failed = manager.open_batch(
        handle, target_iterations=100, batch_id=batch["batch_id"]
    )
    failed["status"] = "FAILED_REQUIRES_USER"
    manager.save_batch(handle, failed)
    with pytest.raises(ValueError, match="explicit retry"):
        manager.open_batch(handle, target_iterations=100)
    resumed = manager.open_batch(
        handle, target_iterations=100, batch_id=batch["batch_id"]
    )
    assert resumed["status"] == "IN_PROGRESS"


def test_cli_exposes_explicit_batch_selection_and_management():
    from src.workflow.critic_pipeline import build_parser

    parser = build_parser()
    selected = parser.parse_args([
        "--paper_path", "paper.pdf", "--campaign_id", "campaign-a",
        "--batch-id", "batch_0004",
    ])
    assert selected.batch_id == "batch_0004"
    assert not selected.new_batch

    created = parser.parse_args([
        "--paper_path", "paper.pdf", "--new-batch", "--mode", "mutate",
    ])
    assert created.new_batch
    assert created.mode == "mutate"

    managed = parser.parse_args([
        "--paper_path", "paper.pdf", "--archive-batch", "batch_0004",
    ])
    assert managed.archive_batch == "batch_0004"


def test_legacy_marker_after_counter_crash_is_attributed_safely(tmp_path):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign(_state(), resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100, new_batch=True)

    batch_path = handle.path / "batches" / batch["batch_id"] / "batch_state.json"
    legacy_batch = json.loads(batch_path.read_text())
    legacy_batch.pop("committed_iteration_ids", None)
    legacy_batch["schema_version"] = 3
    legacy_batch["completed_iterations"] = 0
    batch_path.write_text(json.dumps(legacy_batch), encoding="utf-8")
    campaign_path = handle.path / "campaign_state.json"
    legacy_campaign = json.loads(campaign_path.read_text())
    legacy_campaign["schema_version"] = 3
    legacy_campaign["active_batch"] = legacy_batch
    legacy_campaign.pop("active_batch_id", None)
    legacy_campaign.pop("batch_ids", None)
    campaign_path.write_text(json.dumps(legacy_campaign), encoding="utf-8")
    marker_path = handle.path / "iterations" / "000001" / "COMPLETED.json"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text(json.dumps({
        "campaign_id": handle.campaign_id,
        "iteration": 1,
        "attempt_id": "attempt-legacy",
    }), encoding="utf-8")

    migrated = manager.load_campaign_state(handle)
    stored = manager.load_batch(handle, batch["batch_id"])
    marker = json.loads(marker_path.read_text())
    assert migrated["schema_version"] == 4
    assert marker["batch_id"] == batch["batch_id"]
    assert stored["committed_iteration_ids"] == [1]
    assert stored["completed_iterations"] == 1
