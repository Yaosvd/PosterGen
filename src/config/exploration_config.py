"""Configuration for independent sample runs, separate from evaluation policy."""
from pathlib import Path
import yaml


def load_exploration_config(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[2] / 'config/exploration_config.yaml'
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported exploration configuration')
    if type(data.get('default_samples')) is not int or data['default_samples'] < 1:
        raise ValueError('default_samples must be a positive integer')
    if not isinstance(data.get('storage_root'), str) or not data['storage_root'].strip():
        raise ValueError('storage_root must be a nonempty path')
    return data
