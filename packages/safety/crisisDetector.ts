/**
 * Crisis Detector
 * Ruhsal iyi oluş seanslarında intihar, kendine zarar verme veya akut kriz durumlarını filtreler.
 */

export const CRISIS_KEYWORDS = [
  'suicide', 'suicidal', 'kill myself', 'hurt myself', 'end my life', 'want to die',
  "don't want to live", 'do not want to live', 'selbstmord', 'suizid',
  'mich umbringen', 'mir etwas antun', 'mir selbst schaden', 'nicht mehr leben', 'sterben will', 'will sterben',
  'intihar',
  'kendime zarar',
  'canıma kıymak',
  'yaşamak istemiyorum',
  'ölmek istiyorum',
  'hayatıma son vermek',
  'kendimi asmak',
  'ilaç içip ölmek'
];

export interface CrisisCheckResult {
  isCrisis: boolean;
  emergencyResponseTr?: string;
}

/** Normalize only comparison text. Keep Turkish accents and the original message intact. */
export function normalizeCrisisText(text: string, turkish = true): string {
  const composed = text.normalize('NFC');
  const lower = turkish ? composed.toLocaleLowerCase('tr-TR') : composed.toLowerCase();
  // Some inputs already contain the decomposed dotted lowercase i.
  return lower.replace(/i\u0307/g, 'i').normalize('NFC');
}

export function checkCrisisTrigger(text: string, isMoving: boolean = false): CrisisCheckResult {
  // Also accept ordinary ASCII casing (INTIHAR), without conflating Turkish ı/i.
  const candidates = [normalizeCrisisText(text), normalizeCrisisText(text, false)];
  for (const keyword of CRISIS_KEYWORDS) {
    if (candidates.some(candidate => candidate.includes(normalizeCrisisText(keyword)))) {
      if (isMoving) {
        return {
          isCrisis: true,
          emergencyResponseTr:
            'Söyledikleriniz benim için çok önemli ve zor bir andan geçtiğinizi anlıyorum. Ancak ben acil durum servisi değilim. Lütfen ekrana bakmayın. Mümkün olduğunda aracınızı hemen güvenli bir yerde durdurun ve 112 Acil Çağrı Merkezini arayın. Yalnız değilsiniz.'
        };
      }
      return {
        isCrisis: true,
        emergencyResponseTr:
          'Söyledikleriniz benim için çok önemli ve şu an çok zor bir süreçten geçtiğinizi anlıyorum. Ancak ben bir acil durum veya sağlık servisi değilim. Lütfen şu an güvende kalmak için gecikmeden 112 Acil Çağrı Merkezi ile iletişime geçin. Yalnız değilsiniz, profesyonel uzmanlar size yardımcı olmak için hazır.'
      };
    }
  }
  return { isCrisis: false };
}
