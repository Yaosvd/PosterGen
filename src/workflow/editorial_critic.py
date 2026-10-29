"""Post-render paper comparison; no pre-generation scientific approval or route judge."""
from copy import deepcopy

from src.critic.base import EvaluationResult, issue
from src.workflow.editorial_contract import paper_material, assert_editorial_ready
from src.workflow.editorial_requests import request, obj, STRING

SCORE={'type':'number','minimum':0,'maximum':100}
FINDING=obj({'module_id':STRING,'observation':STRING,'original_support':STRING,
             'severity':{'type':'string','enum':['critical','major','minor','warning']}})
CONTENT_SCHEMA=obj({'status':{'type':'string','enum':['supported','issues','uncertain']},
    'scientific_integrity':SCORE,'content_quality':SCORE,
    'issues':{'type':'array','items':FINDING},'reason':STRING})


def editorial_critic_config(config):
    config=deepcopy(config)
    config.update(rubric_version='academic_poster_editorial_v1',critic_system_version='6.0.0')
    # The retired family-role/reading heuristic cannot certify visual hierarchy.
    # Preserve top-level weights; give its old contribution to the actual-image judge.
    config['dimension_sources']['visual_hierarchy'] = {'typography': .20, 'visual': .80}
    return config


def result(context,name,scores,issues=(),passed=True,metadata=None):
    return EvaluationResult(evaluator=name,version='editorial_v1',
        hard_gate=context.config['evaluators'].get(name,{}).get('hard_gate',False),
        passed=passed,scores=scores,issues=list(issues),metadata=metadata or {})


def content_evaluation(context):
    state=context.state
    assert_editorial_ready(state,compiled=True)
    if state.get('_editorial_content_error'):
        raise ValueError(state['_editorial_content_error'])
    if '_editorial_content_evaluation' not in state:
        try:
            def validate(value):
                from src.workflow.editorial_contract import EditorialOutputError
                ids={m['module_id'] for m in state['editorial_candidate']['modules']}
                if any(r['module_id'] and r['module_id'] not in ids for r in value['issues']):
                    raise EditorialOutputError('Critic finding names an unknown module')
                if value['status']=='supported' and value['issues']:
                    raise EditorialOutputError('Critic support status contradicts reported issues')
            from src.layout.editorial import presentation_lines
            visible = {'paper_metadata': state['narrative_content'].get('meta', {}),
                       'modules': [{'module_id': section['section_id'], 'title': section['section_title'],
                                    'body_lines': presentation_lines(section)} for section in
                                   state['optimized_story_board']['spatial_content_plan']['sections']]}
            state['_editorial_content_evaluation']=request(state,'editorial_content_critic',
                {'paper':paper_material(state,original=True),'final_poster':state['editorial_candidate'],
                 'renderer_visible_text':visible, 'actual_geometry':state['layout_spec'],
                 'content_status':'not_preverified'},CONTENT_SCHEMA,
                directory='editorial/final_content',correction=False,validator=validate)
        except Exception as exc:
            state['editorial_factual_status']='unavailable'
            state['_editorial_content_error']=type(exc).__name__+': '+str(exc)
            raise
    raw=state['_editorial_content_evaluation']
    state['editorial_factual_status']=raw['status']
    return raw


class EditorialEvaluator:
    def __init__(self,name):self.name=name

    def evaluate(self,context):
        state=context.state;name=self.name
        if name in {'grounding','information_narrative'}:
            raw=content_evaluation(context)
            problems=[issue('EDITORIAL-FACTUAL-'+str(i),severity=r['severity'],scope='scientific_integrity',
                observation=r['observation'],location={'section_id':r['module_id']},
                evidence={'original_support':r['original_support']},required_outcome='Review against original paper')
                for i,r in enumerate(raw['issues'])] if name=='grounding' else []
            dimension='scientific_integrity' if name=='grounding' else 'content_quality'
            return result(context,name,{dimension:raw[dimension]},problems,raw['status']=='supported',
                          {'factual_consistency_status':raw['status'],'reason':raw['reason']})
        fit=state['editorial_fit'];modules=fit['modules']
        if name=='section_fit':
            score=max(0,100-sum(max(0,.9-m['utilization'])*100 for m in modules)/max(1,len(modules)))
            problems=[issue('EDITORIAL-UNDERFILLED-'+m['module_id'],severity='major',scope='content_quality',
                location={'section_id':m['module_id']},observation='Module remains below 90% of its independent height allocation',
                evidence=m,required_outcome='Add useful explanation or adjust legal space') for m in modules if m['utilization']<.9]
            return result(context,name,{'layout_integrity':score,'visual_balance':score},problems,
                          fit['passed'] and fit['all_modules_90_percent'],{'section_fit':fit})
        if name=='column_balance':
            values=list(fit['zone_utilization'].values())
            score=max(0,100-100*(max(values)-min(values))) if values else 0
            return result(context,name,{'layout_integrity':score,'visual_balance':score},passed=fit['passed'])
        if name=='content_adequacy':
            texts=[e['text'].strip().casefold() for m in state['editorial_candidate']['modules'] for e in m['entries']]
            score=max(0,100-20*(len(texts)-len(set(texts))))
            return result(context,name,{'content_quality':score})
        if name=='layout_family':
            from src.layout.families import LayoutFamilyRegistry,valid_family_topology
            spec=state['layout_spec'];family=LayoutFamilyRegistry().get(spec['family_id'])
            valid=valid_family_topology(family,spec['zones'])
            return result(context,name,{'layout_integrity':100.0 if valid else 0.0},passed=valid)
        raise ValueError('Unknown editorial evaluator')


class EditorialVisualEvaluator:
    name='visual'
    def evaluate(self,context):
        from src.critic.visual import VisualCriticEvaluator
        state=context.state
        schema=obj({'scores':obj({k:SCORE for k in VisualCriticEvaluator._DIMENSIONS}),
            'submetrics':obj({k:SCORE for k in VisualCriticEvaluator._SUBMETRICS}),
            'issues':{'type':'array','items':FINDING},'reason':STRING})
        raw=request(state,'editorial_visual_critic',{'final_poster':state['editorial_candidate'],
            'actual_geometry':state['layout_spec'],'poster_inches':[state['poster_width'],state['poster_height']]},
            schema,directory='editorial/final_visual',images=[state['current_candidate']['png_path']],correction=False)
        problems=[issue('EDITORIAL-VISUAL-'+str(i),severity=r['severity'],scope='visual',
            observation=r['observation'],location={'section_id':r['module_id']},required_outcome='Review final poster presentation')
            for i,r in enumerate(raw['issues'])]
        return result(context,'visual',raw['scores'],problems,not problems,{'submetrics':raw['submetrics'],'reason':raw['reason']})


def make_critic(config):
    from src.critic.engine import PosterCritic
    from src.critic.evaluators import RenderArtifactEvaluator,GeometryEvaluator,TypographyEvaluator
    from src.critic.quality import ColorQualityEvaluator,VisualAssetEvaluator
    evaluators=[RenderArtifactEvaluator(),GeometryEvaluator(),TypographyEvaluator(),ColorQualityEvaluator(),VisualAssetEvaluator()]
    evaluators += [EditorialEvaluator(name) for name in ('grounding','information_narrative','content_adequacy',
                                                       'column_balance','section_fit','layout_family')]
    evaluators.append(EditorialVisualEvaluator())
    return PosterCritic(config,evaluators=evaluators)
