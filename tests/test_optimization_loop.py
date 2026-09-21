import zipfile
from copy import deepcopy
from pathlib import Path

from PIL import Image

from src.config.critic_config import load_critic_config
from src.templates.library import LoopStorage
from src.workflow.optimization_loop import PosterOptimizationLoop


class FakeCritic:
    def __call__(self, state):
        iteration = state["iteration_context"]["iteration"]
        accepted = iteration == 1
        state["critic_report"] = {
            "candidate_id": state["current_candidate"]["candidate_id"],
            "iteration": iteration,
            "strategy": state["iteration_context"]["strategy"],
            "decision": "archive" if accepted else "discard",
            "archive_eligible": accepted,
            "overall_score": 88 if accepted else 55,
            "dimension_scores": {"readability": 88},
            "issues": [] if accepted else [
                {"issue_id": "TEST", "observation": "test rejection"}
            ],
            "rejection_summary": "" if accepted else "test rejection",
            "critic_system_version": "test",
            "rubric_version": "test",
        }
        return state


def test_loop_archives_good_discards_bad_and_checkpoints(tmp_path):
    output = tmp_path / "output"
    state = {
        "output_dir": str(output),
        "poster_name": "paper",
        "poster_width": 54,
        "poster_height": 36,
        "verification_passed": True,
        "errors": [],
        "raw_text": "paper",
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

    def render_candidate(candidate_state):
        candidate = candidate_state["current_candidate"]
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
        candidate_state["story_board"] = deepcopy(board)
        candidate_state["optimized_story_board"] = deepcopy(board)
        candidate_state["styled_layout"] = [
            {"type": "section_container", "x": 1, "y": 8, "width": 15, "height": 8}
        ]
        return candidate_state

    config = load_critic_config()
    config["evaluators"]["visual"]["enabled"] = False
    storage = LoopStorage(tmp_path / "store", config)
    result = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=FakeCritic(),
        random_seed=3,
        batch_iterations=2,
        fresh_design_nodes=[render_candidate],
        revision_design_nodes=[render_candidate],
    ).run(state, foundation_ready=True)

    loop_state = result["loop_state"]
    assert loop_state["accepted_count"] == 1
    assert loop_state["rejected_count"] == 1
    assert loop_state["stop_reason"] == "batch_complete"
    assert loop_state["status"] == "COMPLETED"
    assert loop_state["batch"]["completed_iterations"] == 2
    assert (output / "paper.png").is_file()
    report_dir = (
        storage.root
        / "loop_sessions"
        / loop_state["session_id"]
        / "iterations"
    )
    assert len(list(report_dir.glob("*.json"))) == 2
    campaign = storage.root / "campaigns" / loop_state["campaign_id"]
    for number in (1, 2):
        iteration_dir = campaign / "iterations" / f"{number:06d}"
        assert (iteration_dir / "COMPLETED.json").is_file()
        assert (iteration_dir / "TEMPLATE_USAGE_APPLIED.json").is_file()
    assert len(list(
        (storage.root / "design_memory" / "global_knowledge" / "events").glob("*.json")
    )) == 2
    rejected = output / "iterations" / "000002"
    assert not (rejected / "paper.pptx").exists()
    assert not (rejected / "paper.png").exists()
