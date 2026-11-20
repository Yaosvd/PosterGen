"""Sealed-round mining produces reviewed candidates, never a published library."""
from collections import Counter
from pathlib import Path
from copy import deepcopy
import json

from jsonschema import Draft202012Validator

from utils.persistence import digest, file_hash, read_json
from src.workflow.poster_grouping import complete_score, poster_group
from src.critic.scoring import validate_policy_snapshot
from src.rubrics.library import LibraryStore, SCHEMA_VERSION
from src.rubrics.providers import ExternalModels, configuration, validate_configuration
from src.rubrics.vectorization import clusters, fit_texts, runtime_identity
from src.rubrics.storage import IntegrityError, WaitingForConfiguration, BudgetExceeded, immutable, read, write, lock
from src.rubrics.refinement import obj, TEXT
from src.rubrics.constraints import check_engineering
from src.rubrics.quality import (QUALITY_FIELDS, RULES, RULE_CONTENT, RECONCILIATION,
                                aggregate_decision, quality_view, validate_candidate, validate_semantic)
from src.rubrics.poster_evidence import extractor_evidence

OBSERVATIONS = obj({'observations':{'type':'array','maxItems':30,'items':obj({
    'dimension':TEXT,'observation':TEXT,'evidence':TEXT,'generalizable_lesson':TEXT})}})
# V1 packages replay the four-way semantic vocabulary and their frozen engineering decision.
LEGACY_COMPARISON = obj({'existing_id': TEXT,
                         'decision': {'enum': ['novel', 'duplicate', 'conflict', 'uncertain']}, 'reason': TEXT})


def verified_samples(seal):
    collection = seal.get('schema_version') == 3 and seal.get('kind') == 'scored_collection'
    if (seal.get('schema_version') != 2 and not collection) or seal.get('route') != 'rubric-refine-score':
        raise ValueError('Only a sealed refinement round may update Rubrics')
    policy = validate_policy_snapshot(seal.get('scoring_policy'))
    if seal.get('scoring_policy_digest') != policy['digest']:
        raise IntegrityError('Sealed evaluator policy digest changed')
    samples = seal.get('samples',[])
    counts = Counter(s['paper_sha256'] for s in samples)
    if collection:
        if not samples or len(samples) != seal['sample_count']:
            raise IntegrityError('Collection count differs from the sealed selection')
    elif len(samples)!=400 or len(counts)!=20 or set(counts.values())!={20}:
        raise ValueError('A round must contain exactly 20 papers × 20 complete-scored samples')
    if len({s['poster_id'] for s in samples})!=len(samples) or set(counts)!=set(seal['paper_hashes']):
        raise ValueError('Duplicate samples or changed round paper manifest')
    for sample in samples:
        root = Path(sample['bundle_path']).resolve()
        if collection:
            rid = sample['round_id']
            if rid not in seal['sources'] or {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()} != set(sample['files']):
                raise IntegrityError('Collection source or file inventory changed')
            manifest_digest = seal['sources'][rid]
        else:
            rid, manifest_digest = seal['round_id'], seal['manifest_digest']
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
                (provenance.get('round_identity') or {}).get('round_id')!=rid or
                (provenance.get('round_identity') or {}).get('manifest_digest')!=manifest_digest):
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
    return '\n'.join(rule[k] for k in QUALITY_FIELDS)


def review_payload(candidate, existing):
    return {'candidate': quality_view(candidate), 'existing': [quality_view(r) for r in existing],
            'review_instructions': 'Compare every supplied ID, including opposite rule types. Compare quality '
            'requirements, applicability to the poster and observable criteria. Use partial_overlap for '
            'shared requirements when either rule also contains distinct content. Explain which parts overlap '
            'and which differ. Differences in historical workflow terminology do not establish novelty.'}


def reconcile(candidate, existing, models, root, mining):
    """TF-IDF orders comparisons; every reference still receives an individual decision."""
    if not existing:
        return {'decision': 'novel', 'reviews': [validate_semantic(candidate, [], {'comparisons': []})]}
    models.check(('reconciler',))
    chunks, current = [], []
    for rule in existing:
        payload = review_payload(candidate, current + [rule])
        if current and (len(current) >= mining['reconcile_batch_size'] or
                        len(json.dumps(payload, ensure_ascii=False)) > mining['reconcile_max_chars']):
            chunks.append(current)
            current = []
        current.append(rule)
        if len(json.dumps(review_payload(candidate, current), ensure_ascii=False)) > mining['reconcile_max_chars']:
            raise ValueError('A single reconciliation pair exceeds the input limit; refusing to truncate rules')
    chunks.append(current)
    reviews = []
    for index, chunk in enumerate(chunks):
        response = models.generate('reconciler', review_payload(candidate, chunk),
                                   RECONCILIATION, Path(root)/str(index))
        reviews.append(validate_semantic(candidate, chunk, response))
    return {'decision': aggregate_decision(r['decision'] for r in reviews), 'reviews': reviews}


def validate_comparison(candidate, existing, response, contract):
    """Require full ID coverage; aggregate conflicts before duplicate decisions."""
    # check_engineering validates the nested review against its frozen contract.
    envelope = obj({'comparisons': {'type':'array','items':LEGACY_COMPARISON},
                    'engineering_review': {'type': 'object'}})
    Draft202012Validator(envelope).validate(response)
    ids = [item['existing_id'] for item in response['comparisons']]
    expected = [r['id'] for r in existing]
    if len(ids) != len(set(ids)) or len(expected) != len(set(expected)) or set(ids) != set(expected):
        raise ValueError('Semantic review must cover every supplied rule exactly once')
    engineering = check_engineering(candidate, response['engineering_review'], contract)
    decisions = [item['decision'] for item in response['comparisons']]
    if engineering['status'] != 'compliant':
        decisions.append(engineering['status'])
    outcome = next((d for d in ('conflict','uncertain','duplicate') if d in decisions), 'novel')
    return {'existing_ids':expected,'decision':outcome,'comparisons':response['comparisons'],
            'engineering':engineering}


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
    if parent['schema_version'] != SCHEMA_VERSION:
        raise IntegrityError('Legacy sealed rounds require their original mining implementation; start a new round with the current rule schema')
    identity = {'seal':digest(seal),'scoring_policy_digest':policy['digest'],'models':config['external_models'],'mining':config['mining'],
                'publication_policy':'human_review_v2', 'mining_policy':'poster_quality_v2',
                'local_processing':runtime_identity(),
                'implementation':{name:file_hash(Path(__file__).with_name(name+'.py'))
                                  for name in ('mining','providers','vectorization','quality','poster_evidence','candidates')},
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
            variant = read(bundle/'refinement/selection.json')['variant']
            evidence = extractor_evidence(bundle, report, variant)
            value = models.generate('extractor',{'group': group, **evidence, 'poster_id': sample['poster_id'],
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
                    'generation_instruction':'Summarize reusable poster-quality requirements, content applicability and observable criteria. '
                        'Make any context-specific applicability explicit in the rule itself.',
                    'poster_support':len({o['poster_id'] for o in members}),
                    'paper_support':len({o['paper_sha256'] for o in members})},RULES,root/'summary'/group/str(i))
                Draft202012Validator(RULES).validate(value)
                valid_refs = {o['id'] for o in members}
                for rule in value['rules']:
                    if rule['type']!=group or not set(rule['evidence_refs'])<=valid_refs:
                        raise ValueError('Candidate rule has unsupported polarity or evidence')
                    candidate = {'id':'r_'+digest(rule)[:24],'revision':1,**rule}
                    validate_candidate(candidate)
                    candidates.append(candidate)
        immutable(root/'candidates.json',candidates)
        assessments, pending = [], []
        all_rules = parent['rules'] + candidates
        matrix = fit_texts([_text(r) for r in all_rules],
            [str(i)+':'+r['id'] for i,r in enumerate(all_rules)],mining['tfidf'],root/'tfidf'/'rules.json')
        for i,candidate in enumerate(candidates,start=len(parent['rules'])):
            similarities = (matrix[:i] @ matrix[i].T).toarray().ravel().tolist()
            ranking = sorted(range(i),key=lambda j:(-similarities[j],j))
            matches = [all_rules[j] for j in ranking]
            immutable(root/'retrieval'/(str(i)+'.json'),{
                'candidate':candidate['id'],'review_scope':'all_existing_rules',
                'ranking':[{'id':all_rules[j]['id'],'cosine':similarities[j]} for j in ranking]})
            try:
                decision = reconcile(candidate,matches,models,root/'reconcile'/str(i),mining)
            except WaitingForConfiguration:
                pending.append({'candidate_id':candidate['id'],'reason':'reconciler_unconfigured'})
                continue
            assessments.append({'candidate_id':candidate['id'],'rule_digest':digest(candidate),**decision})
        recommendations = Counter(a['decision'] for a in assessments)
        review = {'recommendation_counts':dict(recommendations),'pending':pending,'assessments':assessments}
        write(root/'review.json',review)
        if pending:
            return {'status':'WAITING_REVIEW','job':str(root),'parent_version':parent['version'],**review}
        from src.rubrics.candidates import prepare
        package = prepare(library_root, parent, candidates, assessments, observations,
                          identity, root, mining['max_rules'], sources=[s for s,_,_ in samples])
        result = {'status':'AWAITING_HUMAN_REVIEW' if candidates else 'NO_NEW_RULES',
                  'version':parent['version'],'added':0,'candidate_count':len(candidates),
                  'job':str(root),'review_package':str(package),'parent_version':parent['version'],
                  'remaining_capacity':mining['max_rules']-len(parent['rules']),**review}
        immutable(root/'result.json',result)
        return result
