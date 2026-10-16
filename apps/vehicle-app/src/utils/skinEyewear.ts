import {LOCAL_API_BASE} from './previewLocalApi';
import type {FaceAlignment} from './skinAnalyzer';
export const SKIN_CAPTURE_POLICY='glasses-free-skin-capture-v1';
export const SKIN_EYEWEAR_MODEL_HASH='66f75c686974a04bf956d0ed6411315309afcabd36c400edec743953adafccb9';
export const EYE_REGION=[33,133,159,145,158,153,144,163,7,246,362,263,386,374,385,380,373,390,249,466,70,63,105,66,107,336,296,334,293,300,168,6,197,195];
export type EyewearStatus='CLEAR'|'EYEWEAR_PRESENT'|'UNCERTAIN';
export function eyewearCrop(points:{x:number;y:number}[],width:number,height:number){
 if(points.length!==468&&points.length!==478)throw Error('SKIN_EYEWEAR_LANDMARKS');
 const p=EYE_REGION.map(i=>({x:points[i].x*width,y:points[i].y*height}));
 if(!p.every(v=>Number.isFinite(v.x)&&Number.isFinite(v.y)))throw Error('SKIN_EYEWEAR_LANDMARKS');
 const x0=Math.min(...p.map(v=>v.x)),x1=Math.max(...p.map(v=>v.x)),y0=Math.min(...p.map(v=>v.y)),y1=Math.max(...p.map(v=>v.y));
 const side=Math.max(x1-x0,y1-y0)*1.25,cx=(x0+x1)/2,cy=(y0+y1)/2;
 const left=Math.trunc(Math.max(0,cx-side/2)),top=Math.trunc(Math.max(0,cy-side/2)),right=Math.trunc(Math.min(width,cx+side/2)),bottom=Math.trunc(Math.min(height,cy+side/2));
 if(side<24||Math.min(right-left,bottom-top)<24)throw Error('SKIN_EYEWEAR_DETAIL');
 return {x:left,y:top,width:right-left,height:bottom-top};
}
/** Clear evidence must be continuous; any blocked/unknown/missing frame resets it. */
export class SkinEyewearGate {
 private clearSince:number|undefined;
 observe(status:EyewearStatus,now:number){
  if(status!=='CLEAR'){this.clearSince=undefined;return false;}
  if(this.clearSince===undefined)this.clearSince=now;
  return now-this.clearSince>=900;
 }
 reset(){this.clearSince=undefined;}
}
export class SkinEyewearCheck {
 private controller?:AbortController;
 private epoch=0;
 async assess(canvas:HTMLCanvasElement,alignment:FaceAlignment,current:()=>boolean):Promise<EyewearStatus>{
  if(!alignment.faceDetected||!alignment.isMediaPipeActive||!alignment.landmarks||!current())throw Error('SKIN_EYEWEAR_FRAME');
  this.cancel();const epoch=this.epoch,controller=new AbortController();this.controller=controller;
  const timer=setTimeout(()=>controller.abort(),3000),stale=setInterval(()=>{if(!current())controller.abort();},100);
  try{
   const box=eyewearCrop(alignment.landmarks,canvas.width,canvas.height),roi=document.createElement('canvas');roi.width=roi.height=112;
   const ctx=roi.getContext('2d');if(!ctx)throw Error('SKIN_EYEWEAR_CANVAS');
   // Model-only eye tensor; the accepted source canvas/photo is never resized.
   ctx.drawImage(canvas,box.x,box.y,box.width,box.height,0,0,112,112);
   const frameToken=crypto.randomUUID();
   const response=await fetch(`${LOCAL_API_BASE}/api/local-health/skin/capture-check`,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({processingConsent:true,frameToken,policy:SKIN_CAPTURE_POLICY,eyePhoto:roi.toDataURL('image/png')})});
   if(!response.ok)throw Error('SKIN_EYEWEAR_CHECK_UNAVAILABLE');
   const result=await response.json();
   if(epoch!==this.epoch||!current()||result.frameToken!==frameToken||result.version!==SKIN_CAPTURE_POLICY||result.modelHash!==SKIN_EYEWEAR_MODEL_HASH||!['CLEAR','EYEWEAR_PRESENT','UNCERTAIN'].includes(result.status))throw Error('STALE_EYEWEAR_FRAME');
   return result.status as EyewearStatus;
  } finally {clearTimeout(timer);clearInterval(stale);if(this.controller===controller)this.controller=undefined;}
 }
 cancel(){this.epoch++;this.controller?.abort();this.controller=undefined;}
}
