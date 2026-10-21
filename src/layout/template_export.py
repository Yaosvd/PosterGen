"""Export one poster's actual geometry for inspection, never retrieval or learning."""
from copy import deepcopy
from pathlib import Path

from src.layout.family_previews import render_preview
from utils.persistence import _atomic_json, digest, file_hash


def export_template(state, directory):
    directory = Path(directory)
    layout = state.get('styled_layout') or state.get('design_layout') or []
    spec = state.get('layout_spec') or {}
    if not layout or not spec.get('zones'):
        raise ValueError('A poster template requires its actual compiled layout and LayoutSpec')
    width, height = float(state['poster_width']), float(state['poster_height'])
    if width <= 0 or height <= 0:
        raise ValueError('Invalid poster dimensions')
    roles = {'title', 'section_container', 'section_title', 'text', 'visual', 'conf_logo', 'aff_logo'}
    blueprint = []
    for element in layout:
        if element.get('type') not in roles:
            continue
        blueprint.append({
            'role': element['type'], 'element_id': element.get('id'),
            'section_id': element.get('section_id'), 'zone': element.get('zone_id'),
            **{key: float(element.get(key, 0)) / scale for key, scale in
               (('x', width), ('y', height), ('width', width), ('height', height))},
            'font_size': element.get('font_size'),
        })
    geometry = {
        'family': spec['family_id'],
        'zone_topology': {key: deepcopy(spec.get(key)) for key in
                          ('family_id', 'zones', 'reading_order', 'primary_anchor_zone')},
        'normalized_blueprint': blueprint,
        'source_aspect_ratio': width / height,
    }
    candidate = state.get('current_candidate') or {}
    payload = {
        'schema_version': 1, 'purpose': 'inspection_only',
        'source_candidate_id': candidate.get('candidate_id'),
        'source_geometry_fingerprint': spec.get('geometry_fingerprint'),
        'source_artifacts': {kind: file_hash(candidate[f'{kind}_path']) for kind in ('pptx', 'png')},
        'geometry_digest': digest(geometry), **geometry,
    }
    _atomic_json(directory / 'template.json', payload)
    render_preview(payload, directory / 'template.png', directory / 'template.pptx')
    return payload
