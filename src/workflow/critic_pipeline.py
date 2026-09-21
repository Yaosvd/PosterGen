"""CLI entry point for the user-controlled continuous Critic loop."""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

from src.state.poster_state import create_state
from src.workflow.optimization_loop import LoopControl, PosterOptimizationLoop
from src.workflow.pipeline import save_timing_log
from utils.src.logging_utils import log_agent_info, log_agent_success


def _default_model(kind: str) -> str:
    prefix = "LOCAL_TEXT" if kind == "text" else "LOCAL_VISION"
    return f"local-{kind}" if os.getenv(f"{prefix}_BASE_URL") else "gpt-4o-2024-08-06"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PosterGen continuous Planner-Coder-Critic optimization loop"
    )
    parser.add_argument("--paper_path", required=True)
    parser.add_argument("--text_model", default=_default_model("text"))
    parser.add_argument("--vision_model", default=_default_model("vision"))
    parser.add_argument("--poster_width", type=float, default=54)
    parser.add_argument("--poster_height", type=float, default=36)
    parser.add_argument("--url", default="")
    parser.add_argument("--logo", default=None)
    parser.add_argument("--aff_logo", default=None)
    parser.add_argument("--random_seed", type=int, default=None)
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help=(
            "Committed Critic iterations in this resumable Batch "
            "(default: 100)"
        ),
    )
    parser.add_argument(
        "--resume",
        choices=("latest", "required", "new"),
        default="latest",
        help=(
            "latest resumes the newest compatible campaign; required fails "
            "when none exists; new starts an independent campaign"
        ),
    )
    parser.add_argument(
        "--campaign_id",
        default=None,
        help="Resume this exact compatible campaign (overrides latest search)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pdf_path = Path(args.paper_path).resolve()
    if not pdf_path.is_file():
        print("❌ PDF not found")
        return 1
    if args.iterations < 1:
        print("❌ --iterations must be positive")
        return 1
    ratio = args.poster_width / args.poster_height
    if ratio < 1.4 or ratio > 2.0:
        print(f"❌ Poster ratio is out of range: {ratio}. Use 1.4 to 2.0.")
        return 1
    paper_dir = pdf_path.parent
    logo = Path(args.logo).resolve() if args.logo else paper_dir / "logo.png"
    aff_logo = Path(args.aff_logo).resolve() if args.aff_logo else paper_dir / "aff.png"
    final_width = 54.0
    final_height = final_width / ratio
    state = create_state(
        str(pdf_path),
        args.text_model,
        args.vision_model,
        final_width,
        final_height,
        args.url,
        str(logo) if logo.is_file() else "",
        str(aff_logo) if aff_logo.is_file() else "",
    )
    control = LoopControl()
    interrupt_count = 0

    def handle_interrupt(signum, frame):
        nonlocal interrupt_count
        interrupt_count += 1
        if interrupt_count == 1:
            print("\n🛑 Stop requested; finishing the current evaluation and checkpoint.")
            control.request_stop()
        else:
            print("\n⚠️ Force-stop requested.")
            control.request_stop(force=True)

    previous_handler = signal.signal(signal.SIGINT, handle_interrupt)
    try:
        print("🔁 PosterGen resumable Critic optimization Batch")
        print(f"   Target committed iterations: {args.iterations}")
        print("   Quality never terminates a Batch early.")
        print("   Press Ctrl+C to stop after the current iteration.")
        state["timing_metrics"].pipeline_start = time.time()
        final_state = PosterOptimizationLoop(
            control=control,
            random_seed=args.random_seed,
            resume_mode=args.resume,
            campaign_id=args.campaign_id,
            batch_iterations=args.iterations,
        ).run(state)
        final_state["timing_metrics"].pipeline_end = time.time()
        save_timing_log(final_state)
        loop_state = final_state.get("loop_state") or {}
        print(
            f"   Campaign: {loop_state.get('campaign_id', 'unknown')} | "
            f"last completed iteration: "
            f"{loop_state.get('last_completed_iteration', 0)} | "
            f"Batch: {(loop_state.get('batch') or {}).get('batch_id', 'unknown')} "
            f"{(loop_state.get('batch') or {}).get('completed_iterations', 0)}/"
            f"{(loop_state.get('batch') or {}).get('target_iterations', args.iterations)}"
        )

        best = (final_state.get("loop_state") or {}).get("best_candidate")
        if best:
            log_agent_success(
                "critic_pipeline",
                f"best accepted candidate: {best['candidate_id']} ({best['score']})",
            )
        else:
            log_agent_info("critic_pipeline", "loop stopped without an accepted candidate")
        return 0
    finally:
        signal.signal(signal.SIGINT, previous_handler)


if __name__ == "__main__":
    sys.exit(main())
