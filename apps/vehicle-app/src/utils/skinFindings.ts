/** Skin findings of the result screen (server: services/core-api/skin_findings_v1.py). Per region a measured finding
 * is seen, not seen, or inconclusive (capture causes); findings without a saved, validated model are 'unavailable'
 * with a reason and never shown as "not seen". Not-seen findings are never listed as "absent" (recall < 1). */
export type SkinFindingId =
  | 'acne' | 'acneMarks' | 'mole' | 'spots' | 'melasma' | 'redness' | 'rosacea'
  | 'foreheadLines' | 'crowsFeet' | 'eyeBags' | 'darkCircles' | 'hoodedEyelids' | 'downturnedCorners' | 'coldSore'
  | 'eczema' | 'flaking';
export type SkinFindingRegion = 'forehead' | 'periorbital' | 'nose' | 'rightCheek' | 'leftCheek' | 'chin';
import { APPEARANCE_FINDINGS, scopedAppearance, type Appearance, type PooledAppearance } from './skinAppearance';
export type SkinFindingKind = 'count' | 'area' | 'presence';
export type SkinFindingStatus = 'seen' | 'notSeen' | 'inconclusive';
/** Source-pixel point on the photo of `pose` (each marker keeps its own pose: never drawn on another photo). */
export type SkinFindingMarker = { x: number; y: number; r?: number; pose?: 'FRONT' | 'RIGHT' | 'LEFT'; type?: AcneSubtype };
export type AcneSubtype = 'blackhead' | 'whitehead' | 'papule' | 'pustule' | 'nodule' | 'unspecified';
/** Lesion type of a marker; a box the detector did not type is an unidentified acne type. */
export const markerSubtype = (m: SkinFindingMarker): AcneSubtype => m.type || 'unspecified';
export const ACNE_SUBTYPES: { id: AcneSubtype; label: string }[] = [
  { id: 'blackhead', label: 'Siyah nokta (açık komedon)' }, { id: 'whitehead', label: 'Beyaz nokta (kapalı komedon)' },
  { id: 'papule', label: 'Papül' }, { id: 'pustule', label: 'Püstül' }, { id: 'nodule', label: 'Nodül' }, { id: 'unspecified', label: 'Tanımlanamayan akne türü' },
];
const sumSubtypes = (a?: SkinFinding['subtypes'], b?: SkinFinding['subtypes']) => (!a ? b : !b ? a
  : Object.fromEntries(ACNE_SUBTYPES.map(({ id }) => [id, (a[id] || 0) + (b[id] || 0)])) as SkinFinding['subtypes']);
export type SkinFinding = {
  id: SkinFindingId; region: SkinFindingRegion; status: SkinFindingStatus;
  /** count findings: shown as a range until point-level counting is validated */
  countRange?: string;
  /** count findings: number of lesions the detector marked (= markers drawn); countAtLeast = decided present, none marked */
  count?: number;
  countAtLeast?: boolean;
  /** redness/rosacea: light-corrected a* difference of the region from the person's own skin tone */
  toneDiff?: number;
  /** acne: marked lesions by type; the types add up to `count` ('unspecified' = acne without a typed class) */
  subtypes?: Partial<Record<AcneSubtype, number>>;
  /** area findings: share of the region's visible skin, 0–100 */
  areaPct?: number;
  /** validated visibility score, 0–100 (rank among reference faces with this finding) */
  severity?: number;
  /** appearance-v1 raw values + score of the region (skinAppearance.ts); on a page / the overview: pooled over its regions */
  appearance?: Appearance | PooledAppearance;
  /** the regional red mask is shared: these findings show the SAME regional measurement (not independent values) */
  appearanceSharedWith?: SkinFindingId[];
  appearanceSource?: string;
  /** why this finding has no appearance score (e.g. AFFECTED_MASK_NOT_AVAILABLE) */
  appearanceUnavailable?: string;
  /** photo the count was done on; countUnavailable = no photo could be counted (no number is shown) */
  countPose?: 'FRONT' | 'RIGHT' | 'LEFT';
  countUnavailable?: string;
  /** page / overview: regions of this finding that were not measured (the value covers the other regions only) */
  incomplete?: SkinFindingRegion[];
  /** source-pixel markers on the photo of `pose` */
  markers?: SkinFindingMarker[];
  pose?: 'FRONT' | 'RIGHT' | 'LEFT';
  causes?: string[] | null;
};
/** Why a finding was not measured in this scan (server reason codes). */
export type SkinFindingUnavailableReason = 'MODEL_NOT_AVAILABLE' | 'NOT_VALIDATED' | 'REQUIRED_POSES_MISSING' | 'MODEL_BUNDLE_UNAVAILABLE' | 'FUSION_FAILED' | string;
/** general.findings: 'measured' = the listed findings were read (others are in `unavailable`);
 * 'unavailable' = no finding was measured in this scan (reason). Absent = this record has no findings analysis. */
export type SkinFindingsResult = {
  version: string; status?: 'measured' | 'unavailable'; reason?: SkinFindingUnavailableReason; poses?: string[];
  findings: SkinFinding[]; unavailable?: { id: SkinFindingId; reason: SkinFindingUnavailableReason }[];
};
/** One earlier scan, for the history chart. */
/** One earlier scan for the history chart; version/status/unavailable decide what is comparable (skinHistorySummary). */
export type SkinFindingsHistoryEntry = { at: string; findings: SkinFinding[]; version?: string; status?: 'measured' | 'unavailable'; unavailable?: SkinFindingsResult['unavailable'] };
export const REGION_NAMES: Record<SkinFindingRegion, string> = { forehead: 'Alın', nose: 'Burun', periorbital: 'Göz çevresi', rightCheek: 'Sağ profil', leftCheek: 'Sol profil', chin: 'Dudak ve çevresi' };

export type FindingGroup = 'acne' | 'pigment' | 'redness' | 'lines' | 'eye' | 'lip' | 'texture';
export const FINDING_GROUP_COLORS: Record<FindingGroup, string> = {
  acne: '#fb923c', pigment: '#fde047', redness: '#f43f5e', lines: '#38bdf8', eye: '#a78bfa', lip: '#f472b6', texture: '#5eead4'
};
type Def = { label: string; unit?: string; kind: SkinFindingKind; group: FindingGroup; info: string; expert?: boolean };
export const FINDING_DEFS: Record<SkinFindingId, Def> = {
  acne: { label: 'Sivilce', unit: 'sivilce', kind: 'count', group: 'acne', info: 'Ciltte kabarık, kırmızı veya iltihaplı görünen küçük noktalar.' },
  acneMarks: { label: 'Akne izi', kind: 'presence', group: 'pigment', info: 'İyileşmiş sivilcelerden kalan düz, kahverengi veya kırmızımsı lekeler.' },
  mole: { label: 'Ben', unit: 'ben', kind: 'count', group: 'pigment', info: 'Ciltte koyu renkli, sınırları belirgin noktalar.', expert: true },
  spots: { label: 'Türü belirlenemeyen leke', unit: 'leke', kind: 'count', group: 'pigment', info: 'Ciltte görülen, türü bu taramada ayırt edilemeyen renk farklılıkları.' },
  melasma: { label: 'Melazma', kind: 'area', group: 'pigment', info: 'Yanaklarda simetrik, kahverengi ve sınırları düzensiz renk değişimi görünümü.' },
  redness: { label: 'Kızarıklık', kind: 'area', group: 'redness', info: 'Ciltte yaygın veya bölgesel kızarıklık görünümü.' },
  rosacea: { label: 'Rozasea eğilimi', kind: 'presence', group: 'redness', info: 'Yanak ve burunda kalıcı kızarıklık ve ince damar görünümü.', expert: true },
  foreheadLines: { label: 'Alın çizgileri', kind: 'presence', group: 'lines', info: 'Alında yatay ince çizgiler.' },
  crowsFeet: { label: 'Kaz ayakları', kind: 'presence', group: 'lines', info: 'Gözlerin dış köşesinde ince çizgiler.' },
  eyeBags: { label: 'Göz altı torbası', kind: 'presence', group: 'eye', info: 'Alt göz kapağının altında şişkinlik görünümü.' },
  darkCircles: { label: 'Göz altı morluğu', kind: 'presence', group: 'eye', info: 'Göz altında çevreye göre daha koyu renk görünümü.' },
  hoodedEyelids: { label: 'Göz kapağı düşüklüğü', kind: 'presence', group: 'eye', info: 'Üst göz kapağı derisinin kapak çizgisinin üzerine inmiş görünümü.', expert: true },
  downturnedCorners: { label: 'Göz kuyruğu düşüklüğü', kind: 'presence', group: 'eye', info: 'Göz kuyruklarının (dış köşelerin) aşağı doğru eğimli görünümü.' },
  eczema: { label: 'Egzama/sedef eğilimi', kind: 'presence', group: 'redness', info: 'Kızarık, kuru ve pullu görünen, sınırları belirgin yamalar.', expert: true },
  flaking: { label: 'Pullanma', kind: 'presence', group: 'texture', info: 'Cilt yüzeyinde ince, kuru pulcuklar ve pürüzlü doku görünümü.' },
  coldSore: { label: 'Dudakta uçuk', unit: 'uçuk', kind: 'presence', group: 'lip', info: 'Dudak kenarında küçük kabarcık veya kabuklanma görünümü.', expert: true },
};

/* ---------- result pages: T-zone (forehead + nose), eyes, both profiles, lips ---------- */
export type FindingViewId = 'forehead' | 'periorbital' | 'rightCheek' | 'leftCheek' | 'chin';
export const FINDING_VIEWS: FindingViewId[] = ['forehead', 'periorbital', 'rightCheek', 'leftCheek', 'chin'];
export const FINDING_VIEW_ORDER: ('overview' | FindingViewId)[] = ['overview', ...FINDING_VIEWS];
export const FINDING_VIEW_NAMES: Record<FindingViewId, string> = {
  forehead: 'T-bölgesi', periorbital: 'Göz çevresi', rightCheek: 'Sağ profil', leftCheek: 'Sol profil', chin: 'Dudak ve çevresi'
};
/** Anatomical regions (server) shown on each page. */
export const VIEW_REGIONS: Record<FindingViewId, SkinFindingRegion[]> = {
  forehead: ['forehead', 'nose'], periorbital: ['periorbital'], rightCheek: ['rightCheek'], leftCheek: ['leftCheek'], chin: ['chin']
};
export const regionView = (r: SkinFindingRegion): FindingViewId => (r === 'nose' ? 'forehead' : r);
export const ALL_REGIONS: SkinFindingRegion[] = ['forehead', 'nose', 'periorbital', 'rightCheek', 'leftCheek', 'chin'];
export const isFindingView = (v: string): v is FindingViewId => (FINDING_VIEWS as string[]).includes(v);
/** Display order of findings on each page. */
const VIEW_ORDER: Record<FindingViewId, SkinFindingId[]> = {
  forehead: ['foreheadLines', 'acne', 'acneMarks', 'redness', 'rosacea', 'eczema', 'flaking', 'spots', 'melasma', 'mole'],
  periorbital: ['eyeBags', 'darkCircles', 'crowsFeet', 'hoodedEyelids', 'downturnedCorners'],
  rightCheek: ['acne', 'acneMarks', 'redness', 'rosacea', 'eczema', 'flaking', 'melasma', 'spots', 'mole'],
  leftCheek: ['acne', 'acneMarks', 'redness', 'rosacea', 'eczema', 'flaking', 'melasma', 'spots', 'mole'],
  chin: ['coldSore', 'acne', 'acneMarks', 'redness', 'eczema', 'flaking', 'spots', 'mole'],
};
export const findingColor = (id: SkinFindingId) => FINDING_GROUP_COLORS[FINDING_DEFS[id].group];
export const COUNT_RANGE_LABEL: Record<string, string> = {
  '1-2': '1–2', '3-5': '3–5', '6-10': '6–10', '11-20': '11–20', '20+': '20+', '1-3': '1–3', '4-10': '4–10', '10+': '10+'
};
const COUNT_RANK = ['1-2', '1-3', '3-5', '4-10', '6-10', '10+', '11-20', '20+'];
/** Markers keep the pose of the photo they were measured on. */
const withPose = (f: SkinFinding): SkinFindingMarker[] => (f.markers || []).map(m => ({ ...m, pose: m.pose || f.pose }));
/** Markers that belong to the photo of `angle`. A marker whose photo is unknown is never drawn (it could be another pose's). */
export function markersOnPhoto(f: SkinFinding | undefined, angle: string | undefined): SkinFindingMarker[] {
  return f && angle ? withPose(f).filter(m => m.pose === angle) : [];
}
const sumCount = (a?: number, b?: number) => (a === undefined ? b : b === undefined ? a : a + b);
/** "3 sivilce", "1+ uçuk": the number of marked lesions. */
export function countLabel(f: SkinFinding): string | null {
  return f.count === undefined ? (f.countRange ? COUNT_RANGE_LABEL[f.countRange] || f.countRange : null) : `${f.count}${f.countAtLeast ? '+' : ''}`;
}
/** Unit word shown after a count ("3 sivilce", "1 sivilce"). The unit entries of the catalog are plural in English and
 * German; "1 <unit>" has its own singular entry. Turkish output is the unit itself. */
export function countUnit(count: string | null, unit: string | undefined, text: (value: string) => string): string {
  if (!unit) return '';
  if (count !== '1') return text(unit);
  const one = text(`1 ${unit}`);
  return one.startsWith('1 ') ? one.slice(2) : text(unit);
}
const max = (a?: number, b?: number) => (a === undefined ? b : b === undefined ? a : Math.max(a, b));
/** Findings of one status on a page. The same finding in two regions of a page (forehead and nose) is merged:
 * highest score and count range, all markers. */
export function viewFindings(all: SkinFinding[] | undefined, view: FindingViewId, status: SkinFindingStatus = 'seen'): SkinFinding[] {
  const rows = (all || []).filter(f => f.status === status && VIEW_REGIONS[view].includes(f.region) && f.id in FINDING_DEFS);
  return VIEW_ORDER[view].flatMap(id => {
    const same = rows.filter(f => f.id === id);
    if (!same.length) return [];
    // Rosacea has no score of its own: it shows the measured red area of the same regions.
    const redArea = id === 'rosacea' && same.every(f => f.severity === undefined && f.areaPct === undefined)
      ? rows.filter(f => f.id === 'redness' && same.some(r => r.region === f.region)).reduce<number | undefined>((m, f) => max(m, f.areaPct), undefined) : undefined;
    const scope = VIEW_REGIONS[view];
    const rowsAll = (all || []).filter(f => f.id === id && scope.includes(f.region));
    const incomplete = rowsAll.filter(f => f.status === 'inconclusive').map(f => f.region);
    const uncounted = same.some(f => FINDING_DEFS[id].kind === 'count' && f.count === undefined && !f.countRange);
    const appearance = APPEARANCE_FINDINGS.includes(id) ? scopedAppearance(all, id, scope) : null;
    const extra = {
      ...(incomplete.length ? { incomplete } : {}),
      ...(appearance ? { appearance } : {}),
      ...(uncounted ? { count: undefined, countAtLeast: undefined } : {}),
      ...(same.every(f => f.appearanceUnavailable) ? { appearanceUnavailable: same[0].appearanceUnavailable } : {}),
      appearanceSharedWith: [...new Set(same.flatMap(f => f.appearanceSharedWith || []))],
    };
    return [{ ...same.reduce((a, b) => ({
      ...a, severity: max(a.severity, b.severity), areaPct: max(a.areaPct, b.areaPct),
      countRange: COUNT_RANK.indexOf(b.countRange || '') > COUNT_RANK.indexOf(a.countRange || '') ? b.countRange : a.countRange,
      count: sumCount(a.count, b.count), countAtLeast: !!(a.countAtLeast || b.countAtLeast) || undefined, toneDiff: max(a.toneDiff, b.toneDiff),
      subtypes: sumSubtypes(a.subtypes, b.subtypes),
      markers: [...withPose(a), ...withPose(b)], causes: [...new Set([...(a.causes || []), ...(b.causes || [])])],
    })), ...(redArea !== undefined ? { areaPct: redArea } : {}), ...extra }];
  });
}
const OVERVIEW_ORDER: SkinFindingId[] = ['eyeBags', 'darkCircles', 'crowsFeet', 'hoodedEyelids', 'downturnedCorners', 'foreheadLines', 'acne', 'acneMarks', 'redness', 'rosacea', 'eczema', 'flaking', 'melasma', 'spots', 'mole', 'coldSore'];
export type OverviewFinding = SkinFinding & { views: FindingViewId[] };
/** Every seen finding once, across all pages (highest score, largest count range), with the pages it appears on. */
export function overviewFindings(all: SkinFinding[] | undefined): OverviewFinding[] {
  const per = FINDING_VIEWS.flatMap(v => viewFindings(all, v).map(f => ({ ...f, view: v })));
  return OVERVIEW_ORDER.flatMap(id => {
    const same = per.filter(f => f.id === id);
    if (!same.length) return [];
    const { view: _v, ...first } = same[0];
    return [{ ...first, views: same.map(f => f.view), severity: same.reduce<number | undefined>((m, f) => max(m, f.severity), undefined),
      areaPct: same.reduce<number | undefined>((m, f) => max(m, f.areaPct), undefined),
      countRange: same.map(f => f.countRange).filter(Boolean).sort((x, y) => COUNT_RANK.indexOf(y!) - COUNT_RANK.indexOf(x!))[0],
      count: same.reduce<number | undefined>((n, f) => sumCount(n, f.count), undefined), countAtLeast: same.some(f => f.countAtLeast) || undefined,
      toneDiff: same.reduce<number | undefined>((m, f) => max(m, f.toneDiff), undefined),
      subtypes: same.reduce<SkinFinding['subtypes']>((m, f) => sumSubtypes(m, f.subtypes), undefined),
      ...(same.some(f => FINDING_DEFS[id].kind === 'count' && f.count === undefined && !f.countRange) ? { count: undefined, countAtLeast: undefined } : {}),
      incomplete: [...new Set([...(all || []).filter(f => f.id === id && f.status === 'inconclusive').map(f => f.region)])],
      appearance: APPEARANCE_FINDINGS.includes(id) ? scopedAppearance(all, id, ALL_REGIONS) ?? undefined : undefined,
      appearanceUnavailable: same.every(f => f.appearanceUnavailable) ? same[0].appearanceUnavailable : undefined,
      appearanceSharedWith: [...new Set(same.flatMap(f => f.appearanceSharedWith || []))] }];
  });
}
export function seenCount(all: SkinFinding[] | undefined, view?: FindingViewId): number {
  return view ? viewFindings(all, view).length : FINDING_VIEWS.reduce((n, v) => n + viewFindings(all, v).length, 0);
}
/** Inconclusive findings with the page they belong to (all pages when view is omitted). */
export function inconclusiveFindings(all: SkinFinding[] | undefined, view?: FindingViewId): (SkinFinding & { view: FindingViewId })[] {
  return (view ? [view] : FINDING_VIEWS).flatMap(v => viewFindings(all, v, 'inconclusive').map(f => ({ ...f, view: v })));
}
export function validFindings(value: unknown): value is SkinFindingsResult {
  const v = value as SkinFindingsResult;
  const pct = (x?: number) => x === undefined || (Number.isFinite(x) && x >= 0 && x <= 100);
  return !!v && typeof v.version === 'string' && Array.isArray(v.findings) && (v.status === undefined || ['measured', 'unavailable'].includes(v.status)) &&
    (v.unavailable === undefined || (Array.isArray(v.unavailable) && v.unavailable.every(u => u && u.id in FINDING_DEFS && typeof u.reason === 'string'))) &&
    v.findings.every(f =>
      f && f.id in FINDING_DEFS && ['forehead', 'periorbital', 'nose', 'rightCheek', 'leftCheek', 'chin'].includes(f.region) &&
      ['seen', 'notSeen', 'inconclusive'].includes(f.status) && pct(f.areaPct) && pct(f.severity) &&
      (f.count === undefined || (Number.isInteger(f.count) && f.count >= 0)) && (f.toneDiff === undefined || Number.isFinite(f.toneDiff)) &&
      (f.markers === undefined || (Array.isArray(f.markers) && f.markers.every(m => Number.isFinite(m.x) && Number.isFinite(m.y)))));
}
/** Client-side record of a findings analysis that did not run (no score, count or marker is produced). */
export function unavailableFindings(reason: SkinFindingUnavailableReason): SkinFindingsResult {
  return { version: 'skin-findings-v1-detector', status: 'unavailable', reason, poses: [], findings: [],
    unavailable: (Object.keys(FINDING_DEFS) as SkinFindingId[]).map(id => ({ id, reason })) };
}
/** Analysis state of a scan for the result screen: never shows "nothing found" when nothing was measured. */
export type FindingsState = { kind: 'missing' } | { kind: 'unavailable'; reason: string } | { kind: 'measured'; result: SkinFindingsResult };
export function findingsState(value: unknown): FindingsState {
  if (!validFindings(value)) return { kind: 'missing' };
  if (value.status === 'unavailable') return { kind: 'unavailable', reason: value.reason || 'UNKNOWN' };
  return { kind: 'measured', result: value };
}
/** Findings of a page that were not measured in this scan (with reason). */
export function unmeasuredFindings(result: SkinFindingsResult | undefined, view?: FindingViewId): { id: SkinFindingId; reason: string }[] {
  const rows = result?.unavailable || [];
  return view ? rows.filter(u => VIEW_ORDER[view].includes(u.id)) : rows;
}
export const UNAVAILABLE_REASON_TEXT: Record<string, string> = {
  MODEL_NOT_AVAILABLE: 'Bu bulgu için doğrulanmış model bu sürümde yok.',
  NOT_VALIDATED: 'Bu bulgunun ölçümü doğruluk sınırını geçemedi.',
  REQUIRED_POSES_MISSING: 'Bu bulgu için ön ve iki yan poz gerekir; bu tarama bu pozları içermiyor.',
  MODEL_BUNDLE_UNAVAILABLE: 'Bulgu modelleri bu cihazda yüklü değil.',
  FUSION_FAILED: 'Üç pozun birleştirilmesi tamamlanamadı.',
};
/** Point the label on the photo points at: a MediaPipe landmark, optionally offset by [dx, dy] face widths
 * (image-left = subject's right). */
export type FindingAnchor = number | [number, number, number];
export const FINDING_ANCHOR: Record<SkinFindingId, Partial<Record<FindingViewId, FindingAnchor>>> = {
  foreheadLines: { forehead: 151 }, acne: { forehead: 108, rightCheek: 205, leftCheek: 425, chin: 199 },
  acneMarks: { forehead: 337, rightCheek: 187, leftCheek: 411, chin: 200 }, redness: { forehead: 4, rightCheek: 50, leftCheek: 280, chin: 18 },
  rosacea: { forehead: 5, rightCheek: 101, leftCheek: 330 }, spots: { forehead: 67, rightCheek: 123, leftCheek: 352, chin: 175 },
  melasma: { forehead: 299, rightCheek: 116, leftCheek: 345 }, mole: { forehead: 297, rightCheek: 207, leftCheek: 427, chin: 194 },
  eyeBags: { periorbital: 145 }, darkCircles: { periorbital: 374 }, crowsFeet: { periorbital: [33, -0.06, 0.012] }, hoodedEyelids: { periorbital: 386 },
  downturnedCorners: { periorbital: [263, 0.015, 0] }, coldSore: { chin: 291 },
  eczema: { forehead: 104, rightCheek: 147, leftCheek: 376, chin: 208 }, flaking: { forehead: 333, rightCheek: 117, leftCheek: 346, chin: 428 },
};
export function anchorPoint(a: FindingAnchor, lm: { x: number; y: number }[], width: number, height: number): { x: number; y: number } {
  const [i, dx, dy] = typeof a === 'number' ? [a, 0, 0] : a, fw = Math.abs(lm[454].x - lm[234].x) * width;
  return { x: lm[i].x * width + dx * fw, y: lm[i].y * height + dy * fw };
}

/* ---------- photo layer geometry (presentation only, from MediaPipe landmarks) ---------- */
type P = { x: number; y: number };
const LOWER_LID = { r: [33, 7, 163, 144, 145, 153, 154, 155, 133], l: [263, 249, 390, 373, 374, 380, 381, 382, 362] };
const UPPER_LID = { r: [33, 246, 161, 160, 159, 158, 157, 173, 133], l: [263, 466, 388, 387, 386, 385, 384, 398, 362] };
const LIPS = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146];
function smooth(pts: P[]): string {
  const n = pts.length; if (n < 3) return '';
  let d = `M${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    d += `C${(p1.x + (p2.x - p0.x) / 6).toFixed(1)} ${(p1.y + (p2.y - p0.y) / 6).toFixed(1)} ${(p2.x - (p3.x - p1.x) / 6).toFixed(1)} ${(p2.y - (p3.y - p1.y) / 6).toFixed(1)} ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d + 'Z';
}
/** Band below/above a landmark polyline: offsets in face widths. */
function band(lm: P[], idx: number[], from: number, to: number, fw: number): string {
  // Crescent: full depth in the middle of the lid, tapering to the eye corners.
  const line = idx.map(i => lm[i]), n = line.length - 1, depth = (i: number) => from + (to - from) * Math.pow(Math.sin(Math.PI * i / n), 0.8);
  return smooth([...line.map(p => ({ x: p.x, y: p.y + from * fw })), ...line.map((p, i) => ({ x: p.x, y: p.y + depth(i) * fw })).reverse().slice(1, -1)]);
}
function ellipse(c: P, rx: number, ry: number): string {
  return `M${c.x - rx} ${c.y}a${rx} ${ry} 0 1 0 ${2 * rx} 0a${rx} ${ry} 0 1 0 ${-2 * rx} 0Z`;
}
/** Outline of the area a presence finding refers to, in source pixels. null = use the region paint outline. */
export function findingAreaPath(id: SkinFindingId, landmarks: P[] | undefined, width: number, height: number): string | null {
  if (!landmarks || landmarks.length < 468) return null;
  const lm = landmarks.map(p => ({ x: p.x * width, y: p.y * height }));
  const fw = Math.abs(lm[454].x - lm[234].x);
  switch (id) {
    case 'eyeBags': return band(lm, LOWER_LID.r, .015, .085, fw) + band(lm, LOWER_LID.l, .015, .085, fw);
    case 'darkCircles': return band(lm, LOWER_LID.r, .01, .06, fw) + band(lm, LOWER_LID.l, .01, .06, fw);
    case 'hoodedEyelids': return band(lm, UPPER_LID.r, -.045, -.005, fw) + band(lm, UPPER_LID.l, -.045, -.005, fw);
    case 'crowsFeet': return ellipse({ x: lm[33].x - .06 * fw, y: lm[33].y + .01 * fw }, .055 * fw, .07 * fw) + ellipse({ x: lm[263].x + .06 * fw, y: lm[263].y + .01 * fw }, .055 * fw, .07 * fw);
    case 'downturnedCorners': return ellipse({ x: lm[33].x - .01 * fw, y: lm[33].y }, .045 * fw, .035 * fw) + ellipse({ x: lm[263].x + .01 * fw, y: lm[263].y }, .045 * fw, .035 * fw);
    case 'coldSore': return smooth(LIPS.map(i => lm[i]).map(p => ({ x: p.x + (p.x - lm[0].x) * .25, y: p.y + (p.y - (lm[0].y + lm[17].y) / 2) * .35 })));
    default: return null;
  }
}
