"""Unverified editorial material and immutable render identities for Explore v23.

These checks establish ownership and delivery integrity, never scientific truth.
"""
from copy import deepcopy
from pathlib import Path
import math
import re

from utils.persistence import digest, file_hash

VERSION = 'poster_editorial_v1'
PREPARATION = 'sample_editorial_v1'
PAPER_KEYS = ('raw_text', 'structured_sections', 'narrative_content', 'images', 'tables',
              'classified_visuals', 'visual_classification_report', 'source_extraction_report')
SAMPLE_KEYS = ('editorial_version', 'sample_family', 'editorial_candidate', 'editorial_zones',
               'editorial_history', 'editorial_fit', 'editorial_quality', 'editorial_snapshot',
               'color_scheme', 'color_provenance', 'section_title_design', 'styling_interfaces',
               'story_board', 'optimized_story_board', 'layout_spec', 'layout_feasibility_report',
               'joint_candidate', 'joint_preparation', 'editorial_budget', 'editorial_merge_report')


class EditorialOutputError(ValueError):
    """A finite content/fit task failure; do not silently restart or change family."""


class EditorialInterrupted(Exception):
    """Cooperative interruption at a durable editorial boundary."""


class EditorialStructureError(EditorialOutputError):
    def __init__(self, message, paths=()):
        super().__init__(message)
        self.paths = tuple(tuple(p) for p in paths)


def editorial_mode(state):
    return state.get('editorial_version') == VERSION


def asset_index(state):
    return {f'{prefix}_{key}': asset for prefix, field in (('figure', 'images'), ('table', 'tables'))
            for key, asset in (state.get(field) or {}).items()}


def paper_material(state, *, original=False):
    if not state.get('raw_text') or not (state.get('structured_sections') or {}).get('paper_sections'):
        raise ValueError('Incomplete editorial paper material')
    result = {key: deepcopy(state.get(key)) for key in
              ('structured_sections', 'narrative_content', 'classified_visuals')}
    result['visuals'] = {vid: {k: deepcopy(v) for k, v in a.items() if k not in {'path'}}
                         for vid, a in asset_index(state).items()}
    if original:
        result['original_text'] = state['raw_text']
    return result


def paper_identity(state):
    return digest({'fields': {key: state.get(key) for key in PAPER_KEYS},
                   'pdf_hash': file_hash(state['pdf_path']) if state.get('pdf_path') else None})


def validate_zones(state, zones):
    from src.layout.families import LayoutFamilyRegistry, valid_family_topology
    family = LayoutFamilyRegistry().get(state['sample_family']['family'])
    if not zones or not valid_family_topology(family, zones):
        raise ValueError('Invalid editorial family topology')
    return family


def module_limits(zones):
    # Occupancy is deliberately separate from required/protected merge regions.
    return len(zones), sum(z['capacity'] for z in zones)


def normalize_candidate(raw, state, zones, *, allow_underfull=False):
    from collections import Counter
    modules = deepcopy(raw['modules'])
    minimum, maximum = module_limits(zones)
    if not modules or len(modules) > maximum:
        raise EditorialOutputError(f'Editorial module count must be in 1..{maximum}')
    if len(modules) < minimum and not allow_underfull:
        raise EditorialOutputError(f'{len(modules)} meaningful modules cannot occupy {minimum} regions')
    ids = [m['module_id'] for m in modules]
    zone_ids = {z['zone_id'] for z in zones}
    assets, visuals, problems, paths = asset_index(state), [], [], []
    def problem(message, path):
        problems.append(message); paths.append(path)
    for i, module in enumerate(modules):
        base = ('modules', i)
        mid = module['module_id']
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', mid) or ids.count(mid) != 1:
            problem('Module IDs must be unique identifiers', base+('module_id',))
        if not module['title'].strip() or len(module['title']) > 160:
            problem('Module title is empty or overlong', base+('title',))
        if module['zone_id'] not in zone_ids:
            problem('Unknown family region', base+('zone_id',))
        if not math.isfinite(module['space_weight']) or not 1 <= module['space_weight'] <= 3:
            problem('Module space_weight must be 1..3', base+('space_weight',))
        seen = set()
        for j, entry in enumerate(module['entries']):
            ep = base+('entries', j)
            if not entry['text'].strip():
                problem('Empty display expression', ep+('text',))
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', entry['item_id']) or entry['item_id'] in seen:
                problem('Entry IDs must be unique local identifiers', ep+('item_id',))
            if entry['parent_item_id'] and entry['parent_item_id'] not in seen:
                problem('Support entry must follow its local parent', ep+('parent_item_id',))
            if len(entry['display_label']) > 64 or '\n' in entry['display_label']:
                problem('Navigation labels must be short, single-line phrases', ep+('display_label',))
            seen.add(entry['item_id'])
        local = module['visual_ids']+module['reserve_visual_ids']
        if len(local) != len(set(local)) or not set(local) <= assets.keys():
            problem('Unknown or repeated visual ownership', base+('visual_ids',))
        visuals += module['visual_ids']
    repeated = {v for v, count in Counter(visuals).items() if count > 1}
    for i, m in enumerate(modules):
        if repeated.intersection(m['visual_ids']):
            problem('A visible original visual has multiple owners', ('modules', i, 'visual_ids'))
    counts = Counter(m['zone_id'] for m in modules)
    for zone in zones:
        if counts[zone['zone_id']] > zone['capacity']:
            raise EditorialOutputError('Curator allocation exceeds region capacity')
    if len(modules) >= minimum and set(counts) != zone_ids:
        raise EditorialOutputError('Every active region needs a meaningful module')
    if problems:
        raise EditorialStructureError('; '.join(problems), paths)
    candidate = {'version': VERSION, 'modules': modules, 'narrative_flow': raw['narrative_flow']}
    candidate['candidate_id'] = 'editorial_'+digest(candidate)[:24]
    return candidate


def make_board(candidate):
    sections = []
    for m in candidate['modules']:
        ids = [m['module_id']+':'+e['item_id'] for e in m['entries']]
        items = [{'claim_id': cid, 'parent_claim_id': m['module_id']+':'+e['parent_item_id'] if e['parent_item_id'] else '',
                  'display_label': e['display_label'], 'step_index': i+1}
                 for i, (cid, e) in enumerate(zip(ids, m['entries']))]
        sections.append({'section_id': m['module_id'], 'section_title': m['title'],
            'importance_level': m['importance'], 'claim_ids': ids,
            'text_content': [e['text'] for e in m['entries']],
            'visual_assets': [{'visual_id': vid} for vid in m['visual_ids']],
            'editorial': {'version': VERSION, 'active': True, 'body_style': 'editorial',
                'presentation_style': m['presentation_style'], 'items': items},
            'editorial_version': VERSION})
    return {'editorial_version': VERSION, 'spatial_content_plan': {'sections': sections}}


def snapshot_payload(state):
    return {'version': VERSION, 'paper': paper_identity(state), 'candidate': state['editorial_candidate'],
            'spec': state['layout_spec'], 'palette': state['color_scheme'],
            'title_style': state['section_title_design'], 'board': state['optimized_story_board'],
            'budget': state['editorial_budget'], 'logos': {
                key: {'path': state.get(key), 'hash': file_hash(state[key]) if state.get(key) else None}
                for key in ('logo_path', 'aff_logo_path')}, 'resources': {
                vid: file_hash(a['path']) for vid, a in asset_index(state).items() if a.get('path')}}


def assert_editorial_ready(state, *, compiled=False):
    from utils.text_formatting import tokenize_styling
    from src.layout.editorial import presentation_lines
    from src.agents.font_agent import FontAgent
    record = state.get('editorial_snapshot') or {}
    if record.get('digest') != digest(snapshot_payload(state)) or state.get('draft_layout_mode'):
        raise ValueError('Editorial render snapshot changed or is not ready')
    candidate = state['editorial_candidate']
    from src.workflow.editorial_requests import read
    ledger = state.get('editorial_budget') or {}
    if state.get('sample_edit_budget_dir') and read(
            Path(state['sample_edit_budget_dir'])/'editorial_budget.json', ledger.get('input_digest')) != ledger:
        raise ValueError('Editorial render budget changed after freeze')
    # Check the charged generation receipts, including on READY replay. Evaluation
    # failures are deliberately outside this ledger and never block saving a poster.
    preparation = Path(state['sample_edit_budget_dir'])/'preparation'
    for charge in ledger.get('charges', []):
        directory=charge.get('request_directory')
        if directory:
            root=(preparation/directory).resolve()
            if not root.is_relative_to(preparation.resolve()):
                raise ValueError('Editorial request receipt escapes its sample')
            from utils.persistence import read_json
            identity=read_json(root/'identity.json')['payload']['input_digest']
            read(root/'identity.json',identity)
            charges=list(root.glob('request_*.json'))
            if not charges:
                raise ValueError('Editorial charged request receipt missing')
            for receipt in charges:
                read(receipt,identity)
                response=receipt.with_name(receipt.name.replace('request_','response_'))
                read(response,identity)
    normalize_candidate(candidate, state, state['layout_spec']['zones'])
    spec = state['layout_spec']
    for zone in spec['zones']:
        if zone.get('section_ids') != [m['module_id'] for m in candidate['modules'] if m['zone_id'] == zone['zone_id']]:
            raise ValueError('Frozen region ownership/order differs from Curator')
    if state['optimized_story_board'] != make_board(candidate):
        raise ValueError('Compiled board differs from authored editorial content')
    if not compiled:
        return True
    layout = state.get('styled_layout') or state.get('design_layout') or []
    def plain(text):
        return ' '.join(''.join(t['text'] for t in tokenize_styling(str(text))).split())
    sections = state['optimized_story_board']['spatial_content_plan']['sections']
    known = {s['section_id'] for s in sections}
    if any(e.get('type') in {'text','section_title','visual','section_container'} and e.get('section_id') not in known for e in layout):
        raise ValueError('Unexpected editorial display module')
    meta = state['narrative_content'].get('meta', {})
    expected_header = str(meta.get('poster_title', state.get('poster_name', 'Title'))) + '\n' + str(meta.get('authors', state.get('authors', 'Authors')))
    if [e.get('content') for e in layout if e.get('type') == 'title'] != [expected_header]:
        raise ValueError('Rendered paper title/authors differ from the editorial snapshot')
    for section in sections:
        sid = section['section_id']
        text = '\n'.join(str(e.get('content','')) for e in layout if e.get('type') == 'text' and e.get('section_id') == sid)
        expected = FontAgent._escape_formatting_literals('\n'.join(presentation_lines(section)))
        titles = [e.get('section_title') for e in layout if e.get('type') == 'section_title' and e.get('section_id') == sid]
        if plain(text) != plain(expected) or titles != [section['section_title']]:
            raise ValueError('Renderer-visible text differs from editorial snapshot: '+sid)
        module = next(m for m in candidate['modules'] if m['module_id'] == sid)
        visuals = [e.get('visual_id') for e in layout if e.get('type') == 'visual' and e.get('section_id') == sid]
        if visuals != module['visual_ids']:
            raise ValueError('Renderer-visible visuals differ from authored ownership: '+sid)
        containers = [e for e in layout if e.get('type') == 'section_container' and e.get('section_id') == sid]
        if len(containers) != 1 or containers[0].get('zone_id') != module['zone_id']:
            raise ValueError('Rendered module changed its authored region: '+sid)
    for zone in spec['zones']:
        ordered = sorted((e for e in layout if e.get('type') == 'section_container' and
                          e.get('zone_id') == zone['zone_id']), key=lambda e:e['y'])
        if [e['section_id'] for e in ordered] != zone['section_ids']:
            raise ValueError('Rendered within-region order differs from Curator')
    return True
