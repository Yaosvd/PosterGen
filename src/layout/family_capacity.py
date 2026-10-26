"""Paper-local family space briefs; plans are estimates, never fit certificates."""
from copy import deepcopy
from pathlib import Path

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
    return {'version': 'family_capacity_v1', 'family_id': family_id,
            'certifies_feasible_layout': False, 'contract': contract,
            'content_role_policy': 'joint_findings_closing_v1',
            'zones': [{**deepcopy(z), 'width_inches': round(z['width']*width, 4),
                       'height_inches': round(z['height']*height, 4)}
                      for z in ordered_zones(family.zones, family.contract)],
            'rule': 'Multiple display modules may stack in a zone; only contract-legal local topology variants are allowed.'}


def plan_family_capacity(state):
    """Allocate a provisional module space without model coordinates or prose."""
    brief = family_brief(state)
    modules = state['sample_module_plan']['modules']
    bins = [{**z, 'modules': [], 'visual_height': 0.0} for z in brief['zones']]
    sources = {u['section_id']: u for u in state['narrative_plan']['sections']}
    conditional = {z: set(roles) for z, roles in brief['contract']['conditional_roles']}
    for zone, roles in conditional.items():
        if roles == {'conclusion'}:
            roles.update({'results', 'evaluation', 'discussion', 'interpretation'})
    for module in modules:
        roles = {sources[s].get('narrative_role') for s in module['source_plan_unit_ids']}
        allowed = [z for z in bins if len(z['modules']) < z.get('capacity', 1) and
                   (z['zone_id'] not in conditional or roles & conditional[z['zone_id']])]
        if not allowed:
            # Keep an explicit pressure diagnosis. Do not invent/drop scientific modules.
            allowed = bins
        def pressure(z):
            return (len(z['modules'])/max(1, z.get('capacity', 1)), z['visual_height']/z['height_inches'])
        zone = min(allowed, key=pressure)
        zone['modules'].append(module)
        for visual in module['visual_ids']:
            prefix, key = visual.split('_', 1)
            asset = (state.get('images' if prefix == 'figure' else 'tables') or {}).get(key, {})
            zone['visual_height'] += max(.1, zone['width_inches']-.6)/max(.01, float(asset.get('aspect') or 1))+.3
    loads = []
    for zone in bins:
        for module in zone['modules']:
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
            loads.append({'module_id': module['module_id'], 'zone_id': zone['zone_id'],
                'width_inches': zone['width_inches'], 'target_height_inches': round(target_height, 4),
                'visual_height_inches': round(visual_height, 4), 'title_height_inches': round(title, 4),
                'text_height_inches': round(text_height, 4),
                'space_pressure': visual_height+title+1.0 >= target_height,
                'weight': max(.25, text_height)*max(.5, zone['width_inches']-.6)})
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
