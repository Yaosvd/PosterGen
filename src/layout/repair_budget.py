"""Attempt-local durable repair charges, under the sample run's exclusive lease."""

import json
from pathlib import Path

from src.layout.design_content import DESIGN_POLICY_VERSION


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
    directory = context.get('attempt_diagnostics_dir')
    if directory:
        capacity, quality = budget_usage(directory)
        held = max(0, reserve - quality) if phase == 'capacity' else 0
        return max(0, total - capacity - quality - held)
    remaining = max(0, int(context.get('capacity_repair_remaining', total)))
    held = max(0, reserve - int(context.get('quality_repair_used', 0))) if phase == 'capacity' else 0
    return max(0, remaining - held)


def family_rounds_used(state, family_id):
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


def charge_round(state, phase, settings):
    """Charge before a blocking call; abandoned calls are never refunded."""
    if available_rounds(state, phase, settings) < 1:
        return False
    context = state.get('iteration_context') or {}
    directory = context.get('attempt_diagnostics_dir')
    if directory:
        from utils.persistence import _atomic_json
        path = Path(directory) / 'model_repair_budget.json'
        data = json.loads(path.read_text()) if path.exists() else {
            'schema_version': 1, 'design_policy_version': DESIGN_POLICY_VERSION,
            'charges': [],
        }
        data['charges'].append({'phase': phase, 'family_id': context.get('layout_family'),
                                'attempt_id': context.get('attempt_id')})
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
