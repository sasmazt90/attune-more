/** Numeric regional summaries only. Publisher/model polygons are never admitted
 * here as anatomical coverage. The server owns method acceptance; this boundary
 * preserves its evidence and checks consistency before UI/history use. */
export const REGIONAL_MAP_VERSION = 'regional-skin-evidence-v1';
export const REGIONAL_MAP_REGIONS = ['forehead', 'nose', 'chin', 'leftCheek', 'rightCheek'] as const;
const T_ZONE = ['forehead', 'nose', 'chin'];
const OUTSIDE_T = ['leftCheek', 'rightCheek'];
export type RegionalMapRegion = typeof REGIONAL_MAP_REGIONS[number];
type RegionState = 'unknown' | 'normal' | 'dry' | 'oily';
type Observation = { state: 'unknown'; reason: string } | {
  state: 'positive' | 'negative'; reason: null; coverage: number;
  methodVersion: string; normalizationVersion: string; modelHash: string | null;
  validationEvidence: string;
};
export type RegionalMap = {
  version: typeof REGIONAL_MAP_VERSION;
  geometry: 'anatomical-region-summary-not-pixel-mask';
  regions: Record<RegionalMapRegion, {
    state: RegionState; fill: 'blue' | 'green' | 'lightgrey' | null; reason: string | null;
    redness: { state: 'positive' | 'negative' | 'unknown'; colour: 'red' | null; style: 'contour-or-hatching' };
    observations: Record<'oil' | 'dry' | 'redness', Observation>;
  }>;
  complete: boolean; combinationMatched: boolean; tZone: string[]; outsideTZone: string[];
  confidence: null; sensitivityInferred: false;
};
export type RegionalMapSource = {
  captureId: string; pose: 'FRONT'; sourceWidth: number; sourceHeight: number;
  coordinateSpace: 'source-pixels';
};
export type BoundRegionalSkinMap = { source: RegionalMapSource; map: RegionalMap };

const object = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const nonempty = (v: unknown): v is string => typeof v === 'string' && v.length > 0;
function sourceValid(v: unknown): v is RegionalMapSource {
  return object(v) && typeof v.captureId === 'string' && /^[a-f0-9]{64}$/.test(v.captureId)
    && v.pose === 'FRONT' && v.coordinateSpace === 'source-pixels'
    && [v.sourceWidth, v.sourceHeight].every(n => Number.isSafeInteger(n) && n >= 16);
}
function observation(v: unknown): Observation | undefined {
  if (!object(v)) return;
  if (v.state === 'unknown' && nonempty(v.reason)) return { state: 'unknown', reason: v.reason };
  if (!['positive', 'negative'].includes(v.state) || v.reason !== null
    || typeof v.coverage !== 'number' || !Number.isFinite(v.coverage) || v.coverage <= 0 || v.coverage > 1
    || ![v.methodVersion, v.normalizationVersion, v.validationEvidence].every(nonempty)
    || !(v.modelHash === null || nonempty(v.modelHash))) return;
  return { state: v.state, reason: null, coverage: v.coverage, methodVersion: v.methodVersion,
    normalizationVersion: v.normalizationVersion, modelHash: v.modelHash, validationEvidence: v.validationEvidence };
}
/** Strict parser also strips unrelated keys: no image, inferred mask or caller
 * acceptance flag enters the numeric history through this field. */
export function parseRegionalSkinMap(value: unknown): RegionalMap | undefined {
  if (!object(value) || value.version !== REGIONAL_MAP_VERSION
    || value.geometry !== 'anatomical-region-summary-not-pixel-mask'
    || value.confidence !== null || value.sensitivityInferred !== false || !object(value.regions)
    || JSON.stringify(value.tZone) !== JSON.stringify(T_ZONE)
    || JSON.stringify(value.outsideTZone) !== JSON.stringify(OUTSIDE_T)) return;
  const regions = {} as RegionalMap['regions'];
  for (const region of REGIONAL_MAP_REGIONS) {
    const row = value.regions[region];
    if (!object(row) || !object(row.observations) || !object(row.redness)) return;
    const oil = observation(row.observations.oil), dry = observation(row.observations.dry), red = observation(row.observations.redness);
    if (!oil || !dry || !red) return;
    const state: RegionState = oil.state === 'negative' && dry.state === 'negative' ? 'normal'
      : oil.state === 'positive' && dry.state === 'negative' ? 'oily'
      : oil.state === 'negative' && dry.state === 'positive' ? 'dry' : 'unknown';
    const fill = ({ normal: null, oily: 'green', dry: 'blue', unknown: 'lightgrey' } as const)[state];
    const reason = state !== 'unknown' ? null : oil.state === 'positive' && dry.state === 'positive'
      ? 'CONFLICTING_REGION_AGGREGATES_REQUIRE_LOCAL_SUPPORT' : 'REGIONAL_EVIDENCE_INCOMPLETE';
    if (row.state !== state || row.fill !== fill || row.reason !== reason
      || row.redness.state !== red.state || row.redness.colour !== (red.state === 'positive' ? 'red' : null)
      || row.redness.style !== 'contour-or-hatching') return;
    regions[region] = { state, fill, reason, observations: { oil, dry, redness: red },
      redness: { state: red.state, colour: red.state === 'positive' ? 'red' : null, style: 'contour-or-hatching' } };
  }
  const complete = REGIONAL_MAP_REGIONS.every(r => regions[r].state !== 'unknown');
  const combinationMatched = complete && T_ZONE.every(r => regions[r as RegionalMapRegion].state === 'oily')
    && OUTSIDE_T.every(r => ['normal', 'dry'].includes(regions[r as RegionalMapRegion].state));
  if (value.complete !== complete || value.combinationMatched !== combinationMatched) return;
  return { version: REGIONAL_MAP_VERSION, geometry: 'anatomical-region-summary-not-pixel-mask', regions,
    complete, combinationMatched, tZone: [...T_ZONE], outsideTZone: [...OUTSIDE_T], confidence: null, sensitivityInferred: false };
}
export function bindRegionalSkinMap(value: unknown, source: RegionalMapSource): BoundRegionalSkinMap | undefined {
  const map = parseRegionalSkinMap(value);
  if (!map || !sourceValid(source)) return;
  return { source: { captureId: source.captureId, pose: source.pose, sourceWidth: source.sourceWidth,
    sourceHeight: source.sourceHeight, coordinateSpace: source.coordinateSpace }, map };
}
export function validBoundRegionalSkinMap(value: unknown, source: RegionalMapSource): value is BoundRegionalSkinMap {
  if (!object(value) || !sourceValid(source) || !sourceValid(value.source)
    || !['captureId', 'pose', 'sourceWidth', 'sourceHeight', 'coordinateSpace'].every(k => value.source[k] === source[k as keyof RegionalMapSource])) return false;
  const clean = bindRegionalSkinMap(value.map, source);
  // Existing numeric records are validated, never silently rewritten. Unknown
  // fields (including photo material) must fail the persistence boundary.
  return !!clean && sameValue(value, clean);
}
function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => sameValue(v, b[i]));
  if (!object(a) || !object(b)) return false;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(k => Object.prototype.hasOwnProperty.call(b, k) && sameValue(a[k], b[k]));
}
/** Only categorical comparisons, with identical evidence identities per region
 * and criterion. Unknown readings and changed methods have no comparable pair. */
export function comparableRegionalObservations(a: unknown, b: unknown): string[] {
  if (!object(a) || !object(b) || !validBoundRegionalSkinMap(a, a.source) || !validBoundRegionalSkinMap(b, b.source)) return [];
  const comparable: string[] = [];
  for (const region of REGIONAL_MAP_REGIONS) for (const criterion of ['oil', 'dry', 'redness'] as const) {
    const x = a.map.regions[region].observations[criterion], y = b.map.regions[region].observations[criterion];
    if (x.state !== 'unknown' && y.state !== 'unknown'
      && ['methodVersion', 'normalizationVersion', 'modelHash', 'validationEvidence'].every(k => x[k as keyof typeof x] === y[k as keyof typeof y])) comparable.push(`${region}:${criterion}`);
  }
  return comparable;
}
