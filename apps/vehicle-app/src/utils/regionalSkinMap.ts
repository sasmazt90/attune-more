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
export type RegionalSkinLayer = {
  region: RegionalMapRegion;
  state: RegionState;
  fill: 'blue' | 'green' | 'lightgrey' | null;
  redness: 'positive' | 'negative' | 'unknown';
  geometry: 'anatomical-region-summary-not-pixel-mask';
};
export type RegionalSkinReplay = {
  source: RegionalMapSource;
  viewBox: { x: number; y: number; width: number; height: number };
  layers: RegionalSkinLayer[];
};
export type RegionalObservationCriterion = 'oil' | 'dry' | 'redness';
export type RegionalObservationHistoryPoint = {
  recordId: string; time: number; state: 'positive' | 'negative'; changedFromPrevious: boolean | null;
};
export type RegionalObservationHistory = {
  region: RegionalMapRegion; criterion: RegionalObservationCriterion;
  status: 'comparable' | 'single-record' | 'method-changed' | 'not-evaluated' | 'record-unavailable';
  unavailableReason: string | null;
  methodVersion: string | null; normalizationVersion: string | null; modelHash: string | null;
  validationEvidence: string | null;
  points: RegionalObservationHistoryPoint[]; excludedIncompatible: number; excludedUnknown: number;
};

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
  return !!clean && sameValue(value, clean);
}
function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => sameValue(v, b[i]));
  if (!object(a) || !object(b)) return false;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(k => Object.prototype.hasOwnProperty.call(b, k) && sameValue(a[k], b[k]));
}

/** Convert only a source-bound accepted summary to a presentation plan.
 * The plan uses existing anatomical meshes; it is never a predicted pixel mask.
 * A criterion-specific view does not infer normal from another criterion. */
export function regionalSkinLayers(value: unknown, source: RegionalMapSource,
  region: 'overview' | string, criterion?: string | null): RegionalSkinLayer[] {
  if (!validBoundRegionalSkinMap(value, source)
    || ![null, undefined, 'oil', 'dry', 'redness'].includes(criterion)
    || (region !== 'overview' && !REGIONAL_MAP_REGIONS.includes(region as RegionalMapRegion))) return [];
  const ids = region === 'overview' ? REGIONAL_MAP_REGIONS : [region as RegionalMapRegion];
  return ids.map(id => {
    const row = value.map.regions[id];
    let fill = row.fill;
    if (criterion === 'oil') fill = row.observations.oil.state === 'positive' ? 'green'
      : row.observations.oil.state === 'unknown' ? 'lightgrey' : null;
    if (criterion === 'dry') fill = row.observations.dry.state === 'positive' ? 'blue'
      : row.observations.dry.state === 'unknown' ? 'lightgrey' : null;
    if (criterion === 'redness') fill = row.observations.redness.state === 'unknown' ? 'lightgrey' : null;
    return { region: id, state: row.state, fill,
      redness: criterion === 'oil' || criterion === 'dry' ? 'negative' : row.redness.state,
      geometry: 'anatomical-region-summary-not-pixel-mask' };
  });
}

/** Replays a retained photo only when the accepted regional summary, photo,
 * crop and every rendered mesh all share one source-pixel coordinate space. */
export function retainedRegionalSkinReplay(snapshot: unknown, region: 'overview' | string,
  criterion?: string | null): RegionalSkinReplay | undefined {
  if (!object(snapshot) || snapshot.angle !== 'FRONT' || !nonempty(snapshot.photoId)
    || !/^data:image\/png;base64,/.test(snapshot.dataUrl || '')
    || !Number.isSafeInteger(snapshot.width) || !Number.isSafeInteger(snapshot.height)
    || snapshot.width < 16 || snapshot.height < 16 || !object(snapshot.general)
    || !object(snapshot.meshes)) return;
  const source: RegionalMapSource = { captureId: snapshot.photoId, pose: 'FRONT',
    sourceWidth: snapshot.width, sourceHeight: snapshot.height, coordinateSpace: 'source-pixels' };
  const normalized = snapshot.previewCrop;
  const rawCrop = normalized ? object(normalized) && [normalized.x, normalized.y, normalized.width, normalized.height]
    .every(n => typeof n === 'number' && Number.isFinite(n))
    ? { x: normalized.x * snapshot.width, y: normalized.y * snapshot.height,
      width: normalized.width * snapshot.width, height: normalized.height * snapshot.height } : undefined
    : snapshot.crop;
  if (!object(rawCrop) || ![rawCrop.x, rawCrop.y, rawCrop.width, rawCrop.height]
    .every(n => typeof n === 'number' && Number.isFinite(n)) || rawCrop.x < 0 || rawCrop.y < 0
    || rawCrop.width <= 0 || rawCrop.height <= 0 || rawCrop.x + rawCrop.width > snapshot.width
    || rawCrop.y + rawCrop.height > snapshot.height) return;
  const layers = regionalSkinLayers(snapshot.general.regionalSkinMap, source, region, criterion);
  if (!layers.length) return;
  const epsilon = .5;
  for (const layer of layers) {
    const mesh = snapshot.meshes[layer.region];
    if (!object(mesh) || !Array.isArray(mesh.points) || mesh.points.length < 3
      || mesh.points.some((point: unknown) => !object(point) || typeof point.x !== 'number' || !Number.isFinite(point.x)
        || typeof point.y !== 'number' || !Number.isFinite(point.y) || point.x < 0 || point.y < 0
        || point.x > snapshot.width || point.y > snapshot.height
        || point.x < rawCrop.x - epsilon || point.y < rawCrop.y - epsilon
        || point.x > rawCrop.x + rawCrop.width + epsilon || point.y > rawCrop.y + rawCrop.height + epsilon)) return;
  }
  return { source, viewBox: { x: rawCrop.x, y: rawCrop.y, width: rawCrop.width, height: rawCrop.height }, layers };
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

/** Builds a categorical history for one region/criterion without inventing a
 * numeric severity delta. The current (or requested) record pins the evidence
 * identity; records produced by any other method are excluded, not bridged. */
export function regionalObservationHistory(records: unknown[], region: string, criterion: string,
  anchorRecordId?: string): RegionalObservationHistory | undefined {
  if (!Array.isArray(records) || !REGIONAL_MAP_REGIONS.includes(region as RegionalMapRegion)
    || !['oil', 'dry', 'redness'].includes(criterion)) return;
  const regionId = region as RegionalMapRegion, criterionId = criterion as RegionalObservationCriterion;
  const candidates: Array<{recordId: string; time: number; state: 'positive' | 'negative'; identity: string;
    methodVersion: string; normalizationVersion: string; modelHash: string | null; validationEvidence: string}> = [];
  const unknowns: Array<{recordId: string; time: number; reason: string}> = [];
  let requestedRecordSeen = false, requestedRecordInvalid = false;
  for (const raw of records) {
    if (!object(raw) || !nonempty(raw.id)) continue;
    if (anchorRecordId && raw.id === anchorRecordId) requestedRecordSeen = true;
    const date = raw.timestamp ?? raw.date ?? raw.completedAt;
    const time = typeof date === 'string' ? Date.parse(date) : NaN;
    if (!Number.isFinite(time)) {
      if (anchorRecordId && raw.id === anchorRecordId) requestedRecordInvalid = true;
      continue;
    }
    const value = raw.general?.regionalSkinMap;
    if (value === undefined || value === null) {
      unknowns.push({ recordId: raw.id, time, reason: 'REGIONAL_RESULT_NOT_AVAILABLE' });
      continue;
    }
    if (!object(value) || !sourceValid(value.source) || !validBoundRegionalSkinMap(value, value.source)) {
      if (anchorRecordId && raw.id === anchorRecordId) requestedRecordInvalid = true;
      continue;
    }
    const observed = value.map.regions[regionId].observations[criterionId];
    if (observed.state === 'unknown') unknowns.push({ recordId: raw.id, time, reason: observed.reason });
    else {
      const identity = JSON.stringify([observed.methodVersion, observed.normalizationVersion,
        observed.modelHash, observed.validationEvidence]);
      candidates.push({ recordId: raw.id, time, state: observed.state, identity,
        methodVersion: observed.methodVersion, normalizationVersion: observed.normalizationVersion,
        modelHash: observed.modelHash, validationEvidence: observed.validationEvidence });
    }
  }
  candidates.sort((a, b) => a.time - b.time || a.recordId.localeCompare(b.recordId));
  unknowns.sort((a, b) => a.time - b.time || a.recordId.localeCompare(b.recordId));
  const unavailable = (status: 'not-evaluated' | 'record-unavailable', reason: string): RegionalObservationHistory => ({
    region: regionId, criterion: criterionId, status, unavailableReason: reason,
    methodVersion: null, normalizationVersion: null, modelHash: null, validationEvidence: null,
    excludedIncompatible: 0, excludedUnknown: unknowns.length, points: []
  });
  if (anchorRecordId) {
    const unknownAnchor = unknowns.find(row => row.recordId === anchorRecordId);
    if (unknownAnchor) return unavailable('not-evaluated', unknownAnchor.reason);
    if (!requestedRecordSeen || requestedRecordInvalid) return unavailable('record-unavailable', 'SELECTED_RECORD_NOT_AVAILABLE');
  }
  const anchor = anchorRecordId ? candidates.find(row => row.recordId === anchorRecordId) : candidates.at(-1);
  if (!anchor) return unknowns.length ? unavailable('not-evaluated', unknowns.at(-1)!.reason) : undefined;
  const compatible = candidates.filter(row => row.identity === anchor.identity);
  const excludedIncompatible = candidates.length - compatible.length;
  return {
    region: regionId, criterion: criterionId,
    status: compatible.length >= 2 ? 'comparable' : excludedIncompatible > 0 ? 'method-changed' : 'single-record',
    unavailableReason: null, methodVersion: anchor.methodVersion,
    normalizationVersion: anchor.normalizationVersion, modelHash: anchor.modelHash,
    validationEvidence: anchor.validationEvidence, excludedIncompatible, excludedUnknown: unknowns.length,
    points: compatible.map((row, index) => ({ recordId: row.recordId, time: row.time, state: row.state,
      changedFromPrevious: index === 0 ? null : compatible[index - 1].state !== row.state }))
  };
}

