"""Crash-safe campaign persistence for continuous poster optimization.

A campaign spans process launches.  A session is one process launch, while an
iteration is committed only after rendering, Critic evaluation, archive/reject
bookkeeping, and a durable state snapshot have all completed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


CAMPAIGN_SCHEMA_VERSION = 3
FOUNDATION_SCHEMA_VERSION = 2
LAYOUT_ENGINE_SCHEMA_VERSION = 1
BATCH_SCHEMA_VERSION = 3
SCHEDULE_POLICY_VERSION = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "tolist"):
        return _json_ready(value.tolist())
    return str(value)


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(_json_ready(payload), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fallback_hash(state: Dict[str, Any]) -> str:
    raw = state.get("raw_text") or state.get("poster_name") or "unknown-paper"
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned[:48] or "poster"


@dataclass
class CampaignHandle:
    campaign_id: str
    path: Path
    manifest: Dict[str, Any]
    resumed: bool
    last_completed_iteration: int


@dataclass
class IterationAttempt:
    iteration: int
    attempt_number: int
    attempt_id: str
    path: Path


class _CampaignLease:
    _thread_lock = threading.RLock()

    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream = None

    def __enter__(self):
        self._thread_lock.acquire()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+", encoding="utf-8")
        if fcntl is not None:
            try:
                fcntl.flock(
                    self.stream.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            except BlockingIOError as exc:
                self.stream.close()
                self.stream = None
                self._thread_lock.release()
                raise RuntimeError(
                    "This optimization campaign is already running"
                ) from exc
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.stream is not None:
            if fcntl is not None:
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
        self._thread_lock.release()


class CampaignManager:
    """Create, resume, checkpoint, and atomically commit loop campaigns."""

    FOUNDATION_FIELDS = (
        "raw_text",
        "page_records",
        "section_chunks",
        "images",
        "tables",
        "classified_visuals",
        "evidence_bank",
        "academic_entities",
        "narrative_plan",
        "poster_claims",
        "verified_claims",
        "verification_report",
        "verification_passed",
        "narrative_content",
        "structured_sections",
    )

    SNAPSHOT_FIELDS = (
        "story_board",
        "optimized_story_board",
        "initial_layout_data",
        "column_analysis",
        "balancer_decisions",
        "design_layout",
        "final_column_analysis",
        "optimized_column_assignment",
        "color_scheme",
        "color_provenance",
        "style_overrides",
        "section_title_design",
        "keywords",
        "styled_layout",
        "revision_plan",
        "content_revision",
        "verified_content_bank",
        "supplemental_evidence_bank",
        "content_selection",
        "section_fit_analysis",
        "layout_overrides",
        "critic_report",
        "critic_history",
        "layout_spec",
        "layout_family_analysis",
    )

    def __init__(self, root: Path, config: Dict[str, Any]) -> None:
        self.root = Path(root)
        self.config = config
        self.campaigns_root = self.root / "campaigns"
        self.campaigns_root.mkdir(parents=True, exist_ok=True)

    def compatibility_identity(self, state: Dict[str, Any]) -> Dict[str, Any]:
        pdf = Path(str(state.get("pdf_path") or ""))
        paper_hash = _sha256_file(pdf) if pdf.is_file() else _fallback_hash(state)

        asset_hashes: Dict[str, str] = {}
        for field in ("logo_path", "aff_logo_path"):
            path = Path(str(state.get(field) or ""))
            if path.is_file():
                asset_hashes[field] = _sha256_file(path)

        identity = {
            "paper_sha256": paper_hash,
            "poster_width": round(float(state.get("poster_width", 0.0)), 4),
            "poster_height": round(float(state.get("poster_height", 0.0)), 4),
            "foundation_schema_version": FOUNDATION_SCHEMA_VERSION,
            "layout_engine_schema_version": LAYOUT_ENGINE_SCHEMA_VERSION,
            "asset_sha256": asset_hashes,
        }
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        identity["compatibility_fingerprint"] = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()
        return identity

    def open_campaign(
        self,
        state: Dict[str, Any],
        *,
        resume_mode: str = "latest",
        campaign_id: Optional[str] = None,
    ) -> CampaignHandle:
        if resume_mode not in {"latest", "required", "new"}:
            raise ValueError("resume_mode must be latest, required, or new")

        identity = self.compatibility_identity(state)
        selected: Optional[Path] = None
        selected_manifest: Optional[Dict[str, Any]] = None

        if campaign_id:
            if _safe_name(campaign_id) != campaign_id:
                raise ValueError("invalid campaign_id")
            candidate = self.campaigns_root / campaign_id
            manifest = _read_json(candidate / "manifest.json")
            if not isinstance(manifest, dict):
                raise ValueError(f"campaign not found: {campaign_id}")
            if (
                manifest.get("compatibility_fingerprint")
                != identity["compatibility_fingerprint"]
            ):
                raise ValueError("campaign inputs are not compatible with this paper")
            selected, selected_manifest = candidate, manifest
        elif resume_mode != "new":
            candidates = []
            for manifest_path in self.campaigns_root.glob("*/manifest.json"):
                manifest = _read_json(manifest_path)
                if not isinstance(manifest, dict):
                    continue
                if (
                    manifest.get("compatibility_fingerprint")
                    == identity["compatibility_fingerprint"]
                ):
                    candidates.append((str(manifest.get("updated_at", "")), manifest_path.parent, manifest))
            if candidates:
                _, selected, selected_manifest = max(candidates, key=lambda item: item[0])

        if selected is None:
            if resume_mode == "required" or campaign_id:
                raise ValueError("no compatible optimization campaign is available")
            poster_name = _safe_name(str(state.get("poster_name") or "poster"))
            new_id = (
                f"{poster_name}_{identity['compatibility_fingerprint'][:12]}_"
                f"{uuid.uuid4().hex[:6]}"
            )
            selected = self.campaigns_root / new_id
            selected.mkdir(parents=True, exist_ok=False)
            selected_manifest = {
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": new_id,
                "poster_name": state.get("poster_name"),
                **identity,
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
                "input_copies": self._copy_inputs(state, selected),
            }
            _atomic_json(selected / "manifest.json", selected_manifest)
            _atomic_json(selected / "campaign_state.json", {
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": new_id,
                "status": "NEW",
                "last_completed_iteration": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "template_count": 0,
                "strategy_counts": {},
                "recent_template_ids": [],
                "previous_accepted": None,
                "lineage_depth": 0,
                "best_candidate": None,
                "portfolio_state": None,
                "active_batch": None,
                "completed_batches": 0,
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            })
            resumed = False
        else:
            resumed = True

        campaign_state = _read_json(selected / "campaign_state.json", {}) or {}
        handle = CampaignHandle(
            campaign_id=str(selected_manifest["campaign_id"]),
            path=selected,
            manifest=selected_manifest,
            resumed=resumed,
            last_completed_iteration=int(
                campaign_state.get("last_completed_iteration", 0)
            ),
        )
        return handle

    @staticmethod
    def _copy_inputs(state: Dict[str, Any], campaign_dir: Path) -> Dict[str, str]:
        copied: Dict[str, str] = {}
        input_dir = campaign_dir / "inputs"
        for field, filename in (
            ("pdf_path", "paper.pdf"),
            ("logo_path", "logo.png"),
            ("aff_logo_path", "aff.png"),
        ):
            source = Path(str(state.get(field) or ""))
            if not source.is_file():
                continue
            input_dir.mkdir(parents=True, exist_ok=True)
            target = input_dir / filename
            shutil.copy2(source, target)
            copied[field] = str(target)
        return copied

    def apply_persisted_input_paths(
        self,
        handle: CampaignHandle,
        state: Dict[str, Any],
    ) -> None:
        for field, raw_path in (handle.manifest.get("input_copies") or {}).items():
            path = Path(str(raw_path))
            if path.is_file():
                state[field] = str(path)

    @contextmanager
    def lease(self, handle: CampaignHandle) -> Iterator[None]:
        with _CampaignLease(handle.path / ".active.lock"):
            yield

    def load_campaign_state(self, handle: CampaignHandle) -> Dict[str, Any]:
        return _read_json(handle.path / "campaign_state.json", {}) or {}

    def register_session(
        self,
        handle: CampaignHandle,
        session_id: str,
        run_output_dir: Path,
    ) -> None:
        _atomic_json(handle.path / "sessions" / session_id / "session_state.json", {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": handle.campaign_id,
            "session_id": session_id,
            "status": "INITIALIZING",
            "run_output_dir": str(run_output_dir),
            "started_at": _utc_now(),
            "updated_at": _utc_now(),
        })

    def open_batch(
        self,
        handle: CampaignHandle,
        *,
        target_iterations: int,
        mode: Optional[str] = None,
        target_lineage_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resume an incomplete Batch or create the next finite Batch."""

        if target_iterations < 1:
            raise ValueError("target_iterations must be positive")
        if mode is not None and mode not in {"mixed", "explore", "improve", "mutate", "validate"}:
            raise ValueError(f"Unsupported Batch mode: {mode}")
        if target_lineage_id and mode not in {"improve", "mutate"}:
            raise ValueError("target_lineage_id requires improve or mutate mode")
        campaign_state = self.load_campaign_state(handle)
        active = campaign_state.get("active_batch")
        if (
            isinstance(active, dict)
            and active.get("status") == "IN_PROGRESS"
        ):
            committed_in_batch = max(
                0,
                int(campaign_state.get("last_completed_iteration", 0))
                - int(active.get("start_iteration", 1))
                + 1,
            )
            active["completed_iterations"] = max(
                int(active.get("completed_iterations", 0)),
                committed_in_batch,
            )
            if int(active["completed_iterations"]) < int(
                active.get("target_iterations", target_iterations)
            ):
                policy = active.setdefault("schedule_policy", {
                    "version": 1, "mode": "mixed", "target_lineage_id": None,
                })
                if mode is not None and mode != policy["mode"]:
                    raise ValueError("Active Batch mode is frozen; resume it or finish it before changing mode")
                if target_lineage_id is not None and target_lineage_id != policy.get("target_lineage_id"):
                    raise ValueError("Active Batch target Lineage is frozen")
                if (
                    policy.get("mode") == "mixed"
                    and int(policy.get("version", 1)) < SCHEDULE_POLICY_VERSION
                ):
                    policy.update({
                        "version": SCHEDULE_POLICY_VERSION,
                        "mode_weights": dict(
                            self.config.get("portfolio", {}).get(
                                "mode_weights", {}
                            )
                        ),
                    })
                    active["schema_version"] = BATCH_SCHEMA_VERSION
                    active["updated_at"] = _utc_now()
                    campaign_state["active_batch"] = active
                    campaign_state["updated_at"] = _utc_now()
                    _atomic_json(
                        handle.path / "campaign_state.json", campaign_state
                    )
                    _atomic_json(
                        handle.path / "batches" / str(active["batch_id"])
                        / "batch_state.json", active,
                    )
                return active

        number = max(
            int(campaign_state.get("completed_batches", 0)),
            int(active.get("batch_number", 0)) if isinstance(active, dict) else 0,
        ) + 1
        last_completed = int(campaign_state.get("last_completed_iteration", 0))
        selected_mode = mode or self.config.get("batch", {}).get(
            "default_mode", "mixed"
        )
        batch = {
            "schema_version": BATCH_SCHEMA_VERSION,
            "schedule_policy": {
                "version": SCHEDULE_POLICY_VERSION,
                "mode": selected_mode,
                "target_lineage_id": target_lineage_id,
                "mode_weights": dict(
                    self.config.get("portfolio", {}).get("mode_weights", {})
                ) if selected_mode == "mixed" else None,
            },
            "requested_mode_counts": {},
            "executed_mode_counts": {},
            "fallback_counts": {},
            "batch_id": f"batch_{number:04d}",
            "batch_number": number,
            "status": "IN_PROGRESS",
            "start_iteration": last_completed + 1,
            "target_iterations": int(target_iterations),
            "completed_iterations": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "family_counts": {},
            "mode_counts": {},
            "started_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        campaign_state["active_batch"] = batch
        campaign_state["updated_at"] = _utc_now()
        _atomic_json(handle.path / "campaign_state.json", campaign_state)
        _atomic_json(
            handle.path / "batches" / batch["batch_id"] / "batch_state.json",
            batch,
        )
        return batch

    def save_batch(
        self,
        handle: CampaignHandle,
        batch: Dict[str, Any],
        *,
        complete: bool = False,
    ) -> None:
        stored = _json_ready(batch)
        stored["updated_at"] = _utc_now()
        if complete:
            stored["status"] = "COMPLETED"
            stored["completed_at"] = _utc_now()
        campaign_state = self.load_campaign_state(handle)
        campaign_state["active_batch"] = stored
        if complete:
            campaign_state["completed_batches"] = max(
                int(campaign_state.get("completed_batches", 0)),
                int(stored.get("batch_number", 0)),
            )
        campaign_state["updated_at"] = _utc_now()
        _atomic_json(handle.path / "campaign_state.json", campaign_state)
        batch_dir = handle.path / "batches" / str(stored["batch_id"])
        _atomic_json(batch_dir / "batch_state.json", stored)
        if complete:
            _atomic_json(batch_dir / "batch_report.json", stored)

    def save_lineage_snapshot(
        self,
        handle: CampaignHandle,
        lineage_id: str,
        state: Dict[str, Any],
        lineage: Dict[str, Any],
        *,
        accepted: bool,
    ) -> None:
        lineage_dir = handle.path / "lineages" / _safe_name(lineage_id)
        _atomic_json(lineage_dir / "lineage_state.json", lineage)
        report = state.get("critic_report") or {}
        rubric_version = str(report.get("rubric_version") or self.config.get("rubric_version", "unknown"))
        snapshot = {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "saved_at": _utc_now(),
            "accepted": accepted,
            "rubric_version": rubric_version,
            "critic_system_version": report.get("critic_system_version"),
            "fields": {
                field: _json_ready(state.get(field))
                for field in self.SNAPSHOT_FIELDS
            },
        }
        _atomic_json(lineage_dir / "latest_state.json", snapshot)
        if accepted:
            rubric_best_path = lineage_dir / f"best_state_{_safe_name(rubric_version)}.json"
            existing = _read_json(rubric_best_path, {}) or {}
            old_score = float(existing.get("score", -1.0))
            score = float(report.get("overall_score", 0.0))
            if score >= old_score:
                snapshot["score"] = score
                _atomic_json(rubric_best_path, snapshot)
                _atomic_json(lineage_dir / "best_state.json", snapshot)

    def load_lineage_snapshot(
        self,
        handle: CampaignHandle,
        lineage_id: str,
        state: Dict[str, Any],
    ) -> bool:
        lineage_dir = handle.path / "lineages" / _safe_name(lineage_id)
        rubric_version = str(self.config.get("rubric_version", "unknown"))
        payload = _read_json(
            lineage_dir / f"best_state_{_safe_name(rubric_version)}.json"
        )
        if not isinstance(payload, dict):
            payload = _read_json(lineage_dir / "latest_state.json")
        if not isinstance(payload, dict):
            return False
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            return False
        for field in self.SNAPSHOT_FIELDS:
            if field in fields:
                state[field] = fields[field]
        return True

    def checkpoint(
        self,
        handle: CampaignHandle,
        session_id: str,
        loop_state: Dict[str, Any],
    ) -> None:
        campaign_state = self.load_campaign_state(handle)
        last_completed = max(
            int(campaign_state.get("last_completed_iteration", 0)),
            int(loop_state.get("last_completed_iteration", 0)),
        )
        campaign_state.update({
            key: _json_ready(value)
            for key, value in loop_state.items()
            if key not in {"session_id", "started_at", "run_output_dir"}
        })
        campaign_state.update({
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": handle.campaign_id,
            "last_completed_iteration": last_completed,
            "active_session_id": session_id,
            "updated_at": _utc_now(),
        })
        _atomic_json(handle.path / "campaign_state.json", campaign_state)
        _atomic_json(
            handle.path / "sessions" / session_id / "session_state.json",
            {**_json_ready(loop_state), "campaign_id": handle.campaign_id},
        )
        manifest = dict(handle.manifest)
        manifest["updated_at"] = _utc_now()
        _atomic_json(handle.path / "manifest.json", manifest)
        handle.manifest = manifest
        handle.last_completed_iteration = last_completed

    def has_foundation(self, handle: CampaignHandle) -> bool:
        return (handle.path / "foundation" / "scientific_state.json").is_file()

    def save_foundation(self, handle: CampaignHandle, state: Dict[str, Any]) -> None:
        payload = {
            "schema_version": FOUNDATION_SCHEMA_VERSION,
            "saved_at": _utc_now(),
            "fields": {
                field: _json_ready(state.get(field))
                for field in self.FOUNDATION_FIELDS
            },
        }
        _atomic_json(handle.path / "foundation" / "scientific_state.json", payload)

    def load_foundation(self, handle: CampaignHandle, state: Dict[str, Any]) -> bool:
        payload = _read_json(handle.path / "foundation" / "scientific_state.json")
        if not isinstance(payload, dict):
            return False
        if int(payload.get("schema_version", 0)) != FOUNDATION_SCHEMA_VERSION:
            return False
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            return False
        for field in self.FOUNDATION_FIELDS:
            if field in fields:
                state[field] = fields[field]
        return bool(state.get("verification_passed"))

    def recover_incomplete(self, handle: CampaignHandle) -> int:
        """Mark stale attempts abandoned and return the last contiguous commit."""

        iterations_root = handle.path / "iterations"
        iterations_root.mkdir(parents=True, exist_ok=True)
        completed = []
        for iteration_dir in sorted(iterations_root.glob("[0-9][0-9][0-9][0-9][0-9][0-9]")):
            try:
                number = int(iteration_dir.name)
            except ValueError:
                continue
            marker = _read_json(iteration_dir / "COMPLETED.json")
            if isinstance(marker, dict):
                completed.append(number)
                continue
            for attempt_dir in (iteration_dir / "attempts").glob("*"):
                status = _read_json(attempt_dir / "status.json", {}) or {}
                # The iteration-level marker is the sole commit point. A process
                # can die after writing attempt status but before publishing
                # COMPLETED.json, so locally completed attempts here are still
                # uncommitted and must be abandoned.
                self._remove_incomplete_artifacts(status)
                status.update({
                    "status": "ABANDONED",
                    "abandoned_at": _utc_now(),
                    "reason": "interrupted_before_commit",
                })
                _atomic_json(attempt_dir / "status.json", status)

        last_contiguous = 0
        for number in sorted(set(completed)):
            if number == last_contiguous + 1:
                last_contiguous = number
            elif number > last_contiguous + 1:
                break
        campaign_state = self.load_campaign_state(handle)
        campaign_state["last_completed_iteration"] = last_contiguous
        campaign_state["updated_at"] = _utc_now()
        _atomic_json(handle.path / "campaign_state.json", campaign_state)
        handle.last_completed_iteration = last_contiguous
        return last_contiguous

    @staticmethod
    def _remove_incomplete_artifacts(status: Dict[str, Any]) -> None:
        raw_dir = status.get("candidate_dir")
        if not raw_dir:
            return
        candidate_dir = Path(str(raw_dir)).resolve()
        for raw_path in status.get("candidate_artifacts", []):
            path = Path(str(raw_path)).resolve()
            try:
                path.relative_to(candidate_dir)
            except ValueError:
                continue
            if path.is_file() and path.suffix.lower() in {".pptx", ".png"}:
                path.unlink()

    def begin_iteration(
        self,
        handle: CampaignHandle,
        *,
        iteration: int,
        session_id: str,
        candidate: Dict[str, Any],
    ) -> IterationAttempt:
        iteration_dir = handle.path / "iterations" / f"{iteration:06d}"
        attempts_dir = iteration_dir / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)
        attempt_number = 1 + sum(path.is_dir() for path in attempts_dir.iterdir())
        attempt_id = f"attempt_{attempt_number:03d}_{uuid.uuid4().hex[:8]}"
        attempt_dir = attempts_dir / attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=False)
        _atomic_json(attempt_dir / "status.json", {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": handle.campaign_id,
            "session_id": session_id,
            "iteration": iteration,
            "attempt_number": attempt_number,
            "attempt_id": attempt_id,
            "status": "IN_PROGRESS",
            "started_at": _utc_now(),
            "candidate_id": candidate.get("candidate_id"),
            "candidate_dir": candidate.get("candidate_dir"),
            "candidate_artifacts": [
                candidate.get("pptx_path"),
                candidate.get("png_path"),
            ],
        })
        return IterationAttempt(iteration, attempt_number, attempt_id, attempt_dir)

    def abandon_attempt(self, attempt: IterationAttempt, reason: str) -> None:
        status = _read_json(attempt.path / "status.json", {}) or {}
        self._remove_incomplete_artifacts(status)
        status.update({
            "status": "ABANDONED",
            "abandoned_at": _utc_now(),
            "reason": reason,
        })
        _atomic_json(attempt.path / "status.json", status)

    def commit_iteration(
        self,
        handle: CampaignHandle,
        attempt: IterationAttempt,
        *,
        state: Dict[str, Any],
        report: Dict[str, Any],
        outcome: Dict[str, Any],
        loop_state: Dict[str, Any],
    ) -> None:
        snapshot = {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "iteration": attempt.iteration,
            "fields": {
                field: _json_ready(state.get(field))
                for field in self.SNAPSHOT_FIELDS
            },
        }
        _atomic_json(attempt.path / "state_snapshot.json", snapshot)
        _atomic_json(attempt.path / "critic_report.json", report)
        _atomic_json(attempt.path / "outcome.json", outcome)
        status = _read_json(attempt.path / "status.json", {}) or {}
        status.update({"status": "COMPLETED", "completed_at": _utc_now()})
        _atomic_json(attempt.path / "status.json", status)

        iteration_dir = attempt.path.parents[1]
        completion = {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": handle.campaign_id,
            "iteration": attempt.iteration,
            "attempt_id": attempt.attempt_id,
            "candidate_id": report.get("candidate_id"),
            "decision": report.get("decision"),
            "rubric_version": report.get("rubric_version"),
            "critic_system_version": report.get("critic_system_version"),
            "completed_at": _utc_now(),
        }
        # This marker is the commit point.  It is always written last.
        _atomic_json(iteration_dir / "COMPLETED.json", completion)
        loop_state["last_completed_iteration"] = attempt.iteration
        self.checkpoint(handle, str(loop_state["session_id"]), loop_state)

    def load_last_snapshot(
        self,
        handle: CampaignHandle,
        state: Dict[str, Any],
    ) -> bool:
        iteration = int(handle.last_completed_iteration)
        if iteration <= 0:
            return False
        iteration_dir = handle.path / "iterations" / f"{iteration:06d}"
        marker = _read_json(iteration_dir / "COMPLETED.json")
        if not isinstance(marker, dict):
            return False
        attempt_id = marker.get("attempt_id")
        payload = _read_json(
            iteration_dir / "attempts" / str(attempt_id) / "state_snapshot.json"
        )
        if not isinstance(payload, dict):
            return False
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            return False
        for field in self.SNAPSHOT_FIELDS:
            if field in fields:
                state[field] = fields[field]
        return True
