"""The editorial scoring band matches its writing target at the 90% boundary."""
from copy import deepcopy

import pytest

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.section_fit import SectionFitEvaluator
from src.workflow.editorial_critic import EditorialEvaluator,editorial_critic_config
from test_section_fit import _state


def test_editorial_scoring_config_isolated_from_legacy_and_input():
    original=load_critic_config();snapshot=deepcopy(original)
    current=editorial_critic_config(original)
    assert original==snapshot
    assert original['evaluators']['section_fit']['ideal_minimum']==.95
    assert current['evaluators']['section_fit']['ideal_minimum']==.90
    assert current['evaluators']['section_fit']['ideal_maximum']==1
    assert current['dimension_sources']==original['dimension_sources']
    assert current['dimensions']==original['dimensions']
    assert current['rubric_version']=='academic_poster_editorial_v3'


@pytest.mark.parametrize('utilization,ideal',[(.8999,False),(.90,True),(.92,True),(.9499,True),(.95,True),(1,True),(1.006,False)])
def test_boundary_and_underfill_penalty_share_the_same_band(utilization,ideal):
    state=_state(height=30*utilization)
    state.update(editorial_version='poster_editorial_v1',editorial_candidate={'modules':[
        {'module_id':'results','entries':[{'text':'A distinct source explanation.'}]}]})
    state['styled_layout'][0]['planned_module_height']=30
    config=editorial_critic_config(load_critic_config())
    context=CriticContext(state,config)
    measured=SectionFitEvaluator().evaluate(context)
    metric=state['section_fit_analysis']['sections']['results']
    assert metric['in_ideal_band'] is ideal
    assert state['section_fit_analysis']['ideal_band']==[.90,1]
    underfill=[i for i in measured.issues if i['issue_id'].startswith('SECTION-UNDERFILLED')]
    assert bool(underfill)==(utilization<.90)
    if underfill:assert 'less than 90%' in underfill[0]['observation']
    adequacy=EditorialEvaluator('content_adequacy').evaluate(context)
    assert adequacy.scores['content_quality']==(94 if utilization<.90 else 100)
    if ideal:
        assert measured.scores['layout_integrity']==100
        assert adequacy.metadata['underfilled_section_count']==0
        assert measured.positive_patterns
        assert '90%-100%' in measured.positive_patterns[0]['observation']


def test_adequacy_fallback_uses_current_scoring_config_not_old_95_percent():
    state={'editorial_candidate':{'modules':[{'module_id':'m','entries':[{'text':'Useful mechanism.'}]}]},
           'section_fit_analysis':{'sections':{'m':{'utilization':.92}}}}
    verdict=EditorialEvaluator('content_adequacy').evaluate(CriticContext(state,editorial_critic_config(load_critic_config())))
    assert verdict.scores['content_quality']==100
    assert verdict.metadata['underfilled_section_count']==0


def test_legacy_92_percent_still_uses_its_unchanged_95_percent_band():
    state=_state(height=30*.92)
    verdict=SectionFitEvaluator().evaluate(CriticContext(state,load_critic_config()))
    assert not state['section_fit_analysis']['sections']['results']['in_ideal_band']
    assert any('less than 95%' in i['observation'] for i in verdict.issues)
