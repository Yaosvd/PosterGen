"""Independent sample generation and score-independent, inspectable storage."""
from copy import deepcopy
import json
from pathlib import Path

from PIL import Image
from pptx import Presentation
import pytest

from src.config.critic_config import load_critic_config
from src.state.poster_state import create_state
from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.exploration_store import ExplorationStore
from src.workflow.run_control import RunControl
from utils.persistence import read_json, _atomic_json


def scientific(tmp_path):
    paper = tmp_path / 'paper.pdf'
    paper.write_bytes(b'synthetic test paper')
    state = create_state(str(paper), width=54, height=36, poster_name='test')
    state.update(verification_passed=True, raw_text='Synthetic evidence',
                 evidence_bank={'items':[{'evidence_id':'e1','source_excerpt':'Synthetic evidence'}]},
                 verified_claims={'claims':[{'claim_id':'c1','text':'A verified observation.','evidence_ids':['e1']}]},
                 narrative_plan={'sections':[{'section_id':'s1','narrative_role':'results','claim_ids':['c1']}]})
    return state


def prepare_sample(state):
    assert not state.get('narrative_plan') and not state.get('verified_claims')
    assert not state.get('story_board') and not state.get('critic_report')
    state.update(verification_passed=True,
        narrative_plan={'sections':[{'section_id':'s1','narrative_role':'results','evidence_ids':['e1']}]},
        poster_claims={'claims':[{'claim_id':'c1','section_id':'s1','text':'A verified observation.','evidence_ids':['e1']}]},
        verified_claims={'claims':[{'claim_id':'c1','section_id':'s1','text':'A verified observation.','evidence_ids':['e1']}]})
    return state


def render_sample(state):
    assert not (state.get('verified_content_bank') or {}).get('claims')
    assert not state.get('story_board')
    assert not state.get('critic_report')
    claim = state['verified_claims']['claims'][0]
    state['story_board']={'spatial_content_plan':{'sections':[{'section_id':'s1','claim_ids':[claim['claim_id']],'text_content':[claim['text']]}]}}
    state['layout_spec']={'family_id':state['iteration_context']['layout_family'],
                          'zones':[{'zone_id':'zone','x':0,'y':0,'width':1,'height':1,'section_ids':['s1']}],
                          'geometry_fingerprint':'fixed-test-geometry','reading_order':['s1']}
    state['styled_layout']=[{'type':'section_container','id':'box','section_id':'s1','x':2,'y':8,'width':10,'height':15},
                            {'type':'text','id':'text','section_id':'s1','x':2,'y':9,'width':10,'height':3,'text':'SAMPLE SCIENTIFIC TEXT'}]
    root=Path(state['output_dir']);root.mkdir(parents=True,exist_ok=True)
    pptx=root/'test.pptx'; png=root/'test.png'
    deck=Presentation();deck.slides.add_slide(deck.slide_layouts[6]);deck.save(pptx)
    Image.new('RGB',(540,360),'white').save(png)
    state['current_candidate'].update(status='rendered',pptx_path=str(pptx),png_path=str(png))
    state['verified_content_bank']={'claims':[{'claim_id':'variant-from-this-sample'}]}
    return state


def critic_with_scores(scores):
    values=iter(scores)
    def score(state):
        value=next(values)
        state['critic_report']={'evaluation_status':'complete','overall_score':value,'issues':[], 'positive_patterns':[]}
        return state
    return score


def runner(tmp_path, **kwargs):
    return PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'new_samples'),
        design_nodes=[render_sample],paper_nodes=[],random_seed=19,**kwargs)


def test_low_and_high_scores_both_keep_actual_templates_without_learning(tmp_path):
    old=tmp_path/'critic_loop';old.mkdir();(old/'historical.json').write_text('{"untouched":true}')
    before=(old/'historical.json').read_bytes()
    generator=runner(tmp_path,samples=2,critic=critic_with_scores([8,99]))
    result=generator.run(scientific(tmp_path),paper_ready=True)
    assert result['run_state']['status']=='COMPLETED'
    records=result['run_state']['results']
    assert [r['score'] for r in records]==[8,99]
    assert all(r['grouping']=='unclassified' for r in records)
    for record in records:
        directory=generator.storage.verify_poster(record['poster_id'])
        assert {'poster.png','poster.pptx','template.json','template.png','template.pptx','evaluation.json','provenance.json'}<=set(p.name for p in directory.iterdir())
        template=read_json(directory/'template.json')
        assert template['purpose']=='inspection_only'
        assert template['family']==record['layout_family']
        assert template['normalized_blueprint'][0]['width']==10/54
        assert 'SAMPLE SCIENTIFIC TEXT' not in (directory/'template.json').read_text()
    assert (old/'historical.json').read_bytes()==before
    assert not any(p.name in {'lineages','template_library','design_memory','layout_archetypes'} for p in generator.storage.root.rglob('*'))
    assert not generator.storage.paper_foundation(generator.run_id, 'sample_000001').get('verified_content_bank')


def test_resume_does_not_repeat_completed_samples(tmp_path):
    control=RunControl()
    def score(state):
        state=critic_with_scores([30])(state)
        control.request_stop()
        return state
    generator=runner(tmp_path,samples=2,critic=score,control=control)
    first=generator.run(scientific(tmp_path),paper_ready=True)
    assert first['run_state']['status']=='PAUSED'
    assert first['run_state']['finalized_samples']==1
    resumed=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=generator.storage,run_id=generator.run_id,
                                   design_nodes=[render_sample],paper_nodes=[],critic=critic_with_scores([90]))
    result=resumed.run(scientific(tmp_path), paper_ready=True)
    assert result['run_state']['status']=='COMPLETED'
    assert [r['score'] for r in result['run_state']['results']]==[30,90]


def test_local_template_preview_uses_actual_poster_geometry(tmp_path):
    from pptx.util import Inches
    generator = runner(tmp_path, samples=1, critic=critic_with_scores([15]))
    result = generator.run(scientific(tmp_path), paper_ready=True)
    directory = generator.storage.verify_poster(result['run_state']['results'][0]['poster_id'])
    template = read_json(directory / 'template.json')
    shapes = Presentation(directory / 'template.pptx').slides[0].shapes
    assert len(shapes) == len(template['normalized_blueprint'])
    for shape, element in zip(shapes, template['normalized_blueprint']):
        assert shape.left == Inches(16 * element['x'])
        assert shape.top == Inches(16 * element['y'] / template['source_aspect_ratio'])
        assert shape.width == Inches(16 * element['width'])


def test_evaluation_exception_keeps_poster_with_unavailable_score(tmp_path):
    def fail(state): raise RuntimeError('synthetic evaluator failure')
    generator=runner(tmp_path,samples=1,critic=fail)
    result=generator.run(scientific(tmp_path),paper_ready=True)
    record=result['run_state']['results'][0]
    assert record['status']=='evaluation_failed' and record['score'] is None
    assert generator.storage.verify_poster(record['poster_id']).is_dir()


def test_unknown_generation_error_stops_without_fake_score_or_retry(tmp_path):
    calls=[]
    def broken(state):
        calls.append(1)
        raise TypeError('synthetic programming error')
    generator=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'new_samples'),samples=3,
                                    design_nodes=[broken],paper_nodes=[])
    result=generator.run(scientific(tmp_path),paper_ready=True)
    assert result['run_state']['status']=='FAILED'
    assert len(calls)==1 and result['run_state']['results'][0]['score'] is None


def test_known_fit_failure_keeps_one_family_and_finishes_task(tmp_path):
    families=[]
    def design(state):
        families.append(state['iteration_context']['layout_family'])
        if len(families)==1:
            state.update(layout_preflight_failed=True,errors=['known fit failure'],
                         layout_feasibility_report={'status':'infeasible','reason_code':'ASSIGNMENT_EXHAUSTED'})
            state['verified_content_bank']={'claims':[{'claim_id':'must-not-leak'}]}
            return state
        return render_sample(state)
    generator=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'new_samples'),samples=1,
            design_nodes=[design],paper_nodes=[],critic=critic_with_scores([60]))
    result=generator.run(scientific(tmp_path),paper_ready=True)
    assert result['run_state']['status']=='COMPLETED' and len(families)==1
    assert result['run_state']['results'][0]['retry_count']==0


def test_shared_structure_failure_does_not_retry_family_or_score(tmp_path):
    calls=[]
    def design(state):
        calls.append(1)
        state.update(layout_preflight_failed=True,errors=['shared structure'],
                     layout_feasibility_report={'status':'infeasible','failure_scope':'shared_content',
                       'reason_code':'PRESENTATION_STRUCTURE_UNRESOLVED','failure_stage':'structure','trial_count':0})
        return state
    generator=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'new_samples'),samples=2,
            design_nodes=[design],paper_nodes=[],critic=lambda s:pytest.fail('Critic must not run'))
    result=generator.run(scientific(tmp_path),paper_ready=True)
    assert len(calls)==2 and result['run_state']['status']=='COMPLETED'


def test_force_stop_after_render_keeps_diagnostics_but_no_official_sample(tmp_path):
    control=RunControl()
    def render(state):
        state=render_sample(state);control.request_stop(force=True);return state
    generator=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'new_samples'),samples=1,
            design_nodes=[render],paper_nodes=[],control=control,critic=lambda s:pytest.fail('no score'))
    result=generator.run(scientific(tmp_path),paper_ready=True)
    assert result['run_state']['status']=='PAUSED' and result['run_state']['finalized_samples']==0
    assert list(generator.storage.run_path(generator.run_id).rglob('test.png'))


def test_published_bundle_replays_finalization_after_commit_crash(tmp_path,monkeypatch):
    generator=runner(tmp_path,samples=1,critic=critic_with_scores([50]))
    original=generator.storage.finalize
    monkeypatch.setattr(generator.storage,'finalize',lambda *a:(_ for _ in ()).throw(OSError('commit crash')))
    with pytest.raises(OSError,match='commit crash'):
        generator.run(scientific(tmp_path),paper_ready=True)
    monkeypatch.setattr(generator.storage,'finalize',original)
    resumed=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=generator.storage,run_id=generator.run_id,
            design_nodes=[lambda s:pytest.fail('must not regenerate')],critic=lambda s:pytest.fail('must not rescore'))
    result=resumed.run(scientific(tmp_path))
    assert result['run_state']['finalized_samples']==1


@pytest.mark.parametrize('change',['seed','samples','config','paper'])
def test_resume_rejects_input_or_policy_drift(tmp_path,change):
    generator=runner(tmp_path,samples=1,critic=critic_with_scores([50]))
    generator.run(scientific(tmp_path),paper_ready=True)
    kwargs={}
    state=scientific(tmp_path)
    if change=='seed':kwargs['random_seed']=20
    if change=='samples':kwargs['samples']=2
    if change=='config':
        config=load_critic_config();config['explore_layout']['max_exact_candidates']+=1;kwargs['config']=config
    if change=='paper':Path(state['pdf_path']).write_bytes(b'different paper')
    resumed=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=generator.storage,run_id=generator.run_id,**kwargs)
    with pytest.raises(ValueError,match='changed|frozen'):
        resumed.run(state)


def test_corrupt_final_bundle_fails_closed_on_resume(tmp_path):
    generator=runner(tmp_path,samples=1,critic=critic_with_scores([50]))
    result=generator.run(scientific(tmp_path),paper_ready=True)
    poster=generator.storage.posters/result['run_state']['results'][0]['poster_id']/'poster.png'
    poster.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='missing or changed'):
        generator.storage.results(generator.run_id)

@pytest.mark.parametrize('fault',['missing_png','not_rendered','stale'])
def test_unready_artifacts_never_reach_critic_or_become_scored_samples(tmp_path,fault):
    def bad(state):
        state=render_sample(state)
        candidate=state['current_candidate']
        if fault=='missing_png':Path(candidate['png_path']).unlink()
        elif fault=='not_rendered':candidate['status']='planned'
        else:candidate['candidate_id']='stale'
        return state
    generator=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'new_samples'),samples=1,
        design_nodes=[bad],paper_nodes=[],critic=lambda s:pytest.fail('No stale or missing artifacts'))
    result=generator.run(scientific(tmp_path),paper_ready=True)
    assert result['run_state']['status']=='FAILED'
    assert result['run_state']['results'][0]['status']=='generation_failed'
    assert result['run_state']['results'][0]['score'] is None


def test_template_export_failure_resumes_publication_without_regeneration(tmp_path,monkeypatch):
    import src.workflow.exploration_store as module
    original=module.export_template
    monkeypatch.setattr(module,'export_template',lambda *a:(_ for _ in ()).throw(OSError('export interrupted')))
    generator=runner(tmp_path,samples=1,critic=critic_with_scores([45]))
    with pytest.raises(OSError,match='export interrupted'):
        generator.run(scientific(tmp_path),paper_ready=True)
    monkeypatch.setattr(module,'export_template',original)
    resumed=PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=generator.storage,run_id=generator.run_id,
        design_nodes=[lambda s:pytest.fail('Do not regenerate a final poster')],
        critic=lambda s:pytest.fail('Do not score an existing final poster again'))
    result=resumed.run(scientific(tmp_path))
    assert result['run_state']['results'][0]['score']==45
    assert result['run_state']['rendered_samples']==1


def test_foundation_runs_for_each_task_and_scientific_edits_do_not_leak_between_samples(tmp_path):
    calls = []
    control = RunControl()
    def foundation(state):
        calls.append('foundation')
        state.update({key: deepcopy(value) for key, value in scientific(tmp_path).items()
                      if key in {'evidence_bank', 'raw_text'}})
        return state
    def design(state):
        assert state['verified_claims']['claims'][0]['text'] == 'A verified observation.'
        state = render_sample(state)
        state['verified_claims']['claims'][0]['text'] = 'A sample-local mutation must not persist.'
        return state
    def score_and_stop(state):
        control.request_stop()
        return critic_with_scores([55])(state)
    generator = PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'samples'), samples=2,
        paper_nodes=[foundation], design_nodes=[design], critic=score_and_stop, control=control)
    generator.run(scientific(tmp_path))
    resumed = PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=generator.storage, run_id=generator.run_id,
        paper_nodes=[foundation],
        design_nodes=[design], critic=critic_with_scores([20]))
    result = resumed.run(scientific(tmp_path))
    assert calls == ['foundation', 'foundation']
    assert result['run_state']['rendered_samples'] == 2
    assert 'verified_claims' not in resumed.storage.paper_foundation(resumed.run_id, 'sample_000001')
    ready = read_json(resumed.storage.sample_path(resumed.run_id, 'sample_000001')/'preparation/READY.json')
    assert ready['payload']['fields']['verified_claims']['claims'][0]['text'] == 'A verified observation.'


def test_force_stopped_repair_charges_survive_resume_without_cross_sample_leak(tmp_path):
    from src.layout.repair_budget import available_rounds, charge_round
    policy = load_critic_config()['capacity_repair']
    control = RunControl()
    remaining = []
    def charge_and_stop(state):
        assert charge_round(state, 'capacity', policy)
        control.request_stop(force=True)
        return state
    generator = PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=ExplorationStore(tmp_path/'samples'), samples=2,
        paper_nodes=[], design_nodes=[charge_and_stop], control=control)
    generator.run(scientific(tmp_path), paper_ready=True)
    def check_remaining(state):
        remaining.append(available_rounds(state, 'capacity', policy))
        return render_sample(state)
    resumed = PosterExplorationRunner(preparation_nodes=[prepare_sample], storage=generator.storage, run_id=generator.run_id,
        design_nodes=[check_remaining], critic=critic_with_scores([30, 40]))
    result = resumed.run(scientific(tmp_path), paper_ready=True)
    assert remaining == [policy['max_rounds_per_iteration'] - policy['quality_reserved_rounds'] - 1,
                         policy['max_rounds_per_iteration'] - policy['quality_reserved_rounds']]
    assert result['run_state']['rendered_samples'] == 2
    assert result['run_state']['results'][0]['attempt_id'] == 'attempt_0002'
