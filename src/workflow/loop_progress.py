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
        weights = event.get("mode_weights") or {}
        policy = (
            " | policy explore {:.0%}, improve {:.0%}; validation disabled".format(
                float(weights.get("explore", 0.0)),
                float(weights.get("improve", 0.0)),
            ) if event.get("mode") == "mixed" and weights else ""
        )
        return "Campaign {} {} | Batch {} {} ({}) {}/{} committed{}".format(
            event["campaign_id"],
            "resumed" if event["resumed"] else "created",
            event["batch_id"],
            "resumed" if event.get("batch_resumed") else "created",
            event["mode"], event["completed"], event["target"], policy,
        )
    if kind == "validation_snapshot":
        blocked = event.get("blocked_templates") or []
        blocked_text = ", ".join(
            "{} ({})".format(item.get("template_id"), item.get("reason"))
            for item in blocked[:3]
        )
        suffix = f" | blocked {blocked_text}" if blocked_text else ""
        if len(blocked) > 3:
            suffix += f" and {len(blocked) - 3} more"
        return (
            f"Validation snapshot: {event.get('eligible_count', 0)} eligible"
            f" | frozen for this Batch{suffix}"
        )
    if kind == "foundation":
        return f"Scientific foundation: {event['action']}"
    if kind == "iteration":
        validation = ""
        if event.get("validation_target"):
            validation = " | {} attempt {}/{}".format(
                event["validation_target"].replace("_", "-"),
                event.get("validation_attempt", 1),
                event.get("validation_max_attempts", 1),
            )
        return "Batch {}/{} | I{} attempt {} | {} / {} | family {} | lineage {} | templates {}{}".format(
            event["batch_ordinal"], event["batch_target"], iteration,
            event["attempt_number"], event["mode"], event["strategy"],
            event["family"], event["lineage"],
            ",".join(event["template_ids"]) or "none", validation,
        )
    if kind == "improve_base_loaded":
        feedback = event.get("feedback_candidate_id")
        feedback_text = (
            f" | latest feedback {feedback}" if feedback else ""
        )
        return (
            f"{lead}Improve base loaded | {event.get('snapshot_kind')} | "
            f"candidate {event.get('candidate_id')} | score "
            f"{event.get('score')}{feedback_text}"
        )
    if kind == "lineage_parent_blocked":
        return (
            f"Improve parent skipped | lineage {event.get('lineage')} | "
            f"{event.get('reason')} | historical poster and feedback retained"
        )
    if kind == "promising_candidate":
        if event.get("became_best"):
            return (
                f"{lead}Promising base updated | lineage "
                f"{event.get('lineage')} | parent "
                f"{event.get('parent_score')} -> candidate "
                f"{event.get('score')} | poster rejected | next Improve "
                "may use this base"
            )
        if not event.get("eligible"):
            reasons = ",".join(event.get("reasons") or []) or "not eligible"
            return (
                f"{lead}Rejected candidate is not eligible as a promising "
                f"base | {reasons}"
            )
        if event.get("local_improvement"):
            return (
                f"{lead}Local improvement recorded | parent "
                f"{event.get('parent_score')} -> candidate "
                f"{event.get('score')} | best promising remains "
                f"{event.get('best_score')}"
            )
        return (
            f"{lead}Promising base retained | candidate "
            f"{event.get('best_candidate_id')} | score "
            f"{event.get('best_score')}"
        )
    if kind == "layout_fit_retry":
        excluded = ",".join(event.get("excluded") or []) or "none"
        fallback = (
            " | next attempt uses safe parent fallback"
            if event.get("safe_parent_fallback") and not event.get("exhausted")
            else ""
        )
        stage = str(event.get("failure_stage") or "layout_fit").replace("_", "-")
        diagnosis = ""
        if event.get("reason_code"):
            diagnosis = (
                f" | {event['reason_code']} | "
                f"{event.get('fit_feasible_count', 0)}/"
                f"{event.get('fit_trial_count', 0)} variants"
                + (
                    f" | frequent gate {event['dominant_blocker']}"
                    if event.get("dominant_blocker") else ""
                )
            )
            diagnosis += (
                f" | near-miss rechecks {event.get('near_miss_rechecks', 0)}"
            )
        if event.get("repair_status"):
            diagnosis += f" | repair {event['repair_status']}"
            if event.get("repair_skip_reason"):
                diagnosis += f" ({event['repair_skip_reason']})"
        return (
            f"{lead}Layout fit rejected before rendering | family "
            f"{event.get('family')} | stage {stage} | retry {event.get('retry')} | "
            f"excluded {excluded} | Batch budget not consumed"
            f"{diagnosis}{fallback}"
        )
    if kind == "capacity_repair":
        return (
            f"{lead}Capacity repair | family {event.get('family')} | "
            f"{event.get('status')} | {event.get('rounds')} round(s) | "
            f"iteration budget {event.get('used')}/{event.get('limit')}"
        )
    if kind == "lineage_recovery_blocked":
        return (
            f"{lead}Improve Lineage {event.get('lineage')} isolated for "
            f"this Batch | family {event.get('family')} | stage "
            f"{event.get('failure_stage')} | same iteration will be "
            "rescheduled | Batch budget not consumed"
        )
    if kind == "validation_preflight_failed":
        return (
            f"{lead}Validation topology failed before rendering | attempt "
            f"{event.get('attempt', 1)}/{event.get('max_attempts', 3)} | "
            "committed as an unscored validation failure | "
            "no poster artifact produced"
        )
    if kind == "no_change_safe_fallback":
        return (
            f"{lead}Improve safe-parent fallback produced no new design | "
            f"parent {event.get('parent_candidate')} | Batch budget consumed | "
            "no poster archive, template, or global design event"
        )
    if kind == "layout_archetype":
        return (
            f"{lead}Layout archetype {event.get('archetype_id')} | "
            f"family {event.get('family')} | {event.get('status')} | "
            f"{event.get('accepted_posters', 0)} accepted posters across "
            f"{event.get('distinct_papers', 0)} papers"
        )
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
        evidence = event.get("validation_evidence") or {}
        rejected = event.get("rejected_artifact") or {}
        if template.get("reason") == "validation_updates_existing_template":
            evidence_result = (
                f"saved at {evidence.get('archive_dir')}"
                if evidence.get("saved")
                else (
                    "failed; rejected poster saved at "
                    f"{rejected.get('archive_dir')}"
                    if rejected.get("saved")
                    else "not saved (no rendered poster artifact)"
                )
            )
            return (
                f"{lead}Committed | validation poster evidence "
                f"{evidence_result} | source template "
                f"{template.get('template_id')} updated | no new template created"
                + (
                    f" | validation {event['validation']}"
                    if event.get("validation") else ""
                )
            )
        template_result = (
            f"saved {template.get('template_id')}"
            if template.get("registered")
            else f"not saved ({template.get('reason', 'ineligible')})"
        )
        return (f"{lead}Committed | poster "
                f"{'archived at ' + event['archive'] if event.get('archive') else 'not archived'} | "
                + (
                    f"rejected diagnostic saved at {rejected.get('archive_dir')} | "
                    if rejected.get("saved") else ""
                )
                + f"template {template_result}"
                + (f" | design {template.get('design_score') if template.get('design_score') is not None else 'unscored'}"
                   f" L{template.get('level', 0)} | reference seat "
                   f"{'yes' if template.get('retrieval_enabled') else 'no'}"
                   f" ({template.get('retrieval_reason', 'unknown')})"
                   if template.get('registered') and 'retrieval_enabled' in template else "")
                + (f" | preview {template['preview_png']}" if template.get("preview_png") else "")
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
                Text(f"Accepted {data.get('accepted', 0)} | Rejected {data.get('rejected', 0)} | Templates {data.get('templates', 0)} | Validation evidence {data.get('validation_evidence_count', 0)} | Best {data.get('best_score', '-')}"),
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
                "attempt_number", "accepted", "rejected", "templates", "best_score", "validation_evidence_count",
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
