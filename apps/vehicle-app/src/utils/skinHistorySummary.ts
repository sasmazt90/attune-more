/** Skin findings over time — ONE set of rules for the history chart, the Sağlık Geçmişim card, table and detail window.
 *
 * Per finding and region a record says: seen | notSeen (measured absence) | inconclusive | unavailable | missing (no
 * row). Only `notSeen` is a measured absence: a missing row, a finding absent from `unavailable`, or an empty
 * `findings` list is NOT evidence that nothing was there.
 * A record's measure of a finding over a set of regions (`scope`) is exact only when every region of the scope was
 * measured (seen or notSeen), the value exists, and a count is an exact count (legacy "1+" is not).
 * Two measures are compared only when both are exact, of the same kind (count | appearance score | belirginlik
 * percentile | legacy area %) and from the same method version; kinds are never converted into each other.
 * Unknown measurements never enter an average as 0; a measured absence counts as 0 only for counts. */
import { FINDING_DEFS, FINDING_VIEW_NAMES, countLabel, overviewFindings, regionView, validFindings,
  type SkinFinding, type SkinFindingId, type SkinFindingRegion, type SkinFindingsResult } from './skinFindings';
import { APPEARANCE_FINDINGS, scopedAppearance } from './skinAppearance';
import { usesAppearance } from './skinRecommendations';
import { SKIN_TYPE_LABELS } from './skinOverview';

export type SkinRecord = { id: string; timestamp?: string; general?: { skinType?: { value?: string | null; quality?: string }; findings?: unknown } };
export type MetricKind = 'count' | 'appearance' | 'severity' | 'area';
export type MeasureState = 'seen' | 'notSeen' | 'inconclusive' | 'unavailable' | 'missing';
export type Measure = {
  state: MeasureState; kind?: MetricKind; value?: number; exact: boolean; regions: SkinFindingRegion[];
  version?: string; atLeast?: boolean; range?: string;
  /** why the value is not exact: PARTIAL_REGIONS | NO_EXACT_COUNT | NO_VALUE */
  why?: string;
};
export type ChangeKind = 'up' | 'down' | 'same' | 'new' | 'gone' | 'unknownNow' | 'noPrevious' | 'incomparable' | 'none';
export type Change = { kind: ChangeKind; delta?: number; previous?: Measure; why?: string };

const time = (r: SkinRecord) => (r.timestamp && Number.isFinite(Date.parse(r.timestamp)) ? Date.parse(r.timestamp) : -Infinity);
export const resultOf = (r: SkinRecord | undefined): SkinFindingsResult | undefined =>
  (validFindings(r?.general?.findings) ? (r!.general!.findings as SkinFindingsResult) : undefined);
/** Records whose findings analysis ran (status measured), newest first. */
export function findingsRecords(records: SkinRecord[]): SkinRecord[] {
  return records.filter(r => { const res = resultOf(r); return !!res && res.status !== 'unavailable'; }).sort((a, b) => time(b) - time(a));
}
export function skinTypeLabel(r: SkinRecord | undefined): string | null {
  const t = r?.general?.skinType;
  return t && t.quality === 'valid' && t.value && t.value in SKIN_TYPE_LABELS ? SKIN_TYPE_LABELS[t.value as keyof typeof SKIN_TYPE_LABELS] : null;
}
/** Regions where the finding has a row in any of the results (the regions it applies to), optionally within a page. */
export function scopeOf(id: SkinFindingId, results: (SkinFindingsResult | undefined)[], within?: SkinFindingRegion[]): SkinFindingRegion[] {
  const set = new Set<SkinFindingRegion>();
  for (const res of results) for (const f of res?.findings || []) if (f.id === id && (!within || within.includes(f.region))) set.add(f.region);
  return [...set];
}
const isCount = (id: SkinFindingId, rows: SkinFinding[]) => FINDING_DEFS[id].kind === 'count' || rows.some(f => f.count !== undefined || f.countRange !== undefined);
const max = (vs: (number | undefined)[]) => { const v = vs.filter((x): x is number => x !== undefined); return v.length ? Math.max(...v) : undefined; };

/** The record's measure of `id` over `scope`. */
export function measureOf(res: SkinFindingsResult | undefined, id: SkinFindingId, scope: SkinFindingRegion[]): Measure {
  const base = { regions: scope, exact: false };
  if (!res) return { ...base, state: 'missing' };
  if (res.status === 'unavailable') return { ...base, state: 'unavailable' };
  const unav = (res.unavailable || []).some(u => u.id === id);
  const rows = res.findings.filter(f => f.id === id && scope.includes(f.region));
  if (!scope.length) return { ...base, state: unav ? 'unavailable' : 'missing' };
  const states = scope.map(r => rows.find(f => f.region === r)?.status ?? (unav ? 'unavailable' : 'missing'));
  const complete = states.every(s => s === 'seen' || s === 'notSeen');
  const seen = rows.filter(f => f.status === 'seen');
  const version = res.version;
  if (!seen.length) {
    if (complete) return { ...base, state: 'notSeen', exact: true, version, ...(isCount(id, rows) ? { kind: 'count' as const, value: 0 } : {}) };
    return { ...base, state: states.includes('inconclusive') ? 'inconclusive' : states.includes('unavailable') ? 'unavailable' : 'missing' };
  }
  if (isCount(id, seen)) {
    const counted = seen.every(f => f.count !== undefined), atLeast = seen.some(f => f.countAtLeast);
    const value = counted ? seen.reduce((s, f) => s + (f.count as number), 0) : undefined;
    const range = !counted && seen[0].countRange ? countLabel(seen[0]) ?? undefined : undefined;
    const exact = complete && counted && !atLeast;
    return { ...base, state: 'seen', kind: 'count', value, atLeast: atLeast || undefined, range, exact, version,
      why: exact ? undefined : !complete ? 'PARTIAL_REGIONS' : atLeast || !counted ? 'NO_EXACT_COUNT' : undefined };
  }
  if (APPEARANCE_FINDINGS.includes(id) && seen.some(usesAppearance)) {
    const pooled = scopedAppearance(res.findings, id, scope);
    const exact = complete && !!pooled && !pooled.partial;
    return { ...base, state: 'seen', kind: 'appearance', value: pooled?.score, exact, version: pooled ? `${version}|${pooled.version}` : version,
      why: exact ? undefined : !pooled ? 'NO_VALUE' : 'PARTIAL_REGIONS' };
  }
  const sev = max(seen.map(f => f.severity)), area = max(seen.map(f => f.areaPct));
  const kind: MetricKind | undefined = sev !== undefined ? 'severity' : area !== undefined ? 'area' : undefined;
  const value = kind === 'severity' ? sev : kind === 'area' ? area : undefined;
  const exact = complete && value !== undefined;
  return { ...base, state: 'seen', kind, value, exact, version, why: exact ? undefined : value === undefined ? 'NO_VALUE' : 'PARTIAL_REGIONS' };
}

/** cur against prev (both over the same scope). */
export function compareMeasures(cur: Measure, prev: Measure | undefined): Change {
  if (!prev) return { kind: 'none' };
  if (cur.state === 'seen') {
    if (prev.state === 'seen') {
      if (!cur.exact || !prev.exact) return { kind: 'incomparable', previous: prev, why: (!cur.exact ? cur.why : prev.why) || 'NO_VALUE' };
      if (cur.kind !== prev.kind) return { kind: 'incomparable', previous: prev, why: 'DIFFERENT_MEASURE' };
      if (cur.version !== prev.version) return { kind: 'incomparable', previous: prev, why: 'DIFFERENT_METHOD' };
      const delta = Math.round(((cur.value as number) - (prev.value as number)) * 10) / 10;
      return { kind: delta > 0 ? 'up' : delta < 0 ? 'down' : 'same', delta: Math.abs(delta), previous: prev };
    }
    if (prev.state === 'notSeen') return prev.version === cur.version?.split('|')[0] ? { kind: 'new', previous: prev } : { kind: 'incomparable', previous: prev, why: 'DIFFERENT_METHOD' };
    return { kind: 'noPrevious', previous: prev, why: prev.state };
  }
  if (prev.state === 'seen') {
    if (cur.state === 'notSeen') return prev.version?.split('|')[0] === cur.version ? { kind: 'gone', previous: prev } : { kind: 'incomparable', previous: prev, why: 'DIFFERENT_METHOD' };
    return { kind: 'unknownNow', previous: prev, why: cur.state };
  }
  return { kind: 'none', previous: prev };
}

export function formatValue(m: { kind?: MetricKind; value?: number; atLeast?: boolean; range?: string }, locale: string): string {
  if (m.value === undefined) return m.range || '—';
  const n = new Intl.NumberFormat(locale, { maximumFractionDigits: m.kind === 'count' ? 1 : 0 }).format(m.value);
  if (m.kind === 'count') return `${n}${m.atLeast ? '+' : ''}`;
  if (m.kind === 'appearance') return n;   // a 0–100 score, not a percentage
  // percent sign as each language writes it: TR %62, EN 62%, DE 62 %
  return locale.startsWith('tr') ? `%${n}` : locale.startsWith('de') ? `${n} %` : `${n}%`;
}

export type DetailRow = { id: SkinFindingId; label: string; views: string[]; now: Measure; change: Change };
/** Detail window: every finding seen now or in the previous record, measured over the regions of either record. */
export function compareRecords(current: SkinRecord, previous: SkinRecord | undefined): DetailRow[] {
  const cur = resultOf(current), prev = resultOf(previous);
  const ids = new Set<SkinFindingId>();
  for (const res of [cur, prev]) for (const f of res?.findings || []) if (f.status === 'seen') ids.add(f.id);
  const order = overviewFindings((cur?.findings || []).concat((prev?.findings || []).filter(f => !cur?.findings.some(g => g.id === f.id && g.region === f.region)))).map(f => f.id);
  return [...ids].sort((a, b) => order.indexOf(a) - order.indexOf(b)).map(id => {
    const scope = scopeOf(id, [cur, prev]);
    const now = measureOf(cur, id, scope), before = previous ? measureOf(prev, id, scope) : undefined;
    const views = [...new Set(scope.filter(r => (cur?.findings || []).some(f => f.id === id && f.region === r && f.status === 'seen')).map(r => FINDING_VIEW_NAMES[regionView(r)]))];
    return { id, label: FINDING_DEFS[id].label, views, now, change: compareMeasures(now, before) };
  });
}

/** Table summary: state of the analysis and its seen findings with their values. */
export function recordSummary(r: SkinRecord, locale: string): { state: 'measured' | 'none-seen' | 'not-measured'; items: { id: SkinFindingId; label: string; value: string }[] } {
  const res = resultOf(r);
  if (!res || res.status === 'unavailable') return { state: 'not-measured', items: [] };
  const seenIds = [...new Set(overviewFindings(res.findings).map(f => f.id))];
  if (!seenIds.length) return { state: res.findings.some(f => f.status === 'notSeen') ? 'none-seen' : 'not-measured', items: [] };
  return { state: 'measured', items: seenIds.map(id => { const m = measureOf(res, id, scopeOf(id, [res])); return { id, label: FINDING_DEFS[id].label, value: formatValue(m, locale) }; }) };
}

/** Module card: the last `n` analysed scans. Per finding, the exact values of the same kind and method as the newest
 * exact value (a measured absence = 0 for counts only); unknown or incompatible scans are left out, not zeroed. */
export function skinAverages(records: SkinRecord[], n = 3) {
  const last = findingsRecords(records).slice(0, n);
  if (!last.length) return null;
  const results = last.map(resultOf);
  const types = last.map(skinTypeLabel).filter((t): t is string => !!t);
  const skinType = types.length ? types.reduce((best, t) => (types.filter(x => x === t).length > types.filter(x => x === best).length ? t : best), types[0]) : null;
  const ids = [...new Set(results.flatMap(res => (res?.findings || []).filter(f => f.status === 'seen').map(f => f.id)))];
  const rows = ids.map(id => {
    const scope = scopeOf(id, results), ms = results.map(res => measureOf(res, id, scope));
    const ref = ms.find(m => m.state === 'seen' && m.exact && m.value !== undefined);
    const values = !ref ? [] : ms.flatMap(m => m.state === 'seen' && m.exact && m.kind === ref.kind && m.version === ref.version && m.value !== undefined ? [m.value]
      : m.state === 'notSeen' && ref.kind === 'count' && m.version === ref.version?.split('|')[0] ? [0] : []);
    const value = values.length ? values.reduce((a, b) => a + b, 0) / values.length : undefined;
    return { id, label: FINDING_DEFS[id].label, kind: ref?.kind, value, used: values.length, seenIn: ms.filter(m => m.state === 'seen').length };
  }).sort((a, b) => b.seenIn - a.seenIn || ORDER.indexOf(a.id) - ORDER.indexOf(b.id));
  return { scans: last.length, latest: time(last[0]), skinType, rows };
}
const ORDER = Object.keys(FINDING_DEFS) as SkinFindingId[];
