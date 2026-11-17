"""Quality-only rule schema, lawful stage responses and read-only old reviews."""
from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from src.critic.scoring import current_policy
from src.rubrics import candidates, constraints, mining
from src.rubrics.library import LibraryStore
from src.rubrics.storage import IntegrityError, read, write
from utils.persistence import digest


def quality_rule(name='new'):
    return {'id': name, 'revision': 1, 'dimension': 'contribution evidence',
            'type': 'preference', 'requirement': 'Support the contribution with source-grounded evidence.',
            'applicability': 'Posters presenting a research contribution.',
            'criterion': 'Readers can identify the evidence supporting the contribution.',
            'applicable_stages': ['writing', 'review', 'revision'], 'evidence_refs': ['observation1']}


def review(rule, existing=()):
    return {'comparisons': [{'existing_id': r['id'], 'decision': 'novel', 'reason': 'Distinct quality goal.'}
                            for r in existing],
            'engineering_review': {'status': 'compliant', 'findings': [],
                'stage_actions': [{'stage': stage, 'actions': ['inspect', 'record_unresolved'],
                    'reason': 'Inspect evidence and record a missing planning input when no lawful repair is available.'}
                    for stage in rule['applicable_stages']]}}


def test_summarizer_schema_contains_only_quality_fields_and_rejects_old_guidance():
    rule = quality_rule()
    content = {k: v for k, v in rule.items() if k not in {'id', 'revision'}}
    Draft202012Validator(mining.RULES).validate({'rules': [content]})
    with pytest.raises(ValidationError):
        Draft202012Validator(mining.RULES).validate({'rules': [{**content, 'revision_guidance': 'Writer must edit.'}]})
    assert 'revision_guidance' not in mining.RULE_CONTENT['required']
    assert rule['requirement'] in mining._text(rule)
    assert mining._rule_identity(rule)


def test_same_quality_goal_can_have_read_only_or_partial_stage_response():
    rule = quality_rule()
    response = review(rule)
    response['engineering_review']['stage_actions'][0]['actions'] = ['edit_body', 'record_unresolved']
    response['engineering_review']['stage_actions'][2]['actions'] = ['plan_modules', 'allocate_frames', 'edit_body']
    result = mining.validate_comparison(rule, [], response, constraints.snapshot())
    assert result['decision'] == 'novel'
    assert result['engineering']['local_violations'] == []
    assert response['engineering_review']['stage_actions'][1]['actions'] == ['inspect', 'record_unresolved']


@pytest.mark.parametrize('stage,action', [('writing', 'allocate_frames'), ('review', 'edit_body'),
                                         ('revision', 'change_family'), ('revision', 'invent_evidence')])
def test_missing_guidance_does_not_relax_forbidden_stage_actions(stage, action):
    rule = quality_rule()
    response = review(rule)
    next(e for e in response['engineering_review']['stage_actions'] if e['stage'] == stage)['actions'] = [action]
    result = mining.validate_comparison(rule, [], response, constraints.snapshot())
    assert result['decision'] == 'conflict'
    assert result['engineering']['local_violations'] == [{'stage': stage, 'forbidden_actions': [action]}]


def test_explicit_forbidden_requirement_cannot_pass_with_inspection_only():
    rule = quality_rule()
    rule['requirement'] = 'Every poster must change its sampled family to a three-column family.'
    response = review(rule)
    response['engineering_review']['findings'] = [{'constraint_id': 'family',
        'rule_quote': rule['requirement'], 'reason': 'The required family change violates fixed family constraints.'}]
    # Even a model's inconsistent compliant label cannot erase its grounded finding.
    result = mining.validate_comparison(rule, [], response, constraints.snapshot())
    assert result['decision'] == 'conflict'


def legacy_parent(library_root):
    old_rule = {**quality_rule('seed'), 'revision_guidance': 'Writer should explain selected evidence.'}
    parent = {'schema_version': 1, 'parent_version': None, 'status': 'published',
              'rules': [old_rule], 'source_batch_digest': 'legacy seed'}
    parent['version'] = digest(parent)
    write(library_root/'versions'/parent['version']/'library.json', parent)
    write(library_root/'active.json', {'version': parent['version'], 'name': 'seed rubrics'})
    return parent


@pytest.mark.parametrize('conflicting', [False, True])
def test_historical_guidance_reviews_remain_readable_but_cannot_publish(tmp_path, conflicting):
    library_root = tmp_path/'library'
    parent = legacy_parent(library_root)
    rule = {**quality_rule(), 'revision_guidance': 'Writer must change the sampled family.'}
    contract = deepcopy(constraints.snapshot())
    contract['version'] = 'rubrics_engineering_contract_v1'
    response = review(rule, parent['rules'])
    if conflicting:
        response['engineering_review']['status'] = 'conflict'
        response['engineering_review']['findings'] = [{'constraint_id': 'family',
            'rule_quote': rule['revision_guidance'], 'reason': 'Legacy guidance mandates a forbidden edit.'}]
    checked = mining.validate_comparison(rule, parent['rules'], response, contract)
    package = {'schema_version': 1, 'status': 'awaiting_human_review', 'parent_version': parent['version'],
        'source_batch_digest': 'legacy batch', 'engineering_contract': contract,
        'job_identity': {'seal': 'legacy batch', 'publication_policy': 'human_review_v1', 'engineering_contract': contract},
        'job_path': str(tmp_path/'old-job'), 'max_rules': 10, 'candidates': [rule],
        'assessments': [{'candidate_id': rule['id'], 'rule_digest': digest(rule),
                        'decision': checked['decision'], 'reviews': [checked]}],
        'observations': [{'id': 'observation1', 'type': 'preference', 'observation': 'Visible evidence.',
                          'evidence': 'Source and poster agree.'}], 'sources': [],
        'eligible_ids': [] if conflicting else [rule['id']]}
    root = library_root/'candidates'/digest(package)
    write(root/'package.json', package)
    assert candidates.load(root) == package
    assert rule['revision_guidance'] in candidates.render(root, package)
    decision = {'schema_version': 1, 'review_id': root.name, 'parent_version': parent['version'],
                'decision': 'approve', 'approved_ids': [rule['id']], 'reviewer': 'fixture human', 'comment': ''}
    path = root/'decision.json'
    path.write_text(json.dumps(decision))
    with pytest.raises(IntegrityError, match='Engineering contract changed'):
        candidates.publish(root, path)
    assert LibraryStore(library_root).active() == parent
    assert not (root/'human_decision.json').exists()


def test_legacy_round_is_refused_before_any_model_check_or_send(tmp_path, monkeypatch):
    parent = legacy_parent(tmp_path/'library')
    policy = current_policy()
    path = tmp_path/'seal.json'
    write(path, {'library_version': parent['version'], 'scoring_policy': policy})
    monkeypatch.setattr(mining, 'verified_samples', lambda seal: iter(()))
    class NoModels:
        def check(self, *args, **kwargs):
            pytest.fail('Legacy round must not start model checks or calls')
        generate = check
    with pytest.raises(IntegrityError, match='Legacy sealed rounds'):
        mining.process(path, tmp_path/'library', models=NoModels())
    assert not (tmp_path/'postprocess').exists()
    assert read(tmp_path/'library/active.json')['version'] == parent['version']
