"""Local replay inputs without model configurations, endpoints or credentials."""

from copy import deepcopy
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from src.layout.design_content import DESIGN_POLICY_VERSION
from src.layout.reading_flow import READING_POLICY_VERSION
from src.layout.editorial import EDITORIAL_POLICY_VERSION


def measurement_environment(poster_config, styling=None):
    from src.layout.text_height_measurement import get_font_file_path
    names = set((poster_config.get('typography') or {}).get('fonts', {}).values())
    names.update(((styling or {}).get('font_families') or {}).values())
    fonts = []
    for name in sorted(n for n in names if isinstance(n, str)):
        for bold in (False, True):
            path = Path(get_font_file_path(name, bold=bold))
            fonts.append({'name': name, 'bold': bold, 'path': str(path),
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
    return {'fonts': fonts, 'python_pptx': version('python-pptx'), 'pillow': version('Pillow')}


def validate_replay_input(data):
    digest = data.get('input_digest')
    payload = {k: v for k, v in data.items() if k != 'input_digest'}
    if digest and hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() != digest:
        raise ValueError('Saved layout input digest mismatch')
    if data.get('family_contract') and data.get('reading_policy_version') != READING_POLICY_VERSION:
        raise ValueError('Saved reading policy differs from the current policy')
    if data.get('family_contract') and data.get('editorial_policy_version') != EDITORIAL_POLICY_VERSION:
        raise ValueError('Saved editorial policy differs from the current policy')
    if data.get('poster_config'):
        from src.config.poster_config import load_config
        if data['poster_config'] != load_config():
            raise ValueError('Saved measurement configuration differs from the current configuration')
        expected = data.get('measurement_environment')
        if expected and expected != measurement_environment(data['poster_config'], data['state'].get('styling_interfaces')):
            raise ValueError('Saved font or measurement dependency identities differ')


def save_layout_inputs(state, board, family):
    directory = (state.get('iteration_context') or {}).get('attempt_diagnostics_dir')
    if not directory:
        return
    from src.workflow.campaign import _atomic_json
    path = Path(directory) / 'layout_input_snapshot.json'
    # This is the original fit input; repair/refit calls must not overwrite it.
    if path.exists():
        return
    fields = {key: deepcopy(state.get(key)) for key in (
        'poster_width', 'poster_height', 'generation_route', 'narrative_plan',
        'narrative_content', 'poster_name', 'logo_path', 'aff_logo_path', 'url',
        'verified_claims', 'verified_content_bank', 'supplemental_evidence_bank',
        'classified_visuals', 'styling_interfaces', 'section_title_design',
        'color_scheme',
        'style_overrides', 'layout_revision_constraints', 'revision_recovery_policy',
        'revision_contract', 'revision_parent_layout_spec', 'template_validation_topology',
        'improve_safe_fallback', 'layout_required_visual_ids', 'runtime_layout_variants',
        'content_selection', 'critic_config', 'iteration_context',
    )}
    fields['iteration_context'] = fields.get('iteration_context') or {}
    fields['iteration_context'] = {key: value for key, value in fields['iteration_context'].items()
                                   if key in {'campaign_id', 'batch_id', 'iteration', 'attempt_id',
                                              'attempt_number', 'portfolio_mode', 'random_seed',
                                              'layout_family', 'capacity_repair_remaining',
                                              'design_policy_version', 'editorial_policy_version'}}
    fields['images'] = {str(k): {'aspect': v.get('aspect')} for k, v in (state.get('images') or {}).items()}
    fields['tables'] = {str(k): {'aspect': v.get('aspect')} for k, v in (state.get('tables') or {}).items()}
    from src.config.poster_config import load_config
    payload = {'schema_version': 1, 'design_policy_version': DESIGN_POLICY_VERSION,
               'reading_policy_version': READING_POLICY_VERSION,
               'editorial_policy_version': EDITORIAL_POLICY_VERSION,
               'family_id': family.family_id, 'family_contract': family.contract.to_dict(),
               'config': deepcopy(state.get('critic_config') or {}),
               'poster_config': load_config(),
               'state': fields, 'board': deepcopy(board)}
    payload['measurement_environment'] = measurement_environment(payload['poster_config'], fields.get('styling_interfaces'))
    payload['input_digest'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    _atomic_json(path, payload)
