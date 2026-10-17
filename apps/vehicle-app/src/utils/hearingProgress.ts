import type { Ear } from './hearingProtocol';
export type TonePresentation={id:number;ear:Ear;frequency:number;level:number;silent:boolean;scheduledAt:number;startedAt:number|null;deadline:number|null;completedAt:number|null;answered:boolean;duration?:number;gap?:number;audioStartedAt?:number;audioExpectedEnd?:number;audioEndedAt?:number;outputEndedAt?:number;invalidReason?:string};
export type HearingPress={at:number;trialId:number|null;kind:'early'|'silent'|'late'|'valid'|'duplicate'};
/** Retains every press independently from adaptive presentations and stages. */
export class HearingTrialLog {
 presentations:TonePresentation[]=[];presses:HearingPress[]=[];
 press(at:number,current?:TonePresentation){
  const last=this.presentations.at(-1);
  const kind:HearingPress['kind']=!current||current.startedAt===null?
   last?.completedAt!==null&&last?.deadline!==null&&last?.deadline!==undefined&&at>last.deadline?'late':'early':
   at<current.startedAt?'early':current.deadline!==null&&at>current.deadline?'late':
   current.answered?'duplicate':current.silent?'silent':'valid';
  this.presses.push({at,trialId:current?.id??last?.id??null,kind});
  if(current&&(kind==='valid'||kind==='silent'))current.answered=true;
  return kind;
 }
 completed(ear?:Ear){return this.presentations.filter(p=>p.completedAt!==null&&(!ear||p.ear===ear)).length;}
}

/** Only a fully played, current presentation can be consumed once. */
export class DigitTrialGate {
 private sequence=0;private ready=false;
 begin(){this.ready=false;return ++this.sequence;}
 open(token:number){if(token!==this.sequence)return false;this.ready=true;return true;}
 take(token:number){if(token!==this.sequence||!this.ready)return false;this.ready=false;return true;}
 cancel(){this.ready=false;this.sequence++;}
}
