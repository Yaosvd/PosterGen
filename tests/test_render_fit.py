"""Rendered editable text must be checked against its actual slide geometry."""

from src.agents.render_fit_audit import render_fit_audit_node
from src.agents.layout_agent import LayoutAgent
from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.evaluators import GeometryEvaluator
from src.layout.render_fit import evaluate_rendered_boxes
from src.workflow.campaign_runner import _retain_render_fit_preview


def _layout():
    return [
        {
            "type": "text", "id": "body_a", "section_id": "a", "zone_id": "z1",
            "content": "Grounded scientific content stays inside its editable module.",
            "x": 1.0, "y": 1.0, "width": 3.0, "height": 1.0,
        },
        {
            "type": "section_title", "id": "title_b", "section_id": "b",
            "x": 1.0, "y": 2.4, "width": 3.0, "height": 0.4,
        },
    ]


def test_actual_glyph_bounds_detect_overflow_and_cross_module_collision():
    text = _layout()[0]["content"]
    # PDF text blocks use x0/y0/x1/y1 in points, not the planned box height.
    blocks = [(72, 72, 270, 205, text, 0, 0)]
    report = evaluate_rendered_boxes(
        _layout(), blocks, poster_width=5, poster_height=4,
    )
    assert report["status"] == "failed"
    assert report["matched_text_count"] == 1
    assert {item["code"] for item in report["issues"]} == {
        "RENDER_TEXT_BOX_OVERFLOW", "RENDER_CROSS_SECTION_COLLISION",
    }


def test_unmatched_pdf_block_is_inconclusive_not_a_false_rejection():
    report = evaluate_rendered_boxes(
        _layout(), [(72, 72, 270, 205, "Unrelated header", 0, 0)],
        poster_width=5, poster_height=4,
    )
    assert report["status"] == "partial"
    assert report["passed"] is True
    assert report["issues"] == []


def test_render_audit_retries_loop_candidate_but_not_standalone(monkeypatch, tmp_path):
    failed = {"status": "failed", "issue_count": 1, "issues": [{"code": "X"}]}
    monkeypatch.setattr("src.agents.render_fit_audit.audit_rendered_text", lambda state: failed)
    state = {
        "generation_route": "optimization_family", "output_dir": str(tmp_path),
        "iteration_context": {"portfolio_mode": "explore"}, "errors": [],
    }
    render_fit_audit_node(state)
    assert state["layout_preflight_failed"] is True
    assert state["render_fit_report"] == failed
    assert (tmp_path / "content" / "render_fit_report.json").is_file()

    standalone = {"generation_route": "standalone_classic"}
    assert render_fit_audit_node(standalone) is standalone
    assert "render_fit_report" not in standalone


def test_strict_validation_uses_critic_instead_of_family_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.agents.render_fit_audit.audit_rendered_text",
        lambda state: {"status": "failed", "issue_count": 1, "issues": []},
    )
    state = {
        "generation_route": "optimization_family", "output_dir": str(tmp_path),
        "iteration_context": {"portfolio_mode": "validate"}, "errors": [],
    }
    render_fit_audit_node(state)
    assert not state.get("layout_preflight_failed")
    assert not state["errors"]


def test_strict_validation_rendered_fit_is_a_hard_geometry_issue():
    state = {
        "poster_width": 5, "poster_height": 4,
        "styled_layout": _layout(),
        "render_fit_report": {
            "status": "failed", "issues": [{
                "code": "RENDER_TEXT_BOX_OVERFLOW", "section_id": "a",
                "zone_id": "z1", "overflow_bottom_inches": 0.8,
            }],
        },
    }
    evaluation = GeometryEvaluator().evaluate(
        CriticContext(state=state, config=load_critic_config())
    )
    assert evaluation.passed is False
    assert any(item["issue_id"].startswith("RENDER_TEXT_BOX_OVERFLOW")
               for item in evaluation.issues)


def test_loop_reserves_rendered_line_height_without_changing_classic(monkeypatch):
    monkeypatch.setattr(
        "src.agents.layout_agent.measure_text_height",
        lambda **kwargs: {"optimal_height": 2.0},
    )
    monkeypatch.setattr(
        "src.agents.layout_agent.estimate_wrapped_line_count",
        lambda *args, **kwargs: 5,
    )
    agent = LayoutAgent()
    standalone = {"generation_route": "standalone_classic"}
    loop = {"generation_route": "optimization_family"}
    old = agent._measure_body_text(["Grounded scientific text."], 5, standalone)
    new = agent._measure_body_text(["Grounded scientific text."], 5, loop)
    assert old["height"] == 2.1
    assert new["height"] > old["height"]
    assert agent._inter_section_spacing(standalone) == 1.0
    assert 0.6 < agent._inter_section_spacing(loop) < 0.62


def test_failed_render_preview_is_retained_only_from_candidate_directory(tmp_path):
    candidate_dir = tmp_path / "candidate"
    attempt_dir = tmp_path / "attempt"
    candidate_dir.mkdir()
    attempt_dir.mkdir()
    png = candidate_dir / "poster.png"
    png.write_bytes(b"diagnostic")
    state = {"current_candidate": {
        "candidate_dir": str(candidate_dir), "png_path": str(png),
    }}
    assert _retain_render_fit_preview(attempt_dir, state)
    assert (attempt_dir / "render_fit_preview.png").read_bytes() == b"diagnostic"
    state["current_candidate"]["png_path"] = str(tmp_path / "outside.png")
    assert not _retain_render_fit_preview(attempt_dir, state)
