"""File-backed accepted-poster archive and diverse template registry."""

import hashlib
import json
import os
import random
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.config.critic_config import load_critic_config
from src.layout.families import (
    LAYOUT_ENGINE_SCHEMA_VERSION,
    LayoutFamilyRegistry,
    valid_family_topology,
)
from src.state.poster_state import PosterState
from src.templates.scoring import TEMPLATE_RUBRIC_VERSION, score_template
from src.templates.seats import rebuild_retrieval_seats

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


TEMPLATE_LIBRARY_SCHEMA_VERSION = 11
VALIDATION_TRIAL_SCHEMA_VERSION = 8


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()


class _FileLock:
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


def build_paper_profile(state: PosterState) -> Dict[str, Any]:
    """Build a content-only profile for template applicability."""

    verified = state.get("verified_claims") or {}
    claims = verified.get("claims", [])
    narrative = state.get("narrative_plan") or {}
    sections = narrative.get("sections", [])
    visual_count = len(state.get("images") or {}) + len(state.get("tables") or {})
    claim_count = len(claims)
    density = "low" if claim_count <= 8 else "medium" if claim_count <= 16 else "high"
    kind = "visual_heavy" if visual_count >= 4 else "text_heavy" if visual_count <= 1 else "balanced"
    searchable = " ".join(
        str(section.get("title") or section.get("section_title") or section.get("section_id") or "")
        for section in sections
        if isinstance(section, dict)
    ).lower()
    flags = set()
    if any(token in searchable for token in ("method", "approach", "pipeline", "framework")):
        flags.update({"method_heavy", "process"})
    if any(token in searchable for token in ("compar", "versus", "ablation", "baseline")):
        flags.add("comparison")
    if any(token in searchable for token in ("timeline", "stage", "phase", "longitudinal")):
        flags.update({"timeline", "stages"})
    if visual_count >= 4:
        flags.add("results_heavy")
    return {
        "profile_key": f"{kind}:{density}",
        "kind": kind,
        "content_density": density,
        "visual_count": visual_count,
        "claim_count": claim_count,
        "section_count": len(sections),
        "design_flags": sorted(flags),
    }


class TemplateDistiller:
    """Strip paper content and retain a normalized layout pattern."""


    @staticmethod
    def _column(x: float, poster_width: float) -> str:
        normalized = x / poster_width if poster_width else 0.0
        return "left" if normalized < 1 / 3 else "middle" if normalized < 2 / 3 else "right"

    @staticmethod
    def _ratio(value: Any, denominator: float) -> float:
        try:
            return round(float(value) / denominator, 4) if denominator else 0.0
        except (TypeError, ValueError):
            return 0.0

    def distill(
        self,
        state: PosterState,
        critic_report: Dict[str, Any],
        paper_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        if state.get("generation_route") == "standalone_classic":
            raise ValueError(
                "Standalone classic posters cannot enter loop template knowledge"
            )
        layout = state.get("styled_layout") or state.get("design_layout") or []
        width = float(state.get("poster_width", 1.0))
        height = float(state.get("poster_height", 1.0))
        column_counts = {"left": 0, "middle": 0, "right": 0}
        visual_counts = {"left": 0, "middle": 0, "right": 0}
        occupied_area = 0.0
        blueprint: List[Dict[str, Any]] = []
        roles = {
            "title", "section_container", "section_title", "text", "visual",
            "conf_logo", "aff_logo",
        }
        for element in layout:
            role = element.get("type")
            if role not in roles:
                continue
            x = float(element.get("x", 0.0))
            y = float(element.get("y", 0.0))
            element_width = float(element.get("width", 0.0))
            element_height = float(element.get("height", 0.0))
            column = self._column(x + element_width / 2, width)
            if role == "section_container":
                column_counts[column] += 1
            if role == "visual":
                visual_counts[column] += 1
            if role not in {"section_container", "section_title"}:
                occupied_area += max(0.0, element_width * element_height)
            blueprint.append({
                "role": role,
                "column": column,
                "zone": element.get("zone_id"),
                "x": self._ratio(x, width),
                "y": self._ratio(y, height),
                "width": self._ratio(element_width, width),
                "height": self._ratio(element_height, height),
                "font_size_ratio": self._ratio(element.get("font_size", 0), 100.0),
            })

        visual_count = sum(visual_counts.values())
        section_count = sum(column_counts.values())
        primary_visual_column = max(visual_counts, key=visual_counts.get) if visual_count else "none"
        occupied_ratio = min(1.0, occupied_area / (width * height)) if width and height else 0.0
        section_fit = state.get("section_fit_analysis") or {}
        raw_fit_sections = section_fit.get("sections", {})
        fit_sections = (
            raw_fit_sections.values()
            if isinstance(raw_fit_sections, dict)
            else raw_fit_sections
        )
        fit_values = [
            float(item.get("utilization", item.get("utilization_ratio", 0.0)))
            for item in fit_sections
            if isinstance(item, dict)
        ]
        mean_section_utilization = (
            sum(fit_values) / len(fit_values) if fit_values else 0.0
        )
        signature = {
            "section_count": section_count,
            "visual_count": visual_count,
            "left_sections": column_counts["left"],
            "middle_sections": column_counts["middle"],
            "right_sections": column_counts["right"],
            "primary_visual_column": primary_visual_column,
            "occupied_ratio": round(occupied_ratio, 4),
            "mean_section_utilization": round(mean_section_utilization, 4),
        }
        vector = [
            min(section_count / 8.0, 1.5), min(visual_count / 6.0, 1.5),
            min(column_counts["left"] / 4.0, 1.5),
            min(column_counts["middle"] / 4.0, 1.5),
            min(column_counts["right"] / 4.0, 1.5),
            {"none": 0.0, "left": 0.25, "middle": 0.5, "right": 0.75}.get(primary_visual_column, 0.0),
            occupied_ratio,
            mean_section_utilization,
        ]
        layout_spec = state.get("layout_spec") or {}
        family = str(layout_spec.get("family_id") or self._family(signature))
        signature["layout_family"] = family
        signature["zone_count"] = len(layout_spec.get("zones") or [])
        signature_schema_version = 1
        if (
            state.get("generation_route") == "optimization_family"
            and layout_spec.get("zones")
        ):
            # The loop's duplicate/retrieval signature must describe actual
            # zones, not project every family onto three imaginary columns.
            zones = layout_spec["zones"]
            areas = [
                float(zone["width"]) * float(zone["height"])
                for zone in zones
            ]
            loads = [len(zone.get("section_ids") or []) for zone in zones]
            count = max(1, len(zones))
            mean_load = sum(loads) / count
            anchor = str(layout_spec.get("primary_anchor_zone") or "")
            anchor_area = next((
                areas[index] for index, zone in enumerate(zones)
                if str(zone.get("zone_id")) == anchor
            ), 0.0)
            centers = [
                (
                    float(zone["x"]) + float(zone["width"]) / 2,
                    float(zone["y"]) + float(zone["height"]) / 2,
                )
                for zone in zones
            ]
            vector = [
                min(section_count / 8.0, 1.5),
                min(visual_count / 6.0, 1.5),
                occupied_ratio,
                mean_section_utilization,
                min(count / 8.0, 1.5),
                sum(bool(load) for load in loads) / count,
                max(areas),
                min(areas),
                sum(areas) / count,
                min(max(loads) / 4.0, 1.5),
                min(sum((load - mean_load) ** 2 for load in loads) / count / 4.0, 1.5),
                anchor_area,
                sum(area >= 0.40 for area in areas) / count,
                sum(x * load for (x, _), load in zip(centers, loads)) / max(1, section_count),
                sum(y * load for (_, y), load in zip(centers, loads)) / max(1, section_count),
            ]
            signature_schema_version = 2
        canonical = json.dumps({"blueprint": blueprint, "family": family}, sort_keys=True, separators=(",", ":"))
        paper_id = (state.get("loop_state") or {}).get(
            "paper_id", state.get("poster_name", "unknown")
        )
        candidate = state.get("current_candidate") or {}
        iteration_context = state.get("iteration_context") or {}
        template = {
            "schema_version": TEMPLATE_LIBRARY_SCHEMA_VERSION,
            "template_id": f"tpl_{uuid.uuid4().hex[:16]}",
            # New layouts must prove themselves across multiple papers before
            # becoming validated. Legacy paper_specific entries remain usable
            # only for their source paper.
            "status": "paper_specific",
            "template_level": 0,
            "validation_status": "pending",
            "family": family,
            "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "created_at": _utc_now(),
            "source_candidate_id": candidate.get("candidate_id"),
            "source_campaign_id": iteration_context.get("campaign_id"),
            "source_batch_id": iteration_context.get("batch_id"),
            "source_iteration": iteration_context.get("iteration"),
            "source_lineage_id": iteration_context.get("lineage_id"),
            "source_mode": iteration_context.get("portfolio_mode"),
            "source_generation_route": state.get("generation_route"),
            "source_layout_engine_schema_version": LAYOUT_ENGINE_SCHEMA_VERSION,
            "source_parent_candidate_id": iteration_context.get(
                "parent_candidate_id"
            ),
            "lineage_provenance_status": (
                "complete"
                if iteration_context.get("campaign_id")
                and iteration_context.get("lineage_id")
                else "partial"
            ),
            "source_aspect_ratio": round(width / height, 6) if height else None,
            "zone_topology": {
                "schema_version": 1,
                "family_id": family,
                "primary_anchor_zone": layout_spec.get("primary_anchor_zone"),
                "zones": [
                    {key: zone.get(key) for key in
                     ("zone_id", "x", "y", "width", "height", "role", "capacity")}
                    for zone in layout_spec.get("zones", [])
                ],
            },
            "source_paper_id": paper_id,
            "source_profile": paper_profile.get("profile_key"),
            "quality_vector": critic_report.get("dimension_scores", {}),
            "overall_score": critic_report.get("overall_score", 0.0),
            "applicability": {
                "content_density": [paper_profile.get("content_density")],
                "preferred_visual_count": [max(0, paper_profile.get("visual_count", 0) - 1), paper_profile.get("visual_count", 0) + 2],
                "preferred_section_count": [max(1, paper_profile.get("section_count", 0) - 2), paper_profile.get("section_count", 0) + 2],
            },
            "layout_signature": signature,
            "signature_vector": vector,
            "signature_schema_version": signature_schema_version,
            "layout_principles": self._principles(
                family, signature, layout_spec=layout_spec
            ),
            "normalized_blueprint": blueprint,
            "density_targets": {
                "ideal_section_utilization": [0.95, 1.0],
                "observed_mean_section_utilization": round(
                    mean_section_utilization, 4
                ),
                "gaps_acceptable": bool(
                    section_fit.get("gaps_acceptable", False)
                ),
            },
            "usage": {
                "times_retrieved": 0,
                "last_used_iteration": None,
                "last_used_by_campaign": {},
                "successful_papers": [paper_id],
                "successful_profiles": [paper_profile.get("profile_key")],
            },
            "validation": {
                "required": True,
                "status": "pending",
                "source_replay_completed": False,
                "distinct_validation_papers": [],
                "distinct_validation_profiles": [],
                "successful_papers": [paper_id],
                "successful_profiles": [paper_profile.get("profile_key")],
                "cross_paper_success_profiles": [],
                "failed_papers": [],
                "profile_outcomes": {},
                "paper_trials": {},
                "source_replay_attempt": None,
                "blocked_reason": None,
                "events": 0,
                "successful_events": 0,
                "failed_events": 0,
                "last_validated_at": None,
                "next_target": "source_replay",
            },
        }
        template["template_evaluation"] = score_template(template, critic_report)
        template["template_design_score"] = template["template_evaluation"]["score"]
        return template

    @staticmethod
    def _family(signature: Dict[str, Any]) -> str:
        counts = [signature["left_sections"], signature["middle_sections"], signature["right_sections"]]
        if signature["visual_count"] >= 3:
            return "visual_grid"
        if signature["primary_visual_column"] == "middle":
            return "visual_center"
        if max(counts, default=0) - min(counts, default=0) <= 1:
            return "balanced_three_column"
        if signature["left_sections"] == max(counts, default=0):
            return "left_narrative"
        if signature["right_sections"] == max(counts, default=0):
            return "right_results"
        return "adaptive_three_column"

    @staticmethod
    def _principles(
        family: str,
        signature: Dict[str, Any],
        *,
        layout_spec: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        principles = {
            "visual_grid": "Distribute several evidence visuals as a deliberate result grid.",
            "visual_center": "Use the middle column as the primary visual anchor.",
            "balanced_three_column": "Keep section load broadly balanced across all three columns.",
            "left_narrative": "Let the left column establish the narrative before result-heavy columns.",
            "right_results": "Build toward a result- or conclusion-heavy right column.",
            "adaptive_three_column": "Use an intentionally asymmetric three-column rhythm.",
        }
        family_description = (layout_spec or {}).get("family_description")
        return [
            principles.get(
                family,
                str(family_description or "Preserve the registered family relationships while adapting module sizes."),
            ),
            f"Target about {signature['section_count']} sections and {signature['visual_count']} visuals only when appropriate.",
            "Treat normalized coordinates as flexible proportions, not fixed positions.",
        ]


class TemplateLibrary:
    """Registry with family diversity, cooldown, and cross-paper promotion."""

    def __init__(self, root: Path, config: Optional[Dict[str, Any]] = None) -> None:
        self.root = Path(root)
        self.config = config or load_critic_config()
        self.index_path = self.root / "template_library" / "index.json"
        self.outcomes_path = self.root / "template_library" / "usage_outcomes.jsonl"
        self.validation_queue_path = (
            self.root / "template_library" / "validation_queue.json"
        )
        self.lock_path = self.root / "template_library" / ".registry.lock"

    @staticmethod
    def _semantic_index(index: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value for key, value in index.items()
            if key not in {
                "knowledge_revision",
                "knowledge_digest",
                "knowledge_updated_at",
            }
        }

    @classmethod
    def _index_digest(cls, index: Dict[str, Any]) -> str:
        canonical = json.dumps(
            cls._semantic_index(index),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _stamp_loaded_index(
        cls,
        index: Dict[str, Any],
        *,
        stored_digest: Optional[str],
        stored_revision: int,
    ) -> Dict[str, Any]:
        digest = cls._index_digest(index)
        revision = max(0, int(stored_revision))
        if stored_digest != digest:
            revision += 1
        index["knowledge_revision"] = revision
        index["knowledge_digest"] = digest
        return index

    def _write_index(
        self,
        index: Dict[str, Any],
        *,
        previous_digest: Optional[str],
    ) -> None:
        digest = self._index_digest(index)
        revision = max(0, int(index.get("knowledge_revision", 0)))
        if previous_digest != digest:
            revision += 1
        index["knowledge_revision"] = revision
        index["knowledge_digest"] = digest
        index["knowledge_updated_at"] = _utc_now()
        _atomic_json(self.index_path, index)

    def knowledge_snapshot(
        self, index: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        current = index if index is not None else self._load()
        return {
            "schema_version": int(
                current.get("schema_version", TEMPLATE_LIBRARY_SCHEMA_VERSION)
            ),
            "revision": int(current.get("knowledge_revision", 0)),
            "digest": str(
                current.get("knowledge_digest")
                or self._index_digest(current)
            ),
            "template_count": len(current.get("templates") or []),
            "captured_at": _utc_now(),
        }

    def _read_validation_events(self) -> Dict[str, List[Dict[str, Any]]]:
        events_by_template: Dict[str, List[Dict[str, Any]]] = {}
        if not self.outcomes_path.is_file():
            return events_by_template
        seen = set()
        try:
            with self.outcomes_path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not event.get("validation_run"):
                        continue
                    key = str(event.get("event_id") or "legacy:{}:{}:{}:{}".format(
                        event.get("template_id"), event.get("paper_id"),
                        event.get("iteration"), line_number,
                    ))
                    if key in seen:
                        continue
                    seen.add(key)
                    event["_migration_event_id"] = key
                    events_by_template.setdefault(
                        str(event.get("template_id")), []
                    ).append(event)
        except OSError:
            return {}
        return events_by_template

    def _backfill_source_provenance(
        self, template: Dict[str, Any]
    ) -> None:
        """Recover direct Lineage provenance from its immutable poster bundle."""

        candidate_id = str(template.get("source_candidate_id") or "")
        context: Dict[str, Any] = {}
        if candidate_id and all(
            char.isalnum() or char in "_-" for char in candidate_id
        ):
            provenance_path = (
                self.root / "accepted_posters" / candidate_id
                / "provenance.json"
            )
            if provenance_path.is_file():
                try:
                    provenance = json.loads(
                        provenance_path.read_text(encoding="utf-8")
                    )
                    context = provenance.get("iteration_context") or {}
                except (OSError, json.JSONDecodeError):
                    context = {}
        mappings = {
            "source_campaign_id": "campaign_id",
            "source_batch_id": "batch_id",
            "source_iteration": "iteration",
            "source_lineage_id": "lineage_id",
            "source_mode": "portfolio_mode",
            "source_parent_candidate_id": "parent_candidate_id",
        }
        for destination, source in mappings.items():
            if template.get(destination) is None and context.get(source) is not None:
                template[destination] = context[source]
        if template.get("source_campaign_id") and template.get(
            "source_lineage_id"
        ):
            template["lineage_provenance_status"] = "complete"
        elif context:
            template["lineage_provenance_status"] = "partial"
        else:
            template.setdefault(
                "lineage_provenance_status", "unavailable_legacy"
            )

    def _migrate_validation_trials(
        self,
        template: Dict[str, Any],
        events: Sequence[Dict[str, Any]],
    ) -> None:
        validation = self._ensure_validation(template)
        trials = validation.setdefault("paper_trials", {})
        source_paper = str(template.get("source_paper_id") or "")
        maximum = int(
            self.config["templates"].get(
                "max_cross_paper_validation_attempts", 3
            )
        )
        for event in sorted(
            events,
            key=lambda item: (
                int(item.get("iteration", 0) or 0),
                str(item.get("timestamp") or ""),
                str(item.get("_migration_event_id") or ""),
            ),
        ):
            paper_id = str(event.get("paper_id") or "")
            if not paper_id:
                continue
            if paper_id == source_paper:
                validation["source_replay_completed"] = True
                continue
            trial = trials.setdefault(paper_id, {
                "profile_key": str(event.get("profile_key") or "legacy_unknown"),
                "target": "cross_paper",
                "status": "retry_pending",
                "attempts_completed": 0,
                "successful": False,
                "attempts": [],
            })
            if trial.get("status") in {"passed", "failed_final", "blocked"}:
                continue
            event_id = str(event.get("_migration_event_id") or "")
            if any(str(item.get("event_id")) == event_id for item in trial.get("attempts", [])):
                continue
            passed = bool(event.get("accepted") and event.get("transfer_verified"))
            attempt = {
                "event_id": event_id,
                "campaign_id": event.get("campaign_id"),
                "iteration": int(event.get("iteration", 0) or 0),
                "score": float(event.get("score", 0.0) or 0.0),
                "poster_accepted": bool(event.get("accepted")),
                "transfer_verified": bool(event.get("transfer_verified")),
                "result": "passed" if passed else (
                    "strict_transfer_failed"
                    if event.get("accepted") else "poster_rejected"
                ),
                "recorded_at": event.get("timestamp"),
                "migrated": True,
            }
            trial.setdefault("attempts", []).append(attempt)
            trial["attempts_completed"] = len(trial["attempts"])
            if passed:
                trial["status"] = "passed"
                trial["successful"] = True
            elif trial["attempts_completed"] >= maximum:
                trial["status"] = "failed_final"

        successful = set(validation.get("successful_papers", [])) - {source_paper}
        failed = set(validation.get("failed_papers", [])) - successful
        profiles = list(validation.get("cross_paper_success_profiles", []))
        fallback_profile = profiles[0] if len(profiles) == 1 else "legacy_unknown"
        for paper_id in successful:
            trials.setdefault(str(paper_id), {
                "profile_key": fallback_profile,
                "target": "cross_paper",
                "status": "passed",
                "attempts_completed": 1,
                "successful": True,
                "attempts": [],
                "migrated_without_event": True,
            })
        for paper_id in failed:
            trials.setdefault(str(paper_id), {
                "profile_key": "legacy_unknown",
                "target": "cross_paper",
                "status": "retry_pending",
                "attempts_completed": 1,
                "successful": False,
                "attempts": [],
                "migrated_without_event": True,
            })
        for paper_id in validation.get("distinct_validation_papers", []):
            trials.setdefault(str(paper_id), {
                "profile_key": "legacy_unknown",
                "target": "cross_paper",
                "status": "retry_pending",
                "attempts_completed": 0,
                "successful": False,
                "attempts": [],
                "legacy_outcome_unresolved": True,
            })
        validation["migration_status"] = "schema_v7_trials_reconstructed"
        self._refresh_validation_aggregates(template)

    def _load(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            index = {
                "schema_version": TEMPLATE_LIBRARY_SCHEMA_VERSION,
                "templates": [],
                "knowledge_revision": 0,
            }
            index["knowledge_digest"] = self._index_digest(index)
            return index
        try:
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Template index exists but cannot be read: {self.index_path}"
            ) from exc
        if not isinstance(index, dict) or not isinstance(index.get("templates"), list):
            raise ValueError(
                f"Template index has an invalid structure: {self.index_path}"
            )
        stored_schema = int(index.get("schema_version", 0))
        stored_digest = index.get("knowledge_digest")
        stored_revision = int(index.get("knowledge_revision", 0) or 0)
        validation_events = (
            self._read_validation_events()
            if stored_schema < VALIDATION_TRIAL_SCHEMA_VERSION else {}
        )
        for template in index["templates"]:
            if not isinstance(template, dict):
                raise ValueError(
                    f"Template index contains an invalid record: {self.index_path}"
                )
            self._ensure_validation(template)
            self._backfill_source_provenance(template)
            if stored_schema < VALIDATION_TRIAL_SCHEMA_VERSION:
                self._migrate_validation_trials(
                    template,
                    validation_events.get(str(template.get("template_id")), []),
                )
            validation = self._ensure_validation(template)
            validation["blocked_reason"] = self._topology_block_reason(template)
            if (
                VALIDATION_TRIAL_SCHEMA_VERSION < stored_schema
                < TEMPLATE_LIBRARY_SCHEMA_VERSION
            ):
                self._refresh_validation_aggregates(template)
            evaluation = template.get("template_evaluation") or {}
            if evaluation.get("rubric_version") != TEMPLATE_RUBRIC_VERSION:
                report = {}
                candidate_id = str(template.get("source_candidate_id") or "")
                if candidate_id and all(
                    char.isalnum() or char in "_-" for char in candidate_id
                ):
                    report_path = (
                        self.root / "accepted_posters" / candidate_id
                        / "critic_report.json"
                    )
                    if report_path.is_file():
                        try:
                            report = json.loads(
                                report_path.read_text(encoding="utf-8")
                            )
                        except (OSError, json.JSONDecodeError):
                            report = {}
                template["template_evaluation"] = score_template(template, report)
                template["template_design_score"] = template[
                    "template_evaluation"
                ]["score"]
            template["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
        rebuild_retrieval_seats(index, self.config["templates"])
        index["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
        return self._stamp_loaded_index(
            index,
            stored_digest=(
                str(stored_digest) if stored_digest is not None else None
            ),
            stored_revision=stored_revision,
        )

    def validation_summaries(
        self,
        template_ids: Iterable[str],
        *,
        paper_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Read current validation levels and per-paper retry state."""
        identifiers = set(template_ids)
        summaries = {}
        maximum = int(
            self.config["templates"].get(
                "max_cross_paper_validation_attempts", 3
            )
        )
        for item in self._load().get("templates", []):
            if item.get("template_id") not in identifiers:
                continue
            validation = self._ensure_validation(item)
            trial = (validation.get("paper_trials") or {}).get(
                str(paper_id), {}
            ) if paper_id is not None else {}
            summaries[str(item["template_id"])] = {
                "level": int(item.get("template_level", 0)),
                "status": str(item.get("validation_status", "pending")),
                "trial_status": trial.get("status"),
                "attempts_completed": int(
                    trial.get("attempts_completed", 0) or 0
                ),
                "max_attempts": maximum,
                "blocked_reason": validation.get("blocked_reason"),
            }
        return summaries

    def register(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Store every accepted template; levels and diversity gate retrieval only."""
        with _FileLock(self.lock_path):
            index = self._load()
            previous_digest = str(index.get("knowledge_digest") or "")
            template["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
            usage = template.setdefault("usage", {})
            usage.setdefault("last_used_by_campaign", {})
            validation = self._ensure_validation(template)
            validation["blocked_reason"] = self._topology_block_reason(template)
            evaluation = template.get("template_evaluation") or {}
            if evaluation.get("rubric_version") != TEMPLATE_RUBRIC_VERSION:
                template["template_evaluation"] = score_template(template)
                template["template_design_score"] = template["template_evaluation"]["score"]
            for existing in index["templates"]:
                if existing.get("template_id") == template.get("template_id"):
                    self._write_validation_queue(index)
                    return {"registered": False, "reason": "already_registered", "template": existing}
                if (template.get("source_candidate_id") and
                        existing.get("source_candidate_id") == template.get("source_candidate_id")):
                    self._write_validation_queue(index)
                    return {"registered": False, "reason": "candidate_already_registered", "template": existing}
            index["templates"].append(template)
            rebuild_retrieval_seats(index, self.config["templates"])
            self._write_index(index, previous_digest=previous_digest)
            self._write_validation_queue(index)
            return {
                "registered": True,
                "reason": "stored_" + str(template["retrieval_reason"]),
                "template": template,
            }


    def validation_topology(self, template_id: str) -> Dict[str, Any]:
        """Return exact topology to the compiler, never to Planner."""
        for template in self._load().get("templates", []):
            if template.get("template_id") == template_id:
                return dict(template.get("zone_topology") or {})
        return {}

    def validation_identity(
        self, template_id: str
    ) -> Dict[str, Optional[str]]:
        """Snapshot immutable identity used to guard a validation commit."""
        for template in self._load().get("templates", []):
            if template.get("template_id") != template_id:
                continue
            topology = template.get("zone_topology") or {}
            topology_sha256 = hashlib.sha256(
                json.dumps(
                    topology, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            return {
                "template_id": str(template_id),
                "fingerprint": template.get("fingerprint"),
                "topology_sha256": topology_sha256,
            }
        return {}


    @staticmethod
    def _ensure_validation(template: Dict[str, Any]) -> Dict[str, Any]:
        validation = template.get("validation")
        if not isinstance(validation, dict):
            validation = {}
            template["validation"] = validation
        validation.setdefault("required", True)
        validation.setdefault("status", "pending")
        validation.setdefault("source_replay_completed", False)
        validation.setdefault("distinct_validation_papers", [])
        validation.setdefault("distinct_validation_profiles", [])
        validation.setdefault("successful_papers", [])
        validation.setdefault("successful_profiles", [])
        validation.setdefault("cross_paper_success_profiles", [])
        validation.setdefault("failed_papers", [])
        validation.setdefault("profile_outcomes", {})
        validation.setdefault("paper_trials", {})
        validation.setdefault("source_replay_attempt", None)
        validation.setdefault("blocked_reason", None)
        validation.setdefault("events", 0)
        validation.setdefault("successful_events", 0)
        validation.setdefault("failed_events", 0)
        validation.setdefault("last_validated_at", None)
        validation.setdefault("next_target", "source_replay")
        template.setdefault("template_level", 0)
        template.setdefault("validation_status", validation["status"])
        source_paper = template.get("source_paper_id")
        source_profile = template.get("source_profile")
        if source_paper and source_paper not in validation["successful_papers"]:
            validation["successful_papers"].append(source_paper)
        if source_profile and source_profile not in validation["successful_profiles"]:
            validation["successful_profiles"].append(source_profile)
        return validation

    def _topology_block_reason(self, template: Dict[str, Any]) -> Optional[str]:
        topology = template.get("zone_topology")
        if not isinstance(topology, dict) or not topology.get("zones"):
            return "missing_strict_topology"
        family = str(template.get("family") or "")
        if str(topology.get("family_id") or "") != family:
            return "topology_family_mismatch"
        enabled = set(self.config.get("layout_families", {}).get("enabled", []))
        if enabled and family not in enabled:
            return "layout_family_not_enabled"
        try:
            source_engine_version = int(
                template.get("source_layout_engine_schema_version") or 0
            )
        except (TypeError, ValueError):
            return "invalid_source_layout_engine_version"
        registry = LayoutFamilyRegistry()
        if (
            family in registry.ids()
            and source_engine_version >= LAYOUT_ENGINE_SCHEMA_VERSION
        ):
            if not valid_family_topology(
                registry.get(family), topology.get("zones") or []
            ):
                return "topology_violates_family_grammar"
        if (
            family == "classic_three_column"
            and template.get("source_mode") in {"explore", "improve"}
            and template.get("source_layout_engine_schema_version") is None
        ):
            # Earlier loop-classic candidates could use a Balancer geometry
            # different from their family zones. Preserve, but do not validate.
            return "legacy_classic_geometry_unverified"
        zone_ids = []
        for zone in topology.get("zones") or []:
            if not isinstance(zone, dict) or not zone.get("zone_id"):
                return "invalid_topology_zone"
            zone_ids.append(str(zone["zone_id"]))
            try:
                x = float(zone.get("x"))
                y = float(zone.get("y"))
                width = float(zone.get("width"))
                height = float(zone.get("height"))
            except (TypeError, ValueError):
                return "invalid_topology_geometry"
            if (x < 0 or y < 0 or width <= 0 or height <= 0
                    or x + width > 1.0001 or y + height > 1.0001):
                return "invalid_topology_geometry"
        if len(zone_ids) != len(set(zone_ids)):
            return "duplicate_topology_zone"
        anchor = topology.get("primary_anchor_zone")
        if anchor is not None and str(anchor) not in set(zone_ids):
            return "invalid_primary_anchor"
        return None

    def _write_validation_queue(self, index: Dict[str, Any]) -> None:
        queue = []
        for template in index.get("templates", []):
            validation = self._ensure_validation(template)
            if not validation.get("required", True):
                continue
            blocked_reason = self._topology_block_reason(template)
            validation["blocked_reason"] = blocked_reason
            trials = validation.get("paper_trials") or {}
            queue.append({
                "template_id": template.get("template_id"),
                "family": template.get("family"),
                "template_level": int(template.get("template_level", 0)),
                "validation_status": validation.get("status"),
                "next_target": validation.get("next_target"),
                "source_paper_id": template.get("source_paper_id"),
                "blocked_reason": blocked_reason,
                "retry_pending_papers": sum(
                    1 for trial in trials.values()
                    if trial.get("status") == "retry_pending"
                ),
                "distinct_validation_papers": len(
                    validation.get("distinct_validation_papers", [])
                ),
                "distinct_validation_profiles": len(
                    validation.get("distinct_validation_profiles", [])
                ),
            })
        _atomic_json(self.validation_queue_path, {
            "schema_version": 2,
            "updated_at": _utc_now(),
            "pending": queue,
        })

    def validation_candidate_ids(
        self,
        *,
        paper_id: str,
        paper_profile: Dict[str, Any],
    ) -> List[str]:
        return [
            str(item.get("template_id"))
            for item in self._validation_candidates(paper_id, paper_profile)
            if item.get("template_id")
        ]

    def validation_blocked_candidates(
        self,
        *,
        paper_profile: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Describe topology-blocked tasks without consuming attempts."""
        visual_count = int(paper_profile.get("visual_count", 0))
        blocked = []
        for template in self._load().get("templates", []):
            validation = self._ensure_validation(template)
            if not validation.get("required", True):
                continue
            visual_range = (template.get("applicability") or {}).get(
                "preferred_visual_count", [0, 10**9]
            )
            if not visual_range[0] <= visual_count <= visual_range[1]:
                continue
            reason = self._topology_block_reason(template)
            if reason:
                blocked.append({
                    "template_id": str(template.get("template_id") or "unknown"),
                    "reason": reason,
                })
        return blocked

    def has_validation_candidate(
        self,
        *,
        paper_id: str,
        paper_profile: Dict[str, Any],
        template_ids: Optional[Sequence[str]] = None,
    ) -> bool:
        return bool(self._validation_candidates(
            paper_id, paper_profile, template_ids=template_ids
        ))

    def _validation_candidates(
        self,
        paper_id: str,
        paper_profile: Dict[str, Any],
        *,
        template_ids: Optional[Sequence[str]] = None,
        index: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        visual_count = int(paper_profile.get("visual_count", 0))
        maximum = int(self.config["templates"].get(
            "max_cross_paper_validation_attempts", 3
        ))
        allowed = set(template_ids) if template_ids is not None else None
        candidates = []
        source_index = index if index is not None else self._load()
        for template in source_index.get("templates", []):
            if allowed is not None and template.get("template_id") not in allowed:
                continue
            validation = self._ensure_validation(template)
            if not validation.get("required", True):
                continue
            blocked_reason = self._topology_block_reason(template)
            validation["blocked_reason"] = blocked_reason
            if blocked_reason:
                continue
            visual_range = (template.get("applicability") or {}).get(
                "preferred_visual_count", [0, 10**9]
            )
            if not visual_range[0] <= visual_count <= visual_range[1]:
                continue
            source_replay_needed = (
                template.get("source_paper_id") == paper_id
                and not validation.get("source_replay_completed")
            )
            trial = (validation.get("paper_trials") or {}).get(str(paper_id), {})
            cross_paper_needed = (
                template.get("source_paper_id") != paper_id
                and trial.get("status") not in {"passed", "failed_final", "blocked"}
                and int(trial.get("attempts_completed", 0) or 0) < maximum
            )
            if source_replay_needed or cross_paper_needed:
                candidates.append(template)
        return candidates
    @staticmethod
    def _campaign_usage(usage: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        records = usage.get("last_used_by_campaign")
        if not isinstance(records, dict):
            return {}
        return {
            str(campaign_id): record
            for campaign_id, record in records.items()
            if isinstance(record, dict)
        }

    @staticmethod
    def _prune_campaign_usage(
        records: Dict[str, Dict[str, Any]],
        maximum: int,
    ) -> Dict[str, Dict[str, Any]]:
        def sort_key(item: Any) -> Any:
            try:
                iteration = int(item[1].get("iteration", -1))
            except (TypeError, ValueError):
                iteration = -1
            return (
                str(item[1].get("used_at", "")),
                iteration,
                item[0],
            )

        ordered = sorted(
            records.items(),
            key=sort_key,
            reverse=True,
        )
        return dict(ordered[:maximum])

    def retrieve_with_snapshot(
        self,
        **kwargs: Any,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Return Planner contexts and the exact materialized index identity."""

        index = self._load()
        contexts = self.retrieve(**kwargs, _index=index)
        return contexts, self.knowledge_snapshot(index)

    def retrieve(
        self,
        *,
        strategy: str,
        campaign_id: str,
        paper_id: str,
        paper_profile: Dict[str, Any],
        iteration: int,
        recent_template_ids: Sequence[str],
        random_seed: int,
        preferred_family_id: Optional[str] = None,
        exclude_lineage_id: Optional[str] = None,
        validation_template_ids: Optional[Sequence[str]] = None,
        _index: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if strategy == "explore":
            return []
        settings = self.config["templates"]
        cooldown = int(settings.get("cooldown_iterations", 10))
        limit = min(2 if strategy == "hybridize" else 1, int(settings.get("retrieval_limit", 3)))
        recent = set(recent_template_ids)
        candidates = []
        index = _index if _index is not None else self._load()
        source_templates = (
            self._validation_candidates(
                paper_id, paper_profile,
                template_ids=validation_template_ids,
                index=index,
            )
            if strategy == "validate"
            else index["templates"]
        )
        for template in source_templates:
            if (
                strategy == "revise"
                and preferred_family_id
                and template.get("family") != preferred_family_id
            ):
                continue
            if (
                strategy == "revise"
                and exclude_lineage_id
                and template.get("source_lineage_id") == exclude_lineage_id
            ):
                continue
            if strategy != "validate" and (not template.get("retrieval_enabled", True) or template.get("status") in {"superseded", "retired"}):
                continue
            if strategy != "validate" and template.get("source_paper_id") != paper_id:
                level = int(template.get("template_level", 0))
                if level == 0:
                    continue
                profile_key = str(paper_profile.get("profile_key") or "")
                applicability = template.get("applicability") or {}
                if profile_key in applicability.get("observed_inapplicable_profiles", []):
                    continue
                if level == 1:
                    validation = template.get("validation") or {}
                    cross_paper_successes = set(validation.get("successful_papers", [])) - {
                        str(template.get("source_paper_id"))
                    }
                    if not cross_paper_successes:
                        continue
                    proven_profiles = validation.get("cross_paper_success_profiles") or []
                    if not profile_key or profile_key not in proven_profiles:
                        continue
            if strategy != "validate" and template.get("template_id") in recent:
                continue
            usage = template.get("usage") or {}
            last_use = self._campaign_usage(usage).get(campaign_id)
            try:
                last_iteration = int(last_use["iteration"]) if last_use else None
            except (KeyError, TypeError, ValueError):
                last_iteration = None
            if strategy != "validate" and last_iteration is not None and iteration - last_iteration < cooldown:
                continue
            visual_range = (template.get("applicability") or {}).get("preferred_visual_count", [0, 10**9])
            if visual_range[0] <= paper_profile.get("visual_count", 0) <= visual_range[1]:
                candidates.append(template)
        rng = random.Random(random_seed)
        if strategy == "validate":
            maximum = int(
                settings.get("max_cross_paper_validation_attempts", 3)
            )
            rng.shuffle(candidates)

            def validation_priority(item: Dict[str, Any]) -> Any:
                validation = self._ensure_validation(item)
                trial = (validation.get("paper_trials") or {}).get(
                    str(paper_id), {}
                )
                attempts = (
                    0 if item.get("source_paper_id") == paper_id
                    else int(trial.get("attempts_completed", 0) or 0)
                )
                return (
                    0 if attempts > 0 else 1,
                    int(item.get("template_id") in recent),
                    int(item.get("template_level", 0)),
                    int(validation.get("events", 0)),
                    str(item.get("created_at", "")),
                )

            candidates.sort(key=validation_priority)
            selected = []
            for item in candidates[:limit]:
                cross_paper = item.get("source_paper_id") != paper_id
                trial = (
                    (self._ensure_validation(item).get("paper_trials") or {})
                    .get(str(paper_id), {})
                )
                completed = int(trial.get("attempts_completed", 0) or 0)
                selected.append({
                    **self._planner_context(item),
                    "validation_task": True,
                    "validation_target": (
                        "cross_paper" if cross_paper else "source_replay"
                    ),
                    "validation_attempt": completed + 1 if cross_paper else 1,
                    "validation_max_attempts": maximum if cross_paper else 1,
                })
            return selected
        families: Dict[str, List[Dict[str, Any]]] = {}
        for candidate in candidates:
            families.setdefault(candidate.get("family", "unknown"), []).append(candidate)
        names = list(families)
        rng.shuffle(names)
        names.sort(key=lambda family: min(int((item.get("usage") or {}).get("times_retrieved", 0)) for item in families[family]))
        selected = []
        for family in names[:limit]:
            choices = sorted(
                families[family],
                key=lambda item: (
                    int((item.get("usage") or {}).get("times_retrieved", 0)),
                    -float(item["template_design_score"] if item.get("template_design_score") is not None else -1),
                    str(item.get("template_id") or ""),
                ),
            )
            selected.append(choices[0])
        return [self._planner_context(item) for item in selected]

    @staticmethod
    def _planner_context(template: Dict[str, Any]) -> Dict[str, Any]:
        relational_blueprint = []
        for item in template.get("normalized_blueprint") or []:
            try:
                x = float(item.get("x", 0.0))
                y = float(item.get("y", 0.0))
                width = float(item.get("width", 0.0))
                height = float(item.get("height", 0.0))
            except (TypeError, ValueError):
                continue
            relational_blueprint.append({
                "role": item.get("role"),
                "zone": item.get("zone"),
                "horizontal_band": (
                    "left"
                    if x < 0.34
                    else "center"
                    if x < 0.67
                    else "right"
                ),
                "vertical_band": "top" if y < 0.34 else "middle" if y < 0.67 else "bottom",
                "width_class": "wide" if width >= 0.28 else "medium" if width >= 0.16 else "narrow",
                "height_class": "tall" if height >= 0.28 else "medium" if height >= 0.14 else "short",
            })
        return {
            "template_id": template.get("template_id"),
            "family": template.get("family"),
            "status": template.get("status"),
            "template_level": int(template.get("template_level", 0)),
            "validation_status": (
                template.get("validation_status")
                or (template.get("validation") or {}).get("status")
            ),
            "applicability": template.get("applicability"),
            "layout_principles": template.get("layout_principles"),
            "relational_blueprint": relational_blueprint,
            "density_targets": template.get("density_targets"),
            "diversity_requirement": "Change at least one major spatial relationship or visual anchor.",
            "adaptation_rule": (
                "Use principles as inspiration; never reconstruct exact coordinates."
            ),
        }

    def record_usage(
        self,
        *,
        template_ids: Iterable[str],
        campaign_id: str,
        paper_id: str,
        profile_key: str,
        iteration: int,
        accepted: bool,
        score: Optional[float],
        event_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        validation_run: bool = False,
        transfer_verified: bool = False,
        transfer_reasons: Sequence[str] = (),
        candidate_id: Optional[str] = None,
        validation_evidence: Optional[Dict[str, Any]] = None,
        expected_template_fingerprint: Optional[str] = None,
        expected_topology_sha256: Optional[str] = None,
        poster_evaluated: bool = True,
        validation_failure_reason: Optional[str] = None,
    ) -> None:
        """Record ordinary reuse or strict validation without mixing semantics."""
        identifiers = set(template_ids)
        if not identifiers:
            return
        settings = self.config["templates"]
        min_papers = int(settings.get("promotion_min_distinct_papers", 3))
        min_profiles = int(settings.get("promotion_min_distinct_profiles", 2))
        max_campaign_records = max(
            1, int(settings.get("max_campaign_cooldown_records", 128))
        )
        used_at = _utc_now()
        with _FileLock(self.lock_path):
            index = self._load()
            previous_digest = str(index.get("knowledge_digest") or "")
            index["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
            processed_events = set(index.get("processed_usage_events", []))
            if event_id and event_id in processed_events:
                self._write_validation_queue(index)
                return

            matched = set()
            for template in index["templates"]:
                template_id = str(template.get("template_id") or "")
                if template_id not in identifiers:
                    continue
                matched.add(template_id)
                template["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
                if validation_run:
                    if (
                        expected_template_fingerprint is not None
                        and template.get("fingerprint")
                        != expected_template_fingerprint
                    ):
                        raise ValueError(
                            "template_changed_during_validation: fingerprint"
                        )
                    topology = template.get("zone_topology") or {}
                    topology_sha256 = hashlib.sha256(
                        json.dumps(
                            topology, sort_keys=True, separators=(",", ":")
                        ).encode("utf-8")
                    ).hexdigest()
                    if (
                        expected_topology_sha256 is not None
                        and topology_sha256 != expected_topology_sha256
                    ):
                        raise ValueError(
                            "template_changed_during_validation: topology"
                        )
                    self._record_validation_outcome(
                        template,
                        paper_id=paper_id,
                        profile_key=profile_key,
                        poster_accepted=accepted,
                        transfer_verified=transfer_verified,
                        score=score,
                        campaign_id=campaign_id,
                        iteration=iteration,
                        event_id=event_id,
                        batch_id=batch_id,
                        transfer_reasons=transfer_reasons,
                        candidate_id=candidate_id,
                        validation_evidence=validation_evidence,
                        poster_evaluated=poster_evaluated,
                        validation_failure_reason=validation_failure_reason,
                        min_papers=min_papers,
                        min_profiles=min_profiles,
                    )
                    continue

                usage = template.get("usage")
                if not isinstance(usage, dict):
                    usage = {}
                    template["usage"] = usage
                usage["times_retrieved"] = int(
                    usage.get("times_retrieved", 0)
                ) + 1
                usage["last_used_iteration"] = iteration
                usage["last_used_paper_id"] = paper_id
                usage["last_used_campaign_id"] = campaign_id
                campaign_usage = self._campaign_usage(usage)
                campaign_usage[campaign_id] = {
                    "iteration": int(iteration),
                    "paper_id": paper_id,
                    "used_at": used_at,
                    "batch_id": batch_id,
                }
                usage["last_used_by_campaign"] = self._prune_campaign_usage(
                    campaign_usage, max_campaign_records
                )
                if accepted:
                    papers = set(usage.get("successful_papers", []))
                    profiles = set(usage.get("successful_profiles", []))
                    papers.add(paper_id)
                    profiles.add(profile_key)
                    usage["successful_papers"] = sorted(papers)
                    usage["successful_profiles"] = sorted(profiles)

            if validation_run and matched != identifiers:
                missing = ", ".join(sorted(identifiers - matched))
                raise ValueError(f"validation template not found: {missing}")
            if event_id:
                processed_events.add(event_id)
                index["processed_usage_events"] = sorted(
                    processed_events
                )[-10000:]

            rebuild_retrieval_seats(index, self.config["templates"])
            self._write_index(index, previous_digest=previous_digest)
            self._write_validation_queue(index)
            for template_id in identifiers:
                _append_jsonl(self.outcomes_path, {
                    "timestamp": used_at,
                    "template_id": template_id,
                    "campaign_id": campaign_id,
                    "paper_id": paper_id,
                    "profile_key": profile_key,
                    "iteration": iteration,
                    "accepted": accepted,
                    "score": score,
                    "event_id": event_id,
                    "batch_id": batch_id,
                    "validation_run": validation_run,
                    "transfer_verified": transfer_verified,
                    "transfer_reasons": list(transfer_reasons),
                    "candidate_id": candidate_id,
                    "validation_evidence": validation_evidence,
                    "poster_evaluated": bool(poster_evaluated),
                    "validation_failure_reason": validation_failure_reason,
                })
    def _record_validation_outcome(
        self,
        template: Dict[str, Any],
        *,
        paper_id: str,
        profile_key: str,
        poster_accepted: bool,
        transfer_verified: bool,
        score: Optional[float],
        campaign_id: str,
        iteration: int,
        event_id: Optional[str],
        batch_id: Optional[str],
        transfer_reasons: Sequence[str],
        candidate_id: Optional[str],
        validation_evidence: Optional[Dict[str, Any]],
        poster_evaluated: bool,
        validation_failure_reason: Optional[str],
        min_papers: int,
        min_profiles: int,
    ) -> None:
        """Record one committed attempt and finalize only conclusive papers."""

        validation = self._ensure_validation(template)
        source_replay = str(template.get("source_paper_id")) == str(paper_id)
        if source_replay and validation.get("source_replay_completed"):
            return

        maximum = int(
            self.config["templates"].get(
                "max_cross_paper_validation_attempts", 3
            )
        )
        trials = validation.setdefault("paper_trials", {})
        trial = None
        if not source_replay:
            trial = trials.setdefault(str(paper_id), {
                "profile_key": profile_key,
                "target": "cross_paper",
                "status": "retry_pending",
                "attempts_completed": 0,
                "successful": False,
                "attempts": [],
            })
            if trial.get("status") in {"passed", "failed_final", "blocked"}:
                return

        passed = bool(poster_accepted and transfer_verified)
        validation["events"] = int(validation.get("events", 0)) + 1
        counter = "successful_events" if passed else "failed_events"
        validation[counter] = int(validation.get(counter, 0)) + 1
        validation["last_validated_at"] = _utc_now()
        reasons = [str(reason) for reason in transfer_reasons if reason]
        result = (
            "passed" if passed
            else str(validation_failure_reason)
            if validation_failure_reason
            else "strict_transfer_failed" if poster_accepted
            else "poster_rejected"
        )
        evidence = dict(validation_evidence or {})
        attempt_record = {
            "event_id": event_id,
            "candidate_id": candidate_id,
            "campaign_id": campaign_id,
            "batch_id": batch_id,
            "iteration": int(iteration),
            "poster_score": (
                float(score) if isinstance(score, (int, float)) else None
            ),
            "poster_evaluated": bool(poster_evaluated),
            "poster_accepted": bool(poster_accepted),
            "transfer_verified": bool(transfer_verified),
            "transfer_reasons": reasons,
            "result": result,
            "poster_artifact_saved": bool(evidence.get("saved")),
            "evidence": evidence,
            "recorded_at": _utc_now(),
        }

        if source_replay:
            validation["source_replay_completed"] = True
            validation["source_replay_attempt"] = attempt_record
            self._refresh_validation_aggregates(
                template, min_papers=min_papers, min_profiles=min_profiles
            )
            return

        trial["profile_key"] = profile_key
        completed = int(trial.get("attempts_completed", 0) or 0) + 1
        attempt_record["attempt_number"] = completed
        trial.setdefault("attempts", []).append(attempt_record)
        trial["attempts"] = trial["attempts"][-maximum:]
        trial["attempts_completed"] = completed
        trial["last_score"] = (
            float(score) if isinstance(score, (int, float)) else None
        )
        trial["last_result"] = result
        if passed:
            trial["status"] = "passed"
            trial["successful"] = True
            trial["finalized_at"] = _utc_now()
        elif completed >= maximum:
            trial["status"] = "failed_final"
            trial["successful"] = False
            trial["finalized_at"] = _utc_now()
        else:
            trial["status"] = "retry_pending"
            trial["successful"] = False

        self._refresh_validation_aggregates(
            template, min_papers=min_papers, min_profiles=min_profiles
        )
    def _refresh_validation_aggregates(
        self,
        template: Dict[str, Any],
        *,
        min_papers: Optional[int] = None,
        min_profiles: Optional[int] = None,
    ) -> None:
        """Derive levels and applicability from finalized paper outcomes."""

        validation = self._ensure_validation(template)
        settings = self.config["templates"]
        min_papers = int(
            min_papers if min_papers is not None
            else settings.get("promotion_min_distinct_papers", 3)
        )
        min_profiles = int(
            min_profiles if min_profiles is not None
            else settings.get("promotion_min_distinct_profiles", 2)
        )
        source_paper = str(template.get("source_paper_id") or "")
        source_profile = str(template.get("source_profile") or "")
        trials = validation.get("paper_trials") or {}
        finalized = {
            str(paper_id): trial
            for paper_id, trial in trials.items()
            if isinstance(trial, dict)
            and trial.get("status") in {"passed", "failed_final"}
        }
        successful_trials = {
            paper_id: trial for paper_id, trial in finalized.items()
            if trial.get("status") == "passed"
        }
        failed_trials = {
            paper_id: trial for paper_id, trial in finalized.items()
            if trial.get("status") == "failed_final"
        }
        successful_papers = ({source_paper} if source_paper else set()) | set(
            successful_trials
        )
        successful_profiles = ({source_profile} if source_profile else set())
        successful_profiles.update(
            str(trial.get("profile_key"))
            for trial in successful_trials.values()
            if trial.get("profile_key")
            and trial.get("profile_key") != "legacy_unknown"
        )
        cross_success_profiles = {
            str(trial.get("profile_key"))
            for trial in successful_trials.values()
            if trial.get("profile_key")
            and trial.get("profile_key") != "legacy_unknown"
        }
        distinct_profiles = {
            str(trial.get("profile_key"))
            for trial in finalized.values()
            if trial.get("profile_key")
            and trial.get("profile_key") != "legacy_unknown"
        }
        validation["distinct_validation_papers"] = sorted(finalized)
        validation["distinct_validation_profiles"] = sorted(distinct_profiles)
        validation["successful_papers"] = sorted(successful_papers)
        validation["successful_profiles"] = sorted(successful_profiles)
        validation["cross_paper_success_profiles"] = sorted(
            cross_success_profiles
        )
        validation["failed_papers"] = sorted(failed_trials)

        profile_outcomes: Dict[str, Dict[str, Any]] = {}
        for trial in finalized.values():
            profile = str(trial.get("profile_key") or "legacy_unknown")
            outcome = profile_outcomes.setdefault(
                profile, {"successes": 0, "failures": 0, "scores": []}
            )
            key = "successes" if trial.get("status") == "passed" else "failures"
            outcome[key] = int(outcome.get(key, 0)) + 1
            scores = [
                float(attempt["poster_score"])
                for attempt in trial.get("attempts", [])
                if isinstance(attempt, dict)
                and isinstance(attempt.get("poster_score"), (int, float))
            ]
            outcome["scores"] = (outcome.get("scores", []) + scores)[-20:]
        validation["profile_outcomes"] = profile_outcomes

        inapplicable = set(
            (template.get("applicability") or {}).get(
                "observed_inapplicable_profiles", []
            )
        )
        for profile, outcome in profile_outcomes.items():
            if profile == "legacy_unknown":
                continue
            if int(outcome.get("successes", 0)) > 0:
                inapplicable.discard(profile)
            elif int(outcome.get("failures", 0)) >= 2:
                inapplicable.add(profile)
        template.setdefault("applicability", {})[
            "observed_inapplicable_profiles"
        ] = sorted(inapplicable)

        robust_papers = int(settings.get("robust_min_distinct_papers", 6))
        robust_profiles = int(settings.get("robust_min_distinct_profiles", 3))
        if (
            len(successful_papers) >= robust_papers
            and len(successful_profiles) >= robust_profiles
        ):
            level, status = 3, "robust"
            validation["next_target"] = "continued_boundary_sampling"
        elif (
            len(successful_papers) >= min_papers
            and len(successful_profiles) >= min_profiles
        ):
            level, status = 2, "cross_profile_validated"
            validation["next_target"] = "cross_profile"
        elif successful_trials:
            level, status = 1, "profile_validated"
            validation["next_target"] = "cross_profile"
        else:
            level, status = 0, "paper_specific"
            validation["next_target"] = (
                "same_profile"
                if validation.get("source_replay_completed")
                else "source_replay"
            )
        if any(
            trial.get("status") == "retry_pending"
            for trial in trials.values() if isinstance(trial, dict)
        ):
            validation["next_target"] = "retry_pending"
        template["template_level"] = level
        template["validation_status"] = status
        validation["status"] = status
        template["status"] = (
            "validated" if level >= 2
            else "profile_validated" if level == 1
            else "paper_specific"
        )


class LoopStorage:
    """Persist loop checkpoints, failures, and accepted artifacts."""

    def __init__(self, root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or load_critic_config()
        configured = Path(self.config["storage"].get("root", "storage/critic_loop"))
        project_root = Path(__file__).resolve().parents[2]
        self.root = Path(root) if root is not None else project_root / configured
        self.root.mkdir(parents=True, exist_ok=True)

    def create_session(self, poster_name: str) -> str:
        session_id = f"{poster_name}_{uuid.uuid4().hex[:12]}"
        (self.root / "loop_sessions" / session_id / "iterations").mkdir(parents=True, exist_ok=True)
        return session_id

    def save_checkpoint(self, session_id: str, loop_state: Dict[str, Any]) -> Path:
        path = self.root / "loop_sessions" / session_id / "loop_state.json"
        _atomic_json(path, loop_state)
        _append_jsonl(self.root / "loop_sessions" / session_id / "events.jsonl", {"timestamp": _utc_now(), "event": "checkpoint", **loop_state})
        return path

    def save_progress_event(self, session_id: str, event: Dict[str, Any]) -> None:
        """Keep a compact, chronological terminal-progress journal per launch."""
        _append_jsonl(
            self.root / "loop_sessions" / session_id / "progress_events.jsonl",
            {"timestamp": _utc_now(), **event},
        )

    def save_iteration_report(self, session_id: str, iteration: int, report: Dict[str, Any]) -> Path:
        path = self.root / "loop_sessions" / session_id / "iterations" / f"{iteration:06d}.json"
        _atomic_json(path, report)
        return path

    def record_rejection(
        self,
        session_id: str,
        state: PosterState,
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Stage a committed-design rejection and remove its working copy.

        The returned diagnostic is intentionally not published here. The
        Campaign runner publishes it only after ``COMPLETED.json`` exists.
        """

        _append_jsonl(self.root / "design_memory" / "rejection_memory.jsonl", {
            "timestamp": _utc_now(), "session_id": session_id,
            "paper_id": state.get("poster_name"), "candidate_id": report.get("candidate_id"),
            "strategy": report.get("strategy"), "overall_score": report.get("overall_score"),
            "issue_codes": [item.get("issue_id") for item in report.get("issues", [])],
            "rejection_summary": report.get("rejection_summary"),
        })
        diagnostic = self.prepare_rejected_poster(
            session_id,
            state,
            report,
            rejection_kind=str(report.get("loop_disposition") or "poster_rejected"),
        )
        self._remove_candidate_artifacts(state)
        return diagnostic

    def archive_candidate(self, session_id: str, state: PosterState, report: Dict[str, Any]) -> Dict[str, Any]:
        candidate = state.get("current_candidate") or {}
        candidate_id = str(candidate.get("candidate_id") or uuid.uuid4().hex)
        destination = self.root / "accepted_posters" / candidate_id
        destination.mkdir(parents=True, exist_ok=True)
        archived_paths: Dict[str, str] = {}
        for kind in ("pptx", "png"):
            source = Path(candidate.get(f"{kind}_path", ""))
            if source.is_file():
                target = destination / f"poster.{kind}"
                shutil.copy2(source, target)
                archived_paths[f"{kind}_path"] = str(target)
        snapshots = {
            "critic_report.json": report,
            "story_board.json": state.get("optimized_story_board") or state.get("story_board"),
            "styled_layout.json": state.get("styled_layout"),
            "provenance.json": {
                "schema_version": 1, "archived_at": _utc_now(), "session_id": session_id,
                "candidate_id": candidate_id, "paper_id": state.get("poster_name"),
                "iteration_context": state.get("iteration_context"),
                "template_ids": [item.get("template_id") for item in (state.get("template_context") or [])],
                "critic_system_version": report.get("critic_system_version"),
                "rubric_version": report.get("rubric_version"),
            },
        }
        for filename, payload in snapshots.items():
            _atomic_json(destination / filename, payload)
        return {"candidate_id": candidate_id, "archive_dir": str(destination), **archived_paths}

    def prepare_accepted_bundle(
        self, session_id: str, state: PosterState, report: Dict[str, Any],
        template: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Stage a complete 1:1 poster/template bundle before iteration commit."""
        from src.templates.preview import render_preview

        candidate = state.get("current_candidate") or {}
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id or not all(c.isalnum() or c in "_-" for c in candidate_id):
            raise ValueError("Invalid candidate ID for accepted bundle")
        if template.get("source_candidate_id") != candidate_id:
            raise ValueError("Template source must match accepted poster")
        template["artifact_paths"] = {
            kind: f"accepted_posters/{candidate_id}/{filename}"
            for kind, filename in {
                "poster_png": "poster.png", "poster_pptx": "poster.pptx",
                "template_json": "template.json", "template_png": "template.png",
                "template_pptx": "template.pptx",
            }.items()
        }
        pending_root = self.root / "accepted_posters" / ".pending"
        pending_root.mkdir(parents=True, exist_ok=True)
        pending = pending_root / candidate_id
        if pending.exists():
            raise FileExistsError(f"Pending bundle already exists: {candidate_id}")
        with tempfile.TemporaryDirectory(prefix=".bundle_", dir=pending_root) as temporary:
            staging = Path(temporary)
            for kind in ("pptx", "png"):
                source = Path(candidate.get(f"{kind}_path") or "")
                if not source.is_file():
                    raise FileNotFoundError(f"Accepted poster is missing {kind}: {source}")
                shutil.copy2(source, staging / f"poster.{kind}")
            _atomic_json(staging / "critic_report.json", report)
            _atomic_json(staging / "story_board.json", state.get("optimized_story_board") or state.get("story_board"))
            _atomic_json(staging / "styled_layout.json", state.get("styled_layout"))
            for field in ("revision_execution_report", "revision_contract", "revision_safety_report"):
                if state.get(field):
                    _atomic_json(staging / f"{field}.json", state[field])
            _atomic_json(staging / "template.json", template)
            _atomic_json(staging / "provenance.json", {
                "schema_version": 3, "archived_at": _utc_now(),
                "session_id": session_id, "candidate_id": candidate_id,
                "paper_id": state.get("poster_name"),
                "iteration_context": state.get("iteration_context"),
                "source_template_id": template.get("template_id"),
                "critic_system_version": report.get("critic_system_version"),
                "rubric_version": report.get("rubric_version"),
            })
            render_preview(template, staging / "template.png", staging / "template.pptx")
            # Rename a complete directory, never expose an incomplete bundle.
            os.replace(staging, pending)
        final = self.root / "accepted_posters" / candidate_id
        return {
            "candidate_id": candidate_id, "archive_dir": str(final),
            "pptx_path": str(final / "poster.pptx"),
            "png_path": str(final / "poster.png"),
            "template_json_path": str(final / "template.json"),
            "template_png_path": str(final / "template.png"),
            "template_pptx_path": str(final / "template.pptx"),
        }

    def prepare_validation_evidence(
        self,
        session_id: str,
        state: PosterState,
        report: Dict[str, Any],
        *,
        template_id: str,
        template_fingerprint: Optional[str],
        paper_id: str,
    ) -> Dict[str, Any]:
        """Stage a passed strict-validation poster without creating a template."""
        candidate = state.get("current_candidate") or {}
        candidate_id = str(candidate.get("candidate_id") or "")
        components = {
            "candidate_id": candidate_id,
            "template_id": str(template_id),
            "paper_id": str(paper_id),
        }
        for label, value in components.items():
            if not value or not all(char.isalnum() or char in "_-" for char in value):
                raise ValueError(f"Invalid {label} for validation evidence")

        pending_root = self.root / "validation_evidence" / ".pending"
        pending_root.mkdir(parents=True, exist_ok=True)
        pending = pending_root / candidate_id
        if pending.exists():
            raise FileExistsError(
                f"Pending validation evidence already exists: {candidate_id}"
            )
        relative_dir = (
            Path("validation_evidence") / template_id / paper_id / candidate_id
        )
        final = self.root / relative_dir
        task_evaluation = report.get("task_evaluation") or {}
        with tempfile.TemporaryDirectory(
            prefix=".validation_", dir=pending_root
        ) as temporary:
            staging = Path(temporary)
            for kind in ("pptx", "png"):
                source = Path(candidate.get(f"{kind}_path") or "")
                if not source.is_file():
                    raise FileNotFoundError(
                        f"Validation evidence is missing {kind}: {source}"
                    )
                shutil.copy2(source, staging / f"poster.{kind}")
            _atomic_json(staging / "critic_report.json", report)
            _atomic_json(staging / "task_evaluation.json", task_evaluation)
            _atomic_json(
                staging / "story_board.json",
                state.get("optimized_story_board") or state.get("story_board"),
            )
            _atomic_json(
                staging / "styled_layout.json", state.get("styled_layout")
            )
            _atomic_json(staging / "provenance.json", {
                "schema_version": 1,
                "artifact_type": "strict_template_validation_evidence",
                "archived_at": _utc_now(),
                "session_id": session_id,
                "candidate_id": candidate_id,
                "validated_template_id": template_id,
                "template_fingerprint": template_fingerprint,
                "paper_id": paper_id,
                "iteration_context": state.get("iteration_context"),
                "poster_accepted": bool(report.get("archive_eligible")),
                "transfer_verified": bool(task_evaluation.get("passed")),
                "critic_system_version": report.get("critic_system_version"),
                "rubric_version": report.get("rubric_version"),
            })
            os.replace(staging, pending)
        return {
            "artifact_kind": "validation_evidence",
            "saved": True,
            "candidate_id": candidate_id,
            "validated_template_id": template_id,
            "relative_dir": str(relative_dir),
            "archive_dir": str(final),
            "artifact_paths": {
                "poster_pptx": str(relative_dir / "poster.pptx"),
                "poster_png": str(relative_dir / "poster.png"),
                "critic_report": str(relative_dir / "critic_report.json"),
                "task_evaluation": str(
                    relative_dir / "task_evaluation.json"
                ),
            },
            "pptx_path": str(final / "poster.pptx"),
            "png_path": str(final / "poster.png"),
            "critic_report_path": str(final / "critic_report.json"),
            "task_evaluation_path": str(final / "task_evaluation.json"),
        }

    def publish_validation_evidence(self, evidence: Dict[str, Any]) -> None:
        """Publish staged validation evidence after the iteration commit."""
        candidate_id = str(evidence["candidate_id"])
        pending = self.root / "validation_evidence" / ".pending" / candidate_id
        relative = Path(str(evidence.get("relative_dir") or ""))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] != "validation_evidence"
            or relative.name != candidate_id
        ):
            raise ValueError("Invalid validation evidence destination")
        final = self.root / relative
        required = (
            "poster.pptx", "poster.png", "critic_report.json",
            "task_evaluation.json", "provenance.json",
        )
        if final.is_dir() and all((final / name).is_file() for name in required):
            return
        if not pending.is_dir() or not all(
            (pending / name).is_file() for name in required
        ):
            raise FileNotFoundError(
                f"Incomplete validation evidence: {candidate_id}"
            )
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(pending, final)

    def prepare_rejected_poster(
        self,
        session_id: str,
        state: PosterState,
        report: Dict[str, Any],
        *,
        rejection_kind: str,
    ) -> Dict[str, Any]:
        """Stage a complete rendered rejection for post-commit publication."""

        candidate = state.get("current_candidate") or {}
        context = state.get("iteration_context") or {}
        candidate_id = str(
            candidate.get("candidate_id")
            or report.get("candidate_id")
            or ""
        )
        campaign_id = str(context.get("campaign_id") or "")
        batch_id = str(context.get("batch_id") or "")
        components = {
            "campaign_id": campaign_id,
            "batch_id": batch_id,
            "candidate_id": candidate_id,
        }
        for label, value in components.items():
            if not value or not all(
                character.isalnum() or character in "_-"
                for character in value
            ):
                raise ValueError(f"Invalid {label} for rejected poster")

        pending_root = self.root / "rejected_posters" / ".pending"
        pending_root.mkdir(parents=True, exist_ok=True)
        pending = pending_root / candidate_id
        if pending.exists():
            raise FileExistsError(
                f"Pending rejected poster already exists: {candidate_id}"
            )
        relative_dir = (
            Path("rejected_posters") / campaign_id / batch_id / candidate_id
        )
        final = self.root / relative_dir
        selected_template_ids = [
            str(item.get("template_id"))
            for item in (state.get("template_context") or [])
            if isinstance(item, dict) and item.get("template_id")
        ]
        with tempfile.TemporaryDirectory(
            prefix=".rejected_", dir=pending_root
        ) as temporary:
            staging = Path(temporary)
            for kind in ("pptx", "png"):
                source = Path(candidate.get(f"{kind}_path") or "")
                if not source.is_file():
                    raise FileNotFoundError(
                        f"Rejected poster is missing {kind}: {source}"
                    )
                shutil.copy2(source, staging / f"poster.{kind}")
            _atomic_json(staging / "critic_report.json", report)
            _atomic_json(
                staging / "layout_feasibility_report.json",
                state.get("layout_feasibility_report") or {},
            )
            for field in ("revision_execution_report", "revision_contract", "revision_safety_report"):
                if state.get(field):
                    _atomic_json(staging / f"{field}.json", state[field])
            _atomic_json(
                staging / "layout_preflight_report.json",
                state.get("layout_preflight_report") or {},
            )
            _atomic_json(
                staging / "render_fit_report.json",
                state.get("render_fit_report") or {},
            )
            _atomic_json(
                staging / "story_board.json",
                state.get("optimized_story_board")
                or state.get("story_board")
                or {},
            )
            _atomic_json(
                staging / "styled_layout.json",
                state.get("styled_layout") or [],
            )
            _atomic_json(staging / "provenance.json", {
                "schema_version": 2,
                "artifact_type": "rejected_poster_diagnostic",
                "recorded_at": _utc_now(),
                "session_id": session_id,
                "campaign_id": campaign_id,
                "batch_id": batch_id,
                "iteration": context.get("iteration"),
                "candidate_id": candidate_id,
                "rejection_kind": str(rejection_kind),
                "decision": report.get("decision"),
                "overall_score": report.get("overall_score"),
                "executed_mode": context.get("portfolio_mode"),
                "requested_mode": context.get("requested_mode"),
                "batch_mode": context.get("batch_mode"),
                "layout_family": context.get("layout_family"),
                "lineage_id": context.get("lineage_id"),
                "parent_candidate_id": context.get(
                    "parent_candidate_id"
                ),
                "selected_template_ids": selected_template_ids,
                "validation_target": context.get("validation_target"),
                "validation_attempt": context.get("validation_attempt"),
                "critic_system_version": report.get(
                    "critic_system_version"
                ),
                "rubric_version": report.get("rubric_version"),
            })
            os.replace(staging, pending)
        return {
            "artifact_kind": "rejected_poster",
            "saved": True,
            "candidate_id": candidate_id,
            "rejection_kind": str(rejection_kind),
            "relative_dir": str(relative_dir),
            "archive_dir": str(final),
            "artifact_paths": {
                "poster_pptx": str(relative_dir / "poster.pptx"),
                "poster_png": str(relative_dir / "poster.png"),
                "critic_report": str(
                    relative_dir / "critic_report.json"
                ),
                "provenance": str(relative_dir / "provenance.json"),
            },
            "pptx_path": str(final / "poster.pptx"),
            "png_path": str(final / "poster.png"),
            "critic_report_path": str(final / "critic_report.json"),
        }

    def publish_rejected_poster(
        self, diagnostic: Dict[str, Any]
    ) -> None:
        """Publish one staged diagnostic without indexing it as knowledge."""

        candidate_id = str(diagnostic["candidate_id"])
        pending = self.root / "rejected_posters" / ".pending" / candidate_id
        relative = Path(str(diagnostic.get("relative_dir") or ""))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or len(relative.parts) != 4
            or relative.parts[0] != "rejected_posters"
            or relative.name != candidate_id
        ):
            raise ValueError("Invalid rejected poster destination")
        final = self.root / relative
        required = (
            "poster.pptx",
            "poster.png",
            "critic_report.json",
            "layout_feasibility_report.json",
            "layout_preflight_report.json",
            "story_board.json",
            "styled_layout.json",
            "provenance.json",
        )
        if final.is_dir() and all(
            (final / name).is_file() for name in required
        ):
            return
        if final.exists():
            raise FileExistsError(
                f"Incomplete rejected poster destination: {candidate_id}"
            )
        if not pending.is_dir() or not all(
            (pending / name).is_file() for name in required
        ):
            raise FileNotFoundError(
                f"Incomplete rejected poster diagnostic: {candidate_id}"
            )
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(pending, final)

    def discard_candidate_artifacts(self, state: PosterState) -> None:
        """Remove rendered candidate files that must not be archived."""
        self._remove_candidate_artifacts(state)

    def discard_pending(self, candidate_id: str) -> None:
        """Remove only a known uncommitted candidate's staged bundle."""
        candidate_id = str(candidate_id)
        if not candidate_id or not all(c.isalnum() or c in "_-" for c in candidate_id):
            return
        pending_roots = (
            self.root / "accepted_posters" / ".pending",
            self.root / "validation_evidence" / ".pending",
            self.root / "rejected_posters" / ".pending",
        )
        for pending_root in pending_roots:
            pending = pending_root / candidate_id
            if pending.is_dir():
                shutil.rmtree(pending)

    def publish_accepted_bundle(self, archive: Dict[str, Any]) -> None:
        """Publish a staged bundle only after COMPLETED.json exists."""
        candidate_id = str(archive["candidate_id"])
        pending = self.root / "accepted_posters" / ".pending" / candidate_id
        final = self.root / "accepted_posters" / candidate_id
        required = ("poster.pptx", "poster.png", "template.json",
                    "template.pptx", "template.png", "critic_report.json")
        if final.is_dir() and all((final / name).is_file() for name in required):
            return
        if not pending.is_dir() or not all((pending / name).is_file() for name in required):
            raise FileNotFoundError(f"Incomplete accepted bundle: {candidate_id}")
        os.replace(pending, final)

    def promote_best(self, state: PosterState, archive: Dict[str, Any], output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for kind in ("pptx", "png"):
            source = Path(archive.get(f"{kind}_path", ""))
            if source.is_file():
                target = output_dir / f"{state['poster_name']}.{kind}"
                temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
                try:
                    shutil.copy2(source, temporary)
                    os.replace(temporary, target)
                finally:
                    if temporary.exists():
                        temporary.unlink()

    def _remove_candidate_artifacts(self, state: PosterState) -> None:
        candidate = state.get("current_candidate") or {}
        raw_dir = candidate.get("candidate_dir")
        if not raw_dir:
            return
        candidate_dir = Path(raw_dir).resolve()
        for kind in ("pptx", "png"):
            if not self.config["storage"].get(f"remove_rejected_{kind}", True):
                continue
            raw_path = candidate.get(f"{kind}_path")
            if not raw_path:
                continue
            path = Path(raw_path).resolve()
            try:
                path.relative_to(candidate_dir)
            except ValueError:
                continue
            if path.is_file():
                path.unlink()
