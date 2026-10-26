/** Validated skin findings (in-domain classifiers, ≥0.80 precision on held-out persons). Only these are shown.
 * A finding is either seen, not seen in this scan, or inconclusive for its region (capture causes). Findings that were
 * not seen are never listed: recall is below 1 for several findings, so "not seen" is not presented as "absent". */
export type SkinFindingId =
  | 'acne' | 'acneMarks' | 'mole' | 'spots' | 'melasma' | 'redness' | 'rosacea'
  | 'foreheadLines' | 'crowsFeet' | 'eyeBags' | 'darkCircles' | 'hoodedEyelids' | 'downturnedCorners' | 'coldSore'
  | 'eczema' | 'flaking';
export type SkinFindingRegion = 'forehead' | 'periorbital' | 'nose' | 'rightCheek' | 'leftCheek' | 'chin';
export type SkinFindingKind = 'count' | 'area' | 'presence';
export type SkinFindingStatus = 'seen' | 'notSeen' | 'inconclusive';
export type SkinFindingMarker = { x: number; y: number; r?: number };
export type SkinFinding = {
  id: SkinFindingId; region: SkinFindingRegion; status: SkinFindingStatus;
  /** count findings: shown as a range until point-level counting is validated */
  countRange?: string;
  /** area findings: share of the region's visible skin, 0–100 */
  areaPct?: number;
  /** validated visibility score, 0–100 (rank among reference faces with this finding) */
  severity?: number;
  /** source-pixel markers on the photo of `pose` */
  markers?: SkinFindingMarker[];
  pose?: 'FRONT' | 'RIGHT' | 'LEFT';
  causes?: string[] | null;
};
export type SkinFindingsResult = { version: string; findings: SkinFinding[] };
/** One earlier scan, for the history chart. */
export type SkinFindingsHistoryEntry = { at: string; findings: SkinFinding[] };

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
  rosacea: { label: 'Rozasea benzeri kızarıklık', kind: 'presence', group: 'redness', info: 'Yanak ve burunda kalıcı kızarıklık ve ince damar görünümü.', expert: true },
  foreheadLines: { label: 'Alın çizgileri', kind: 'presence', group: 'lines', info: 'Alında yatay ince çizgiler.' },
  crowsFeet: { label: 'Kaz ayakları', kind: 'presence', group: 'lines', info: 'Gözlerin dış köşesinde ince çizgiler.' },
  eyeBags: { label: 'Göz altı torbası', kind: 'presence', group: 'eye', info: 'Alt göz kapağının altında şişkinlik görünümü.' },
  darkCircles: { label: 'Göz altı morluğu', kind: 'presence', group: 'eye', info: 'Göz altında çevreye göre daha koyu renk görünümü.' },
  hoodedEyelids: { label: 'Göz kapağı düşüklüğü', kind: 'presence', group: 'eye', info: 'Üst göz kapağı derisinin kapak çizgisinin üzerine inmiş görünümü.', expert: true },
  downturnedCorners: { label: 'Göz kuyruğu düşüklüğü', kind: 'presence', group: 'eye', info: 'Göz kuyruklarının (dış köşelerin) aşağı doğru eğimli görünümü.' },
  eczema: { label: 'Egzama veya sedef benzeri görünüm', kind: 'presence', group: 'redness', info: 'Kızarık, kuru ve pullu görünen, sınırları belirgin yamalar.', expert: true },
  flaking: { label: 'Pullanma', kind: 'presence', group: 'texture', info: 'Cilt yüzeyinde ince, kuru pulcuklar ve pürüzlü doku görünümü.' },
  coldSore: { label: 'Dudakta uçuk', kind: 'presence', group: 'lip', info: 'Dudak kenarında küçük kabarcık veya kabuklanma görünümü.', expert: true },
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
const max = (a?: number, b?: number) => (a === undefined ? b : b === undefined ? a : Math.max(a, b));
/** Findings of one status on a page. The same finding in two regions of a page (forehead and nose) is merged:
 * highest score and count range, all markers. */
export function viewFindings(all: SkinFinding[] | undefined, view: FindingViewId, status: SkinFindingStatus = 'seen'): SkinFinding[] {
  const rows = (all || []).filter(f => f.status === status && VIEW_REGIONS[view].includes(f.region) && f.id in FINDING_DEFS);
  return VIEW_ORDER[view].flatMap(id => {
    const same = rows.filter(f => f.id === id);
    if (!same.length) return [];
    return [same.reduce((a, b) => ({
      ...a, severity: max(a.severity, b.severity), areaPct: max(a.areaPct, b.areaPct),
      countRange: COUNT_RANK.indexOf(b.countRange || '') > COUNT_RANK.indexOf(a.countRange || '') ? b.countRange : a.countRange,
      markers: [...(a.markers || []), ...(b.markers || [])], causes: [...new Set([...(a.causes || []), ...(b.causes || [])])],
    }))];
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
      countRange: same.map(f => f.countRange).filter(Boolean).sort((x, y) => COUNT_RANK.indexOf(y!) - COUNT_RANK.indexOf(x!))[0] }];
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
  return !!v && typeof v.version === 'string' && Array.isArray(v.findings) && v.findings.every(f =>
    f && f.id in FINDING_DEFS && ['forehead', 'periorbital', 'nose', 'rightCheek', 'leftCheek', 'chin'].includes(f.region) &&
    ['seen', 'notSeen', 'inconclusive'].includes(f.status) && pct(f.areaPct) && pct(f.severity));
}
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
