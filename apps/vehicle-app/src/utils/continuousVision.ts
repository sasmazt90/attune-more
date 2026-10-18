/** Screen coordinates: 0 points right, 90 down; clockwise, never quantized.
 * Descriptive orientation task, NOT an acuity/clinical threshold estimator.
 * Legacy visionEngine.ts is deliberately retained under its original contract.
 */
export const CONTINUOUS_VISION_PROTOCOL = 'landolt-orientation-guided-v2' as const;
export const CALIBRATION_KEY = 'attune_manual_screen_scale_v1';
export type VisionEye = 'RIGHT' | 'LEFT' | 'BOTH';
export function normalizeAngle(value: number): number {
  if (!Number.isFinite(value)) throw new Error('Geçersiz açı');
  return ((value % 360) + 360) % 360;
}
export function circularError(target: number, response: number): number {
  const difference = Math.abs(normalizeAngle(target) - normalizeAngle(response));
  return Math.min(difference, 360 - difference);
}
export function randomAngle(): number {
  const value = new Uint32Array(1); crypto.getRandomValues(value);
  return value[0] / 4294967296 * 360;
}
export interface ScreenContext { width: number; height: number; dpr: number; viewportScale: number }
export interface ScreenCalibration { version: 1; method: 'manual-card'; pixelsPerMm: number; context: ScreenContext; calibratedAt: string }
export function screenContext(): ScreenContext {
  return { width: screen.width, height: screen.height, dpr: window.devicePixelRatio, viewportScale: window.visualViewport?.scale ?? 1 };
}
export function calibrationMatches(calibration: ScreenCalibration | null, context: ScreenContext): boolean {
  return !!calibration && calibration.version === 1 && calibration.method === 'manual-card' &&
    Number.isFinite(calibration.pixelsPerMm) && calibration.pixelsPerMm > 0 &&
    Object.entries(context).every(([key, value]) => calibration.context?.[key as keyof ScreenContext] === value);
}
export interface VisionConditions {
  observedAt: number; modelActive: boolean; cameraLive: boolean; faceCount: number;
  qualityValid: boolean; positionValid: boolean; relativeScaleChange: number | null;
  eye: VisionEye; eyeEvidence: 'unsupported' | 'wrong-eye' | 'both-open' | 'uncertain';
}
export function conditionFailure(conditions: VisionConditions | null, now: number): string | null {
  if (!conditions || now - conditions.observedAt > 750 || now < conditions.observedAt) return 'Kamera değerlendirmesi güncel değil. Sabit durun.';
  if (!conditions.cameraLive) return 'Kamera bağlantısı kesildi.';
  if (!conditions.modelActive) return 'Yüz değerlendirmesi kullanılamıyor.';
  if (conditions.faceCount !== 1) return 'Kadrajda yalnız bir yüz bulunmalı.';
  if (!conditions.qualityValid) return 'Işığı ve görüntü netliğini düzeltin.';
  if (!conditions.positionValid) return 'Başınızı karşıya hizalayın ve kadrajda kalın.';
  if (conditions.relativeScaleChange === null || !Number.isFinite(conditions.relativeScaleChange) || Math.abs(conditions.relativeScaleChange) > .08) return 'Başlangıç konumunuza dönün. Mutlak mesafe ölçülmüyor.';
  if (conditions.eyeEvidence === 'wrong-eye') return 'İstenen göz koşulu sağlanmıyor.';
  if (conditions.eyeEvidence === 'both-open') return 'Tek göz ölçümü için diğer gözün kapatılması gerekiyor.';
  // Unknown optical occlusion is metadata, not an automatic camera failure.
  // This guided descriptive task never claims camera-certified occlusion.
  return null;
}
export function eyeInstruction(eye: VisionEye): string {
  return eye === 'RIGHT' ? 'Sağ gözünüzle bakın; sol gözünüzü opak bir kapatıcıyla, baskı uygulamadan örtün.'
    : eye === 'LEFT' ? 'Sol gözünüzle bakın; sağ gözünüzü opak bir kapatıcıyla, baskı uygulamadan örtün.'
    : 'Kontrast denemelerinde iki gözünüz açık olsun.';
}
export interface ContinuousTrial {
  protocolVersion: typeof CONTINUOUS_VISION_PROTOCOL; targetAngle: number; responseAngle: number | null;
  minimumCircularError: number | null; stimulusSizeMm: number; contrast: number; eye: VisionEye;
  visibility: 'visible' | 'not-visible'; responseMs: number; conditions: VisionConditions;
  eyeInstruction: string; eyeOcclusionVerification: 'not-camera-verified-user-instruction';
}
export function summarizeContinuousTrials(trials: ContinuousTrial[]) {
  const visible = trials.filter(t => t.visibility === 'visible');
  const errors = visible.map(t => t.minimumCircularError).filter((n): n is number => typeof n === 'number' && Number.isFinite(n));
  return { validTrials: trials.length, visible: visible.length, notVisible: trials.length-visible.length,
    meanAngularError: errors.length ? errors.reduce((a,b)=>a+b,0)/errors.length : null,
    acuityStatus: 'Görme keskinliği bu protokolle hesaplanmadı' };
}
/** Engineering exploration schedule, not a calibrated psychometric staircase.
 * Each of three conditions has eight valid trials; no error becomes pass/fail.
 * Visibility failure makes the next stimulus larger/higher contrast; it remains
 * in the dataset. No stopping threshold, referral or guessing correction.
 */
export class ContinuousVisionSession {
  trials: ContinuousTrial[] = []; invalidPresentations = 0;
  presentationId = 0;
  targetAngle = randomAngle(); private presentedAt = performance.now(); private answered = false;
  stimulusSizeMm = 2; contrast = 1;
  get eye(): VisionEye { return this.trials.length < 8 ? 'RIGHT' : this.trials.length < 16 ? 'LEFT' : 'BOTH'; }
  get completed() { return this.trials.length === 24; }
  invalidate() { if (!this.answered) { this.invalidPresentations++; this.answered=true; } }
  present(now=performance.now()) { if (this.completed) return; this.presentationId++;this.targetAngle=randomAngle(); this.presentedAt=now; this.answered=false; }
  respond(responseAngle: number | null, interacted: boolean, conditions: VisionConditions, now: number): boolean {
    if (this.answered || this.completed || (!interacted && responseAngle !== null) || conditions.eye!==this.eye || conditionFailure(conditions,now)) return false;
    this.answered=true;
    const eye=this.eye;
    this.trials.push({ protocolVersion: CONTINUOUS_VISION_PROTOCOL, targetAngle: this.targetAngle,
      responseAngle: responseAngle===null?null:normalizeAngle(responseAngle), minimumCircularError:responseAngle===null?null:circularError(this.targetAngle,responseAngle),
      stimulusSizeMm:this.stimulusSizeMm,contrast:this.contrast,eye,visibility:responseAngle===null?'not-visible':'visible',responseMs:Math.max(0,now-this.presentedAt),conditions:{...conditions},
      eyeInstruction:eyeInstruction(eye),eyeOcclusionVerification:'not-camera-verified-user-instruction' });
    if (this.eye!==eye) { this.stimulusSizeMm=2; this.contrast=1; }
    else if (responseAngle===null) { if(eye==='BOTH') this.contrast=Math.min(1,this.contrast*2); else this.stimulusSizeMm*=1.25; }
    else if(eye==='BOTH') this.contrast/=1.25; else this.stimulusSizeMm/=1.25;
    return true;
  }
}
