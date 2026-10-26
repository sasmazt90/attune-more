/** Sağlık Geçmişim (health history) presentation of the skin findings records: read-only, numbers as stored.
 * - module card: average of the last scans that carry measured findings
 * - table row: skin type + the first findings with their value
 * - record detail: every seen finding with its value, compared with the scan just before it (not with an average). */
import { FINDING_DEFS, FINDING_VIEW_NAMES, countLabel, overviewFindings, validFindings, type SkinFinding, type SkinFindingId } from './skinFindings';
import { SKIN_TYPE_LABELS } from './skinOverview';

type SkinRecord = { id: string; timestamp?: string; general?: { skinType?: { value?: string | null; quality?: string }; findings?: unknown } };
export type MetricKind = 'count' | 'severity' | 'area';
export type FindingRow = { id: SkinFindingId; label: string; views: string[]; metric?: number; kind?: MetricKind; atLeast?: boolean; range?: string };
export type Change = { kind: 'up' | 'down' | 'same' | 'new' | 'gone' | 'none'; delta?: number; previous?: string };

const time = (r: SkinRecord) => (r.timestamp && Number.isFinite(Date.parse(r.timestamp)) ? Date.parse(r.timestamp) : -Infinity);
/** Records that carry measured findings, newest first. */
export function findingsRecords(records: SkinRecord[]): SkinRecord[] {
  return records.filter(r => validFindings(r.general?.findings) && (r.general!.findings as { status?: string }).status !== 'unavailable')
    .sort((a, b) => time(b) - time(a));
}
export function skinTypeLabel(r: SkinRecord | undefined): string | null {
  const t = r?.general?.skinType;
  return t && t.quality === 'valid' && t.value && t.value in SKIN_TYPE_LABELS ? SKIN_TYPE_LABELS[t.value as keyof typeof SKIN_TYPE_LABELS] : null;
}
const metricOf = (f: SkinFinding): { metric?: number; kind?: MetricKind } =>
  f.count !== undefined ? { metric: f.count, kind: 'count' } : f.severity !== undefined ? { metric: f.severity, kind: 'severity' } : f.areaPct !== undefined ? { metric: f.areaPct, kind: 'area' } : {};

/** Seen findings of a record, one row per finding (regions merged as on the overview page). */
export function findingRows(r: SkinRecord | undefined): FindingRow[] {
  const result = r?.general?.findings;
  if (!validFindings(result)) return [];
  return overviewFindings(result.findings).map(f => ({ id: f.id, label: FINDING_DEFS[f.id].label, views: f.views.map(v => FINDING_VIEW_NAMES[v]), ...metricOf(f), atLeast: f.countAtLeast, range: f.count === undefined && f.countRange ? countLabel(f) ?? undefined : undefined }));
}
/** Findings that were measured (seen or not seen) in a record: unavailable ones are unknown, never "gone". */
function measuredIds(r: SkinRecord): Set<SkinFindingId> {
  const res = r.general?.findings;
  if (!validFindings(res)) return new Set();
  const off = new Set((res.unavailable || []).map(u => u.id)), seen = new Set(res.findings.filter(f => f.status === 'seen').map(f => f.id));
  return new Set((Object.keys(FINDING_DEFS) as SkinFindingId[]).filter(id => seen.has(id) || !off.has(id)));
}
export function formatMetric(row: { metric?: number; kind?: MetricKind; atLeast?: boolean; range?: string; id: SkinFindingId }, locale: string): string {
  if (row.metric === undefined) return row.range || '—';
  const n = new Intl.NumberFormat(locale, { maximumFractionDigits: row.kind === 'count' ? 1 : 0 }).format(row.metric);
  // percent sign as each language writes it: TR %62, EN 62%, DE 62 %
  return row.kind === 'count' ? `${n}${row.atLeast ? '+' : ''}` : locale.startsWith('tr') ? `%${n}` : locale.startsWith('de') ? `${n}\u00a0%` : `${n}%`;
}
/** Change of each finding of `current` against the scan just before it. */
export function compareWithPrevious(current: SkinRecord, previous: SkinRecord | undefined, locale: string): { rows: (FindingRow & { change: Change })[]; gone: (FindingRow & { change: Change })[] } {
  const now = findingRows(current), before = previous ? findingRows(previous) : [], prevIds = previous ? measuredIds(previous) : new Set<SkinFindingId>();
  const rows = now.map(row => {
    if (!previous) return { ...row, change: { kind: 'none' as const } };
    const old = before.find(b => b.id === row.id);
    if (!old) return { ...row, change: prevIds.has(row.id) ? { kind: 'new' as const } : { kind: 'none' as const } };
    if (row.metric === undefined || old.metric === undefined || old.kind !== row.kind) return { ...row, change: { kind: 'none' as const, previous: formatMetric(old, locale) } };
    const delta = Math.round((row.metric - old.metric) * 10) / 10;
    return { ...row, change: { kind: delta > 0 ? 'up' as const : delta < 0 ? 'down' as const : 'same' as const, delta: Math.abs(delta), previous: formatMetric(old, locale) } };
  });
  const curIds = measuredIds(current);
  const gone = before.filter(b => !now.some(r => r.id === b.id) && curIds.has(b.id)).map(b => ({ ...b, metric: undefined, change: { kind: 'gone' as const, previous: formatMetric(b, locale) } }));
  return { rows, gone };
}
/** Module card: the last `n` measured scans; counts are averaged over those scans (not seen = 0 when it was
 * measured), scores over the scans where the finding was seen. Skin type = most frequent valid type (newest wins a tie). */
export function skinAverages(records: SkinRecord[], n = 3) {
  const last = findingsRecords(records).slice(0, n);
  if (!last.length) return null;
  const types = last.map(skinTypeLabel).filter((t): t is string => !!t);
  const skinType = types.length ? types.reduce((best, t) => (types.filter(x => x === t).length > types.filter(x => x === best).length ? t : best), types[0]) : null;
  const ids = [...new Set(last.flatMap(r => findingRows(r).map(f => f.id)))];
  const rows = ids.map(id => {
    const seen = last.map(r => findingRows(r).find(f => f.id === id)).filter((f): f is FindingRow => !!f);
    const kind = seen.find(f => f.kind)?.kind;
    const values = kind === 'count'
      ? last.filter(r => measuredIds(r).has(id)).map(r => findingRows(r).find(f => f.id === id)?.metric ?? 0)
      : seen.map(f => f.metric).filter((v): v is number => v !== undefined);
    const metric = values.length ? values.reduce((a, b) => a + b, 0) / values.length : undefined;
    return { id, label: FINDING_DEFS[id].label, views: [], kind, metric, seenIn: seen.length };
  }).sort((a, b) => b.seenIn - a.seenIn || OVERVIEW_RANK(a.id) - OVERVIEW_RANK(b.id));
  return { scans: last.length, latest: time(last[0]), skinType, rows };
}
const ORDER = Object.keys(FINDING_DEFS) as SkinFindingId[];
const OVERVIEW_RANK = (id: SkinFindingId) => ORDER.indexOf(id);
