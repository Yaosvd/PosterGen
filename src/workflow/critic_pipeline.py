"""CLI entry point for the user-controlled continuous Critic loop."""

import argparse
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from src.config.critic_config import load_critic_config
from src.state.poster_state import create_state
from src.workflow.campaign import CampaignManager
from src.workflow.optimization_loop import LoopControl, PosterOptimizationLoop
from src.workflow.pipeline import save_timing_log, tee_console_output
from src.workflow.loop_progress import LoopProgressReporter
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
            "Committed iterations in this resumable Batch "
            "(default: 100)"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("mixed", "explore", "improve", "validate"),
        default=None,
        help="Batch scheduling mode; omitted preserves a resumed Batch mode",
    )
    parser.add_argument(
        "--target-lineage-id",
        default=None,
        help="Restrict a pure improve Batch to this Lineage",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Resume this exact paused or failed Batch within the selected Campaign",
    )
    parser.add_argument(
        "--new-batch",
        action="store_true",
        help="Create the next permanent Batch ID even when paused Batches exist",
    )
    parser.add_argument(
        "--list-batches",
        action="store_true",
        help="List persisted Batches for the selected Campaign and exit",
    )
    parser.add_argument(
        "--archive-batch",
        default=None,
        help="Archive one paused or failed Batch and exit",
    )
    parser.add_argument(
        "--unarchive-batch",
        default=None,
        help="Return one archived Batch to PAUSED and exit",
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
    if args.target_lineage_id and args.mode != "improve":
        print("❌ --target-lineage-id requires --mode improve")
        return 1
    if args.batch_id and args.new_batch:
        print("❌ --batch-id and --new-batch are mutually exclusive")
        return 1
    if args.batch_id and args.resume == "new":
        print("❌ --batch-id requires an existing Campaign")
        return 1
    admin_actions = sum(bool(value) for value in (
        args.list_batches, args.archive_batch, args.unarchive_batch,
    ))
    if admin_actions > 1:
        print("❌ Select only one Batch administration action")
        return 1
    if admin_actions and args.resume == "new":
        print("❌ Batch administration requires an existing Campaign")
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
    if admin_actions:
        config = load_critic_config()
        manager = CampaignManager(
            Path(config.get("storage", {}).get("root", "storage/critic_loop")),
            config,
        )
        try:
            handle = manager.open_campaign(
                state,
                resume_mode="required",
                campaign_id=args.campaign_id,
            )
            with manager.lease(handle):
                if args.archive_batch:
                    manager.archive_batch(handle, args.archive_batch)
                elif args.unarchive_batch:
                    manager.unarchive_batch(handle, args.unarchive_batch)
                batches = manager.list_batches(handle)
            print(f"Campaign {handle.campaign_id} Batches:")
            for batch in batches:
                print(
                    "  {batch_id} | {mode} | {completed}/{target} | {status}".format(
                        batch_id=batch.get("batch_id"),
                        mode=(batch.get("schedule_policy") or {}).get("mode", "unknown"),
                        completed=batch.get("completed_iterations", 0),
                        target=batch.get("target_iterations", 0),
                        status=batch.get("status", "unknown"),
                    )
                )
            return 0
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"❌ Batch administration failed: {exc}")
            return 1

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
        log_path = Path(state["output_dir"]) / "run.log"
        with tee_console_output(log_path):
            with LoopProgressReporter(log_path) as progress:
                try:
                    print("PosterGen resumable Critic optimization Batch")
                    print(f"Target committed iterations: {args.iterations}")
                    print(f"Requested Batch mode: {args.mode or 'resume selected / mixed for new'}")
                    print(f"Requested Batch: {args.batch_id or ('new' if args.new_batch else 'automatic')}")
                    print("Quality never terminates a Batch early. Press Ctrl+C to pause it safely.")
                    state["timing_metrics"].pipeline_start = time.time()
                    final_state = PosterOptimizationLoop(
                        control=control,
                        random_seed=args.random_seed,
                        resume_mode=args.resume,
                        campaign_id=args.campaign_id,
                        batch_iterations=args.iterations,
                        batch_mode=args.mode,
                        target_lineage_id=args.target_lineage_id,
                        batch_id=args.batch_id,
                        new_batch=args.new_batch,
                        progress_reporter=progress,
                    ).run(state)
                    final_state["timing_metrics"].pipeline_end = time.time()
                    save_timing_log(final_state)
                    loop_state = final_state.get("loop_state") or {}
                    batch = loop_state.get("batch") or {}
                    print(
                        f"Campaign: {loop_state.get('campaign_id', 'unknown')} | "
                        f"last completed iteration: {loop_state.get('last_completed_iteration', 0)} | "
                        f"Batch: {batch.get('batch_id', 'unknown')} "
                        f"{batch.get('completed_iterations', 0)}/{batch.get('target_iterations', args.iterations)}"
                    )
                    best = loop_state.get("best_candidate")
                    if best:
                        log_agent_success(
                            "critic_pipeline",
                            f"best accepted candidate: {best['candidate_id']} ({best['score']})",
                        )
                    else:
                        log_agent_info("critic_pipeline", "loop stopped without an accepted candidate")
                    return 1 if loop_state.get("status") in {"FAILED_REQUIRES_USER", "UNAVAILABLE"} else 0
                except Exception as exc:
                    progress.emit({
                        "type": "error", "stage": "startup_or_shutdown",
                        "error_type": type(exc).__name__, "message": str(exc),
                    })
                    progress.write_traceback(traceback.format_exc())
                    return 1
    finally:
        signal.signal(signal.SIGINT, previous_handler)


if __name__ == "__main__":
    sys.exit(main())
