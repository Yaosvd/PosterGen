"""Generate independent Explore samples; no historical Campaign is restored."""
import argparse
import os
from pathlib import Path
import signal
import sys
import time
import traceback

from src.state.poster_state import create_state
from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.run_control import RunControl
from src.workflow.sample_progress import SampleProgressReporter
from src.workflow.pipeline import save_timing_log, tee_console_output


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper_path', required=True)
    parser.add_argument('--text_model', default='local-text' if os.getenv('LOCAL_TEXT_BASE_URL') else 'gpt-4o-2024-08-06')
    parser.add_argument('--vision_model', default='local-vision' if os.getenv('LOCAL_VISION_BASE_URL') else 'gpt-4o-2024-08-06')
    parser.add_argument('--poster_width', type=float, default=54)
    parser.add_argument('--poster_height', type=float, default=36)
    parser.add_argument('--logo')
    parser.add_argument('--aff_logo')
    parser.add_argument('--url', default='')
    parser.add_argument('--samples', type=int, default=None)
    parser.add_argument('--random_seed', type=int, default=None)
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--paper-cache-run-id', default=None,
                        help='Reuse only compatible hash-verified paper/evidence/assets from this sample run')
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    pdf = Path(args.paper_path).resolve()
    if not pdf.is_file():
        parser.error('PDF not found')
    if args.samples is not None and args.samples < 1:
        parser.error('--samples must be positive')
    if args.poster_height <= 0 or not 1.4 <= args.poster_width / args.poster_height <= 2:
        parser.error('Poster aspect ratio must be between 1.4 and 2.0')
    ratio = args.poster_width / args.poster_height
    logo = Path(args.logo).resolve() if args.logo else pdf.parent / 'logo.png'
    affiliation = Path(args.aff_logo).resolve() if args.aff_logo else pdf.parent / 'aff.png'
    state = create_state(str(pdf), args.text_model, args.vision_model, 54, 54 / ratio, args.url,
                         str(logo) if logo.is_file() else '', str(affiliation) if affiliation.is_file() else '')
    control = RunControl()
    count = 0

    def interrupt(_signum, _frame):
        nonlocal count
        count += 1
        control.request_stop(force=count > 1)
        print('Stop requested; preserving results at the next safe boundary.')

    old = signal.signal(signal.SIGINT, interrupt)
    log = Path(state['output_dir']) / 'run.log'
    try:
        with tee_console_output(log), SampleProgressReporter(log) as progress:
            try:
                state['timing_metrics'].pipeline_start = time.time()
                result = PosterExplorationRunner(control=control, samples=args.samples,
                    random_seed=args.random_seed, run_id=args.run_id, progress_reporter=progress,
                    paper_cache_run_id=args.paper_cache_run_id).run(state)
                result['timing_metrics'].pipeline_end = time.time()
                save_timing_log(result)
                run = result['run_state']
                print(f"Run {run['run_id']}: {run['finalized_samples']}/{run['planned_samples']} tasks, "
                      f"{run['rendered_samples']} posters saved, {run['scored_samples']} scored, "
                      f"{run['failed_samples']} failed | {run['status']}")
                return 1 if run['status'] == 'FAILED' else 0
            except Exception as exc:
                progress.emit({'type': 'error', 'stage': 'run', 'message': str(exc)})
                progress.write_traceback(traceback.format_exc())
                return 1
    finally:
        signal.signal(signal.SIGINT, old)


if __name__ == '__main__':
    sys.exit(main())
