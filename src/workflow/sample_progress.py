"""Progress events for independent samples, captured by the console tee."""
import sys
import threading


def format_event(event):
    kind = event.get('type')
    number = event.get('iteration')
    lead = f'Sample {number} | ' if number is not None else ''
    if kind == 'family_frozen':
        return f"{lead}Family frozen before module planning | {event.get('family')}"
    if kind == 'sample':
        return f"{lead}{event.get('attempt')} | {event.get('family')}"
    if kind == 'sample_saved':
        r = event['result']
        return f"{r['sample_id']} saved | {r['status']} | score {r['score']} | unclassified"
    if kind == 'stage_start':
        return f"{lead}{event['stage']} started"
    if kind == 'stage_done':
        return f"{lead}{event['stage']} finished ({event.get('elapsed', 0):.2f}s)"
    if kind == 'layout_detail':
        details = ' | '.join(f'{k} {v}' for k, v in event.items()
                             if k not in {'type', 'run_id', 'iteration', 'label'})
        return f"{lead}{event.get('label', 'layout')} | {details}"
    if kind == 'layout_fit_retry':
        return f"{lead}Fit retry after {event.get('family')} | {event.get('reason')}"
    if kind == 'curation_reused':
        return f"{lead}Reusing this sample's content plan (revision {event.get('revision')}); no Curator request"
    if kind == 'curation_repair':
        return f"{lead}One charged content-plan repair | {event.get('reason')}"
    if kind == 'content_completion_rollback':
        return f'{lead}Restoring same-attempt completion baseline and checking again'
    if kind == 'error':
        return f"{lead}Error in {event.get('stage')}: {event.get('message')}"
    if kind == 'finished':
        return f"Run {event.get('run_id')} | {event.get('status')}"
    return lead + str(event.get('message') or kind)


class SampleProgressReporter:
    def __init__(self, log_path, terminal=None):
        self.terminal = terminal or sys.stdout
        self._stop = threading.Event()
        self._thread = None
        self._stage = 'initializing'

    def __enter__(self):
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._stop.set()
        self._thread.join(timeout=1)

    def _heartbeat(self):
        while not self._stop.wait(60):
            print(f'Working | {self._stage}', file=self.terminal, flush=True)

    def emit(self, event):
        if event.get('type') == 'stage_start':
            self._stage = event['stage']
        print(format_event(event), file=self.terminal, flush=True)

    def write_traceback(self, text):
        print(text, file=self.terminal, flush=True)
