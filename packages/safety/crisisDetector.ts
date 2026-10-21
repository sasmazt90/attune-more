/**
 * Crisis Detector
 * Ruhsal iyi oluş seanslarında intihar, kendine zarar verme veya akut kriz durumlarını filtreler.
 */

import urgentSafetyPatterns from '../../shared/localization/urgent-safety.json';
import englishPolicy from '../../shared/localization/english-crisis.json';
import germanPolicy from '../../shared/localization/german-crisis.json';

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
  riskLevel?: 'NONE'|'UNCERTAIN';
}

/** Shared bounded grammar, not a clinical intent/risk diagnosis. */
function contextualCrisisContext(text:string,policy:typeof englishPolicy):{signal:boolean;context:string} {
  let value=text.normalize('NFC').toLowerCase().replace(/’/g,"'").replace(/\s+/g,' ').trim();
  if(!new RegExp(policy.signal,'u').test(value))return {signal:false,context:'NONE'};
  const observed=new Set<string>();
  for(const kind of ['reassurance','historical','uncertain'] as const){
    for(const pattern of policy[kind]){
      const rule=new RegExp(pattern,'gu');
      if(rule.test(value)){observed.add(kind);value=value.replace(new RegExp(pattern,'gu'),' ');}
    }
  }
  if([policy.selfDirected,policy.currentState].some(pattern=>new RegExp(pattern,'u').test(value)))return {signal:true,context:'CURRENT_RISK_SIGNAL'};
  if(observed.size&&new RegExp(policy.continuedRisk,'u').test(value))return {signal:true,context:'CONTINUING_RISK_SIGNAL'};
  if(new RegExp(policy.signal,'u').test(value))return {signal:false,context:'UNCERTAIN'};
  if(observed.size&&new RegExp(policy.conditional,'u').test(value))return {signal:false,context:'UNCERTAIN'};
  return {signal:false,context:observed.has('uncertain')?'UNCERTAIN':observed.has('historical')?'HISTORICAL':'REASSURANCE'};
}
export function englishCrisisContext(text:string){return contextualCrisisContext(text,englishPolicy);}
export function germanCrisisContext(text:string){return contextualCrisisContext(text,germanPolicy);}

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
  const urgentSafety=Object.values(urgentSafetyPatterns).some(pair=>pair.every(pattern=>new RegExp(pattern,'u').test(candidates[1])));
  const english=englishCrisisContext(text);
  const german=germanCrisisContext(text);
  const contextualKeywords=new Set<string>([...englishPolicy.legacyKeywords,...germanPolicy.legacyKeywords]);
  const selfHarmSignal=english.signal||german.signal||CRISIS_KEYWORDS.filter(keyword=>!contextualKeywords.has(keyword)).some(keyword=>candidates.some(candidate=>candidate.includes(normalizeCrisisText(keyword))));
  if (urgentSafety || selfHarmSignal) {
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
  return { isCrisis: false, riskLevel:[english,german].some(r=>['UNCERTAIN','HISTORICAL'].includes(r.context))?'UNCERTAIN':'NONE' };
}
