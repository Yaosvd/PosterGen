"""Utilization remains observable evidence, not a deterministic quality score."""
from copy import deepcopy

import pytest

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.section_fit import SectionFitEvaluator
from src.workflow.editorial_critic import MeasurementEvaluator, editorial_critic_config
from test_section_fit import _state


def test_scoring_config_has_one_current_policy_and_preserves_input():
    original=load_critic_config();snapshot=deepcopy(original)
    current=editorial_critic_config(original)
    assert original==snapshot
    assert original['evaluators']['section_fit']['ideal_minimum']==.90
    assert current['evaluators']['section_fit']['ideal_minimum']==.90
    assert current['evaluators']['section_fit']['ideal_maximum']==1
    assert 'dimension_sources' not in current
    assert current['editorial_scoring']['dimensions']['content_quality']['submetrics']['narrative_flow']==.15
    assert current['rubric_version']=='academic_poster_editorial_v4_model_scored'


@pytest.mark.parametrize('utilization,ideal',[(.8999,False),(.90,True),(.92,True),(.9499,True),(.95,True),(1,True),(1.006,False)])
def test_boundary_is_preserved_as_evidence_without_quality_scores(utilization,ideal):
    state=_state(height=30*utilization)
    state.update(editorial_version='poster_editorial_v1')
    state['styled_layout'][0]['planned_module_height']=30
    context=CriticContext(state,editorial_critic_config(load_critic_config()))
    measured=MeasurementEvaluator(SectionFitEvaluator()).evaluate(context)
    metric=state['section_fit_analysis']['sections']['results']
    assert metric['in_ideal_band'] is ideal
    assert state['section_fit_analysis']['ideal_band']==[.90,1]
    assert "scores" not in measured.to_dict() and measured.positive_patterns==[]
    assert state['critic_measurement_evidence']['section_fit']['metadata']['section_fit']['sections']['results']==metric
    assert 'submetrics' not in measured.metadata
