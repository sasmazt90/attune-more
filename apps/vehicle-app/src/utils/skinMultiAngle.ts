import { FaceAlignment, ImageQuality, RegionMetrics, SkinAnalyzer, SkinCapturePose, canCompareSkinReference } from './skinAnalyzer';

export const SKIN_ANGLES = ['FRONT', 'RIGHT', 'LEFT'] as const;
export type SkinAngle = typeof SKIN_ANGLES[number];
export const ANGLE_LABELS = { FRONT: 'Ön', RIGHT: 'Anatomik sağ', LEFT: 'Anatomik sol' };
export interface AngleCapture {
  indicators?:import('./skinIndicators').SkinIndicators;
  angle: SkinAngle; pose: SkinCapturePose; quality: ImageQuality;
  regions: Record<string, RegionMetrics>; frameToken: string;
}
export interface MultiAngleReference {
  schemaVersion: 2; scope: 'three-angle-v2'; id: string; timestamp: string;
  captures: Record<SkinAngle, AngleCapture>;
}
// Camera pixels are unmirrored. Positive yaw means nose toward raw image right,
// i.e. the participant's anatomical LEFT. CSS preview mirroring never changes this sign.
export function matchesSkinAngle(a: FaceAlignment, angle: SkinAngle): boolean {
  if (!a.faceDetected || !a.isMediaPipeActive || ![a.yaw, a.pitch, a.roll, a.scaleRatio].every(Number.isFinite)) return false;
  const actualScale = a.landmarks?.length ? Math.max(...a.landmarks.map(p => p.x)) - Math.min(...a.landmarks.map(p => p.x)) : a.scaleRatio;
  if ((a.sourceFramed===undefined ? actualScale < .28 || actualScale > .68 : !a.sourceFramed) || Math.abs(a.pitch) > .22 || Math.abs(a.roll) > .15) return false;
  return angle === 'FRONT' ? Math.abs(a.yaw) <= .20 : angle === 'RIGHT' ? a.yaw <= -.28 && a.yaw >= -.65 : a.yaw >= .28 && a.yaw <= .65;
}
export function angleGuidance(a: FaceAlignment, angle: SkinAngle): string {
  if (!a.faceDetected) return 'Yüz algılanamadı. Kameranın karşısına geçin.';
  if (a.sourceFramed===false) return 'Alın ve çeneniz dahil yüzünüz kamera görüntüsünde olsun';
  if (a.sourceFramed===undefined&&a.scaleRatio < .28) return 'Lütfen kameraya biraz yaklaşın';
  if (a.sourceFramed===undefined&&a.scaleRatio > .68) return 'Lütfen biraz geriye çekilin';
  if (Math.abs(a.pitch) > .22 || Math.abs(a.roll) > .15) return 'Başınızı dik tutun; yukarı veya aşağı eğmeyin.';
  if (matchesSkinAngle(a, angle)) return 'Poz uygun. Lütfen sabit durun...';
  if (angle === 'FRONT') return 'Doğrudan kameraya bakın.';
  return angle === 'RIGHT' ? 'Başınızı kendi sağınıza çevirin; çok yan dönmeden sol yanağınızı kameraya gösterin.' : 'Başınızı kendi solunuza çevirin; çok yan dönmeden sağ yanağınızı kameraya gösterin.';
}
export async function captureSkinAngle(ctx: CanvasRenderingContext2D, a: FaceAlignment, quality: ImageQuality, angle: SkinAngle, prior: Partial<Record<SkinAngle, AngleCapture>>): Promise<AngleCapture> {
  if (!matchesSkinAngle(a, angle) || !quality.isValid) throw new Error('INVALID_ANGLE');
  const pixels = ctx.getImageData(0, 0, ctx.canvas.width, ctx.canvas.height);
  const digest = await crypto.subtle.digest('SHA-256', pixels.data);
  const frameToken = Array.from(new Uint8Array(digest)).map(v => v.toString(16).padStart(2, '0')).join('');
  if (Object.values(prior).some(c => c?.frameToken === frameToken)) throw new Error('DUPLICATE_FRAME');
  // Side captures only measure the exposed cheek; occluded regions are never inferred.
  const ids = angle === 'FRONT' ? undefined : [angle === 'RIGHT' ? 'leftCheek' : 'rightCheek'];
  const regions = SkinAnalyzer.analyzeRegions(ctx, ctx.canvas.width, ctx.canvas.height, a, ids);
  return { angle, frameToken, regions, quality, pose: { yaw: a.yaw, pitch: a.pitch, roll: a.roll, scaleRatio: a.scaleRatio } };
}
export function compareMultiAngle(current: MultiAngleReference, prior: MultiAngleReference | null) {
  const hasReference = prior !== null;
  if (prior && (prior.schemaVersion !== 2 || prior.scope !== 'three-angle-v2' || !SKIN_ANGLES.every(angle => prior.captures?.[angle]?.angle === angle))) throw new Error('INVALID_REFERENCE');
  const regions: Record<string, RegionMetrics> = {};
  const unavailable: SkinAngle[] = [];
  const reasons: ('legacy-quality-missing'|'capture-conditions-incompatible')[] = [];
  for (const angle of SKIN_ANGLES) {
    const capture = current.captures[angle], base = prior?.captures[angle];
    const comparable = base && canCompareSkinReference({ id: prior!.id, timestamp: prior!.timestamp, schemaVersion: 1, scope: 'single-front-v1', quality: base.quality, pose: base.pose }, capture.quality, capture.pose);
    if (hasReference && !comparable) { unavailable.push(angle); reasons.push(!base?.quality || !base?.pose ? 'legacy-quality-missing' : 'capture-conditions-incompatible'); }
    const compared = SkinAnalyzer.compareWithBaseline(capture.regions, comparable ? base!.regions : null);
    // Front measurements for the remaining four regions, cheeks from their exposed side poses.
    for (const [id, metrics] of Object.entries(compared.comparedRegions)) {
      if (angle === 'FRONT' && ['leftCheek', 'rightCheek'].includes(id)) continue;
      regions[id] = metrics;
    }
  }
  let highestChangeRegion = '', highestChangePct = 0;
  for (const region of Object.values(regions)) if (Math.abs(region.changeFromBaselinePct || 0) > Math.abs(highestChangePct)) { highestChangeRegion = region.nameTr; highestChangePct = region.changeFromBaselinePct!; }
  return { regions, unavailable, reasons: [...new Set(reasons)], highestChangeRegion, highestChangePct, referralSuggested: Math.abs(highestChangePct) >= 20 };
}
