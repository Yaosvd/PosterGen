"""Post-render paper comparison; no pre-generation scientific approval or route judge."""
from copy import deepcopy

from src.critic.base import EvaluationResult, issue
from src.workflow.editorial_contract import paper_material, assert_editorial_ready
from src.workflow.editorial_requests import request, obj, STRING

CONTENT_KEYS=('information_layering','information_coverage','information_depth',
              'information_completeness','narrative_structure','narrative_conciseness')
SCORE={'type':'number','minimum':0,'maximum':100}
FINDING=obj({'module_id':STRING,'observation':STRING,'original_support':STRING,
             'severity':{'type':'string','enum':['critical','major','minor','warning']}})
CONTENT_SCHEMA=obj({'status':{'type':'string','enum':['supported','issues','uncertain']},
    'scientific_integrity':SCORE,'content_submetrics':obj({k:SCORE for k in CONTENT_KEYS}),
    'issues':{'type':'array','items':FINDING},'reason':STRING})


def editorial_critic_config(config):
    config=deepcopy(config)
    config.update(rubric_version='academic_poster_editorial_v2',critic_system_version='6.1.0')
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
            if name=='information_narrative' and not context.config['evaluators'].get(name,{}).get('semantic_enabled',True):
                return result(context,name,{},metadata={'semantic_model_completed':False})
            raw=content_evaluation(context)
            problems=[issue('EDITORIAL-FACTUAL-'+str(i),severity=r['severity'],scope='scientific_integrity',
                observation=r['observation'],location={'section_id':r['module_id']},
                evidence={'original_support':r['original_support']},required_outcome='Review against original paper')
                for i,r in enumerate(raw['issues'])] if name=='grounding' else []
            dimension='scientific_integrity' if name=='grounding' else 'content_quality'
            score=(raw['scientific_integrity'] if name=='grounding' else
                   round(sum(raw['content_submetrics'].values())/len(CONTENT_KEYS),2))
            return result(context,name,{dimension:score},problems,raw['status']=='supported',
                          {'factual_consistency_status':raw['status'],'reason':raw['reason'],
                           'submetrics':raw.get('content_submetrics',{})})
        if name=='content_adequacy':
            fit=state.get('section_fit_analysis') or {};duplicates=sparse=0;problems=[]
            for module in state['editorial_candidate']['modules']:
                texts=[' '.join(e['text'].casefold().split()) for e in module['entries']]
                duplicates+=len(texts)-len(set(texts))
                use=float((fit.get('sections') or {}).get(module['module_id'],{}).get('utilization',1.0))
                if use<float((fit.get('ideal_band') or [.95,1])[0]):
                    sparse+=1
                    problems.append(issue('EDITORIAL-CONTENT-UNDERFILLED-'+module['module_id'],
                        severity='major' if use<.9 else 'warning',scope='content_quality',
                        location={'section_id':module['module_id']},
                        observation='Measured module remains underfilled',evidence={'utilization':use},
                        required_outcome='Explain useful paper material or adjust legal space without filler'))
            return result(context,name,{'content_quality':max(0.0,100-25*duplicates-6*sparse)},problems,
                          metadata={'underfilled_section_count':sparse,'duplicate_claim_count':duplicates,
                                    'coverage_basis':'original_paper_comparison_not_evidence_counts'})
        raise ValueError('Unknown editorial evaluator')


class EditorialVisualEvaluator:
    name='visual'
    def evaluate(self,context):
        from src.critic.visual import VisualCriticEvaluator
        state=context.state
        finding=obj({'severity':{'type':'string','enum':['critical','major','minor','warning']},
            'scope':STRING,'location':obj({'zone_id':STRING,'section_id':STRING,'element_id':STRING}),
            'observation':STRING,'required_outcome':STRING,
            'allowed_operations':{'type':'array','items':STRING},'forbidden_operations':{'type':'array','items':STRING}})
        schema=obj({'scores':obj({k:SCORE for k in VisualCriticEvaluator._DIMENSIONS}),
            'submetrics':obj({k:SCORE for k in VisualCriticEvaluator._SUBMETRICS}),
            'issues':{'type':'array','items':finding},
            'positive_patterns':{'type':'array','items':obj({'scope':STRING,'observation':STRING})},'reason':STRING})
        visual=VisualCriticEvaluator()
        raw=request(state,'editorial_visual_critic',{'final_poster':state['editorial_candidate'],
            'actual_geometry':state['layout_spec'],'poster_inches':[state['poster_width'],state['poster_height']],
            'rubric_instructions':visual.prompt},
            schema,directory='editorial/final_visual',images=[state['current_candidate']['png_path']],correction=False)
        problems=[]
        for i,finding in enumerate(raw['issues']):
            location,evidence=visual._validated_location(finding['location'],state)
            problems.append(issue('EDITORIAL-VISUAL-'+str(i),severity=finding['severity'],scope=finding['scope'],
                observation=finding['observation'],location=location,evidence=evidence,
                required_outcome=finding['required_outcome'],allowed_operations=finding['allowed_operations'],
                forbidden_operations=finding['forbidden_operations']))
        verdict=result(context,'visual',raw['scores'],problems,
                       not any(p['severity']=='critical' for p in problems),
                       {'submetrics':raw['submetrics'],'reason':raw['reason'],'model_evaluation_completed':True})
        verdict.positive_patterns=raw['positive_patterns']
        return verdict


def make_critic(config):
    from src.critic.engine import PosterCritic
    from src.critic.evaluators import RenderArtifactEvaluator,GeometryEvaluator,TypographyEvaluator,ColumnBalanceEvaluator
    from src.critic.section_fit import SectionFitEvaluator
    from src.critic.layout_family import LayoutFamilyCriticEvaluator
    from src.critic.quality import ColorQualityEvaluator,VisualAssetEvaluator
    evaluators=[RenderArtifactEvaluator(),GeometryEvaluator(),TypographyEvaluator(),ColorQualityEvaluator(),VisualAssetEvaluator(),
                ColumnBalanceEvaluator(),SectionFitEvaluator(),LayoutFamilyCriticEvaluator()]
    evaluators += [EditorialEvaluator(name) for name in ('grounding','information_narrative','content_adequacy')]
    evaluators.append(EditorialVisualEvaluator())
    return PosterCritic(config,evaluators=evaluators)
