"""Audit required scientific images in the actual PPTX and existing PDF export.

Image identities are checked in PPTX, painted bounds in PDF. Physical size is a
conservative floor, not a claim that every embedded axis label is legible.
"""

import hashlib

from src.layout.visual_requirements import board_audit, contract_for, enabled, file_digest


def artifact_identity(state):
    candidate = state.get('current_candidate') or {}
    return {'candidate_id': candidate.get('candidate_id'),
            'pptx_sha256': file_digest(candidate.get('pptx_path')),
            'png_sha256': file_digest(candidate.get('png_path'))}


def audit_rendered_visuals(state, page=None):
    if not enabled(state):
        return {'status': 'not_applicable', 'passed': True, 'issues': []}
    board = state.get('optimized_story_board') or state.get('story_board') or {}
    layout = state.get('styled_layout') or state.get('design_layout') or []
    contract = contract_for(state, board)
    report = board_audit(state, board, layout, contract=contract)
    report.update(artifact_identity(state), assets={})
    issues = report['issues']
    required = contract.get('required_visual_ids') or []
    if not required and not issues:
        report.update(status='not_applicable', passed=True)
        return report
    candidate = state.get('current_candidate') or {}
    if not report['pptx_sha256'] or not report['png_sha256']:
        issues.append({'code': 'REQUIRED_VISUAL_ARTIFACT_MISSING'})
    binding = (state.get('render_diagnostics') or {}).get('artifact_identity')
    if binding != {key: report[key] for key in ('candidate_id', 'pptx_sha256', 'png_sha256')}:
        issues.append({'code': 'REQUIRED_VISUAL_RENDER_IDENTITY_UNCONFIRMED'})
    if page is None:
        issues.append({'code': 'REQUIRED_VISUAL_RENDER_UNAVAILABLE'})
    else:
        try:
            from pptx import Presentation
            from PIL import Image
            from src.layout.visual_requirements import catalog
            presentation = Presentation(candidate['pptx_path'])
            if len(presentation.slides) != 1:
                raise ValueError('expected one poster slide')
            pictures = [s for s in presentation.slides[0].shapes if s.shape_type == 13]
            pdf_images = page.get_image_info()
            paint_log = page.get_bboxlog() if hasattr(page, 'get_bboxlog') else []
            drawings = page.get_drawings() if hasattr(page, 'get_drawings') else []
            used_pdf = set()
            config = state.get('critic_config') or {}
            policy = config.get('critical_visuals') or {}
            settings = (config.get('evaluators') or {}).get('visual_assets') or {}
            records = catalog(state)
            for vid in required:
                found = [s for s in pictures if s.name == 'PosterGenVisual:' + vid]
                targets = [e for e in layout if e.get('type') == 'visual' and e.get('visual_id') == vid]
                if len(found) != 1 or len(targets) != 1:
                    issues.append({'code': 'REQUIRED_VISUAL_EMBEDDING_MISSING_OR_DUPLICATED', 'visual_id': vid})
                    continue
                picture, target = found[0], targets[0]
                box = [picture.left / 914400, picture.top / 914400,
                       picture.width / 914400, picture.height / 914400]
                expected = [float(target[k]) for k in ('x', 'y', 'width', 'height')]
                sha = hashlib.sha256(picture.image.blob).hexdigest()
                entry = {'box_inches': box, 'sha256': sha}
                report['assets'][vid] = entry
                if sha != (contract.get('catalog', {}).get(vid) or {}).get('sha256'):
                    issues.append({'code': 'REQUIRED_VISUAL_EMBEDDED_SOURCE_MISMATCH', 'visual_id': vid})
                if max(abs(a-b) for a, b in zip(box, expected)) > 0.03:
                    issues.append({'code': 'REQUIRED_VISUAL_PLACEMENT_MISMATCH', 'visual_id': vid})
                if any(abs(getattr(picture, 'crop_' + side)) > 0.0001 for side in ('left', 'right', 'top', 'bottom')):
                    issues.append({'code': 'REQUIRED_VISUAL_CROPPED', 'visual_id': vid})
                x, y, w, h = box
                minimum_width = float(policy.get('minimum_table_width_inches' if vid.startswith('table_')
                                                  else 'minimum_figure_width_inches', 3.0 if vid.startswith('table_') else 2.0))
                if (w < minimum_width or min(w, h) < float(policy.get('minimum_short_edge_inches', 0.5))
                        or min(x, y) < -0.02 or x+w > float(state['poster_width'])+0.02
                        or y+h > float(state['poster_height'])+0.02):
                    issues.append({'code': 'REQUIRED_VISUAL_TOO_SMALL_OR_OUTSIDE', 'visual_id': vid})
                with Image.open(records[vid]['path']) as image:
                    pw, ph = image.size
                if h <= 0 or abs(w / h - pw / ph) / (pw / ph) > float(settings.get('maximum_aspect_deviation', 0.03)):
                    issues.append({'code': 'REQUIRED_VISUAL_DISTORTED', 'visual_id': vid})
                if w <= 0 or h <= 0 or min(pw / w, ph / h) < float(settings.get('minimum_effective_dpi', 72)):
                    issues.append({'code': 'REQUIRED_VISUAL_LOW_RESOLUTION', 'visual_id': vid})
                rect = (x*72, y*72, (x+w)*72, (y+h)*72)
                matches = [i for i, info in enumerate(pdf_images) if i not in used_pdf
                           and max(abs(a-b) for a, b in zip(rect, info['bbox'])) <= 2.2]
                if len(matches) != 1:
                    issues.append({'code': 'REQUIRED_VISUAL_PDF_PLACEMENT_UNCONFIRMED', 'visual_id': vid})
                else:
                    used_pdf.add(matches[0])
                    entry['pdf_box_points'] = list(pdf_images[matches[0]]['bbox'])
                    paints = [i for i, (kind, bounds, *_) in enumerate(paint_log)
                              if kind == 'fill-image' and max(abs(a-b) for a, b in zip(rect, bounds)) <= 2.2]
                    if len(paints) == 1:
                        for drawing in drawings:
                            if (drawing.get('seqno', -1) <= paints[0] or drawing.get('fill') is None
                                    or drawing.get('fill_opacity', 1) < 0.98):
                                continue
                            for command in drawing.get('items') or []:
                                if command[0] != 're':
                                    continue
                                cover = command[1]
                                overlap = max(0, min(rect[2], cover[2])-max(rect[0], cover[0])) * max(
                                    0, min(rect[3], cover[3])-max(rect[1], cover[1]))
                                if overlap / max(1, (rect[2]-rect[0])*(rect[3]-rect[1])) >= 0.95:
                                    issues.append({'code': 'REQUIRED_VISUAL_COVERED', 'visual_id': vid})
                                    break
        except (OSError, ValueError, KeyError, RuntimeError, ImportError) as exc:
            issues.append({'code': 'REQUIRED_VISUAL_RENDER_UNAVAILABLE', 'reason': type(exc).__name__})
    report.update(status='failed' if issues else 'passed', passed=not issues)
    return report


def admission_audit(state):
    """Only current, digest-bound rendering evidence can certify admission."""
    board = state.get('optimized_story_board') or state.get('story_board') or {}
    report = board_audit(state, board, state.get('styled_layout') or state.get('design_layout') or [])
    if not enabled(state):
        return report
    if not report.get('required_visual_ids') and report['passed']:
        report['status'] = 'not_applicable'
        return report
    actual = (state.get('render_fit_report') or {}).get('visual_audit') or {}
    issues = report['issues']
    if not actual.get('passed') or actual.get('status') != 'passed':
        issues.extend(actual.get('issues') or [{'code': 'REQUIRED_VISUAL_RENDER_UNCONFIRMED'}])
    identity = artifact_identity(state)
    if (not identity['pptx_sha256'] or not identity['png_sha256']
            or any(actual.get(k) != v for k, v in identity.items())
            or actual.get('contract_digest') != report.get('contract_digest')):
        issues.append({'code': 'REQUIRED_VISUAL_AUDIT_STALE'})
    report.update(status='failed' if issues else 'passed', passed=not issues, rendered=actual)
    return report
