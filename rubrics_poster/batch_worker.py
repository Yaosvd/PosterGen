"""One isolated generation attempt. Only launched by the batch coordinator."""
import os
from pathlib import Path
import signal
import sys
import traceback

from utils.persistence import _atomic_json, read_json, file_hash


def main():
    directory = Path(sys.argv[1]).resolve()
    spec = read_json(directory / 'task.json')
    if file_hash(spec['paper_path']) != spec['paper_sha256']:
        raise ValueError('PDF changed since batch planning')
    for name, expected in spec['logos'].items():
        asset = Path(spec['paper_path']).parent / name
        if (file_hash(asset) if asset.is_file() else None) != expected:
            raise ValueError('Logo changed since batch planning')
    # The coordinator sets visibility before this interpreter starts. dotenv
    # modules may override environment; reassert before creating model resources.
    from src.state.poster_state import create_state
    from src.workflow.exploration_runner import PosterExplorationRunner
    from src.workflow.exploration_store import ExplorationStore
    from src.workflow.run_control import RunControl
    from src.workflow.runtime import activate_project, tee_console_output
    from src.workflow.sample_progress import SampleProgressReporter
    from src.workflow.task_inputs import create_input_state
    from utils.concurrency import WorkStopped, stopped
    os.environ['CUDA_VISIBLE_DEVICES'] = spec['gpu_uuid']
    os.environ['TORCH_DEVICE'] = 'cuda'
    # Surya/Marker settings may have been constructed during imports.
    from marker.settings import settings as marker_settings
    from surya.settings import settings as surya_settings
    marker_settings.TORCH_DEVICE = surya_settings.TORCH_DEVICE = 'cuda'
    activate_project()
    control = RunControl()
    def stop(_sig, _frame):
        control.request_stop()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    receipt = directory / 'run.json'
    run_id = read_json(receipt)['run_id'] if receipt.exists() else None
    try:
        state = create_input_state({'paper_path': spec['paper_path']}, spec['defaults'],
                                   Path.cwd(), create_state)
        with tee_console_output(directory / 'run.log'), SampleProgressReporter(directory / 'run.log') as reporter:
            runner = PosterExplorationRunner(storage=ExplorationStore(spec['storage_root']),
                samples=1, random_seed=spec['seed'], run_id=run_id,
                family_counts=spec['family_counts'], control=control, progress_reporter=reporter,
                run_opened=lambda rid: _atomic_json(receipt, {'run_id': rid}))
            result = runner.run(state)
            status = result['run_state']['status']
            _atomic_json(directory / 'outcome.json', {'status': status, 'run_id': runner.run_id})
            return 0 if status == 'COMPLETED' else 2
    except WorkStopped:
        _atomic_json(directory / 'outcome.json', {'status': 'PAUSED'})
        return 2
    except Exception as exc:
        traceback.print_exc()
        _atomic_json(directory / 'outcome.json', {'status': 'PAUSED' if stopped() else 'FAILED',
            'error_type': type(exc).__name__, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
