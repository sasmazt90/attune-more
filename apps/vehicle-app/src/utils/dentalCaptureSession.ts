import {DENTAL_POSES,type DentalCapture,type DentalPose} from './dentalCapture';

export type DentalSessionAccept='added'|'complete'|'duplicate'|'closed'|'wrong-pose';
/** One camera scan: the only owner of the captured source list.
 *
 * Poses are taken in FRONT→RIGHT→LEFT→BITE order; a pose the user cannot
 * show may be skipped and is reported as missing, never as measured. The list
 * is sealed exactly once — after the last pose is captured or skipped — and
 * the sealed, frozen copy is handed to `onSealed`. A capture whose async
 * encoding finishes after its pose was skipped or the scan was sealed (e.g. a
 * BITE frame still hashing when the user pressed "skip") is rejected and can
 * neither change the analysed sources nor start a second analysis. */
export class DentalCaptureSession {
 private readonly items:DentalCapture[]=[];
 private readonly missingPoses:DentalPose[]=[];
 private cursor=0;
 private sealedSources:readonly DentalCapture[]|null=null;
 constructor(private readonly onSealed:(sources:readonly DentalCapture[],missing:readonly DentalPose[])=>void){}
 get count(){return this.items.length;}
 get missing():readonly DentalPose[]{return [...this.missingPoses];}
 get sealed(){return this.sealedSources!==null;}
 /** Pose the next accepted capture must have, or undefined once sealed. */
 get nextPose():DentalPose|undefined{return this.sealed?undefined:DENTAL_POSES[this.cursor];}
 get step(){return this.cursor;}
 accept(capture:DentalCapture):DentalSessionAccept{
  if(this.sealed)return 'closed';
  if(capture.pose!==this.nextPose)return 'wrong-pose';
  if(this.items.some(c=>c.photoId===capture.photoId))return 'duplicate';
  this.items.push(capture);this.cursor++;
  if(this.cursor===DENTAL_POSES.length){this.seal();return 'complete';}
  return 'added';
 }
 /** Skip the pending pose; it is carried as missing ("alınmadı"). */
 skipCurrent():boolean{
  const pose=this.nextPose;if(!pose)return false;
  this.missingPoses.push(pose);this.cursor++;
  if(this.cursor===DENTAL_POSES.length)this.seal();
  return true;
 }
 /** Only allowed while BITE is the pending pose. */
 skipBite():boolean{return this.nextPose==='BITE'&&this.skipCurrent();}
 /** Cancel/stop: nothing captured later may start an analysis. */
 close(){if(!this.sealed)this.sealedSources=Object.freeze([]);}
 private seal(){
  const sources=Object.freeze(this.items.map(c=>Object.freeze({...c})));
  this.sealedSources=sources;
  this.onSealed(sources,Object.freeze([...this.missingPoses]));
 }
}
