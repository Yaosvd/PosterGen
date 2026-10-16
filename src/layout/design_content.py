"""Bounded editorial hints; no new prose, semantic gate or admission policy."""

from src.layout.paper_profile import narrative_role
from utils.grounded_content import all_publishable_claims, claim_root_id
from src.layout.reading_flow import ROLE_RANK, ordered_known, reading_conflicts


DESIGN_POLICY_VERSION = "grounded_family_design_v2"
ROLE_GROUPS = (
    {'foundation', 'background', 'problem', 'motivation', 'insight'},
    {'method', 'theory'}, {'results', 'evaluation'},
    {'conclusion', 'impact', 'implications', 'discussion'},
)


def candidate_quality_key(candidate):
    hints = candidate.get('content_quality_hints') or {}
    return (-len(hints.get('missing_core_roots') or []),
            -len(hints.get('reading_conflicts') or []),
            -len(hints.get('thin_section_ids') or []),
            -len(hints.get('completion_section_ids') or []))


class ContentPriorities:
    def __init__(self, state, sections):
        self.claims = all_publishable_claims(state)
        self.planned = {str(s.get('section_id')): s for s in
                        (state.get('narrative_plan') or {}).get('sections', [])
                        if isinstance(s, dict)}
        self.source = {str(s['section_id']): s for s in sections}
        self.evidence = {str(c): set(self.claims.get(str(c), {}).get('evidence_ids') or [])
                         for s in sections for c in s.get('claim_ids', [])}
        self.core = set()
        self.available = set()
        self._values = {}
        excluded = {tuple(item) for item in (state.get('revision_recovery_policy') or {}).get('excluded_claim_roots', [])}
        self.reference_roots = {}
        for s in sections:
            ids = set(s.get('claim_ids') or [])
            sid = str(s['section_id'])
            roots = set(s.get('curated_claim_roots') or [self.root(c) for c in ids])
            roots = {root for root in roots if (sid, root) not in excluded}
            self.reference_roots[sid] = roots
            self.available.update(roots)
            # Core annotations are preferences, never exact-wording locks.
            self.core.update(self.root(c) for c in s.get('core_claim_ids', []) if self.root(c) in roots)
        self.high_evidence = {str(e) for s in self.planned.values()
                              if int(s.get('importance', 2) or 2) == 1
                              for e in s.get('evidence_ids', [])}

    def root(self, claim_id):
        return claim_root_id(self.claims.get(str(claim_id), {'claim_id': str(claim_id)}))

    def role(self, section):
        return narrative_role(self.planned.get(str(section.get('section_id')), {}))

    def rank(self, section):
        plan_ids = list(self.planned)
        sid = str(section.get('section_id'))
        return (ROLE_RANK.get(self.role(section), 5),
                plan_ids.index(sid) if sid in plan_ids else len(plan_ids), sid)

    def summary(self, selected):
        roots = {self.root(c) for s in selected for c in s.get('claim_ids', [])}
        evidence = {str(e) for s in selected for c in s.get('claim_ids', [])
                    for e in self.claims.get(str(c), {}).get('evidence_ids', [])}
        roles = {self.role(s) for s in selected if self.role(s)}
        available_roles = {self.role(s) for s in self.source.values() if self.role(s)}
        available_groups = [g for g in ROLE_GROUPS if g & available_roles]
        covered_groups = sum(bool(g & roles) for g in available_groups)
        thin = []
        diagnostics = []
        for s in selected:
            original = self.source.get(str(s['section_id']), {})
            original_roots = self.reference_roots.get(str(s['section_id']), set())
            visible_roots = {self.root(c) for c in s.get('claim_ids', [])}
            # Core labels do not excuse loss of the rest of a module. A short
            # original source is only a risk hint, never a semantic failure.
            lost = original_roots - visible_roots
            if len(original_roots) >= 2 and len(visible_roots) == 1:
                thin.append(str(s['section_id']))
            diagnostics.append({
                'section_id': str(s['section_id']),
                'missing_original_roots': sorted(lost),
                'visible_root_count': len(visible_roots),
                'short_text_only': (len(visible_roots) <= 1 and not s.get('visual_assets')
                                    and sum(len(t) for t in s.get('text_content', [])) <= 160),
            })
        return {'core_coverage': len(roots & self.core) / max(1, len(self.core)),
                'root_coverage': len(roots & self.available) / max(1, len(self.available)),
                'high_evidence_coverage': len(evidence & self.high_evidence) / max(1, len(self.high_evidence)),
                'role_coverage': covered_groups / max(1, len(available_groups)),
                'thin_section_ids': sorted(thin),
                'module_diagnostics': diagnostics,
                'missing_core_roots': sorted(self.core - roots),
                'missing_role_hints': sorted(available_roles - roles),
                'metadata_is_not_scientific_proof': True}

    def value(self, selected):
        key = tuple((s['section_id'], tuple(s.get('claim_ids', []))) for s in selected)
        if key in self._values:
            return self._values[key]
        q = self.summary(selected)
        value = (q['core_coverage'] + q['high_evidence_coverage']
                 + q['role_coverage'] - 0.25 * len(q['thin_section_ids']))
        if len(self._values) < 4096:
            self._values[key] = value
        return value


def select_beam(expanded, width, coverage_key, visual_key, priorities, zone_heights, reading_key=None):
    """Keep coverage, imagery, compact and editorial paths within one budget."""
    def compact(item):
        # Reward future room, without pretending estimates prove impossibility.
        use = sum(item['heights'][z] / max(zone_heights[z], .1) for z in zone_heights)
        return (len(item['selected']), -use, priorities.value(item['selected']))

    rankings = [sorted(expanded, key=coverage_key, reverse=True),
                sorted(expanded, key=lambda x: (visual_key(x), coverage_key(x)), reverse=True),
                sorted(expanded, key=compact, reverse=True),
                sorted(expanded, key=lambda x: (len(x['selected']), reading_key(x) if reading_key else 0,
                                               priorities.value(x['selected']),
                                               coverage_key(x)), reverse=True)]
    chosen, seen = [], set()
    def identity(item):
        return (tuple((z, tuple(ids)) for z, ids in item['assignments'].items()),
                tuple((s['section_id'], tuple(s.get('claim_ids', [])),
                       tuple(v.get('visual_id') for v in s.get('visual_assets', [])))
                      for s in item['selected']))
    while len(chosen) < width and any(rankings):
        for ranking in rankings:
            while ranking:
                item = ranking.pop(0)
                key = identity(item)
                if key not in seen:
                    chosen.append(item)
                    seen.add(key)
                    break
            if len(chosen) >= width:
                break
    return chosen


def apply_reading_flow(spec, selected, priorities, contract, locked=False, constraints=None):
    """Change real per-zone stacking, not just the reported reading-order list."""
    from src.layout.family_contract import ordered_zones
    constraints = constraints or {}
    if locked or constraints.get('reading_order') or contract.reading == 'neutral':
        return
    for zone in spec['zones']:
        ids = zone.get('section_ids', [])
        zone['section_ids'] = ordered_known(ids, lambda sid: priorities.role(selected[sid]),
                                           lambda sid: priorities.rank(selected[sid]))
    spec['zones'] = ordered_zones(spec['zones'], contract)
    spec['reading_order'] = [sid for zone in spec['zones'] for sid in zone.get('section_ids', [])]


def flow_conflicts(spec, selected, priorities, contract):
    return reading_conflicts(spec, contract, lambda sid: priorities.role(selected[sid]))
