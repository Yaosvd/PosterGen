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
from src.state.poster_state import PosterState

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


TEMPLATE_LIBRARY_SCHEMA_VERSION = 4


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
        vector.extend([
            min(signature["zone_count"] / 8.0, 1.5),
            min(
                sum(
                    1
                    for zone in layout_spec.get("zones", [])
                    if float(zone.get("width", 0.0)) >= 0.65
                ) / 4.0,
                1.5,
            ),
        ])
        canonical = json.dumps({"blueprint": blueprint, "family": family}, sort_keys=True, separators=(",", ":"))
        paper_id = (state.get("loop_state") or {}).get(
            "paper_id", state.get("poster_name", "unknown")
        )
        candidate = state.get("current_candidate") or {}
        return {
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
                "failed_papers": [],
                "profile_outcomes": {},
                "events": 0,
                "successful_events": 0,
                "failed_events": 0,
                "last_validated_at": None,
                "next_target": "source_replay",
            },
        }

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

    def _load(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return {"schema_version": TEMPLATE_LIBRARY_SCHEMA_VERSION, "templates": []}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": TEMPLATE_LIBRARY_SCHEMA_VERSION, "templates": []}

    def validation_summaries(self, template_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        """Read current validation levels after a committed usage outcome."""
        identifiers = set(template_ids)
        return {
            str(item["template_id"]): {
                "level": int(item.get("template_level", 0)),
                "status": str(item.get("validation_status", "pending")),
            }
            for item in self._load().get("templates", [])
            if item.get("template_id") in identifiers
        }

    @staticmethod
    def _distance(left: Sequence[float], right: Sequence[float]) -> float:
        length = max(len(left), len(right))
        if not length:
            return 0.0
        a = list(left) + [0.0] * (length - len(left))
        b = list(right) + [0.0] * (length - len(right))
        return (sum((x - y) ** 2 for x, y in zip(a, b)) / length) ** 0.5

    def register(self, template: Dict[str, Any]) -> Dict[str, Any]:
        settings = self.config["templates"]
        threshold = float(settings.get("novelty_distance_threshold", 0.08))
        max_per_family = int(settings.get("max_active_per_family", 20))
        with _FileLock(self.lock_path):
            index = self._load()
            index["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
            template["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
            usage = template.get("usage")
            if not isinstance(usage, dict):
                usage = {}
                template["usage"] = usage
            usage.setdefault("last_used_by_campaign", {})
            self._ensure_validation(template)
            active = [item for item in index["templates"] if item.get("status") not in {"superseded", "retired"}]
            for existing in active:
                if existing.get("fingerprint") == template.get("fingerprint"):
                    return {"registered": False, "reason": "duplicate_fingerprint", "template": existing}
            comparison_pool = active
            closest = min(
                comparison_pool,
                key=lambda item: self._distance(item.get("signature_vector", []), template.get("signature_vector", [])),
                default=None,
            )
            if closest is not None:
                distance = self._distance(closest.get("signature_vector", []), template.get("signature_vector", []))
                if distance < threshold:
                    if float(template.get("overall_score", 0)) <= float(closest.get("overall_score", 0)):
                        return {"registered": False, "reason": "near_duplicate_not_better", "template": closest, "distance": distance}
                    closest["status"] = "superseded"
                    closest["superseded_by"] = template["template_id"]
            same_family = [item for item in index["templates"] if item.get("family") == template.get("family") and item.get("status") not in {"superseded", "retired"}]
            if len(same_family) >= max_per_family:
                weakest = min(same_family, key=lambda item: float(item.get("overall_score", 0)))
                if float(template.get("overall_score", 0)) <= float(weakest.get("overall_score", 0)):
                    return {"registered": False, "reason": "family_capacity", "template": weakest}
                weakest["status"] = "superseded"
                weakest["superseded_by"] = template["template_id"]
            index["templates"].append(template)
            _atomic_json(self.index_path, index)
            self._write_validation_queue(index)
            return {"registered": True, "reason": "novel_template", "template": template}

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
        validation.setdefault("failed_papers", [])
        validation.setdefault("profile_outcomes", {})
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
        if (
            source_profile
            and source_profile not in validation["successful_profiles"]
        ):
            validation["successful_profiles"].append(source_profile)
        return validation

    def _write_validation_queue(self, index: Dict[str, Any]) -> None:
        queue = []
        for template in index.get("templates", []):
            if template.get("status") in {"superseded", "retired"}:
                continue
            validation = self._ensure_validation(template)
            if not validation.get("required", True):
                continue
            queue.append({
                "template_id": template.get("template_id"),
                "family": template.get("family"),
                "template_level": int(template.get("template_level", 0)),
                "validation_status": validation.get("status"),
                "next_target": validation.get("next_target"),
                "source_paper_id": template.get("source_paper_id"),
                "distinct_validation_papers": len(
                    validation.get("distinct_validation_papers", [])
                ),
                "distinct_validation_profiles": len(
                    validation.get("distinct_validation_profiles", [])
                ),
            })
        _atomic_json(self.validation_queue_path, {
            "schema_version": 1,
            "updated_at": _utc_now(),
            "pending": queue,
        })

    def has_validation_candidate(
        self,
        *,
        paper_id: str,
        paper_profile: Dict[str, Any],
    ) -> bool:
        return bool(self._validation_candidates(paper_id, paper_profile))

    def _validation_candidates(
        self,
        paper_id: str,
        paper_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        visual_count = int(paper_profile.get("visual_count", 0))
        candidates = []
        for template in self._load().get("templates", []):
            if template.get("status") in {"superseded", "retired"}:
                continue
            validation = self._ensure_validation(template)
            if not validation.get("required", True):
                continue
            visual_range = (
                template.get("applicability") or {}
            ).get("preferred_visual_count", [0, 10**9])
            if not visual_range[0] <= visual_count <= visual_range[1]:
                continue
            source_replay_needed = (
                template.get("source_paper_id") == paper_id
                and not validation.get("source_replay_completed")
            )
            cross_paper_needed = (
                template.get("source_paper_id") != paper_id
                and paper_id not in validation.get(
                    "distinct_validation_papers", []
                )
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
    ) -> List[Dict[str, Any]]:
        if strategy in {"explore", "revise", "mutate"}:
            return []
        settings = self.config["templates"]
        cooldown = int(settings.get("cooldown_iterations", 10))
        limit = min(2 if strategy == "hybridize" else 1, int(settings.get("retrieval_limit", 3)))
        recent = set(recent_template_ids)
        candidates = []
        source_templates = (
            self._validation_candidates(paper_id, paper_profile)
            if strategy == "validate"
            else self._load()["templates"]
        )
        for template in source_templates:
            if template.get("status") in {"superseded", "retired"}:
                continue
            status = template.get("status", "paper_specific")
            if (
                strategy != "validate"
                and status == "paper_specific"
                and template.get("source_paper_id") != paper_id
            ):
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
            rng.shuffle(candidates)
            candidates.sort(key=lambda item: (
                int(item.get("template_level", 0)),
                int((item.get("validation") or {}).get("events", 0)),
                str(item.get("created_at", "")),
            ))
            return [
                {
                    **self._planner_context(item),
                    "validation_task": True,
                    "validation_target": (
                        "source_replay"
                        if item.get("source_paper_id") == paper_id
                        else "cross_paper"
                    ),
                }
                for item in candidates[:limit]
            ]
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
                key=lambda item: (int((item.get("usage") or {}).get("times_retrieved", 0)), -float(item.get("overall_score", 0))),
            )
            selected.append(choices[0])
        return [self._planner_context(item) for item in selected]

    @staticmethod
    def _planner_context(template: Dict[str, Any]) -> Dict[str, Any]:
        relational_blueprint = []
        for item in template.get("normalized_blueprint") or []:
            try:
                y = float(item.get("y", 0.0))
                width = float(item.get("width", 0.0))
                height = float(item.get("height", 0.0))
            except (TypeError, ValueError):
                continue
            relational_blueprint.append({
                "role": item.get("role"),
                "column": item.get("column"),
                "zone": item.get("zone"),
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
        score: float,
        event_id: Optional[str] = None,
        validation_run: bool = False,
    ) -> None:
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
            index["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
            processed_events = set(index.get("processed_usage_events", []))
            if event_id and event_id in processed_events:
                return

            for template in index["templates"]:
                if template.get("template_id") not in identifiers:
                    continue
                template["schema_version"] = TEMPLATE_LIBRARY_SCHEMA_VERSION
                usage = template.get("usage")
                if not isinstance(usage, dict):
                    usage = {}
                    template["usage"] = usage
                usage["times_retrieved"] = int(usage.get("times_retrieved", 0)) + 1
                usage["last_used_iteration"] = iteration
                usage["last_used_paper_id"] = paper_id
                usage["last_used_campaign_id"] = campaign_id
                campaign_usage = self._campaign_usage(usage)
                campaign_usage[campaign_id] = {
                    "iteration": int(iteration),
                    "paper_id": paper_id,
                    "used_at": used_at,
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
                    if len(papers) >= min_papers and len(profiles) >= min_profiles:
                        template["status"] = "validated"
                is_cross_paper = (
                    str(template.get("source_paper_id")) != str(paper_id)
                )
                if validation_run or is_cross_paper:
                    self._record_validation_outcome(
                        template,
                        paper_id=paper_id,
                        profile_key=profile_key,
                        accepted=accepted,
                        score=score,
                        min_papers=min_papers,
                        min_profiles=min_profiles,
                    )
            if event_id:
                processed_events.add(event_id)
                index["processed_usage_events"] = sorted(processed_events)[-10000:]

            _atomic_json(self.index_path, index)
            self._write_validation_queue(index)
            for template_id in identifiers:
                _append_jsonl(self.outcomes_path, {
                    "timestamp": used_at, "template_id": template_id,
                    "campaign_id": campaign_id, "paper_id": paper_id,
                    "profile_key": profile_key,
                    "iteration": iteration, "accepted": accepted, "score": score,
                    "event_id": event_id,
                    "validation_run": validation_run,
                })

    def _record_validation_outcome(
        self,
        template: Dict[str, Any],
        *,
        paper_id: str,
        profile_key: str,
        accepted: bool,
        score: float,
        min_papers: int,
        min_profiles: int,
    ) -> None:
        """Grade scope without deleting a source-paper-successful template."""

        validation = self._ensure_validation(template)
        validation["events"] = int(validation.get("events", 0)) + 1
        counter = "successful_events" if accepted else "failed_events"
        validation[counter] = int(validation.get(counter, 0)) + 1
        validation["last_validated_at"] = _utc_now()

        if str(template.get("source_paper_id")) == str(paper_id):
            validation["source_replay_completed"] = True
        else:
            papers = set(validation.get("distinct_validation_papers", []))
            profiles = set(validation.get("distinct_validation_profiles", []))
            papers.add(paper_id)
            profiles.add(profile_key)
            validation["distinct_validation_papers"] = sorted(papers)
            validation["distinct_validation_profiles"] = sorted(profiles)

        outcome = validation.setdefault("profile_outcomes", {}).setdefault(
            profile_key,
            {"successes": 0, "failures": 0, "scores": []},
        )
        outcome["successes" if accepted else "failures"] = int(
            outcome.get("successes" if accepted else "failures", 0)
        ) + 1
        scores = list(outcome.get("scores", []))
        scores.append(float(score))
        outcome["scores"] = scores[-20:]

        if accepted:
            validation["successful_papers"] = sorted(set(
                validation.get("successful_papers", []) + [paper_id]
            ))
            validation["successful_profiles"] = sorted(set(
                validation.get("successful_profiles", []) + [profile_key]
            ))
        else:
            validation["failed_papers"] = sorted(set(
                validation.get("failed_papers", []) + [paper_id]
            ))

        successful_papers = set(validation.get("successful_papers", []))
        successful_profiles = set(validation.get("successful_profiles", []))
        cross_paper_successes = successful_papers - {
            str(template.get("source_paper_id"))
        }
        robust_papers = int(
            self.config["templates"].get("robust_min_distinct_papers", 6)
        )
        robust_profiles = int(
            self.config["templates"].get("robust_min_distinct_profiles", 3)
        )
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
        elif len(cross_paper_successes) >= 1:
            level, status = 1, "profile_validated"
            validation["next_target"] = "cross_profile"
        else:
            level, status = 0, "paper_specific"
            validation["next_target"] = (
                "same_profile"
                if validation.get("source_replay_completed")
                else "source_replay"
            )
        template["template_level"] = level
        template["validation_status"] = status
        validation["status"] = status
        # Keep legacy retrieval/promotion compatibility while retaining a more
        # expressive validation_status.
        template["status"] = "validated" if level >= 2 else "paper_specific"

        inapplicable = set(
            (template.get("applicability") or {}).get(
                "observed_inapplicable_profiles", []
            )
        )
        if (
            int(outcome.get("failures", 0)) >= 2
            and int(outcome.get("successes", 0)) == 0
        ):
            inapplicable.add(profile_key)
        template.setdefault("applicability", {})[
            "observed_inapplicable_profiles"
        ] = sorted(inapplicable)


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

    def record_rejection(self, session_id: str, state: PosterState, report: Dict[str, Any]) -> None:
        _append_jsonl(self.root / "design_memory" / "rejection_memory.jsonl", {
            "timestamp": _utc_now(), "session_id": session_id,
            "paper_id": state.get("poster_name"), "candidate_id": report.get("candidate_id"),
            "strategy": report.get("strategy"), "overall_score": report.get("overall_score"),
            "issue_codes": [item.get("issue_id") for item in report.get("issues", [])],
            "rejection_summary": report.get("rejection_summary"),
        })
        self._remove_candidate_artifacts(state)

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
