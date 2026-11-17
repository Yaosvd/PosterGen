"""Versioned mining context and checks for declared stage permissions.

The model interprets prose; local checks enforce declared actions and coverage.
Neither is proof of arbitrary prose safety. Publication always requires a human.
"""
from copy import deepcopy
from pathlib import Path
import json

from src.rubrics.library import STAGES
from utils.persistence import file_hash

VERSION = 'rubrics_engineering_contract_v2'
COMMON = {'inspect', 'record_unresolved'}
STAGE_ACTIONS = {
    'parser': COMMON | {'extract_paper'},
    'planning': COMMON | {'plan_modules', 'assign_visuals', 'allocate_frames'},
    'writing': COMMON | {'edit_body', 'edit_module_title'},
    'capacity': COMMON | {'edit_body'},
    'palette': COMMON | {'select_palette'},
    'review': COMMON,
    'revision': COMMON | {'plan_modules', 'assign_visuals', 'allocate_frames',
                          'edit_body', 'edit_module_title', 'style_elements', 'change_font_size'},
}
OPERATIONS = {
    'inspect': 'Check content/rendering without changing it.',
    'record_unresolved': 'Report a defect or hand it to an authorized stage; do not perform its edit here.',
    'extract_paper': 'Extract/correct source-grounded paper material within parser schemas.',
    'plan_modules': 'Plan/replan modules and their content only inside the already selected family and legal regions.',
    'assign_visuals': 'Select/reassign existing source assets to modules; never modify asset bytes.',
    'allocate_frames': 'Recompute lawful module frames inside existing family regions, weights 1..2 and existing gutters; not arbitrary resizing.',
    'edit_body': 'Write/compress/expand complete source-grounded body items and their supported formatting inside the frozen module.',
    'edit_module_title': 'Edit a module heading within the title/output contract; never the paper title.',
    'select_palette': 'Choose permitted poster palette fields, never recolor source figures.',
    'style_elements': 'Actor-only lawful drawing styles/positions inside the allocated frames.',
    'change_font_size': 'Actor drawing styles only, subject to current 4..300 validation and legibility; no such permission in Writer/capacity/planning.',
    'change_family': 'Replace a sampled family, its topology/regions, or force a hero/column structure the current family does not support (forbidden).',
    'resize_arbitrarily': 'Enlarge/move a frozen module or region without legal family allocation (forbidden).',
    'edit_assets': 'Crop/redraw/recolor/fabricate source image bytes or data (forbidden).',
    'edit_header': 'Change paper title/authors/logos/QR/canvas (forbidden).',
    'edit_pipeline': 'Change shared source, evaluator, schemas, model budgets, or add repair rounds (forbidden).',
    'invent_evidence': 'Invent facts, numeric values, citations, measurements, or claim unseen rendering succeeded (forbidden).',
}
CONSTRAINTS = {
    'family': 'The sampled family and legal region topology remain fixed. A good hero/column example is not a general mandate. Restrict applicability explicitly to an existing compatible family/structure; module count alone is insufficient. Do not silently narrow a candidate while reviewing it.',
    'stages': 'Check every applicable stage separately. Writer edits module title/body only; capacity edits existing body only, not title, visual assignment, frames, positions or fonts. Parser/palette/review do not gain editing permissions from Rubrics. Planning/Actor may replan only within their permissions. Quality requirements do not grant editing authority or require every listed stage to perform the same edits. List a lawful response for each stage, including inspection or recording an unresolved defect when it cannot make a repair. Such limits alone are not a conflict in the quality rule. Explicit unauthorized commands and requirements that necessarily violate hard constraints remain conflicts.',
    'geometry': 'Legal frame allocation follows the selected family regions, space_weight 1..2 and existing gutters. Actual overflow/whitespace remains reportable. Do not fix overflow by enlarging frozen frames, hiding required science, or unreadable text. Do not confuse planned-box estimates with measured rendered bounds.',
    'assets_science': 'Preserve original asset bytes, facts, uncertainty, units, comparison conditions and qualification. Distinguish a number in body prose from a number inside a table image. Scores/explanations can be wrong; resolve against the actual image and original paper, or report uncertainty.',
    'header': 'Paper title, authors, logos, QR and canvas stay unchanged.',
    'execution': 'Keep output schemas, shared pipeline, independent evaluator G and call budgets unchanged. Actor has one bounded script execution/revision; no new tools, arbitrary code, rounds or self-publication.',
    'typography': 'Writer/capacity/planning use fixed supplied typography. Actor currently may restyle legal elements (font validation 4..300); this is not permission to modify immutable header elements or conceal unreadability. Do not incorrectly impose an all-stage font freeze that the Actor interface does not implement.',
}


def snapshot():
    root = Path(__file__).resolve().parents[2]
    sources = ('src/rubrics/constraints.py', 'src/rubrics/program.py',
               'src/layout/editorial_frames.py', 'src/layout/families.py',
               'src/workflow/editorial_pipeline.py', 'src/workflow/editorial_contract.py',
               'config/prompts/rubrics_revision.txt')
    return {'version': VERSION, 'constraints': deepcopy(CONSTRAINTS),
            'allowed_actions': {s: sorted(a) for s, a in STAGE_ACTIONS.items()},
            'operations': deepcopy(OPERATIONS),
            'sources': {p: file_hash(root/p) for p in sources},
            'publication': 'All model outputs are advisory candidates. Only an explicit human decision can publish.'}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


TEXT = {'type': 'string', 'minLength': 1}
ENGINEERING_REVIEW = obj({
    'status': {'enum': ['compliant', 'conflict', 'uncertain']},
    'stage_actions': {'type': 'array', 'items': obj({
        'stage': {'enum': sorted(STAGES)},
        'actions': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'enum': sorted(OPERATIONS)}},
        'reason': TEXT})},
    'findings': {'type': 'array', 'items': obj({
        'constraint_id': {'enum': sorted(CONSTRAINTS)}, 'rule_quote': TEXT, 'reason': TEXT})},
})

REVIEW_INSTRUCTIONS = (
    'Review the complete requirement, applicability and criterion. '
    'Return one comparison for EVERY supplied existing rule ID, including opposite types and '
    'rules covered only partly by a compound candidate. Check the engineering_contract independently '
    'even when no existing rule is supplied. List lawful responses for EVERY candidate applicable stage; '
    'use inspect or record_unresolved when that stage cannot repair the defect. '
    'A quality requirement is not conflicting merely because one stage cannot implement every improvement. '
    'Explicit operational commands remain subject to stage permissions; do not reinterpret a forbidden mandate as inspection. '
    'Do not infer a hidden restriction to current-family geometry: '
    'when the rule mandates an action, evaluate it for all its stated cases. '
    'Consider a concrete permitted poster/task where the mandatory action would be forbidden. '
    'An implicit exception invented by the reviewer cannot make a rule compatible. '
    'Findings quote exact candidate text. If action classification or compatibility is uncertain, '
    'return uncertain. Preserve the candidate verbatim; never infer permission to publish.'
)


def check_engineering(rule, review, contract):
    from jsonschema import Draft202012Validator
    Draft202012Validator(ENGINEERING_REVIEW).validate(review)
    stages = [entry['stage'] for entry in review['stage_actions']]
    if len(stages) != len(set(stages)) or set(stages) != set(rule['applicable_stages']):
        raise ValueError('Engineering review must cover every applicable stage exactly once')
    fields = ('requirement', 'applicability', 'criterion')
    # Historical review packages retain their original contract and full rule text.
    if contract.get('version') == 'rubrics_engineering_contract_v1':
        fields += ('revision_guidance',)
    text = '\n'.join(rule[k] for k in fields)
    serialized = json.dumps(rule, ensure_ascii=False)
    for finding in review['findings']:
        if finding['rule_quote'] not in text and finding['rule_quote'] not in serialized:
            raise ValueError('Engineering finding quote is not in the candidate')
    violations = []
    for entry in review['stage_actions']:
        forbidden = sorted(set(entry['actions']) - set(contract['allowed_actions'][entry['stage']]))
        if forbidden:
            violations.append({'stage': entry['stage'], 'forbidden_actions': forbidden})
    status = review['status']
    if violations or (review['findings'] and status == 'compliant'):
        status = 'conflict'
    return {'status': status, 'declared': deepcopy(review), 'local_violations': violations}
