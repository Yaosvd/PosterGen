"""Freeze defective but renderable editorial outcomes without quality rewriting."""
from copy import deepcopy
import math

import pytest

from test_editorial_generation import state_for,draft_for,install
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import (VERSION,OUTPUT_POLICY,permits_layout_defects,
    geometry_digest,assert_editorial_ready)


def test_quality_editor_and_draft_preview_are_removed():
    assert 'quality' not in pipeline.LIMITS
    assert not permits_layout_defects({'editorial_version':VERSION,'editorial_output_policy':OUTPUT_POLICY})
    assert not hasattr(pipeline,'preview') and not hasattr(pipeline,'_preview')
    with pytest.raises(ValueError,match='capacity'):
        pipeline.edit({},None,'quality')


def freeze(monkeypatch,tmp_path,*,defects=False):
    from src.layout.editorial_layout import measure
    state=state_for(tmp_path);raw=draft_for(state)
    if defects:
        raw['modules'][0]['entries'][0]['text']='Limited resources.\n'*60
        extra=deepcopy(raw['modules'][1]);extra['module_id']='extra';extra['zone_id']=raw['modules'][0]['zone_id']
        raw['modules'].insert(1,extra)
    install(state,raw)
    pipeline.charge(state,'curator','offline_fixture')
    monkeypatch.setattr(pipeline,'fit',lambda s,c,z:measure(s,c,z))
    phases=[]
    def no_useful_edit(s,result,phase):phases.append(phase);return False
    monkeypatch.setattr(pipeline,'edit',no_useful_edit)
    pipeline.editorial_joint_node(state)
    pipeline.editorial_compile_node(state)
    assert phases==['capacity']
    return state


def test_actual_overflow_and_overlap_freeze_with_failed_diagnostics(monkeypatch,tmp_path):
    from src.agents.layout_preflight import layout_preflight_node
    from src.critic.evaluators import GeometryEvaluator
    from src.critic.base import CriticContext
    state=freeze(monkeypatch,tmp_path,defects=True)
    assert permits_layout_defects(state) and not state['editorial_fit']['passed']
    assert state['editorial_fit']['status']=='layout_defects'
    assert state['editorial_fit']['completion_reason']=='no_useful_edit'
    state['styled_layout']=deepcopy(state['design_layout'])
    layout_preflight_node(state)
    assert state['layout_preflight_report']['passed'] is False
    assert state['layout_preflight_report']['generation_blocking'] is False
    assert state['layout_preflight_failed'] and not state['errors']
    codes={row['code'] for row in state['layout_preflight_report']['issues']}
    assert any('BOUND' in code for code in codes),codes
    verdict=GeometryEvaluator().evaluate(CriticContext(state,state['critic_config']))
    assert not verdict.passed and verdict.metadata['element_count'] > 0
    assert any('OVERLAP' in row['issue_id'] for row in verdict.issues)
    assert_editorial_ready(state,compiled=True)


def test_frozen_geometry_and_policy_cannot_be_silently_changed(monkeypatch,tmp_path):
    state=freeze(monkeypatch,tmp_path)
    saved=state['design_layout'][0]['x'];state['design_layout'][0]['x']+=.1
    with pytest.raises(ValueError,match='geometry'):assert_editorial_ready(state,compiled=True)
    state['design_layout'][0]['x']=saved
    state['editorial_output_policy']=None
    with pytest.raises(ValueError,match='snapshot'):assert_editorial_ready(state,compiled=True)


def test_outside_canvas_boxes_are_drawable_but_nan_and_nonpositive_boxes_are_not():
    assert geometry_digest([{'type':'text','x':-5,'y':50,'width':10,'height':20}])
    for key,value in (('x',math.nan),('height',0),('width',-1)):
        box={'type':'text','x':0,'y':0,'width':1,'height':1};box[key]=value
        with pytest.raises(ValueError,match='non-renderable'):geometry_digest([box])


@pytest.mark.parametrize('advisory',[False,True])
def test_renderfit_records_failure_without_repair_only_under_new_policy(monkeypatch,tmp_path,advisory):
    from src.agents import render_fit_audit as audit
    calls=[]
    state={'generation_route':'optimization_family','editorial_version':VERSION,
           'output_dir':str(tmp_path),'errors':[]}
    if advisory:state['editorial_output_policy']=OUTPUT_POLICY
    report={'status':'failed','passed':False,'issues':[{'code':'RENDER_TEXT_OVERFLOW'}],
            'issue_count':1,'expected_text_count':1,'matched_text_count':1}
    monkeypatch.setattr(audit,'audit_rendered_text',lambda s:deepcopy(report))
    monkeypatch.setattr(audit,'_correct_title_fit',lambda *a:calls.append(True))
    audit.render_fit_audit_node(state)
    assert state['render_fit_report']['passed'] is False and state['layout_preflight_failed']
    assert bool(state['errors']) is not advisory
    assert bool(calls) is not advisory
    if advisory:assert state['render_fit_report']['correction_policy']=='frozen_no_rerender'


def test_real_runtime_error_still_stops_even_with_recorded_geometry_failure(tmp_path):
    from src.workflow.exploration_runner import PosterExplorationRunner
    runner=PosterExplorationRunner();runner.runtime={};runner._curation=None
    state=state_for(tmp_path);state['editorial_output_policy']=OUTPUT_POLICY
    state['layout_preflight_failed']=True
    def broken_renderer(s):s['errors'].append('actual output could not be created');return s
    def forbidden_next(s):pytest.fail('Runtime failures cannot become saved posters')
    result=runner._run_nodes(state,[broken_renderer,forbidden_next],stage='design')
    assert result['fatal_generation_error'] and result['attempt_failure_report']
