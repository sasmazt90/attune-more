import { answerTransform, mergeLetterAnswer, type Eye, type ParsedAnswer } from './spokenVision';

export interface AnswerTarget {sessionId:string;eye:Eye;targetId:string}
/** In-memory only: one actual target, across render/ASR/presentation restarts.
 * Raw speech fragments are used only by the existing live "Duyulan" field.
 * They are never copied to the result ledger or persistent diagnostics. */
export class VisionAnswerMemory {
 private target:AnswerTarget|null=null;
 private keys=new Set<string>();
 private fragments:string[]=[];
 private confirmation=new Set<'letter'|'rotation'|'mirror'>();
 answer:ParsedAnswer={};processed=false;
 bind(target:AnswerTarget){
  if(this.matches(target))return false;
  this.clear();this.target={...target};return true;
 }
 matches(target:AnswerTarget){return !!this.target&&this.target.sessionId===target.sessionId&&this.target.eye===target.eye&&this.target.targetId===target.targetId;}
 append(target:AnswerTarget,key:string,text:string,parsed:ParsedAnswer,confidence=1){
  if(!this.matches(target)||this.processed||this.keys.has(key)||parsed.command)return false;
  this.keys.add(key);this.fragments.push(text.trim().slice(0,160));
  this.answer=mergeLetterAnswer(this.answer,parsed);
  const uncertain=confidence>0&&confidence<.5;
  // Confidence belongs to the heard component, not to the next ASR callback.
  // A confidently repeated/corrected component confirms it without losing the other.
  const fields:('letter'|'rotation'|'mirror')[]=[];
  if(parsed.letter||parsed.ambiguous==='letter')fields.push('letter');
  if(parsed.rotation!==undefined||parsed.orientation||parsed.ambiguous==='rotation')fields.push('rotation');
  if(parsed.mirrored!==undefined||parsed.clarify==='reverse')fields.push('mirror');
  for(const field of fields){if(uncertain)this.confirmation.add(field);else this.confirmation.delete(field);}
  return true;
 }
 get heard(){return this.fragments.join(' · ');}
 get fragmentCount(){return this.fragments.length;}
 get missing(): 'letter'|'orientation'|'reverse'|null {
  if(this.answer.clarify==='reverse')return 'reverse';
  if(!this.answer.letter||this.answer.ambiguous==='letter')return 'letter';
  if(!answerTransform(this.answer))return 'orientation';
  return this.confirmation.has('letter')?'letter':this.confirmation.has('rotation')||this.confirmation.has('mirror')?'orientation':null;
 }
 markProcessed(){this.processed=true;}
 clear(){this.target=null;this.keys.clear();this.fragments=[];this.confirmation.clear();this.answer={};this.processed=false;}
}
