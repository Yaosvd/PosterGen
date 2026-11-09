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
from src.workflow.task_inputs import create_input_state, load_task_file
from src.workflow.sample_progress import SampleProgressReporter
from src.workflow.runtime import save_timing_log, tee_console_output, activate_project


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--paper_path')
    inputs.add_argument('--task-file', help='JSON list of full PDF/Logo/parameter tasks; relative paths use its directory')
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
    parser.add_argument('--verbose', action='store_true', help='Show detailed agent/layout logs and source locations; full details always remain in run.log')
    parser.add_argument('--paper-cache-run-id', default=None,
                        help='Explicitly reuse compatible paper material for each task; never sample prose or designs')
    parser.add_argument('--paper-cache-sample-id', default=None,
                        help='Select the source task when the paper-cache run contains multiple posters')
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    caller_dir = Path.cwd()
    activate_project()
    if args.samples is not None and args.samples < 1:
        parser.error('--samples must be positive')
    if args.paper_cache_sample_id and not (args.paper_cache_run_id or args.run_id):
        parser.error('--paper-cache-sample-id requires --paper-cache-run-id')
    defaults = {key: getattr(args, key) for key in
                ('text_model', 'vision_model', 'poster_width', 'poster_height', 'url', 'logo', 'aff_logo')}
    for key in ('logo', 'aff_logo'):
        if defaults[key] is not None:
            defaults[key] = str((caller_dir / defaults[key]).resolve())
    input_states = None
    try:
        if args.task_file:
            if args.samples is not None:
                parser.error('--task-file defines one poster per task; do not combine with --samples')
            input_states = load_task_file(caller_dir / args.task_file, defaults, create_state)
            state = input_states[0]
        else:
            state = create_input_state({'paper_path': args.paper_path}, defaults, caller_dir, create_state)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    control = RunControl()
    count = 0
    progress = None

    def interrupt(_signum, _frame):
        nonlocal count
        count += 1
        control.request_stop(force=count > 1)
        if progress is not None:
            progress.emit({'type': 'stop_requested', 'message': 'Stop requested; preserving results at the next safe boundary.'})

    old = signal.signal(signal.SIGINT, interrupt)
    log = Path(state['output_dir']) / 'run.log'
    try:
        with tee_console_output(log), SampleProgressReporter(log, verbose=args.verbose) as progress:
            try:
                state['timing_metrics'].pipeline_start = time.time()
                result = PosterExplorationRunner(control=control, samples=args.samples,
                    random_seed=args.random_seed, run_id=args.run_id, progress_reporter=progress,
                    paper_cache_run_id=args.paper_cache_run_id,
                    paper_cache_sample_id=args.paper_cache_sample_id, input_states=input_states).run(state)
                result['timing_metrics'].pipeline_end = time.time()
                save_timing_log(result)
                run = result['run_state']
                progress.emit({'type': 'run_summary', 'run': run, 'output_dir': result['output_dir']})
                return 1 if run['status'] == 'FAILED' else 0
            except Exception as exc:
                progress.emit({'type': 'error', 'stage': 'run', 'message': str(exc)})
                progress.write_traceback(traceback.format_exc())
                return 1
    finally:
        signal.signal(signal.SIGINT, old)


if __name__ == '__main__':
    sys.exit(main())
