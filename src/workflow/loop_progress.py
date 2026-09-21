"""Terminal progress display for a resumable optimization Batch."""

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from utils.src import logging_utils


def format_event(event):
    kind = event.get("type")
    iteration = event.get("iteration")
    lead = f"I{iteration} " if iteration is not None else ""
    if kind == "session":
        return (f"Campaign {event['campaign_id']} {'resumed' if event['resumed'] else 'created'} | "
                f"Batch {event['batch_id']} {'resumed' if event.get('batch_resumed') else 'created'} ({event['mode']}) "
                f"{event['completed']}/{event['target']} committed")
    if kind == "foundation":
        return f"Scientific foundation: {event['action']}"
    if kind == "iteration":
        return (f"Batch {event['batch_ordinal']}/{event['batch_target']} | I{iteration} "
                f"attempt {event['attempt_number']} | {event['mode']} / {event['strategy']} | "
                f"family {event['family']} | lineage {event['lineage']} | "
                f"templates {','.join(event['template_ids']) or 'none'}")
    if kind == "stage_start":
        return f"{lead}Stage {event['stage_index']}/{event['stage_total']}: {event['stage']} started"
    if kind == "stage_done":
        return f"{lead}Stage {event['stage']} finished in {event['elapsed']:.1f}s"
    if kind == "critic":
        issues = ",".join(event.get("issues", [])[:3])
        return (f"{lead}Critic: {event['decision']} score {event['score']} | "
                f"poster {'accepted' if event['accepted'] else 'rejected'} | "
                f"template {'eligible' if event['template_eligible'] else 'ineligible'}"
                + (f" | issues {issues}" if issues else ""))
    if kind == "committed":
        template = event.get("template") or {}
        template_result = (f"saved {template.get('template_id')}" if template.get("registered")
                           else f"not saved ({template.get('reason', 'ineligible')})")
        return (f"{lead}Committed | poster "
                f"{'archived at ' + event['archive'] if event.get('archive') else 'not archived'} | "
                f"template {template_result}"
                + (f" | validation {event['validation']}" if event.get("validation") else "")
                + (" | new best" if event.get("best") else ""))
    if kind == "error":
        return f"{lead}ERROR at {event.get('stage', 'unknown')} ({event.get('error_type', 'Error')}): {event.get('message', '')}"
    if kind == "finished":
        return (f"Batch {event['status']} ({event['reason']}) | "
                f"{event['completed']}/{event['target']} committed | "
                f"accepted {event['accepted']}, rejected {event['rejected']}, templates {event['templates']}")
    if kind == "heartbeat":
        return f"{lead}Working on {event['stage']} for {event['elapsed']:.0f}s"
    return str(event.get("message", kind))


class LoopProgressReporter:
    """Use a live Rich panel on TTY and plain events when redirected."""

    def __init__(self, log_path, terminal=None):
        self.log_path = Path(log_path)
        self.terminal = terminal or getattr(sys.stderr, "console_stream", sys.stderr)
        self.is_tty = bool(self.terminal.isatty())
        self.console = Console(file=self.terminal)
        self.live = None
        self._old_console = None
        self._old_sink = None
        self._stop = threading.Event()
        self._worker = None
        self._lock = threading.RLock()
        self._last = {}
        self._stage = ""
        self._stage_started = None
        self._heartbeat_at = time.monotonic()

    def __enter__(self):
        if self.is_tty:
            self._old_console = logging_utils.console
            self._old_sink = logging_utils.progress_log_sink
            logging_utils.console = self.console
            logging_utils.progress_log_sink = self._write_log
            self.live = Live(get_renderable=self._dashboard, console=self.console,
                             refresh_per_second=1, redirect_stdout=False,
                             redirect_stderr=False, transient=False)
            self.live.start()
        else:
            self._worker = threading.Thread(target=self._heartbeat, daemon=True)
            self._worker.start()
        return self

    def __exit__(self, *_exc):
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=2)
        if self.live:
            self.live.stop()
        if self._old_console is not None:
            logging_utils.console = self._old_console
            logging_utils.progress_log_sink = self._old_sink

    def _write_log(self, line):
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(line.rstrip() + "\n")

    def write_traceback(self, traceback_text):
        self._write_log("TRACEBACK\n" + traceback_text.rstrip())

    def _dashboard(self):
        with self._lock:
            data = dict(self._last)
            elapsed = time.monotonic() - self._stage_started if self._stage_started else 0
            completed = int(data.get("completed", 0))
            target = max(1, int(data.get("target", 1)))
            filled = min(24, int(24 * completed / target))
            body = Group(
                Text(f"Campaign {data.get('campaign_id', 'starting')} | Batch {data.get('batch_id', 'starting')} ({data.get('mode', 'mixed')})"),
                Text(f"{'━' * filled}{'─' * (24 - filled)} {completed}/{target} committed"),
                Text(f"Global iteration {data.get('iteration', '-')} | attempt {data.get('attempt_number', '-')} | stage {self._stage or 'idle'} {elapsed:.0f}s"),
                Text(f"Accepted {data.get('accepted', 0)} | Rejected {data.get('rejected', 0)} | Templates {data.get('templates', 0)} | Best {data.get('best_score', '-')}"),
            )
            return Panel(body, title="PosterGen optimization", border_style="cyan")

    def _heartbeat(self):
        while not self._stop.wait(1):
            with self._lock:
                elapsed = time.monotonic() - self._stage_started if self._stage_started else 0
                if not self._stage or elapsed < 60 or time.monotonic() - self._heartbeat_at < 60:
                    continue
                self._heartbeat_at = time.monotonic()
                event = {"type": "heartbeat", "iteration": self._last.get("iteration"),
                         "stage": self._stage, "elapsed": elapsed}
            self.emit(event)

    def emit(self, event):
        with self._lock:
            self._last.update({key: value for key, value in event.items() if key in {
                "campaign_id", "batch_id", "mode", "completed", "target", "iteration",
                "attempt_number", "accepted", "rejected", "templates", "best_score",
            }})
            if event.get("type") == "stage_start":
                self._stage = str(event["stage"])
                self._stage_started = time.monotonic()
                self._heartbeat_at = self._stage_started
            elif event.get("type") in {"stage_done", "error", "committed", "finished"}:
                self._stage = ""
                self._stage_started = None
            line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {format_event(event)}"
            if self.is_tty:
                self._write_log(line)
                if self.live:
                    self.live.console.print(line)
            else:
                print(line, flush=True)
