"""WebUI Batch administration API regressions."""

import json

from fastapi.testclient import TestClient

from src.config.critic_config import load_critic_config
from src.workflow.campaign import CampaignManager
from webui.backend import main as backend


def _state():
    return {
        "poster_name": "paper",
        "raw_text": "identity",
        "poster_width": 54,
        "poster_height": 36,
    }


def test_webui_lists_selects_and_archives_persisted_batches(
    tmp_path, monkeypatch,
):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = manager.open_campaign(_state(), resume_mode="new")
    batch = manager.open_batch(
        handle, target_iterations=100, mode="mixed", new_batch=True
    )
    monkeypatch.setattr(backend, "_batch_manager", lambda: manager)
    client = TestClient(backend.app)

    listed = client.get(f"/campaigns/{handle.campaign_id}/batches")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["active_batch_id"] == batch["batch_id"]
    assert payload["batches"][0]["status"] == "IN_PROGRESS"
    assert payload["batches"][0]["mode"] == "mixed"

    running_archive = client.post(
        f"/campaigns/{handle.campaign_id}/batches/"
        f"{batch['batch_id']}/archive"
    )
    assert running_archive.status_code == 409

    manager.pause_batch(handle, batch, reason="webui_test")
    archived = client.post(
        f"/campaigns/{handle.campaign_id}/batches/"
        f"{batch['batch_id']}/archive"
    )
    assert archived.status_code == 200
    assert archived.json()["batch"]["status"] == "ARCHIVED"

    unarchived = client.post(
        f"/campaigns/{handle.campaign_id}/batches/"
        f"{batch['batch_id']}/unarchive"
    )
    assert unarchived.status_code == 200
    assert unarchived.json()["batch"]["status"] == "PAUSED"

    detail = client.get(
        f"/campaigns/{handle.campaign_id}/batches/{batch['batch_id']}"
    )
    assert detail.status_code == 200
    assert detail.json()["state"]["knowledge_watermarks"][
        "created_after_iteration"
    ] == 0

    report_path = (
        handle.path / "batches" / batch["batch_id"] / "batch_report.json"
    )
    report_path.write_text(
        json.dumps({"batch_id": batch["batch_id"], "status": "PAUSED"}),
        encoding="utf-8",
    )
    report = client.get(
        f"/campaigns/{handle.campaign_id}/batches/"
        f"{batch['batch_id']}/report"
    )
    assert report.status_code == 200
    assert report.json()["batch_id"] == batch["batch_id"]


def test_webui_batch_admin_rejects_unknown_campaign(tmp_path, monkeypatch):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    monkeypatch.setattr(backend, "_batch_manager", lambda: manager)
    client = TestClient(backend.app)
    response = client.get("/campaigns/missing_campaign/batches")
    assert response.status_code == 404
