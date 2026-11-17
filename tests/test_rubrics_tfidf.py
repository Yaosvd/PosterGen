"""Offline lexical mining, exhaustive semantic review, and durable recovery contracts."""
from copy import deepcopy
from pathlib import Path
import json

import numpy as np
import pytest
from jsonschema.exceptions import ValidationError

from src.rubrics import mining, vectorization
from src.rubrics.library import LibraryStore
from src.rubrics.providers import configuration, ExternalModels, validate_configuration
from src.rubrics.storage import BudgetExceeded, IntegrityError, WaitingForConfiguration, read, write, request_once
from test_rubrics_framework import Models, rule, sealed, semantic_response


def test_configuration_has_only_three_generation_roles_and_requires_reconciler():
    config = configuration()
    assert set(config['external_models']) == {'extractor', 'summarizer', 'reconciler'}
    config['external_models']['reconciler'].update(provider=None, model=None, base_url=None)
    for role in ('extractor', 'summarizer'):
        config['external_models'][role].update(provider='openai_compatible', model='fixture',
                                             base_url='https://fixture.invalid/v1', api_key_env=None)
    with pytest.raises(WaitingForConfiguration, match='reconciler'):
        ExternalModels(config).check()
    config['external_models']['reconciler'].update(provider='openai_compatible', model='fixture',
                                                 base_url='https://fixture.invalid/v1', api_key_env=None)
    ExternalModels(config).check()  # Read-only preflight, no HTTP.
    assert not hasattr(ExternalModels(config), 'embed')


@pytest.mark.parametrize('change', ['legacy', 'threshold', 'batch', 'seed', 'features', 'ngrams'])
def test_incompatible_or_unbounded_configuration_is_rejected(change):
    config = configuration()
    if change == 'legacy':
        config['schema_version'] = 1
    elif change == 'threshold':
        config['mining']['similarity_threshold'] = 0.9
    elif change == 'batch':
        config['mining']['embedding_batch_size'] = 64
    elif change == 'seed':
        config['mining']['random_seed'] = True
    elif change == 'features':
        config['mining']['tfidf']['max_features'] = 10000000
    else:
        config['mining']['tfidf']['ngram_range'] = [4, 2]
    with pytest.raises(ValueError):
        validate_configuration(config)


def test_shared_multilingual_features_and_sparse_receipt_are_reproducible(tmp_path):
    texts = ['模块正文不得溢出边界', '模块标题不得溢出边界', 'Keep body text within the module',
             'Keep module titles within the module', '模块正文不得溢出边界']
    settings = configuration()['mining']['tfidf']
    ids = [str(i) for i in range(len(texts))]
    path = tmp_path/'features.json'
    x = vectorization.fit_texts(texts, ids, settings, path)
    assert hasattr(x, 'indptr') and x.shape[0] == 5 and x.shape[1] <= 16000
    assert np.allclose(x.multiply(x).sum(axis=1), 1)
    saved = read(path)
    assert '模块' in saved['vocabulary'] and 'keep' in saved['vocabulary']
    assert len(saved['idf']) == x.shape[1] and len(saved['matrix']['data']) == x.nnz
    assert (x[0] != x[4]).nnz == 0
    repeated = vectorization.fit_texts(texts, ids, settings, path)
    assert (x != repeated).nnz == 0
    groups = vectorization.clusters(x, 8, 17)
    assert groups == vectorization.clusters(repeated, 8, 17)
    assert len(groups) <= 4 and sorted(i for group in groups for i in group) == list(range(5))
    assert any(0 in group and 4 in group for group in groups)
    saved['idf'][0] += 1
    write(path, saved)
    with pytest.raises(IntegrityError, match='Immutable'):
        vectorization.fit_texts(texts, ids, settings, path)


def test_empty_group_singleton_and_zero_features_are_explicit(tmp_path):
    settings = configuration()['mining']['tfidf']
    assert vectorization.fit_texts([], [], settings, tmp_path/'empty.json') is None
    assert read(tmp_path/'empty.json')['matrix'] is None
    x = vectorization.fit_texts(['模块'], ['one'], settings, tmp_path/'one.json')
    assert vectorization.clusters(x, 8, 17) == [[0]]
    with pytest.raises(ValueError, match='textual evidence'):
        vectorization.fit_texts(['!!!'], ['bad'], settings, tmp_path/'bad.json')
    with pytest.raises(ValueError, match='cannot represent'):
        vectorization.fit_texts(['字'], ['short'], settings, tmp_path/'short.json')
    limited = {**settings, 'max_features': 1}
    with pytest.raises(ValueError, match='zero-feature'):
        vectorization.fit_texts(['aaaaaa', '中文内容'], ['en', 'zh'], limited, tmp_path/'limited.json')
    assert not (tmp_path/'limited.json').exists()


def test_round_maximum_observation_count_stays_sparse_and_feature_bounded(tmp_path):
    # 400 posters × 30 observations: no dense n_documents × vocabulary allocation.
    texts = ['模块边界 body frame ' + str(i % 25) for i in range(12000)]
    x = vectorization.fit_texts(texts, [str(i) for i in range(12000)],
        {**configuration()['mining']['tfidf'], 'max_features': 64}, tmp_path/'large.json')
    assert x.shape == (12000, 64) and hasattr(x, 'indptr')
    groups = vectorization.clusters(x, 8, 17)
    assert len(groups) <= 8 and sum(map(len, groups)) == 12000


class Reviewer:
    def __init__(self, answers):
        self.answers, self.batches = iter(answers), []
    def check(self, roles):
        assert roles == ('reconciler',)
    def generate(self, role, payload, schema, root):
        self.batches.append(payload['existing'])
        return semantic_response(payload, next(self.answers))


@pytest.mark.parametrize('answers,expected', [
    (['novel', 'novel', 'novel'], 'novel'),
    (['duplicate', 'novel', 'conflict'], 'conflict'),
    (['novel', 'uncertain', 'duplicate'], 'uncertain'),
    (['novel', 'duplicate', 'novel'], 'duplicate'),
])
def test_semantic_review_covers_all_chunks_and_conflicts_override_duplicates(tmp_path, answers, expected):
    existing = [rule(str(i), 'Requirement '+str(i)) for i in range(45)]
    existing[-1]['type'] = 'rejection'
    model = Reviewer(answers)
    value = mining.reconcile(rule('candidate'), existing, model, tmp_path, configuration()['mining'])
    assert value['decision'] == expected
    assert [len(b) for b in model.batches] == [20, 20, 5]
    assert [r['id'] for b in model.batches for r in b] == [str(i) for i in range(45)]
    assert model.batches[-1][-1]['type'] == 'rejection'


def test_reconciliation_splits_by_characters_without_truncating_rules(tmp_path):
    candidate = rule('candidate')
    existing = [rule(str(i)) for i in range(3)]
    limit = len(json.dumps(mining.review_payload(candidate,existing[:1],mining.snapshot()),ensure_ascii=False))
    settings = {**configuration()['mining'], 'reconcile_max_chars': limit}
    model = Reviewer(['novel']*3)
    assert mining.reconcile(candidate, existing, model, tmp_path, settings)['decision'] == 'novel'
    assert [r for b in model.batches for r in b] == existing and len(model.batches) == 3
    with pytest.raises(ValueError, match='refusing to truncate'):
        mining.reconcile(candidate, existing, model, tmp_path, {**settings, 'reconcile_max_chars': limit-1})


def test_exact_dedup_respects_criteria_and_stage_scope():
    base = rule()
    for change in ({'criterion': 'New criterion'}, {'applicable_stages': ['planning']},
                   {'type': 'rejection'}, {'applicability': 'Different context'},
                   {'requirement': base['requirement'].swapcase()}):
        assert mining._rule_identity(base) != mining._rule_identity({**base, **change})
    assert mining._rule_identity(base) == mining._rule_identity({**base, 'id': 'other',
        'evidence_refs': ['different evidence'], 'applicable_stages': ['capacity', 'writing']})


def test_lexical_similarity_never_bypasses_semantics_and_local_work_is_not_charged(tmp_path):
    sealed(tmp_path)
    class Model(Models):
        def __init__(self):
            super().__init__(); self.comparisons = []
        def generate(self, role, payload, schema, root, **kwargs):
            if role == 'reconciler':
                self.comparisons.append(deepcopy(payload))
            return super().generate(role, payload, schema, root, **kwargs)
    model = Model()
    result = mining.process(tmp_path/'seal.json', tmp_path/'library', models=model)
    assert result['added'] == 0 and result['candidate_count'] == 2
    job = Path(result['job'])
    retrievals = [read(p) for p in sorted((job/'retrieval').glob('*.json'))]
    assert any(r['cosine'] < 0.9 for d in retrievals for r in d['ranking'])
    assert len(model.comparisons) == 2
    assert all('seed' in {r['id'] for r in p['existing']} for p in model.comparisons)
    # The second candidate is also checked against the first accepted candidate.
    assert len(model.comparisons[1]['existing']) == 2
    ledger = read(job/'budget.json')['requests']
    assert len(ledger) == 404 and not any('embed' in r or 'tfidf' in r for r in ledger)
    assert read(job/'identity.json')['local_processing'] == vectorization.runtime_identity()
    assert not (job/'embedding').exists()


def test_duplicate_decisions_produce_no_new_rules(tmp_path):
    sealed(tmp_path)
    class Duplicates(Models):
        def generate(self, role, payload, *args, **kwargs):
            if role == 'reconciler':
                return semantic_response(payload, 'duplicate')
            return super().generate(role, payload, *args, **kwargs)
    result = mining.process(tmp_path/'seal.json', tmp_path/'library', models=Duplicates())
    assert result['status'] == 'NO_NEW_RULES' and result['added'] == 0
    assert len(read(Path(result['job'])/'review.json')['duplicates']) == 2


def test_pending_conflict_blocks_all_publication(tmp_path):
    sealed(tmp_path)
    class Conflict(Models):
        def generate(self, role, payload, *args, **kwargs):
            if role == 'reconciler' and payload['candidate']['type'] == 'rejection':
                return semantic_response(payload, 'conflict')
            return super().generate(role, payload, *args, **kwargs)
    result = mining.process(tmp_path/'seal.json', tmp_path/'library', models=Conflict())
    assert result['status'] == 'AWAITING_HUMAN_REVIEW' and len(result['accepted']) == 1
    assert len(LibraryStore(tmp_path/'library').active()['rules']) == 1
    assert (Path(result['job'])/'result.json').exists()


@pytest.mark.parametrize('count', [0, 2])
def test_one_cluster_requires_exactly_one_rule(tmp_path, count):
    sealed(tmp_path)
    class BadSummary(Models):
        def generate(self, role, *args, **kwargs):
            response = super().generate(role, *args, **kwargs)
            if role == 'summarizer':
                response['rules'] *= count
            return response
    with pytest.raises(ValidationError):
        mining.process(tmp_path/'seal.json', tmp_path/'library', models=BadSummary())
    assert len(LibraryStore(tmp_path/'library').active()['rules']) == 1


def test_empty_observations_are_not_sent_to_clustering_or_summarization(tmp_path):
    sealed(tmp_path)
    class Empty(Models):
        def generate(self, role, *args, **kwargs):
            assert role == 'extractor'
            self.calls.append(role)
            return {'observations': []}
    model = Empty()
    result = mining.process(tmp_path/'seal.json', tmp_path/'library', models=model)
    assert result['status'] == 'NO_NEW_RULES' and len(model.calls) == 400
    assert read(Path(result['job'])/'tfidf/preference.json')['matrix'] is None


def test_exact_cap_without_deferred_rules_is_reported_and_full_parent_needs_no_calls(tmp_path):
    sealed(tmp_path)
    config = configuration(); config['mining']['max_rules'] = 3
    result = mining.process(tmp_path/'seal.json', tmp_path/'library', config=config, models=Models())
    assert result['status'] == 'AWAITING_HUMAN_REVIEW' and result['added'] == 0
    assert result['candidate_count'] == result['remaining_capacity'] == 2
    # A separate frozen job already at its configured cap does not mine useless candidates.
    config['mining']['max_rules'] = 1
    model = Models()
    result = mining.process(tmp_path/'seal.json', tmp_path/'library', config=config, models=model)
    assert result['status'] == 'RULE_CAP' and result['added'] == 0 and not model.calls


def test_budget_exhaustion_does_not_publish_or_report_convergence(tmp_path):
    sealed(tmp_path)
    config = configuration(); config['limits']['max_postprocess_requests'] = 401
    model = Models()
    with pytest.raises(BudgetExceeded):
        mining.process(tmp_path/'seal.json', tmp_path/'library', config=config, models=model)
    assert len(model.calls) == 401
    assert len(LibraryStore(tmp_path/'library').active()['rules']) == 1
    assert not list((tmp_path/'postprocess').glob('*/result.json'))


def test_resume_reuses_api_receipts_and_identical_tfidf_after_interruption(tmp_path):
    sealed(tmp_path)
    class Durable(Models):
        def __init__(self):
            super().__init__(); self.interrupt = True
        def generate(self, role, payload, schema, root, **kwargs):
            if role == 'reconciler' and self.interrupt:
                self.interrupt = False
                raise RuntimeError('Fixture interruption before sending')
            identity = {'role':role, 'payload':payload, 'schema':schema}
            return request_once(root, identity,
                lambda: super(Durable, self).generate(role, payload, schema, root, **kwargs))
    model = Durable()
    with pytest.raises(RuntimeError, match='Fixture interruption'):
        mining.process(tmp_path/'seal.json', tmp_path/'library', models=model)
    assert len(model.calls) == 402
    result = mining.process(tmp_path/'seal.json', tmp_path/'library', models=model)
    assert result['status'] == 'AWAITING_HUMAN_REVIEW' and len(model.calls) == 404
    assert len(read(Path(result['job'])/'budget.json')['requests']) == 404
    def unavailable():
        raise WaitingForConfiguration('Credentials have been removed')
    model.check = unavailable
    assert mining.process(tmp_path/'seal.json', tmp_path/'library', models=model) == result
    assert len(model.calls) == 404


@pytest.mark.parametrize('local,expected', [(None, 'process-fixture'), ('file-fixture', 'file-fixture'), ('', None)])
def test_external_credential_uses_project_dotenv_precedence(monkeypatch, tmp_path, local, expected):
    from src.rubrics import providers
    monkeypatch.setattr(providers, 'CONFIG_PATH', tmp_path/'config/rubrics_iteration.json')
    monkeypatch.setenv('BUZZ_API_KEY', 'process-fixture')
    if local is not None:
        (tmp_path/'.env').write_text('BUZZ_API_KEY='+local+'\n')
    settings = {'api_key_env':'BUZZ_API_KEY'}
    if expected is None:
        with pytest.raises(WaitingForConfiguration, match='BUZZ_API_KEY'):
            providers._credential(settings)
    else:
        assert providers._credential(settings) == expected
    assert providers._credential({'api_key_env':None}) is None


def test_preflight_and_http_both_read_project_dotenv_without_export(monkeypatch, tmp_path):
    import httpx
    from src.rubrics import providers
    monkeypatch.setattr(providers, 'CONFIG_PATH', tmp_path/'config/rubrics_iteration.json')
    monkeypatch.delenv('BUZZ_API_KEY', raising=False)
    (tmp_path/'.env').write_text('BUZZ_API_KEY=local-offline-fixture\n')
    config = configuration(Path(__file__).resolve().parents[1]/'config/rubrics_iteration.json')
    for settings in config['external_models'].values():
        settings.update(provider='openai_compatible', model='fixture', base_url='https://fixture.invalid/v1')
    ExternalModels(config).check()
    requests = []
    def handler(request):
        assert request.headers['authorization'] == 'Bearer local-offline-fixture'
        requests.append(request)
        return httpx.Response(200, json={'ok':True})
    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))
    assert providers.OpenAICompatible(config['external_models']['extractor'])._post('chat/completions', {}) == {'ok':True}
    assert len(requests) == 1
