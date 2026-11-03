"""Migration boundary and behavioral-copy checks without a donor checkout."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'docs/reports/extraction_manifest.json'
# Historical donor path; runtime-boundary checks must work without local reports.
SOURCE_PROJECT='/projectone/projects/PosterGen'


@pytest.mark.skipif(os.getenv('RUBRICS_VALIDATE_EXTRACTION')!='1' or not MANIFEST.is_file(), reason='Optional one-time extraction check requires the local historical manifest')
def test_active_algorithms_prompts_fonts_and_configs_match_migration_baseline():
    manifest=json.loads(MANIFEST.read_text())
    checked=[]
    for name in manifest['unchanged_source_files']:
        if name.startswith(('src/','utils/','config/','fonts/')):
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==manifest['source_file_sha256'][name],name
            checked.append(name)
    assert len(checked)>100
    assert len(list((ROOT/'config/prompts').glob('editorial_*.txt')))>=8


def test_editable_environment_and_interpreter_are_project_local():
    assert Path(sys.prefix).resolve()==ROOT/'.venv'
    forbidden=SOURCE_PROJECT
    assert forbidden not in '\n'.join(sys.path)
    site=ROOT/'.venv/lib/python3.11/site-packages'
    for path in site.glob('*.pth'):
        assert forbidden not in path.read_text()
    for path in (ROOT/'src').rglob('*'):
        assert not path.is_symlink()


def test_production_imports_work_with_all_donor_file_access_denied(tmp_path):
    donor=SOURCE_PROJECT
    program='''import os,sys\nfrom pathlib import Path\ndonor=Path(sys.argv[1]).resolve()\ndef guard(event,args):\n    if event in {'open','os.listdir','os.scandir'} and args and isinstance(args[0],(str,bytes)):\n        value=Path(os.fsdecode(args[0])).absolute()\n        if value==donor or donor in value.parents:raise RuntimeError('Donor access forbidden: '+str(value))\nsys.addaudithook(guard)\nfrom src.workflow.exploration_cli import build_parser\nfrom src.workflow.exploration_runner import default_nodes\nfrom webui.backend.sample_api import app\nassert 'src.workflow.pipeline' not in sys.modules\npaper,preparation,design=default_nodes()\nassert [n.__name__ for n in paper]==['parser_node']\nassert [n.__name__ for n in preparation]==['editorial_curator_node','editorial_color_node','editorial_title_node','editorial_joint_node']\nassert len(design)==5\nprint('donor-free production imports passed')\n'''
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    result=subprocess.run([sys.executable,'-c',program,donor],cwd=tmp_path,env=env,
                          capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert 'donor-free production imports passed' in result.stdout


@pytest.mark.parametrize('module',['rubrics_poster','src.workflow.critic_pipeline','src.workflow.pipeline'])
def test_all_public_cli_names_expose_the_same_sample_route(module,tmp_path):
    result=subprocess.run([sys.executable,'-m',module,'--help'],cwd=tmp_path,
                          capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert '--samples' in result.stdout and '--random_seed' in result.stdout
    assert '--iterations' not in result.stdout and '--mode' not in result.stdout


def test_project_path_activation_and_configuration_are_local(tmp_path,monkeypatch):
    from src.workflow.runtime import activate_project,PROJECT_ROOT
    from src.config.poster_config import load_config
    monkeypatch.chdir(tmp_path);activate_project()
    assert Path.cwd()==ROOT and PROJECT_ROOT==ROOT
    assert load_config()['pdf_processing']['batch_sizes']['recognition']>0


def test_webui_rejects_classic_mode_before_generation(monkeypatch):
    from fastapi.testclient import TestClient
    from webui.backend import sample_api
    monkeypatch.setattr(sample_api,'run_poster_generation',lambda *a:pytest.fail('No classic generation'))
    response=TestClient(sample_api.app).post('/generate',data={
        'text_model':'gpt-4o-2024-08-06','vision_model':'gpt-4o-2024-08-06',
        'poster_width':54,'poster_height':36,'sample_generation':'false'},
        files={k:('paper.pdf' if k=='pdf_file' else 'logo.png',b'offline')
               for k in ('pdf_file','logo_file','aff_logo_file')})
    assert response.status_code==400 and 'samples only' in response.text


def test_project_cache_identity_rejects_source_project_identity():
    from src.workflow.paper_cache import extraction_identity
    common={'preparation_policy_version':'sample_editorial_v1','code_identity':{}}
    assert extraction_identity(common)!=extraction_identity({**common,'project_identity':'rubrics_poster_v1'})


@pytest.mark.skipif(not MANIFEST.is_file(), reason='Historical reports are intentionally local and untracked')
def test_report_snapshots_and_all_prior_reports_are_present_and_annotated():
    manifest=json.loads(MANIFEST.read_text())
    assert len(manifest['reports_carried'])==14
    for name in manifest['reports_carried']:
        assert '独立项目迁出说明' in (ROOT/name).read_text()
    assert (ROOT/'docs/reports/archive/POSTERGEN_AGENTS_SNAPSHOT_20261102.md').is_file()
    assert (ROOT/'docs/reports/MODEL_SETUP_20261102.md').is_file()


def test_runtime_tee_captures_both_streams_and_restores_on_error(tmp_path):
    from src.workflow.runtime import tee_console_output
    from contextlib import redirect_stdout, redirect_stderr
    from io import StringIO

    stdout, stderr = StringIO(), StringIO()
    log = tmp_path / 'run.log'
    with redirect_stdout(stdout), redirect_stderr(stderr):
        with pytest.raises(RuntimeError, match='offline failure'):
            with tee_console_output(log):
                print('console message')
                print('diagnostic message', file=sys.stderr)
                raise RuntimeError('offline failure')
        assert sys.stdout is stdout and sys.stderr is stderr
    assert stdout.getvalue() == 'console message\n'
    assert stderr.getvalue() == 'diagnostic message\n'
    assert log.read_text() == 'console message\ndiagnostic message\n'
