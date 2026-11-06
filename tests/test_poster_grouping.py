"""Score boundaries, incomplete reviews, immutable migration and grouped recovery."""
from copy import deepcopy
from pathlib import Path

import pytest

from src.workflow.exploration_store import ExplorationStore
from src.workflow.poster_grouping import complete_score, poster_group
from utils.persistence import _atomic_json, file_hash, read_json


def report(score=80):
    return {'evaluation_status': 'complete', 'overall_score': score}


@pytest.mark.parametrize('score,expected', [(0, 'low_score'), (79.999, 'low_score'),
                                         (80, 'high_score'), (100, 'high_score')])
def test_boundary_uses_complete_numeric_score(score, expected):
    assert poster_group({'status': 'scored', 'score': score}, report(score)) == expected


@pytest.mark.parametrize('score', [None, True, '90', -1, 101, float('nan'), float('inf'), 10**1000])
def test_invalid_score_is_not_high_or_low(score):
    assert not complete_score(report(score))
    assert poster_group({'status': 'scored', 'score': score}, report(score)) == 'evaluation_failed'


@pytest.mark.parametrize('change', ['status', 'result_status', 'mismatch', 'dimensions', 'stage',
                                  'missing_stage', 'missing_leaf', 'missing_assessment', 'missing_policy'])
def test_partial_or_failed_review_wins_over_surviving_high_score(change):
    result = {'status': 'scored', 'score': 90}
    evaluation = {**report(90), 'scoring_method': 'model_submetrics_v1',
        'assessment_stages': {'content': {'status': 'complete'}, 'visual': {'status': 'complete'}},
        'aggregation_policy': {'dimensions': {'science': {'submetrics': {'grounding': 1}}}},
        'dimension_scores': {'science': 90}, 'submetric_scores': {'grounding': 90},
        'submetric_assessments': {'grounding': {'score': 90, 'assessment_status': 'assessed'}}}
    assert poster_group(result, evaluation) == 'high_score'
    if change == 'status': evaluation['evaluation_status'] = 'failed'
    elif change == 'result_status': result['status'] = 'evaluation_failed'
    elif change == 'mismatch': result['score'] = 91
    elif change == 'dimensions': evaluation['required_dimensions_present'] = False
    elif change == 'stage': evaluation['assessment_stages']['visual']['status'] = 'failed'
    elif change == 'missing_stage': del evaluation['assessment_stages']['visual']
    elif change == 'missing_leaf': del evaluation['submetric_scores']['grounding']
    elif change == 'missing_assessment': del evaluation['submetric_assessments']['grounding']
    elif change == 'missing_policy': del evaluation['aggregation_policy']
    assert poster_group(result, evaluation) == 'evaluation_failed'


def bundle(store, poster_id, score=80, status='complete', group=None):
    directory = store.posters / group / poster_id if group else store.posters / poster_id
    directory.mkdir(parents=True)
    result = {'run_id': 'run_test', 'sample_id': poster_id, 'poster_id': poster_id,
              'status': 'scored' if status == 'complete' else 'evaluation_failed',
              'score': score if status == 'complete' else None, 'grouping': 'unclassified'}
    for name in ('poster.png', 'poster.pptx', 'template.json'):
        (directory / name).write_bytes(b'preserved bundle bytes')
    _atomic_json(directory / 'evaluation.json', {**report(score), 'evaluation_status': status})
    _atomic_json(directory / 'provenance.json', result)
    _atomic_json(directory / 'bundle.json', {'files': {p.name: file_hash(p) for p in directory.iterdir()}})
    (directory / 'diagnostics').mkdir()
    (directory / 'diagnostics' / 'detail.json').write_bytes(b'{"original":true}')
    return directory, result


def fingerprints(directory):
    return {str(p.relative_to(directory)): file_hash(p) for p in directory.rglob('*') if p.is_file()}


def test_migrate_flat_and_wrong_group_preserves_bytes_and_finalization(tmp_path):
    store = ExplorationStore(tmp_path)
    cases = [('a', 80, 'complete', None, 'high_score'),
             ('b', 79.9, 'complete', 'high_score', 'low_score'),
             ('c', 99, 'partial', None, 'evaluation_failed')]
    before = {}
    for pid, score, status, group, expected in cases:
        directory, result = bundle(store, pid, score, status, group)
        before[pid] = fingerprints(directory)
        store.finalize('run_test', pid, result)
    markers = fingerprints(store.runs)
    preview = store.regroup_posters(dry_run=True)
    assert preview['counts'] == dict(high_score=1, low_score=1, evaluation_failed=1)
    assert all(Path(row['source']).exists() for row in preview['posters'])
    store.regroup_posters()
    for pid, _, _, _, expected in cases:
        directory = store.verify_poster(pid)
        assert directory.parent.name == expected
        assert fingerprints(directory) == before[pid]
    assert fingerprints(store.runs) == markers
    assert [r['grouping'] for r in store.results('run_test')] == ['high_score', 'low_score', 'evaluation_failed']
    assert not any(row['moved'] for row in store.regroup_posters()['posters'])


def test_failed_migration_can_resume_after_one_atomic_move(tmp_path, monkeypatch):
    import src.workflow.exploration_store as module
    store = ExplorationStore(tmp_path)
    bundle(store, 'a'); bundle(store, 'b', 40)
    replace = module.os.replace
    def interrupt(source, destination):
        if Path(source).name == 'b': raise OSError('interrupted migration')
        return replace(source, destination)
    monkeypatch.setattr(module.os, 'replace', interrupt)
    with pytest.raises(OSError, match='interrupted migration'): store.regroup_posters()
    assert store.verify_poster('a').parent.name == 'high_score'
    assert store.verify_poster('b').parent == store.posters
    monkeypatch.setattr(module.os, 'replace', replace)
    assert sum(r['moved'] for r in store.regroup_posters()['posters']) == 1


def test_corruption_preflight_prevents_partial_migration(tmp_path):
    store = ExplorationStore(tmp_path)
    first, _ = bundle(store, 'a')
    last, _ = bundle(store, 'z')
    (last / 'poster.png').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='missing or changed'): store.regroup_posters()
    assert first.exists()


@pytest.mark.parametrize('fault', ['duplicate', 'poster_symlink', 'group_symlink', 'unsafe_id'])
def test_paths_cannot_escape_or_ambiguously_select_a_bundle(tmp_path, fault):
    store = ExplorationStore(tmp_path / 'store')
    directory, _ = bundle(store, 'a')
    if fault == 'duplicate': bundle(store, 'a', group='low_score')
    elif fault == 'poster_symlink': (store.posters / 'link').symlink_to(directory, target_is_directory=True)
    elif fault == 'group_symlink': (store.posters / 'high_score').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        if fault == 'unsafe_id': store.verify_poster('../a')
        else: store.regroup_posters()


def test_incomplete_live_report_publishes_to_failure_group(tmp_path):
    from test_exploration_samples import runner, scientific
    def partial(state):
        state['critic_report'] = {**report(99), 'assessment_stages': {
            'content': {'status': 'complete'}, 'visual': {'status': 'failed'}}}
        return state
    generator = runner(tmp_path, samples=1, critic=partial)
    outcome = generator.run(scientific(tmp_path), paper_ready=True)['run_state']
    result = outcome['results'][0]
    assert result['status'] == 'evaluation_failed' and result['score'] is None
    assert result['grouping'] == 'evaluation_failed' and outcome['scored_samples'] == 0
    assert generator.storage.verify_poster(result['poster_id']).parent.name == 'evaluation_failed'
