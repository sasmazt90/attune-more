import { REGION_ORDER, SKIN_REGIONS, buildSkinRegionViewModel, type SkinRegionData, type SkinRegionId } from '../data/skinDemoFixture';
import type { SkinIndicator } from './skinIndicators';
import { skinCriterionLabel, SIGN_LABELS } from './skinIndicators';
import type { AppearanceResponse } from './appearanceMeasurements';

export const SKIN_TYPE_LABELS = { normal: 'Normal', dry: 'Kuru', oily: 'Yağlı', combination: 'Karma' } as const;
export type SkinTypeId = keyof typeof SKIN_TYPE_LABELS;
export type SkinViewId = 'overview' | SkinRegionId;
export const SKIN_VIEW_ORDER: SkinViewId[] = ['overview', ...REGION_ORDER];
/** Display known criteria from the current UTF-8 dictionary. Never rewrite a
 * historical row or attempt a blanket encoding conversion of unknown text. */
function displayLabels(rows: SkinIndicator[], scope: 'regional'|'whole-face'): SkinIndicator[] {
  return rows.map(row => Object.prototype.hasOwnProperty.call(SIGN_LABELS,row.id)
    ? {...row,label:skinCriterionLabel(row.id,scope)} : row);
}
export type SkinOverview = {
  schemaVersion: 1; analysisId?: string; captureId: string; pose: 'FRONT';
  skinType: { value: SkinTypeId | null; quality: 'valid' | 'invalid' | 'insufficient'; confidence: number | null; methodVersion: string; modelHash: string | null; limitationCode: string | null; provider?:string;providerModelId?:string;inferenceKind?:'hosted'|'local-onnx';decisionVersion?:string;sourceModel?:string };
  indicators: SkinIndicator[]; normalizationVersion: string;
  modelInputTransform?:Record<string,number|string|boolean>|null;modelInference?:Record<string,Record<string,number|string>>;
  sourceTransform: { sourceWidth: number; sourceHeight: number; coordinateSpace: 'source-pixels' };
};
export function overviewFromResponse(response: AppearanceResponse): SkinOverview | undefined {
  if (!response.general) return;
  return { schemaVersion: 1, captureId: response.photoId, pose: 'FRONT',
    skinType: response.general.skinType, normalizationVersion: response.general.normalizationVersion,
    modelInputTransform:response.general.modelInputTransform,modelInference:response.general.modelInference,
    sourceTransform: { sourceWidth: response.sourceWidth, sourceHeight: response.sourceHeight, coordinateSpace: 'source-pixels' },
    indicators: response.general.measurements.map(value => ({ id: value.id, label: skinCriterionLabel(value.id,'whole-face'), score: value.value,
      reason: value.value === null ? 'Bu karede yeterli güvenilir ölçüm yok.' : 'Bu oturumun genel görünüm göstergesi.', method: value.methodVersion, unit: '%', sampleCount: value.evaluatedArea.analysisPixels || 0, appearance: value,
      measurement: { scope: 'whole-face', region: 'overview', methodVersion: value.methodVersion, modelHash: value.modelHash, unit: value.unit as import('./skinIndicators').SkinMeasurement['unit'], rawValue: value.value, confidence: null, quality: value.quality, validation: 'appearance-proxy', unavailableReason: value.limitationCode } })) };
}
export function validSkinOverview(value: SkinOverview | undefined, analysisId:string): boolean {
  if (!value || value.schemaVersion!==1 || value.analysisId!==analysisId || value.pose!=='FRONT' || !/^[a-f0-9]{64}$/.test(value.captureId)) return false;
  const type=value.skinType,ids=['tone','oil','redness','acne','sag','dry','lines','dark','bags'];
  if(!type||!['valid','invalid','insufficient'].includes(type.quality)||type.value!==null&&!(type.value in SKIN_TYPE_LABELS)||type.confidence!==null&&(!Number.isFinite(type.confidence)||type.confidence<0||type.confidence>1))return false;
  const hosted=type.inferenceKind==='hosted'&&type.provider==='roboflow'&&type.providerModelId==='skin-type-axavj/1'&&type.methodVersion==='hosted-roboflow-skin-type-axavj/1'&&type.modelHash===null;
  if(type.quality==='valid'?(type.value===null||!type.modelHash&&!hosted):type.value!==null)return false;
  return !!value.normalizationVersion && value.sourceTransform.coordinateSpace==='source-pixels' && value.sourceTransform.sourceWidth>=16 && value.sourceTransform.sourceHeight>=16 &&
    value.indicators.length===ids.length && ids.every(id=>{
      const rows=value.indicators.filter(r=>r.id===id);if(rows.length!==1)return false;
      const row=rows[0],m=row.measurement;
      return !!m && m.scope==='whole-face' && m.region==='overview' && !!m.methodVersion &&
        (row.score===null?m.quality!=='valid'&&!!m.unavailableReason:Number.isFinite(row.score)&&row.score>=0&&row.score<=100&&m.quality==='valid'&&m.rawValue===row.score);
    });
}
/** Older six-region records do not acquire invented overview measurements. */
export function skinViewOrder(result: { general?: SkinOverview } | null): SkinViewId[] {
  return result?.general ? SKIN_VIEW_ORDER : REGION_ORDER;
}
export function buildSkinViewModel(id: SkinViewId, result: any, demo = false): SkinRegionData {
  if (id !== 'overview') {
    const region = buildSkinRegionViewModel(id, result, demo);
    // Historical numeric records can predate schemaVersion 3. Preserve their
    // actual regional rows without inventing an overview or changing units.
    return { ...region, ...(Array.isArray(result?.indicators?.[id]) ? { indicators: displayLabels(result.indicators[id],'regional') } : {}),
      index: region.index + (result?.general ? 1 : 0), viewTotal: result?.general ? 7 : 6 };
  }
  return { ...SKIN_REGIONS.forehead, id: 'overview', index: 1, viewTotal: 7,
    nameTr: 'Genel Bakış', indicators: displayLabels(result?.general?.indicators || [],'whole-face'), skinType: result?.general?.skinType,
    badgeText: '', changePct: 0, isAttentionRequired: false, trend: [],
    observation: { headline: 'Genel Bakış', details: 'Bu oturumun ön pozundaki genel cilt görünümü.' } };
}
