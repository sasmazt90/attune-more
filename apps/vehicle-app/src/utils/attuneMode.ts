/**
 * Attune.more Runtime Mode & Storage Contract
 * Lisans: UNLICENSED
 * 
 * DEMO MODE vs REAL MODE kesin ayrımı:
 * - DEMO MODE: ?demo=1, ?demo=true, localStorage.attune_demo_mode === 'true' veya NEXT_PUBLIC_ATTUNE_DEMO_MODE=true
 * - REAL MODE: Gerçek kamera, MediaPipe analizi, canlı telemetri. Asla sahte sonuç üretmez.
 */

export const STORAGE_KEYS = {
  // Real Mode Keys
  LATEST_SKIN: 'togg_health_latest_skin',
  SKIN_BASELINE: 'togg_health_skin_baseline',
  SKIN_BASELINE_META: 'togg_health_skin_baseline_meta',
  SKIN_MULTI_BASELINE: 'togg_health_skin_multi_baseline_v2',
  SKIN_SIGNS_BASELINE: 'togg_health_skin_signs_baseline_v3',
  SKIN_SINGLE_SIGNS_BASELINE: 'togg_health_skin_single_signs_baseline_v3',
  SKIN_REMINDER: 'togg_health_skin_reminder',
  SKIN_HISTORY: 'togg_health_skin_history',
  LATEST_VISION: 'togg_health_latest_vision',
  LATEST_MENTAL: 'togg_health_latest_mental',
  MENTAL_HISTORY: 'togg_health_mental_history',
  REFERRAL_CONTEXT: 'togg_active_referral_context',

  // Demo Mode Keys
  DEMO_SKIN_RESULT: 'attune_demo_skin_result',
  DEMO_REFERRAL: 'attune_demo_referral_context',

  // App-Level Privacy Preferences
  PRIVACY_CAMERA_ALLOWED: 'attune_privacy_camera_allowed',
  PRIVACY_MIC_ALLOWED: 'attune_privacy_microphone_allowed',
  PRIVACY_MENTAL_SAVE_ALLOWED: 'togg_privacy_mental_summary_allowed',
  PRIVACY_MENTAL_TRANSCRIPT_ALLOWED: 'attune_privacy_mental_transcript_allowed',
  PRIVACY_VISION_SAVE_ALLOWED: 'attune_privacy_vision_save_allowed'
} as const;

export const SKIN_HOSTED_PROCESSING_PERMISSION='attune_privacy_skin_hosted_processing_allowed';
export function isSkinHostedProcessingAllowed():boolean {
  try{return typeof window!=='undefined'&&localStorage.getItem(SKIN_HOSTED_PROCESSING_PERMISSION)==='true';}catch{return false;}
}

export function isDemoMode(): boolean {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_ATTUNE_DEMO_MODE === 'true';
  }

  try {
    const params = new URLSearchParams(window.location.search);
    const demoParam = params.get('demo');
    if (demoParam === '1' || demoParam === 'true') {
      return true;
    }

    const storedDemo = localStorage.getItem('attune_demo_mode');
    if (storedDemo === 'true') {
      return true;
    }
  } catch {
    // SSR veya sandbox koruması
  }

  return process.env.NEXT_PUBLIC_ATTUNE_DEMO_MODE === 'true';
}

export function isCameraAllowed(): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(STORAGE_KEYS.PRIVACY_CAMERA_ALLOWED) !== 'false';
}

export function isMicrophoneAllowed(): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(STORAGE_KEYS.PRIVACY_MIC_ALLOWED) !== 'false';
}

export function isMentalSummarySavingAllowed(): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(STORAGE_KEYS.PRIVACY_MENTAL_SAVE_ALLOWED) !== 'false';
}

export function isMentalTranscriptSavingAllowed(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(STORAGE_KEYS.PRIVACY_MENTAL_TRANSCRIPT_ALLOWED) === 'true';
}

export function isVisionSavingAllowed(): boolean {
  return typeof window !== 'undefined' && localStorage.getItem(STORAGE_KEYS.PRIVACY_VISION_SAVE_ALLOWED) === 'true';
}
