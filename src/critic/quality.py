"""Measured palette contrast, color provenance, and visual-asset diagnostics."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from src.critic.base import CriticContext, EvaluationResult, issue


def _settings(context: CriticContext, name: str) -> Dict[str, Any]:
    return context.config.get("evaluators", {}).get(name, {})


def _result(
    context: CriticContext,
    name: str,
    *,
    passed: bool,
    issues: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> EvaluationResult:
    settings = _settings(context, name)
    return EvaluationResult(
        evaluator=name,
        version=str(settings.get("version", "1.0.0")),
        hard_gate=bool(settings.get("hard_gate", False)),
        passed=passed,
        issues=issues,
        metadata=metadata or {},
    )


def _sections(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    board = state.get("optimized_story_board") or state.get("story_board") or {}
    return [
        section
        for section in board.get("spatial_content_plan", {}).get("sections", [])
        if isinstance(section, dict) and section.get("section_id")
    ]


def _hex_rgb(value: Any) -> Optional[Tuple[int, int, int]]:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not match:
        return None
    raw = match.group(1)
    return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))


def _luminance(rgb: Tuple[int, int, int]) -> float:
    values = []
    for channel in rgb:
        normalized = channel / 255.0
        values.append(
            normalized / 12.92
            if normalized <= 0.03928
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def _contrast(left: Any, right: Any) -> Optional[float]:
    left_rgb = _hex_rgb(left)
    right_rgb = _hex_rgb(right)
    if left_rgb is None or right_rgb is None:
        return None
    high, low = sorted((_luminance(left_rgb), _luminance(right_rgb)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ColorQualityEvaluator:
    """Check palette validity, provenance, semantic consistency, and WCAG contrast."""

    name = "color_quality"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        scheme = context.state.get("color_scheme") or {}
        threshold = float(settings.get("minimum_contrast_ratio", 4.5))
        problems: List[Dict[str, Any]] = []
        palette_keys = ("theme", "mono_light", "mono_dark", "text", "text_on_theme", "contrast")
        invalid = [key for key in palette_keys if _hex_rgb(scheme.get(key)) is None]
        if invalid:
            problems.append(issue(
                "COLOR-PALETTE-INVALID",
                severity="critical",
                scope="color",
                observation="The resolved poster palette contains missing or invalid colors",
                evidence={"invalid_keys": invalid},
                required_outcome="Regenerate a complete accessible palette from an approved source",
                allowed_operations=["use_accessible_palette_variant", "normalize_semantic_colors"],
            ))

        backgrounds = {"white": "#FFFFFF"}
        visible_sections = _sections(context.state)
        if any((s.get('editorial') or {}).get('active') for s in visible_sections):
            containers = [e for e in (context.state.get('styled_layout') or context.state.get('design_layout') or [])
                          if e.get('type') == 'section_container']
            for section in containers or visible_sections:
                explicit = section.get('emphasis_background') or (section.get('editorial') or {}).get('background')
                current = (context.state.get('editorial_version') == 'poster_editorial_v1'
                           and context.state.get('generation_route') == 'optimization_family')
                if ((bool(explicit) if current else int(section.get('importance_level', 2) or 2) == 1)
                        and not section.get('emphasis_disabled')
                        and not (section.get('editorial') or {}).get('emphasis_disabled')):
                    color = (section.get('emphasis_background') or (section.get('editorial') or {}).get('background')
                             or scheme.get('mono_light'))
                    if _hex_rgb(color):
                        backgrounds['module_' + str(section['section_id'])] = color
        elif _hex_rgb(scheme.get("mono_light")):
            backgrounds["mono_light"] = scheme["mono_light"]
        pairs = []
        if not invalid:
            styled = context.state.get('styled_layout') or context.state.get('design_layout') or []
            bodies = ([e for e in styled if e.get('section_id') and e.get('type') == 'text']
                      if any((s.get('editorial') or {}).get('active') for s in visible_sections) else [])
            if bodies:
                from utils.text_formatting import tokenize_formatting
                for element in bodies:
                    name = 'module_' + str(element.get('section_id'))
                    background = backgrounds.get(name, '#FFFFFF')
                    pairs.append(('body_text', name, element.get('font_color', scheme['text']), background))
                    actual_colors = {s['color'] for s in tokenize_formatting(element.get('content') or '') if s.get('color')}
                    for i, ink in enumerate(sorted(actual_colors)):
                        pairs.append(('highlight_' + str(i), name, ink, background))
            else:
                by_id = {'module_' + str(s['section_id']): s.get('editorial') or {} for s in visible_sections}
                for background_name, background in backgrounds.items():
                    meta = by_id.get(background_name, {})
                    pairs.append(("body_text", background_name, meta.get('text_color', scheme['text']), background))
                    pairs.append(("highlight", background_name, meta.get('accent_color', scheme['contrast']), background))
            pairs.append(("text_on_theme", "theme", scheme["text_on_theme"], scheme["theme"]))

        panel_ratios = {name: round(_contrast(background, '#FFFFFF') or 0, 4)
                        for name, background in backgrounds.items() if name.startswith('module_')}
        visibility = float((context.config.get('poster_editorial') or {}).get('minimum_panel_canvas_contrast', 1.12))
        faint = {name: value for name, value in panel_ratios.items() if value < visibility}
        if faint:
            problems.append(issue('COLOR-EMPHASIS-FAINT', severity='warning', scope='color',
                observation='A highlighted module background is difficult to distinguish from the canvas',
                evidence={'panel_canvas_contrasts': faint, 'design_target': visibility},
                required_outcome='Resolve a visible theme panel and accessible foregrounds jointly',
                allowed_operations=['use_accessible_palette_variant'],
                forbidden_operations=['supply_raw_hex_color', 'reduce_font_below_minimum']))

        ratios: Dict[str, float] = {}
        failed_pairs = []
        for role, background_name, foreground, background in pairs:
            ratio = _contrast(foreground, background)
            if ratio is None:
                continue
            key = f"{role}_on_{background_name}"
            ratios[key] = round(ratio, 3)
            if ratio < threshold:
                failed_pairs.append({"pair": key, "ratio": round(ratio, 3)})
        if failed_pairs:
            problems.append(issue(
                "COLOR-CONTRAST-INSUFFICIENT",
                severity="critical",
                scope="color",
                observation="One or more rendered text roles fail the configured WCAG contrast ratio",
                evidence={"minimum_ratio": threshold, "failed_pairs": failed_pairs},
                required_outcome="Use a deterministic accessible foreground/palette variant with at least 4.5:1 contrast",
                allowed_operations=["repair_text_contrast", "use_accessible_palette_variant", "reduce_accent_density"],
                forbidden_operations=["supply_raw_hex_color", "reduce_font_below_minimum"],
            ))

        provenance = context.state.get("color_provenance") or {}
        source_known = str(provenance.get("source", "")).lower() in {
            "affiliation_logo", "key_visual", "configured_fallback", "critic_accessible_variant"
        }
        if not source_known:
            problems.append(issue(
                "COLOR-SOURCE-UNKNOWN",
                severity="warning",
                scope="color",
                observation="The palette source is not recorded",
                evidence={"provenance": provenance},
                required_outcome="Record whether the theme came from the affiliation logo, key visual, or configured fallback",
                allowed_operations=["normalize_semantic_colors"],
            ))

        critical = any(item.get("severity") == "critical" for item in problems)
        return _result(
            context,
            self.name,
            passed=not critical,
            issues=problems,
            metadata={
                "contrast_ratios": ratios,
                "palette_source": provenance,
                "panel_canvas_contrasts": panel_ratios,
            },
        )


def _asset_record(state: Dict[str, Any], visual_id: str) -> Optional[Dict[str, Any]]:
    raw = str(visual_id)
    if raw.startswith("figure_"):
        key = raw[len("figure_"):]
        return (state.get("images") or {}).get(key) or (state.get("images") or {}).get(raw)
    if raw.startswith("table_"):
        key = raw[len("table_"):]
        return (state.get("tables") or {}).get(key) or (state.get("tables") or {}).get(raw)
    return (state.get("images") or {}).get(raw) or (state.get("tables") or {}).get(raw)


class VisualAssetEvaluator:
    """Validate provenance, uniqueness, aspect ratio, and effective resolution."""

    name = "visual_assets"

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        settings = _settings(context, self.name)
        state = context.state
        visual_ids = [
            str(asset.get("visual_id"))
            for section in _sections(state)
            for asset in section.get("visual_assets", [])
            if isinstance(asset, dict) and asset.get("visual_id")
        ]
        counts = Counter(visual_ids)
        layout_visuals = {
            str(item.get("visual_id")): item
            for item in (state.get("styled_layout") or state.get("design_layout") or [])
            if item.get("type") == "visual" and item.get("visual_id")
        }
        problems: List[Dict[str, Any]] = []
        metadata_assets: Dict[str, Any] = {}
        for visual_id in sorted(set(visual_ids)):
            record = _asset_record(state, visual_id)
            if not isinstance(record, dict):
                problems.append(issue(
                    f"VISUAL-ASSET-UNKNOWN-{visual_id}",
                    severity="critical",
                    scope="visual_relevance",
                    location={"visual_id": visual_id},
                    observation="The poster references a visual that is not present in the approved paper assets",
                    required_outcome="Remove or replace the visual with an approved paper figure/table",
                    allowed_operations=["remove_visual", "replace_visual"],
                    forbidden_operations=["invent_visual"],
                ))
                continue
            path = Path(str(record.get("path") or ""))
            if not path.is_file():
                problems.append(issue(
                    f"VISUAL-ASSET-MISSING-{visual_id}",
                    severity="critical",
                    scope="visual_relevance",
                    location={"visual_id": visual_id},
                    observation="An approved visual asset file is missing",
                    required_outcome="Restore the extracted asset or remove it from the poster",
                    allowed_operations=["remove_visual", "replace_visual", "rerender_candidate"],
                    forbidden_operations=["invent_visual"],
                ))
                continue

            entry: Dict[str, Any] = {"path": str(path), "placements": counts[visual_id]}
            rendered = layout_visuals.get(visual_id)
            try:
                with Image.open(path) as image:
                    pixel_width, pixel_height = image.size
                source_aspect = pixel_width / max(pixel_height, 1)
                entry.update({
                    "pixel_size": [pixel_width, pixel_height],
                    "source_aspect": round(source_aspect, 4),
                })
                if rendered:
                    rendered_width = float(rendered.get("width", 0.0))
                    rendered_height = float(rendered.get("height", 0.0))
                    rendered_aspect = rendered_width / rendered_height if rendered_height > 0 else 0.0
                    deviation = abs(rendered_aspect - source_aspect) / source_aspect if source_aspect else 1.0
                    dpi = pixel_width / rendered_width if rendered_width > 0 else 0.0
                    entry.update({
                        "rendered_aspect": round(rendered_aspect, 4),
                        "aspect_deviation": round(deviation, 4),
                        "effective_dpi": round(dpi, 2),
                    })
                    if deviation > float(settings.get("maximum_aspect_deviation", 0.03)):
                        problems.append(issue(
                            f"VISUAL-ASSET-DISTORTED-{visual_id}",
                            severity="major",
                            scope="visual_relevance",
                            location={"visual_id": visual_id},
                            observation="A visual is rendered with a distorted aspect ratio",
                            evidence={"aspect_deviation": round(deviation, 4)},
                            required_outcome="Restore the source aspect ratio through deterministic layout",
                            allowed_operations=["restore_visual_aspect_ratio", "move_visual"],
                        ))
                    if dpi < float(settings.get("minimum_effective_dpi", 72.0)):
                        problems.append(issue(
                            f"VISUAL-ASSET-LOW-RESOLUTION-{visual_id}",
                            severity="major",
                            scope="visual_relevance",
                            location={"visual_id": visual_id},
                            observation="A visual has insufficient effective resolution at its rendered size",
                            evidence={"effective_dpi": round(dpi, 2)},
                            required_outcome="Use a smaller rendering or another approved higher-resolution visual",
                            allowed_operations=["move_visual", "replace_visual", "remove_visual"],
                            forbidden_operations=["invent_visual"],
                        ))
            except Exception:
                problems.append(issue(
                    f"VISUAL-ASSET-UNREADABLE-{visual_id}",
                    severity="critical",
                    scope="visual_relevance",
                    location={"visual_id": visual_id},
                    observation="A paper visual cannot be decoded as an image",
                    required_outcome="Remove or replace the unreadable asset",
                    allowed_operations=["remove_visual", "replace_visual"],
                ))
            metadata_assets[visual_id] = entry

        duplicates = sorted(item for item, count in counts.items() if count > 1)
        if duplicates:
            problems.append(issue(
                "VISUAL-ASSET-DUPLICATED",
                severity="major",
                scope="visual_relevance",
                observation="The same paper visual appears in more than one poster section",
                evidence={"visual_ids": duplicates},
                required_outcome="Keep one purposeful occurrence of each visual",
                allowed_operations=["remove_visual", "replace_visual"],
            ))

        critical = any(item.get("severity") == "critical" for item in problems)
        source_manifest = state.get("layout_visual_source_manifest") or {}
        source_ids = {
            str(visual_id)
            for ids in source_manifest.values()
            for visual_id in ids
        }
        omitted_source_ids = sorted(source_ids - set(visual_ids))
        key_visual = (state.get("classified_visuals") or {}).get("key_visual")
        available_ids = {
            f"{prefix}_{key}"
            for prefix, field in (("figure", "images"), ("table", "tables"))
            for key in (state.get(field) or {})
        }
        curated_ids = {
            str(item.get("visual_id"))
            for section in (state.get("story_board") or {}).get("spatial_content_plan", {}).get("sections", [])
            for item in section.get("visual_assets") or []
            if isinstance(item, dict) and item.get("visual_id")
        }
        return _result(
            context,
            self.name,
            passed=not critical,
            issues=problems,
            metadata={
                "assets": metadata_assets,
                "source_visual_selection": {
                    "available_visual_ids": sorted(available_ids),
                    "curated_visual_ids": sorted(curated_ids),
                    "uncurated_visual_ids": sorted(available_ids - curated_ids),
                    "visible_visual_ids": sorted(set(visual_ids)),
                    "key_visual_uncurated": bool(
                        isinstance(key_visual, str)
                        and key_visual in available_ids - curated_ids
                    ),
                    "classification_policy_version": (
                        (state.get("visual_classification_report") or {}).get("policy_version")
                        or "legacy_unversioned"
                    ),
                    "source_visual_ids": sorted(source_ids),
                    "omitted_source_visual_ids": omitted_source_ids,
                    "key_visual_omitted": bool(
                        isinstance(key_visual, str) and key_visual in omitted_source_ids
                    ),
                    "capacity_restore_attempts": (
                        (state.get("capacity_repair_report") or {}).get("visual_restoration") or []
                    ),
                },
            },
        )
