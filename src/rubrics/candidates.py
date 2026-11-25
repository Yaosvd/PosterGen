"""Immutable review packages and a separate, explicitly human publication step."""
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote
import json

from src.rubrics.quality import aggregate_decision, validate_candidate, validate_semantic
from src.rubrics.library import LibraryStore, SCHEMA_VERSION as LIBRARY_SCHEMA_VERSION, STAGES, validate_rule
from src.rubrics.storage import IntegrityError, immutable, lock, read, text_file
from utils.persistence import digest, file_hash, read_json

SCHEMA_VERSION = 3
COMPLETE_REVIEW_VERSION = 2
LEGACY_SCHEMA_VERSION = 1


def prepare(library_root, parent, candidates, assessments, observations, identity, job, max_rules, *, sources=(), completion=None):
    if parent['schema_version'] != LIBRARY_SCHEMA_VERSION:
        raise IntegrityError('New candidate packages require the current library schema')
    version = SCHEMA_VERSION if completion is not None else COMPLETE_REVIEW_VERSION
    payload = {'schema_version':version,'status':'awaiting_human_review',
               'parent_version':parent['version'],'source_batch_digest':identity['seal'],
               'job_identity':deepcopy(identity),
               'job_path':str(Path(job).resolve()),'max_rules':max_rules,
               'candidates':deepcopy(candidates),'assessments':deepcopy(assessments),
               'observations':deepcopy(observations),
               'sources':[{**deepcopy(s), 'bundle_path':str(Path(s['bundle_path']).resolve())} for s in sources],
               'eligible_ids':[r['id'] for r in candidates]}
    if completion is not None:
        payload['completion'] = deepcopy(completion)
    review_id = digest(payload)
    root = Path(library_root)/'candidates'/review_id
    immutable(root/'package.json',payload)
    # Verify the evidence and account for every expected comparison before offering the package.
    load(root)
    decision = {'schema_version':version,'review_id':review_id,'parent_version':parent['version'],
                'decision':'pending','approved_rules':[],'reviewer':'','comment':''}
    template = root/'decision.template.json'
    if not template.exists():
        text_file(template,json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
    with lock(Path(library_root) / '.publish.lock'):
        text_file(root/'review.md', render(root, payload))
    return root


def load(root, *, current_contract=False):
    root = Path(root).resolve()
    if root.parent.name != 'candidates':
        raise IntegrityError('Review package must be inside the unified library candidates directory')
    value = read(root/'package.json')
    version = value.get('schema_version')
    if (type(version) is not int or version not in {LEGACY_SCHEMA_VERSION, COMPLETE_REVIEW_VERSION, SCHEMA_VERSION}
            or value.get('status') != 'awaiting_human_review' or digest(value) != root.name):
        raise IntegrityError('Review package identity or schema changed')
    legacy = version == LEGACY_SCHEMA_VERSION
    if legacy and current_contract:
        raise IntegrityError('Legacy candidate packages are read-only')
    parent = LibraryStore(root.parent.parent).version(value['parent_version'])
    identity = value['job_identity']
    if legacy:
        from src.rubrics.mining import validate_comparison
        if (identity.get('publication_policy') != 'human_review_v1'
                or identity.get('engineering_contract') != value['engineering_contract']):
            raise IntegrityError('Package is not bound to a legacy human-review mining job')
    elif (identity.get('publication_policy') != 'human_review_v2'
          or parent['schema_version'] != LIBRARY_SCHEMA_VERSION
          or 'engineering_contract' in value or 'engineering_contract' in identity):
        raise IntegrityError('Invalid quality-only package or job identity')
    if value['source_batch_digest'] != value['job_identity']['seal']:
        raise IntegrityError('Candidate source batch changed')
    tracked = version == SCHEMA_VERSION
    if tracked != (identity.get('failure_policy') == 'continue_independent_items_v1') or tracked != ('completion' in value):
        raise IntegrityError('Package completion policy changed')
    if type(value['max_rules']) is not int or value['max_rules'] < len(parent['rules']):
        raise IntegrityError('Invalid candidate library cap')
    candidates = value['candidates']
    for rule in candidates:
        if legacy:
            validate_rule(rule, schema_version=parent['schema_version'])
        else:
            validate_candidate(rule)
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
        raise IntegrityError('Every candidate requires one ordered assessment')
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
        failed = assessment.get('failed_chunks', [])
        if failed and not tracked:
            raise IntegrityError('Historical reviews require complete comparisons')
        if not assessment['reviews'] and not failed:
            raise IntegrityError('Candidate has no complete review')
        for review in assessment['reviews']:
            covered.extend(review['existing_ids'])
            if not set(review['existing_ids']) <= set(by_id):
                raise IntegrityError('Semantic review referenced an unknown rule')
            chunk = [by_id[i] for i in review['existing_ids']]
            response = {'comparisons': review['comparisons']}
            if legacy:
                response['engineering_review'] = review['engineering']['declared']
                checked = validate_comparison(rule,chunk,response,value['engineering_contract'])
            else:
                checked = validate_semantic(rule,chunk,response)
            if checked != review:
                raise IntegrityError('Stored semantic or engineering result changed')
            outcomes.append(checked['decision'])
        indices = set()
        for failure in failed:
            index = failure['chunk']
            if (type(index) is not int or not 0 <= index < len(failed) + len(assessment['reviews'])
                    or index in indices or not failure['existing_ids']):
                raise IntegrityError('Invalid failed semantic chunk')
            indices.add(index)
            _check_error(failure['error'])
            covered.extend(failure['existing_ids'])
        if len(covered) != len(set(covered)) or set(covered) != set(by_id):
            raise IntegrityError('Full library/earlier candidate coverage is incomplete')
        if legacy:
            decision = next((d for d in ('conflict','uncertain','duplicate') if d in outcomes),'novel')
        elif failed:
            decision = 'incomplete'
        else:
            decision = aggregate_decision(outcomes)
        if assessment['decision'] != decision:
            raise IntegrityError('Aggregate review decision changed')
        if not legacy or decision == 'novel':
            eligible.append(rule['id'])
            comparison.append(rule)
    if eligible != value['eligible_ids']:
        raise IntegrityError('Eligible candidates changed')
    if tracked:
        _check_completion(value, sources, observations)
    return value


def _check_error(error):
    if (not isinstance(error, dict) or not isinstance(error.get('error_type'), str) or not error['error_type']
            or not isinstance(error.get('message'), str) or not error['message']
            or type(error.get('send_recorded')) is not bool or type(error.get('response_saved')) is not bool):
        raise IntegrityError('Invalid item failure record')


def _check_completion(package, sources, observations):
    completion = package['completion']
    extraction, summary = completion['extraction'], completion['summary']
    for stage in (extraction, summary):
        if (type(stage['planned']) is not int or type(stage['completed']) is not int or stage['completed'] < 0
                or stage['planned'] != stage['completed'] + len(stage['failures'])):
            raise IntegrityError('Stage completion counts do not match failures')
        for item in stage['failures']:
            _check_error(item['error'])
    posters = [f['poster_id'] for f in extraction['failures']]
    if (extraction['planned'] != len(sources) or len(posters) != len(set(posters)) or not set(posters) <= sources.keys()
            or set(posters) & {o['poster_id'] for o in observations.values()}):
        raise IntegrityError('Extraction failures differ from sealed source coverage')
    clusters, failed_refs = set(), set()
    for item in summary['failures']:
        group, index, refs = item['type'], item['cluster'], item['observation_ids']
        if (group not in ('preference','rejection') or type(index) is not int or index < 0 or (group,index) in clusters
                or not refs or len(set(refs)) != len(refs) or not set(refs) <= observations.keys()
                or failed_refs.intersection(refs) or any(observations[r]['type'] != group for r in refs)):
            raise IntegrityError('Invalid failed cluster or observation membership')
        clusters.add((group,index))
        failed_refs.update(refs)
    if (summary['completed'] != len(package['candidates'])
            or any(failed_refs.intersection(r['evidence_refs']) for r in package['candidates'])):
        raise IntegrityError('Summary failures differ from candidate evidence')
    done = sum(len(r['comparisons']) for a in package['assessments'] for r in a['reviews'])
    missing = sum(len(f['existing_ids']) for a in package['assessments'] for f in a.get('failed_chunks', []))
    if completion['comparison'] != {'planned': done + missing, 'completed': done}:
        raise IntegrityError('Comparison completion counts changed')


RECOMMENDATION_LABELS = {
    'novel': '新颖', 'partial_overlap': '部分重叠', 'duplicate': '重复',
    'conflict': '语义冲突', 'uncertain': '待判断', 'incomplete': '去重未完成',
}


def render(root, package):
    legacy = package['schema_version'] == LEGACY_SCHEMA_VERSION
    lines = ['# Rubrics 待人工审核候选', '', f'审核包：`{Path(root).name}`',
             f'父版本：`{package["parent_version"]}`', '']
    if legacy:
        lines += ['历史审核记录，仅供查阅。', '']
    else:
        if 'completion' in package:
            completion = package['completion']
            lines += ['## 处理完成情况', '']
            for stage, name in [('extraction','海报抽取'), ('summary','簇总结'), ('comparison','逐条比较')]:
                counts = completion[stage]
                lines.append(f"- {name}完成 {counts['completed']} / {counts['planned']}，"
                             f"未完成 {counts['planned'] - counts['completed']} 项")
            lines.append('')
            for failure in completion['extraction']['failures']:
                error = failure['error']
                lines.append(f"- 抽取失败 `{failure['poster_id']}`，{error['error_type']} · {error['message']}")
            for failure in completion['summary']['failures']:
                error = failure['error']
                lines.append(f"- 簇总结失败 `{failure['type']}/{failure['cluster']}`，{error['error_type']} · {error['message']}。"
                             f"已保留观察 {', '.join(failure['observation_ids'])}。")
            if any(a['decision'] == 'incomplete' for a in package['assessments']):
                lines += ['', '去重未完成的候选保留已通过校验的比较，可由审核人明确选中入库。']
            lines.append('')
        lines += [
            '本包记录海报质量候选及语义比较建议，尚未发布。请结合原海报、证据和适用情境决定收录条目。',
            '复制 decision.template.json 作为你的决定文件。批准时将 decision 填为 approve，并填写 reviewer。',
            '在 approved_rules 中逐条填写所选 candidate_id 和 applicable_stages。每条须至少选一个阶段。',
            '例如 `{"candidate_id": "所选候选ID", "applicable_stages": ["你选择的阶段"]}`。',
            '可选阶段包括 ' + '、'.join(sorted(STAGES)) + '。',
            '全部拒绝时填写 reject，approved_rules 留空。重复提交同一决定可恢复发布。', '']
        entries = list(zip(package['candidates'], package['assessments']))
        lines += ['## 按语义建议浏览', '']
        for value, label in RECOMMENDATION_LABELS.items():
            group = [r for r, a in entries if a['decision'] == value]
            lines += [f'### {label}（{len(group)}）', '']
            for r in group:
                lines.append(f"- [{r['id']}](#candidate-{r['id']}) · {r['requirement']}")
            lines.append('')
        store = LibraryStore(Path(root).resolve().parent.parent)
        parent = store.version(package['parent_version'])
        library_path = f"../../{quote(store.history_dir.name)}/{parent['version']}/library.json"
        compare_with = {r['id']: (r, f'库内规则 [{r["id"]}]({library_path})') for r in parent['rules']}
        compare_with.update({r['id']: (r, f'同批候选 [{r["id"]}](#candidate-{r["id"]})')
                             for r in package['candidates']})
    observations = {o['id']:o for o in package['observations']}
    sources = {s['poster_id']:s for s in package['sources']}
    for rule, assessment in zip(package['candidates'],package['assessments']):
        label = assessment['decision']
        if not legacy:
            lines += [f'<a id="candidate-{rule["id"]}"></a>', '']
            label = RECOMMENDATION_LABELS[label]
        lines += [f'## {rule["id"]} — {label}', '']
        fields = ['type','dimension','requirement','applicability','criterion']
        if 'revision_guidance' in rule:  # Preserve historical packages for read-only inspection.
            fields.append('revision_guidance')
        if legacy:
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
        if legacy:
            lines += ['', '### 完整语义比较与工程约束检查', '',
                      '```json', json.dumps(assessment,ensure_ascii=False,indent=2), '```', '']
        else:
            pairs = [c for part in assessment['reviews'] for c in part['comparisons']]
            related = [c for c in pairs if c['decision'] != 'novel']
            lines += ['', '### 语义比较依据', '']
            failed = assessment.get('failed_chunks', [])
            if failed:
                missing = sum(len(f['existing_ids']) for f in failed)
                lines += [f'去重未完成，已比较 {len(pairs)} / {len(pairs) + missing} 项。', '']
                for chunk in failed:
                    error = chunk['error']
                    lines.append(f"- 缺少比较 `{', '.join(chunk['existing_ids'])}`，{error['error_type']} · {error['message']}")
                lines.append('')
            if related:
                for item in related:
                    compared, link = compare_with[item['existing_id']]
                    lines += [f'- **{RECOMMENDATION_LABELS[item["decision"]]}** · {link}',
                              f'  - 对方规则：{compared["requirement"]}',
                              f'  - 比较理由：{item["reason"]}', '']
            elif pairs and not failed:
                lines += [f'全部 {len(pairs)} 项比较均判为新颖。逐项模型理由见完整比较记录。', '']
            elif not failed:
                lines += ['本条没有可供比较的库内规则或更早的同批候选。', '']
            detail = '已返回的比较及缺失记录' if failed else '完整语义比较记录'
            lines += [f'<details><summary>{detail}</summary>', '', '```json',
                      json.dumps(assessment,ensure_ascii=False,indent=2), '```', '', '</details>', '']
    return '\n'.join(lines)


def publish(root, decision_file):
    """No model calls. Only explicit, package-bound human selections can append."""
    root = Path(root).resolve()
    package = load(root, current_contract=True)
    decision = read_json(Path(decision_file))
    fields = {'schema_version','review_id','parent_version','decision','approved_rules','reviewer','comment'}
    if (not isinstance(decision,dict) or set(decision) != fields or type(decision['schema_version']) is not int or
            decision['schema_version'] != package['schema_version'] or
            decision['decision'] not in ('approve','reject') or not isinstance(decision['reviewer'],str) or
            not decision['reviewer'].strip() or not isinstance(decision['comment'],str) or
            not isinstance(decision['approved_rules'],list)):
        raise ValueError('An explicit human approve/reject decision, reviewer and stage selections are required')
    if decision['review_id'] != root.name or decision['parent_version'] != package['parent_version']:
        raise IntegrityError('Human decision belongs to a different review or parent')
    selections = {}
    for entry in decision['approved_rules']:
        if not isinstance(entry,dict) or set(entry) != {'candidate_id','applicable_stages'}:
            raise ValueError('Each approved candidate requires its ID and explicit applicable stages')
        rule_id = entry['candidate_id']
        if not isinstance(rule_id,str) or rule_id in selections or rule_id not in package['eligible_ids']:
            raise ValueError('Approval requires distinct candidate IDs listed in this package')
        stages = entry['applicable_stages']
        if not isinstance(stages,list) or not all(isinstance(stage,str) for stage in stages):
            raise ValueError('Invalid applicable stages')
        selections[rule_id] = stages
    if (decision['decision'] == 'approve') != bool(selections):
        raise ValueError('Approve requires selected rules; reject requires an empty selection')
    rules = [validate_rule({**r,'applicable_stages':selections[r['id']]}) for r in package['candidates']
             if r['id'] in selections]
    with lock(root/'.decision.lock',blocking=False):
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
