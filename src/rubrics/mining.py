"""Sealed-round observation extraction, separate clustering, and rule publication."""
from collections import Counter
from pathlib import Path
from copy import deepcopy
import re
import json

from jsonschema import Draft202012Validator

from utils.persistence import digest, file_hash, read_json
from src.workflow.poster_grouping import complete_score, poster_group
from src.critic.scoring import validate_policy_snapshot
from src.rubrics.library import LibraryStore, STAGES, validate_rule
from src.rubrics.providers import ExternalModels, configuration, validate_configuration
from src.rubrics.vectorization import clusters, fit_texts, runtime_identity
from src.rubrics.storage import IntegrityError, WaitingForConfiguration, BudgetExceeded, immutable, read, write, lock
from src.rubrics.refinement import obj, TEXT

OBSERVATIONS = obj({'observations':{'type':'array','maxItems':30,'items':obj({
    'dimension':TEXT,'observation':TEXT,'evidence':TEXT,'generalizable_lesson':TEXT})}})
RULE_CONTENT = obj({'dimension':TEXT,'type':{'enum':['preference','rejection']},
    'requirement':TEXT,'applicability':TEXT,'criterion':TEXT,'revision_guidance':TEXT,
    'applicable_stages':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':sorted(STAGES)}},
    'evidence_refs':{'type':'array','minItems':1,'uniqueItems':True,'items':TEXT}})
RULES = obj({'rules':{'type':'array','minItems':1,'maxItems':1,'items':RULE_CONTENT}})
DECISION = obj({'decision':{'enum':['novel','duplicate','conflict','uncertain']},'reason':TEXT})


def verified_samples(seal):
    if seal.get('schema_version')!=2 or seal.get('route')!='rubric-refine-score':
        raise ValueError('Only a sealed refinement round may update Rubrics')
    policy = validate_policy_snapshot(seal.get('scoring_policy'))
    if seal.get('scoring_policy_digest') != policy['digest']:
        raise IntegrityError('Sealed evaluator policy digest changed')
    samples = seal.get('samples',[])
    counts = Counter(s['paper_sha256'] for s in samples)
    if len(samples)!=400 or len(counts)!=20 or set(counts.values())!={20}:
        raise ValueError('A round must contain exactly 20 papers × 20 complete-scored samples')
    if len({s['poster_id'] for s in samples})!=400 or set(counts)!=set(seal['paper_hashes']):
        raise ValueError('Duplicate samples or changed round paper manifest')
    for sample in samples:
        root = Path(sample['bundle_path']).resolve()
        for relative, expected in sample['files'].items():
            path = (root/relative).resolve()
            if not path.is_relative_to(root) or file_hash(path)!=expected:
                raise IntegrityError('Sealed poster artifact changed')
        report = read_json(root/'evaluation.json')
        provenance = read_json(root/'provenance.json')
        if (not complete_score(report) or report.get('scoring_policy') != policy or
                poster_group(provenance, report) not in {'high_score', 'low_score'} or
                provenance.get('scoring_policy_digest') != policy['digest'] or
                provenance.get('status')!='scored' or
                provenance.get('score')!=report.get('overall_score') or provenance.get('poster_id')!=sample['poster_id'] or
                provenance.get('sample_mode')!='rubric-refine-score' or
                provenance.get('generation_rubrics')!=seal['library_version'] or
                (provenance.get('round_identity') or {}).get('round_id')!=seal['round_id'] or
                (provenance.get('round_identity') or {}).get('manifest_digest')!=seal['manifest_digest']):
            raise IntegrityError('Sample scoring, route, rules or round membership changed')
        selection=read(root/'refinement/selection.json')
        if selection.get('variant') not in {'P0','P1'} or selection.get('rubrics')!=seal['library_version']:
            raise IntegrityError('Invalid final selection')
        for kind in ('pptx','png'):
            if file_hash(root/('poster.'+kind))!=selection['artifact_hashes'][kind]:
                raise IntegrityError('Mining input is not the frozen final selection')
        if provenance.get('paper_id') and provenance['paper_id'] != sample['paper_sha256']:
            # Existing paper IDs may be prefixed; the input hash is checked by the coordinator.
            if provenance['paper_id'] != 'pdf_'+sample['paper_sha256']:
                raise IntegrityError('Sample paper attribution changed')
        yield sample, root, report


def _text(rule):
    return '\n'.join(rule[k] for k in ('type','dimension','requirement','applicability','criterion','revision_guidance')) + \
        '\n' + '\n'.join(sorted(rule['applicable_stages']))


def _normal(text):
    # Case can distinguish scientific symbols; let the semantic reviewer decide.
    return re.sub(r'\s+',' ',text.strip())


def _rule_identity(rule):
    return tuple(_normal(rule[k]) for k in ('type','dimension','requirement','applicability',
        'criterion','revision_guidance')) + (tuple(sorted(rule['applicable_stages'])),)


def reconcile(candidate, existing, models, root, mining):
    """Review every existing rule, including zero lexical similarity and opposite polarity.

    TF-IDF only orders comparisons. All chunks must be novel before acceptance;
    conflicts/uncertainty take priority over a duplicate found in another chunk.
    """
    if not existing:
        return {'decision':'novel','reviews':[]}
    models.check(('reconciler',))
    chunks, current = [], []
    for rule in existing:
        payload = {'candidate':candidate,'existing':current+[rule]}
        if current and (len(current) >= mining['reconcile_batch_size'] or
                        len(json.dumps(payload,ensure_ascii=False)) > mining['reconcile_max_chars']):
            chunks.append(current)
            current = []
        current.append(rule)
        if len(json.dumps({'candidate':candidate,'existing':current},ensure_ascii=False)) > mining['reconcile_max_chars']:
            raise ValueError('A single reconciliation pair exceeds the input limit; refusing to truncate rules')
    if current:
        chunks.append(current)
    reviews = []
    for index, chunk in enumerate(chunks):
        decision = models.generate('reconciler',{'candidate':candidate,'existing':chunk},DECISION,
                                   Path(root)/str(index))
        Draft202012Validator(DECISION).validate(decision)
        reviews.append({'existing_ids':[r['id'] for r in chunk],**decision})
    outcome = next((d for d in ('conflict','uncertain','duplicate')
                    if any(r['decision']==d for r in reviews)), 'novel')
    return {'decision':outcome,'reviews':reviews}


class BudgetedModels:
    """Durable conservative reservations, including uncertain/failed API sends."""
    def __init__(self,models,root,limit):
        self.models,self.root,self.limit=models,Path(root),limit
    def check(self,*args,**kwargs):return self.models.check(*args,**kwargs)
    def reserve(self,path):
        key=str(Path(path).relative_to(self.root))
        ledger=self.root/'budget.json'
        with lock(self.root/'.budget.lock'):
            value=read(ledger) if ledger.exists() else {'limit':self.limit,'requests':[]}
            if value['limit']!=self.limit:raise IntegrityError('Postprocess budget changed')
            if key in value['requests']:return
            if self.limit is not None and len(value['requests'])>=self.limit:
                raise BudgetExceeded('POSTPROCESS_BUDGET_EXHAUSTED')
            value['requests'].append(key);write(ledger,value)
    def generate(self,role,payload,schema,root,**kwargs):
        self.reserve(root);return self.models.generate(role,payload,schema,root,**kwargs)


def process(seal_path, library_root, *, config=None, models=None):
    seal_path = Path(seal_path)
    seal = read(seal_path)
    config = deepcopy(config or configuration())
    if 'high_score_threshold' in config.get('mining', {}):
        raise ValueError('Cannot override a sealed evaluator grouping threshold through mining/API configuration')
    validate_configuration(config)
    models = models or ExternalModels(config)
    # Verify the sealed G policy before any external request or configuration preflight.
    samples = list(verified_samples(seal))
    policy = validate_policy_snapshot(seal['scoring_policy'])
    store = LibraryStore(library_root)
    parent = store.version(seal['library_version'])
    identity = {'seal':digest(seal),'scoring_policy_digest':policy['digest'],'models':config['external_models'],'mining':config['mining'],
                'local_processing':runtime_identity(),
                'implementation':{name:file_hash(Path(__file__).with_name(name+'.py'))
                                  for name in ('mining','providers','vectorization')},
                'limits':config.get('limits',{}),
                'prompts':{role:file_hash(Path(__file__).resolve().parents[2]/'config/prompts'/('rubrics_'+role+'.txt'))
                           for role in ('extractor','summarizer','reconciler')}}
    root = seal_path.parent/'postprocess'/digest(identity)
    with lock(root/'.job.lock',blocking=False):
        immutable(root/'identity.json',identity)
        if (root/'result.json').exists():
            return read(root/'result.json')
        if len(parent['rules']) >= config['mining']['max_rules']:
            result = {'status':'RULE_CAP','version':parent['version'],'added':0,'job':str(root),'deferred':[]}
            immutable(root/'result.json',result)
            return result
        models.check()
        models=BudgetedModels(models,root,config.get('limits',{}).get('max_postprocess_requests'))
        observations = []
        for sample,bundle,report in samples:
            group = 'preference' if report['overall_score']>=policy['high_score_threshold'] else 'rejection'
            paper = read(bundle/'refinement/paper.json')
            diagnostics = {p.stem:read_json(p) for p in (bundle/'diagnostics').glob('*.json')
                           if p.stem in {'render_fit_report','layout_preflight_report','critic_measurement_evidence','editorial_candidate'}}
            value = models.generate('extractor',{'group':group,'paper':paper,'evaluation':report,
                'diagnostics':diagnostics,'poster_id':sample['poster_id'],
                'instruction':'Extract grounded strengths' if group=='preference' else 'Extract grounded weaknesses'},
                OBSERVATIONS,root/'extract'/sample['poster_id'],images=(bundle/'poster.png',))
            Draft202012Validator(OBSERVATIONS).validate(value)
            for index,observation in enumerate(value['observations']):
                observations.append({**observation,'id':sample['poster_id']+':'+str(index),
                    'type':group,'poster_id':sample['poster_id'],'paper_sha256':sample['paper_sha256']})
        immutable(root/'observations.json',observations)
        candidates = []
        mining = config['mining']
        for group in ('preference','rejection'):
            selected = [o for o in observations if o['type']==group]
            vectors = fit_texts([o['dimension']+'\n'+o['observation']+'\n'+o['generalizable_lesson'] for o in selected],
                [o['id'] for o in selected],mining['tfidf'],root/'tfidf'/(group+'.json'))
            groups = clusters(vectors,mining['clusters'],mining['random_seed'])
            immutable(root/(group+'_clusters.json'),{'observations':[o['id'] for o in selected],
                'features_receipt':'tfidf/'+group+'.json','clusters':groups})
            for i,indices in enumerate(groups):
                members = [selected[j] for j in indices]
                value = models.generate('summarizer',{'type':group,'observations':members,
                    'poster_support':len({o['poster_id'] for o in members}),
                    'paper_support':len({o['paper_sha256'] for o in members})},RULES,root/'summary'/group/str(i))
                Draft202012Validator(RULES).validate(value)
                valid_refs = {o['id'] for o in members}
                for rule in value['rules']:
                    if rule['type']!=group or not set(rule['evidence_refs'])<=valid_refs:
                        raise ValueError('Candidate rule has unsupported polarity or evidence')
                    candidate = {'id':'r_'+digest(rule)[:24],'revision':1,**rule}
                    validate_rule(candidate)
                    candidates.append(candidate)
        immutable(root/'candidates.json',candidates)
        accepted, pending, duplicates = [], [], []
        comparison = list(parent['rules'])
        all_rules = comparison+candidates
        matrix = fit_texts([_text(r) for r in all_rules],
            [str(i)+':'+r['id'] for i,r in enumerate(all_rules)],mining['tfidf'],root/'tfidf'/'rules.json')
        indices = list(range(len(comparison)))
        for i,candidate in enumerate(candidates,start=len(parent['rules'])):
            exact = [r for r in comparison if _rule_identity(r) == _rule_identity(candidate)]
            if exact:
                duplicates.append({'id':candidate['id'],'reason':'exact','matches':[r['id'] for r in exact]})
                continue
            similarities = (matrix[indices] @ matrix[i].T).toarray().ravel().tolist()
            ranking = sorted(range(len(comparison)),key=lambda j:(-similarities[j],j))
            matches = [comparison[j] for j in ranking]
            immutable(root/'retrieval'/(str(i)+'.json'),{
                'candidate':candidate['id'],'review_scope':'all_existing_rules',
                'ranking':[{'id':comparison[j]['id'],'cosine':similarities[j]} for j in ranking]})
            try:
                decision = reconcile(candidate,matches,models,root/'reconcile'/str(i),mining)
            except WaitingForConfiguration:
                pending.append({'candidate':candidate,'matches':matches,'reason':'reconciler_unconfigured'})
                continue
            if decision['decision']=='duplicate':
                duplicates.append({'id':candidate['id'],**decision})
                continue
            if decision['decision']!='novel':
                pending.append({'candidate':candidate,'matches':matches,**decision})
                continue
            if len(comparison)>=mining['max_rules']:
                pending.append({'candidate':candidate,'reason':'rule_cap'})
                continue
            comparison.append(candidate); indices.append(i); accepted.append(candidate)
        review = {'accepted':accepted,'pending':pending,'duplicates':duplicates}
        write(root/'review.json',review)
        if pending and not all(p.get('reason')=='rule_cap' for p in pending):
            # No partial publication can masquerade as convergence. Reconfigure and rerun
            # under a new postprocess identity, or explicitly resolve conflicts in a future version.
            return {'status':'WAITING_REVIEW','job':str(root),'parent_version':parent['version'],**review}
        if accepted:
            published = store.publish(comparison,parent_version=parent['version'],source_batch_digest=digest(seal))
            result = {'status':'PUBLISHED','version':published['version'],'added':len(accepted),'job':str(root)}
        else:
            result = {'status':'NO_NEW_RULES','version':parent['version'],'added':0,'job':str(root)}
        if pending or len(comparison) >= mining['max_rules']:
            result.update(status='RULE_CAP',deferred=pending)
        immutable(root/'result.json',result)
        return result
