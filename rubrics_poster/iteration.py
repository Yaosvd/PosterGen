"""Round generation always stops at sealing; mining requires explicit postprocess."""
import argparse
import json
from pathlib import Path

from src.rubrics.library import LibraryStore
from src.rubrics.providers import configuration
from src.rubrics.storage import WaitingForConfiguration, read


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--storage-root',type=Path,default=Path('storage/rubrics_samples'))
    sub = p.add_subparsers(dest='command',required=True)
    publish = sub.add_parser('publish-seed'); publish.add_argument('file',type=Path)
    plan = sub.add_parser('create'); plan.add_argument('--input-folder',type=Path,required=True)
    plan.add_argument('--target-group', choices=('complete_score', 'high_score'), help='Override the quota for this batch only')
    plan.add_argument('--previous-batch', type=Path, help='Reuse the output and verified posters of this closed batch')
    plan.add_argument('--poster-output',type=Path,help='Freeze a custom poster collection directory for this round')
    plan.add_argument('--round-number',type=int,help='Positive round number; defaults to the next unused number')
    plan.add_argument('--logo-folder',type=Path,help='Shared logo.png and aff.png for all papers')
    plan.add_argument('--seed',type=int,default=20261116); plan.add_argument('--generate-only',action='store_true')
    run = sub.add_parser('run', help='Generate/resume and seal only; never start batch-end processing'); run.add_argument('round',type=Path)
    collection = sub.add_parser('seal-collection', help='Freeze complete scores from selected paused or sealed runs')
    collection.add_argument('--expected-count', type=int, required=True)
    collection.add_argument('rounds', type=Path, nargs='+')
    mine = sub.add_parser('postprocess', help='Extract strengths and weaknesses, cluster, summarize and compare candidate rules'); mine.add_argument('round',type=Path); mine.add_argument('--config',type=Path)
    inspect = sub.add_parser('review-candidates', help='Inspect a completed candidate review without publishing'); inspect.add_argument('package',type=Path)
    approve = sub.add_parser('publish-candidates', help='Publish human-selected candidates with the stages supplied in the decision file')
    approve.add_argument('package',type=Path); approve.add_argument('--decision',type=Path,required=True)
    status = sub.add_parser('status'); status.add_argument('round',type=Path,nargs='?')
    preview = sub.add_parser('validate'); preview.add_argument('--input-folder',type=Path)
    preview.add_argument('--target-group', choices=('complete_score', 'high_score'))
    for command in (plan, preview):
        command.add_argument('--paper-count', type=int, help='Expected number of distinct PDFs for this batch')
    stop = sub.add_parser('stop'); stop.add_argument('round',type=Path)
    args = p.parse_args(argv)
    store = LibraryStore(args.storage_root/'rubrics')
    try:
        if args.command=='publish-seed':
            from utils.persistence import read_json, file_hash
            seed = read_json(args.file)
            result = store.publish(seed['rules'],parent_version=None,source_batch_digest='manual_seed:'+file_hash(args.file))
        elif args.command=='create':
            from src.rubrics.rounds import create
            root = create(args.input_folder,args.storage_root,seed=args.seed,generate_only=args.generate_only,
                          poster_output=args.poster_output,logo_folder=args.logo_folder,round_number=args.round_number,
                          target_group=args.target_group,previous_batch=args.previous_batch,paper_count=args.paper_count)
            result = {'status':'PLANNED','round':str(root)}
        elif args.command=='run':
            from src.rubrics.rounds import run
            seal = run(args.round)
            result = read(args.round/'state.json')
            if seal:
                # This applies even to full-mode and previously sealed rounds.
                # Generation authorization never authorizes batch-end model calls.
                result = {**result, 'seal':str(seal), 'postprocess_trigger':'manual'}
        elif args.command=='seal-collection':
            from src.rubrics.collection import seal_collection
            path = seal_collection(args.storage_root, args.rounds, args.expected_count)
            result = {'collection': str(path), 'complete_scores': args.expected_count}
        elif args.command=='postprocess':
            from src.rubrics.mining import process
            manifest = read(args.round/'manifest.json')
            result = process(args.round/'seal.json',Path(manifest['storage_root'])/'rubrics',config=configuration(args.config))
        elif args.command=='review-candidates':
            from src.rubrics.candidates import load
            package = load(args.package)
            result = {'status':'AWAITING_HUMAN_REVIEW','review_id':args.package.resolve().name,
                      'parent_version':package['parent_version'],'package_schema_version':package['schema_version'],
                      'eligible_ids':package['eligible_ids'],
                      'assessments':package['assessments'],'review_document':str(args.package/'review.md'),
                      'decision_template':str(args.package/'decision.template.json')}
            if 'completion' in package:
                result['completion'] = package['completion']
                if any(s['completed'] < s['planned'] for s in package['completion'].values()):
                    result['status'] = 'PARTIAL_REVIEW'
            if (args.package/'publication.json').exists():
                result['human_result'] = read(args.package/'publication.json')
                result['status'] = result['human_result']['status']
        elif args.command=='publish-candidates':
            from src.rubrics.candidates import publish
            result = publish(args.package,args.decision)
        elif args.command=='validate':
            from src.rubrics.providers import ExternalModels
            from src.rubrics.rounds import check_round_batch, inputs
            missing=[]
            try:store.active(required=True)
            except WaitingForConfiguration as exc:missing.append(str(exc))
            try:ExternalModels().check()
            except WaitingForConfiguration as exc:missing.append(str(exc))
            batch = configuration()['batch']
            if args.target_group is not None:
                batch['target_group'] = args.target_group
            if args.paper_count is not None:
                batch['papers'] = args.paper_count
            check_round_batch(batch)
            target_name = {'complete_score': 'complete scores', 'high_score': 'high scores'}[batch['target_group']]
            count=len(inputs(args.input_folder, paper_count=batch["papers"])) if args.input_folder else None
            result={'status':'WAITING_CONFIGURATION' if missing else 'READY','missing':missing,
                    'input_papers':count,'target':f"{batch['papers']} papers × {batch['target']} {target_name}",
                    'max_attempts_per_paper':batch['max_attempts'],'starts_generation':False}
        elif args.command=='stop':
            read(args.round/'manifest.json')
            (args.round/'STOP').touch()
            result={'status':'STOP_REQUESTED','round':str(args.round)}
        else:
            result = read(args.round/'state.json') if args.round else store.active()
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except WaitingForConfiguration as exc:
        print(json.dumps({'status':'WAITING_CONFIGURATION','reason':str(exc)},ensure_ascii=False)); return 2
    except (ValueError,OSError,RuntimeError) as exc:
        print(json.dumps({'status':'FAILED','reason':str(exc)},ensure_ascii=False)); return 1


if __name__=='__main__':
    raise SystemExit(main())
