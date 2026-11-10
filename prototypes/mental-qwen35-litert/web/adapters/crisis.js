// Product crisis control, unchanged: checkCrisisTrigger compiled from packages/safety/crisisDetector.ts
// (generated/crisisDetector.js, source hashes in generated/crisisDetector.sources.sha256). The emergency text is
// translated with the product's own message catalogue (shared/localization/messages.json), as the product's t() does.
import {checkCrisisTrigger} from '../generated/crisisDetector.js';
export function makeCrisis(lang, messages) {
  const byTr = new Map(Object.values(messages).map(m => [m.tr, m]));
  return (text, moving) => {
    const r = checkCrisisTrigger(text, moving);
    if (!r.isCrisis) return {isCrisis: false};
    const entry = byTr.get(r.emergencyResponseTr);
    const emergencyText = lang === 'tr' ? r.emergencyResponseTr : (entry && entry[lang]) || r.emergencyResponseTr;
    return {isCrisis: true, emergencyText, translated: lang === 'tr' || !!(entry && entry[lang])};
  };
}
