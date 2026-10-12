"""CPU-only oracle tests: reuse may change cost, never measurement or selection."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
import json

import pytest

from src.agents.layout_agent import LayoutAgent
from src.agents.layout_with_balancer import LayoutWithBalancerAgent
from src.config.critic_config import load_critic_config
from src.layout.families import LayoutFamilyRegistry
from src.layout.feasibility import LayoutFeasibilityError, fit_family_layout
from src.layout.measurement_context import (
    current_context, measurement_scope, progress_observer, validate_settings,
)
import src.layout.measurement_context as context_module
import src.layout.text_fit_adapter as adapter
import src.layout.text_height_measurement as measurement
from src.workflow.campaign_runner import _reset_attempt_diagnostics
from src.workflow.loop_progress import format_event


@pytest.mark.parametrize("text,width,extra", [
    ("", 12, {}), ("   ", 12, {}),
    ("A grounded claim.", 12, {}),
    ("First line.\n\nSecond line.", 4.1, {}),
    ("Many  spaces\tand words\nExplicit line.", 3.02, {}),
    ("Boundary wrapping with several words.", 2.81, {}),
    ("Boundary wrapping with several words.", 2.810001, {}),
    ("Long bold section title wrapping to multiple lines", 8, {"bold": True, "font_size": 64}),
    ("中文测试 café α β – scientific text", 9, {}),
    ("x<sub>2</sub> and y<sup>3</sup>", 5, {}),
    ("Averylongunbrokenwordwhichcannotfit", 0.5, {}),
    ("Alternate font sample", 7, {"font_name": "Helvetica Neue"}),
    ("Fractional size", 6, {"font_size": 44.5, "line_spacing": 1.2}),
    ("Margined text", 6, {"margins": {"left": 0.3, "right": 0.2}}),
    ("Verified result.\nε = (α × a) / b\nGrounded conclusion.", 8, {}),
])
def test_exact_measurement_matches_original_and_returns_fresh_copy(text, width, extra):
    baseline = measurement.measure_text_height(text, width, **extra)
    if "ε =" in text:
        assert baseline["display_formula_count"] == 1
    with measurement_scope() as context:
        first = measurement.measure_text_height(text, width, **extra)
        assert first == baseline
        first["optimal_height"] = -1
        assert measurement.measure_text_height(text, width, **extra) == baseline
        # Legacy impossible-width inputs can legitimately report fit errors;
        # they must never be stored as reusable successful measurements.
        if context.failures:
            assert context.stats["exact"]["hits"] == 0
        else:
            assert context.stats["exact"]["hits"] >= 1
    assert current_context() is None and not context.cache


@pytest.mark.parametrize("extra", [
    {}, {"bold": True}, {"font_width_factor": 1.1},
    {"render_width_factor": 0.98}, {"margins": {"left": 0.3}},
])
def test_estimated_wrapping_matches_original(extra):
    text = "Verified first line.\n\nAnother line with café and 中文."
    baseline = measurement.estimate_wrapped_line_count(text, 5, "Arial", 44, **extra)
    with measurement_scope() as context:
        assert measurement.estimate_wrapped_line_count(text, 5, "Arial", 44, **extra) == baseline
        assert measurement.estimate_wrapped_line_count(text, 5, "Arial", 44, **extra) == baseline
        assert context.stats["line"]["hits"] == 1


def test_cache_keys_include_text_width_style_and_config(monkeypatch):
    calls = []
    def plain(**values):
        calls.append(values)
        return {"optimal_height": float(len(calls))}
    monkeypatch.setattr(measurement, "_measure_plain_text_height", plain)
    with measurement_scope() as context:
        for kwargs in ({}, {"width_inches": 12.000001}, {"bold": True},
                       {"font_size": 45}, {"line_spacing": 1.2},
                       {"precision": 0.002}, {"margins": {"left": 0.4}},
                       {"text_content": "Changed wording."}):
            measurement.measure_text_height(**{"text_content": "Verified text", "width_inches": 12, **kwargs})
        assert len(calls) == 8
        config = measurement.load_config()
        config["text_measurement"]["newline_offset_ratio"] += 0.01
        monkeypatch.setattr(measurement, "load_config", lambda: deepcopy(config))
        measurement.measure_text_height("Verified text", 12)
        assert len(calls) == 9
        assert context.stats["exact"]["hits"] == 0


def test_config_file_and_font_file_changes_invalidate(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("value: 1")
    monkeypatch.setattr(context_module, "CONFIG_PATH", config_path)
    calls = []
    def config_loader():
        calls.append(1)
        return {"value": config_path.read_text()}
    with measurement_scope() as context:
        assert context.config(config_loader) == {"value": "value: 1"}
        context.config(config_loader)
        assert len(calls) == 1
        config_path.write_text("value: changed")
        assert context.config(config_loader) == {"value": "value: changed"}
        assert len(calls) == 2
    font_path = tmp_path / "font.ttf"
    font_path.write_bytes(b"first")
    monkeypatch.setattr(measurement, "get_font_file_path", lambda *a, **k: str(font_path))
    calls.clear()
    monkeypatch.setattr(measurement, "_measure_plain_text_height",
                        lambda **kwargs: calls.append(1) or {"optimal_height": 1.0})
    with measurement_scope():
        measurement.measure_text_height("Text", 12)
        measurement.measure_text_height("Text", 12)
        font_path.write_bytes(b"second-font")
        measurement.measure_text_height("Text", 12)
    assert len(calls) == 2


def test_lru_eviction_and_payload_limit_change_only_cost():
    with measurement_scope({"exact_cache_entries": 1, "max_text_payload_bytes": 16}) as context:
        def get(key):
            return context.memo("exact", key, lambda: {"height": len(key)}, clone=True)
        assert get("a") == get("a") == {"height": 1}
        assert get("bb") == {"height": 2}
        assert get("a") == {"height": 1}
        assert context.stats["exact"]["evictions"] == 2
        assert get("x" * 100) == {"height": 100}
        assert context.payload_bytes <= 16
        assert context.counts["exact"] <= 1


@pytest.mark.parametrize("entries", [0, 1])
def test_eviction_or_disabled_buckets_preserve_real_measurement(entries):
    baseline = measurement.measure_text_height("Verified evidence.", 12)
    settings = {f"{bucket}_cache_entries": entries for bucket in ("exact", "line", "wrap", "glyph", "font")}
    settings["max_text_payload_bytes"] = 64
    with measurement_scope(settings) as context:
        assert measurement.measure_text_height("Verified evidence.", 12) == baseline
        assert measurement.measure_text_height("Verified evidence.", 12) == baseline
        assert context.peak_payload_bytes <= 64


def test_failures_never_enter_cache_and_unknown_versions_use_original(monkeypatch):
    monkeypatch.setattr(adapter, "backend_versions", lambda: ("future", "future"))
    expected = measurement.measure_text_height("Verified text", 12)
    with measurement_scope() as context:
        assert measurement.measure_text_height("Verified text", 12) == expected
        assert context.fallbacks["unverified_dependency_version"] > 0
    with measurement_scope() as context:
        def fail():
            raise RuntimeError("injected failure")
        for _ in range(2):
            with pytest.raises(RuntimeError):
                context.memo("exact", "key", fail)
        assert not context.cache


def test_legacy_fit_errors_are_not_cached(monkeypatch):
    def failing_fit(*args, **kwargs):
        raise ValueError("injected font failure")
    monkeypatch.setattr(measurement, "fit_text", failing_fit)
    baseline = measurement.measure_text_height("Text", 12)
    with measurement_scope() as context:
        assert measurement.measure_text_height("Text", 12) == baseline
        assert measurement.measure_text_height("Text", 12) == baseline
        assert context.failures > 0
        assert context.stats["exact"]["hits"] == 0


def test_adapter_programming_errors_fail_closed_instead_of_becoming_text_overflow(monkeypatch):
    def broken(*args, **kwargs):
        raise AttributeError("injected adapter bug")
    monkeypatch.setattr(adapter._CachedTextFitter, "best_fit_font_size", broken)
    with measurement_scope() as context:
        with pytest.raises(adapter.OptimizedFitError, match="Unexpected cached"):
            measurement.measure_text_height("Verified content", 12)
        assert context.stats["exact"]["hits"] == 0 and not context.counts["exact"]


def test_adapter_error_disagreement_cannot_be_silently_cached(monkeypatch):
    def broken(*args, **kwargs):
        raise TypeError("injected non-library bug")
    monkeypatch.setattr(adapter._CachedTextFitter, "best_fit_font_size", broken)
    with measurement_scope():
        with pytest.raises(adapter.OptimizedFitError, match="disagreed"):
            measurement.measure_text_height("Verified content", 12)


@pytest.mark.parametrize("mode", ["initial", "final"])
def test_compile_wrapper_cannot_turn_adapter_bug_into_geometry_retry(monkeypatch, mode):
    import src.agents.layout_agent as layout_module
    agent = LayoutAgent()
    board = {"spatial_content_plan": {"sections": [{"section_id": "s0"}]}}
    state = {"generation_route": "optimization_family", "errors": [],
             "story_board": board, "optimized_story_board": board}
    spec = {"family_id": "classic_three_column", "zones": [{"section_ids": ["s0"]}]}
    monkeypatch.setattr(agent, "_ensure_layout_spec", lambda *args: spec)
    def broken(*args):
        raise adapter.OptimizedFitError("injected compilation adapter error")
    monkeypatch.setattr(layout_module, "compile_layout", broken)
    with pytest.raises(adapter.OptimizedFitError, match="compilation adapter error"):
        agent(state, mode=mode)
    assert not state["errors"] and not state.get("layout_preflight_failed")


def test_missing_font_identity_keeps_original_error_behavior(monkeypatch, tmp_path):
    monkeypatch.setattr(measurement, "get_font_file_path", lambda *a, **k: str(tmp_path / "missing.ttf"))
    expected = measurement.measure_text_height("Text", 12)
    with measurement_scope() as context:
        assert measurement.measure_text_height("Text", 12) == expected
        assert context.stats["exact"]["hits"] == 0


@pytest.mark.parametrize("outcome", ["committed", "preflight_retry", "generation_error"])
def test_attempt_report_persistence_without_scientific_snapshot_pollution(tmp_path, outcome, monkeypatch):
    from test_generation_failure import make_loop
    from test_campaign_resume import _state, _render_candidate
    from src.workflow.optimization_loop import LoopControl
    control = LoopControl()
    def node(state):
        with measurement_scope() as context:
            measurement.measure_text_height("Private evidence wording", 12)
            state["layout_performance_report"] = context.report("completed")
        if outcome == "generation_error":
            raise RuntimeError("injected failure after measurement")
        if outcome == "preflight_retry":
            state["layout_preflight_failed"] = True
            state["layout_feasibility_report"] = {"status": "infeasible"}
            return state
        _render_candidate(state)
        control.request_stop()
        return state
    loop = make_loop(tmp_path, node, control=control)
    if outcome == "preflight_retry":
        original_progress = loop._progress
        def progress(*args, **kwargs):
            result = original_progress(*args, **kwargs)
            if args[1] == "layout_fit_retry":
                control.request_stop(force=True)
            return result
        monkeypatch.setattr(loop, "_progress", progress)
    result = loop.run(_state(tmp_path / "run"), foundation_ready=True)
    root = loop.storage.root / "campaigns" / result["loop_state"]["campaign_id"]
    reports = list(root.glob("iterations/*/attempts/*/layout_performance_report.json"))
    assert len(reports) == 1
    assert "Private evidence wording" not in reports[0].read_text()
    if outcome == "committed":
        snapshot = json.loads((reports[0].parent / "state_snapshot.json").read_text())
        assert "layout_performance_report" not in snapshot["fields"]
    else:
        assert not list(root.glob("iterations/*/COMPLETED.json"))


def test_scope_cleanup_nested_contexts_and_copied_thread_context():
    with pytest.raises(RuntimeError):
        with measurement_scope() as parent:
            parent.memo("exact", "key", lambda: 1)
            with measurement_scope() as child:
                assert child is not parent and not child.cache
            assert current_context() is parent
            copied = copy_context()
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(copied.run, current_context).result() is None
            raise RuntimeError("exit")
    assert current_context() is None and not parent.cache and parent.configuration is None


def test_copied_context_cannot_reactivate_closed_attempt():
    with measurement_scope():
        copied = copy_context()
    assert copied.run(current_context) is None


def test_config_changed_during_measurement_does_not_cache_result(monkeypatch, tmp_path):
    path = tmp_path / "poster_config.yaml"
    path.write_text("first")
    monkeypatch.setattr(context_module, "CONFIG_PATH", path)
    calls = []
    def plain(**kwargs):
        calls.append(1)
        path.write_text(f"changed {len(calls)}")
        return {"optimal_height": 1.0}
    monkeypatch.setattr(measurement, "_measure_plain_text_height", plain)
    with measurement_scope() as context:
        measurement.measure_text_height("Verified", 12)
        measurement.measure_text_height("Verified", 12)
        assert len(calls) == 2 and not context.counts["exact"]


def test_diagnostic_write_failure_does_not_mask_generation_error(monkeypatch, tmp_path):
    from pathlib import Path
    agent = LayoutWithBalancerAgent.__new__(LayoutWithBalancerAgent)
    agent.name = "layout_with_balancer"
    def engine(*args):
        raise RuntimeError("original layout failure")
    monkeypatch.setattr(agent, "_run_family_constraint_engine", engine)
    original_open = Path.open
    def guarded_open(path, *args, **kwargs):
        if path.name == "layout_performance_report.json":
            raise PermissionError("injected telemetry write failure")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)
    state = {"generation_route": "optimization_family", "output_dir": str(tmp_path)}
    result = agent(state)
    assert "original layout failure" in result["errors"][-1]
    assert result["layout_performance_report"]["output_write_error"] == "PermissionError"
    assert current_context() is None


@pytest.mark.parametrize("setting,value", [
    ("enabled", "false"), ("exact_cache_entries", -1),
    ("line_cache_entries", True), ("wrap_cache_entries", 65537),
    ("max_text_payload_bytes", 1.5),
])
def test_invalid_settings_fail_closed(setting, value):
    with pytest.raises(ValueError, match="layout_performance"):
        validate_settings({setting: value})


def test_disabled_mode_runs_original_and_records_misses():
    baseline = measurement.measure_text_height("Verified content", 10)
    with measurement_scope({"enabled": False}) as context:
        assert measurement.measure_text_height("Verified content", 10) == baseline
        assert measurement.measure_text_height("Verified content", 10) == baseline
        assert context.stats["exact"]["computed"] == 2
        assert not context.cache


def test_route_scope_and_error_report_are_isolated(monkeypatch, tmp_path):
    agent = LayoutWithBalancerAgent.__new__(LayoutWithBalancerAgent)
    agent.name = "layout_with_balancer"
    contexts = []
    def engine(state, family):
        contexts.append(current_context())
        measurement.measure_text_height("PRIVATE SCIENTIFIC CONTENT", 12)
        raise RuntimeError("injected generation error")
    monkeypatch.setattr(agent, "_run_family_constraint_engine", engine)
    state = {"generation_route": "optimization_family", "output_dir": str(tmp_path),
             "iteration_context": {"layout_family": "classic_three_column"}}
    agent(state)
    report = json.loads((tmp_path / "content/layout_performance_report.json").read_text())
    assert report["status"] == "error" and report["caches"]["exact"]["computed"] == 1
    assert "PRIVATE SCIENTIFIC CONTENT" not in json.dumps(report)
    assert not contexts[0].cache and current_context() is None
    def classic(state, *, mode):
        assert current_context() is None
        raise RuntimeError("classic route reached")
    agent.layout_agent = classic
    standalone = {"generation_route": "standalone_classic", "errors": []}
    agent(standalone)
    assert "layout_performance_report" not in standalone
    _reset_attempt_diagnostics(state)
    assert state["layout_performance_report"] is None


def test_progress_observer_is_runtime_only_and_has_subphase_timings():
    events = []
    with progress_observer(events.append), measurement_scope() as context:
        with context.phase("family_fit", family_id="classic_three_column"):
            with context.phase("exact_candidate", candidate=1):
                measurement.measure_text_height("Evidence", 12)
        report = context.report("completed")
    assert any("Layout: exact_candidate started" in format_event(event) for event in events)
    assert len(report["phases"]) == 2
    assert report["phases"][0]["parent_id"] == report["phases"][1]["id"]
    assert "Evidence" not in json.dumps(report)


@pytest.mark.parametrize("family_id", LayoutFamilyRegistry().ids())
@pytest.mark.parametrize("mode", ["explore", "improve", "validate"])
def test_all_families_keep_real_compiled_results_with_reuse(family_id, mode):
    board = {"spatial_content_plan": {"sections": [
        {"section_id": f"s{i}", "section_title": "Module", "importance_level": 2,
         "claim_ids": [f"c{i}"], "text_content": ["Verified evidence."], "visual_assets": []}
        for i in range(6)
    ]}}
    state = {"poster_width": 54, "poster_height": 36, "generation_route": "optimization_family",
             "iteration_context": {"random_seed": 3, "portfolio_mode": mode}}
    from src.layout.feasibility import generate_zone_variants
    zones = generate_zone_variants(LayoutFamilyRegistry().get(family_id), random_seed=3, maximum=1)[0]["zones"]
    if mode == "improve":
        state["revision_parent_layout_spec"] = {"family_id": family_id, "zones": zones}
    fixed_zones = zones if mode == "validate" else None
    from src.agents.section_title_designer import SectionTitleDesigner
    state["section_title_design"] = SectionTitleDesigner()._generate_colorblock_design(
        board, {"theme": "#123456"},
    )
    config = {"explore_layout": {"max_geometry_candidates_per_family": 1,
              "max_adaptive_geometry_candidates": 1, "max_exact_candidates": 1,
              "max_exact_refill_steps": 1, "max_near_miss_rechecks": 0},
              "improve_layout": {"local_geometry_candidates": 1}}
    def run(enabled):
        with progress_observer(lambda event: None), measurement_scope({"enabled": enabled}):
            try:
                return fit_family_layout(LayoutAgent(), deepcopy(board), deepcopy(state),
                                         family_id, config=config, fixed_zones=fixed_zones)
            except LayoutFeasibilityError as exc:
                return exc.report
    assert run(True) == run(False)
