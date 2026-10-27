import type {Eye,EyePixelEvidence,LetterConditions} from './spokenVision';
export type CoverageConfirmation={testEye:Eye;coveredEye:Eye;kind:'closed'|'hand'|'object';confirmedAt:number;source:'user-confirmed'};
export type EyeObservation='EYE_OPEN'|'EYE_CLOSED'|'EYE_COVERED_BY_HAND'|'EYE_OCCLUDED_BY_OBJECT'|'EYE_NOT_VISIBLE_OR_UNCERTAIN'|'FACE_NOT_ALIGNED'|'CAMERA_UNAVAILABLE';
export function eyeObservation(c:LetterConditions|null,eye:Eye,now:number):EyeObservation{
 if(!c||!Number.isFinite(now)||now<c.observedAt||now-c.observedAt>750||!c.cameraLive||!c.modelActive)return 'CAMERA_UNAVAILABLE';
 if(c.faceCount!==1||!c.positionValid)return 'FACE_NOT_ALIGNED';
 const e=eye==='RIGHT'?c.right:c.left;
 if(!c.qualityValid)return 'EYE_NOT_VISIBLE_OR_UNCERTAIN';
 if(e.state==='open')return 'EYE_OPEN';if(e.state==='closed')return 'EYE_CLOSED';
 if(e.state==='covered'&&e.occlusionKind==='hand')return 'EYE_COVERED_BY_HAND';
 if(e.state==='covered'&&e.occlusionKind==='object')return 'EYE_OCCLUDED_BY_OBJECT';
 return 'EYE_NOT_VISIBLE_OR_UNCERTAIN';
}
/** Confirmation supplies only the covered-eye requirement. It never changes
 * source eye observations or overrides an open wrong eye, missing face, stale
 * camera, alignment, lighting, distance, or the independently open test eye. */
export function confirmationUsable(c:LetterConditions,eye:Eye,confirmation:CoverageConfirmation|null,now:number){
 const open=eye==='RIGHT'?c.right:c.left,other=eye==='RIGHT'?c.left:c.right;
 return !!confirmation&&confirmation.source==='user-confirmed'&&confirmation.testEye===eye&&confirmation.coveredEye!==eye&&
  Number.isFinite(confirmation.confirmedAt)&&now>=confirmation.confirmedAt&&now-confirmation.confirmedAt<=60000&&
  Number.isFinite(c.observedAt)&&now>=c.observedAt&&now-c.observedAt<=750&&c.cameraLive&&c.modelActive&&c.faceCount===1&&c.qualityValid&&c.positionValid&&!c.blocker&&
  c.relativeScaleChange!==null&&Number.isFinite(c.relativeScaleChange)&&open.state==='open'&&other.state==='uncertain';
}
export function withCoverageConfirmation(c:LetterConditions,eye:Eye|null,confirmation:CoverageConfirmation|null,now:number):LetterConditions{
 const {coverageConfirmation:ignored,...raw}=c;void ignored;
 return eye&&confirmationUsable(raw,eye,confirmation,now)?{...raw,coverageConfirmation:confirmation!}:raw;
}
/** Keep details in evidence while retaining legacy state values in history. */
export function occlusionKind(method:string):EyePixelEvidence['occlusionKind']{
 return method==='palm-over-eye-and-local-appearance'?'hand':method==='opaque-local-appearance-and-visible-head'?'object':undefined;
}
