"""Final-Critic evidence views; never rewrite generation state or source artifacts."""
from copy import deepcopy
import math
from pathlib import Path

from src.layout.element_identity import identified_layout

VERSION = 'critic_evidence_v1'
SOURCE_PRIORITY = {
    'primary': ['original_text'],
    'advisory': ['proofread_text', 'spelling_review', 'structured_sections',
                 'narrative_content', 'classified_visuals'],
    'conflict_rule': 'Check original equations and prose; auxiliary summaries cannot overrule them.',
    'extraction_limit': 'original_text is a PDF extraction, not an infallible transcription; '
                        'report unresolved formula/table extraction as uncertainty.',
}


def _box(element):
    try:
        result = tuple(float(element[k]) for k in ('x', 'y', 'width', 'height'))
        return result if all(math.isfinite(v) for v in result) and min(result[2:]) > 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def geometry_view(measurement, layout):
    """Keep original finding IDs/numbers, but identify the boxes and ratio denominator."""
    from src.critic.evaluators import GeometryEvaluator
    result = deepcopy(measurement)
    aliases = {}
    for index, (raw, element) in enumerate(zip(layout, identified_layout(layout))):
        if raw.get('type') in GeometryEvaluator._OVERLAP_TYPES:
            aliases.setdefault(GeometryEvaluator._identity(raw, index), []).append(element)
    for finding in result.get('findings', []):
        if not str(finding.get('issue_id', '')).startswith('GEOMETRY-OVERLAP-'):
            continue
        finding['observation'] = 'Planned element bounding boxes intersect; glyph occlusion is not established'
        evidence = finding.setdefault('evidence', {})
        evidence.update(measurement_kind='planned_bounding_box_intersection',
                        glyph_occlusion='not_established')
        boxes = []
        for identity in finding.get('location', {}).get('element_ids', []):
            matches = aliases.get(identity, [])
            box = _box(matches[0]) if len(matches) == 1 else None
            if box:
                boxes.append({'element_id': matches[0]['id'], 'element_type': matches[0]['type'],
                              'box_inches': list(box), 'area_square_inches': box[2] * box[3]})
        if len(boxes) != 2:
            evidence['ratio_denominator'] = {'rule': 'smaller_box_area', 'status': 'unresolved'}
            continue
        area = min(b['area_square_inches'] for b in boxes)
        evidence['element_boxes'] = boxes
        evidence['ratio_denominator'] = {'rule': 'smaller_box_area', 'status': 'resolved',
            'area_square_inches': area,
            'element_ids': [b['element_id'] for b in boxes if b['area_square_inches'] == area]}
        overlap = evidence.get('overlap_area_inches_squared')
        if type(overlap) in (int, float) and math.isfinite(overlap):
            evidence['fraction_of_each_box'] = {
                b['element_id']: round(overlap / b['area_square_inches'], 6) for b in boxes}
    return result


def diagnostic_provenance(state):
    """Mixed visible bounds never become a completely measured glyph clearance."""
    report = state.get('render_fit_report') or {}
    matched = {b['element_id'] for b in report.get('matched_text_boxes', []) if b.get('element_id')}
    elements = identified_layout(state.get('styled_layout') or state.get('design_layout') or [])
    unmatched = set(report.get('unmatched_text_ids') or [])
    texts = {}
    for e in elements:
        if e.get('type') in {'text', 'section_title'} and e.get('id'):
            identity = e['id']
            texts[identity] = {'module_id': e.get('section_id', ''),
                'bounds_basis': 'rendered_glyph_bounds' if identity in matched else 'planned_box_fallback',
                'visibility': 'not_certified' if identity not in matched else 'text_matched_not_occlusion_test'}
            if identity not in matched:
                unmatched.add(identity)
    return {'version': VERSION, 'render_fit_status': report.get('status', 'unavailable'),
        'render_fit_conclusive': report.get('conclusive', False), 'text_bounds': texts,
        'unmatched_text_ids': sorted(unmatched),
        'visible_gap_basis': 'mixed_rendered_glyphs_and_planned_boxes',
        'gap_limit': 'Gaps involving unmatched text include planned-box fallbacks, not fully measured '
                     'glyph clearance. Matching or an empty issues list is not proof of no occlusion.',
        'whitespace_basis': 'compiled_section_containers_not_blank_pixel_fraction'}



def annotate_gaps(value, provenance):
    """Label copies of clearance estimates without changing numbers or source reports."""
    if isinstance(value, dict):
        if 'gap_inches' in value and 'after_section_id' in value and 'before_section_id' in value:
            modules = {value['after_section_id'], value['before_section_id']}
            rows = {identity: row for identity, row in provenance['text_bounds'].items()
                    if row['module_id'] in modules}
            fallbacks = [identity for identity, row in rows.items()
                         if row['bounds_basis'] == 'planned_box_fallback']
            value['measurement_basis'] = ('includes_planned_text_fallback' if fallbacks else
                'rendered_text_with_planned_nontext_bounds' if rows else 'planned_bounds_unverified')
            value['unmatched_text_ids'] = fallbacks
        for child in list(value.values()):
            annotate_gaps(child, provenance)
    elif isinstance(value, list):
        for child in value:
            annotate_gaps(child, provenance)


def _xml_color(node, theme, mapping, placeholder=None):
    """Resolve only unmodified solid colors; unsupported effects remain unknown."""
    if node is None or len(node):
        return None
    from lxml.etree import QName
    kind, value = QName(node).localname, node.get('val')
    if kind == 'srgbClr':
        return '#' + value.upper()
    if kind == 'sysClr' and node.get('lastClr'):
        return '#' + node.get('lastClr').upper()
    if kind == 'schemeClr':
        if value == 'phClr':
            return placeholder
        found = theme.xpath('./a:themeElements/a:clrScheme/a:' + mapping.get(value, value))
        return _xml_color(found[0][0], theme, mapping) if found and len(found[0]) else None
    return None


def _canvas(slide):
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    from pptx.oxml import parse_xml
    theme = parse_xml(slide.slide_layout.slide_master.part.part_related_by(RT.THEME).blob)
    owners = [slide, slide.slide_layout, slide.slide_layout.slide_master]
    maps = owners[-1]._element.xpath('./p:clrMap')
    mapping = dict(maps[0].attrib) if maps else {}
    for owner in reversed(owners[:-1]):
        overrides = owner._element.xpath('./p:clrMapOvr/a:overrideClrMapping')
        if overrides:
            mapping.update(overrides[0].attrib)
    for owner in owners:
        backgrounds = owner._element.xpath('./p:cSld/p:bg')
        if not backgrounds:
            continue
        background = backgrounds[0]
        fills = background.xpath('./p:bgPr/a:solidFill')
        if fills:
            return _xml_color(fills[0][0], theme, mapping), theme, mapping
        refs = background.xpath('./p:bgRef')
        if refs:
            ref = refs[0]
            color = _xml_color(ref[0], theme, mapping) if len(ref) else None
            styles = theme.xpath('./a:themeElements/a:fmtScheme/a:bgFillStyleLst')
            index = int(ref.get('idx', '0')) - 1001
            if styles and 0 <= index < len(styles[0]):
                fill = styles[0][index]
                if fill.tag.endswith('}solidFill') and len(fill):
                    return _xml_color(fill[0], theme, mapping, color), theme, mapping
        return None, theme, mapping
    return None, theme, mapping


def _intersects(a, b):
    return (min(a[0]+a[2], b[0]+b[2]) > max(a[0], b[0]) and
            min(a[1]+a[3], b[1]+b[3]) > max(a[1], b[1]))


def _contains(outer, inner):
    return (outer[0] <= inner[0] and outer[1] <= inner[1] and
            outer[0]+outer[2] >= inner[0]+inner[2] and outer[1]+outer[3] >= inner[1]+inner[3])


def applied_colors(state):
    """Read exported PPTX text/fills, binding only unique exact geometry matches."""
    from pptx import Presentation
    from src.critic.quality import _contrast
    from utils.persistence import file_hash
    path = (state.get('current_candidate') or {}).get('pptx_path')
    unavailable = {'status': 'unavailable', 'source': 'exported_pptx_styles',
                   'pixel_visibility': 'not_verified', 'text_elements': []}
    if not path or not Path(path).is_file():
        return {**unavailable, 'reason': 'Final PPTX unavailable; never substitute candidate palette.'}
    try:
        presentation = Presentation(path)
        if len(presentation.slides) != 1:
            return {**unavailable, 'reason': 'Expected one final poster slide.'}
        slide = presentation.slides[0]
        canvas, theme, mapping = _canvas(slide)
        shapes = list(slide.shapes)
        shape_boxes = [tuple(v / 914400 for v in (s.left, s.top, s.width, s.height)) for s in shapes]
        rows = []
        for element in identified_layout(state.get('styled_layout') or state.get('design_layout') or []):
            if element.get('type') not in {'title', 'section_title', 'text', 'mixed'} or not element.get('id'):
                continue
            box = _box(element)
            candidates = [i for i, (shape, bounds) in enumerate(zip(shapes, shape_boxes))
                          if box and shape.has_text_frame and shape.text.strip() and
                          all(abs(a-b) < .001 for a, b in zip(box, bounds))]
            row = {'element_id': element['id'], 'module_id': element.get('section_id', ''),
                   'status': 'unavailable', 'foreground_colors': [], 'background_colors': [], 'style_contrast_pairs': []}
            if len(candidates) != 1:
                rows.append(row)
                continue
            index = candidates[0]
            colors, unknown_ink = set(), False
            for paragraph in shapes[index].text_frame.paragraphs:
                default = paragraph._p.xpath('./a:pPr/a:defRPr/a:solidFill/*')
                for run in paragraph.runs:
                    if not run.text.strip():
                        continue
                    explicit = run._r.xpath('./a:rPr/a:solidFill/*') or default
                    color = _xml_color(explicit[0], theme, mapping) if explicit else None
                    if color:
                        colors.add(color)
                    else:
                        unknown_ink = True
            backgrounds, unknown_background = {canvas} if canvas else set(), canvas is None
            for shape, bounds in zip(shapes[:index+1], shape_boxes[:index+1]):
                if not _intersects(bounds, box):
                    continue
                fills = shape._element.xpath('./p:spPr/a:solidFill/*')
                if fills:
                    color = _xml_color(fills[0], theme, mapping)
                    if _contains(bounds, box):
                        backgrounds, unknown_background = set(), color is None
                    if color:
                        backgrounds.add(color)
                    else:
                        unknown_background = True
                elif shape._element.xpath('./p:spPr/a:gradFill|./p:spPr/a:pattFill|./p:blipFill'):
                    unknown_background = True
            row.update(status='partial' if unknown_ink or unknown_background else 'resolved',
                foreground_colors=sorted(colors), background_colors=sorted(backgrounds),
                style_contrast_pairs=[{'foreground': ink, 'background': bg, 'ratio': round(_contrast(ink, bg), 3)}
                                for ink in sorted(colors) for bg in sorted(backgrounds)],
                coverage='Style pairs only; partial fills may cover different parts of the textbox. '
                         'Color-set combinations are not per-glyph samples or proof each combination occurs. '
                         'No inference of glyph visibility or image-internal lettering.')
            rows.append(row)
        return {'status': 'partial' if canvas is None or any(r['status'] != 'resolved' for r in rows) else 'resolved',
                'source': 'exported_pptx_styles', 'artifact_sha256': file_hash(path),
                'canvas_color': canvas, 'pixel_visibility': 'not_verified', 'text_elements': rows}
    except Exception as exc:
        return {**unavailable, 'reason': 'PPTX style inspection failed: ' + type(exc).__name__}


def measurement_view(state):
    layout = state.get('styled_layout') or state.get('design_layout') or []
    measurements = deepcopy(state.get('critic_measurement_evidence') or {})
    if 'geometry' in measurements:
        measurements['geometry'] = geometry_view(measurements['geometry'], layout)
    color = measurements.get('color_quality', {})
    if color.get('status') == 'measured':
        metadata = color.setdefault('metadata', {})
        if 'contrast_ratios' in metadata:
            metadata['candidate_or_layout_contrast_ratios'] = metadata.pop('contrast_ratios')
        for finding in color.get('findings', []):
            if finding.get('issue_id') == 'COLOR-CONTRAST-INSUFFICIENT':
                finding['observation'] = 'Legacy palette/layout contrast calculation is below threshold; rendered use requires artifact verification'
                finding.setdefault('evidence', {})['rendered_use_verified'] = False
        metadata['contrast_scope'] = ('Legacy palette/layout calculations, not proof each pair is rendered. '
                                      'Use applied_colors for artifact-bound pairs and PNG for visible appearance.')
    annotate_gaps(measurements, diagnostic_provenance(state))
    return {'version': VERSION, 'measurements': measurements,
            'authored_elements': deepcopy(identified_layout(layout)),
            'candidate_palette': {'role': 'design_candidates_not_rendered_facts',
                                 'colors': deepcopy(state.get('color_scheme') or {}),
                                 'provenance': deepcopy(state.get('color_provenance') or {})},
            'applied_colors': applied_colors(state)}
