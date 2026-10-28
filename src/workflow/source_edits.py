"""Merge small untrusted editorial patches; own mechanical provenance in code."""
from copy import deepcopy

from src.workflow.source_document import SourceOutputError
from src.workflow.source_editorial import MODULE, normalize_candidate, validate_revision, unique_ids
from src.workflow.source_requests import object_schema, STRING, STRINGS
from src.workflow.source_reading import READING_CONTENT_SCHEMA, bound_reading

LAYOUT_REQUEST_SCHEMA = object_schema({'section_to_zone': {'type':'array','items':object_schema({
    'module_id':STRING,'zone_id':STRING})}, 'variant_id':STRING})
PATCH_SCHEMA = object_schema({'modules':{'type':'array','items':MODULE},
    'remove_module_ids':STRINGS, 'module_order':STRINGS,
    'lineage':{'type':'array','items':object_schema({'new_module_id':STRING,'old_module_ids':STRINGS})},
    'reason':STRING,'layout_requests':LAYOUT_REQUEST_SCHEMA})
# The model judges routes. The program binds the exact supplied image, text,
# geometry and styles; copying cryptographic hashes is not a model task.


def edit_schema(has_image, phase='quality'):
    properties = deepcopy(PATCH_SCHEMA['properties'])
    if phase == 'capacity':
        properties['modules']['minItems'] = 1
        # A writing estimate never pins the only geometry the fitter may try.
        properties['layout_requests']['properties']['variant_id'] = {'type':'string','enum':['']}
    if has_image:
        properties['reading_review'] = READING_CONTENT_SCHEMA
    return object_schema(properties)


def edit_task(state, feedback, phase, space):
    modules = state['source_candidate']['modules']
    missing = feedback.get('missing_indispensable_meanings') or []
    ids = space.get('suggested_target_module_ids') or []
    observed = {}
    for row in feedback.get('pressure') or []:
        mid=row.get('section_id')
        used,limit=float(row.get('estimated_used_in') or 0),float(row.get('zone_limit_in') or 0)
        if mid and used>limit>0:
            if mid not in observed or used-limit < observed[mid]['estimated_used_in']-observed[mid]['zone_limit_in']:
                observed[mid]={**row,'estimated_used_in':used,'zone_limit_in':limit}
    if not ids and feedback.get('reason_code'):
        ids=sorted(observed,key=lambda mid:-(observed[mid]['estimated_used_in']-observed[mid]['zone_limit_in']))[:2]
        if not ids:
            ids=[m['module_id'] for m in sorted(modules,key=lambda m:-sum(len(e['text'].split()) for e in m['entries']))[:2]]
    if missing:
        # A small text-led opening is a useful EDIT target, not an automatic
        # assertion assignment. The semantic verifier still judges actual prose.
        ranked = sorted(modules,key=lambda m:(m['narrative_role'] not in {'problem','background','motivation'},
            bool(m['visual_ids']),m['module_purpose']!='primary',
            sum(len(e['text'].split()) for e in m['entries'])))
        ids = [ranked[0]['module_id']]
    diagnostic = feedback.get('scientific_diagnostic') or ''
    if diagnostic:
        ids = [m['module_id'] for m in modules if diagnostic.startswith(m['module_id']+':')]
    targets = [m for m in modules if m['module_id'] in ids][:2]
    estimates={r['module_id']:r for r in space.get('modules') or []}
    def target(m):
        mid=m['module_id'];wc=sum(len(e['text'].split()) for e in m['entries'])
        words=estimates.get(mid,{}).get('suggested_body_words',wc)
        pressure=observed.get(mid)
        if pressure:
            words=min(words,int(wc*pressure['zone_limit_in']/pressure['estimated_used_in']*.85))
        return {'module_id':mid,'title':m['title'],'obligation_ids':m['obligation_ids'],
            'current_words':wc,'suggested_body_words':words,'observed_failed_fit_pressure':pressure,
            'entries':[{'item_id':e['item_id'],'text':e['text']} for e in m['entries']]}
    return {'phase':phase,'must_return_action':phase=='capacity',
        'actual_fit_failed':bool(feedback.get('reason_code')),
        'missing_meaning_ids':[m['obligation_id'] for m in missing],
        'missing_meanings':[m['meaning'] for m in missing],
        'current_visible_targets':[target(m) for m in targets],
        'scientific_diagnostic':diagnostic,
        'instruction':('Return an actual changed-module patch NOW. The text above is the CURRENT VISIBLE POSTER; '
            'paper paragraphs and source_refs are NOT displayed text. Missing IDs are not already assigned. '
            'For a missing meaning, include its ID in a returned module and add concise supported explanation if '
            'that module does not already express it. A rationale claiming it is present does not change the poster. '
            'For a failed fit, change prose, optional visuals or legal placement now; provisional estimates do not '
            'cancel the observed fit failure. The observed failure is authoritative even if an estimate looks feasible. '
            'Leave layout_requests.variant_id empty: the program must search legal family variants after editing. '
            'Return at least one module; retain all other neighbors. '
            'Do not return an empty patch or promise a later edit.' if phase=='capacity' else
            'Judge the supplied image and make a useful local improvement if possible. An empty quality patch is valid.')}


def merge_patch(raw, state, *, normalizations=None):
    before = state['source_candidate']
    old = {m['module_id']:m for m in before['modules']}
    unique_ids(raw['modules'],'module_id')
    removals = raw['remove_module_ids']
    if len(set(removals))!=len(removals) or not set(removals)<=old.keys():
        raise SourceOutputError('Unknown or duplicate removed module')
    updates = {m['module_id']:deepcopy(m) for m in raw['modules']}
    if set(updates)&set(removals):
        raise SourceOutputError('A module cannot be both replaced and removed')
    modules = [updates.pop(mid,deepcopy(m)) for mid,m in old.items() if mid not in removals]
    modules.extend(updates.values())
    if raw['module_order']:
        ids = [m['module_id'] for m in modules]
        if len(raw['module_order'])!=len(ids) or set(raw['module_order'])!=set(ids):
            raise SourceOutputError('Module order must contain every final module exactly once')
        lookup = {m['module_id']:m for m in modules}
        modules = [lookup[mid] for mid in raw['module_order']]
    # Diagnose paths in the returned patch, never in absent untouched neighbors.
    # Normalize each patch module in situ before assembling the full candidate.
    if raw['modules']:
        normalized = normalize_candidate({'modules':raw['modules']},state,
            normalizations=normalizations,allow_missing=True)
        lookup = {m['module_id']:m for m in normalized['modules']}
        modules = [lookup.get(m['module_id'],m) for m in modules]
    candidate = normalize_candidate({'modules':modules},state,allow_missing=True)
    new = {m['module_id']:m for m in candidate['modules']}
    changed = {mid for mid,m in new.items() if old.get(mid)!=m}
    common_old,common_new = [mid for mid in old if mid in new],[mid for mid in new if mid in old]
    if common_old!=common_new:
        changed.update(mid for mid in common_old if common_old.index(mid)!=common_new.index(mid))
    explicit = {}
    for link in raw['lineage']:
        mid,origins = link['new_module_id'],link['old_module_ids']
        if mid in explicit:
            raise SourceOutputError('Duplicate split/merge lineage')
        # A harmless identity for an untouched module can be removed exactly.
        if mid not in changed and mid in old and origins==[mid]:
            continue
        if mid not in changed:
            raise SourceOutputError('Lineage refers to an unchanged or absent module')
        explicit[mid]=origins
    links = []
    for mid in sorted(changed):
        if mid in explicit:
            origins = explicit[mid]
        elif mid in old:
            origins = [mid]  # ordinary in-place editing is mechanically known
        else:
            # A genuinely new explanation may have no predecessor. Splits and
            # merges MUST declare old owners, checked below and by preservation.
            origins = []
        links.append({'new_module_id':mid,'old_module_ids':origins})
    revision = validate_revision(before,candidate,links,raw['reason'])
    return candidate,revision
