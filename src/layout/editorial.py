"""Bounded poster editing of the explicit current board.

Presentation metadata never replaces verified scientific prose. Labels are
optional local extracts, dependencies are local claim roots, and regrouping is a
content-preserving, same-zone alternative rather than a semantic admission gate.
"""

from copy import deepcopy
import re

from utils.grounded_content import layout_claims as all_publishable_claims, claim_root_id


from src.layout.body_presentation import (
    LEGACY_LABELS, extract_label, paragraphs, paragraph_text, wording_issues,
)

EDITORIAL_POLICY_VERSION = 'poster_editorial_v4'
KINDS = {'definition', 'goal', 'setup', 'method', 'result', 'interpretation', 'limitation'}
LABELS = LEGACY_LABELS  # Read-only compatibility for locked historical boards.
KIND_RANK = {'definition': 0, 'goal': 0, 'setup': 1, 'method': 2,
             'result': 3, 'interpretation': 4, 'limitation': 4}


class EditorialFitResult(tuple):
    """Ordinary three-item fit result with a runtime-only rollback attachment."""


def remember_baseline(state, result):
    baseline = getattr(result, 'editorial_baseline', None)
    if baseline is None or '_quality_repair_baseline' in state:
        return
    from src.layout.module_repair import CONTENT_FIELDS
    state['_quality_repair_baseline'] = {
        'attempt_id': (state.get('iteration_context') or {}).get('attempt_id'),
        'fields': {key: deepcopy(state.get(key)) for key in CONTENT_FIELDS},
        'result': deepcopy(baseline),
    }


def sections(board):
    return (board or {}).get('spatial_content_plan', {}).get('sections', [])


def locked(state):
    return bool(state.get('fit_locked') or state.get('fixed_layout_topology'))


def _root(cid, claims):
    return claim_root_id(claims.get(cid, {'claim_id': cid}))


def _kind(text, claim, role):
    """Conservative discourse hints, never evidence of a scientific relationship."""
    if re.search(r'^(?:the )?(?:dataset|evaluation|experiments?|test set|training set)\s+'
                 r'(?:uses?|comprises?|contains?|includes?|consists? of|is conducted)', text, re.I):
        return 'setup'
    if re.search(r'^(?:in [^,]{1,35},\s*)?(?:the )?search space is divided\b', text, re.I):
        return 'setup'
    if role in {'results', 'evaluation'} and claim.get('claim_type') in {'numeric', 'comparative'}:
        return 'result'
    return ''


def prepare_board(board, state, raw_sections=()):
    """Sanitize optional Curator hints without editing wording or geometry."""
    result = deepcopy(board)
    claims = all_publishable_claims(state)
    planned = {str(s.get('section_id')): s for s in (state.get('narrative_plan') or {}).get('sections', [])}
    raw = {str(s.get('section_id')): s for s in raw_sections if isinstance(s, dict)}
    for section in sections(result):
        sid = str(section['section_id'])
        ids = section.get('claim_ids') or []
        existing = section.get('editorial') or {}
        hints = raw.get(sid, {}).get('claim_layout', existing.get('items', []))
        if not isinstance(hints, list):
            hints = []
        hints = {str(h.get('claim_id')): h for h in hints if isinstance(h, dict)}
        role = str(planned.get(sid, {}).get('narrative_role') or '').lower()
        local_ids = set(ids) | {h['claim_id'] for h in existing.get('items', []) if isinstance(h.get('claim_id'), str)}
        active_by_root = {_root(c, claims): c for c in ids}
        items = []
        for cid, text in zip(ids, section.get('text_content') or []):
            root = _root(cid, claims)
            hint = hints.get(cid) or next((h for c, h in hints.items() if _root(c, claims) == root), {})
            kind = hint.get('kind')
            if not isinstance(kind, str) or kind not in KINDS:
                kind = _kind(str(text), claims.get(cid, {}), role)
            requires = hint.get('requires_claim_ids') or []
            if not isinstance(requires, list):
                requires = []
            # Cycles remain all-or-none selection groups below. Never borrow IDs.
            requires = list(dict.fromkeys(active_by_root.get(_root(c, claims), c)
                            for c in requires[:32] if isinstance(c, str) and c in local_ids and c != cid))
            parent = hint.get('parent_claim_id')
            parent = parent if isinstance(parent, str) and parent in local_ids and parent != cid else None
            if parent:
                parent = active_by_root.get(_root(parent, claims), parent)
            if parent and parent not in requires:
                requires.append(parent)
            items.append({'claim_id': cid, 'kind': kind, 'requires_claim_ids': requires,
                          'parent_claim_id': parent,
                          'display_label': extract_label(hint.get('display_label'), text,
                                                         section.get('section_title', '')),
                          'step_index': (hint.get('step_index') if isinstance(hint.get('step_index'), int)
                                         and not isinstance(hint.get('step_index'), bool) else None)})
        items.extend(deepcopy(h) for h in existing.get('items', []) if h.get('claim_id') not in ids
                     and _root(h.get('claim_id'), claims) not in active_by_root)
        graph = {h['claim_id']: h['requires_claim_ids'] for h in items}
        colors = {}
        def cycle(cid):
            if colors.get(cid):
                return colors[cid] == 1
            colors[cid] = 1
            if any(cycle(c) for c in graph.get(cid, [])):
                return True
            colors[cid] = 2
            return False
        if any(cycle(cid) for cid in graph):
            for item in items:
                item['parent_claim_id'] = None
        candidates = raw.get(sid, {}).get('title_candidates', existing.get('title_candidates', []))
        if not isinstance(candidates, list):
            candidates = []
        from src.workflow.sample_modules import source_units
        source_ids = sorted({sid for c in ids if c in claims for sid in source_units(claims[c])})
        style = raw.get(sid, {}).get('presentation_style', existing.get('presentation_style'))
        section['editorial'] = {
            **existing, 'version': EDITORIAL_POLICY_VERSION, 'items': items,
            'source_title': existing.get('source_title', str(section.get('section_title') or '')),
            'source_section_ids': list(dict.fromkeys(existing.get('source_section_ids', []) + source_ids)),
            'title_candidates': [c for c in candidates[:3] if isinstance(c, str) and len(c) <= 160],
            'order_mode': ('takeaway_first' if raw.get(sid, {}).get('narrative_style', existing.get('order_mode'))
                           == 'takeaway_first' else 'explanatory'),
            'presentation_style': style if isinstance(style, str) and style in {'plain', 'topics', 'steps'} else 'plain',
            'module_purpose': (raw.get(sid, {}).get('module_purpose', existing.get('module_purpose'))
                               if raw.get(sid, {}).get('module_purpose', existing.get('module_purpose')) in
                               {'primary', 'context', 'supporting'} else ''),
        }
    return result


def dependencies_met(section, claims):
    metadata = section.get('editorial') or {}
    if metadata.get('version') not in {'poster_editorial_v1', 'poster_editorial_v2', 'poster_editorial_v3', EDITORIAL_POLICY_VERSION}:
        return True
    visible = {_root(c, claims) for c in section.get('claim_ids', [])}
    for h in metadata.get('items', []):
        if _root(h['claim_id'], claims) in visible:
            if any(_root(c, claims) not in visible for c in h.get('requires_claim_ids', [])):
                return False
    return True


def presentation_lines(section):
    """Return exact claim sentences with optional non-scientific labels/bullets."""
    meta = section.get('editorial') or {}
    if meta.get('version') not in {'poster_editorial_v1', 'poster_editorial_v2', 'poster_editorial_v3', EDITORIAL_POLICY_VERSION} or not meta.get('active') or meta.get('body_style') == 'flat':
        return [str(t).strip() for t in section.get('text_content', []) if str(t).strip()]
    return [paragraph_text(p) for p in paragraphs(section)]


def presentation_line_count(text, width, font_name, font_size, description=None):
    """Measure bold label runs and per-paragraph indents, not all-bold prose.

    The small width reserve also covers later keyword emphasis; the ordinary
    final rendered-glyph audit remains mandatory and may roll this edit back.
    """
    from PIL import ImageFont
    from src.layout.measurement_context import current_context, file_identity
    from src.layout.text_height_measurement import get_font_file_path
    from utils.inline_math import visible_inline_math_text
    context = current_context()
    paths = [get_font_file_path(font_name, bold=bold) for bold in (False, True)]
    identities = tuple(file_identity(p) for p in paths)

    def compute():
        fonts = [(context.memo('font', (identity, font_size), lambda p=p: ImageFont.truetype(p, int(font_size)))
                  if context and context.settings['enabled'] else ImageFont.truetype(p, int(font_size)))
                 for p, identity in zip(paths, identities)]
        total = 0
        space = float(fonts[0].getlength(' ')) * 1.03
        for paragraph_index, paragraph in enumerate(text.split('\n')):
            line = visible_inline_math_text(paragraph.strip())
            inset = .30 if line.startswith('◦ ') else 0
            available = max(1, (width - .20 - inset) * 72 * .98)
            if description is not None:
                item = description[paragraph_index] if paragraph_index < len(description) else {}
                label = item.get('label', '') if item and paragraph_text(item) == paragraph else ''
            else:
                label = next((label for label in LABELS.values() if line.startswith(('• ' + label + ':', '◦ ' + label + ':'))), '')
            bold_words = len(label.split()) + 1 if label else 0
            used, lines = 0, 1
            for index, word in enumerate(line.split()):
                face = int(bool(label and 1 <= index < bold_words))
                font = fonts[face]
                word_width = (context.memo('glyph', ('poster_editorial_word_v1', identities[face], font_size, word),
                                          lambda: float(font.getlength(word)))
                              if context and context.settings['enabled'] else float(font.getlength(word))) * 1.03
                gap = space if used else 0
                if used and used + gap + word_width > available:
                    lines += 1
                    used = word_width
                else:
                    used += gap + word_width
            total += lines
        return total
    style_key = tuple((p['prefix'], p['label'], p['indent_inches']) for p in description) if description is not None else None
    key = ('poster_editorial_lines_v2', text, width, font_name, font_size, identities, style_key)
    return context.memo('line', key, compute) if context and context.settings['enabled'] else compute()


def _title_candidates(section):
    title = str((section.get('editorial') or {}).get('source_title') or section.get('section_title') or '')
    short = re.sub(r'^(?:The Challenge of|Defining the|Understanding the)\s+', '', title, flags=re.I)
    short = re.sub(r'^(?:Performance Evaluation|Experimental Evaluation):\s*', '', short, flags=re.I)
    short = re.sub(r'\s+for (?:Scalable|Efficient|Large[- ]Scale)\b.*$', '', short, flags=re.I)
    short = re.sub(r'\bStudies and\b', '&', short, flags=re.I)
    # Only remove editorial filler; never cut a phrase to a word-count prefix.
    short = re.sub(r'\bFeature Utility Analysis\b', 'Feature Analysis', short, flags=re.I)
    short = re.sub(r'\bData Integration and Experimental Setup\b', 'Data & Setup', short, flags=re.I)
    short = re.sub(r'^Implications for (.+)$', r'\1 Implications', short, flags=re.I)
    hints = {h['claim_id']: h for h in (section.get('editorial') or {}).get('items', [])}
    if (section.get('claim_ids') and not section.get('visual_assets')
            and all(hints.get(c, {}).get('kind') == 'setup' for c in section['claim_ids'])):
        text = ' '.join(section.get('text_content', [])).lower()
        return ['Dataset' if 'dataset' in text else 'Evaluation Setup', title]
    return [*(section.get('editorial') or {}).get('title_candidates', []), short, title]


def _summary(board):
    return {'module_count': len(sections(board)),
            'claim_count': sum(len(s.get('claim_ids', [])) for s in sections(board)),
            'title_word_counts': {s['section_id']: len(str(s.get('section_title') or '').split()) for s in sections(board)},
            'emphasized_section_ids': [s['section_id'] for s in sections(board) if s.get('importance_level') == 1],
            'panel_styles': {s['section_id']: deepcopy(s['editorial']['emphasis_resolution'])
                             for s in sections(board) if (s.get('editorial') or {}).get('emphasis_resolution')},
            'review_style_claim_ids': [cid for s in sections(board) for cid, t in zip(s.get('claim_ids', []), s.get('text_content', []))
                                       if wording_issues(t)]}


def choose_title(section):
    """Accept extractive, complete phrases; reject invented metrics/claims."""
    original = str(section.get('section_title') or '')
    if section.get('source_editorial_version') == 'source_editorial_v1':
        return original
    vocabulary = set(re.findall(r'[\w-]+', (original + ' '
                               + str((section.get('editorial') or {}).get('source_title') or '')
                               + ' ' + ' '.join(section.get('text_content', []))).lower()))
    vocabulary |= {'and', 'of', 'for', 'the', 'in', 'on', 'with', 'vs'}
    hints = {h['claim_id']: h for h in (section.get('editorial') or {}).get('items', [])}
    if section.get('claim_ids') and all(hints.get(c, {}).get('kind') == 'setup' for c in section['claim_ids']):
        vocabulary.add('setup')  # Closed discourse label, not a new scientific claim.
    valid = []
    for title in _title_candidates(section):
        title = ' '.join(title.split()).strip(' :;')
        words = re.findall(r'[\w-]+', title.lower())
        if (not words or len(words) > 12 or not set(words).issubset(vocabulary)
                or words[-1] in {'and', 'of', 'for', 'the', 'in', 'on', 'with', 'vs'}
                or re.search(r'\b(?:proves?|causes?|significant|best|novel)\b', title, re.I)):
            continue
        valid.append(title)
    # Avoid expanding short existing titles; retain long scientific terms when necessary.
    return min(valid, key=lambda t: (max(0, len(t.split()) - 5), len(t))) if valid else original


def _organize(section):
    meta = section['editorial']
    hints = {h['claim_id']: h for h in meta['items']}
    rank = ({**KIND_RANK, 'result': -1} if meta.get('order_mode') == 'takeaway_first' else KIND_RANK)
    pairs = list(zip(section.get('claim_ids', []), section.get('text_content', [])))
    steps = meta.get('presentation_style') == 'steps' and sorted(
        hints.get(cid, {}).get('step_index') or 0 for cid, _ in pairs) == list(range(1, len(pairs) + 1))
    if meta.get('module_prose_order'):
        pass  # Writer/Verifier own the module's explanatory sequence.
    elif steps:
        pairs.sort(key=lambda p: hints[p[0]]['step_index'])
    else:
        known = iter(sorted((p for p in pairs if hints.get(p[0], {}).get('kind') in KIND_RANK),
                            key=lambda p: rank[hints[p[0]]['kind']]))
        pairs = [next(known) if hints.get(p[0], {}).get('kind') in KIND_RANK else p for p in pairs]
    # Stable topological ordering protects explicit conditions and parent entries.
    ordered = []
    while pairs:
        ready = next((p for p in pairs if all(c in {x[0] for x in ordered}
                      for c in hints.get(p[0], {}).get('requires_claim_ids', [])
                      if c in section.get('claim_ids', []))), None)
        if ready is None:
            # Mutual prerequisites form one flat packet. Preserve its order;
            # the selection filter still requires every member to be present.
            ordered.extend(pairs)
            break
        ordered.append(ready)
        pairs.remove(ready)
    section['claim_ids'] = [p[0] for p in ordered]
    section['text_content'] = [p[1] for p in ordered]
    if meta.get('entry_label_applied'):
        section['section_title'] = section['section_title'].removeprefix('Key finding: ')
    section['section_title'] = choose_title(section)
    if meta.get('reading_entry') and not section.get('source_editorial_version'):
        section['section_title'] = 'Key finding: ' + section['section_title']
    meta['entry_label_applied'] = bool(meta.get('reading_entry')) and not section.get('source_editorial_version')
    meta['active'] = True


def _emphasize(board, state, spec):
    from src.layout.emphasis import resolve_emphasis
    resolved, color_report = resolve_emphasis(state.get('color_scheme') or {}, state.get('critic_config'))
    if resolved is None:
        for section in sections(board):
            meta = section.setdefault('editorial', {})
            for key in ('background', 'text_color', 'accent_color'):
                meta.pop(key, None)
            meta.update(emphasis_disabled=True, emphasis_resolution=deepcopy(color_report))
        return
    planned = {str(s.get('section_id')): s for s in (state.get('narrative_plan') or {}).get('sections', [])}
    hero = {sid for z in spec.get('zones', []) if z.get('role') == 'hero' for sid in z.get('section_ids', [])}
    candidates = sections(board)
    if not candidates:
        return
    def priority(s):
        sources = (s.get('editorial') or {}).get('source_section_ids') or [str(s['section_id'])]
        importance = min((int(planned.get(sid, {}).get('importance', 2) or 2) for sid in sources), default=2)
        return (s['section_id'] in hero, importance == 1, bool(s.get('core_claim_ids')),
                bool(s.get('visual_assets')), len(s.get('claim_ids', [])))
    eligible = [s for s in candidates if any(priority(s)[:3])]
    if not eligible:
        return
    chosen = max(eligible, key=priority)
    for s in candidates:
        s['importance_level'] = 1 if s is chosen else 2
        for key in ('background', 'text_color', 'accent_color', 'emphasis_resolution', 'emphasis_disabled'):
            s['editorial'].pop(key, None)
    chosen['editorial'].update(resolved, emphasis_resolution=color_report)


def _merge_thin(board, spec, state, family):
    """At most one adjacent same-role pair in the same occupied zone."""
    if not family.contract.allow_module_grouping or state.get('layout_revision_constraints'):
        return None
    from src.layout.design_content import ContentPriorities
    priorities = ContentPriorities(state, sections(board))
    by_id = {s['section_id']: s for s in sections(board)}
    for zone in spec.get('zones', []):
        ids = zone.get('section_ids', [])
        for a, b in zip(ids, ids[1:]):
            left, right = by_id[a], by_id[b]
            from src.layout.presentation_policy import context_pair, section_sources
            if state.get('verified_module_board') or state.get('joint_preparation'):
                origins = set(section_sources(left, state))
                if not origins or origins != set(section_sources(right, state)):
                    continue  # Do not undo distinct module writing tasks with auxiliary accumulation.
            problem_pair = context_pair(left, right, state)
            if not problem_pair and (not priorities.role(left) or priorities.role(left) != priorities.role(right)):
                continue
            if not any(len(s.get('claim_ids', [])) == 1 and not s.get('visual_assets') for s in (left, right)):
                continue
            result, layout = deepcopy(board), deepcopy(spec)
            target = next(s for s in sections(result) if s['section_id'] == a)
            other = next(s for s in sections(result) if s['section_id'] == b)
            # Keep the original title intentions as candidate labels; no inferred relationship.
            target['claim_ids'] += other['claim_ids']
            target['text_content'] += other['text_content']
            target['visual_assets'] += other.get('visual_assets', [])
            target['core_claim_ids'] = list(dict.fromkeys(target.get('core_claim_ids', []) + other.get('core_claim_ids', [])))
            target['curated_claim_roots'] = list(dict.fromkeys(target.get('curated_claim_roots', []) + other.get('curated_claim_roots', [])))
            target.setdefault('presentation', {})['required_claim_roots'] = sorted(set(
                target.get('presentation', {}).get('required_claim_roots', [])) | set(
                other.get('presentation', {}).get('required_claim_roots', [])))
            for sid, roots in other.get('presentation', {}).get('source_claim_roots', {}).items():
                current = target['presentation'].setdefault('source_claim_roots', {}).get(sid, [])
                target['presentation']['source_claim_roots'][sid] = sorted(set(current) | set(roots))
            support = set((target.get('presentation') or {}).get('supporting_claim_roots', []))
            support.update((other.get('presentation') or {}).get('supporting_claim_roots', []))
            if support:
                target.setdefault('presentation', {})['supporting_claim_roots'] = sorted(support)
            groups = (other.get('presentation') or {}).get('supporting_context_groups', [])
            if groups:
                target.setdefault('presentation', {}).setdefault('supporting_context_groups', []).extend(deepcopy(groups))
            target['editorial']['items'] += other['editorial']['items']
            target['editorial']['source_section_ids'] = list(dict.fromkeys(
                target['editorial']['source_section_ids'] + other['editorial']['source_section_ids']))
            target['editorial']['merged_section_ids'] = list(dict.fromkeys(
                target['editorial'].get('merged_section_ids', [a]) + other['editorial'].get('merged_section_ids', [b])))
            # Broad same-role title covers both retained subtopics without claiming novelty.
            target['section_title'] = ('Research Problem' if problem_pair else {
                'method': 'Methods', 'results': 'Results', 'problem': 'Research Problem',
                'conclusion': 'Conclusions'}.get(priorities.role(left), target['section_title']))
            target['editorial']['title_candidates'] = []
            target['editorial']['source_title'] = target['section_title']
            result['spatial_content_plan']['sections'].remove(other)
            for z in layout['zones']:
                z['section_ids'] = [sid for sid in z.get('section_ids', []) if sid != b]
            layout['reading_order'] = [sid for sid in layout.get('reading_order', []) if sid != b]
            return result, layout, {'kept_section_id': a, 'merged_section_id': b, 'zone_id': zone['zone_id']}
    return None


def source_for_fit(source, fitted, state, *, include_omitted_modules=False):
    """Keep omitted original roots attached to their edited display owner."""
    original = {s['section_id']: s for s in sections(source)}
    result = deepcopy(fitted)
    from src.layout.editorial_selection import root_allowed, filter_board
    if source.get('editorial_selection') and not result.get('editorial_selection'):
        result['editorial_selection'] = deepcopy(source['editorial_selection'])
    claims = all_publishable_claims(state)
    owned = set()
    for section in sections(result):
        visible_roots = {_root(c, claims) for c in section.get('claim_ids', [])}
        ids = (section.get('editorial') or {}).get('merged_section_ids', [section['section_id']])
        owned.update(ids)
        for sid in ids:
            src = original.get(sid, {})
            for cid, text in zip(src.get('claim_ids', []), src.get('text_content', [])):
                assigned = (section.get('presentation') or {}).get('source_claim_roots', {}).get(sid)
                if assigned is not None and _root(cid, claims) not in assigned:
                    continue
                if _root(cid, claims) not in visible_roots and root_allowed(result, state, claims.get(cid, {'claim_id': cid})):
                    section['claim_ids'].append(cid)
                    section['text_content'].append(text)
                    visible_roots.add(_root(cid, claims))
            section['curated_claim_roots'] = list(dict.fromkeys(
                section.get('curated_claim_roots', []) + [root for root in src.get('curated_claim_roots', [])
                    if (section.get('presentation') or {}).get('source_claim_roots', {}).get(sid) is None
                    or root in section['presentation']['source_claim_roots'][sid]]))
            visible_visuals = {v['visual_id'] for v in section.get('visual_assets', [])}
            section.setdefault('visual_assets', []).extend(deepcopy(v) for v in src.get('visual_assets', [])
                                                        if v['visual_id'] not in visible_visuals)
    if include_omitted_modules:
        sections(result).extend(deepcopy(s) for sid, s in original.items() if sid not in owned)
    # A previous completion may have materialized only its visible board. Its
    # original roots remain explicit provenance; recover base claims only, not
    # un-reverified bank alternatives or unrelated evidence-sharing claims.
    from utils.module_content import existing_module_candidates
    base_ids = {str(c.get('claim_id')) for c in (state.get('verified_claims') or {}).get('claims', [])}
    for section in sections(result):
        roots = set(section.get('curated_claim_roots', []))
        for claim in existing_module_candidates(state, result, section['section_id']):
            if claim['claim_id'] in base_ids and _root(claim['claim_id'], claims) in roots:
                section['claim_ids'].append(claim['claim_id'])
                section['text_content'].append(claim['text'])
    return prepare_board(filter_board(result, state), state)


def refine_editorial(agent, candidate, source_board, state, family, config, refine):
    """Two exact trials maximum; original feasible content is always a fallback."""
    audit = {'version': EDITORIAL_POLICY_VERSION, 'status': 'skipped', 'trials': [],
             'max_exact_trials': 2, 'scientific_prose_rewritten': False}
    from src.layout.body_presentation import BODY_PRESENTATION_VERSION
    from src.layout.emphasis import EMPHASIS_POLICY_VERSION
    audit.update(body_presentation_version=BODY_PRESENTATION_VERSION, emphasis_policy_version=EMPHASIS_POLICY_VERSION)
    audit['before'] = _summary(candidate['board'])
    if state.get('generation_route') != 'optimization_family' or locked(state):
        audit['reason'] = 'locked_or_standalone'
        return candidate, audit
    if not (config.get('poster_editorial') or {}).get('enabled', True):
        audit['reason'] = 'disabled'
        return candidate, audit
    from src.layout.module_repair import space_preserved
    baseline = candidate
    board = prepare_board(candidate['board'], state)
    for s in sections(board):
        _organize(s)
    if not state.get('layout_revision_constraints'):
        _emphasize(board, state, candidate['layout_spec'])
    plain = (board, deepcopy(candidate['layout_spec']), None)
    merged = _merge_thin(board, candidate['layout_spec'], state, family)
    if not merged and sections(board) == sections(candidate['board']):
        audit['reason'] = 'already_edited'
        return candidate, audit
    # Evaluate grouping first, then keep the ungrouped edited candidate as fallback.
    options = [merged, plain] if merged else [plain]
    claims = all_publishable_claims(state)
    old_occurrences = {(s['section_id'], _root(c, claims)) for s in sections(baseline['board']) for c in s.get('claim_ids', [])}
    old_visuals = {(s['section_id'], v['visual_id']) for s in sections(baseline['board']) for v in s.get('visual_assets', [])}
    for edited, spec, merge in options:
        item = {'status': 'no_exact_fit', 'merge': merge}
        audit['trials'].append(item)
        # Refill from this attempt's original modules, never a parent/other iteration.
        sources = source_for_fit(source_board, edited, state)
        for s in sections(sources):
            _organize(s)
        trial_state = dict(state)
        pins = {sid: z['zone_id'] for z in spec['zones'] for sid in z.get('section_ids', [])}
        trial_state['layout_revision_constraints'] = {
            **(state.get('layout_revision_constraints') or {}),
            'section_to_zone': pins, 'reading_order': list(spec['reading_order'])}
        trial = deepcopy(candidate)
        trial.update(board=edited, layout_spec=spec)
        # Keep the scientific sentences and title edits if added labels would
        # overfill an already dense zone. New Curator boards budget the rich
        # presentation before the initial search, rather than adding it late.
        if agent is not None and hasattr(agent, '_calculate_precise_section_height'):
            by_id = {s['section_id']: s for s in sections(edited)}
            body_width = float(state['poster_width']) - 2 * agent.poster_margin
            body_height = (float(state['poster_height']) - 2 * agent.poster_margin) * (1 - agent.title_height_fraction)
            for zone in spec['zones']:
                width, height = body_width * float(zone['width']), body_height * float(zone['height'])
                owned = [by_id[sid] for sid in zone.get('section_ids', [])]
                used = sum(agent._calculate_precise_section_height(s, width, state, height) for s in owned)
                used += max(0, len(owned) - 1) * agent._inter_section_spacing(state)
                if used > height - float(agent.layout_constants.get('body_render_reserve', 0)):
                    item.setdefault('flat_body_zone_ids', []).append(zone['zone_id'])
                    for section in owned:
                        section['editorial']['body_style'] = 'flat'
                        next(s for s in sections(sources) if s['section_id'] == section['section_id'])['editorial']['body_style'] = 'flat'
        details = {}
        trial = refine(agent, trial, sources, trial_state,
                       {**(config.get('explore_layout') or {}), 'max_exact_refill_steps': 8},
                       allow_changes=True, diagnostics=details)
        item['diagnostics'] = details
        if trial is None:
            continue
        def owner(sid):
            return merge['kept_section_id'] if merge and sid == merge['merged_section_id'] else sid
        new_occurrences = {(s['section_id'], _root(c, claims)) for s in sections(trial['board']) for c in s.get('claim_ids', [])}
        new_visuals = {(s['section_id'], v['visual_id']) for s in sections(trial['board']) for v in s.get('visual_assets', [])}
        if (not {(owner(s), c) for s, c in old_occurrences}.issubset(new_occurrences)
                or not {(owner(s), v) for s, v in old_visuals}.issubset(new_visuals)
                or any(not dependencies_met(s, claims) for s in sections(trial['board']))):
            item['status'] = 'content_regression'
            continue
        old_space = {**baseline, 'zone_utilization': baseline.get('exact_utilization', {})}
        new_space = {**trial, 'zone_utilization': trial.get('exact_utilization', {})}
        if not space_preserved(old_space, new_space):
            item['status'] = 'space_regression'
            continue
        item['status'] = 'adopted'
        audit.update(status='applied', reason='exact_content_preserving_edit')
        audit['after'] = _summary(trial['board'])
        # Final rollback captures the pre-editorial candidate, not a different board.
        trial['_editorial_baseline'] = deepcopy(baseline)
        return trial, audit
    audit['reason'] = 'no_nonregressing_exact_edit'
    return candidate, audit


def polish_wording(agent, state, current, family_id, *, optimizer=None):
    """At most one charged quality round for legacy review-style wording.

    All sentences remain verified variants. This optional pass cannot borrow
    another board, consume additional budgets, or publish a failed trial.
    """
    config = state.get('critic_config') or {}
    report = {'version': EDITORIAL_POLICY_VERSION, 'status': 'skipped', 'rounds_attempted': 0}
    audit = state.setdefault('capacity_repair_report', {})
    audit['editorial_wording'] = report
    if (state.get('generation_route') == 'standalone_classic' or locked(state)
            or not (config.get('poster_editorial') or {}).get('enabled', True)):
        report['reason'] = 'locked_or_disabled'
        return current
    actions = []
    for s in sections(current[0]):
        first = next(((cid, text) for cid, text in zip(s.get('claim_ids', []), s.get('text_content', []))
                      if wording_issues(text)), None)
        if first:
            cid, text = first
            actions.append({'operation': 'create_style_variant', 'section_id': s['section_id'],
                'claim_id': cid, 'target_max_characters': max(40, int(len(text) * 1.15) + 20),
                'reason': 'Direct poster prose; retain all essential facts and qualifications.'})
    actions = actions[:2]
    report['remaining_issue_claim_ids'] = [cid for s in sections(current[0])
        for cid, text in zip(s.get('claim_ids', []), s.get('text_content', [])) if wording_issues(text)]
    if not actions:
        report['reason'] = 'no_review_style_wording'
        return current
    from src.layout.repair_budget import charge_round, family_rounds_used
    settings = config.get('capacity_repair') or {}
    actions = actions[:max(0, min(2, int(settings.get('max_actions_per_round', 2))))]
    if not actions:
        report['reason'] = 'actions_disabled'
        return current
    optimization = config.get('content_optimization') or {}
    if not optimization.get('enabled', True) or not state.get('text_model'):
        report['reason'] = 'content_optimization_disabled_or_no_model'
        return current
    if (family_rounds_used(state, family_id) >= int(settings.get('max_rounds_per_family', 2))
            or not charge_round(state, 'quality', settings)):
        report['reason'] = 'shared_budget_exhausted'
        return current
    from src.layout.module_repair import CONTENT_FIELDS, content_preserved, space_preserved, _publish
    from src.agents.content_optimizer import content_optimizer
    from src.layout.feasibility import fit_family_layout, LayoutFeasibilityError
    saved = {key: deepcopy(state.get(key)) for key in CONTENT_FIELDS}
    trial = dict(state)
    trial.update(deepcopy(saved))
    trial['errors'] = []
    report.update(status='not_adopted', rounds_attempted=1)
    audit['rounds_attempted'] = int(audit.get('rounds_attempted', 0)) + 1
    audit.setdefault('rounds', []).append({'phase': 'quality', 'purpose': 'poster_editorial', 'status': 'charged'})
    optimizer = optimizer or content_optimizer
    trial = optimizer(trial, board_override=current[0], actions_override=actions, save=False)
    accepted = (trial.get('content_revision') or {}).get('accepted_actions') or []
    if trial.get('errors') or not accepted:
        report['reason'] = 'no_verified_edit'
        return current
    source = source_for_fit(current[0], trial['story_board'], trial)
    # Pin every owner and preserve stacking. No new geometry or grouping here.
    pins = {sid: z['zone_id'] for z in current[1]['zones'] for sid in z.get('section_ids', [])}
    original_constraints = deepcopy(trial.get('layout_revision_constraints'))
    trial['layout_revision_constraints'] = {**(original_constraints or {}),
        'section_to_zone': pins, 'reading_order': list(current[1]['reading_order']),
        'must_retain_claim_ids': [c for s in sections(trial['story_board']) for c in s.get('claim_ids', [])]}
    # This refit belongs to the current sample. It is not a historical-parent task.
    trial['fit_locked'] = True
    limited = deepcopy(config)
    limited.setdefault('explore_layout', {}).update(max_geometry_candidates_per_family=1,
                                                  max_exact_candidates=2, max_exact_refill_steps=8)
    limited['composition_refinement'] = {'enabled': False}
    limited['poster_editorial'] = {'enabled': False}
    try:
        fitted = fit_family_layout(agent, source, trial, family_id, config=limited, fixed_zones=current[1]['zones'])
    except LayoutFeasibilityError:
        report['reason'] = 'no_exact_fit'
        return current
    finally:
        trial['layout_revision_constraints'] = original_constraints
    if (not content_preserved(current[0], fitted[0], trial) or not space_preserved(current[2], fitted[2])):
        report['reason'] = 'content_or_space_regression'
        return current
    _publish(state, trial, fitted[0])
    report.update(status='applied', reason='verified_and_exact_fitted')
    report['remaining_issue_claim_ids'] = [cid for s in sections(fitted[0])
        for cid, text in zip(s.get('claim_ids', []), s.get('text_content', [])) if wording_issues(text)]
    if '_quality_repair_baseline' not in state:
        state['_quality_repair_baseline'] = {
            'attempt_id': (state.get('iteration_context') or {}).get('attempt_id'),
            'fields': saved, 'result': deepcopy(current)}
    fitted[2]['editorial'] = {**deepcopy(current[2].get('editorial') or {}), 'wording': deepcopy(report)}
    return fitted
