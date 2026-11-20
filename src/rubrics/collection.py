"""Freeze the completed scores of explicitly selected generation runs."""
from pathlib import Path

from src.rubrics.mining import verified_samples
from src.rubrics.storage import IntegrityError, immutable, lock, read
from src.workflow.exploration_store import ExplorationStore
from utils.persistence import digest, file_hash


def seal_collection(storage, rounds, expected_count):
    storage = Path(storage).resolve()
    samples = []
    sources = {}
    common = None
    with lock(storage/'concurrency/coordinator.lock', blocking=False):
        for directory in sorted(Path(r).resolve() for r in rounds):
            manifest = read(directory/'manifest.json')
            state = read(directory/'state.json')
            rid = manifest['round_id']
            manifest_hash = digest(manifest)
            if (rid in sources or directory.name != rid or manifest['storage_root'] != str(storage)
                    or state['manifest_digest'] != manifest_hash or state['status'] not in {'PAUSED', 'SEALED'}
                    or manifest['route'] != 'rubric-refine-score'):
                raise IntegrityError('Invalid collection source')
            identity = (manifest['round_number'], manifest['library']['version'], manifest['scoring_policy'])
            if common is not None and common != identity:
                raise IntegrityError('Incompatible iteration, library or scoring policy')
            common = identity
            sources[rid] = manifest_hash
            store = ExplorationStore(storage, poster_output=manifest['poster_output'])
            for attempt in state['attempts']:
                result = attempt.get('result', {})
                if not result.get('complete_score'):
                    continue
                if not attempt['finished'] or result['status'] != 'scored':
                    raise IntegrityError('Invalid completed score receipt')
                paper = manifest['papers'][attempt['paper_index']]
                bundle = store.verify_poster(result['poster_id'])
                if bundle.parent.parent.name != result['grouping']:
                    raise IntegrityError('Bundle grouping differs from the completion receipt')
                samples.append({'poster_id': result['poster_id'], 'round_id': rid,
                                'paper_sha256': paper['sha256'], 'bundle_path': str(bundle),
                                'files': {str(p.relative_to(bundle)): file_hash(p)
                                          for p in bundle.rglob('*') if p.is_file()}})
        if not samples or len(samples) != expected_count:
            raise IntegrityError(f'Expected {expected_count} completed scores, found {len(samples)}')
        number, library, policy = common
        seal = {'schema_version': 3, 'kind': 'scored_collection', 'route': 'rubric-refine-score',
                'round_number': number, 'sources': sources, 'sample_count': expected_count,
                'samples': samples, 'paper_hashes': sorted({s['paper_sha256'] for s in samples}),
                'library_version': library, 'scoring_policy': policy, 'scoring_policy_digest': policy['digest']}
        for _ in verified_samples(seal):
            pass
        root = storage/'iterations/collections'/digest(seal)
        immutable(root/'manifest.json', {'storage_root': str(storage), 'kind': 'scored_collection'})
        immutable(root/'seal.json', seal)
        return root
