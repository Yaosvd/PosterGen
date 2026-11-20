"""Stage-independent candidate and semantic comparison contracts for batch mining."""
from jsonschema import Draft202012Validator, ValidationError

from src.rubrics.constraints import obj, TEXT

QUALITY_FIELDS = ('type', 'dimension', 'requirement', 'applicability', 'criterion')
RULE_CONTENT = obj({
    'type': {'enum': ['preference', 'rejection']}, 'dimension': TEXT, 'requirement': TEXT,
    'applicability': TEXT, 'criterion': TEXT,
    'evidence_refs': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': TEXT},
})
RULES = obj({'rules': {'type': 'array', 'minItems': 1, 'maxItems': 1, 'items': RULE_CONTENT}})
CANDIDATE = obj({
    'id': {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_-]{0,79}$'},
    'revision': {'type': 'integer', 'minimum': 1},
    **RULE_CONTENT['properties'],
})
DECISION_ORDER = ('conflict', 'uncertain', 'duplicate', 'partial_overlap', 'novel')
DECISION = obj({'decision': {'enum': list(DECISION_ORDER)}, 'reason': TEXT})
RECONCILIATION = obj({'comparisons': {'type': 'array', 'items': obj({
    'existing_id': TEXT, **DECISION['properties']})}})


class PartialComparison(ValueError):
    """A complete JSON reply contained only some individually valid, unambiguous decisions."""
    def __init__(self, comparisons):
        super().__init__('Incomplete semantic block; individually validated comparisons retained')
        self.comparisons = comparisons


def validate_keyed_comparison(value, schema):
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError:
        if isinstance(value, dict) and set(value) == {'comparisons'} and isinstance(value['comparisons'], dict):
            pairs = value['comparisons']
            expected = schema['properties']['comparisons']['required']
            if pairs.keys() <= set(expected):
                validator = Draft202012Validator(DECISION)
                valid = [{'existing_id': rid, **pairs[rid]} for rid in expected
                         if rid in pairs and validator.is_valid(pairs[rid])]
                if 0 < len(valid) < len(expected):
                    raise PartialComparison(valid)
        raise


def validate_candidate(rule):
    Draft202012Validator(CANDIDATE).validate(rule)
    if type(rule['revision']) is not int or any(not rule[k].strip() for k in QUALITY_FIELDS):
        raise ValueError('Invalid candidate revision or blank quality field')
    return rule


def quality_view(rule):
    return {field: rule[field] for field in ('id', *QUALITY_FIELDS)}


def aggregate_decision(decisions):
    states = set(decisions)
    return next((decision for decision in DECISION_ORDER if decision in states), 'novel')


def validate_semantic(candidate, existing, response):
    Draft202012Validator(RECONCILIATION).validate(response)
    expected = [rule['id'] for rule in existing]
    actual = [item['existing_id'] for item in response['comparisons']]
    if len(set(expected)) != len(expected) or len(actual) != len(expected) or set(actual) != set(expected):
        raise ValueError('Semantic review must cover every supplied rule exactly once')
    return {'existing_ids': expected, 'comparisons': response['comparisons'],
            'decision': aggregate_decision(item['decision'] for item in response['comparisons'])}
