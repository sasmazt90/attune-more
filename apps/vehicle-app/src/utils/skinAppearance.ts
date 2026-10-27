/** Görünüm skoru (appearance score), contract `appearance-v1` — the same formula as services/core-api/skin_appearance.py
 * (parity tested). Affected area = real light-corrected red pixel mask (a* > face-median a* + 4), never a box;
 * intensity = mean a* excess of the affected pixels over the reference skin. Regions are pooled by pixel sums
 * (never by adding regional percentages); each region comes from one photo only.
 *   score = round(100 * sqrt(min(1, area / 0.50) * min(1, intensity / 16)))
 * Fixed constants (engineering choices, not clinically validated); not a probability, an area % or a disease severity. */
import type { SkinFinding, SkinFindingId, SkinFindingRegion } from './skinFindings';

export const APPEARANCE_VERSION = 'appearance-v1';
export const AREA_FULL = 0.5;
export const INTENSITY_FULL = 16;
/** findings whose bar is the appearance score (melasma has no affected-area mask yet: the score is unavailable) */
export const APPEARANCE_FINDINGS: SkinFindingId[] = ['redness', 'rosacea', 'eczema', 'melasma'];
export type Appearance = { version: string; usablePx: number; affectedPx: number; areaPct: number; intensity: number; score: number };
export type PooledAppearance = Appearance & { partial: boolean; covered: SkinFindingRegion[]; missing: SkinFindingRegion[] };

/** floor(x * 10^d + 0.5) / 10^d — the one rounding rule shared with skin_appearance.py (round_half_up); never
 * Math.round's or Python round()'s own rules, so server, record and screen carry the same numbers. */
export function roundHalfUp(x: number, digits = 0): number {
  const k = 10 ** digits;
  return Math.floor(x * k + 0.5) / k;
}
export function appearanceScore(area: number, intensity: number): number {
  const a = Math.min(1, Math.max(0, area) / AREA_FULL), i = Math.min(1, Math.max(0, intensity) / INTENSITY_FULL);
  return roundHalfUp(100 * Math.sqrt(a * i));
}
const r2 = (v: number) => roundHalfUp(v, 2);
export function poolAppearance(rows: Appearance[]): Appearance | null {
  if (!rows.length || rows.some(r => !r || r.version !== APPEARANCE_VERSION)) return null;
  const usable = rows.reduce((s, r) => s + r.usablePx, 0), affected = rows.reduce((s, r) => s + r.affectedPx, 0);
  if (usable <= 0) return null;
  // the score uses the stored 2-decimal intensity, exactly as the server does
  const intensity = affected ? r2(rows.reduce((s, r) => s + r.affectedPx * r.intensity, 0) / affected) : 0, area = affected / usable;
  return { version: APPEARANCE_VERSION, usablePx: usable, affectedPx: affected, areaPct: r2(100 * area), intensity, score: appearanceScore(area, intensity) };
}
const valid = (a: unknown): a is Appearance => {
  const v = a as Appearance;
  return !!v && v.version === APPEARANCE_VERSION && [v.usablePx, v.affectedPx, v.areaPct, v.intensity, v.score].every(Number.isFinite) && v.affectedPx <= v.usablePx;
};
/** Appearance of a finding over `regions`: pooled from every measured row (seen and measured-absent). Regions that were
 * not measured (inconclusive, no row, no raw values) are listed in `missing` and make the result partial; a partial
 * result is never presented as the whole area and is not comparable. null when no region has raw values. */
export function scopedAppearance(all: SkinFinding[] | undefined, id: SkinFindingId, regions: SkinFindingRegion[]): PooledAppearance | null {
  const rows = (all || []).filter(f => f.id === id && regions.includes(f.region));
  const got = regions.map(r => rows.find(f => f.region === r && (f.status === 'seen' || f.status === 'notSeen') && valid(f.appearance)));
  const covered = regions.filter((_, i) => got[i]), missing = regions.filter((_, i) => !got[i]);
  // a region where the finding does not apply has no row at all; only regions with a row count as missing
  const relevantMissing = missing.filter(r => rows.some(f => f.region === r));
  const pooled = poolAppearance(got.filter((g): g is SkinFinding => !!g).map(g => g.appearance as Appearance));
  return pooled ? { ...pooled, partial: relevantMissing.length > 0, covered, missing: relevantMissing } : null;
}
