import {HEARING_CONFIG, type Ear, type ToneThreshold} from './hearingProtocol';
import type {TonePresentation,HearingPress} from './hearingProgress';
/** Read-only presentation of persisted measurements. No changes to protocol, records or scores. */
export type ToneRecord={id:string;timestamp?:string;date?:string;completedAt?:string;methodVersion?:string;unit?:string;presentationVersion?:string;thresholds?:ToneThreshold[];presentations?:TonePresentation[];presses?:HearingPress[];deviceSession?:string;calibrationProfile?:unknown;captureConditions?:{contextSampleRate?:number};catchTrials?:number;catchFalsePositive?:number;quality?:string;[key:string]:unknown};
export const HEARING_FREQUENCIES=[250,500,1000,2000,4000,8000] as const;
const finite=(x:unknown):x is number=>typeof x==='number'&&Number.isFinite(x);
const time=(r:ToneRecord)=>Date.parse(r.timestamp||r.date||r.completedAt||'');
export function thresholdRows(record:ToneRecord,ear:Ear):(number|null)[]{
 const rows=Array.isArray(record.thresholds)?record.thresholds:[];
 return HEARING_FREQUENCIES.map(hz=>{const matches=rows.filter(r=>r.ear===ear&&r.frequency===hz&&!r.repeat);const t=matches.length===1?matches[0]:undefined;return t&&t.status==='threshold'&&finite(t.value)&&t.value>=HEARING_CONFIG.minDbFS&&t.value<=HEARING_CONFIG.maxDbFS?t.value:null;});
}
export function hearingLevelY(value:number,top=12,height=180){return top+(HEARING_CONFIG.maxDbFS-value)/(HEARING_CONFIG.maxDbFS-HEARING_CONFIG.minDbFS)*height;}
export function thresholdPaths(values:(number|null)[],x:(i:number)=>number,y:(v:number)=>number){
 const paths:string[]=[];let segment='';values.forEach((v,i)=>{if(v===null){if(segment)paths.push(segment);segment='';}else segment+=`${segment?' L':'M'}${x(i)} ${y(v)}`;});if(segment)paths.push(segment);return paths;
}
export function completedToneRecord(r:ToneRecord){
 if(r.methodVersion!==HEARING_CONFIG.version||r.unit!=='dBFS-peak'||!Array.isArray(r.thresholds)||r.thresholds.length!==14)return false;
 return (['left','right'] as Ear[]).every(ear=>HEARING_CONFIG.frequencies.every((hz,i)=>r.thresholds!.filter(t=>t.ear===ear&&t.frequency===hz&&!!t.repeat===(i===6)).length===1));
}
export type ValidResponse={trialId:number;ear:Ear;frequency:number;level:number;seconds:number;presentation:TonePresentation};
/** Require a fully finished source and its single classified valid press. Other events never become averages. */
export function completedHearingResponses(record:Pick<ToneRecord,'presentations'|'presses'|'captureConditions'>,ear:Ear):ValidResponse[]{
 if(!Array.isArray(record.presentations)||!Array.isArray(record.presses))return [];
 const byId=new Map<number,TonePresentation[]>(),presses=new Map<number,HearingPress[]>();
 for(const p of record.presentations){if(!p||!Number.isSafeInteger(p.id)||p.id<=0)continue;byId.set(p.id,[...(byId.get(p.id)||[]),p]);}
 for(const p of record.presses){if(!p||!Number.isSafeInteger(p.trialId))continue;presses.set(p.trialId!,[...(presses.get(p.trialId!)||[]),p]);}
 // Browser setTimeout rounds fractional millisecond delays down. The source must
 // still have ended fully; allow only that <1ms observation precision at the
 // completed response-window boundary. The press window itself stays exact.
 const rate=record.captureConditions?.contextSampleRate;const tolerance=128/(finite(rate)&&rate>=16000?rate:48000);
 const valid:ValidResponse[]=[];
 for(const [id,items] of byId){
  if(items.length!==1)continue;const p=items[0];
  if(p.ear!==ear||p.silent||p.invalidReason||!p.answered||!HEARING_FREQUENCIES.includes(p.frequency as typeof HEARING_FREQUENCIES[number])||!finite(p.level)||p.level<-90||p.level>-30)continue;
  if(!finite(p.scheduledAt)||!finite(p.startedAt)||!finite(p.deadline)||!finite(p.completedAt)||!finite(p.duration)||!finite(p.outputEndedAt)||!finite(p.audioStartedAt)||!finite(p.audioExpectedEnd)||!finite(p.audioEndedAt))continue;
  if(p.duration<HEARING_CONFIG.durationMin||p.duration>HEARING_CONFIG.durationMax||p.scheduledAt<0||p.startedAt<p.scheduledAt||p.deadline<=p.startedAt||Math.abs(p.deadline-p.startedAt-(p.duration+HEARING_CONFIG.responseSeconds)*1000)>1||p.completedAt+1<p.deadline||p.outputEndedAt<p.startedAt||p.completedAt<p.outputEndedAt||p.audioExpectedEnd<=p.audioStartedAt||Math.abs(p.audioExpectedEnd-p.audioStartedAt-p.duration)>tolerance||p.audioEndedAt+tolerance<p.audioExpectedEnd)continue;
  const candidates=(presses.get(id)||[]).filter(x=>x.kind==='valid');if(candidates.length!==1)continue;
  const press=candidates[0];if(!finite(press.at)||press.at<p.startedAt||press.at>p.deadline)continue;
  valid.push({trialId:id,ear,frequency:p.frequency,level:p.level,seconds:(press.at-p.startedAt)/1000,presentation:p});
 }
 return valid;
}
export function validHearingResponses(record:ToneRecord,ear:Ear):ValidResponse[]{
 if(!completedToneRecord(record)||record.presentationVersion!=='source-complete-token-v1')return [];
 return completedHearingResponses(record,ear);
}
export function meanHearingResponse(record:ToneRecord,ear:Ear):{seconds:number;count:number}|null{
 const responses=validHearingResponses(record,ear);return responses.length?{seconds:responses.reduce((n,r)=>n+r.seconds,0)/responses.length,count:responses.length}:null;
}
/** Select the nearest compatible older test, even when it has no timing; never cherry-pick an older mean. */
export function previousHearingRecord(current:ToneRecord,records:ToneRecord[]):ToneRecord|undefined{
 if(!completedToneRecord(current)||!finite(time(current)))return undefined;
 const same=(r:ToneRecord)=>completedToneRecord(r)&&r.unit===current.unit&&r.methodVersion===current.methodVersion&&r.deviceSession===current.deviceSession&&JSON.stringify(r.calibrationProfile??null)===JSON.stringify(current.calibrationProfile??null);
 return records.filter(r=>r.id!==current.id&&finite(time(r))&&time(r)<time(current)&&same(r)).sort((a,b)=>time(b)-time(a))[0];
}
