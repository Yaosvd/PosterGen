"""Default generation → isolated revision → unchanged G → publication and recovery."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from src.workflow.exploration_runner import PosterExplorationRunner
from src.workflow.exploration_store import ExplorationStore
from src.rubrics.library import LibraryStore
from src.rubrics import refinement
from src.workflow.poster_grouping import complete_score
from test_editorial_generation import state_for, draft_for, plan_for, prose_for, capacity_reply
from test_rubrics_framework import rule, model
from critic_fixtures import content_reply, visual_reply, content_wire_reply, reference_wire_reply


@pytest.mark.parametrize('failure',['none','review','revision','evaluation','interrupt','stage_counts'])
def test_real_pipeline_selects_one_final_and_keeps_process_bundle(monkeypatch,tmp_path,failure):
    state=state_for(tmp_path)
    import fitz
    path=Path(state['pdf_path']);path.unlink()
    doc=fitz.open();page=doc.new_page();page.insert_text((30,30),state['raw_text']);doc.save(path);doc.close()
    prototype=draft_for(state)
    if failure == 'none':
        steps = prototype['modules'][1]
        steps['presentation_style'] = 'steps'
        steps['entries'][0].update(text='Step 1: Collect examples.', display_label='')
        steps['entries'][1].update(text='Analyze examples.', parent_item_id='')
    if failure=='stage_counts':
        # A legal six-module three-column plan, with four results (advisory cap 3).
        modules=[]
        for m in prototype['modules']:
            modules.append(m)
            extra=deepcopy(m);extra['module_id']+='_extra';modules.append(extra)
        prototype['modules']=modules
        for i,m in enumerate(modules):m['narrative_stage']='background' if i<2 else 'results'
    def paper_node(current):
        for key in ('raw_text','structured_sections','narrative_content','images','tables','classified_visuals'):
            current[key]=deepcopy(state[key])
        return current
    from src.agents.font_agent import FontAgent
    selections = []
    def keywords(agent, board, current):
        selections.append(board)
        return {'section_keywords': {'module_0': {'bold_contrast': ['prediction', 'resources'],
                                                  'italic': ['limited']}}}
    monkeypatch.setattr(FontAgent, '_identify_keywords', keywords)
    calls=[]
    class Model:
        def __init__(self,system,config,current,name):self.state=current;self.name=name
        def reset(self):pass
        def step(self,message):
            calls.append(self.name)
            try:parts=json.loads(message)
            except ValueError:parts=None
            text=parts[0]['text'] if isinstance(parts,list) else message
            data=json.loads(text.split('\nINPUT:\n',1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0].split('\n\n<GENERATION_RUBRICS>',1)[0])
            if self.name=='source_curator':value=prose_for(prototype) if data['phase']=='writer' else plan_for(prototype)
            elif self.name=='source_balancer':value=capacity_reply()
            elif self.name=='color_agent':value={'theme_color':'#224466'}
            elif self.name=='critic_content':
                assert '<GENERATION_RUBRICS>' not in text
                if failure=='evaluation':raise TimeoutError('Offline G failure')
                assert self.state.get('refinement_result',{}).get('variant')==('P0' if failure in {'review','revision','interrupt'} else 'P1')
                value=content_wire_reply(content_reply(data['final_poster']['modules'],score=1),self.state)
            elif self.name=='critic_visual':
                assert '<GENERATION_RUBRICS>' not in text
                value=reference_wire_reply(visual_reply(data['final_poster']['modules'],score=0),self.state)
            else:raise AssertionError('Unexpected old call '+self.name)
            return SimpleNamespace(content=json.dumps(value),input_tokens=7,output_tokens=4)
    import utils.langgraph_utils as language
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    monkeypatch.setattr(language,'create_model',lambda *a,**k:pytest.fail('Real network forbidden'))
    from src.layout.families import LayoutFamilyRegistry
    monkeypatch.setattr(LayoutFamilyRegistry,'choose_with_report',lambda self,*a,**k:('classic_three_column',{'offline':True}))
    review_calls=[]
    def request(st,role,*args,**kwargs):
        def invoke():
            review_calls.append(role)
            if role==failure:raise ValueError('Offline technical failure')
            if failure=='interrupt' and role=='revision':
                from utils.concurrency import WorkStopped
                raise WorkStopped()
            reply = model(st,role,*args,**kwargs)
            if failure == 'none' and role == 'revision':
                reply['program_lines'] = [line.replace('shared prediction model', 'shared ranking model')
                                              .replace('Analyze examples.', '(2) Analyze examples.')
                                          for line in reply['program_lines']]
            return reply
        if failure=='interrupt':
            from src.rubrics.storage import request_once
            return request_once(args[2],{'fixture_role':role},invoke)
        return invoke()
    original=refinement.refine_once
    monkeypatch.setattr(refinement,'refine_once',lambda st,**kw:original(st,request=request,**kw))
    monkeypatch.setattr(refinement,'preflight_internal',lambda s:None)
    store=ExplorationStore(tmp_path/'store')
    library=LibraryStore(store.root/'rubrics').publish([rule()],parent_version=None,source_batch_digest='fixture')
    runner=PosterExplorationRunner(storage=store,paper_nodes=[paper_node],samples=1,random_seed=42,
        mode='rubric-refine-score',round_identity={'round_id':'offline_round'})
    result=runner.run(state)
    if failure=='interrupt':
        assert result['run_state']['status']=='PAUSED' and not result['run_state']['results']
        before=list(calls)
        runner=PosterExplorationRunner(storage=store,paper_nodes=[paper_node],run_id=runner.run_id,
            mode='rubric-refine-score',round_identity={'round_id':'offline_round'})
        result=runner.run(state)
        # Initial generation was recovered. Charged-but-unanswered Actor is not sent twice.
        assert calls[:len(before)]==before
        assert calls[len(before):]==['critic_content','critic_visual']
    rows=result['run_state']['results']
    assert len(rows)==1 and rows[0]['poster_id'],rows
    row=rows[0]
    assert row['status']==('evaluation_failed' if failure=='evaluation' else 'scored'),row
    assert row['generation_rubrics']==library['version'] and row['sample_mode']=='rubric-refine-score'
    directory=store.verify_poster(row['poster_id'])
    if failure=='stage_counts':
        spec=json.loads((directory/'diagnostics/layout_spec.json').read_text())
        issues=[i for i in spec['reading_route']['issues'] if i['code']=='narrative_stage_count_exceeded']
        assert issues==[{'code':'narrative_stage_count_exceeded','stage':'results','actual':4,
                        'maximum':3,'module_ids':[m['module_id'] for m in prototype['modules'][2:]],
                        'generation_blocking':False}]
        assert complete_score(json.loads((directory/'evaluation.json').read_text()))
        assert row['status']=='scored'
    assert len(selections) == 1
    assert (directory/'refinement/C0.py').exists()
    # The isolated C0 renderer enforces pixel equality; verify the original deck
    # contains multiple independently highlighted terms and program-owned markers.
    from pptx import Presentation
    deck = Presentation(directory/'refinement/P0.pptx')
    paragraphs = [p for shape in deck.slides[0].shapes if shape.has_text_frame
                  for p in shape.text_frame.paragraphs]
    assert any(p.text.startswith('• Core mechanism:') for p in paragraphs)
    assert any(p.text.startswith('◦ The policy') for p in paragraphs)
    accented = [r.text for p in paragraphs for r in p.runs
                if r.font.bold and r.text in ('prediction', 'resources') and r.font.color.rgb]
    assert {'prediction', 'resources'} <= set(accented)
    if failure == 'none':
        assert {'Step 1: Collect examples.', '2) Analyze examples.'} <= {p.text for p in paragraphs}
        revised_deck = Presentation(directory/'refinement/P1/poster.pptx')
        revised_lines = {p.text for shape in revised_deck.slides[0].shapes if shape.has_text_frame
                         for p in shape.text_frame.paragraphs}
        assert {'Step 1: Collect examples.', '(2) Analyze examples.'} <= revised_lines
        revised_runs = [r for shape in revised_deck.slides[0].shapes if shape.has_text_frame
                        for p in shape.text_frame.paragraphs for r in p.runs]
        assert any('shared ranking model' in r.text for r in revised_runs)
        assert not any(r.text == 'prediction' for r in revised_runs)
        original_color = next(r.font.color.rgb for p in paragraphs for r in p.runs if r.text == 'resources')
        assert any(r.text == 'resources' and r.font.bold and r.font.color.rgb == original_color
                   for r in revised_runs)
    if failure not in {'review','revision','interrupt'}:assert (directory/'refinement/C1.py').exists()
    assert review_calls==(['review'] if failure=='review' else ['review','revision'])
    assert calls.count('critic_content')==1 and calls.count('critic_visual')==(0 if failure=='evaluation' else 1)
    # Simulate a crash between publication and finalization; no models are repeated.
    final=store.sample_path(runner.run_id,'sample_000001')/'FINALIZED.json'
    before=final.read_bytes();final.unlink()
    store.recover_published(runner.run_id)
    assert final.read_bytes()==before
    assert store.verify_poster(row['poster_id'])==directory
