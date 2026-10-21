from contextlib import nullcontext
import io
import signal
from pathlib import Path
import pytest

from src.workflow import exploration_cli as cli
from src.workflow.sample_progress import SampleProgressReporter


def test_cli_uses_only_independent_samples_and_restores_signal(tmp_path,monkeypatch):
    pdf=tmp_path/'paper.pdf';pdf.write_bytes(b'test')
    captured={}
    original=cli.create_state
    def make_state(*args,**kwargs):
        state=original(*args,**kwargs);state['output_dir']=str(tmp_path/'work');return state
    class Runner:
        def __init__(self,**kwargs):captured.update(kwargs)
        def run(self,state):
            signal.getsignal(signal.SIGINT)(signal.SIGINT,None)
            assert captured['control'].stop_requested
            state['run_state']={'run_id':'run_test','finalized_samples':1,'planned_samples':2,
                                'rendered_samples':1,'scored_samples':1,'status':'PAUSED'}
            return state
    before=signal.getsignal(signal.SIGINT)
    monkeypatch.setattr(cli,'create_state',make_state)
    monkeypatch.setattr(cli,'PosterExplorationRunner',Runner)
    monkeypatch.setattr(cli,'tee_console_output',lambda p:nullcontext())
    monkeypatch.setattr(cli,'save_timing_log',lambda s:None)
    monkeypatch.setattr('sys.argv',['samples','--paper_path',str(pdf),'--samples','2','--random_seed','31'])
    assert cli.main()==0
    assert captured['samples']==2 and captured['random_seed']==31
    assert signal.getsignal(signal.SIGINT)==before
    assert 'batch_mode' not in captured and 'campaign_id' not in captured


@pytest.mark.parametrize('old',['--mode','--iterations','--campaign_id','--batch-id','--target-lineage-id'])
def test_removed_modes_are_explicit_errors(old):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(['--paper_path','paper.pdf',old,'value'])
    assert exc.value.code==2


def test_sample_progress_reports_low_score_as_saved_and_shuts_down(tmp_path):
    output=io.StringIO()
    with SampleProgressReporter(tmp_path/'run.log',terminal=output) as reporter:
        reporter.emit({'type':'sample_saved','result':{'sample_id':'s1','status':'scored','score':2}})
        reporter.emit({'type':'stage_start','stage':'renderer'})
        reporter.write_traceback('trace')
    assert 's1 saved' in output.getvalue() and 'score 2' in output.getvalue()
    assert 'discard' not in output.getvalue() and not reporter._thread.is_alive()
