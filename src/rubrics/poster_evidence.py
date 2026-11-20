"""Project frozen source and final-score artifacts into evidence for quality mining."""
from src.rubrics.storage import read
from utils.persistence import read_json


def _fields(record, names):
    return {key: record[key] for key in names if key in record}


def _same_score(first, second):
    return type(first) in (int, float) and type(first) is type(second) and first == second


def _paper_evidence(bundle):
    paper = read(bundle / 'refinement' / 'paper.json')
    source = _fields(paper, ('original_text',))
    if not source.get('original_text'):
        # Keep the attribution explicit when only a transcription is available.
        source.update(_fields(paper, ('proofread_text',)))
    if paper.get('visuals'):
        source['visuals'] = {
            identifier: _fields(asset, ('caption', 'page', 'block_id', 'block_type', 'width', 'height', 'aspect'))
            for identifier, asset in paper['visuals'].items()
        }
    if paper.get('extraction_quality'):
        source['extraction_quality'] = _fields(paper['extraction_quality'],
            ('status', 'uncertain', 'warnings', 'scientific_truth_verified'))
    return source


def _score_evidence(report):
    score = _fields(report, ('overall_score', 'score_maximum', 'high_score_threshold',
                             'dimension_scores', 'submetric_scores', 'submetric_grades'))
    # G's reasons, locations and paper support accompany the scores. Its operational
    # advice, stage permissions, request text and generated layout plans stay local.
    observation_fields = ('issue_id', 'severity', 'scope', 'location', 'observation', 'original_support', 'note_type')
    for key in ('positive_patterns', 'issues', 'review_notes'):
        if key in report:
            score[key] = [_fields(entry, observation_fields) for entry in report[key]]
    for issue, original in zip(score.get('issues', []), report.get('issues', [])):
        evidence = original.get('evidence', {})
        if isinstance(evidence, dict):
            issue['evidence'] = _fields(evidence, (
                'original_support', 'locations', 'element_id', 'other_section_id', 'other_element_type',
                'overlap_ratio', 'overlap_area_inches_squared', 'overflow_right_inches', 'overflow_bottom_inches',
                'overlap_width_inches', 'overlap_height_inches', 'effective_dpi', 'aspect_deviation',
                'gap_inches', 'gap_body_lines', 'overflow_inches'))
    if 'submetric_assessments' in report:
        assessments = {}
        for name, entry in report['submetric_assessments'].items():
            assessment = _fields(entry, ('score', 'grade', 'points', 'maximum_score', 'assessment_status', 'reason', 'uncertainty'))
            if _same_score(assessment.get('score'), assessment.get('grade')):
                del assessment['score']
            assessment['evidence'] = []
            for item in entry.get('evidence', []):
                evidence = _fields(item, ('observation', 'original_support', 'measurement_id',
                    'finding_id', 'locations', 'module_id', 'element_id'))
                for locator in ('measurement_id', 'finding_id', 'module_id', 'element_id'):
                    if evidence.get(locator) == '':
                        del evidence[locator]
                assessment['evidence'].append(evidence)
            assessments[name] = assessment
        score['submetric_assessments'] = assessments
        # A partial or differently weighted historical map still carries information.
        for table, field in (('submetric_scores', 'points'), ('submetric_grades', 'grade')):
            values = score.get(table)
            if (isinstance(values, dict) and values.keys() == assessments.keys() and
                    all(_same_score(value, assessments[name].get(field)) for name, value in values.items())):
                del score[table]
    return score


def _final_measurements(report):
    measures = report.get('measurement_evidence', {})
    diagnostics = {}
    for key, fields in (
        ('typography', ('checked_text_elements', 'font_families', 'emphasis_ratio', 'font_sizes')),
        ('color_quality', ('contrast_ratios', 'panel_canvas_contrasts')),
        ('column_balance', ('group_kind', 'region_utilization', 'utilization_spread')),
    ):
        if key in measures:
            diagnostics[key] = _fields(measures[key].get('metadata', {}), fields)
    if 'visual_assets' in measures:
        assets = measures['visual_assets'].get('metadata', {}).get('assets', {})
        diagnostics['visual_assets'] = {key: _fields(asset, ('placements', 'pixel_size', 'source_aspect',
            'rendered_aspect', 'aspect_deviation', 'effective_dpi')) for key, asset in assets.items()}
    return diagnostics


def extractor_evidence(bundle, report, variant):
    """Use the evaluated poster's measurements. P1 cannot fall back to P0 fit data."""
    diagnostics = _final_measurements(report)
    if variant == 'P1':
        selected = bundle / 'refinement' / 'selected_state.json'
        fit = read(selected).get('render_fit_report') if selected.exists() else None
    elif variant == 'P0':
        exported = bundle / 'diagnostics' / 'render_fit_report.json'
        fit = read_json(exported) if exported.exists() else None
    else:
        raise ValueError('Unknown final poster selection')
    if fit:
        fit_view = _fields(fit, ('status', 'conclusive', 'measurement_source', 'text_coverage', 'unmatched_text_ids'))
        fit_view['matched_text_boxes'] = [_fields(box, ('element_id', 'section_id', 'zone_id', 'element_type',
            'planned_box_inches', 'rendered_box_inches', 'match_method')) for box in fit.get('matched_text_boxes', [])]
        fit_view['issues'] = [_fields(issue, ('code', 'element_id', 'section_id', 'zone_id', 'other_section_id', 'gap_inches', 'status',
            'other_element_type', 'overflow_right_inches', 'overflow_bottom_inches', 'overlap_width_inches',
            'overlap_height_inches')) for issue in fit.get('issues', [])]
        diagnostics['render_fit'] = fit_view
    return {'paper': _paper_evidence(bundle), 'evaluation': _score_evidence(report), 'diagnostics': diagnostics}
