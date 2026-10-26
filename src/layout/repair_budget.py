"""Attempt-local durable repair charges, under the sample run's exclusive lease."""

import json
from pathlib import Path

from src.layout.design_content import DESIGN_POLICY_VERSION


JOINT_POLICY = {'version': 1, 'max_edit_rounds': 4, 'max_capacity_rounds': 3,
                'max_quality_rounds': 1, 'max_modules_per_edit': 2}


def validate_joint_policy(config):
    policy = config.get('sample_joint_preparation', JOINT_POLICY)
    if not isinstance(policy, dict) or policy != JOINT_POLICY or any(type(v) is not int for v in policy.values()):
        raise ValueError('Unsupported single-family preparation policy or edit limits')
    return dict(policy)


def sample_ledger(state):
    """One identity-bound ledger across draft edits, verification callbacks and fit."""
    directory = state.get('sample_edit_budget_dir')
    if not directory:
        return None, None
    from utils.persistence import read_json, digest
    path = Path(directory)/'content_edit_budget.json'
    context = state.get('iteration_context') or {}
    policy = validate_joint_policy(state.get('critic_config') or {})
    identity = digest({'version': 'sample_edit_v1', 'policy': policy, 'run': context.get('run_id'),
        'sample': context.get('sample_id'), 'paper': state.get('paper_foundation_digest'),
        'family': (state.get('sample_family') or {}).get('family')})
    if path.exists():
        envelope = read_json(path)
        data = envelope['payload']
        if envelope.get('digest') != digest(data):
            raise ValueError('Sample content-edit ledger digest mismatch')
    else:
        if any(Path(directory).glob('preparation/joint/edits/*/request_00.json')):
            raise ValueError('Sample content-edit ledger missing from existing requests')
        data = {'version': 1, 'identity': identity, 'charges': []}
    if data.get('identity') != identity or data.get('version') != 1:
        raise ValueError('Sample content-edit ledger identity mismatch')
    if any(e.get('phase') not in {'capacity', 'quality'} for e in data.get('charges', [])):
        raise ValueError('Invalid sample content-edit charge')
    charges = data['charges']
    if (len(charges) > 4 or sum(e['phase'] == 'capacity' for e in charges) > 3 or
            sum(e['phase'] == 'quality' for e in charges) > 1 or
            any(e.get('ordinal') != i for i, e in enumerate(charges, 1))):
        raise ValueError('Invalid sample content-edit allowance')
    return path, data


def budget_usage(attempt_dir):
    capacity = quality = 0
    for directory in Path(attempt_dir).parent.iterdir():
        ledger = directory / 'model_repair_budget.json'
        report = directory / 'capacity_repair_report.json'
        if ledger.exists():
            data = json.loads(ledger.read_text())
            if data.get('schema_version') != 1:
                raise ValueError('Unsupported repair budget ledger')
            for entry in data.get('charges', []):
                if entry['phase'] == 'quality':
                    quality += 1
                elif entry['phase'] == 'capacity':
                    capacity += 1
                else:
                    raise ValueError('Invalid repair budget charge')
        elif report.exists():
            data = json.loads(report.read_text())
            rounds = int(data.get('rounds_attempted', 0))
            if rounds < 0:
                raise ValueError('Invalid historical repair accounting')
            if data.get('budget_phase') == 'quality':
                quality += rounds
            else:
                capacity += rounds
    return capacity, quality


def available_rounds(state, phase, settings):
    context = state.get('iteration_context') or {}
    total = max(0, int(settings.get('max_rounds_per_iteration', 4)))
    # Legacy direct callers without a frozen policy retain their old budget.
    reserve = min(total, max(0, int(settings.get('quality_reserved_rounds', 0))))
    path, ledger = sample_ledger(state)
    if path is not None:
        used = sum(e['phase'] == phase for e in ledger['charges'])
        return max(0, min((3 if phase == 'capacity' else 1)-used, 4-len(ledger['charges'])))
    directory = context.get('attempt_diagnostics_dir')
    if directory:
        capacity, quality = budget_usage(directory)
        held = max(0, reserve - quality) if phase == 'capacity' else 0
        return max(0, total - capacity - quality - held)
    remaining = max(0, int(context.get('capacity_repair_remaining', total)))
    held = max(0, reserve - int(context.get('quality_repair_used', 0))) if phase == 'capacity' else 0
    return max(0, remaining - held)


def family_rounds_used(state, family_id):
    path, ledger = sample_ledger(state)
    if path is not None:
        return sum(e.get('family_id') == family_id for e in ledger['charges'])
    context = state.get('iteration_context') or {}
    directory = context.get('attempt_diagnostics_dir')
    if not directory:
        return int((context.get('family_repair_used') or {}).get(family_id, 0))
    used = 0
    for attempt in Path(directory).parent.iterdir():
        ledger, report = attempt / 'model_repair_budget.json', attempt / 'capacity_repair_report.json'
        if ledger.exists():
            used += sum(entry.get('family_id') == family_id for entry in json.loads(ledger.read_text()).get('charges', []))
        elif report.exists():
            data = json.loads(report.read_text())
            if data.get('family_id') == family_id:
                used += int(data.get('rounds_attempted', 0))
    return used


def charge_round(state, phase, settings, *, kind=None):
    """Charge before a blocking call; abandoned calls are never refunded."""
    if phase not in {'capacity', 'quality'}:
        raise ValueError('Unknown content-edit budget phase')
    if available_rounds(state, phase, settings) < 1:
        return False
    context = state.get('iteration_context') or {}
    path, ledger = sample_ledger(state)
    if path is not None:
        from utils.persistence import _atomic_json, digest
        ledger['charges'].append({'phase': phase, 'family_id': context.get('layout_family'),
                                 'kind': kind or 'wording', 'ordinal': len(ledger['charges'])+1})
        _atomic_json(path, {'payload': ledger, 'digest': digest(ledger)})
        return True
    directory = context.get('attempt_diagnostics_dir')
    if directory:
        from utils.persistence import _atomic_json
        path = Path(directory) / 'model_repair_budget.json'
        data = json.loads(path.read_text()) if path.exists() else {
            'schema_version': 1, 'design_policy_version': DESIGN_POLICY_VERSION,
            'charges': [],
        }
        data['charges'].append({'phase': phase, 'family_id': context.get('layout_family'),
                                'attempt_id': context.get('attempt_id'), **({'kind': kind} if kind else {})})
        _atomic_json(path, data)
    else:
        context['capacity_repair_remaining'] = max(
            0, int(context.get('capacity_repair_remaining', settings.get('max_rounds_per_iteration', 4))) - 1)
        if phase == 'quality':
            context['quality_repair_used'] = int(context.get('quality_repair_used', 0)) + 1
        family_id = context.get('layout_family')
        if family_id:
            used = context.setdefault('family_repair_used', {})
            used[family_id] = int(used.get(family_id, 0)) + 1
        state['iteration_context'] = context
    return True


def pressure_progress(report):
    samples = report.get('repair_pressure_candidates') or report.get('progress_pressure_samples') or []
    if not samples:
        return None
    advanced = max(int(s.get('placed_section_count', 0)) for s in samples)
    overages = [float(s['estimated_used_in']) - float(s['zone_limit_in'])
                for s in samples if int(s.get('placed_section_count', 0)) == advanced]
    return advanced, -min(overages)
