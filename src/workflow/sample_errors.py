"""Separate diagnosed sample-output failures from unsafe runtime/history failures."""
from utils.model_requests import SampleRequestFailure


def record_sample_error(state, exc, kind, *, output_error=False):
    if not state.get('joint_preparation'):
        return
    chain, seen = [], set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current)); chain.append(current)
        current = current.__cause__ or current.__context__
    request = any(isinstance(e, SampleRequestFailure) for e in chain)
    truncated = any('truncated' in str(e).lower() or type(e).__name__ == 'LengthFinishReasonError' for e in chain)
    history = any(any(word in str(e).lower() for word in (
        'identity mismatch', 'digest mismatch', 'charged but', 'refusing automatic',
        'response has no durable', 'missing from existing', 'checkpoint')) for e in chain)
    system = any(isinstance(e, (OSError, KeyError, IndexError, AttributeError)) for e in chain)
    allowance_exhausted = str(exc) == 'Shared preparation repair allowance is exhausted'
    fatal = history or system or (request and not truncated) or not (output_error or truncated or allowance_exhausted)
    if fatal:
        state['fatal_generation_error'] = True
    else:
        state['sample_failure'] = {'kind': kind, 'reason': str(exc)}
