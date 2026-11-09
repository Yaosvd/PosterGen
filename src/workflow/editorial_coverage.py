"""Curator source navigation, not a semantic coverage verdict or admission gate."""
from src.agents.visual_classification import ROLE_FIELDS

VERSION = 'editorial_coverage_navigation_v1'


def authoring_coverage(paper):
    """Index all organized sections/assets without copying or filtering evidence.

    Parser labels are navigation hints. Empty evaluation/result groups do not
    establish absence of findings; the author must still inspect all material.
    Paths address the existing paper payload, not newly invented source IDs.
    """
    sections = paper['structured_sections']['paper_sections']
    assets = paper['visuals']
    classified = paper.get('classified_visuals') or {}
    section_rows = [
        {'source_path': ['paper', 'structured_sections', 'paper_sections', i],
         'section_name': section['section_name'], 'section_type': section['section_type']}
        for i, section in enumerate(sections)]
    visual_rows = [
        {'visual_id': vid, 'source_path': ['paper', 'visuals', vid],
         'reported_roles': [role for role in ROLE_FIELDS if vid in (classified.get(role) or [])],
         'required_key_visual': vid == classified.get('key_visual')}
        for vid in assets]
    return {'version': VERSION,
            'basis': 'existing_organized_material_navigation_only',
            'sections': section_rows, 'visuals': visual_rows,
            'review_for_findings': {
                'section_paths': [row['source_path'][:] for row in section_rows
                                  if row['section_type'] == 'evaluation'],
                'visual_ids': [row['visual_id'] for row in visual_rows
                               if set(row['reported_roles']) & {'main_results', 'comparative_results'}]},
            'instructions': 'Resolve source_path against this request. Read the referenced full content, '
                'key_points and captions in paper, not just these labels or ABT. All sections and assets '
                'remain available, including those outside review_for_findings. Reported roles come from '
                'upstream organization and may be incomplete or wrong; they do not verify claims, assign '
                'module owners, require selecting every result visual or prove absence of results. '
                'Do not copy paths/roles into visible prose. Plan research coverage before subdividing '
                'methods or allocating space. After planning, the program computes actual body frames for writing.'}
