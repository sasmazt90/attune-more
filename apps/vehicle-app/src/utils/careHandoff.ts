/** A pending question, never evidence of a booking. Survives native WebView recreation. */
export const CARE_HANDOFF_KEY = 'attune.care.handoff.v1';
const MAX_AGE_MS = 24 * 60 * 60 * 1000;
export interface CareHandoff {
  specialty: string;
  providerName: string;
  sourceType?: string;
}

export function clearCareHandoff(): void {
  try { localStorage.removeItem(CARE_HANDOFF_KEY); } catch { /* Storage may be unavailable. */ }
}

export function writeCareHandoff(provider: CareHandoff, now = Date.now()): void {
  try {
    // Do not retain appointment times, referral health details or the external URL.
    localStorage.setItem(CARE_HANDOFF_KEY, JSON.stringify({
      specialty: provider.specialty, providerName: provider.providerName,
      sourceType: provider.sourceType, openedAt: now,
    }));
  } catch { /* The current page can still show the return question. */ }
}

export function readCareHandoff(now = Date.now()): CareHandoff | null {
  try {
    const raw = localStorage.getItem(CARE_HANDOFF_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || typeof value.specialty !== 'string' || typeof value.providerName !== 'string'
        || (value.sourceType !== undefined && typeof value.sourceType !== 'string')
        || !Number.isFinite(value.openedAt) || now < value.openedAt || now - value.openedAt > MAX_AGE_MS) {
      clearCareHandoff(); return null;
    }
    return {specialty: value.specialty, providerName: value.providerName, sourceType: value.sourceType};
  } catch { return null; }
}
