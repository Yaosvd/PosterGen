"""Paper-local family space briefs; plans are estimates, never fit certificates."""
from copy import deepcopy
from pathlib import Path
from math import log1p, sqrt

from src.agents.layout_agent import LayoutAgent
from src.layout.families import LayoutFamilyRegistry
from src.layout.family_contract import ordered_zones
from utils.persistence import _atomic_json


def family_brief(state):
    family_id = (state.get('sample_family') or {}).get('family') or (state.get('iteration_context') or {}).get('layout_family')
    if not family_id:
        raise ValueError('A family must be frozen before module planning')
    family = LayoutFamilyRegistry().get(family_id)
    agent = LayoutAgent()
    width = float(state['poster_width']) - 2*agent.poster_margin
    height = (float(state['poster_height']) - 2*agent.poster_margin)*(1-agent.title_height_fraction)
    contract = family.contract.to_dict()
    contract['conditional_roles'] = [(zone, tuple(dict.fromkeys([*roles, 'results', 'evaluation', 'discussion', 'interpretation'])))
        if set(roles) == {'conclusion'} else (zone, roles) for zone, roles in contract['conditional_roles']]
    return {'version': 'family_capacity_v2', 'family_id': family_id,
            'certifies_feasible_layout': False, 'contract': contract,
            'content_role_policy': 'joint_findings_closing_v1',
            'zones': [{**deepcopy(z), 'width_inches': round(z['width']*width, 4),
                       'height_inches': round(z['height']*height, 4)}
                      for z in ordered_zones(family.zones, family.contract)],
            'rule': 'Multiple display modules may stack in a zone; only contract-legal local topology variants are allowed.'}


def _priority(module, state):
    from src.workflow.sample_editorial import module_roles
    roles = module_roles(module, state)
    if roles & {'results', 'method', 'theory', 'insight'} and 'task_definition' not in roles:
        return 1.6
    if roles & {'evaluation', 'task_definition'}:
        return 1.0
    return .7


def _placements(modules, brief, state):
    """Bounded source-order partitions used only for uncertain writing estimates."""
    from src.workflow.sample_editorial import module_roles
    zones = brief['zones']
    conditional = {z: set(roles) for z, roles in brief['contract']['conditional_roles']}
    focus = set(brief['contract']['focus_roles'])
    beam = [(0.0, (), (0,)*len(zones))]
    for module in modules:
        roles = module_roles(module, state)
        expanded = []
        for score, owners, loads in beam:
            for index, zone in enumerate(zones):
                if owners and index < owners[-1]:
                    continue
                if loads[index] >= zone.get('capacity', 1):
                    continue
                if zone['zone_id'] in conditional and not roles & conditional[zone['zone_id']]:
                    continue
                if zone.get('role') in {'hero', 'spine'} and roles and not roles & focus:
                    continue
                updated = list(loads); updated[index] += 1
                area = zone['width']*zone['height']
                gain = _priority(module, state)*log1p(4*area)
                if module['visual_ids']:
                    gain += 2*zone['width']
                expanded.append((score+gain, owners+(index,), tuple(updated)))
        beam = sorted(expanded, key=lambda row: (-row[0], row[1]))[:128]
        if not beam:
            return []
    required = set(brief['contract']['required_zones'])
    beam = [row for row in beam if required <= {zones[i]['zone_id'] for i in row[1]}]
    # Retain several near alternatives instead of claiming the eventual solver ownership.
    beam.sort(key=lambda row: (-(row[0]-.75*sum(n == 0 for n in row[2])), row[1]))
    return [row[1] for row in beam[:16]]


def plan_family_capacity(state, layout_spec=None):
    """Use role/source-compatible estimates, or measured ownership before editing."""
    brief = family_brief(state)
    modules = state['sample_module_plan']['modules']
    if layout_spec:
        width = float(state['poster_width'])-2*LayoutAgent().poster_margin
        height = brief['zones'][0]['height_inches']/brief['zones'][0]['height']
        brief['zones'] = [{**deepcopy(z), 'width_inches': z['width']*width,
                          'height_inches': z['height']*height} for z in layout_spec['zones']]
        owners = {sid: i for i,z in enumerate(brief['zones']) for sid in z.get('section_ids', [])}
        placements = [tuple(owners[m['module_id']] for m in modules)] if all(m['module_id'] in owners for m in modules) else []
    else:
        placements = _placements(modules, brief, state)
    brief['assignment_status'] = 'measured_ownership' if layout_spec and placements else 'provisional_range' if placements else 'unresolved'
    brief['assignment_is_binding'] = False
    bins = [{**z, 'modules': []} for z in brief['zones']]
    for index, module in enumerate(modules):
        if placements:
            bins[placements[0][index]]['modules'].append(module)
    loads = []
    for index, module in enumerate(modules):
        candidates = [bins[i] for i in sorted({p[index] for p in placements})] if placements else bins
        estimates = []
        for zone in candidates:
            target_height = zone['height_inches']/max(1, len(zone['modules']))
            visual_height = 0.0
            for visual in module['visual_ids']:
                prefix, key = visual.split('_', 1)
                asset = (state.get('images' if prefix == 'figure' else 'tables') or {}).get(key, {})
                visual_height += max(.1, zone['width_inches']-.6)/max(.01, float(asset.get('aspect') or 1))+.3
            # Account for title wrapping using the same physical title measurer.
            from src.layout.title_metrics import measure_loop_title
            from src.config.poster_config import load_config
            config = load_config()
            title = measure_loop_title(module['title'], max(.5, zone['width_inches']-.6),
                config['typography']['fonts']['section_title'], config['typography']['sizes']['section_title'], config)['height']+.6
            text_height = max(.25, target_height-visual_height-title-1.0)
            estimates.append({'module_id': module['module_id'], 'zone_id': zone['zone_id'],
                'width_inches': zone['width_inches'], 'target_height_inches': round(target_height, 4),
                'visual_height_inches': round(visual_height, 4), 'title_height_inches': round(title, 4),
                'text_height_inches': round(text_height, 4),
                'space_pressure': visual_height+title+1.0 >= target_height,
                'weight': sqrt(max(.25, text_height)*max(.5, zone['width_inches']-.6))*_priority(module, state)})
        primary = next((r for r in estimates if placements and r['zone_id'] == bins[placements[0][index]]['zone_id']), estimates[0])
        primary['candidate_zone_ids'] = [r['zone_id'] for r in estimates]
        primary['width_range_inches'] = [min(r['width_inches'] for r in estimates), max(r['width_inches'] for r in estimates)]
        primary['assignment_status'] = brief['assignment_status']
        loads.append(primary)
    from src.config.poster_config import load_config
    font = load_config()['typography']['sizes']['body_text']
    scale = float(state['poster_width'])/54*float(state['poster_height'])/36*(44/float(font))**2
    total = sum(r['weight'] for r in loads)
    for module in modules:
        row = next(r for r in loads if r['module_id'] == module['module_id'])
        fraction = row.pop('weight')/total
        module['soft_word_range'] = [max(8, round(280*scale*fraction)), max(12, round(420*scale*fraction))]
        module['space_target'] = deepcopy(row)
    state['family_capacity'] = {**brief, 'modules': loads, 'word_reference': [round(280*scale), round(420*scale)]}
    _atomic_json(Path(state['output_dir'])/'content/family_capacity.json', state['family_capacity'])
    return state
