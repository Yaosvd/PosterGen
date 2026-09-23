import json
import zipfile
from copy import deepcopy
from pathlib import Path

from PIL import Image

from src.config.critic_config import load_critic_config
from src.templates.library import LoopStorage, TemplateLibrary
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
    progress_path = storage.root / "loop_sessions" / loop_state["session_id"] / "progress_events.jsonl"
    events = [json.loads(line) for line in progress_path.read_text().splitlines()]
    assert [event["type"] for event in events].count("iteration") == 2
    assert [event["type"] for event in events].count("critic") == 2
    committed = [event for event in events if event["type"] == "committed"]
    assert [event["completed"] for event in committed] == [1, 2]
    assert committed[0]["archive"]
    assert not committed[1]["archive"]
    assert events[-1]["type"] == "finished"
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


class FakeValidationCritic:
    def __call__(self, state):
        iteration = state["iteration_context"]["iteration"]
        state["critic_report"] = {
            "candidate_id": state["current_candidate"]["candidate_id"],
            "iteration": iteration,
            "strategy": "validate",
            "decision": "archive",
            "archive_eligible": True,
            "template_eligible": True,
            "overall_score": 94,
            "dimension_scores": {"readability": 94},
            "issues": [],
            "rejection_summary": "",
            "critic_system_version": "test",
            "rubric_version": "test",
            "task_evaluation": {
                "task": "strict_template_transfer",
                "passed": True,
                "reasons": [],
            },
        }
        return state


def test_pure_validate_updates_source_template_without_creating_one(tmp_path):
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

    def render_validation(candidate_state):
        candidate = candidate_state["current_candidate"]
        pptx = Path(candidate["pptx_path"])
        pptx.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(pptx, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
        Image.new("RGB", (20, 10), "white").save(candidate["png_path"])
        candidate_state["story_board"] = {
            "spatial_content_plan": {"sections": []}
        }
        candidate_state["styled_layout"] = []
        return candidate_state

    config = load_critic_config()
    storage = LoopStorage(tmp_path / "store", config)
    library = TemplateLibrary(storage.root, config)
    assert library.register({
        "template_id": "source-template",
        "status": "paper_specific",
        "family": "classic_three_column",
        "fingerprint": "source-template-fingerprint",
        "source_paper_id": "different-paper",
        "source_profile": "balanced:medium",
        "overall_score": 91,
        "signature_vector": [0.2, 0.4],
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": ["clear hierarchy"],
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
        "usage": {
            "times_retrieved": 0,
            "successful_papers": ["different-paper"],
            "successful_profiles": ["balanced:medium"],
        },
    })["registered"]
    before = library._load()["templates"][0]
    frozen_structure = {
        key: deepcopy(before.get(key))
        for key in (
            "fingerprint",
            "family",
            "normalized_blueprint",
            "zone_topology",
            "template_design_score",
            "template_evaluation",
        )
    }

    result = PosterOptimizationLoop(
        config=config,
        storage=storage,
        critic=FakeValidationCritic(),
        random_seed=3,
        batch_mode="validate",
        batch_iterations=1,
        fresh_design_nodes=[render_validation],
        revision_design_nodes=[render_validation],
    ).run(state, foundation_ready=True)

    loop = result["loop_state"]
    assert loop["status"] == "COMPLETED"
    assert loop["template_count"] == 0
    assert loop["validation_evidence_count"] == 1
    assert loop["portfolio_state"]["lineages"] == {}
    assert loop["portfolio_state"]["family_counts"] == {}
    assert not (storage.root / "accepted_posters").exists()
    evidence_dirs = [
        path for path in (storage.root / "validation_evidence").glob("*/*/*")
        if path.is_dir()
    ]
    assert len(evidence_dirs) == 1
    assert (evidence_dirs[0] / "poster.pptx").is_file()
    assert (evidence_dirs[0] / "poster.png").is_file()
    assert not list(evidence_dirs[0].glob("template.*"))

    templates = library._load()["templates"]
    assert len(templates) == 1
    stored = templates[0]
    assert {
        key: stored.get(key) for key in frozen_structure
    } == frozen_structure
    assert stored["usage"]["times_retrieved"] == 0
    assert stored["template_level"] == 1
    assert loop["paper_id"] in stored["validation"]["successful_papers"]
    assert not list(
        (storage.root / "design_memory" / "global_knowledge" / "events").glob(
            "*.json"
        )
    )
    outcome_path = next(
        (storage.root / "campaigns").glob(
            "*/iterations/000001/attempts/*/outcome.json"
        )
    )
    outcome = json.loads(outcome_path.read_text())
    assert outcome["template_registration"] == {
        "registered": False,
        "reason": "validation_updates_existing_template",
        "template_id": "source-template",
        "new_template_created": False,
    }
    assert outcome["validation_evidence"]["saved"] is True
