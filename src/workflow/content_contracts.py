"""Versioned ownership of paper facts, sample science and display modules.

These are provenance/data checks, not a new semantic admission mechanism.
"""
from copy import deepcopy

GENERATOR_VERSION = 'explore_samples_v9'
PREPARATION_VERSION = 'sample_science_v6'
PAPER_FIELDS = (
    'raw_text', 'page_records', 'section_chunks', 'images', 'tables',
    'classified_visuals', 'visual_classification_report', 'evidence_bank',
    'academic_entities', 'narrative_content', 'structured_sections', 'evidence_extraction_report',
)
SCIENCE_FIELDS = ('narrative_plan', 'poster_claims', 'verified_claims',
                  'verification_report', 'verification_passed', 'sample_module_plan',
                  'verified_module_board', 'module_body_report', 'sample_family',
                  'family_capacity', 'joint_preparation', 'joint_candidate')


def paper_fields(state):
    fields = {key: deepcopy(state.get(key)) for key in PAPER_FIELDS}
    # The sample route never freezes a poster narrative in the paper cache.
    fields['narrative_content'] = {'meta': deepcopy(
        (state.get('narrative_content') or {}).get('meta') or {})}
    return fields


def science_fields(state):
    return {key: deepcopy(state.get(key)) for key in SCIENCE_FIELDS}


def science_ready(state):
    return bool((not state.get('joint_preparation') or
                 (state.get('joint_candidate') or {}).get('status') == 'verified_feasible') and
                (not state.get('sample_module_plan') or state.get('verified_module_board')) and
                state.get('verification_passed') and
                (state.get('verified_claims') or {}).get('claims') and
                (state.get('narrative_plan') or {}).get('sections'))


def module_provenance(board, state):
    """Keep display IDs separate from original plan/source identities."""
    from src.layout.presentation_policy import section_sources
    from utils.grounded_content import all_publishable_claims, merge_evidence_banks
    claims = all_publishable_claims(state)
    evidence = {e['evidence_id']: e for e in merge_evidence_banks(state).get('items', [])}
    result = []
    for module in (board or {}).get('spatial_content_plan', {}).get('sections', []):
        ids = module.get('claim_ids') or []
        eids = sorted({eid for cid in ids for eid in claims.get(cid, {}).get('evidence_ids', [])})
        result.append({'display_section_id': module['section_id'],
                       'plan_section_ids': section_sources(module, state),
                       'claim_ids': list(ids), 'evidence_ids': eids,
                       'paper_section_ids': sorted({str((evidence[eid].get('source') or {})['section_id'])
                           for eid in eids if eid in evidence and
                           (evidence[eid].get('source') or {}).get('section_id') is not None})})
    return {'version': PREPARATION_VERSION, 'modules': result}
