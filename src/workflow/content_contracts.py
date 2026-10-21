"""Versioned ownership of paper facts, sample science and display modules.

These are provenance/data checks, not a new semantic admission mechanism.
"""
from copy import deepcopy

PREPARATION_VERSION = 'sample_science_v1'
PAPER_FIELDS = (
    'raw_text', 'page_records', 'section_chunks', 'images', 'tables',
    'classified_visuals', 'visual_classification_report', 'evidence_bank',
    'academic_entities', 'narrative_content', 'structured_sections',
)
SCIENCE_FIELDS = ('narrative_plan', 'poster_claims', 'verified_claims',
                  'verification_report', 'verification_passed')


def paper_fields(state):
    fields = {key: deepcopy(state.get(key)) for key in PAPER_FIELDS}
    # The sample route never freezes a poster narrative in the paper cache.
    fields['narrative_content'] = {'meta': deepcopy(
        (state.get('narrative_content') or {}).get('meta') or {})}
    return fields


def science_fields(state):
    return {key: deepcopy(state.get(key)) for key in SCIENCE_FIELDS}


def science_ready(state):
    return bool(state.get('verification_passed') and
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
