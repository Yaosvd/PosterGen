import io
import json
import sys
from types import SimpleNamespace

import pytest

from src.workflow.loop_progress import LoopProgressReporter, format_event
from src.workflow.pipeline import tee_console_output
from utils.src import logging_utils


def test_plain_progress_is_tee_logged_and_readable(tmp_path, capsys):
    log_path = tmp_path / "run.log"
    with tee_console_output(log_path):
        with LoopProgressReporter(log_path, terminal=io.StringIO()) as reporter:
            reporter.emit({
                "type": "iteration", "iteration": 32,
                "batch_ordinal": 1, "batch_target": 100, "attempt_number": 2,
                "mode": "explore", "strategy": "explore",
                "family": "classic_three_column", "lineage": "L1",
                "template_ids": [],
            })
            reporter.emit({
                "type": "committed", "iteration": 32, "completed": 1,
                "target": 100, "accepted": 1, "rejected": 0, "templates": 1,
                "archive": "/archive/c32", "template": {
                    "registered": True, "template_id": "T32",
                }, "best": True,
            })
            reporter.emit({
                "type": "error", "iteration": 33, "stage": "renderer",
                "error_type": "RuntimeError", "message": "render failed",
            })
            reporter.write_traceback("Traceback: example")
    output = capsys.readouterr().out
    log = log_path.read_text()
    assert "Batch 1/100 | I32 attempt 2" in output
    assert "template saved T32" in output
    assert "ERROR at renderer (RuntimeError)" in output
    assert "Traceback: example" in log
    assert "Traceback: example" not in output


def test_progress_format_distinguishes_rejected_and_validation():
    line = format_event({
        "type": "committed", "iteration": 5, "archive": None,
        "template": {"registered": False, "reason": "poster_rejected"},
        "rejected_artifact": {
            "saved": True,
            "archive_dir": "/store/rejected/candidate-5",
        },
        "validation": "T1 failed", "best": False,
    })
    assert "poster not archived" in line
    assert "template not saved (poster_rejected)" in line
    assert "rejected diagnostic saved at /store/rejected/candidate-5" in line
    assert "validation T1 failed" in line
    fallback = format_event({
        "type": "no_change_safe_fallback",
        "iteration": 6,
        "parent_candidate": "parent-1",
    })
    assert "no new design" in fallback
    assert "Batch budget consumed" in fallback
    assert "no poster archive, template, or global design event" in fallback


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


def test_live_panel_restores_logger_and_keeps_run_log_plain(tmp_path):
    terminal = FakeTTY()
    log_path = tmp_path / "run.log"
    original_console = logging_utils.console
    with LoopProgressReporter(log_path, terminal=terminal) as reporter:
        reporter.emit({
            "type": "session", "campaign_id": "C1", "batch_id": "B1",
            "mode": "mixed", "resumed": False, "completed": 0, "target": 100,
        })
        logging_utils.log_agent_info("renderer", "working", show_location=False)
    assert logging_utils.console is original_console
    assert logging_utils.progress_log_sink is None
    log = log_path.read_text()
    assert "Campaign C1 created" in log
    assert "[Renderer INFO] working" in log
    assert "\x1b[" not in log
    assert "PosterGen optimization" in terminal.getvalue()


@pytest.mark.parametrize("status,exit_code", [
    ("COMPLETED", 0), ("FAILED_REQUIRES_USER", 1), ("UNAVAILABLE", 1),
])
def test_cli_exit_code_follows_loop_status(tmp_path, monkeypatch, status, exit_code):
    from src.workflow import critic_pipeline

    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\n")
    output = tmp_path / "output"

    def fake_state(*_args):
        return {"output_dir": str(output), "timing_metrics": SimpleNamespace(
            pipeline_start=None, pipeline_end=None,
        )}

    class FakeLoop:
        def __init__(self, **kwargs):
            self.reporter = kwargs["progress_reporter"]

        def run(self, state):
            self.reporter.emit({
                "type": "session", "campaign_id": "C1", "batch_id": "B1",
                "mode": "mixed", "resumed": False, "completed": 0, "target": 100,
            })
            state["loop_state"] = {
                "status": status, "campaign_id": "C1",
                "last_completed_iteration": 0,
                "batch": {"batch_id": "B1", "completed_iterations": 0,
                          "target_iterations": 100},
            }
            return state

    monkeypatch.setattr(critic_pipeline, "create_state", fake_state)
    monkeypatch.setattr(critic_pipeline, "PosterOptimizationLoop", FakeLoop)
    monkeypatch.setattr(critic_pipeline, "save_timing_log", lambda _state: None)
    monkeypatch.setattr(sys, "argv", ["critic_pipeline", "--paper_path", str(paper)])
    assert critic_pipeline.main() == exit_code
    assert "Campaign C1 created" in (output / "run.log").read_text()


def test_cli_uncaught_loop_error_is_nonzero_and_logged(tmp_path, monkeypatch):
    from src.workflow import critic_pipeline

    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\n")
    output = tmp_path / "output"

    class BrokenLoop:
        def __init__(self, **_kwargs):
            pass

        def run(self, _state):
            raise RuntimeError("sample failure")

    monkeypatch.setattr(
        critic_pipeline, "create_state",
        lambda *_args: {"output_dir": str(output),
                        "timing_metrics": SimpleNamespace(pipeline_start=None)},
    )
    monkeypatch.setattr(critic_pipeline, "PosterOptimizationLoop", BrokenLoop)
    monkeypatch.setattr(sys, "argv", ["critic_pipeline", "--paper_path", str(paper)])
    assert critic_pipeline.main() == 1
    log = (output / "run.log").read_text()
    assert "ERROR at startup_or_shutdown (RuntimeError): sample failure" in log
    assert "RuntimeError: sample failure" in log
    assert "Traceback" in log


def test_validation_summary_reports_level_without_other_templates(tmp_path):
    from src.templates.library import TemplateLibrary

    library = TemplateLibrary(tmp_path)
    library.index_path.parent.mkdir(parents=True)
    library.index_path.write_text(json.dumps({
        "schema_version": 8,
        "templates": [
            {"template_id": "T1", "template_level": 2,
             "validation_status": "cross_profile"},
            {"template_id": "T2", "template_level": 0,
             "validation_status": "pending"},
        ],
    }))
    assert library.validation_summaries(["T1"]) == {
        "T1": {
            "level": 2,
            "status": "cross_profile",
            "trial_status": None,
            "attempts_completed": 0,
            "max_attempts": 3,
            "blocked_reason": "missing_strict_topology",
        }
    }


def test_validation_snapshot_reports_eligible_and_blocked_templates():
    line = format_event({
        "type": "validation_snapshot", "eligible_count": 4,
        "blocked_templates": [{
            "template_id": "legacy-template",
            "reason": "missing_strict_topology",
        }],
        "frozen": True,
    })
    assert "Validation snapshot: 4 eligible" in line
    assert "frozen for this Batch" in line
    assert "legacy-template (missing_strict_topology)" in line


def test_progress_reports_validation_evidence_without_new_template():
    line = format_event({
        "type": "committed",
        "iteration": 9,
        "archive": "/store/validation_evidence/T1/P1/C1",
        "template": {
            "registered": False,
            "reason": "validation_updates_existing_template",
            "template_id": "T1",
            "new_template_created": False,
        },
        "validation_evidence": {
            "saved": True,
            "archive_dir": "/store/validation_evidence/T1/P1/C1",
        },
        "validation": "T1 cross-paper attempt 1/3 passed L1",
    })
    assert "validation poster evidence saved at" in line
    assert "source template T1 updated" in line
    assert "no new template created" in line
    assert "template not saved" not in line
