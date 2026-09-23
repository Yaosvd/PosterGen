import json
import zipfile
from copy import deepcopy
from pathlib import Path

from PIL import Image

from src.config.critic_config import load_critic_config
from src.templates.library import LoopStorage
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
