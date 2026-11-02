"""Versioned ownership of paper facts, sample science and display modules.

These are provenance/data checks, not a new semantic admission mechanism.
"""
from copy import deepcopy

GENERATOR_VERSION = 'explore_samples_v32'
PREPARATION_VERSION = 'sample_editorial_v1'
PAPER_FIELDS = (
    'raw_text', 'page_records', 'section_chunks', 'images', 'tables',
    'classified_visuals', 'visual_classification_report', 'evidence_bank',
    'academic_entities', 'narrative_content', 'structured_sections', 'evidence_extraction_report',
)
SCIENCE_FIELDS = ('narrative_plan', 'poster_claims', 'verified_claims',
                  'verification_report', 'verification_passed', 'sample_module_plan',
                  'verified_module_board', 'module_body_report', 'sample_family',
                  'family_capacity', 'joint_preparation', 'joint_candidate',
                  'source_editorial_version', 'source_narrative_plan', 'source_candidate',
                  'source_verification_report', 'source_layout_requests', 'source_reading_review',
                  'source_candidate_lineage', 'source_quality_report', 'source_visual_report')


def paper_fields(state):
    from src.workflow.editorial_contract import editorial_mode, PAPER_KEYS
    if editorial_mode(state):
        return {key: deepcopy(state.get(key)) for key in (*PAPER_KEYS, 'editorial_version')}
    from src.workflow.source_document import source_mode
    keys = PAPER_FIELDS
    if source_mode(state):
        keys = tuple(k for k in PAPER_FIELDS if k not in {
            'evidence_bank', 'academic_entities', 'evidence_extraction_report'}) + (
            'source_editorial_version', 'source_document', 'source_extraction_report')
    fields = {key: deepcopy(state.get(key)) for key in keys}
    # The sample route never freezes a poster narrative in the paper cache.
    fields['narrative_content'] = {'meta': deepcopy(
        (state.get('narrative_content') or {}).get('meta') or {})}
    return fields


def science_fields(state):
    from src.workflow.editorial_contract import editorial_mode, SAMPLE_KEYS
    if editorial_mode(state):
        return {key: deepcopy(state.get(key)) for key in SAMPLE_KEYS}
    return {key: deepcopy(state.get(key)) for key in SCIENCE_FIELDS}


def science_ready(state):
    from src.workflow.editorial_contract import editorial_mode, assert_editorial_ready
    if editorial_mode(state):
        try:
            return assert_editorial_ready(state)
        except (ValueError, KeyError, TypeError):
            return False
    from src.workflow.source_document import source_mode
    if source_mode(state):
        from src.workflow.source_verification import assert_verified
        try:
            assert_verified(state, (state.get('joint_candidate') or {}).get('board'))
            return (state.get('joint_candidate') or {}).get('status') == 'verified_feasible'
        except (ValueError, KeyError, TypeError):
            return False
    return bool((not state.get('joint_preparation') or
                 (state.get('joint_candidate') or {}).get('status') == 'verified_feasible') and
                (not state.get('sample_module_plan') or state.get('verified_module_board')) and
                state.get('verification_passed') and
                (state.get('verified_claims') or {}).get('claims') and
                (state.get('narrative_plan') or {}).get('sections'))


def module_provenance(board, state):
    """Keep display IDs separate from original plan/source identities."""
    from src.workflow.editorial_contract import editorial_mode
    if editorial_mode(state):
        return {'version': PREPARATION_VERSION, 'content_status': 'not_preverified',
                'candidate_id': state['editorial_candidate']['candidate_id'],
                'modules': [{'module_id':m['module_id'], 'zone_id':m['zone_id'],
                             'visual_ids':m['visual_ids']} for m in state['editorial_candidate']['modules']]}
    from src.workflow.source_document import source_mode
    if source_mode(state):
        from src.workflow.source_verification import assert_verified
        assert_verified(state, board)
        index = {m['module_id']: m for m in state['source_candidate']['modules']}
        return {'version': PREPARATION_VERSION, 'source_digest': state['source_document']['digest'],
            'verification_digest': state['source_verification_report']['digest'],
            'modules': [{'display_section_id': s['section_id'], 'claim_ids': s['claim_ids'],
                'original_source_ids': sorted({r['source_id'] for r in index[s['section_id']]['source_refs']
                    + [r for e in index[s['section_id']]['entries'] for r in e['source_refs']]}),
                'obligation_ids': index[s['section_id']]['obligation_ids']} for s in
                (board or {}).get('spatial_content_plan', {}).get('sections', [])]}
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
