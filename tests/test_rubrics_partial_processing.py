"""Exercise isolated failures through the normal batch, HTTP, review and publication entry points."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from rubrics_poster.iteration import main
from src.rubrics import candidates, mining, providers, quality
from src.rubrics.storage import IntegrityError, read, write
from test_rubrics_candidate_review import decision_file
from test_rubrics_framework import rule, sealed
from utils.persistence import digest


def test_partial_package_retains_evidence_and_valid_decisions_across_resume(tmp_path, monkeypatch, capsys):
    seal = sealed(tmp_path)
    samples = [dict(s, round_id=seal['round_id']) for s in seal['samples'][:8]]
    seal_file = tmp_path/'subset.json'
    write(seal_file, dict(seal, schema_version=3, kind='scored_collection', samples=samples,
        sources={seal['round_id']: seal['manifest_digest']}, sample_count=8, paper_hashes=['0']))
    config = providers.configuration()
    for settings in config['external_models'].values():
        settings.update(base_url='http://fixture.invalid/v1', api_key_env=None)
    config['mining']['reconcile_batch_size'] = 2
    calls = Counter()

    def post(self, endpoint, body):
        schema = body['response_format']['json_schema']['schema']
        role = next(iter(schema['properties']))
        calls[role] += 1
        n = calls[role]
        message = body['messages'][0]['content']
        if role == 'observations':
            if n == 1:
                req = httpx.Request('POST', 'http://fixture.invalid')
                raise httpx.HTTPStatusError('service failure', request=req, response=httpx.Response(502, request=req))
            value = {'observations': [] if n == 2 else [{'dimension': 'layout', 'observation': f'Finding {n}',
                     'evidence': 'Visible gap', 'generalizable_lesson': f'Spacing in region {n}'}]}
            if n == 3:
                value = {'observations': [{'dimension': 'incomplete'}]}
        elif role == 'rules':
            payload = json.loads(message.split('\nINPUT:\n')[1].rsplit('\nOUTPUT SCHEMA:\n', 1)[0])
            ref = payload['observations'][0]['id']
            value = {'rules': [{'type': payload['type'], 'dimension': 'layout', 'requirement': f'Spacing {n}',
                     'applicability': 'Panels', 'criterion': 'Gap visible',
                     'evidence_refs': ['unknown'] if n == 1 else [ref]}]}
        else:
            ids = schema['properties']['comparisons']['required']
            if n == 3:
                raise httpx.ReadTimeout('No reply')
            if n == 2:
                assert len(ids) == 2
                ids = ids[:1]
            value = {'comparisons': {rid: {'decision': 'novel', 'reason': 'Distinct criterion'} for rid in ids}}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]}

    monkeypatch.setattr(providers.OpenAICompatible, '_post', post)
    library = tmp_path/'library'
    with monkeypatch.context() as m:
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt()
        m.setattr(candidates, 'prepare', interrupt)
        with pytest.raises(KeyboardInterrupt):
            mining.process(seal_file, library, config=config)
    expected_calls = calls.copy()
    assert expected_calls == {'observations': 8, 'rules': 5, 'comparisons': 6}
    result = mining.process(seal_file, library, config=config)
    assert result == mining.process(seal_file, library, config=config) and calls == expected_calls
    assert result['status'] == 'PARTIAL_REVIEW' and result['candidate_count'] == 4
    root = Path(result['review_package'])
    pack = candidates.load(root)
    progress = pack['completion']
    extraction = progress['extraction']
    assert (extraction['planned'], extraction['completed']) == (8, 6)
    assert [f['poster_id'] for f in extraction['failures']] == ['p0_0', 'p0_2']
    first, third = (f['error'] for f in extraction['failures'])
    assert first == {'error_type': 'HTTPStatusError', 'message': 'HTTP 502 Bad Gateway',
                     'send_recorded': True, 'response_saved': False}
    assert third['response_saved'] and third['error_type'] == 'ValidationError'
    assert len(pack['observations']) == 5
    assert progress['summary']['completed'] == 4 and progress['summary']['planned'] == 5
    assert len(progress['summary']['failures'][0]['observation_ids']) == 1
    assert progress['comparison'] == {'planned': 10, 'completed': 7}
    assert result['recommendation_counts'] == {'novel': 2}
    assert [a['decision'] for a in pack['assessments']] == ['novel','incomplete','incomplete','novel']
    assert len(result['pending'][0]['missing_ids']) == 1 and len(result['pending'][1]['missing_ids']) == 2
    assert all(len(a['reviews']) == 1 for a in pack['assessments'][1:3])
    for a, pending in zip(pack['assessments'][1:3], result['pending']):
        assert pending['missing_ids'] == a['failed_chunks'][0]['existing_ids']
    assert main(['review-candidates', str(root)]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'PARTIAL_REVIEW'
    doc = (root/'review.md').read_text()
    assert '海报抽取完成 6 / 8，未完成 2 项' in doc and '已比较 1 / 2 项' in doc and '已比较 1 / 3 项' in doc
    assert 'HTTP 502' in doc and 'p0_0' in doc

    # Repack with a valid checksum: dropping a gap or falsely marking it novel must still be rejected.
    for edit in ('missing_id', 'decision', 'counts'):
        changed = deepcopy(pack)
        if edit == 'missing_id':
            changed['assessments'][1]['failed_chunks'][0]['existing_ids'] = []
        elif edit == 'decision':
            changed['assessments'][1]['decision'] = 'novel'
        else:
            changed['completion']['extraction']['completed'] = 8
        bad = root.parent/digest(changed)
        write(bad/'package.json', changed)
        with pytest.raises(IntegrityError):
            candidates.load(bad)
    chosen = pack['assessments'][1]['candidate_id']
    assert chosen in pack['eligible_ids']
    decision = decision_file(root, ids=[chosen])
    published = candidates.publish(root, decision)
    assert published['approved_ids'] == [chosen] and candidates.publish(root, decision) == published


def test_all_failed_extractions_deliver_failure_package_without_false_convergence(tmp_path, monkeypatch):
    seal = sealed(tmp_path)
    config = providers.configuration()
    for settings in config['external_models'].values():
        settings.update(base_url='http://fixture.invalid/v1', api_key_env=None)
    def fail(self, endpoint, body):
        assert 'observations' in body['response_format']['json_schema']['schema']['properties']
        raise httpx.ConnectError('Offline')
    monkeypatch.setattr(providers.OpenAICompatible, '_post', fail)
    sample = dict(seal['samples'][0], round_id=seal['round_id'])
    path = tmp_path/'collection.json'
    write(path, dict(seal, schema_version=3, kind='scored_collection', samples=[sample], sample_count=1,
                     sources={seal['round_id']: seal['manifest_digest']}, paper_hashes=[sample['paper_sha256']]))
    result = mining.process(path, tmp_path/'library', config=config)
    assert result['status'] == 'PARTIAL_REVIEW'
    package = candidates.load(result['review_package'])
    assert package['completion']['extraction']['completed'] == 0
    assert package['completion']['summary']['planned'] == package['completion']['comparison']['planned'] == 0
    assert package['eligible_ids'] == []


@pytest.mark.parametrize('fault,retained', [('missing', 1), ('bad_verdict', 1), ('foreign_id', 0),
                                            ('duplicate_key', 0), ('truncated', 0)])
def test_semantic_recovery_only_counts_unambiguous_valid_items(tmp_path, monkeypatch, fault, retained):
    config = providers.configuration()
    config['external_models']['reconciler'].update(base_url='http://fixture.invalid', api_key_env=None)
    good = {'decision': 'duplicate', 'reason': 'Matches the criterion.'}
    pairs = {'first': good}
    if fault == 'bad_verdict':
        pairs['second'] = dict(good, decision='invented_label')
    if fault == 'foreign_id':
        pairs['foreign'] = good
    content = json.dumps({'comparisons': pairs})
    if fault == 'duplicate_key':
        content = '{"comparisons":{"first":' + json.dumps(good) + ',"first":' + json.dumps(good) + '}}'
    def post(self, endpoint, data):
        return {'choices': [{'finish_reason': 'length' if fault == 'truncated' else 'stop',
                             'message': {'content': content}}]}
    monkeypatch.setattr(providers.OpenAICompatible, '_post', post)
    reviewed = mining.reconcile(rule('new'), [rule('first'), rule('second')], providers.ExternalModels(config),
                                tmp_path, config['mining'])
    assert reviewed['decision'] == 'incomplete'
    assert [r['decision'] for r in reviewed['reviews']] == ['duplicate'] * retained
    assert reviewed['failed_chunks'][0]['existing_ids'] == (['second'] if retained else ['first', 'second'])
    assert read(tmp_path/'0/response.json')['raw']['choices'][0]['message']['content'] == content


def test_uncertain_send_survives_interruption_and_corrupt_failure_receipt_stops_processing(tmp_path, monkeypatch):
    config = providers.configuration()
    config['external_models']['reconciler'].update(base_url='http://fixture.invalid', api_key_env=None)
    models = providers.ExternalModels(config)
    subject, references = rule('new'), [rule('first')]
    def interrupted(self, endpoint, body):
        raise KeyboardInterrupt()
    monkeypatch.setattr(providers.OpenAICompatible, '_post', interrupted)
    with pytest.raises(KeyboardInterrupt):
        models.generate('reconciler', mining.review_payload(subject, references), quality.RECONCILIATION, tmp_path/'0')
    monkeypatch.setattr(providers.OpenAICompatible, '_post', lambda *a: pytest.fail('Uncertain send was repeated'))
    result = mining.reconcile(subject, references, models, tmp_path, config['mining'])
    error = result['failed_chunks'][0]['error']
    assert error['error_type'] == 'RequestUncertain' and error['previous_error_type'] == 'KeyboardInterrupt'
    assert error['send_recorded'] and not error['response_saved']
    assert result == mining.reconcile(subject, references, models, tmp_path, config['mining'])
    with pytest.raises(IntegrityError, match='inputs changed'):
        mining.reconcile(subject, [rule('different')], models, tmp_path, config['mining'])
    (tmp_path/'0/item_error.json').write_text('corrupt')
    with pytest.raises(IntegrityError):
        mining.reconcile(subject, references, models, tmp_path, config['mining'])
