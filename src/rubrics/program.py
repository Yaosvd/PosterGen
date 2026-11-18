"""Bounded drawing language. Model text is interpreted, never executed as Python.

The only output operations are poster(candidate) and draw(element). There is no
attribute access, import, filesystem, network, process, or shared-code API.
"""
import ast
from copy import deepcopy
import math
import operator

from utils.persistence import digest

MAX_SOURCE = 600000
FIXED_TYPES = {'title', 'conf_logo', 'aff_logo', 'qr_code'}


def execute_isolated(source):
    """Resource/fault isolation for the bounded interpreter; not an OS permission sandbox."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    if not isinstance(source,str) or len(source)>MAX_SOURCE:
        raise ValueError('Drawing program exceeds source limit')
    from utils.concurrency import inherited_lease
    env={k:v for k,v in os.environ.items() if k in {'PATH','LANG','LC_ALL','SYSTEMROOT'}}
    result=subprocess.run([sys.executable,'-m','src.rubrics.program'],input=source,text=True,
        capture_output=True,timeout=15,cwd=Path(__file__).resolve().parents[2],env=env,
        pass_fds=inherited_lease())
    if result.returncode:
        raise ValueError('Isolated drawing interpreter rejected program: '+result.stderr[-1000:])
    if len(result.stdout)>4000000:
        raise ValueError('Drawing document exceeds output limit')
    return json.loads(result.stdout)


def execute(source):
    if not isinstance(source, str) or len(source) > MAX_SOURCE:
        raise ValueError('Drawing program exceeds source limit')
    tree = ast.parse(source)
    if sum(1 for _ in ast.walk(tree)) > 50000:
        raise ValueError('Drawing program exceeds syntax limit')
    names, result, budget = {}, {'candidate': None, 'elements': []}, [60000]
    expanded = [0]
    def charge(value):
        import json
        expanded[0] += len(json.dumps(value,ensure_ascii=False,allow_nan=False))
        if expanded[0] > 4000000:
            raise ValueError('Drawing expansion limit exceeded')
    def tick():
        budget[0] -= 1
        if budget[0] < 0:
            raise ValueError('Drawing program step limit exceeded')
    def checked(value):
        if type(value) in (int, float) and (not math.isfinite(value) or abs(value) > 1e9):
            raise ValueError('Drawing numeric limit exceeded')
        if isinstance(value, (str, list, dict, tuple)) and len(value) > 100000:
            raise ValueError('Drawing value limit exceeded')
        return value
    def expr(node):
        tick()
        if isinstance(node, ast.Constant) and type(node.value) in (str, int, float, bool, type(None)):
            return checked(node.value)
        if isinstance(node, ast.Name) and node.id in names:
            charge(names[node.id])
            return deepcopy(names[node.id])
        if isinstance(node, (ast.List, ast.Tuple)):
            return [expr(n) for n in node.elts]
        if isinstance(node, ast.Dict) and all(k is not None for k in node.keys):
            keys = [expr(k) for k in node.keys]
            if any(type(k) is not str for k in keys) or len(keys) != len(set(keys)):
                raise ValueError('Drawing keys must be unique strings')
            return dict(zip(keys, (expr(v) for v in node.values)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd):
            value = expr(node.operand)
            if type(value) not in (int, float):
                raise ValueError('Numeric operand required')
            return checked(-value if isinstance(node.op, ast.USub) else value)
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div):
            a, b = expr(node.left), expr(node.right)
            if type(a) not in (int, float) or type(b) not in (int, float):
                raise ValueError('Only bounded numeric arithmetic is permitted')
            return checked({ast.Add: operator.add, ast.Sub: operator.sub,
                            ast.Mult: operator.mul, ast.Div: operator.truediv}[type(node.op)](a, b))
        if isinstance(node, ast.Subscript):
            value, key = expr(node.value), expr(node.slice)
            if type(value) not in (dict, list) or type(key) not in (str, int):
                raise ValueError('Invalid drawing lookup')
            return deepcopy(value[key])
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE):
            return {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}[type(node.ops[0])](expr(node.left), expr(node.comparators[0]))
        raise ValueError('Unsupported drawing expression: ' + type(node).__name__)
    def statements(nodes):
        for node in nodes:
            tick()
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name.startswith('_') or name in {'poster', 'draw'}:
                    raise ValueError('Reserved drawing name')
                names[name] = expr(node.value)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if not isinstance(call.func, ast.Name) or call.func.id not in {'poster', 'draw'} or len(call.args) != 1 or call.keywords:
                    raise ValueError('Only poster(dict) and draw(dict) are permitted')
                value = expr(call.args[0])
                if not isinstance(value, dict):
                    raise ValueError('Drawing command needs an object')
                if call.func.id == 'poster':
                    if result['candidate'] is not None:
                        raise ValueError('Exactly one poster declaration is required')
                    result['candidate'] = value
                else:
                    result['elements'].append(value)
                    if len(result['elements']) > 512:
                        raise ValueError('Too many drawing elements')
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name) and not node.orelse:
                values = expr(node.iter)
                if not isinstance(values, list) or len(values) > 64 or node.target.id.startswith('_'):
                    raise ValueError('Drawing loop must iterate a list of at most 64 items')
                for value in values:
                    names[node.target.id] = value
                    statements(node.body)
            elif isinstance(node, ast.If):
                statements(node.body if expr(node.test) else node.orelse)
            else:
                raise ValueError('Unsupported drawing statement: ' + type(node).__name__)
    statements(tree.body)
    if result['candidate'] is None or not result['elements']:
        raise ValueError('Drawing program produced no poster')
    digest(result)
    return result


def export(state):
    """Readable Python-subset code with a single authoritative body per module."""
    candidate = deepcopy(state['editorial_candidate'])
    elements = deepcopy(state['styled_layout'])
    for element in elements:
        if element.get('type') == 'text':
            for key in ('content', 'editorial_paragraphs', 'body_format'):
                element.pop(key, None)
        if element.get('type') == 'section_title':
            element.pop('section_title', None)
    return drawing_source(candidate, elements)


def restore_fixed_drawings(document, original):
    """Fill original editable slots in order; extra draws precede trailing fixed layers."""
    editable = [e for e in document['elements'] if e.get('type') not in FIXED_TYPES]
    last_slot = max((i for i, e in enumerate(original) if e['type'] not in FIXED_TYPES), default=-1)
    elements = []
    used = 0
    for index, element in enumerate(original):
        if element['type'] in FIXED_TYPES:
            elements.append(element)
        elif index == last_slot:
            elements.extend(editable[used:])
        elif used < len(editable):
            elements.append(editable[used])
            used += 1
    if last_slot < 0:
        elements.extend(editable)
    return drawing_source(document['candidate'], elements)


def drawing_source(candidate, elements):
    import pprint
    fmt = lambda v: pprint.pformat(v, width=110, sort_dicts=False)
    return '# Rubrics drawing program v1; coordinates are inches.\nposter(' + fmt(candidate) + ')\n\n' + '\n\n'.join('draw(' + fmt(e) + ')' for e in elements) + '\n'


def materialize(document, initial):
    """Derive content and all visible text from the executed program, not claims."""
    from src.workflow.editorial_contract import normalize_candidate, make_board, asset_index
    from src.layout.editorial import presentation_lines
    from src.layout.body_presentation import paragraphs
    from src.layout.element_identity import identified_layout
    state = dict(initial)
    state['errors'] = list(initial.get('errors', []))
    for key in ('editorial_visual_selection', 'editorial_composition', 'editorial_emphasis'):
        state.pop(key, None)
    from jsonschema import Draft202012Validator
    from src.workflow.editorial_pipeline import MODULE
    raw = document['candidate']
    if not isinstance(raw, dict) or set(raw) != {'version','modules','core_module_ids','narrative_flow','candidate_id'}:
        raise ValueError('Drawing candidate fields changed')
    if not isinstance(raw['modules'],list) or len(raw['modules'])>64:
        raise ValueError('Invalid drawing module count')
    for m in raw['modules']:
        Draft202012Validator(MODULE).validate(m)
    candidate = normalize_candidate(raw, state, state['layout_spec']['zones'])
    board = make_board(candidate)
    sections = {s['section_id']: s for s in board['spatial_content_plan']['sections']}
    modules = {m['module_id']: m for m in candidate['modules']}
    elements = deepcopy(document['elements'])
    types = {'title','section_title','title_accent_block','title_accent_line','conf_logo','aff_logo',
             'section_container','text','visual','qr_code'}
    assets = asset_index(initial)
    for e in elements:
        if e.get('type') not in types:
            raise ValueError('Unsupported drawing element')
        for k in ('x', 'y', 'width', 'height'):
            if type(e.get(k)) not in (int, float) or not math.isfinite(e[k]) or abs(e[k]) > 1000:
                raise ValueError('Invalid element geometry')
        if min(e['width'], e['height']) <= 0:
            raise ValueError('Nonpositive element size')
        if 'font_size' in e and (type(e['font_size']) not in (int,float) or not 4 <= e['font_size'] <= 300):
            raise ValueError('Invalid element font size')
        sid = e.get('section_id')
        if e['type'] in {'text','section_title','visual','section_container'} and sid not in sections:
            raise ValueError('Element has no module owner')
        if e['type'] == 'text':
            s = sections[sid]
            e.update(content='\n'.join(presentation_lines(s)), editorial_paragraphs=paragraphs(s), body_format=s['body_format'])
        if e['type'] == 'section_title':
            e['section_title'] = sections[sid]['section_title']
        if e['type'] == 'visual' and e.get('visual_id') not in assets:
            raise ValueError('Only original paper visuals may be drawn')
        if e['type'] == 'section_container':
            if e.get('zone_id') != modules[sid]['zone_id']:
                raise ValueError('Module region differs from drawing')
            from src.layout.editorial_frames import frame_box
            frame_box(e)
    for sid, m in modules.items():
        for kind in ('text', 'section_title', 'section_container'):
            if sum(e['type'] == kind and e.get('section_id') == sid for e in elements) != 1:
                raise ValueError('Each module needs exactly one body, title and frame')
        if [e.get('visual_id') for e in elements if e['type']=='visual' and e.get('section_id')==sid] != m['visual_ids']:
            raise ValueError('Drawn visuals differ from module ownership')
    if [e for e in elements if e['type'] in FIXED_TYPES] != [e for e in initial['styled_layout'] if e['type'] in FIXED_TYPES]:
        raise ValueError('Paper header, logos and QR are immutable')
    identities = identified_layout(elements)
    ids = [e['id'] for e in identities]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate drawing identities')
    state.update(editorial_candidate=candidate, optimized_story_board=board, story_board=deepcopy(board),
                 styled_layout=elements, design_layout=deepcopy(elements))
    spec = deepcopy(initial['layout_spec'])
    from src.layout.editorial_reading import reading_report
    from src.workflow.editorial_contract import validate_zones
    for z in spec['zones']:
        z['section_ids'] = [m['module_id'] for m in candidate['modules'] if m['zone_id']==z['zone_id']]
    spec['reading_route'] = reading_report(validate_zones(state, spec['zones']), spec['zones'], candidate['modules'])
    spec['reading_order'] = spec['reading_route']['spatial_module_order']
    state['layout_spec'] = spec
    # Frames remain allocated by the selected family's legal weights and gutters.
    from src.layout.editorial_frames import assert_frames
    assert_frames(state, candidate, spec, elements)
    return state


if __name__=='__main__':
    import json
    import resource
    import sys
    resource.setrlimit(resource.RLIMIT_CPU,(10,10))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    try:
        source=sys.stdin.read(MAX_SOURCE+1)
        output=json.dumps(execute(source),ensure_ascii=False,allow_nan=False)
        if len(output)>4000000:raise ValueError('Drawing output limit exceeded')
        sys.stdout.write(output)
    except Exception as exc:
        sys.stderr.write(type(exc).__name__+': '+str(exc));sys.exit(1)
