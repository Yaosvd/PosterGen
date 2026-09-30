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
from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

from src.layout.families import LAYOUT_ENGINE_SCHEMA_VERSION

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


CAMPAIGN_SCHEMA_VERSION = 6
FOUNDATION_SCHEMA_VERSION = 2
BATCH_SCHEMA_VERSION = 7
SCHEDULE_POLICY_VERSION = 3
CONTENT_MEMORY_SCHEMA_VERSION = 1


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


def _canonical_digest(value: Any) -> str:
    canonical = json.dumps(
        _json_ready(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned[:48] or "poster"


def _valid_persisted_id(value: str) -> bool:
    return bool(
        value
        and value not in {".", ".."}
        and len(value) <= 96
        and re.fullmatch(r"[A-Za-z0-9_.-]+", value)
    )


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

    ITERATION_SNAPSHOT_FIELDS = (
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
        "layout_feasibility_report",
        "layout_preflight_report",
        "layout_content_selection",
    )

    # A Lineage owns one active design/content-selection branch. Campaign-wide
    # verified variants and supplemental evidence are deliberately excluded:
    # restoring an old Lineage must never roll shared append-only knowledge
    # back to the version that happened to exist when that branch was saved.
    LINEAGE_SNAPSHOT_FIELDS = tuple(
        field for field in ITERATION_SNAPSHOT_FIELDS
        if field not in {"verified_content_bank", "supplemental_evidence_bank"}
    )
    CAMPAIGN_CONTENT_MEMORY_FIELDS = (
        "verified_content_bank",
        "supplemental_evidence_bank",
    )
    # Compatibility for callers that treat a committed iteration as the full
    # state snapshot. New Lineage code must use LINEAGE_SNAPSHOT_FIELDS.
    SNAPSHOT_FIELDS = ITERATION_SNAPSHOT_FIELDS

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

    @staticmethod
    def _legacy_layout_identity_matches(
        manifest: Dict[str, Any],
        identity: Dict[str, Any],
    ) -> bool:
        """Allow an in-place engine migration when all user inputs match."""

        try:
            previous_layout = int(
                manifest.get("layout_engine_schema_version", 0)
            )
        except (TypeError, ValueError):
            return False
        if previous_layout >= LAYOUT_ENGINE_SCHEMA_VERSION:
            return False
        for field in (
            "paper_sha256",
            "poster_width",
            "poster_height",
            "foundation_schema_version",
            "asset_sha256",
        ):
            if manifest.get(field) != identity.get(field):
                return False
        return True

    @staticmethod
    def _migrate_layout_identity(
        campaign_path: Path,
        manifest: Dict[str, Any],
        identity: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Atomically advance only the derived layout-engine identity."""

        with _CampaignLease(campaign_path / ".campaign.lock"):
            current = _read_json(
                campaign_path / "manifest.json", manifest
            ) or dict(manifest)
            if (
                current.get("compatibility_fingerprint")
                == identity["compatibility_fingerprint"]
            ):
                return current
            previous = int(
                current.get("layout_engine_schema_version", 0)
            )
            migrated = dict(current)
            migrated.update(identity)
            history = list(
                migrated.get("layout_engine_migration_history") or []
            )
            history.append({
                "from_version": previous,
                "to_version": LAYOUT_ENGINE_SCHEMA_VERSION,
                "migrated_at": _utc_now(),
                "policy": "preserve_foundation_batches_and_lineages",
            })
            migrated["layout_engine_migration_history"] = history[-20:]
            migrated["updated_at"] = _utc_now()
            _atomic_json(campaign_path / "manifest.json", migrated)
            return migrated

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
            if not _valid_persisted_id(campaign_id):
                raise ValueError("invalid campaign_id")
            candidate = self.campaigns_root / campaign_id
            manifest = _read_json(candidate / "manifest.json")
            if not isinstance(manifest, dict):
                raise ValueError(f"campaign not found: {campaign_id}")
            exact = (
                manifest.get("compatibility_fingerprint")
                == identity["compatibility_fingerprint"]
            )
            if not exact and not self._legacy_layout_identity_matches(
                manifest, identity
            ):
                raise ValueError("campaign inputs are not compatible with this paper")
            if not exact:
                manifest = self._migrate_layout_identity(
                    candidate, manifest, identity
                )
            selected, selected_manifest = candidate, manifest
        elif resume_mode != "new":
            candidates = []
            for manifest_path in self.campaigns_root.glob("*/manifest.json"):
                manifest = _read_json(manifest_path)
                if not isinstance(manifest, dict):
                    continue
                exact = (
                    manifest.get("compatibility_fingerprint")
                    == identity["compatibility_fingerprint"]
                )
                legacy = self._legacy_layout_identity_matches(
                    manifest, identity
                )
                if exact or legacy:
                    candidates.append((
                        str(manifest.get("updated_at", "")),
                        manifest_path.parent,
                        manifest,
                        exact,
                    ))
            if candidates:
                _, selected, selected_manifest, exact = max(
                    candidates, key=lambda item: item[0]
                )
                if not exact:
                    selected_manifest = self._migrate_layout_identity(
                        selected, selected_manifest, identity
                    )

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
                "active_batch_id": None,
                "batch_ids": [],
                "paused_batch_ids": [],
                "archived_batch_ids": [],
                "next_batch_number": 1,
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

    def load_existing_campaign(self, campaign_id: str) -> CampaignHandle:
        """Open an exact persisted Campaign for model-free administration."""

        if not _valid_persisted_id(campaign_id):
            raise ValueError("invalid campaign_id")
        candidate = (self.campaigns_root / campaign_id).resolve()
        try:
            candidate.relative_to(self.campaigns_root.resolve())
        except ValueError as exc:
            raise ValueError("invalid campaign_id") from exc
        manifest = _read_json(candidate / "manifest.json")
        if not isinstance(manifest, dict):
            raise ValueError(f"campaign not found: {campaign_id}")
        if str(manifest.get("campaign_id") or "") != campaign_id:
            raise ValueError("campaign manifest identity mismatch")
        campaign_state = self.load_campaign_state(CampaignHandle(
            campaign_id=campaign_id,
            path=candidate,
            manifest=manifest,
            resumed=True,
            last_completed_iteration=0,
        ))
        return CampaignHandle(
            campaign_id=campaign_id,
            path=candidate,
            manifest=manifest,
            resumed=True,
            last_completed_iteration=int(
                campaign_state.get("last_completed_iteration", 0)
            ),
        )

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
        path = handle.path / "campaign_state.json"
        state = _read_json(path, {}) or {}
        migrated = self._migrate_batch_registry(handle, state)
        if migrated != state:
            _atomic_json(path, migrated)
        return migrated

    def _migrate_batch_registry(
        self,
        handle: CampaignHandle,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Lazily migrate the legacy single-active-Batch representation."""

        migrated = dict(state)
        batches: Dict[str, Dict[str, Any]] = {}
        batches_root = handle.path / "batches"
        if batches_root.is_dir():
            for path in sorted(batches_root.glob("*/batch_state.json")):
                payload = _read_json(path)
                if isinstance(payload, dict) and payload.get("batch_id"):
                    batches[str(payload["batch_id"])] = dict(payload)

        legacy_active = migrated.get("active_batch")
        if isinstance(legacy_active, dict) and legacy_active.get("batch_id"):
            batch_id = str(legacy_active["batch_id"])
            merged = dict(batches.get(batch_id, {}))
            merged.update(legacy_active)
            batches[batch_id] = merged

        ordered = sorted(
            batches.values(),
            key=lambda item: (
                int(item.get("batch_number", 0)), str(item.get("batch_id", ""))
            ),
        )
        marker_ids: Dict[str, list[int]] = {
            str(item["batch_id"]): [] for item in ordered
        }
        for marker_path in sorted(
            (handle.path / "iterations").glob("*/COMPLETED.json")
        ):
            marker = _read_json(marker_path)
            if not isinstance(marker, dict):
                continue
            try:
                iteration = int(marker.get("iteration", marker_path.parent.name))
            except (TypeError, ValueError):
                continue
            batch_id = str(marker.get("batch_id") or "")
            if batch_id not in marker_ids:
                matches = []
                for item in ordered:
                    start = int(item.get("start_iteration", 1))
                    completed = int(item.get("completed_iterations", 0))
                    end = int(item.get("end_iteration", start + completed - 1))
                    if completed > 0 and start <= iteration <= end:
                        matches.append(str(item["batch_id"]))
                if not matches:
                    matches = [
                        str(item["batch_id"])
                        for item in ordered
                        if item.get("status") == "IN_PROGRESS"
                        and int(item.get("start_iteration", 1)) <= iteration
                        < int(item.get("start_iteration", 1))
                        + int(item.get("target_iterations", 0))
                    ]
                if len(matches) == 1:
                    batch_id = matches[0]
                    marker["batch_id"] = batch_id
                    _atomic_json(marker_path, marker)
                elif ordered:
                    raise ValueError(
                        "Cannot safely attribute legacy committed iteration "
                        f"{iteration} to one Batch"
                    )
            if batch_id in marker_ids:
                marker_ids[batch_id].append(iteration)

        for item in ordered:
            original_item = dict(item)
            batch_id = str(item["batch_id"])
            committed = sorted(set(
                int(value) for value in (
                    item.get("committed_iteration_ids") or marker_ids[batch_id]
                )
            ))
            if marker_ids[batch_id]:
                committed = sorted(set(marker_ids[batch_id]))
            self._migrate_schedule_policy(item)
            item["schema_version"] = BATCH_SCHEMA_VERSION
            item["campaign_id"] = handle.campaign_id
            item.setdefault("layout_recovery_blocks", {})
            item["committed_iteration_ids"] = committed
            legacy_completed = int(item.get("completed_iterations", 0))
            if committed or legacy_completed == 0:
                item["completed_iterations"] = len(committed)
            if committed:
                item["start_iteration"] = min(
                    int(item.get("start_iteration", committed[0])), committed[0]
                )
                item["end_iteration"] = max(committed)
            if int(item.get("completed_iterations", 0)) >= int(
                item.get("target_iterations", 1)
            ):
                item["status"] = "COMPLETED"
                item.setdefault("completed_at", item.get("updated_at") or _utc_now())
            if item != original_item:
                _atomic_json(batches_root / batch_id / "batch_state.json", item)
            batches[batch_id] = item

        batch_ids = [str(item["batch_id"]) for item in ordered]
        active_ids = [
            batch_id for batch_id in batch_ids
            if batches[batch_id].get("status") == "IN_PROGRESS"
        ]
        if len(active_ids) > 1:
            raise ValueError(
                "Campaign is corrupt: multiple Batches are marked IN_PROGRESS"
            )
        requested_active = str(migrated.get("active_batch_id") or "")
        active_id = (
            requested_active if requested_active in active_ids
            else active_ids[-1] if active_ids else None
        )
        paused_ids = [
            batch_id for batch_id in batch_ids
            if batches[batch_id].get("status") == "PAUSED"
        ]
        archived_ids = [
            batch_id for batch_id in batch_ids
            if batches[batch_id].get("status") == "ARCHIVED"
        ]
        highest = max(
            [int(item.get("batch_number", 0)) for item in ordered] or [0]
        )
        migrated.update({
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "batch_ids": batch_ids,
            "active_batch_id": active_id,
            "active_batch": batches.get(active_id) if active_id else (
                batches.get(str((legacy_active or {}).get("batch_id")))
                if isinstance(legacy_active, dict) else None
            ),
            "paused_batch_ids": paused_ids,
            "archived_batch_ids": archived_ids,
            "next_batch_number": max(
                int(migrated.get("next_batch_number", 1)), highest + 1
            ),
            "completed_batches": sum(
                batches[batch_id].get("status") == "COMPLETED"
                for batch_id in batch_ids
            ),
        })
        return migrated

    def load_batch(
        self, handle: CampaignHandle, batch_id: str
    ) -> Dict[str, Any]:
        if _safe_name(batch_id) != batch_id:
            raise ValueError("invalid batch_id")
        payload = _read_json(
            handle.path / "batches" / batch_id / "batch_state.json"
        )
        if not isinstance(payload, dict):
            raise ValueError(f"Batch not found: {batch_id}")
        return payload

    def list_batches(self, handle: CampaignHandle) -> list[Dict[str, Any]]:
        campaign_state = self.load_campaign_state(handle)
        result = []
        for batch_id in campaign_state.get("batch_ids") or []:
            try:
                result.append(self.load_batch(handle, str(batch_id)))
            except ValueError:
                continue
        return result

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

    def _migrate_schedule_policy(self, batch: Dict[str, Any]) -> None:
        """Upgrade zero-use legacy mixed policies; fail closed on Mutate history."""

        policy = batch.setdefault("schedule_policy", {
            "version": 1,
            "mode": "mixed",
            "target_lineage_id": None,
        })
        if str(policy.get("mode")) == "mutate":
            raise ValueError(
                "Legacy Mutate Batch cannot be resumed by this release"
            )
        executed_mutate = max(
            int((batch.get("executed_mode_counts") or {}).get("mutate", 0)),
            int((batch.get("mode_counts") or {}).get("mutate", 0)),
        )
        if executed_mutate:
            raise ValueError(
                "Cannot migrate Batch with executed Mutate history; "
                "preserve it with a compatible historical release"
            )
        for field in ("requested_mode_counts", "executed_mode_counts", "mode_counts"):
            counts = batch.get(field)
            if isinstance(counts, dict):
                counts.pop("mutate", None)
        old_version = int(policy.get("version", 1))
        old_weights = dict(policy.get("mode_weights") or {})
        if str(policy.get("mode")) == "mixed" and (
            old_version < SCHEDULE_POLICY_VERSION or "mutate" in old_weights
        ):
            policy.update({
                "version": SCHEDULE_POLICY_VERSION,
                "mode_weights": dict(
                    self.config.get("portfolio", {}).get("mode_weights", {})
                ),
            })
            batch["schedule_policy_migration"] = {
                "from_version": old_version,
                "to_version": SCHEDULE_POLICY_VERSION,
                "from_mode_weights": old_weights,
                "to_mode_weights": dict(policy["mode_weights"]),
                "reason": "remove_unused_mutate_mode",
                "migrated_at": _utc_now(),
            }
        else:
            policy["version"] = SCHEDULE_POLICY_VERSION

    def open_batch(
        self,
        handle: CampaignHandle,
        *,
        target_iterations: int,
        mode: Optional[str] = None,
        target_lineage_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        new_batch: bool = False,
    ) -> Dict[str, Any]:
        """Resume one selected Batch or create the next finite Batch."""

        if target_iterations < 1:
            raise ValueError("target_iterations must be positive")
        if mode is not None and mode not in {
            "mixed", "explore", "improve", "validate"
        }:
            raise ValueError(f"Unsupported Batch mode: {mode}")
        if target_lineage_id and mode != "improve":
            raise ValueError("target_lineage_id requires improve mode")
        if batch_id and new_batch:
            raise ValueError("batch_id and new_batch are mutually exclusive")

        campaign_state = self.load_campaign_state(handle)
        active_id = campaign_state.get("active_batch_id")
        if active_id:
            active = self.load_batch(handle, str(active_id))
            if batch_id and batch_id != active_id:
                raise ValueError(
                    f"Batch {active_id} is already running in this Campaign"
                )
            if new_batch:
                raise ValueError(
                    f"Pause Batch {active_id} before creating another Batch"
                )
            return self._resume_batch(
                handle,
                active,
                mode=mode,
                target_lineage_id=target_lineage_id,
            )

        selected: Optional[Dict[str, Any]] = None
        if batch_id:
            selected = self.load_batch(handle, batch_id)
        elif not new_batch:
            all_batches = self.list_batches(handle)
            paused = [
                item for item in all_batches if item.get("status") == "PAUSED"
            ]
            failed = [
                item for item in all_batches
                if item.get("status") == "FAILED_REQUIRES_USER"
            ]
            if len(paused) == 1 and not failed:
                selected = paused[0]
            elif paused or failed:
                identifiers = ", ".join(
                    "{} ({})".format(item["batch_id"], item.get("status"))
                    for item in [*paused, *failed]
                )
                raise ValueError(
                    "Batch selection is ambiguous or requires explicit retry; "
                    f"specify --batch-id or --new-batch: {identifiers}"
                )
        if selected is not None:
            return self._resume_batch(
                handle,
                selected,
                mode=mode,
                target_lineage_id=target_lineage_id,
            )

        number = int(campaign_state.get("next_batch_number", 1))
        last_completed = int(campaign_state.get("last_completed_iteration", 0))
        selected_mode = mode or self.config.get("batch", {}).get(
            "default_mode", "mixed"
        )
        now = _utc_now()
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
            "layout_recovery_blocks": {},
            "batch_id": f"batch_{number:04d}",
            "batch_number": number,
            "campaign_id": handle.campaign_id,
            "status": "IN_PROGRESS",
            "start_iteration": last_completed + 1,
            "target_iterations": int(target_iterations),
            "completed_iterations": 0,
            "committed_iteration_ids": [],
            "accepted_count": 0,
            "rejected_count": 0,
            "family_counts": {},
            "mode_counts": {},
            "created_at": now,
            "started_at": now,
            "knowledge_watermarks": {
                "created_after_iteration": last_completed,
                "last_resumed_after_iteration": last_completed,
            },
            "updated_at": now,
        }
        campaign_state["next_batch_number"] = number + 1
        self.save_batch(handle, batch, campaign_state=campaign_state)
        return batch

    def _resume_batch(
        self,
        handle: CampaignHandle,
        batch: Dict[str, Any],
        *,
        mode: Optional[str],
        target_lineage_id: Optional[str],
    ) -> Dict[str, Any]:
        status = str(batch.get("status"))
        if status in {
            "COMPLETED",
            "EXHAUSTED",
            "UNAVAILABLE",
            "FAILED_REQUIRES_USER",
            "ARCHIVED",
        }:
            raise ValueError(
                f"Batch {batch.get('batch_id')} is {status} and cannot be resumed"
            )
        policy = batch.setdefault("schedule_policy", {
            "version": 1,
            "mode": "mixed",
            "target_lineage_id": None,
        })
        if mode is not None and mode != policy.get("mode"):
            raise ValueError("Batch mode is frozen; resume it without changing mode")
        if (
            target_lineage_id is not None
            and target_lineage_id != policy.get("target_lineage_id")
        ):
            raise ValueError("Batch target Lineage is frozen")
        self._migrate_schedule_policy(batch)
        policy = batch["schedule_policy"]
        campaign_state = self.load_campaign_state(handle)
        last_completed = int(campaign_state.get("last_completed_iteration", 0))
        batch.update({
            "schema_version": BATCH_SCHEMA_VERSION,
            "campaign_id": handle.campaign_id,
            "status": "IN_PROGRESS",
            "last_resumed_at": _utc_now(),
        })
        batch.setdefault("layout_recovery_blocks", {})
        watermarks = batch.setdefault("knowledge_watermarks", {})
        watermarks.setdefault("created_after_iteration", last_completed)
        watermarks["last_resumed_after_iteration"] = last_completed
        self.save_batch(handle, batch, campaign_state=campaign_state)
        return batch

    def save_batch(
        self,
        handle: CampaignHandle,
        batch: Dict[str, Any],
        *,
        complete: bool = False,
        campaign_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        stored = _json_ready(batch)
        stored["updated_at"] = _utc_now()
        if complete:
            stored["status"] = "COMPLETED"
            stored["completed_at"] = _utc_now()
        committed = sorted(set(
            int(value) for value in stored.get("committed_iteration_ids", [])
        ))
        stored["committed_iteration_ids"] = committed
        if committed:
            stored["completed_iterations"] = len(committed)
            stored["start_iteration"] = min(
                int(stored.get("start_iteration", committed[0])), committed[0]
            )
            stored["end_iteration"] = max(committed)

        campaign_state = campaign_state or self.load_campaign_state(handle)
        batch_ids = list(campaign_state.get("batch_ids") or [])
        if stored["batch_id"] not in batch_ids:
            batch_ids.append(stored["batch_id"])
        campaign_state["batch_ids"] = batch_ids
        campaign_state["active_batch"] = stored
        campaign_state["active_batch_id"] = (
            stored["batch_id"] if stored.get("status") == "IN_PROGRESS" else None
        )

        statuses: Dict[str, str] = {}
        for known_id in batch_ids:
            if known_id == stored["batch_id"]:
                statuses[known_id] = str(stored.get("status"))
            else:
                known = _read_json(
                    handle.path / "batches" / known_id / "batch_state.json", {}
                ) or {}
                statuses[known_id] = str(known.get("status"))
        campaign_state["paused_batch_ids"] = [
            known_id for known_id in batch_ids
            if statuses.get(known_id) == "PAUSED"
        ]
        campaign_state["archived_batch_ids"] = [
            known_id for known_id in batch_ids
            if statuses.get(known_id) == "ARCHIVED"
        ]
        campaign_state["completed_batches"] = sum(
            statuses.get(known_id) == "COMPLETED" for known_id in batch_ids
        )
        campaign_state["next_batch_number"] = max(
            int(campaign_state.get("next_batch_number", 1)),
            int(stored.get("batch_number", 0)) + 1,
        )
        campaign_state["updated_at"] = _utc_now()

        batch_dir = handle.path / "batches" / str(stored["batch_id"])
        _atomic_json(batch_dir / "batch_state.json", stored)
        _atomic_json(handle.path / "campaign_state.json", campaign_state)
        batch.clear()
        batch.update(stored)
        if stored.get("status") in {
            "COMPLETED", "EXHAUSTED", "UNAVAILABLE", "ARCHIVED"
        }:
            _atomic_json(batch_dir / "batch_report.json", stored)

    def pause_batch(
        self,
        handle: CampaignHandle,
        batch: Dict[str, Any],
        *,
        reason: str,
    ) -> Dict[str, Any]:
        if batch.get("status") not in {"COMPLETED", "EXHAUSTED", "UNAVAILABLE"}:
            batch["status"] = "PAUSED"
            batch["paused_at"] = _utc_now()
            batch["pause_reason"] = reason
            self.save_batch(handle, batch)
        return batch

    def archive_batch(
        self, handle: CampaignHandle, batch_id: str
    ) -> Dict[str, Any]:
        batch = self.load_batch(handle, batch_id)
        if batch.get("status") == "IN_PROGRESS":
            raise ValueError("A running Batch must be paused before it is archived")
        if batch.get("status") not in {
            "PAUSED", "FAILED_REQUIRES_USER", "ARCHIVED"
        }:
            raise ValueError("Only paused or failed Batches can be archived")
        batch["status"] = "ARCHIVED"
        batch["archived_at"] = _utc_now()
        self.save_batch(handle, batch)
        return batch

    def unarchive_batch(
        self, handle: CampaignHandle, batch_id: str
    ) -> Dict[str, Any]:
        batch = self.load_batch(handle, batch_id)
        if batch.get("status") != "ARCHIVED":
            raise ValueError("Batch is not archived")
        batch["status"] = "PAUSED"
        batch["unarchived_at"] = _utc_now()
        self.save_batch(handle, batch)
        return batch

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
        _atomic_json(
            lineage_dir / "latest_feedback.json",
            lineage.get("latest_feedback") or {},
        )
        _atomic_json(
            lineage_dir / "revision_history.json",
            {
                "schema_version": 1,
                "lineage_id": lineage_id,
                "attempts": list(
                    lineage.get("recent_revision_attempts") or []
                )[-25:],
            },
        )
        report = state.get("critic_report") or {}
        rubric_version = str(report.get("rubric_version") or self.config.get("rubric_version", "unknown"))
        snapshot = {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "saved_at": _utc_now(),
            "accepted": accepted,
            "candidate_id": report.get("candidate_id"),
            "score": (
                float(report["overall_score"])
                if isinstance(report.get("overall_score"), (int, float))
                else None
            ),
            "rubric_version": rubric_version,
            "critic_system_version": report.get("critic_system_version"),
            "fields": {
                field: _json_ready(state.get(field))
                for field in self.LINEAGE_SNAPSHOT_FIELDS
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
        elif (
            str(lineage.get("best_promising_candidate_id") or "")
            == str(report.get("candidate_id") or "")
        ):
            promising_path = (
                lineage_dir
                / f"best_promising_state_{_safe_name(rubric_version)}.json"
            )
            _atomic_json(promising_path, snapshot)
            _atomic_json(
                lineage_dir / "best_promising_state.json", snapshot
            )

    def load_lineage_snapshot(
        self,
        handle: CampaignHandle,
        lineage_id: str,
        state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        lineage_dir = handle.path / "lineages" / _safe_name(lineage_id)
        rubric_version = str(self.config.get("rubric_version", "unknown"))
        payload = _read_json(
            lineage_dir / f"best_state_{_safe_name(rubric_version)}.json"
        )
        snapshot_kind = "best"
        if not isinstance(payload, dict):
            payload = _read_json(
                lineage_dir
                / f"best_promising_state_{_safe_name(rubric_version)}.json"
            )
            snapshot_kind = "best_promising"
        if not isinstance(payload, dict):
            payload = _read_json(lineage_dir / "latest_state.json")
            snapshot_kind = "latest"
        if not isinstance(payload, dict):
            return None
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            return None
        for field in self.LINEAGE_SNAPSHOT_FIELDS:
            if field in fields:
                state[field] = fields[field]
        report = fields.get("critic_report") or {}
        stored_candidate = payload.get("candidate_id")
        report_candidate = report.get("candidate_id") if isinstance(report, dict) else None
        if stored_candidate and report_candidate and stored_candidate != report_candidate:
            raise ValueError("Lineage snapshot candidate identity mismatch")
        lineage_state = _read_json(lineage_dir / "lineage_state.json", {}) or {}
        if (
            snapshot_kind == "latest"
            and not bool(payload.get("accepted"))
            and str(lineage_state.get("best_candidate_id") or "")
            == str(stored_candidate or report_candidate or "")
            and not lineage_state.get("best_accepted_candidate_id")
        ):
            from src.workflow.portfolio import assess_promising_candidate

            assessment = assess_promising_candidate(report)
            if assessment.get("eligible"):
                promising_path = (
                    lineage_dir
                    / f"best_promising_state_{_safe_name(rubric_version)}.json"
                )
                _atomic_json(promising_path, payload)
                _atomic_json(
                    lineage_dir / "best_promising_state.json", payload
                )
                lineage_state.update({
                    "schema_version": 3,
                    "best_promising_score": payload.get("score"),
                    "best_promising_candidate_id": (
                        stored_candidate or report_candidate
                    ),
                    "best_promising_rank": assessment.get("rank") or {},
                    "best_promising_updated_at": _utc_now(),
                })
                _atomic_json(
                    lineage_dir / "lineage_state.json", lineage_state
                )
                snapshot_kind = "best_promising_migrated"
        feedback = _read_json(lineage_dir / "latest_feedback.json")
        if not isinstance(feedback, dict):
            feedback = lineage_state.get("latest_feedback") or {}
        if feedback and str(feedback.get("lineage_id") or lineage_id) != lineage_id:
            raise ValueError("Lineage feedback identity mismatch")
        feedback_rubric = feedback.get("rubric_version")
        if feedback_rubric and str(feedback_rubric) != rubric_version:
            feedback = {}
        history_payload = _read_json(
            lineage_dir / "revision_history.json", {}
        ) or {}
        history = history_payload.get("attempts")
        if not isinstance(history, list):
            history = lineage_state.get("recent_revision_attempts") or []
        history = [
            item for item in history
            if isinstance(item, dict)
            and str(item.get("rubric_version") or "") == rubric_version
        ]
        state["lineage_base_context"] = {
            "lineage_id": lineage_id,
            "snapshot_kind": snapshot_kind,
            "candidate_id": stored_candidate or report_candidate,
            "score": payload.get(
                "score",
                report.get("overall_score") if isinstance(report, dict) else None,
            ),
            "rubric_version": payload.get("rubric_version"),
            "saved_at": payload.get("saved_at"),
        }
        state["lineage_feedback"] = deepcopy(feedback)
        state["lineage_revision_history"] = deepcopy(history[-25:])
        return {
            "snapshot_kind": snapshot_kind,
            "candidate_id": stored_candidate or report_candidate,
            "score": payload.get("score", report.get("overall_score") if isinstance(report, dict) else None),
            "saved_at": payload.get("saved_at"),
            "feedback_candidate_id": feedback.get("candidate_id"),
        }

    @staticmethod
    def _empty_content_memory() -> Dict[str, Any]:
        return {
            "schema_version": CONTENT_MEMORY_SCHEMA_VERSION,
            "revision": 0,
            "digest": _canonical_digest({
                "verified_content_bank": {"schema_version": 1, "claims": []},
                "supplemental_evidence_bank": {
                    "schema_version": 1, "items": [],
                },
            }),
            "applied_iteration_events": [],
            "verified_content_bank": {"schema_version": 1, "claims": []},
            "supplemental_evidence_bank": {
                "schema_version": 1, "items": [],
            },
            "updated_at": _utc_now(),
        }

    @staticmethod
    def _merge_content_records(
        target: list[Dict[str, Any]],
        incoming: Iterable[Any],
        *,
        id_field: str,
        mutable_list_fields: Iterable[str] = (),
    ) -> None:
        mutable = set(mutable_list_fields)
        by_id = {
            str(item.get(id_field)): item
            for item in target
            if isinstance(item, dict) and item.get(id_field)
        }
        for raw in incoming:
            if not isinstance(raw, dict) or not raw.get(id_field):
                raise ValueError(
                    f"Campaign content memory contains an invalid {id_field}"
                )
            item = _json_ready(raw)
            identifier = str(item[id_field])
            existing = by_id.get(identifier)
            if existing is None:
                target.append(item)
                by_id[identifier] = item
                continue

            existing_fixed = {
                key: value for key, value in existing.items()
                if key not in mutable
            }
            incoming_fixed = {
                key: value for key, value in item.items()
                if key not in mutable
            }
            if _canonical_digest(existing_fixed) != _canonical_digest(
                incoming_fixed
            ):
                raise ValueError(
                    "Campaign content identity conflict for "
                    f"{id_field}={identifier}"
                )

            for field in mutable:
                merged: Dict[str, Any] = {}
                for value in [
                    *(existing.get(field) or []),
                    *(item.get(field) or []),
                ]:
                    key = _canonical_digest(value)
                    merged[key] = _json_ready(value)
                values = list(merged.values())
                values.sort(key=lambda value: (
                    str((value or {}).get("campaign_id", "")),
                    str((value or {}).get("batch_id", "")),
                    int((value or {}).get("iteration", 0) or 0),
                    _canonical_digest(value),
                ))
                existing[field] = values[-50:]

    def _merge_content_fields(
        self,
        memory: Dict[str, Any],
        fields: Dict[str, Any],
    ) -> None:
        variant_bank = fields.get("verified_content_bank") or {}
        supplemental_bank = fields.get("supplemental_evidence_bank") or {}
        variants = variant_bank.get("claims") or []
        evidence = supplemental_bank.get("items") or []
        if not isinstance(variants, list) or not isinstance(evidence, list):
            raise ValueError("Campaign content memory banks must contain lists")
        self._merge_content_records(
            memory["verified_content_bank"]["claims"],
            variants,
            id_field="claim_id",
            mutable_list_fields=("outcomes",),
        )
        self._merge_content_records(
            memory["supplemental_evidence_bank"]["items"],
            evidence,
            id_field="evidence_id",
        )

    @staticmethod
    def _content_semantics(memory: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "verified_content_bank": memory.get("verified_content_bank"),
            "supplemental_evidence_bank": memory.get(
                "supplemental_evidence_bank"
            ),
        }

    def reconcile_content_memory(
        self, handle: CampaignHandle
    ) -> Dict[str, Any]:
        """Apply committed content events to the Campaign materialized view."""

        marker_records = []
        for marker_path in sorted(
            (handle.path / "iterations").glob("*/COMPLETED.json")
        ):
            marker = _read_json(marker_path)
            if not isinstance(marker, dict):
                continue
            marker_records.append((
                f"{handle.campaign_id}:{int(marker.get('iteration', 0))}",
                marker_path,
                marker,
            ))

        path = handle.path / "memory" / "content_memory.json"
        existing = _read_json(path)
        event_ids = [item[0] for item in marker_records]
        use_existing = False
        if isinstance(existing, dict):
            applied = list(existing.get("applied_iteration_events") or [])
            digest = _canonical_digest(self._content_semantics(existing))
            use_existing = (
                int(existing.get("schema_version", 0))
                == CONTENT_MEMORY_SCHEMA_VERSION
                and applied == event_ids[:len(applied)]
                and digest == existing.get("digest")
                and isinstance(
                    (existing.get("verified_content_bank") or {}).get(
                        "claims"
                    ),
                    list,
                )
                and isinstance(
                    (existing.get("supplemental_evidence_bank") or {}).get(
                        "items"
                    ),
                    list,
                )
                and all(
                    isinstance(item, dict) and item.get("claim_id")
                    for item in (
                        (existing.get("verified_content_bank") or {}).get(
                            "claims"
                        ) or []
                    )
                )
                and all(
                    isinstance(item, dict) and item.get("evidence_id")
                    for item in (
                        (
                            existing.get("supplemental_evidence_bank")
                            or {}
                        ).get("items") or []
                    )
                )
            )

        memory = (
            _json_ready(existing)
            if use_existing
            else self._empty_content_memory()
        )
        events = list(memory.get("applied_iteration_events") or [])
        revision = int(memory.get("revision", 0) or 0)
        for event_id, marker_path, marker in marker_records[len(events):]:
            attempt_id = marker.get("attempt_id")
            snapshot = _read_json(
                marker_path.parent / "attempts" / str(attempt_id)
                / "state_snapshot.json"
            )
            fields = (
                snapshot.get("fields")
                if isinstance(snapshot, dict) else None
            )
            previous = _canonical_digest(self._content_semantics(memory))
            if isinstance(fields, dict):
                self._merge_content_fields(memory, fields)
            elif int(marker.get("schema_version", 0) or 0) >= (
                CAMPAIGN_SCHEMA_VERSION
            ):
                raise ValueError(
                    f"Committed content snapshot is missing: {marker_path}"
                )
            current = _canonical_digest(self._content_semantics(memory))
            if current != previous:
                revision += 1
            # Old committed markers can lack a recoverable snapshot. Treat the
            # event as applied with no content delta so future reconciliations
            # remain incremental; modern commits always persist the snapshot.
            events.append(event_id)

        memory.update({
            "schema_version": CONTENT_MEMORY_SCHEMA_VERSION,
            "revision": revision,
            "digest": _canonical_digest(self._content_semantics(memory)),
            "applied_iteration_events": events,
        })
        comparable = dict(memory)
        comparable.pop("updated_at", None)
        old_comparable = dict(existing) if isinstance(existing, dict) else {}
        old_comparable.pop("updated_at", None)
        if comparable != old_comparable:
            memory["updated_at"] = _utc_now()
            _atomic_json(path, memory)
        elif isinstance(existing, dict):
            memory["updated_at"] = existing.get("updated_at")
        return memory

    def validate_content_memory_state(
        self,
        handle: CampaignHandle,
        state: Dict[str, Any],
    ) -> None:
        """Fail before commit if a candidate conflicts with shared knowledge."""

        memory = self.reconcile_content_memory(handle)
        self._merge_content_fields(memory, state)

    def load_campaign_content_memory(
        self,
        handle: CampaignHandle,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        memory = self.reconcile_content_memory(handle)
        for field in self.CAMPAIGN_CONTENT_MEMORY_FIELDS:
            state[field] = _json_ready(memory[field])
        return memory

    @staticmethod
    def content_memory_snapshot(memory: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "schema_version": int(
                memory.get("schema_version", CONTENT_MEMORY_SCHEMA_VERSION)
            ),
            "revision": int(memory.get("revision", 0)),
            "digest": str(memory.get("digest") or ""),
            "verified_variant_count": len(
                (memory.get("verified_content_bank") or {}).get("claims") or []
            ),
            "supplemental_evidence_count": len(
                (memory.get("supplemental_evidence_bank") or {}).get("items")
                or []
            ),
        }

    @staticmethod
    def sanitize_content_selection(state: Dict[str, Any]) -> list[str]:
        selection = state.get("content_selection")
        if not isinstance(selection, dict):
            return []
        base_claims = (
            (state.get("verified_claims") or {}).get("claims") or []
        )
        variants = (
            (state.get("verified_content_bank") or {}).get("claims") or []
        )
        known = {
            str(item.get("claim_id"))
            for item in [*base_claims, *variants]
            if isinstance(item, dict) and item.get("claim_id")
        }
        roots = set(known)
        roots.update(
            str(item.get("root_claim_id"))
            for item in variants
            if isinstance(item, dict) and item.get("root_claim_id")
        )
        removed = []
        replacements = selection.get("replacements") or {}
        if isinstance(replacements, dict):
            clean = {}
            for root_id, claim_id in replacements.items():
                if str(root_id) in roots and str(claim_id) in known:
                    clean[str(root_id)] = str(claim_id)
                else:
                    removed.append(str(claim_id))
            selection["replacements"] = clean
        for field in (
            "active_supplemental_claim_ids",
            "disabled_claim_ids",
        ):
            values = selection.get(field) or []
            clean_values = [
                str(value) for value in values if str(value) in known
            ]
            removed.extend(
                str(value) for value in values if str(value) not in known
            )
            selection[field] = clean_values
        changed = selection.get("last_changed_iteration") or {}
        if isinstance(changed, dict):
            selection["last_changed_iteration"] = {
                str(root_id): value
                for root_id, value in changed.items()
                if str(root_id) in roots
            }
        return sorted(set(removed))


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
            if key not in {
                "session_id", "started_at", "run_output_dir", "batch",
                "active_batch", "active_batch_id", "batch_ids",
                "paused_batch_ids", "archived_batch_ids", "next_batch_number",
            }
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
        active_id = campaign_state.get("active_batch_id")
        if active_id:
            active = self.load_batch(handle, str(active_id))
            if active.get("status") == "IN_PROGRESS":
                self.pause_batch(
                    handle, active, reason="recovered_after_process_exit"
                )
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
        batch_id: Optional[str] = None,
    ) -> IterationAttempt:
        if batch_id is None:
            batch_id = self.load_campaign_state(handle).get("active_batch_id")
        if not batch_id:
            raise ValueError("begin_iteration requires an active Batch")
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
            "batch_id": batch_id,
            "session_id": session_id,
            "iteration": iteration,
            "attempt_number": attempt_number,
            "attempt_id": attempt_id,
            "status": "IN_PROGRESS",
            "started_at": _utc_now(),
            "candidate_id": candidate.get("candidate_id"),
            "candidate_dir": candidate.get("candidate_dir"),
            "knowledge_inputs": _json_ready(
                candidate.get("knowledge_inputs") or {}
            ),
            "selected_template_ids": _json_ready(
                candidate.get("selected_template_ids") or []
            ),
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
        status = _read_json(attempt.path / "status.json", {}) or {}
        batch_id = str(
            status.get("batch_id")
            or (loop_state.get("batch") or {}).get("batch_id")
            or ""
        )
        if not batch_id:
            raise ValueError("iteration commit requires a batch_id")
        # Validate shared scientific content before the sole commit marker is
        # written. Identity conflicts must fail closed and remain uncommitted.
        self.validate_content_memory_state(handle, state)
        snapshot = {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": handle.campaign_id,
            "batch_id": batch_id,
            "iteration": attempt.iteration,
            "fields": {
                field: _json_ready(state.get(field))
                for field in self.ITERATION_SNAPSHOT_FIELDS
            },
        }
        persisted_outcome = dict(outcome)
        persisted_outcome["campaign_id"] = handle.campaign_id
        persisted_outcome["batch_id"] = batch_id
        _atomic_json(attempt.path / "state_snapshot.json", snapshot)
        _atomic_json(attempt.path / "critic_report.json", report)
        _atomic_json(attempt.path / "outcome.json", persisted_outcome)
        status.update({"status": "COMPLETED", "completed_at": _utc_now()})
        _atomic_json(attempt.path / "status.json", status)

        iteration_dir = attempt.path.parents[1]
        completion = {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": handle.campaign_id,
            "batch_id": batch_id,
            "iteration": attempt.iteration,
            "attempt_id": attempt.attempt_id,
            "candidate_id": report.get("candidate_id"),
            "decision": report.get("decision"),
            "rubric_version": report.get("rubric_version"),
            "critic_system_version": report.get("critic_system_version"),
            "knowledge_inputs": _json_ready(
                persisted_outcome.get("knowledge_inputs") or {}
            ),
            "selected_template_ids": _json_ready(
                persisted_outcome.get("selected_template_ids") or []
            ),
            "completed_at": _utc_now(),
        }
        # This marker is the sole commit point. Derived Campaign memory can be
        # replayed from the committed attempt if the following write is lost.
        _atomic_json(iteration_dir / "COMPLETED.json", completion)
        try:
            memory = self.reconcile_content_memory(handle)
            _atomic_json(
                iteration_dir / "CONTENT_MEMORY_APPLIED.json",
                {
                    "schema_version": CONTENT_MEMORY_SCHEMA_VERSION,
                    "event_id": f"{handle.campaign_id}:{attempt.iteration}",
                    "revision": memory.get("revision", 0),
                    "digest": memory.get("digest"),
                },
            )
        except OSError:
            # The iteration is already committed; startup reconciliation is the
            # crash-safe repair path for this derived materialized view.
            pass

        batch = dict(loop_state.get("batch") or self.load_batch(handle, batch_id))
        committed = set(batch.get("committed_iteration_ids") or [])
        committed.add(attempt.iteration)
        batch["committed_iteration_ids"] = sorted(int(value) for value in committed)
        batch["completed_iterations"] = len(batch["committed_iteration_ids"])
        batch["end_iteration"] = max(batch["committed_iteration_ids"])
        reached_target = batch["completed_iterations"] >= int(
            batch.get("target_iterations", 1)
        )
        if reached_target:
            batch["status"] = "COMPLETED"
            batch.setdefault("completed_at", _utc_now())
        self.save_batch(handle, batch, complete=reached_target)
        loop_state["batch"] = dict(batch)
        loop_state["active_batch"] = dict(batch)
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
        for field in self.ITERATION_SNAPSHOT_FIELDS:
            if field in fields:
                state[field] = fields[field]
        return True
