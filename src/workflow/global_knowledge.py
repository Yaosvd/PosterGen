"""Privacy-bounded, idempotent design feedback shared across Campaigns.

Only structured rubric outcomes are stored here. No paper text, claims,
candidate files, exact geometry, or rendered artifacts cross Campaigns.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


_SAFE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_DIMENSIONS = {
    "scientific_integrity", "content_quality", "layout_integrity",
    "readability", "visual_hierarchy", "visual_balance", "aesthetics",
}
_SCOPES = {
    "layout", "layout_family", "visual_hierarchy", "visual_balance",
    "content_quality", "color", "visual_relevance", "renderer",
    "critic", "scientific_integrity", "typography", "aesthetics",
}
_OPERATIONS = {
    "move_section", "swap_sections", "reorder_sections", "set_vertical_priority",
    "remove_claim", "remove_visual", "move_visual", "replace_visual",
    "restore_visual_aspect_ratio", "set_section_importance", "set_section_gap",
    "move_section_to_zone", "set_reading_order", "set_primary_anchor",
    "add_existing_claim", "add_claim_from_evidence", "create_compact_variant",
    "use_claim_variant", "recompute_layout", "reduce_spacing",
    "remove_low_priority_claim", "increase_title_separation",
    "normalize_typography_hierarchy", "normalize_font_family",
    "reduce_accent_density", "rerender_candidate", "retry_critic",
    "restore_verified_claim_text", "rebuild_layout_spec", "switch_layout_family",
    "normalize_semantic_colors", "repair_text_contrast",
    "use_accessible_palette_variant",
}


def _identifier(value: Any) -> Optional[str]:
    text = str(value or "")
    return text if _SAFE.fullmatch(text) else None


class GlobalDesignKnowledge:
    """Append committed, de-identified events and return bounded priors."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root) / "design_memory" / "global_knowledge" / "events"
        self.root.mkdir(parents=True, exist_ok=True)

    def _events_with_snapshot(
        self,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        corrupt = 0
        digest = hashlib.sha256()
        for path in sorted(self.root.glob("*.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                corrupt += 1
                continue
            if not isinstance(item, dict):
                corrupt += 1
                continue
            canonical = json.dumps(
                item, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False,
            )
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(canonical.encode("utf-8"))
            digest.update(b"\0")
            events.append(item)
        snapshot = {
            "schema_version": 1,
            "event_count": len(events),
            "valid_event_count": len(events),
            "corrupt_event_count": corrupt,
            "digest": digest.hexdigest(),
        }
        return events, snapshot

    def knowledge_snapshot(self) -> Dict[str, Any]:
        return self._events_with_snapshot()[1]

    def retrieve_with_snapshot(
        self, *, rubric_version: str, paper_profile: Dict[str, Any],
        family_id: str, mode: str,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        events, snapshot = self._events_with_snapshot()
        context = self.retrieve(
            rubric_version=rubric_version,
            paper_profile=paper_profile,
            family_id=family_id,
            mode=mode,
            _events=events,
        )
        return context, snapshot

    def record(
        self,
        *,
        campaign_id: str,
        iteration: int,
        paper_profile: Dict[str, Any],
        batch_id: Optional[str] = None,
        report: Dict[str, Any],
        requested_mode: str,
        executed_mode: str,
        previous_report: Optional[Dict[str, Any]] = None,
        operations: Iterable[str] = (),
    ) -> bool:
        campaign = _identifier(campaign_id)
        if not campaign or iteration < 1:
            raise ValueError("Invalid committed event identity")
        campaign_fingerprint = hashlib.sha256(campaign.encode("utf-8")).hexdigest()[:24]
        path = self.root / f"{campaign_fingerprint}_{iteration:08d}.json"
        if path.exists():
            return False
        rubric = _identifier(report.get("rubric_version"))
        profile = _identifier(paper_profile.get("profile_key"))
        family = _identifier(report.get("layout_family"))
        issue_scopes = Counter(
            scope for issue in (report.get("issues") or [])
            if isinstance(issue, dict)
            if (scope := _identifier(issue.get("scope"))) in _SCOPES
        )
        allowed = Counter(
            operation for issue in (report.get("issues") or [])
            if isinstance(issue, dict)
            for raw in (issue.get("allowed_operations") or [])
            if (operation := _identifier(raw)) in _OPERATIONS
        )
        safe_operations = [
            value for raw in operations if (value := _identifier(raw)) in _OPERATIONS
        ][:20]
        previous = previous_report or {}
        comparable = (
            executed_mode == "improve"
            and bool(report.get("rubric_version"))
            and bool(report.get("layout_family"))
            and previous.get("rubric_version") == report.get("rubric_version")
            and previous.get("layout_family") == report.get("layout_family")
        )
        delta = (
            round(float(report.get("overall_score", 0)) - float(previous.get("overall_score", 0)), 2)
            if comparable else None
        )
        event = {
            "schema_version": 1,
            "campaign_fingerprint": campaign_fingerprint,
            "iteration": iteration,
            "batch_id": _identifier(batch_id),
            "rubric_version": rubric,
            "profile_key": profile,
            "layout_family": family,
            "requested_mode": _identifier(requested_mode),
            "executed_mode": _identifier(executed_mode),
            "accepted": bool(report.get("archive_eligible")),
            "template_eligible": bool(report.get("template_eligible")),
            "hard_gate_passed": bool(report.get("hard_gate_passed")),
            "overall_score": round(float(report.get("overall_score", 0)), 2),
            "dimension_scores": {
                key: round(float(value), 2)
                for raw, value in (report.get("dimension_scores") or {}).items()
                if (key := _identifier(raw)) in _DIMENSIONS
            },
            "issue_scopes": dict(issue_scopes),
            "allowed_operations": dict(allowed),
            "revision_operations": safe_operations,
            "score_delta": delta,
            "repair_association": (
                "single_operation_associated" if comparable and len(safe_operations) == 1
                else "multi_operation_unattributed" if comparable and safe_operations
                else "none"
            ),
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.stem}.", suffix=".tmp", dir=self.root
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(event, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return True

    def retrieve(
        self, *, rubric_version: str, paper_profile: Dict[str, Any],
        family_id: str, mode: str,
        _events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Return descriptive priors, never a winning template or prose."""
        rubric = _identifier(rubric_version)
        profile = _identifier(paper_profile.get("profile_key"))
        family = _identifier(family_id)
        matching: List[Dict[str, Any]] = []
        events = (
            _events if _events is not None
            else self._events_with_snapshot()[0]
        )
        for item in events:
            if (
                item.get("rubric_version") == rubric
                and item.get("layout_family") == family
            ):
                matching.append(item)
        local = [item for item in matching if item.get("profile_key") == profile]
        sample = local if len(local) >= 5 else matching
        issues = Counter()
        operations = Counter()
        for item in sample:
            issues.update(item.get("issue_scopes") or {})
            operations.update(item.get("allowed_operations") or {})
        repairs = {}
        if mode == "improve":
            for item in sample:
                if item.get("repair_association") != "single_operation_associated":
                    continue
                name = (item.get("revision_operations") or [None])[0]
                delta = item.get("score_delta")
                if name in _OPERATIONS and isinstance(delta, (int, float)):
                    repairs.setdefault(name, []).append(float(delta))
        associations = [
            {
                "operation": name,
                "sample_count": len(values),
                "mean_score_delta": round(sum(values) / len(values), 2),
                "causal_claim": False,
            }
            for name, values in repairs.items() if len(values) >= 2
        ]
        associations.sort(key=lambda item: (-item["sample_count"], -item["mean_score_delta"]))
        context = {
            "schema_version": 1,
            "scope": "same_profile_family" if len(local) >= 5 else "same_family",
            "sample_count": len(sample),
            "family_id": family,
            "acceptance_rate": round(sum(bool(item.get("accepted")) for item in sample) / len(sample), 3) if sample else None,
            "frequent_issue_scopes": [name for name, _ in issues.most_common(3)],
            "safe_operation_candidates": [name for name, _ in operations.most_common(3)] if mode == "improve" else [],
            "observed_repair_associations": associations[:3],
            "interpretation": "Descriptive aggregate only; preserve family diversity and verify every candidate independently.",
        }
        return context

    def reconcile_campaign(self, campaign_path: Path, paper_profile: Dict[str, Any]) -> int:
        """Replay committed iterations after a crash between commit and sharing."""
        restored = 0
        for marker in (Path(campaign_path) / "iterations").glob("*/COMPLETED.json"):
            try:
                completion = json.loads(marker.read_text(encoding="utf-8"))
                attempt_id = completion["attempt_id"]
                attempt = marker.parent / "attempts" / attempt_id
                report = json.loads((attempt / "critic_report.json").read_text(encoding="utf-8"))
                outcome = json.loads((attempt / "outcome.json").read_text(encoding="utf-8"))
                task = outcome.get("portfolio_task") or {}
                if task.get("mode") == "validate":
                    continue
                if self.record(
                    campaign_id=completion["campaign_id"],
                    iteration=int(completion["iteration"]),
                    paper_profile=paper_profile,
                    batch_id=completion.get("batch_id"),
                    report=report,
                    requested_mode=outcome.get("requested_mode", task.get("mode", "mixed")),
                    executed_mode=task.get("mode", "explore"),
                ):
                    restored += 1
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return restored
