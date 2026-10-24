import { FaceAlignment, ImageQuality, RegionMetrics, SkinAnalyzer, SkinCapturePose, canCompareSkinReference, detectCameraMirrored } from './skinAnalyzer';
import type { SkinIndicators } from './skinIndicators';
import type { SkinOverview, SkinTypeId } from './skinOverview';

export const SKIN_ANGLES = ['FRONT', 'RIGHT', 'LEFT'] as const;
export type SkinAngle = typeof SKIN_ANGLES[number];
export const ANGLE_LABELS = { FRONT: 'Ön', RIGHT: 'Anatomik sağ', LEFT: 'Anatomik sol' };

export const SKIN_FRONT_MAX_YAW_DEG = 12;
export const SKIN_SIDE_MIN_YAW_DEG = 10.5;
export const SKIN_SIDE_MAX_YAW_DEG = 45;
export const SKIN_MAX_PITCH_DEG = 18;
export const SKIN_MAX_ROLL_DEG = 15;

export const OIL_POSITIVE_MIN = 2.0;
export const OIL_NEGATIVE_MAX = 1.0;
export const DRY_POSITIVE_MIN = 2.0;
export const DRY_NEGATIVE_MAX = 1.0;
export const MIN_ANALYSIS_PIXELS = 100;
export const DEFAULT_ACCEPTED_NEGATIVE_METHODS = [
  'appearance-cv-6',
  'appearance-native-dry-2',
  'appearance-native-dry-3',
  'preserved'
] as const;

export interface AngleCapture {
  indicators?: import('./skinIndicators').SkinIndicators;
  angle: SkinAngle;
  pose: SkinCapturePose;
  cameraMirrored?: boolean | null;
  cameraMirrorStatus?: 'canvas-mirrored' | 'not-measured-driver-level';
  quality: ImageQuality;
  regions: Record<string, RegionMetrics>;
  frameToken: string;
}
export interface MultiAngleReference {
  schemaVersion: 2;
  scope: 'three-angle-v2';
  id: string;
  timestamp: string;
  captures: Record<SkinAngle, AngleCapture>;
}

export function skinPoseRotation(
  a: FaceAlignment | undefined | null
): {
  yawDeg: number;
  pitchDeg: number;
  rollDeg: number;
  cameraMirrored: boolean | null;
  cameraMirrorStatus: 'canvas-mirrored' | 'not-measured-driver-level';
} | null {
  const m = a?.faceTransform;
  if (!Array.isArray(m) || m.length < 16 || !m.slice(0, 16).every(Number.isFinite)) return null;
  if (![m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10]].every(v => Math.abs(v) <= 1.05)) return null;
  const yawDeg = Math.round(((Math.atan2(m[8], m[10]) * 180) / Math.PI) * 100) / 100;
  const pitchDeg = Math.round(((Math.asin(Math.max(-1, Math.min(1, -m[9]))) * 180) / Math.PI) * 100) / 100;
  const rollDeg = Math.round(((Math.atan2(m[1], m[5]) * 180) / Math.PI) * 100) / 100;
  const cameraMirrored = a?.cameraMirrored !== undefined ? a.cameraMirrored : detectCameraMirrored(null, null, m);
  const cameraMirrorStatus = cameraMirrored === true ? 'canvas-mirrored' : 'not-measured-driver-level';
  return { yawDeg, pitchDeg, rollDeg, cameraMirrored, cameraMirrorStatus };
}

export function hasTargetCheekVisibility(a: FaceAlignment, angle: SkinAngle): boolean {
  const lms = a.landmarks;
  if (!lms || lms.length < 468) return true;
  // RIGHT head turn exposes anatomical leftCheek; LEFT head turn exposes anatomical rightCheek.
  const indices =
    angle === 'RIGHT'
      ? [266, 330, 347, 346, 352, 411, 425, 280]
      : angle === 'LEFT'
      ? [36, 101, 118, 117, 123, 187, 205, 50]
      : [10, 152, 36, 266];
  const pts = indices.map(i => lms[i]).filter(Boolean);
  if (pts.length < 4) return false;
  const xs = pts.map(p => p.x);
  const ys = pts.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  return minX >= 0.01 && maxX <= 0.99 && minY >= 0.01 && maxY <= 0.99 && (maxX - minX) >= 0.025 && (maxY - minY) >= 0.025;
}

// Camera pixels are unmirrored. Positive yaw means nose toward raw image right,
// i.e. the participant's anatomical LEFT (exposing the right cheek). CSS preview mirroring never changes this sign.
// Preserves all poses accepted by 7463eef/51ab991 (|a.yaw| >= 0.25 or |rot.yawDeg| >= 10.5°) while expanding the upper bound to 45°.
export function matchesSkinAngle(a: FaceAlignment, angle: SkinAngle): boolean {
  if (!a.faceDetected || !a.isMediaPipeActive || ![a.yaw, a.pitch, a.roll, a.scaleRatio].every(Number.isFinite)) return false;
  const actualScale = a.landmarks?.length
    ? Math.max(...a.landmarks.map(p => p.x)) - Math.min(...a.landmarks.map(p => p.x))
    : a.scaleRatio;
  if (a.sourceFramed === undefined ? actualScale < 0.28 || actualScale > 0.68 : !a.sourceFramed) return false;

  const rot = skinPoseRotation(a);
  if (rot) {
    if (Math.abs(rot.pitchDeg) > SKIN_MAX_PITCH_DEG || Math.abs(rot.rollDeg) > SKIN_MAX_ROLL_DEG) return false;
    if (angle === 'FRONT') return Math.abs(rot.yawDeg) <= SKIN_FRONT_MAX_YAW_DEG && Math.abs(a.yaw) <= 0.20;
    if (angle === 'RIGHT') {
      return (rot.yawDeg <= -SKIN_SIDE_MIN_YAW_DEG || a.yaw <= -0.25) && rot.yawDeg >= -SKIN_SIDE_MAX_YAW_DEG && a.yaw >= -1.15;
    }
    return (rot.yawDeg >= SKIN_SIDE_MIN_YAW_DEG || a.yaw >= 0.25) && rot.yawDeg <= SKIN_SIDE_MAX_YAW_DEG && a.yaw <= 1.15;
  }

  if (Math.abs(a.pitch) > 0.22 || Math.abs(a.roll) > 0.15) return false;
  return angle === 'FRONT'
    ? Math.abs(a.yaw) <= 0.20
    : angle === 'RIGHT'
    ? a.yaw <= -0.25 && a.yaw >= -1.15
    : a.yaw >= 0.25 && a.yaw <= 1.15;
}

export function angleGuidance(a: FaceAlignment, angle: SkinAngle): string {
  if (!a.faceDetected) return 'Yüz algılanamadı. Kameranın karşısına geçin.';
  if (a.sourceFramed === false) return 'Alın ve çeneniz dahil yüzünüz kamera görüntüsünde olsun';
  if (a.sourceFramed === undefined && a.scaleRatio < 0.28) return 'Lütfen kameraya biraz yaklaşın';
  if (a.sourceFramed === undefined && a.scaleRatio > 0.68) return 'Lütfen biraz geriye çekilin';
  const rot = skinPoseRotation(a);
  if (rot ? Math.abs(rot.pitchDeg) > SKIN_MAX_PITCH_DEG || Math.abs(rot.rollDeg) > SKIN_MAX_ROLL_DEG : Math.abs(a.pitch) > 0.22 || Math.abs(a.roll) > 0.15) {
    return 'Başınızı dik tutun; yukarı veya aşağı eğmeyin.';
  }
  if (matchesSkinAngle(a, angle)) return 'Poz uygun. Lütfen sabit durun...';
  if (angle === 'FRONT') return 'Doğrudan kameraya bakın.';
  if ((rot && Math.abs(rot.yawDeg) > SKIN_SIDE_MAX_YAW_DEG) || (!rot && Math.abs(a.yaw) > 1.15)) {
    return 'Başınızı çok fazla çevirdiniz; kameraya biraz geri dönün (12°–45°).';
  }
  return angle === 'RIGHT'
    ? 'Sol yanağınızı kameraya göstermek için başınızı hafifçe sağa çevirin (12°–45°).'
    : 'Sağ yanağınızı kameraya göstermek için başınızı hafifçe sola çevirin (12°–45°).';
}

export async function captureSkinAngle(
  ctx: CanvasRenderingContext2D,
  a: FaceAlignment,
  quality: ImageQuality,
  angle: SkinAngle,
  prior: Partial<Record<SkinAngle, AngleCapture>>
): Promise<AngleCapture> {
  if (!matchesSkinAngle(a, angle) || !quality.isValid) throw new Error('INVALID_ANGLE');
  const pixels = ctx.getImageData(0, 0, ctx.canvas.width, ctx.canvas.height);
  const digest = await crypto.subtle.digest('SHA-256', pixels.data);
  const frameToken = Array.from(new Uint8Array(digest))
    .map(v => v.toString(16).padStart(2, '0'))
    .join('');
  if (Object.values(prior).some(c => c?.frameToken === frameToken)) throw new Error('DUPLICATE_FRAME');
  // Side captures only measure the exposed cheek; occluded regions are never inferred.
  const ids = angle === 'FRONT' ? undefined : [angle === 'RIGHT' ? 'leftCheek' : 'rightCheek'];
  const regions = SkinAnalyzer.analyzeRegions(ctx, ctx.canvas.width, ctx.canvas.height, a, ids);
  const rot = skinPoseRotation(a);
  const cameraMirrored = rot ? rot.cameraMirrored : detectCameraMirrored(null, ctx, a.faceTransform);
  const cameraMirrorStatus = cameraMirrored === true ? 'canvas-mirrored' : 'not-measured-driver-level';
  return {
    angle,
    frameToken,
    regions,
    quality,
    cameraMirrored,
    cameraMirrorStatus,
    pose: {
      yaw: a.yaw,
      pitch: a.pitch,
      roll: a.roll,
      scaleRatio: a.scaleRatio,
      ...(rot ? { yawDeg: rot.yawDeg, pitchDeg: rot.pitchDeg, rollDeg: rot.rollDeg } : {})
    }
  };
}

export function compareMultiAngle(current: MultiAngleReference, prior: MultiAngleReference | null) {
  const hasReference = prior !== null;
  if (
    prior &&
    (prior.schemaVersion !== 2 ||
      prior.scope !== 'three-angle-v2' ||
      !SKIN_ANGLES.every(angle => prior.captures?.[angle]?.angle === angle))
  ) {
    throw new Error('INVALID_REFERENCE');
  }
  const regions: Record<string, RegionMetrics> = {};
  const unavailable: SkinAngle[] = [];
  const reasons: ('legacy-quality-missing' | 'capture-conditions-incompatible')[] = [];
  for (const angle of SKIN_ANGLES) {
    const capture = current.captures[angle],
      base = prior?.captures[angle];
    const comparable =
      base &&
      canCompareSkinReference(
        { id: prior!.id, timestamp: prior!.timestamp, schemaVersion: 1, scope: 'single-front-v1', quality: base.quality, pose: base.pose },
        capture.quality,
        capture.pose
      );
    if (hasReference && !comparable) {
      unavailable.push(angle);
      reasons.push(!base?.quality || !base?.pose ? 'legacy-quality-missing' : 'capture-conditions-incompatible');
    }
    const compared = SkinAnalyzer.compareWithBaseline(capture.regions, comparable ? base!.regions : null);
    // Front measurements for the remaining four regions, cheeks from their exposed side poses.
    for (const [id, metrics] of Object.entries(compared.comparedRegions)) {
      if (angle === 'FRONT' && ['leftCheek', 'rightCheek'].includes(id)) continue;
      regions[id] = metrics;
    }
  }
  let highestChangeRegion = '',
    highestChangePct = 0;
  for (const region of Object.values(regions)) {
    if (Math.abs(region.changeFromBaselinePct || 0) > Math.abs(highestChangePct)) {
      highestChangeRegion = region.nameTr;
      highestChangePct = region.changeFromBaselinePct!;
    }
  }
  return {
    regions,
    unavailable,
    reasons: [...new Set(reasons)],
    highestChangeRegion,
    highestChangePct,
    referralSuggested: Math.abs(highestChangePct) >= 20
  };
}

/**
 * Recompute regional skin-type map and whole-face skinType decision from 3-angle fused indicators:
 * - T-zone (`forehead`, `nose`, `chin`) from `FRONT`
 * - `rightCheek` from `LEFT`
 * - `leftCheek` from `RIGHT`
 * Preserves each region's `sourcePose` and `sourcePhotoId`, never uses redness as sensitivity,
 * and never leaks the global ViT prediction when regional evidence is incomplete or mixed.
 */
export function fuseMultiAngleSkinOverview(
  frontGeneral: SkinOverview | undefined,
  indicators: SkinIndicators,
  captures: Partial<Record<SkinAngle, { captureId?: string; photoId?: string; pose?: string }>>,
  acceptedNegativeMethods: string[] = [...DEFAULT_ACCEPTED_NEGATIVE_METHODS]
): SkinOverview | undefined {
  if (!frontGeneral || !frontGeneral.skinType) return frontGeneral;
  const REGIONS = ['forehead', 'nose', 'chin', 'leftCheek', 'rightCheek'] as const;
  const TZONE_REGIONS = ['forehead', 'nose', 'chin'] as const;
  const negSet = new Set(acceptedNegativeMethods);

  const poseForRegion: Record<(typeof REGIONS)[number], SkinAngle> = {
    forehead: 'FRONT',
    nose: 'FRONT',
    chin: 'FRONT',
    rightCheek: 'LEFT',
    leftCheek: 'RIGHT'
  };

  const regTrace: Record<string, any> = {};
  const vals: Record<string, { oil: number | null; dry: number | null }> = {};

  for (const rName of REGIONS) {
    const rows = indicators[rName] || [];
    const oilRow = rows.find(r => r.id === 'oil');
    const dryRow = rows.find(r => r.id === 'dry');
    const oilApp = oilRow?.appearance;
    const dryApp = dryRow?.appearance;

    const extractVal = (row: typeof oilRow, key: 'oil' | 'dry') => {
      if (!row) return { val: null as number | null, meta: { value: null, quality: 'insufficient', limitationCode: 'METRIC_MISSING' } };
      const app = row.appearance;
      const m = row.measurement;
      const v = app ? app.value : row.score;
      const q = app ? app.quality : m?.quality;
      const ap = app?.evaluatedArea?.analysisPixels ?? row.sampleCount ?? 0;
      const sp = app?.evaluatedArea?.sourcePixels ?? row.sampleCount ?? 0;
      if (q === 'valid' && typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 100 && ap >= MIN_ANALYSIS_PIXELS && sp > 0) {
        if (key === 'oil' && rName === 'nose' && app?.evaluatedArea) {
          if ((app.evaluatedArea.foreheadSourcePixels ?? 1) <= 0 || (app.evaluatedArea.noseSourcePixels ?? 1) <= 0) {
            return { val: null, meta: { value: null, quality: 'insufficient', limitationCode: 'TZONE_SUBREGION_MISSING' } };
          }
        }
        return {
          val: v,
          meta: {
            value: v,
            quality: 'valid',
            limitationCode: app?.limitationCode ?? null,
            methodVersion: app?.methodVersion ?? m?.methodVersion ?? row.method,
            normalizationVersion: app?.normalizationVersion ?? null,
            evaluatedArea: app?.evaluatedArea ?? { analysisPixels: ap, sourcePixels: sp }
          }
        };
      }
      return {
        val: null,
        meta: {
          value: null,
          quality: q || 'insufficient',
          limitationCode: app?.limitationCode ?? m?.unavailableReason ?? 'METRIC_UNAVAILABLE',
          methodVersion: app?.methodVersion ?? m?.methodVersion ?? row.method
        }
      };
    };

    const oilEx = extractVal(oilRow, 'oil');
    const dryEx = extractVal(dryRow, 'dry');
    const oil = oilEx.val;
    const dry = dryEx.val;
    vals[rName] = { oil, dry };

    const oilMethod = String(oilEx.meta.methodVersion || '');
    const dryMethod = String(dryEx.meta.methodVersion || '');
    const negOk = negSet.has(oilMethod) && negSet.has(dryMethod);

    let state: string | null = null;
    let reason = 'MISSING_OIL_OR_DRY_MEASUREMENT';
    if (oil !== null && dry !== null) {
      if (oil >= OIL_POSITIVE_MIN && dry >= DRY_POSITIVE_MIN) {
        state = 'unknown';
        reason = 'CONFLICTING_OIL_AND_DRY_POSITIVE';
      } else if ((oil > OIL_NEGATIVE_MAX && oil < OIL_POSITIVE_MIN) || (dry > DRY_NEGATIVE_MAX && dry < DRY_POSITIVE_MIN)) {
        state = 'unknown';
        reason = 'INTERMEDIATE_BAND_UNKNOWN';
      } else if (oil >= OIL_POSITIVE_MIN) {
        state = 'oily';
        reason = 'OIL_AT_OR_ABOVE_UNCALIBRATED_THRESHOLD';
      } else if (dry >= DRY_POSITIVE_MIN) {
        state = 'dry';
        reason = 'DRY_AT_OR_ABOVE_UNCALIBRATED_THRESHOLD';
      } else if (negOk) {
        state = 'normal';
        reason = 'CONFIRMED_BELOW_NEGATIVE_THRESHOLDS';
      } else {
        state = 'unevaluated';
        reason = 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED';
      }
    }

    const expectedPose = poseForRegion[rName];
    const capMeta = captures?.[expectedPose];
    const sourcePhotoId =
      (oilApp as any)?.photoId ||
      oilApp?.localMap?.photoId ||
      (dryApp as any)?.photoId ||
      dryApp?.localMap?.photoId ||
      capMeta?.captureId ||
      capMeta?.photoId ||
      null;
    const sourcePose = (oilApp as any)?.capturePose || (dryApp as any)?.capturePose || capMeta?.pose || expectedPose;

    regTrace[rName] = {
      oil: oil !== null ? oilEx.meta : null,
      dry: dry !== null ? dryEx.meta : null,
      inputs: { oil: oilEx.meta, dry: dryEx.meta },
      state,
      reason,
      negativeEvidenceAccepted: negOk,
      sourcePose,
      sourcePhotoId
    };
  }

  const tMeasured = TZONE_REGIONS.every(r => vals[r].oil !== null && vals[r].dry !== null);
  const tStates = TZONE_REGIONS.map(r => regTrace[r].state);
  const tValid = tMeasured && tStates.every(s => ['oily', 'dry', 'normal', 'unevaluated'].includes(s));
  const tOilyRegions = TZONE_REGIONS.filter(r => regTrace[r].state === 'oily');
  const tOily =
    tValid &&
    tOilyRegions.length >= 2 &&
    tOilyRegions.some(r => r === 'forehead' || r === 'nose');
  const tOilMean = tMeasured ? Math.round(((vals.forehead.oil! + vals.nose.oil! + vals.chin.oil!) / 3) * 100) / 100 : null;

  const cheekMeasured = vals.leftCheek.oil !== null && vals.leftCheek.dry !== null && vals.rightCheek.oil !== null && vals.rightCheek.dry !== null;
  const cheekComplete = cheekMeasured && regTrace.leftCheek.state !== null && regTrace.rightCheek.state !== null;
  const cheekNonOily =
    cheekComplete &&
    vals.leftCheek.oil! <= OIL_NEGATIVE_MAX &&
    vals.rightCheek.oil! <= OIL_NEGATIVE_MAX &&
    ['normal', 'dry'].includes(regTrace.leftCheek.state) &&
    ['normal', 'dry'].includes(regTrace.rightCheek.state) &&
    (regTrace.leftCheek.negativeEvidenceAccepted || regTrace.leftCheek.state === 'dry') &&
    (regTrace.rightCheek.negativeEvidenceAccepted || regTrace.rightCheek.state === 'dry');

  const allMeasured = tMeasured && cheekMeasured;
  const states = REGIONS.map(r => regTrace[r].state);
  const hasUnknown = states.some(s => s === 'unknown');
  const hasUnevaluated = states.some(s => s === 'unevaluated');
  const complete = allMeasured && !hasUnknown && !hasUnevaluated;
  const comb = allMeasured && !hasUnknown && tOily && cheekNonOily;

  let finalValue: SkinTypeId | null = null;
  let finalQuality: 'valid' | 'insufficient' | 'invalid' = 'insufficient';
  let limitationCode: string | null = null;
  let displayValue: string | null = null;
  let applied = false;

  if (!cheekMeasured) {
    limitationCode = 'INCOMPLETE_CHEEKS_UNVERIFIED';
    displayValue = 'Belirsiz (Yanak verisi eksik)';
  } else if (!tMeasured) {
    limitationCode = 'INCOMPLETE_TZONE_UNVERIFIED';
    displayValue = 'Belirsiz (T-bölgesi verisi eksik)';
  } else if (hasUnknown) {
    limitationCode = 'INTERMEDIATE_BAND_UNDETERMINED';
    displayValue = 'Belirlenemedi (Ara sinyal bandı)';
  } else if (comb) {
    finalValue = 'combination';
    finalQuality = 'valid';
    applied = true;
    limitationCode = 'DERIVED_REGIONAL_RULE_CONFIDENCE_NOT_APPLICABLE';
  } else {
    const oilyCount = states.filter(s => s === 'oily').length;
    const dryCount = states.filter(s => s === 'dry').length;
    const normalCount = states.filter(s => s === 'normal').length;
    if (oilyCount === REGIONS.length) {
      finalValue = 'oily';
      finalQuality = 'valid';
      applied = true;
    } else if (dryCount === REGIONS.length) {
      finalValue = 'dry';
      finalQuality = 'valid';
      applied = true;
    } else if (normalCount === REGIONS.length) {
      finalValue = 'normal';
      finalQuality = 'valid';
      applied = true;
    } else if (hasUnevaluated && oilyCount === 0 && dryCount === 0) {
      limitationCode = 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED';
      displayValue = 'Değerlendirilmedi';
    } else {
      limitationCode = 'MIXED_REGIONAL_PATTERN_UNDETERMINED';
      displayValue = 'Karışık desen (Belirlenemedi)';
    }
  }

  const priorTrace = frontGeneral.skinType.decisionTrace || {};
  const updatedTrace = {
    ...priorTrace,
    applied,
    complete,
    combinationMatched: comb,
    finalValue,
    displayValue,
    tZoneOily: tOily,
    tZoneValid: tValid,
    tZoneOilySubregions: tOilyRegions,
    cheekComplete,
    cheekNonOily,
    limitationCode,
    thresholds: {
      status: 'uncalibrated-hypothesis',
      oilPositiveMin: OIL_POSITIVE_MIN,
      oilNegativeMax: OIL_NEGATIVE_MAX,
      dryPositiveMin: DRY_POSITIVE_MIN,
      dryNegativeMax: DRY_NEGATIVE_MAX,
      minAnalysisPixels: MIN_ANALYSIS_PIXELS,
      tZoneMinOilySubregions: 2,
      tZoneRequiresForeheadOrNose: true,
      negativeEvidenceMethods: [...negSet]
    },
    tZone: {
      valid: tValid,
      oily: tOily,
      state: tOily ? 'oily' : tValid && !hasUnevaluated ? 'non-oily' : 'unknown',
      oilyRegions: tOilyRegions,
      oilySubregions: tOilyRegions,
      meanOil: tOilMean
    },
    cheeks: {
      complete: cheekComplete,
      nonOily: cheekNonOily,
      leftState: regTrace.leftCheek.state,
      rightState: regTrace.rightCheek.state
    },
    regions: regTrace
  };

  const regionalSkinMap = {
    schemaVersion: 2,
    methodVersion: frontGeneral.skinType.methodVersion,
    complete,
    limitationCode,
    displayValue,
    thresholds: updatedTrace.thresholds,
    tZone: updatedTrace.tZone,
    cheeks: updatedTrace.cheeks,
    regions: Object.fromEntries(
      REGIONS.map(rName => [
        rName,
        {
          state: regTrace[rName].state || 'unknown',
          reason: regTrace[rName].reason,
          oil: vals[rName].oil,
          dry: vals[rName].dry,
          sourcePose: regTrace[rName].sourcePose,
          sourcePhotoId: regTrace[rName].sourcePhotoId
        }
      ])
    )
  };

  return {
    ...frontGeneral,
    skinType: {
      ...frontGeneral.skinType,
      value: finalValue,
      quality: finalQuality,
      confidence: null,
      limitationCode,
      ...(displayValue ? { displayValue } : {}),
      decisionTrace: updatedTrace
    } as any,
    regionalSkinMap
  };
}
