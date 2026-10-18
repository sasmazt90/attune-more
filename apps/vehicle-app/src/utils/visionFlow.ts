import type { Eye } from './spokenVision';
export type VisionStage='idle'|'preparing'|'eye-instruction'|'eye-check'|'rendering'|'prompting'|'listening'|'condition-paused'|'user-paused'|'result'|'error';
/** The controller uses this state for both UI and all async admission gates. */
export class VisionFlow {
 stage:VisionStage='idle';version=0;sessionId='';presentationId='';eye:Eye='RIGHT';instructionEye:Eye|null=null;reason='';conditionsValid=false;
 transition(stage:VisionStage,reason=''){if(this.stage!==stage||this.reason!==reason){this.stage=stage;this.reason=reason;this.version++;}}
 start(sessionId:string){this.sessionId=sessionId;this.presentationId='';this.instructionEye=null;this.eye='RIGHT';this.conditionsValid=false;this.transition('preparing');}
 // A transient sensor gate blocks answers without cancelling the same
 // presentation's in-flight instruction. Session/eye/stage tokens still expire.
 setConditions(valid:boolean){this.conditionsValid=valid;}
 token(){return `${this.sessionId}/${this.presentationId}/${this.eye}/${this.version}`;}
 matches(token:string){return token===this.token();}
 gatedEye(currentEye:Eye){return this.instructionEye===currentEye?currentEye:null;}
 get letterVisible(){return !!this.presentationId&&['rendering','prompting','listening'].includes(this.stage);}
 get canAnswer(){return this.stage==='listening'&&this.letterVisible&&this.conditionsValid;}
 reset(){this.sessionId='';this.presentationId='';this.instructionEye=null;this.conditionsValid=false;this.transition('idle');}
}
export function eyeInstruction(eye:Eye){return (eye==='RIGHT'?'Sağ gözünüzü test ediyoruz. Sol gözünüzü kapatın veya örtün.':'Sol gözünüzü test ediyoruz. Sağ gözünüzü kapatın veya örtün.')+' Açık gözünüzle harf alanına bakın.';}
