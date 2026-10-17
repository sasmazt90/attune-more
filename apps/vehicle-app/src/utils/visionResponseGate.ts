import { letterConditionFailure, type Eye, type LetterConditions } from './spokenVision';

/** A brief uncertain landmark/quality sample can retain the last independently
 * valid source evidence. Known eye violations, distance changes, lost cameras,
 * lighting/pose/framing failures never use this bridge. UI and scoring both
 * consume the returned evidence; no future recovery queues an old answer. */
export class VisionResponseGate {
 private valid:LetterConditions|null=null;
 private eye:Eye|null=null;
 assess(latest:LetterConditions|null,eye:Eye|null,now:number):LetterConditions|null {
  if(this.eye!==eye){this.valid=null;this.eye=eye;}
  if(!latest||!Number.isFinite(now)||!Number.isFinite(latest.observedAt)||(latest.relativeScaleChange!==null&&!Number.isFinite(latest.relativeScaleChange))||now<latest.observedAt||now-latest.observedAt>750||!latest.cameraLive||!latest.modelActive||latest.faceCount!==1){this.valid=null;return latest;}
  if(!latest.blocker&&!letterConditionFailure(latest,eye,now)){this.valid=latest;return latest;}
  const previous=this.valid;
  const soft=(!latest.blocker||latest.blocker==='distance-unknown'||latest.blocker==='blur')&&latest.distanceState!=='near'&&latest.distanceState!=='far'&&(latest.relativeScaleChange===null||Math.abs(latest.relativeScaleChange)<=.15);
  const open=eye==='RIGHT'?latest.right:latest.left,covered=eye==='RIGHT'?latest.left:latest.right;
  const noEyeViolation=!eye||((open.state==='open'||open.state==='uncertain')&&(covered.state==='closed'||covered.state==='covered'||covered.state==='uncertain'));
  if(previous&&soft&&noEyeViolation&&now-previous.observedAt<=350)return previous;
  // A known violation breaks the bridge immediately; an unknown transient can
  // only age out, never refresh the last valid timestamp.
  if(!soft||!noEyeViolation)this.valid=null;
  return latest;
 }
}
