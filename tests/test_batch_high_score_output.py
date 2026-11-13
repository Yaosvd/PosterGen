"""High-score batch preview and custom-output publication, without model calls."""
from pathlib import Path

import pytest

from rubrics_poster import batch
from src.workflow.exploration_store import ExplorationStore
from utils.persistence import _atomic_json, digest, read_json
from test_exploration_samples import runner, scientific, critic_with_scores


def test_default_plan_uses_same_thirty_papers_without_starting(tmp_path, monkeypatch, capsys):
    import json
    import src.config.exploration_config as config
    monkeypatch.setattr(config, 'load_exploration_config', lambda: {'storage_root': str(tmp_path/'storage')})
    monkeypatch.setattr(batch, 'gpu_uuid', lambda *_: pytest.fail('Preview must not access GPU'))
    monkeypatch.setattr(batch.subprocess, 'Popen', lambda *a, **k: pytest.fail('Preview must not start workers'))
    args = batch.parser().parse_args([])
    assert batch.run(args) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['papers'] == 30 and plan['target'] == 10 and plan['total_high_scores'] == 300
    assert plan['workers'] == 30 and plan['model_slots'] == 6 and plan['render_slots'] == 2
    assert plan['gpu_index'] == 2 and plan['max_attempts'] == 150
    assert plan['target_group'] == 'high_score' and plan['score_threshold'] == 80
    assert plan['poster_output'] == str(batch.PROJECT/'output/test_posters')
    assert not plan['execute'] and not (tmp_path/'storage').exists()
    selection = read_json(args.manifest)
    assert selection['sampling_plan']['samples_per_paper'] == plan['target']
    assert selection['sampling_plan']['max_attempts_per_paper'] == plan['max_attempts']
    assert selection['sampling_plan']['eligible_score_groups'] == ['high_score']


def test_old_complete_score_batch_cannot_resume_as_high_score_batch(tmp_path):
    state = {'version': 1, 'config': {}}
    _atomic_json(tmp_path/'batch.json', {**state, 'digest': digest(state)})
    with pytest.raises(ValueError, match='target contract changed'):
        batch.run(batch.parser().parse_args(['--resume', str(tmp_path)]))


@pytest.mark.parametrize('ceiling', ['0', '-1', '9'])
def test_invalid_attempt_limit_rejected(ceiling):
    with pytest.raises((SystemExit, ValueError)):
        batch.run(batch.parser().parse_args(['--max-attempts', ceiling]))


def custom_generator(tmp_path, scores):
    generator = runner(tmp_path, samples=len(scores), critic=critic_with_scores(scores))
    output = tmp_path/'output/test_posters'
    generator.storage = ExplorationStore(tmp_path/'storage', poster_output=output)
    result = generator.run(scientific(tmp_path), paper_ready=True)
    return generator, output, result


def test_custom_output_keeps_all_groups_and_default_readers_and_webui_work(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from webui.backend import sample_api as api
    generator, output, result = custom_generator(tmp_path, [79.99, 80])
    reader = ExplorationStore(generator.storage.root)
    records = reader.results(generator.run_id)
    assert [r['grouping'] for r in records] == ['low_score', 'high_score']
    assert all(r['poster_collection'] == 'test_posters' for r in records)
    assert not (generator.storage.root/'posters').exists()
    for row in records:
        directory = reader.verify_poster(row['poster_id'])
        assert directory == output/row['grouping']/row['paper_directory']/row['poster_id']
        assert (directory/'poster.pptx').is_file()
    assert not any(generator.storage._pending_root().iterdir())
    assert not any(r['moved'] for r in generator.storage.regroup_posters()['posters'])
    monkeypatch.setattr(api, 'store', lambda: reader)
    client = TestClient(api.app)
    assert client.get(f'/runs/{generator.run_id}').status_code == 200
    assert client.get(f"/runs/{generator.run_id}/posters/{records[1]['poster_id']}/poster.png").status_code == 200


def test_custom_output_recovers_published_result_and_rejects_destination_change(tmp_path):
    generator, output, result = custom_generator(tmp_path, [90])
    store = generator.storage
    sample = store.sample_path(generator.run_id, 'sample_000001')
    original = (sample/'FINALIZED.json').read_bytes()
    (sample/'FINALIZED.json').unlink()
    reader = ExplorationStore(store.root)
    reader.recover_published(generator.run_id)
    assert (sample/'FINALIZED.json').read_bytes() == original
    assert len(reader.results(generator.run_id)) == 1
    wrong = ExplorationStore(store.root, poster_output=tmp_path/'different')
    with pytest.raises(ValueError, match='output changed'):
        wrong.results(generator.run_id)
    manifest = store.run_path(generator.run_id)/'manifest.json'
    data = read_json(manifest)
    for invalid in (str(tmp_path/'different'), None):
        data['poster_output'] = invalid
        _atomic_json(manifest, data)
        with pytest.raises(ValueError, match='output identity mismatch'):
            reader.results(generator.run_id)


def test_output_staging_uses_destination_filesystem_and_rejects_symlinks(tmp_path, monkeypatch):
    import src.workflow.exploration_store as module
    replace = module.os.replace
    renames = []
    def checked(source, destination):
        if Path(source).is_dir():
            assert Path(source).is_relative_to(tmp_path/'output/test_posters')
            assert Path(destination).is_relative_to(tmp_path/'output/test_posters')
            renames.append((source, destination))
        return replace(source, destination)
    monkeypatch.setattr(module.os, 'replace', checked)
    generator, output, _ = custom_generator(tmp_path, [85])
    assert len(renames) == 2  # Paper identity reservation and complete poster bundle.
    link = tmp_path/'linked_output'; link.symlink_to(output, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        ExplorationStore(tmp_path/'storage', poster_output=link)
    (output/'low_score').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        generator.storage.regroup_posters()
