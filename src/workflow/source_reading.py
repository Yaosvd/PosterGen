"""Image-bound natural-reading judgments; no source-order or axis-order oracle."""
from copy import deepcopy
from pathlib import Path
import re

from src.workflow.source_document import SourceOutputError, VERSION, check_stop
from src.workflow.source_requests import object_schema, STRING, STRINGS
from utils.persistence import digest, file_hash

READING_VERSION = 'visual_natural_reading_v1'
ROUTES = {'type': 'array', 'items': STRINGS}
READING_SCHEMA = object_schema({
    'candidate_id': STRING, 'image_digest': STRING, 'text_digest': STRING,
    'geometry_digest': STRING, 'style_digest': STRING,
    'status': {'type': 'string', 'enum': ['clear','needs_revision','ambiguous','incomplete']},
    'primary_routes': ROUTES, 'acceptable_alternatives': {'type': 'array', 'items': ROUTES},
    'shared_module_ids': STRINGS,
    'issues': {'type': 'array', 'items': object_schema({'module_ids': STRINGS, 'reason': STRING,
        'suggestion': STRING})}, 'reason': STRING})
READING_INSTRUCTIONS = '''Observe the ACTUAL image first. Infer likely primary and acceptable alternative
human reading routes from grouping, typography, spanning and actual physical geometry.
Top-to-bottom and left-to-right are peers: column-major, row-major and mixed routes
can all be valid. Independent branches/matrices need not have one total permutation.
Never use paper-source order, role rank, family reading_order or curator intention as
the answer key. Then assess semantic continuity, local definitions/conditions,
ambiguous entrances and forced backtracking. Report only what this exact image shows.
Return reading_review with the exact supplied fingerprints. primary_routes is a list
of branch paths whose union covers every module; shared_module_ids declares shared
opening/convergence nodes. Each acceptable alternative has the same structure.
If the image cannot be assessed, use incomplete, never assume clear. Do not predict
that proposed edits have already passed a new visual review. Reading is a quality
judgment; physical geometry and original-source truth are checked separately.'''


def reading_context(state, board, spec, layout, image, candidate_id):
    sections = board.get('spatial_content_plan', {}).get('sections', [])
    boxes = {str(e['section_id']): {k:e[k] for k in ('x','y','width','height')}
             for e in layout if e.get('type') == 'section_container'}
    text = [{'module_id': s['section_id'], 'title': s['section_title'],
             'text': s['text_content']} for s in sections]
    # Fingerprints bind actual input, not an asserted natural order. Array order
    # is deliberately lexical here to avoid presenting the desired route as truth.
    text.sort(key=lambda s: s['module_id'])
    binding = {'candidate_id': candidate_id, 'image_digest': file_hash(image) if image else '',
        'text_digest': digest(text), 'geometry_digest': digest({'spec': spec, 'boxes': boxes}),
        'style_digest': digest({'layout': layout, 'styles': state.get('styling_interfaces'),
                                'palette': state.get('color_scheme')})}
    return {'version': READING_VERSION, 'binding': binding,
            'poster_inches': [state['poster_width'], state['poster_height']],
            'modules': [{**s, 'bbox_inches': boxes.get(s['module_id'])} for s in text],
            'groups': [{'zone_id': z['zone_id'], 'bbox_normalized': {k:z[k] for k in ('x','y','width','height')},
                        'module_ids': sorted(z.get('section_ids', []))} for z in spec.get('zones', [])],
            'axis_priority': 'equal', 'has_actual_image': bool(image)}


def check_reading_review(review, context):
    if any(review[k] != v for k,v in context['binding'].items()):
        raise SourceOutputError('Reading review belongs to a different image/text/geometry/style')
    ids = {m['module_id'] for m in context['modules']}
    shared = set(review['shared_module_ids'])
    if not shared <= ids or len(shared) != len(review['shared_module_ids']):
        raise SourceOutputError('Invalid shared reading nodes')
    if not context['has_actual_image'] and review['status'] != 'incomplete':
        raise SourceOutputError('No image was observed; visual reading cannot be complete')
    def check(routes, complete):
        flat = [mid for route in routes for mid in route]
        if not set(flat) <= ids or any(len(set(route)) != len(route) or not route for route in routes):
            raise SourceOutputError('Reading route has foreign, empty or duplicated module IDs')
        if any(flat.count(mid) > 1 and mid not in shared for mid in flat):
            raise SourceOutputError('Repeated route nodes need explicit branch sharing')
        if complete and set(flat) != ids:
            raise SourceOutputError('Reading review omits visible modules')
    check(review['primary_routes'], review['status'] != 'incomplete')
    for routes in review['acceptable_alternatives']:
        check(routes, True)
    for issue in review['issues']:
        if not issue['module_ids'] or not set(issue['module_ids']) <= ids or not issue['reason'].strip():
            raise SourceOutputError('Reading issue has no actual module location/reason')
    if review['status'] == 'clear' and review['issues']:
        raise SourceOutputError('Clear reading verdict contradicts reported reading issues')
    return review


def _draft_preview(state, result):
    """Real editable rendering, isolated from publication and any verified-bank claim."""
    from src.workflow.source_requests import save, read
    from src.agents.layout_agent import LayoutAgent
    from src.agents.font_agent import FontAgent
    from src.agents.renderer import Renderer
    from src.layout.feasibility import validate_compiled_layout
    board, spec, report = deepcopy(tuple(result))
    candidate_id = state['source_candidate']['candidate_id']
    key = digest({'candidate': candidate_id, 'board': board, 'spec': spec,
                  'palette': state.get('color_scheme'), 'styles': state.get('styling_interfaces')})
    root = Path(state.get('sample_preparation_dir') or state['output_dir'])/'source/previews'/key
    ready = root/'READY.json'
    if ready.exists():
        record = read(ready, key)
        if any(file_hash(record[k]) != record[k+'_digest'] for k in ('png','pptx')):
            raise ValueError('Saved draft preview digest mismatch')
        return record
    charge = root/'CHARGED.json'
    if charge.exists():
        raise ValueError('Draft preview charged but missing completion; refusing automatic rerender')
    if len(list(root.parent.glob('*/CHARGED.json'))) >= 4:
        raise SourceOutputError('Sample preview allowance exhausted')
    check_stop(state)
    save(charge, {'input_digest': key, 'limit': 4, 'purpose': 'draft_only_not_publishable'})
    view = dict(state)
    view.update(output_dir=str(root), story_board=board, optimized_story_board=board,
                layout_spec=spec, errors=[], current_candidate=None, render_history=None)
    # No FontAgent model call for a draft preview: deterministic actual styling.
    from src.agents.color_agent import ColorAgent
    from src.agents.section_title_designer import SectionTitleDesigner
    if not view.get('color_scheme'):
        color = ColorAgent()
        view['color_scheme'] = color._add_contrast_color(color._generate_color_scheme('#1E3A8A'))
    view['section_title_design'] = SectionTitleDesigner()._generate_colorblock_design(board, view['color_scheme'])
    view = LayoutAgent()(view, mode='final')
    layout = view.get('design_layout') or []
    agent = LayoutAgent()
    preflight = validate_compiled_layout(layout, spec, view, poster_margin=agent.poster_margin,
                                         title_height_fraction=agent.title_height_fraction)
    if not preflight['passed']:
        raise SourceOutputError('Draft preview compiled preflight failed')
    font = FontAgent()
    view['styling_interfaces'] = font.get_styling_interfaces()
    view['styled_layout'] = font._apply_styling(layout, view['color_scheme'], {'section_keywords': {}}, view)
    renderer = Renderer()
    renderer.styling_interfaces = view['styling_interfaces']
    pptx = root/'draft.pptx'
    renderer._render_presentation(view, pptx)
    png = renderer._convert_to_png(pptx)
    if not png or not Path(png).is_file():
        raise SourceOutputError('Actual draft preview PNG could not be rendered')
    context = reading_context(view, board, spec, view['styled_layout'], png, candidate_id)
    record = {'input_digest': key, 'candidate_id': candidate_id, 'status': 'draft_not_publishable',
        'png': str(png), 'pptx': str(pptx), 'png_digest': file_hash(png), 'pptx_digest': file_hash(pptx),
        'reading_context': context, 'preflight': preflight,
        'style_scope': 'deterministic draft palette and typography; final styling may differ'}
    save(ready, record)
    return record


def draft_preview(state, result):
    import time
    started = time.perf_counter()
    try:
        return _draft_preview(state, result)
    finally:
        metrics = state.get('timing_metrics')
        if metrics is not None:
            metrics.record_component('source_preview', time.perf_counter()-started,
                                     state.get('iteration_context', {}).get('iteration', 0))
