import type { SampleResult } from './sampleTypes';

// Use the recorded policy only: numeric scores cannot identify their scale.
export function scoreLabel(result: SampleResult): string {
  if (result.score == null) return 'Unavailable';
  const maximum = result.score_maximum;
  return typeof maximum === 'number' && Number.isFinite(maximum) && maximum > 0
    ? `${result.score} / ${maximum}` : `${result.score} (scale unavailable)`;
}

export function groupLabel(result: SampleResult): string {
  if (result.grouping === 'evaluation_failed') return 'Failed / incomplete';
  if (result.grouping === 'unclassified') return 'No poster';
  const high = result.grouping === 'high_score';
  const threshold = result.high_score_threshold;
  return typeof threshold === 'number' && Number.isFinite(threshold)
    ? `${high ? 'High' : 'Low'} (${high ? '≥' : '<'}${threshold})`
    : `${high ? 'High' : 'Low'} (threshold unavailable)`;
}
