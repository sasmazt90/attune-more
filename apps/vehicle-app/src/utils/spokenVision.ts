import prompts from '../../../../shared/localization/vision-prompts.json';
import {t} from '../i18n/core';
import {interpretVisionAnswer} from './visionLanguage';
import {confirmationUsable,type CoverageConfirmation} from './visionCoverage';
/** Target-independent interpretation and a nonclinical letter task. */
export const LETTER_PROTOCOL='spoken-letter-v2';
export const LETTER_METHOD='mirror-x-then-rotate-two-up-two-down-step50-min15-v4';
export type Orientation='upright'|'right'|'down'|'left'|'mirror';
export type Letter='A'|'B'|'E'|'F'|'P'|'R';
export type Eye='RIGHT'|'LEFT';
export const LETTER_PATHS:Record<Letter,string>={
 A:'M15 90L50 10L85 90M29 60H71', B:'M20 90V10H55C85 10 85 50 55 50H20M55 50C90 50 90 90 55 90H20',
 E:'M80 10H20V90H80M20 50H70', F:'M80 10H20V90M20 50H70',
 P:'M20 90V10H55C90 10 90 50 55 50H20', R:'M20 90V10H55C90 10 90 50 55 50H20M55 50L85 90'
};
export type Rotation=0|90|180|270;
export type LetterTransform={rotation:Rotation;mirrored:boolean;mirrorAxis:'x';order:'mirror-then-rotate'};
export type ParsedAnswer={command?:'not-visible'|'repeat'|'pause'|'resume'|'finish';letter?:Letter;orientation?:Orientation;rotation?:Rotation;mirrored?:boolean;clarify?:'letter'|'orientation'|'reverse';ambiguous?:'letter'|'rotation'};
export const LEGACY_LETTER_PROTOCOL='spoken-letter-v1';
export function isLetterProtocol(protocol:unknown){return protocol===LETTER_PROTOCOL||protocol===LEGACY_LETTER_PROTOCOL;}
export function legacyTransform(orientation:Orientation):LetterTransform{return {rotation:({upright:0,right:90,down:180,left:270,mirror:0} as const)[orientation],mirrored:orientation==='mirror',mirrorAxis:'x',order:'mirror-then-rotate'};}
export function answerTransform(answer:ParsedAnswer):LetterTransform|null{
 if(answer.ambiguous||answer.clarify==='reverse')return null;
 const legacy=answer.orientation?legacyTransform(answer.orientation):null;
 const rotation=answer.rotation??legacy?.rotation;
 if(rotation===undefined&&answer.mirrored!==true)return null;
 return {rotation:rotation??0,mirrored:answer.mirrored??legacy?.mirrored??false,mirrorAxis:'x',order:'mirror-then-rotate'};
}
export function describeAnswer(p:ParsedAnswer){
 const t=answerTransform(p),direction=t?({0:'düz',90:'sağa yatmış',180:'baş aşağı',270:'sola yatmış'} as const)[t.rotation]+(t.mirrored?' ve aynalı':''):'yön anlaşılmadı';
 return `${p.letter||'harf anlaşılmadı'} · ${direction}`;
}
/** Components belong to one presentation. The caller owns that identity. */
export function mergeLetterAnswer(partial:ParsedAnswer,answer:ParsedAnswer):ParsedAnswer{
 if(answer.command)return answer;
 const old=partial.orientation?legacyTransform(partial.orientation):null,next=answer.orientation?legacyTransform(answer.orientation):null;
 const merged:ParsedAnswer={...partial,...answer,letter:answer.letter??partial.letter,rotation:answer.rotation??(answer.orientation&&answer.orientation!=='mirror'?next?.rotation:undefined)??partial.rotation??old?.rotation,mirrored:answer.mirrored??(answer.orientation==='mirror'?true:undefined)??partial.mirrored??old?.mirrored};
 // A bare mirror fragment keeps an already heard rotation, or means upright mirror.
 if(merged.rotation===undefined&&merged.mirrored===true)merged.rotation=0;
 delete merged.orientation;
 if(answer.ambiguous){merged.ambiguous=answer.ambiguous;merged.clarify=answer.ambiguous==='letter'?'letter':'orientation';}
 else if(answer.clarify==='reverse'){merged.clarify='reverse';}
 else if(partial.ambiguous==='letter'&&!answer.letter){merged.ambiguous='letter';merged.clarify='letter';}
 else if((partial.ambiguous==='rotation'||partial.clarify==='reverse')&&answer.rotation===undefined&&answer.mirrored===undefined&&!answer.orientation){merged.ambiguous=partial.ambiguous;merged.clarify=partial.clarify;}
 else {delete merged.ambiguous;merged.clarify=!merged.letter?'letter':!answerTransform({...merged,clarify:undefined})?'orientation':undefined;}
 return merged;
}
export const LETTER_INSTRUCTIONS={
 first:'Harf alanına bakın. Harfi ve yönünü istediğiniz sırada söyleyin. Yön ile birlikte, gördüğünüz harfle başlayan bir kelime söyleyebilirsiniz. Harf görünüyorsa yönergenin bitmesini beklemeniz gerekmez.',
 next1:'Şimdi sıradaki harfi söyleyin.',
 next2:'Lütfen bu harfi aynı şekilde okuyun.',
 next3:'Yanıtınız kaydedildi. Sıradaki harfe geçiyoruz.',
 letter:'Harfi söyler misiniz? O harfle başlayan bir kelime de kullanabilirsiniz.',
 orientation:'Harfin hangi yöne dönük olduğunu söyler misiniz?',
 reverse:'Baş aşağı mı, aynalı mı?',
 repeat:'Ekrandaki harfi ve yönünü söyleyin.'
} as const;
function normalizeSpeech(text:string){return text.toLocaleLowerCase('tr-TR').normalize('NFKC').replace(/[’‘`]/g,"'").replace(/[^a-zçğıöşü ]/g,' ').replace(/\s+/g,' ').trim();}
/** Only instruction clauses, not broad vocabulary/short answer filtering. */
export function isLetterInstructionEcho(text:string,language:'tr'|'en'|'de'='tr'){
 if(language!=='tr'){
  const normal=(value:string)=>value.toLocaleLowerCase(language==='de'?'de-DE':'en-US').normalize('NFKC').replace(/[^\p{L} ]/gu,' ').replace(/\s+/g,' ').trim();
  const value=normal(text);
  if(value.split(' ').length>=3&&Object.values(prompts).some(source=>normal(t(source,language)).includes(value)))return true;
 }
 if(language==='en')return /please (?:say|look|keep)|look at the letter|which way|you can (?:say|use)|keep your|cover the other/i.test(text);
 if(language==='de')return /bitte (?:sagen|schauen|halten)|schauen sie|in welche richtung|sie können|decken sie|halten sie/i.test(text);
 const value=normalizeSpeech(text);
 if(/söyleyin|söyler misiniz|okuyun|bakın|kullanabilirsiniz|beklemeniz gerekmez|yanıtınız alındı|test ediyoruz|kalsın|kapatın|örtün/.test(value))return true;
 return Object.values(LETTER_INSTRUCTIONS).map(normalizeSpeech).some(line=>value.split(' ').length>=3&&line.includes(value));
}
export function parseLetterAnswer(text:string,language:'tr'|'en'|'de'='tr',context?:{letter:Letter}):ParsedAnswer {
 return interpretVisionAnswer(text,language,context);
}
/** These are exact symmetries of the drawn A and E paths. Composition is
 * mirror in local x, then clockwise rotation, as in LetterStimulus. */
export function equivalentTransform(letter:Letter,a:LetterTransform,b:LetterTransform){
 const matrix=(t:LetterTransform)=>{const angle=t.rotation*Math.PI/180,c=Math.round(Math.cos(angle)),s=Math.round(Math.sin(angle)),m=t.mirrored?-1:1;return [c*m,-s,s*m,c];};
 const x=matrix(a),y=matrix(b);if(x.every((v,i)=>v===y[i]))return true;
 const symmetry=letter==='A'?[-1,1]:letter==='E'?[1,-1]:null;
 return !!symmetry&&x.every((v,i)=>v===y[i]*symmetry[i%2]);
}
export function equivalentOrientation(letter:Letter,a:Orientation,b:Orientation){return equivalentTransform(letter,legacyTransform(a),legacyTransform(b));}
export type EyePixelEvidence={state:'open'|'closed'|'covered'|'uncertain';occlusionKind?:'hand'|'object';ear:number|null;darkFraction:number|null;contrast:number|null;method:string;baselineEar?:number;blinkCoefficient?:number|null;heldMs?:number;appearanceChange?:number;templateCorrelation?:number;palmCoverage?:number;wideTemplateCorrelation?:number;candidateState?:'open'|'closed'|'covered'|'uncertain'};
export type LetterConditions={coverageConfirmation?:CoverageConfirmation;observedAt:number;cameraLive:boolean;modelActive:boolean;faceCount:number;qualityValid:boolean;positionValid:boolean;relativeScaleChange:number|null;motionStable?:boolean;right:EyePixelEvidence;left:EyePixelEvidence;distancePolicy?:'head-anchors-hysteresis-v1';distanceState?:'learning'|'stable'|'near'|'far'|'unknown';blocker?:string|null;trackingMethod?:string};
export function letterConditionFailure(c:LetterConditions|null,eye:Eye|null,now:number):'camera'|'position'|'eye'|'uncertain'|null {
 if(!c||!Number.isFinite(now)||!Number.isFinite(c.observedAt)||now-c.observedAt>750||now<c.observedAt||!c.cameraLive||!c.modelActive||c.faceCount!==1||!c.qualityValid)return 'camera';
 if(!c.positionValid||c.relativeScaleChange===null||!Number.isFinite(c.relativeScaleChange)||(c.distancePolicy!=='head-anchors-hysteresis-v1'&&(c.motionStable===false||Math.abs(c.relativeScaleChange)>.08)))return 'position';
 if(!eye)return null;
 const opened=eye==='RIGHT'?c.right:c.left,closed=eye==='RIGHT'?c.left:c.right;
 if(opened.state==='open'&&confirmationUsable(c,eye,c.coverageConfirmation||null,now))return null;
 if(opened.state==='uncertain'||closed.state==='uncertain')return 'uncertain';
 return opened.state==='open'&&(closed.state==='closed'||closed.state==='covered')?null:'eye';
}

// Product adaptation: two full correct halve each dimension; two errors undo one step.
export const LETTER_RULES={startPx:120,minPx:15,maxPx:180,shrinkRatio:.50,perEye:12,maxValid:24} as const;
export interface RenderedSymbolGeometry {viewportWidthCssPx:number;viewportHeightCssPx:number;pathWidthCssPx:number;pathHeightCssPx:number;strokeWidthCssPx:number;measuredAt:number;method:'dom-svg-css-pixels'}
export interface LetterTrial {
 id:string;presentationId:string;sequence:number;protocolVersion:typeof LETTER_PROTOCOL|typeof LEGACY_LETTER_PROTOCOL;transform?:LetterTransform;methodVersion?:string;eye:Eye;letter:Letter;orientation:Orientation;sizePx:number;
 renderedGeometry:RenderedSymbolGeometry|null;parsedAnswer:ParsedAnswer;answer:({letter:Letter;orientation?:Orientation;transform?:LetterTransform})|null;
 letterCorrect:boolean|null;orientationCorrect:boolean|null;combinedCorrect:boolean|null;correct:boolean;notVisible:boolean;
 inputMethod?:'speech'|'buttons';coverageVerification?:'camera'|'user-confirmed';valid:boolean;invalidReason:string|null;conditions:LetterConditions|null;answeredAt:string;responseTimeMs:number;
 distanceEvidence:{method:'relative-face-scale-only'|'relative-head-anchors';relativeScaleChange:number|null;absoluteDistanceCm:null;confidence:'unverified-absolute'};
}
export function scoreLetterTrial(t:Pick<LetterTrial,'valid'|'letter'|'orientation'|'answer'|'notVisible'> & {transform?:LetterTransform}){
 if(!t.valid)return {letterCorrect:null,orientationCorrect:null,combinedCorrect:null};
 const letterCorrect=!t.notVisible&&t.answer?.letter===t.letter;
 const target='transform' in t&&t.transform?(t.transform as LetterTransform):legacyTransform(t.orientation);
 const actual=t.answer?.transform||(t.answer?.orientation?legacyTransform(t.answer.orientation):null);
 const orientationCorrect=!t.notVisible&&!!actual&&equivalentTransform(t.letter,actual,target);
 return {letterCorrect,orientationCorrect,combinedCorrect:letterCorrect&&orientationCorrect};
}
export interface Accuracy {correct:number;total:number;percentage:number|null}
function accuracy(values:(boolean|null)[]):Accuracy {const evaluated=values.filter((v):v is boolean=>v!==null);const correct=evaluated.filter(Boolean).length;return {correct,total:evaluated.length,percentage:evaluated.length?100*correct/evaluated.length:null};}
/** Recompute from the stored targets/answers/validity, never trust cached scores. */
export function performanceBySize(trials:LetterTrial[],eye:Eye){
 const valid=trials.filter(t=>t.eye===eye&&t.valid&&t.renderedGeometry);
 const sizes=new Map<string,LetterTrial[]>();
 for(const t of valid){const g=t.renderedGeometry!;const key=`${g.viewportWidthCssPx.toFixed(3)}×${g.viewportHeightCssPx.toFixed(3)}`;sizes.set(key,[...(sizes.get(key)||[]),t]);}
 return [...sizes.entries()].map(([size,rows])=>{const scores=rows.map(scoreLetterTrial);return {size,widthCssPx:rows[0].renderedGeometry!.viewportWidthCssPx,heightCssPx:rows[0].renderedGeometry!.viewportHeightCssPx,
  letter:accuracy(scores.map(s=>s.letterCorrect)),orientation:accuracy(scores.map(s=>s.orientationCorrect)),combined:accuracy(scores.map(s=>s.combinedCorrect)),average:averageAccuracy(scores),notVisible:rows.filter(t=>t.notVisible).length};}).sort((a,b)=>b.widthCssPx-a.widthCssPx);
}
export function averageAccuracy(scores:ReturnType<typeof scoreLetterTrial>[]){const l=accuracy(scores.map(s=>s.letterCorrect)),o=accuracy(scores.map(s=>s.orientationCorrect));return l.percentage===null||o.percentage===null?null:(l.percentage+o.percentage)/2;}
export function performanceForEye(trials:LetterTrial[],eye:Eye){const rows=trials.filter(t=>t.eye===eye&&t.valid),scores=rows.map(scoreLetterTrial);return {letter:accuracy(scores.map(s=>s.letterCorrect)),orientation:accuracy(scores.map(s=>s.orientationCorrect)),average:averageAccuracy(scores),valid:rows.length,notVisible:rows.filter(t=>t.notVisible).length};}
function random(max:number){const a=new Uint32Array(1);crypto.getRandomValues(a);return Math.floor(a[0]/4294967296*max);}
export class SpokenLetterSession {
 trials:LetterTrial[]=[];invalidTrials:LetterTrial[]=[];id=crypto.randomUUID();trialId='';presentationId='';letter:Letter='E';orientation:Orientation='upright';transform:LetterTransform=legacyTransform('upright');sizePx:number=LETTER_RULES.startPx;
 private streak=0;private wrongStreak=0;private previousTarget='';private presentedAt=0;private elapsed=0;private timing=false;private pending=false;private sequence=0;
 get completed(){return this.trials.length>=LETTER_RULES.maxValid;}
 get eye():Eye{return this.trials.length<LETTER_RULES.perEye?'RIGHT':'LEFT';}
 get ledger(){return [...this.trials,...this.invalidTrials].sort((a,b)=>a.sequence-b.sequence);}
 get adaptationState(){return {correctStreak:this.streak,wrongStreak:this.wrongStreak,sizePx:this.sizePx};}
 beginResponse(now=performance.now()){if(this.presentationId&&!this.timing){this.presentedAt=now;this.timing=true;}}
 suspendResponse(now=performance.now()){if(this.timing){this.elapsed+=Math.max(0,now-this.presentedAt);this.timing=false;}}
 present(now=performance.now()){
  if(this.completed||this.presentationId)return;
  if(!this.pending){this.trialId=crypto.randomUUID();const targets:{letter:Letter;transform:LetterTransform}[]=[];
   for(const letter of Object.keys(LETTER_PATHS) as Letter[]){const unique:LetterTransform[]=[];for(const rotation of [0,90,180,270] as Rotation[])for(const mirrored of [false,true]){const t:LetterTransform={rotation,mirrored,mirrorAxis:'x',order:'mirror-then-rotate'};if(!unique.some(u=>equivalentTransform(letter,u,t)))unique.push(t);}for(const transform of unique)if(this.previousTarget!==letter+JSON.stringify(transform))targets.push({letter,transform});}
   const target=targets[random(targets.length)];this.letter=target.letter;this.transform=target.transform;this.orientation=({0:'upright',90:'right',180:'down',270:'left'} as const)[target.transform.rotation];this.previousTarget=this.letter+JSON.stringify(this.transform);}
  this.pending=false;this.presentationId=crypto.randomUUID();this.presentedAt=now;this.elapsed=0;this.timing=false;
 }
 private record(answer:ParsedAnswer,c:LetterConditions|null,now:number,geometry:RenderedSymbolGeometry|null,reason:string|null):LetterTrial {
  const notVisible=answer.command==='not-visible',transform=answerTransform(answer);const parsed=notVisible||!answer.letter||!transform?null:{letter:answer.letter,transform};
  const base={valid:reason===null,letter:this.letter,orientation:this.orientation,transform:structuredClone(this.transform),answer:parsed,notVisible};const scores=scoreLetterTrial(base);
  return {id:this.trialId,presentationId:this.presentationId,sequence:++this.sequence,protocolVersion:LETTER_PROTOCOL,methodVersion:LETTER_METHOD,eye:this.eye,...base,sizePx:this.sizePx,renderedGeometry:geometry?structuredClone(geometry):null,parsedAnswer:structuredClone(answer),...scores,correct:scores.combinedCorrect===true,coverageVerification:c?.coverageConfirmation?'user-confirmed':'camera',invalidReason:reason,conditions:c?structuredClone(c):null,answeredAt:new Date().toISOString(),responseTimeMs:this.elapsed+(this.timing?Math.max(0,now-this.presentedAt):0),distanceEvidence:{method:c?.distancePolicy==='head-anchors-hysteresis-v1'?'relative-head-anchors':'relative-face-scale-only',relativeScaleChange:c?.relativeScaleChange??null,absoluteDistanceCm:null,confidence:'unverified-absolute'}};
 }
 unscored(reason:string,c:LetterConditions|null,now:number,geometry:RenderedSymbolGeometry|null,parsed:ParsedAnswer={}){if(this.presentationId)this.invalidTrials.push(this.record(parsed,c,now,geometry,reason));}
 invalidate(reason:string,c:LetterConditions|null,now:number,geometry:RenderedSymbolGeometry|null){
  if(!this.presentationId)return false;this.unscored(reason,c,now,geometry);this.presentationId='';this.pending=true;return true;
 }
 respond(answer:ParsedAnswer,c:LetterConditions|null,now:number,presentationId:string,geometry:RenderedSymbolGeometry|null){
  if(this.completed||!this.presentationId||presentationId!==this.presentationId||letterConditionFailure(c,this.eye,now)||!c)return false;
  if(answer.clarify||(!answer.command&&(!answer.letter||!answerTransform(answer)))||(answer.command&&answer.command!=='not-visible'))return false;
  if(!geometry||![geometry.viewportWidthCssPx,geometry.viewportHeightCssPx,geometry.pathWidthCssPx,geometry.pathHeightCssPx,geometry.strokeWidthCssPx,geometry.measuredAt].every(Number.isFinite)||geometry.viewportWidthCssPx<=0||geometry.viewportHeightCssPx<=0||geometry.pathWidthCssPx<=0||geometry.pathHeightCssPx<=0||now<geometry.measuredAt||now-geometry.measuredAt>750)return false;
  const eye=this.eye,t=this.record(answer,c,now,geometry,null);this.trials.push(t);this.presentationId='';this.streak=t.combinedCorrect?this.streak+1:0;this.wrongStreak=t.combinedCorrect?0:this.wrongStreak+1;
  if(this.wrongStreak===2){this.sizePx=Math.min(LETTER_RULES.maxPx,this.sizePx/LETTER_RULES.shrinkRatio);this.wrongStreak=0;}
  else if(this.streak===2){this.sizePx=Math.max(LETTER_RULES.minPx,this.sizePx*LETTER_RULES.shrinkRatio);this.streak=0;}
  if(!this.completed&&this.eye!==eye){this.sizePx=LETTER_RULES.startPx;this.streak=0;this.wrongStreak=0;}
  return true;
 }
}
export interface LetterResult {id:string;date:string;protocolVersion:typeof LETTER_PROTOCOL|typeof LEGACY_LETTER_PROTOCOL;methodVersion?:string;trials:LetterTrial[];deviceContext:{width:number;height:number;dpr:number};profileVerification:'unverified';distanceMethod:'relative-face-scale-only'|'relative-head-anchors';physicalScale:null;completed:boolean}
/** Read the displayed geometry before sampling the response clock. Passing a
 * clock sampled first makes the real DOM measurement appear to be in the
 * future, which respond correctly rejects. Keep that strict guard intact. */
export function respondToVisibleLetter(session:SpokenLetterSession,answer:ParsedAnswer,conditions:LetterConditions|null,presentationId:string,measure:()=>RenderedSymbolGeometry|null,clock:()=>number=()=>performance.now()){
 const geometry=measure();return session.respond(answer,conditions,clock(),presentationId,geometry);
}
