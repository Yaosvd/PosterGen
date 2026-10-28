"""Whole-poster source writing and mutable display modules, independent of facts."""
from copy import deepcopy
from pathlib import Path
import json
import re

from src.workflow.source_document import (VERSION, SourceOutputError, validate_refs,
                                        source_material, check_stop, paragraph_hints)
from src.workflow.source_requests import (SourceRequests, object_schema, STRING, STRINGS,
                                          BOOL, REFS, SourceFieldError)
from utils.persistence import digest, _atomic_json

ROLE = {'type': 'string', 'enum': ['background', 'problem', 'motivation', 'insight', 'method',
    'theory', 'evaluation', 'results', 'discussion', 'conclusion', 'supporting']}
ENTRY = object_schema({'item_id': STRING, 'text': STRING, 'kind': {'type': 'string', 'enum':
    ['definition', 'goal', 'method', 'result', 'interpretation', 'setup', 'context', 'limitation']},
    'source_refs': REFS, 'parent_item_id': STRING,
    'display_label': {'type': 'string', 'description':
        'Optional topics cue: an exact short phrase from this entry text, never a new heading. '
        'Use an empty string for plain or steps, or when no useful extractive cue exists.'},
    'step_index': {'type': 'integer', 'minimum': 0, 'description':
        'Use 1,2,3,... in entry order for steps; use 0 otherwise. '
        'The program derives display ordinals without reordering entries; scientific chronology needs verification.'}})
MODULE = object_schema({'module_id': STRING, 'title': STRING, 'narrative_role': ROLE,
    'importance': {'type': 'integer', 'minimum': 1, 'maximum': 3},
    'module_purpose': {'type': 'string', 'enum': ['primary', 'context', 'supporting']},
    'presentation_style': {'type': 'string', 'enum': ['plain', 'topics', 'steps']},
    'reader_question': STRING, 'communication_goal': STRING, 'source_refs': REFS,
    'obligation_ids': STRINGS, 'entries': {'type': 'array', 'items': ENTRY, 'minItems': 1},
    'visual_ids': STRINGS, 'reserve_visual_ids': STRINGS, 'visual_rationale': STRING})
CANDIDATE_SCHEMA = object_schema({'modules': {'type': 'array', 'items': MODULE, 'minItems': 1}})
PLAN_SCHEMA = object_schema({'reader_question': STRING, 'research_story': STRING,
    'sections': {'type': 'array', 'minItems': 1, 'items': object_schema({'section_id': STRING,
        'title_intent': STRING, 'narrative_role': ROLE, 'source_refs': REFS})},
    'obligations': {'type': 'array', 'minItems': 1, 'items': object_schema({
        'obligation_id': STRING, 'meaning': STRING, 'rationale': STRING, 'source_refs': REFS})}})


def load_prompt(name):
    return (Path('config/prompts')/name).read_text()  # explicit repository prompt identity


def agent_for(state, kind, *, vision=False):
    from utils.langgraph_utils import LangGraphAgent
    from utils.agent_policy import apply_agent_policy
    policy = kind
    return LangGraphAgent('Read original scientific source; generated material is untrusted.',
        apply_agent_policy(state['vision_model' if vision else 'text_model'], policy), state, kind)


def request(state, kind, payload, schema, *, directory, preview=None, validator=None):
    check_stop(state)
    if preview is not None and state.get('vision_model') is None:
        raise SourceOutputError('Source editorial visual reading requires a configured vision-capable model')
    prompt = load_prompt(kind+'.txt') + '\nINPUT:\n'+json.dumps(paragraph_hints(payload, state['source_document']), ensure_ascii=False, sort_keys=True)
    journal = SourceRequests(state, directory, prompt, schema, vision=preview is not None,
                             images=[preview] if preview else [])
    return journal.call(agent_for(state, kind, vision=preview is not None), validator=validator)


def unique_ids(rows, key):
    ids = [r.get(key) for r in rows]
    if any(not isinstance(i, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', i) for i in ids) or len(set(ids)) != len(ids):
        raise SourceOutputError('Invalid or duplicate '+key)
    return ids


def source_narrative_node(state):
    plan = request(state, 'source_narrative', source_material(state), PLAN_SCHEMA,
                   directory='source/narrative')
    unique_ids(plan['sections'], 'section_id')
    unique_ids(plan['obligations'], 'obligation_id')
    for row in [*plan['sections'], *plan['obligations']]:
        validate_refs(row['source_refs'], state['source_document'])
    if not plan['reader_question'].strip() or not plan['research_story'].strip():
        raise SourceOutputError('Empty global research story')
    state['source_narrative_plan'] = deepcopy(plan)
    state['narrative_plan'] = {'sections': deepcopy(plan['sections']),
        'narrative_summary': plan['research_story'], 'source_editorial_version': VERSION}
    _atomic_json(Path(state['output_dir'])/'content/source_narrative_plan.json', plan)
    return state


def family_material(state):
    from src.layout.family_capacity import family_brief
    from src.layout.families import LayoutFamilyRegistry
    from src.layout.feasibility import generate_zone_variants
    brief = family_brief(state)
    family = LayoutFamilyRegistry().get(brief['family_id'])
    settings = state['critic_config'].get('explore_layout') or {}
    variants = generate_zone_variants(family, random_seed=int(state['iteration_context']['random_seed']),
        maximum=max(int(settings.get('max_geometry_candidates_per_family', 4)),
                    min(12, int(settings.get('max_adaptive_geometry_candidates', 12)))))
    # Geometry is program-generated. No semantic source order is given as a reading answer.
    for key in ('reading', 'entry_roles'):
        brief['contract'].pop(key, None)
    brief['variants'] = [{k: deepcopy(v) for k,v in r.items() if k in
        {'variant_id','zones','geometry_fingerprint','variant_label'}} for r in variants]
    brief['maximum_legal_modules'] = max(sum(int(z.get('capacity',1)) for z in r['zones']) for r in variants)
    from src.config.poster_config import load_config
    typography = load_config()['typography']
    brief['typography'] = deepcopy(typography)
    body_font = float(typography['sizes']['body_text'])
    scale = float(state['poster_width'])/54*float(state['poster_height'])/36*(44/body_font)**2
    brief['soft_total_word_reference'] = [round(280*scale), round(420*scale)]
    brief['word_reference_is_not_a_limit'] = True
    brief['natural_reading_policy'] = 'Observe actual preview; horizontal and vertical axes are peers.'
    return brief


def missing_obligations(candidate, state):
    assigned = {oid for module in candidate['modules'] for oid in module['obligation_ids']}
    return [deepcopy(row) for row in state['source_narrative_plan']['obligations']
            if row['obligation_id'] not in assigned]


def normalize_candidate(raw, state, *, normalizations=None, path_prefix=(), allow_missing=False):
    modules = deepcopy(raw['modules'])
    obligations = {o['obligation_id'] for o in state['source_narrative_plan']['obligations']}
    if len(modules) > family_material(state)['maximum_legal_modules']:
        raise SourceOutputError('Module count exceeds every bounded legal variant capacity')
    assets = state['source_document']['assets']
    visuals, problems, paths = set(), [], []

    def problem(message, path):
        problems.append({'path': list(path), 'error': message})
        paths.append(path_prefix+path)

    def check_ids(rows, key, prefix):
        ids = [row[key] for row in rows]
        for i, value in enumerate(ids):
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', value) or ids.count(value) > 1:
                problem('Invalid or duplicate '+key, prefix+(i, key))
        return ids

    check_ids(modules, 'module_id', ('modules',))
    from src.layout.body_presentation import extract_label
    for mi, module in enumerate(modules):
        mid = module['module_id']
        base = ('modules', mi)
        if not module['title'].strip() or len(module['title']) > 160:
            problem('Empty or overlong complete module title', base+('title',))
        validate_refs(module['source_refs'], state['source_document'])
        if not set(module['obligation_ids']) <= obligations:
            problem('Unknown indispensable meaning ID', base+('obligation_ids',))
        local_ids = check_ids(module['entries'], 'item_id', base+('entries',))
        seen = set()
        for ei, entry in enumerate(module['entries']):
            entry_path = base+('entries', ei)
            # These are renderer-owned cues, never scientific prose or order edits.
            values = {'step_index': ei+1 if module['presentation_style'] == 'steps' else 0}
            label = entry['display_label']
            if module['presentation_style'] != 'topics':
                values['display_label'] = ''
            elif label and (label not in entry['text'] or
                    extract_label(label, entry['text'], module['title']) != label):
                values['display_label'] = ''
            for field, value in values.items():
                if entry[field] != value:
                    if normalizations is not None:
                        normalizations.append({'module_id': mid, 'item_id': entry['item_id'],
                            'field': field, 'before': entry[field], 'after': value,
                            'reason': ('derive_ordinal_from_entry_order' if field == 'step_index' else
                                'invalid_optional_topics_cue' if module['presentation_style'] == 'topics' else
                                'unused_display_cue')})
                    entry[field] = value
            if not entry['text'].strip():
                problem('Empty display expression', entry_path+('text',))
            if re.search(r'\bev_\d+\b', entry['text']):
                problem('Machine evidence markers are not visible prose', entry_path+('text',))
            validate_refs(entry['source_refs'], state['source_document'])
            if entry['parent_item_id'] and (entry['parent_item_id'] not in seen or
                    local_ids.count(entry['parent_item_id']) != 1):
                problem('Lead/support reference must name an unambiguous earlier local entry',
                        entry_path+('parent_item_id',))
            seen.add(entry['item_id'])
        for field in ('visual_ids', 'reserve_visual_ids'):
            if len(set(module[field])) != len(module[field]) or not set(module[field]) <= assets.keys():
                problem('Unknown or duplicate original visual', base+(field,))
        if set(module['visual_ids']) & set(module['reserve_visual_ids']):
            problem('A visible visual cannot also be reserved', base+('reserve_visual_ids',))
        if visuals & set(module['visual_ids']):
            problem('Visual ownership must be unique', base+('visual_ids',))
        visuals.update(module['visual_ids'])
    missing = missing_obligations({'modules': modules}, state)
    if problems:
        raise SourceFieldError('Invalid candidate fields: '+json.dumps(problems, ensure_ascii=False)+
            '. Missing meaning assignments (content edits, not a format license): '+
            json.dumps(missing, ensure_ascii=False)+
            '. Correct only the diagnosed fields; preserve every other field and module.', paths)
    if missing and not allow_missing:
        raise SourceOutputError('Candidate leaves indispensable meaning unassigned: '+
                                json.dumps(missing, ensure_ascii=False))
    candidate = {'version': VERSION, 'modules': modules}
    candidate['candidate_id'] = 'candidate_'+digest(candidate)[:24]
    return candidate


def install_candidate(state, candidate, *, verified=None):
    """Render IDs identify display entries, never precomputed scientific atoms."""
    state['source_candidate'] = deepcopy(candidate)
    state['sample_module_plan'] = {'version': VERSION, 'modules': deepcopy(candidate['modules'])}
    state['narrative_plan'] = {'narrative_summary': state['source_narrative_plan']['research_story'],
        'source_editorial_version': VERSION, 'sections': [{
            'section_id': m['module_id'], 'title_intent': m['title'],
            'narrative_role': m['narrative_role'], 'importance': m['importance'],
            'source_refs': deepcopy(m['source_refs']), 'presentation_function': m['module_purpose']}
            for m in candidate['modules']]}
    claims = []
    for module in candidate['modules']:
        mid = module['module_id']
        for entry in module['entries']:
            claim = {'claim_id': mid+':'+entry['item_id'], 'section_id': mid, 'display_module_id': mid,
                'source_plan_unit_ids': [mid], 'body_contract': 'sample_body_source_v1',
                'text': entry['text'], 'discourse_kind': entry['kind'],
                'source_refs': deepcopy(entry['source_refs']), 'display_label': entry['display_label'],
                'parent_claim_id': mid+':'+entry['parent_item_id'] if entry['parent_item_id'] else None,
                'requires_claim_ids': [], 'step_index': entry['step_index'] or None,
                'verified': verified is not None}
            if verified is not None:
                claim['source_verification_digest'] = verified['digest']
            claims.append(claim)
    state['poster_claims'] = {'claims': deepcopy(claims)}
    if verified is not None:
        state['verified_claims'] = {'claims': deepcopy(claims)}
        state['source_verification_report'] = deepcopy(verified)
        state['verification_report'] = deepcopy(verified)
        state['verification_passed'] = True
    else:
        state['verification_passed'] = False
        state['verified_claims'] = None
        state['verified_module_board'] = None
    return state


def make_board(state):
    from src.layout.editorial import prepare_board
    from src.layout.editorial_selection import sanitize_selection
    claims = {c['claim_id']: c for c in state['poster_claims']['claims']}
    sections = []
    for m in state['source_candidate']['modules']:
        local = [c for c in claims.values() if c['display_module_id'] == m['module_id']]
        sections.append({'section_id': m['module_id'], 'source_editorial_version': VERSION, 'section_title': m['title'],
            'title_candidates': [m['title']], 'vertical_priority': 'middle',
            'importance_level': m['importance'], 'module_purpose': m['module_purpose'],
            'presentation_style': m['presentation_style'],
            'claim_ids': [c['claim_id'] for c in local], 'text_content': [c['text'] for c in local],
            'core_claim_ids': [c['claim_id'] for c in local[:3]],
            'visual_assets': [{'visual_id': v} for v in m['visual_ids']],
            'claim_layout': [{'claim_id': c['claim_id'], 'kind': c['discourse_kind'],
                'requires_claim_ids': [], 'parent_claim_id': c['parent_claim_id'],
                'display_label': c['display_label'], 'step_index': c['step_index']} for c in local]})
    # A fit may not silently delete authored text. Balancer can restructure the NEXT
    # candidate under source preservation; these IDs do not lock scientific roots.
    board = {'spatial_content_plan': {'sections': sections},
        'source_editorial_version': VERSION,
        'editorial_selection': sanitize_selection(None, claims, visible=claims, required=claims)}
    board = prepare_board(board, state, raw_sections=sections)
    for s in board['spatial_content_plan']['sections']:
        s['editorial'].update(module_prose_order=True, active=True)
    return board


def source_curator_node(state):
    brief = family_material(state)
    raw = request(state, 'source_curator', {'source': source_material(state),
        'story': state['source_narrative_plan'], 'family': brief,
        'poster_inches': [state['poster_width'], state['poster_height']]},
        CANDIDATE_SCHEMA, directory='source/curator',
        validator=lambda value: normalize_candidate(value, state, allow_missing=True))
    normalizations = []
    candidate = normalize_candidate(raw, state, normalizations=normalizations, allow_missing=True)
    _atomic_json(Path(state.get('sample_preparation_dir') or state['output_dir'])/'source/curator/normalization.json',
        {'raw_digest': digest(raw), 'candidate_id': candidate['candidate_id'], 'changes': normalizations,
         'missing_obligations': missing_obligations(candidate, state), 'scientific_status': 'unverified'})
    from src.workflow.source_visuals import offer_key_reserve
    candidate = offer_key_reserve(candidate, state, allow_missing=True)
    install_candidate(state, candidate)
    state['family_capacity'] = brief
    _atomic_json(Path(state['output_dir'])/'content/source_candidate.json', candidate)
    return state


def validate_revision(before, after, lineage, reason):
    old, new = {m['module_id']: m for m in before['modules']}, {m['module_id']: m for m in after['modules']}
    old_positions = {m['module_id']: i for i,m in enumerate(before['modules'])}
    new_positions = {m['module_id']: i for i,m in enumerate(after['modules'])}
    changed_old = {mid for mid in old if mid not in new or old[mid] != new[mid]}
    changed_new = {mid for mid in new if mid not in old or old[mid] != new[mid]}
    # Relative order of surviving neighbors matters; insertions don't charge all shifted neighbors.
    common_old = [m for m in old if m in new]
    common_new = [m for m in new if m in old]
    if common_old != common_new:
        moved = {m for m in common_old if common_old.index(m) != common_new.index(m)}
        changed_old.update(moved); changed_new.update(moved)
    if len(changed_old) > 2 or len(changed_new) > 2:
        raise SourceOutputError('Editorial round exceeds two affected old/new modules')
    if (changed_old or changed_new) and not reason.strip():
        raise SourceOutputError('Edits require an explicit preservation/omission rationale')
    links = {r['new_module_id']: r['old_module_ids'] for r in lineage}
    if len(links) != len(lineage) or set(links) != changed_new:
        raise SourceOutputError('Changed/new modules require exact lineage coverage')
    represented = set()
    for mid, origins in links.items():
        if len(set(origins)) != len(origins) or not set(origins) <= changed_old:
            raise SourceOutputError('Invalid split/merge lineage')
        represented.update(origins)
    # Explicit deletion may have no new owner; the scientific preservation verdict
    # checks it against the full before/after candidate and indispensable meanings.
    return {'old_modules': sorted(changed_old), 'new_modules': sorted(changed_new),
            'deleted_modules': sorted(set(old)-set(new)), 'lineage': deepcopy(lineage), 'reason': reason}
