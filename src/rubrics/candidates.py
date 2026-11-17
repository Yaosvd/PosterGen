"""Immutable review packages and a separate, explicitly human publication step."""
from copy import deepcopy
from pathlib import Path
import json

from src.rubrics.constraints import snapshot
from src.rubrics.library import LibraryStore, SCHEMA_VERSION as LIBRARY_SCHEMA_VERSION, validate_rule
from src.rubrics.storage import IntegrityError, immutable, lock, read, text_file
from utils.persistence import digest, file_hash, read_json

SCHEMA_VERSION = 1


def prepare(library_root, parent, candidates, assessments, observations, contract, identity, job, max_rules, *, sources=()):
    if parent['schema_version'] != LIBRARY_SCHEMA_VERSION or contract != snapshot():
        raise IntegrityError('New candidate packages require the current library schema and engineering contract')
    payload = {'schema_version':SCHEMA_VERSION,'status':'awaiting_human_review',
               'parent_version':parent['version'],'source_batch_digest':identity['seal'],
               'engineering_contract':deepcopy(contract),'job_identity':deepcopy(identity),
               'job_path':str(Path(job).resolve()),'max_rules':max_rules,
               'candidates':deepcopy(candidates),'assessments':deepcopy(assessments),
               'observations':deepcopy(observations),
               'sources':[{**deepcopy(s), 'bundle_path':str(Path(s['bundle_path']).resolve())} for s in sources],
               'eligible_ids':[a['candidate_id'] for a in assessments if a['decision']=='novel']}
    review_id = digest(payload)
    root = Path(library_root)/'candidates'/review_id
    immutable(root/'package.json',payload)
    # Validation also proves references, pair coverage and local action checks before handoff.
    load(root)
    decision = {'schema_version':1,'review_id':review_id,'parent_version':parent['version'],
                'decision':'pending','approved_ids':[],'reviewer':'','comment':''}
    template = root/'decision.template.json'
    if not template.exists():
        text_file(template,json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
    text_file(root/'review.md',render(root, payload))
    return root


def load(root, *, current_contract=False):
    from src.rubrics.mining import validate_comparison
    root = Path(root).resolve()
    if root.parent.name != 'candidates':
        raise IntegrityError('Review package must be inside the unified library candidates directory')
    value = read(root/'package.json')
    if value.get('schema_version') != SCHEMA_VERSION or value.get('status') != 'awaiting_human_review' or digest(value) != root.name:
        raise IntegrityError('Review package identity or schema changed')
    if current_contract and value['engineering_contract'] != snapshot():
        raise IntegrityError('Engineering contract changed; candidates require a new review')
    parent = LibraryStore(root.parent.parent).version(value['parent_version'])
    if current_contract and parent['schema_version'] != LIBRARY_SCHEMA_VERSION:
        raise IntegrityError('Legacy candidate packages are read-only; a current-schema parent requires new review')
    if value['job_identity'].get('publication_policy') != 'human_review_v1' or value['job_identity'].get('engineering_contract') != value['engineering_contract']:
        raise IntegrityError('Package is not bound to a human-review mining job')
    if value['source_batch_digest'] != value['job_identity']['seal']:
        raise IntegrityError('Candidate source batch changed')
    if type(value['max_rules']) is not int or value['max_rules'] < len(parent['rules']):
        raise IntegrityError('Invalid candidate library cap')
    candidates = value['candidates']
    for rule in candidates:
        validate_rule(rule, schema_version=parent['schema_version'])
    ids = [r['id'] for r in candidates]
    if len(ids) != len(set(ids)) or set(ids) & {r['id'] for r in parent['rules']}:
        raise IntegrityError('Candidate rule IDs must be unique and distinct from the parent')
    observations = {o['id']:o for o in value['observations']}
    if len(observations) != len(value['observations']):
        raise IntegrityError('Duplicate evidence IDs')
    sources = {s['poster_id']:s for s in value['sources']}
    if len(sources) != len(value['sources']):
        raise IntegrityError('Duplicate source poster IDs')
    for observation in observations.values():
        if 'poster_id' in observation:
            source = sources.get(observation['poster_id'])
            if not source or source['paper_sha256'] != observation['paper_sha256'] or not source['files']:
                raise IntegrityError('Observation is missing its sealed source evidence')
    assessments = value['assessments']
    if [a['candidate_id'] for a in assessments] != ids:
        raise IntegrityError('Every candidate requires one complete ordered assessment')
    comparison = list(parent['rules'])
    eligible = []
    for rule, assessment in zip(candidates, assessments):
        if assessment['rule_digest'] != digest(rule):
            raise IntegrityError('Candidate changed after semantic review')
        if not rule['evidence_refs'] or not set(rule['evidence_refs']) <= set(observations):
            raise IntegrityError('Candidate evidence references are missing')
        if any(observations[r]['type'] != rule['type'] for r in rule['evidence_refs']):
            raise IntegrityError('Candidate evidence polarity changed')
        by_id = {r['id']:r for r in comparison}
        covered = []
        outcomes = []
        if not assessment['reviews']:
            raise IntegrityError('Candidate has no engineering/semantic review')
        for review in assessment['reviews']:
            covered.extend(review['existing_ids'])
            if not set(review['existing_ids']) <= set(by_id):
                raise IntegrityError('Semantic review referenced an unknown rule')
            response = {'comparisons':review['comparisons'], 'engineering_review':review['engineering']['declared']}
            checked = validate_comparison(rule,[by_id[i] for i in review['existing_ids']],response,value['engineering_contract'])
            if checked != review:
                raise IntegrityError('Stored semantic or engineering result changed')
            outcomes.append(checked['decision'])
        if len(covered) != len(set(covered)) or set(covered) != set(by_id):
            raise IntegrityError('Full library/earlier eligible candidate coverage is incomplete')
        decision = next((d for d in ('conflict','uncertain','duplicate') if d in outcomes),'novel')
        if assessment['decision'] != decision:
            raise IntegrityError('Aggregate review decision changed')
        if decision == 'novel':
            eligible.append(rule['id'])
            comparison.append(rule)
    if eligible != value['eligible_ids']:
        raise IntegrityError('Eligible candidates changed')
    return value


def render(root, package):
    lines = ['# Rubrics 待人工审核候选', '', f'审核包：`{Path(root).name}`',
             f'父版本：`{package["parent_version"]}`', '',
             '模型通过仅表示入库候选；尚未发布，也不会被生成流程读取。',
             '请复核证据、适用范围、阶段权限及逐条比较理由，再明确选择发布哪些规则。',
             '复制 decision.template.json 为自己的决定文件；pending 模板不能发布。',
             'decision=approve 时填写 approved_ids、reviewer；decision=reject 时 approved_ids 必须为空。',
             '未选中的候选不会发布；冲突、不确定或重复条目不可直接批准，修改内容后必须重新复核。',
             '该审核包只接受一次决定；重复相同决定可恢复，父版本变化须重新审核。', '']
    observations = {o['id']:o for o in package['observations']}
    sources = {s['poster_id']:s for s in package['sources']}
    for rule, assessment in zip(package['candidates'],package['assessments']):
        lines += [f'## {rule["id"]} — {assessment["decision"]}', '']
        fields = ['type','dimension','requirement','applicability','criterion']
        if 'revision_guidance' in rule:  # Preserve historical packages for read-only inspection.
            fields.append('revision_guidance')
        fields.append('applicable_stages')
        for name in fields:
            lines += [f'**{name}**：{rule[name]}', '']
        lines += ['### 证据', '']
        for ref in rule['evidence_refs']:
            o = observations[ref]
            lines += [f'- `{ref}`：{o["observation"]}；证据：{o["evidence"]}']
            if o.get('poster_id') in sources:
                source = sources[o['poster_id']]
                bundle = Path(source['bundle_path'])
                lines += [f'  论文 SHA256：`{source["paper_sha256"]}`；'
                          f'[最终海报](<{bundle / "poster.png"}>) · '
                          f'[评分](<{bundle / "evaluation.json"}>) · '
                          f'[论文材料](<{bundle / "refinement/paper.json"}>)']
        lines += ['', '### 完整语义比较与工程约束检查', '',
                  '```json', json.dumps(assessment,ensure_ascii=False,indent=2), '```', '']
    return '\n'.join(lines)


def publish(root, decision_file):
    """No model calls. Only explicit, package-bound human selections can append."""
    root = Path(root).resolve()
    decision = read_json(Path(decision_file))
    fields = {'schema_version','review_id','parent_version','decision','approved_ids','reviewer','comment'}
    if (not isinstance(decision,dict) or set(decision) != fields or decision['schema_version'] != 1 or
            decision['decision'] not in {'approve','reject'} or not isinstance(decision['reviewer'],str) or
            not decision['reviewer'].strip() or not isinstance(decision['comment'],str) or
            not isinstance(decision['approved_ids'],list) or
            any(not isinstance(i,str) for i in decision['approved_ids']) or
            len(decision['approved_ids']) != len(set(decision['approved_ids']))):
        raise ValueError('An explicit human approve/reject decision with reviewer and unique IDs is required')
    with lock(root/'.decision.lock',blocking=False):
        package = load(root, current_contract=True)
        if decision['review_id'] != root.name or decision['parent_version'] != package['parent_version']:
            raise IntegrityError('Human decision belongs to a different review or parent')
        selected = set(decision['approved_ids'])
        if not selected <= set(package['eligible_ids']):
            raise ValueError('Only fully reviewed, compatible novel candidates can be selected')
        if (decision['decision'] == 'approve') != bool(selected):
            raise ValueError('Approve requires selected IDs; reject requires no selected IDs')
        prior = root/'human_decision.json'
        if prior.exists() and read(prior) != decision:
            raise IntegrityError('A different human decision is already recorded for this package')
        result_path = root/'publication.json'
        if result_path.exists():
            if not prior.exists():
                raise IntegrityError('Publication receipt has no human decision')
            return read(result_path)
        store = LibraryStore(root.parent.parent)
        parent = store.version(package['parent_version'])
        rules = [r for r in package['candidates'] if r['id'] in selected]
        if len(parent['rules']) + len(rules) > package['max_rules']:
            raise ValueError('Selected candidates exceed the frozen rule cap; select fewer')
        # Recheck selected evidence at the publication boundary, without calling a model.
        refs = {ref for rule in rules for ref in rule['evidence_refs']}
        posters = {o['poster_id'] for o in package['observations'] if o['id'] in refs and 'poster_id' in o}
        for sample in package['sources']:
            if sample['poster_id'] not in posters:
                continue
            bundle = Path(sample['bundle_path']).resolve()
            for relative, expected_hash in sample['files'].items():
                path = (bundle/relative).resolve()
                if not path.is_relative_to(bundle) or not path.is_file() or file_hash(path) != expected_hash:
                    raise IntegrityError('Selected candidate source evidence changed or is missing')
        source = digest({'review_id':root.name,'human_decision':decision,'batch':package['source_batch_digest']})
        expected = {'schema_version':LIBRARY_SCHEMA_VERSION,'parent_version':parent['version'],'status':'published',
                    'rules':parent['rules']+rules,'source_batch_digest':source}
        current = store.active(required=True)['version']
        # Only a recorded approval can resume a publication interrupted after active.json.
        if current != parent['version'] and not (prior.exists() and rules and current == digest(expected)):
            raise IntegrityError('UPDATE_CONFLICT: active parent changed; a new full review is required')
        immutable(prior,decision)
        if rules:
            published = store.publish(parent['rules']+rules,parent_version=parent['version'],source_batch_digest=source)
            result = {'status':'PUBLISHED','version':published['version'],'name':store.name(published['version']),
                      'added':len(rules),'approved_ids':[r['id'] for r in rules],'review_id':root.name}
        else:
            result = {'status':'REJECTED','version':parent['version'],'added':0,'approved_ids':[],'review_id':root.name}
        immutable(result_path,result)
        return result
