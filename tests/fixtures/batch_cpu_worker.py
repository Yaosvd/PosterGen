"""Subprocess fixture: real runner/storage/rendered files, synthetic science/models."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_exploration_samples import scientific, prepare_sample, render_sample, critic_with_scores
from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.exploration_store import ExplorationStore
from utils.persistence import _atomic_json, read_json

job = Path(sys.argv[1])
spec = read_json(job / 'task.json')
number = int(job.name.split('_')[-1])
if Path(spec['paper_path']).parent.name == 'B' and number == 1:
    os._exit(17)  # Simulate a process crash before any run exists.
state = scientific(job)
state['pdf_path'] = spec['paper_path']
state['poster_name'] = Path(spec['paper_path']).parent.name
receipt = job / 'run.json'
def score(state):
    if number == 2:
        state['critic_report'] = {'evaluation_status': 'failed', 'overall_score': 99}
        return state
    return critic_with_scores([10 if number == 1 else 90])(state)
runner = PosterExplorationRunner(storage=ExplorationStore(spec['storage_root']),
    paper_nodes=[], preparation_nodes=[prepare_sample], design_nodes=[render_sample], critic=score,
    samples=1, random_seed=spec['seed'], family_counts=spec['family_counts'],
    run_id=read_json(receipt)['run_id'] if receipt.exists() else None,
    run_opened=lambda rid: _atomic_json(receipt, {'run_id': rid}))
result = runner.run(state, paper_ready=True)
_atomic_json(job / 'outcome.json', {'status': result['run_state']['status']})
