import type { SkinIndicator } from './skinIndicators';

// These are display colors only, never clinical decision thresholds.
export const SKIN_DISPLAY_DIRECTION: Record<string, 'adverse' | 'positive' | 'neutral'> = {
  tone: 'adverse', redness: 'adverse', oil: 'adverse', dry: 'adverse', sag: 'adverse', bags: 'adverse', dark: 'adverse', lines: 'adverse', acne: 'adverse',
};
const stops = [[52, 211, 153], [251, 146, 60], [248, 75, 85]];
export function appearanceColor(value: number, direction: 'adverse' | 'positive' | 'neutral' = 'adverse') {
  if (direction === 'neutral') return '#cbd5e1';
  const position = Math.max(0, Math.min(100, direction === 'positive' ? 100 - value : value)) / 50;
  const left = position < 1 ? 0 : 1, ratio = Math.min(1, position - left);
  return `rgb(${stops[left].map((v, i) => Math.round(v + (stops[left + 1][i] - v) * ratio)).join(',')})`;
}
export function skinDisplayKind(row: SkinIndicator): 'percent' | 'count' | 'contour' | 'other' {
  const unit = row.appearance?.unit || row.measurement?.unit || row.unit;
  if (row.appearance?.type === 'longitudinal_measurement' || unit === 'normalized-contour-ratio') return 'contour';
  if (['candidate-count', 'lesion-count'].includes(unit) || row.id === 'acne' && /aday/.test(row.unit)) return 'count';
  if (['appearance-score-0-100', 'relative-color-index-0-100', 'color-index-0-100', 'directional-line-index-0-100', 'contour-fold-index-0-100', 'percent-visible-area', 'visible-highlight-area-percent'].includes(unit) || ['tone', 'redness'].includes(row.id) && /100/.test(row.unit)) return 'percent';
  return 'other';
}
