"""Read-only CPU benchmarks; never execute models, renderers or Campaign commits."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import time

from src.layout.measurement_context import measurement_scope, progress_observer
from src.layout.text_height_measurement import measure_text_height


def benchmark_samples(samples):
    rows = []
    for sample in samples:
        with measurement_scope({"enabled": False}):
            start = time.perf_counter()
            original = measure_text_height(**sample)
            original_seconds = time.perf_counter() - start
        with measurement_scope() as context:
            start = time.perf_counter()
            cold = measure_text_height(**sample)
            cold_seconds = time.perf_counter() - start
            start = time.perf_counter()
            warm = measure_text_height(**sample)
            warm_seconds = time.perf_counter() - start
            if not original == cold == warm:
                raise AssertionError("Measurement benchmark failed exact equivalence")
            rows.append({
                "characters": len(sample["text_content"]),
                "original_seconds": round(original_seconds, 6),
                "optimized_cold_seconds": round(cold_seconds, 6),
                "optimized_warm_seconds": round(warm_seconds, 6),
                "cold_speedup": round(original_seconds / max(cold_seconds, 1e-9), 3),
                "exactly_equal": True, "measurement_failures": context.failures,
                "caches": deepcopy(context.stats),
            })
    return rows


def replay_layout(state, board, family_id, config):
    """Compare pure Solver inputs, not LLM repair or the complete old iteration."""
    from src.agents.layout_agent import LayoutAgent
    from src.layout.feasibility import LayoutFeasibilityError, fit_family_layout
    outcomes, rows = [], []
    for enabled in (False, True):
        with progress_observer(lambda event: None), measurement_scope({"enabled": enabled}) as context:
            start = time.perf_counter()
            try:
                topology = state.get("template_validation_topology") or {}
                result = fit_family_layout(LayoutAgent(), deepcopy(board), deepcopy(state),
                                           family_id, config=deepcopy(config),
                                           fixed_zones=deepcopy(topology.get("zones")))
            except LayoutFeasibilityError as exc:
                result = exc.report
            outcomes.append(result)
            rows.append({"enabled": enabled, "elapsed_seconds": round(time.perf_counter() - start, 6),
                         "caches": deepcopy(context.stats)})
    if outcomes[0] != outcomes[1]:
        raise AssertionError("Solver replay failed exact equivalence")
    return {"scope": "pure_solver_only", "exactly_equal": True, "runs": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--candidate-dir", type=Path,
                        help="Read saved optimized_story_board and optional layout/style data")
    inputs.add_argument("--replay-input", type=Path,
                        help="Read a complete JSON object containing state, board, family_id and config")
    parser.add_argument("--sample-limit", type=int, default=3)
    args = parser.parse_args()
    if args.sample_limit < 1:
        parser.error("--sample-limit must be positive")
    if args.replay_input:
        data = json.loads(args.replay_input.read_text())
        result = replay_layout(data["state"], data["board"], data["family_id"], data["config"])
    else:
        root = args.candidate_dir / "content"
        board = json.loads((root / "optimized_story_board.json").read_text())
        sections = board["spatial_content_plan"]["sections"]
        layout_path = root / "final_design_layout.json"
        layout = json.loads(layout_path.read_text()) if layout_path.exists() else []
        text_boxes = {str(item.get("id")): item for item in layout if item.get("type") == "text"}
        samples = []
        for section in sorted(sections, key=lambda item: sum(len(t) for t in item.get("text_content", [])),
                              reverse=True)[:args.sample_limit]:
            box = text_boxes.get(f"{section['section_id']}_text", {})
            samples.append({"text_content": "\n".join(t.strip() for t in section.get("text_content", []) if t.strip()),
                            "width_inches": float(box.get("width", 15.0)),
                            "font_name": box.get("font_family", "Arial"),
                            "font_size": box.get("font_size", 44),
                            "margins": {"left": 0.10, "right": 0.10, "top": 0.05, "bottom": 0.05}})
        result = {"scope": "saved_module_measurements_only", "samples": benchmark_samples(samples)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
