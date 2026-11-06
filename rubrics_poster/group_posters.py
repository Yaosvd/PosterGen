"""Reorganize existing poster bundles without generation or re-scoring."""
import argparse
import json


def main():
    parser = argparse.ArgumentParser(description='Group saved posters at 80 points; incomplete scores stay separate.')
    parser.add_argument('--storage-root', default='storage/rubrics_samples')
    parser.add_argument('--dry-run', action='store_true', help='Show destinations without moving any poster.')
    args = parser.parse_args()
    from src.workflow.exploration_store import ExplorationStore
    print(json.dumps(ExplorationStore(args.storage_root).regroup_posters(dry_run=args.dry_run),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
