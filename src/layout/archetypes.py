"""Global, evidence-backed runtime layout archetypes.

Seed families remain code-owned grammars. Accepted generated variants are stored
as derived archetypes; they never modify source files and never contain paper
text or visual assets. Cross-paper use is allowed only after promotion.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


ARCHETYPE_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class _RegistryLock:
    _thread_lock = threading.RLock()

    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream = None

    def __enter__(self):
        self._thread_lock.acquire()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.stream is not None:
            if fcntl is not None:
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
        self._thread_lock.release()


class LayoutArchetypeRegistry:
    """Persist accepted geometry variants and promote reusable structures."""

    def __init__(self, storage_root: Path, config: Dict[str, Any]) -> None:
        self.config = config
        self.root = Path(storage_root) / "layout_archetypes"
        self.index_path = self.root / "index.json"
        self.lock_path = self.root / ".lock"

    def _empty(self) -> Dict[str, Any]:
        return {
            "schema_version": ARCHETYPE_SCHEMA_VERSION,
            "revision": 0,
            "archetypes": [],
            "applied_event_ids": [],
            "updated_at": _utc_now(),
        }

    def _load(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return self._empty()
        with self.index_path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("archetypes"), list
        ):
            raise ValueError("Corrupt runtime layout-archetype index")
        if int(payload.get("schema_version", 0)) != ARCHETYPE_SCHEMA_VERSION:
            raise ValueError("Unsupported runtime layout-archetype schema")
        return payload

    @staticmethod
    def _blueprint(layout_spec: Dict[str, Any]) -> Dict[str, Any]:
        zones = []
        for raw in layout_spec.get("zones") or []:
            zones.append({
                "zone_id": str(raw["zone_id"]),
                "x": round(float(raw["x"]), 6),
                "y": round(float(raw["y"]), 6),
                "width": round(float(raw["width"]), 6),
                "height": round(float(raw["height"]), 6),
                "role": str(raw.get("role") or "support"),
                "capacity": max(1, int(raw.get("capacity", 1))),
            })
        if not zones:
            raise ValueError("Cannot register an archetype without zones")
        return {
            "family_id": str(layout_spec["family_id"]),
            "zones": zones,
            "primary_anchor_zone": layout_spec.get("primary_anchor_zone"),
            "reading_zone_order": [item["zone_id"] for item in zones],
        }

    def record_accepted(
        self,
        *,
        event_id: str,
        paper_id: str,
        paper_profile: Dict[str, Any],
        candidate_id: str,
        layout_spec: Dict[str, Any],
        design_score: Optional[float],
        template_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        blueprint = self._blueprint(layout_spec)
        fingerprint = _fingerprint(blueprint)
        settings = self.config.get("explore_layout", {})
        with _RegistryLock(self.lock_path):
            index = self._load()
            prior_record = next(
                (
                    item
                    for item in index["archetypes"]
                    if any(
                        evidence.get("event_id") == event_id
                        for evidence in item.get("evidence") or []
                    )
                ),
                None,
            )
            if prior_record is not None:
                if prior_record.get("geometry_fingerprint") != fingerprint:
                    raise ValueError(
                        "Layout archetype event was replayed with different geometry"
                    )
                return deepcopy(prior_record)
            record = next(
                (
                    item for item in index["archetypes"]
                    if item.get("geometry_fingerprint") == fingerprint
                ),
                None,
            )
            if record is None:
                record = {
                    "schema_version": ARCHETYPE_SCHEMA_VERSION,
                    "archetype_id": f"arc_{fingerprint[:16]}",
                    "family_id": blueprint["family_id"],
                    "geometry_fingerprint": fingerprint,
                    "blueprint": blueprint,
                    "status": "candidate",
                    "evidence": [],
                    "created_at": _utc_now(),
                }
                index["archetypes"].append(record)
            record["evidence"].append({
                "event_id": event_id,
                "paper_id": str(paper_id),
                "profile_key": str(
                    paper_profile.get("profile_key") or "unknown"
                ),
                "candidate_id": str(candidate_id),
                "template_id": str(template_id) if template_id else None,
                "design_score": (
                    float(design_score)
                    if design_score is not None else None
                ),
                "accepted_at": _utc_now(),
            })
            papers = {
                item["paper_id"] for item in record["evidence"]
                if item.get("paper_id")
            }
            profiles = {
                item["profile_key"] for item in record["evidence"]
                if item.get("profile_key")
            }
            record["accepted_poster_count"] = len(record["evidence"])
            record["distinct_paper_count"] = len(papers)
            record["distinct_profile_count"] = len(profiles)
            scored = [
                float(item["design_score"])
                for item in record["evidence"]
                if item.get("design_score") is not None
            ]
            record["mean_design_score"] = (
                round(sum(scored) / len(scored), 4)
                if scored else None
            )
            if (
                len(papers) >= int(
                    settings.get("promote_archetype_min_distinct_papers", 2)
                )
                and len(record["evidence"]) >= int(
                    settings.get(
                        "promote_archetype_min_accepted_posters", 3
                    )
                )
            ):
                record["status"] = "promoted"
                record.setdefault("promoted_at", _utc_now())
            record["updated_at"] = _utc_now()
            applied = list(index.get("applied_event_ids") or [])
            applied.append(event_id)
            index["applied_event_ids"] = applied[-10000:]
            index["revision"] = int(index.get("revision", 0)) + 1
            index["updated_at"] = _utc_now()
            _atomic_json(self.index_path, index)
            return deepcopy(record)

    def retrieve(
        self,
        *,
        family_id: str,
        paper_id: str,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        with _RegistryLock(self.lock_path):
            index = self._load()
        candidates = []
        for record in index["archetypes"]:
            if record.get("family_id") != family_id:
                continue
            source_papers = {
                str(item.get("paper_id"))
                for item in record.get("evidence") or []
            }
            if (
                record.get("status") != "promoted"
                and str(paper_id) not in source_papers
            ):
                continue
            candidates.append(record)
        candidates.sort(
            key=lambda item: (
                item.get("status") == "promoted",
                float(item.get("mean_design_score") or 0.0),
                int(item.get("distinct_paper_count", 0)),
                int(item.get("accepted_poster_count", 0)),
                str(item.get("archetype_id")),
            ),
            reverse=True,
        )
        result = []
        for record in candidates[: max(0, int(limit))]:
            blueprint = record["blueprint"]
            result.append({
                "variant_id": record["archetype_id"],
                "variant_label": "runtime_archetype",
                "geometry_fingerprint": record[
                    "geometry_fingerprint"
                ][:16],
                "zones": deepcopy(blueprint["zones"]),
                "mutation_trace": ["runtime_archetype"],
                "generation_method": "accepted_runtime_archetype",
                "archetype_status": record.get("status"),
            })
        return result
