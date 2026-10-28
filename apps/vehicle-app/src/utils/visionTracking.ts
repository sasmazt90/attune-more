import type { NormalizedLandmark } from '@mediapipe/tasks-vision';
import { SkinAnalyzer, type FaceAlignment } from './skinAnalyzer';
import { visionFrameQuality } from './visionFrameQuality';
import {occlusionKind} from './visionEyeState';
import type { Eye, EyePixelEvidence, LetterConditions } from './spokenVision';
export const VISION_TRACKING_RULES={baselineMs:1000,eyeHoldMs:600,maxFrameGapMs:750,eyeHoldSamples:3,distanceEnter:.15,distanceExit:.10,distanceHoldMs:600,recoveryMs:350,openLidRatio:.62} as const;
/** Native geometry remains distinct from occlusion. The open candidate keeps
 * a margin above the closed bound, plus low blink and visible-template gates.
 * Physical wink evidence had an otherwise visible test eye at ratios .63-.72;
 * .74 rejected it despite low blink and strong appearance correlation. */
export function nativeLidState(ratio:number,blink:number|null,baselineBlink:number):'closed'|'open'|'uncertain'{
 if(ratio<.58&&((blink!==null&&blink>baselineBlink+.28)||ratio<.42))return 'closed';
 if(ratio>VISION_TRACKING_RULES.openLidRatio&&blink!==null&&blink<Math.min(.90,baselineBlink+.25))return 'open';
 return 'uncertain';
}
export function baselineEyeVisible(ear:number,blink:number|null,palm:number){return ear>.12&&blink!==null&&blink<.55&&palm<.25;}
/** Physical palm occlusion can have accidental narrow-ROI correlation while
 * the larger eye/brow ROI is strongly replaced (change > .75, NCC < .08).
 * Require that stronger wide evidence when narrow correlation is ambiguous. */
export function opaqueEyeAppearance(change:number,wideCorrelation:number,narrowCorrelation:number,narrowChange=0){
 // An eye-sized opaque object need not replace the still-visible eyebrow.
 // Strong replacement of the actual narrow eye ROI uses the same change/NCC
 // bounds; anatomical side, visible head, opposite eye and hold still gate.
 return narrowChange>.65&&narrowCorrelation<.18||change>.65&&wideCorrelation<.18&&(narrowCorrelation<.25||(change>.75&&wideCorrelation<.08));
}
/** Source coordinates are unmirrored. The bridge-to-nose line also rotates
 * with the head, so anatomical identity does not come from screen crop/zoom. */
export function eyeOnAnatomicalSide(side:Eye,x:number,y:number,bridge:{x:number;y:number},nose:{x:number;y:number}){
 const dy=nose.y-bridge.y,dx=nose.x-bridge.x;if(dy<=0)return false;
 const signed=(x-bridge.x)*dy-(y-bridge.y)*dx;
 return side==='RIGHT'?signed<0:signed>0;
}
export function sourceFaceFramed(minX:number,maxX:number,minY:number,maxY:number,eyePixelsAvailable:boolean){return minX>.005&&maxX<.995&&minY>.005&&maxY<.995&&eyePixelsAvailable;}
const eyeIds={RIGHT:[33,160,158,133,153,144],LEFT:[362,385,387,263,373,380]};
const anchors=[10,168,1,4,2,234,454,127,356,93,323];
// Forehead, nose bridge and temples; exclude mouth/chin distances.
const pairs=[[10,168],[10,1],[168,2],[234,454],[127,356],[93,323]];
type Patch={gray:number[];rgb:number[];mean:number;gradient:number};
type Box={x:number;y:number;width:number;height:number};
const median=(v:number[])=>[...v].sort((a,b)=>a-b)[Math.floor(v.length/2)];
/** One corrupted head pair under an eye cover must not veto all other
 * agreeing source measurements. Keep the existing .24 agreement range,
 * at least three pairs, and reject competing clusters differing by more
 * than the existing .10 recovery band. Near/far thresholds are unchanged. */
export function headScaleConsensus(ratios:number[]):number|null{
 if(ratios.length<3||!ratios.every(Number.isFinite))return null;
 const values=[...ratios].sort((a,b)=>a-b),span=(v:number[])=>v[v.length-1]-v[0];
 if(span(values)<.24)return median(values);
 if(values.length<4)return null;
 const candidates=[values.slice(1),values.slice(0,-1)].filter(v=>span(v)<.24);
 if(!candidates.length||candidates.length===2&&Math.abs(median(candidates[0])-median(candidates[1]))>VISION_TRACKING_RULES.distanceExit)return null;
 return median(candidates[0]);
}
export class SustainedEyeState {
 private candidate='uncertain';private since=0;private last:number|null=null;private samples=0;private cadence:number|null=null;
 update(candidate:EyePixelEvidence['state'],now:number){
  const occluded=(v:string)=>v==='closed'||v==='covered';
  const gap=this.last===null?null:now-this.last;
  // Consistently slow fresh frames can establish a hold. A sudden stall in a
  // previously fast stream still breaks continuity, even inside freshness.
  const discontinuity=gap===null||gap<0||gap>VISION_TRACKING_RULES.maxFrameGapMs||this.cadence!==null&&gap>Math.max(300,this.cadence*2);
  this.cadence=gap!==null&&gap>0&&gap<=VISION_TRACKING_RULES.maxFrameGapMs?gap:null;
  if(discontinuity||candidate!==this.candidate&&!(occluded(candidate)&&occluded(this.candidate))){this.since=now;this.samples=0;}
  this.last=now;this.candidate=candidate;this.samples++;
  const heldMs=now-this.since;
  return {state:occluded(candidate)?heldMs>=VISION_TRACKING_RULES.eyeHoldMs&&this.samples>=VISION_TRACKING_RULES.eyeHoldSamples?candidate:'uncertain':candidate,heldMs} as {state:EyePixelEvidence['state'];heldMs:number};
 }
}
export class HeadDistanceHysteresis {
 private committed:'stable'|'near'|'far'='stable';private candidate='';private since=0;private last:number|null=null;
 update(relative:number|null,now:number,reliable=true):'stable'|'near'|'far'|'unknown'{
  if(!Number.isFinite(now)){this.candidate='';this.last=null;return 'unknown';}
  if(this.last!==null&&now-this.last>VISION_TRACKING_RULES.maxFrameGapMs)this.candidate='';this.last=now;if(relative===null||!Number.isFinite(relative)||!reliable){this.candidate='';return 'unknown';}
  const target=relative>VISION_TRACKING_RULES.distanceEnter?'near':relative< -VISION_TRACKING_RULES.distanceEnter?'far':Math.abs(relative)<=VISION_TRACKING_RULES.distanceExit?'stable':this.committed;
  if(target!==this.committed){if(this.candidate!==target){this.candidate=target;this.since=now;}if(now-this.since>=(target==='stable'?VISION_TRACKING_RULES.recoveryMs:VISION_TRACKING_RULES.distanceHoldMs))this.committed=target;}else this.candidate='';
  return this.committed;
 }
}
/** A lid-bounded ROI shrinks as the eye closes and can fall below patch's
 * four-pixel minimum, making a valid closure impossible to evaluate. Use fixed
 * eye-corner geometry so open/closed/covered pixels share the same source area.
 * The .35 lid band covers the open-eye baseline; padding remains unchanged. */
export function visionEyeRegion(p:NormalizedLandmark[],ids:number[],w:number,h:number,padding:number):Box{
 const a=p[ids[0]],b=p[ids[3]],dx=(b.x-a.x)*w,dy=(b.y-a.y)*h,span=Math.hypot(dx,dy),cx=(a.x+b.x)*w/2,cy=(a.y+b.y)*h/2;
 const width=Math.abs(dx)+span*padding*2,height=Math.abs(dy)+span*(.35+padding*2);
 return {x:cx-width/2,y:cy-height/2,width,height};
}
/** At least three spatially distinct visible head patches must agree. Several
 * adjacent nose landmarks alone cannot stand in for the entire missing face. */
export function distributedHeadAnchors(points:{x:number;y:number}[],templeWidth:number){
 if(!Number.isFinite(templeWidth)||templeWidth<=0)return false;
 const independent:{x:number;y:number}[]=[];
 for(const p of points)if(Number.isFinite(p.x)&&Number.isFinite(p.y)&&independent.every(q=>Math.hypot(p.x-q.x,p.y-q.y)>=templeWidth*.20))independent.push(p);
 return independent.length>=3;
}

function patch(ctx:CanvasRenderingContext2D,b:Box):Patch|null{
 const {width:w,height:h}=ctx.canvas;if(b.x<0||b.y<0||b.x+b.width>w||b.y+b.height>h||b.width<8||b.height<4)return null;
 const data=ctx.getImageData(Math.floor(b.x),Math.floor(b.y),Math.ceil(b.width),Math.ceil(b.height)),gray:number[]=[],rgb:number[]=[];
 for(let y=0;y<16;y++)for(let x=0;x<24;x++){const i=(Math.min(data.height-1,Math.floor(y*data.height/16))*data.width+Math.min(data.width-1,Math.floor(x*data.width/24)))*4;rgb.push(data.data[i],data.data[i+1],data.data[i+2]);gray.push(.299*data.data[i]+.587*data.data[i+1]+.114*data.data[i+2]);}
 let gradient=0;for(let i=0;i<gray.length;i++)if(i%24)gradient+=Math.abs(gray[i]-gray[i-1]);
 return {gray,rgb,mean:gray.reduce((s,v)=>s+v,0)/gray.length,gradient:gradient/gray.length};
}
function compare(a:Patch,b:Patch){let cross=0,aa=0,bb=0,changed=0;for(let i=0;i<a.gray.length;i++){const x=a.gray[i]-a.mean,y=b.gray[i]-b.mean;cross+=x*y;aa+=x*x;bb+=y*y;const j=i*3;const d=Math.abs(a.rgb[j]-b.rgb[j])+Math.abs(a.rgb[j+1]-b.rgb[j+1])+Math.abs(a.rgb[j+2]-b.rgb[j+2]);if(d>85)changed++;}return {correlation:cross/Math.max(1,Math.sqrt(aa*bb)),change:changed/a.gray.length};}
function inside(p:NormalizedLandmark,b:Box,w:number,h:number){return p.x*w>=b.x&&p.x*w<=b.x+b.width&&p.y*h>=b.y&&p.y*h<=b.y+b.height;}
function handCoverage(hands:NormalizedLandmark[][],b:Box,w:number,h:number){
 // Use the palm (not a broad whole-hand box). Its projected polygon must
 // actually overlap the eye ROI; a raised hand elsewhere cannot pass.
 let covered=0;for(const hand of hands){const hull=[0,1,5,9,13,17].map(i=>({x:hand[i].x*w,y:hand[i].y*h}));let count=0;
  for(let y=0;y<8;y++)for(let x=0;x<12;x++){const px=b.x+(x+.5)*b.width/12,py=b.y+(y+.5)*b.height/8;let hit=false;for(let i=0,j=hull.length-1;i<hull.length;j=i++){const a=hull[i],z=hull[j];if((a.y>py)!==(z.y>py)&&px<(z.x-a.x)*(py-a.y)/(z.y-a.y)+a.x)hit=!hit;}if(hit)count++;}covered=Math.max(covered,count/96);
 }return covered;
}
export interface VisionModelFrame {landmarks:NormalizedLandmark[][];hands:NormalizedLandmark[][];blinkRight:number|null;blinkLeft:number|null;inferenceMs:number;frameTime:number}
export interface VisionEvidence {alignment:FaceAlignment;quality:ReturnType<typeof visionFrameQuality>;conditions:LetterConditions;distanceSamples:number;distanceRatios:number[];inferenceMs:number;width:number;height:number;delegate?:'CPU'|'GPU'}
/** Templates and personal baseline stay in worker memory and are destroyed on
 * close. No image, identity embedding or absolute camera distance is stored. */
export class VisionTracker {
 private baseline:Record<Eye,{ear:number;blink:number;patch:Patch;wide:Patch}>|null=null;
 private baselinePairs:number[]|null=null;private baselinePoseHeight=0;private baselineTempleWidth=0;private samples:{ears:number[];blinks:number[];narrow:Patch[];wide:Patch[];lengths:number[]}[]=[];private baselineSince=0;private lastFrame=0;
 private eyeHold={RIGHT:new SustainedEyeState(),LEFT:new SustainedEyeState()};
 private distance:'learning'|'stable'|'near'|'far'|'unknown'='learning';private distanceHold=new HeadDistanceHysteresis();
 private lastPoints:NormalizedLandmark[]|null=null;private trustedPatches:{id:number;image:Patch;box:Box}[]=[];private trackedScaleReliable=false;
 private followPixels(ctx:CanvasRenderingContext2D,w:number,h:number):NormalizedLandmark[]|null{
  this.trackedScaleReliable=false;if(!this.lastPoints||this.trustedPatches.length<3)return null;
  const hits:{id:number;dx:number;dy:number;correlation:number}[]=[];
  for(const a of this.trustedPatches){let best={dx:0,dy:0,correlation:-1};for(let dy=-12;dy<=12;dy+=3)for(let dx=-12;dx<=12;dx+=3){const p=patch(ctx,{...a.box,x:a.box.x+dx,y:a.box.y+dy});if(!p)continue;const cmp=compare(a.image,p);if(cmp.correlation>best.correlation)best={dx,dy,correlation:cmp.correlation};}if(best.correlation>.78)hits.push({id:a.id,...best});}
  if(hits.length<3)return null;const dx=median(hits.map(v=>v.dx)),dy=median(hits.map(v=>v.dy));if(hits.filter(v=>Math.hypot(v.dx-dx,v.dy-dy)<5).length<3)return null;
  const templeWidth=Math.hypot((this.lastPoints[454].x-this.lastPoints[234].x)*w,(this.lastPoints[454].y-this.lastPoints[234].y)*h);
  if(!distributedHeadAnchors(hits.map(v=>({x:this.lastPoints![v.id].x*w,y:this.lastPoints![v.id].y*h})),templeWidth))return null;
  const scales:number[]=[];for(let i=0;i<hits.length;i++)for(let j=i+1;j<hits.length;j++){const a=this.lastPoints[hits[i].id],b=this.lastPoints[hits[j].id],x=(a.x-b.x)*w,y=(a.y-b.y)*h,d=Math.hypot(x,y);if(d>80)scales.push(Math.hypot(x+hits[i].dx-hits[j].dx,y+hits[i].dy-hits[j].dy)/d);}
  if(scales.length<2||Math.max(...scales)-Math.min(...scales)>.06)return null;
  const scale=median(scales),cx=median(hits.map(v=>this.lastPoints![v.id].x)),cy=median(hits.map(v=>this.lastPoints![v.id].y));
  const tx=median(hits.map(v=>v.dx/w-(this.lastPoints![v.id].x-cx)*(scale-1))),ty=median(hits.map(v=>v.dy/h-(this.lastPoints![v.id].y-cy)*(scale-1)));
  // Scale comes from several independently matched, separated visible head
  // patches. Missing eye landmarks themselves never supply cover or distance.
  const p=this.lastPoints.map(v=>({...v,x:cx+(v.x-cx)*scale+tx,y:cy+(v.y-cy)*scale+ty,z:v.z*scale}));this.lastPoints=p;
  this.trustedPatches=this.trustedPatches.map(v=>({...v,box:{x:cx*w+(v.box.x-cx*w)*scale+tx*w,y:cy*h+(v.box.y-cy*h)*scale+ty*h,width:v.box.width*scale,height:v.box.height*scale}}));this.trackedScaleReliable=true;return p;
 }
 assess(ctx:CanvasRenderingContext2D,w:number,h:number,model:VisionModelFrame,now:number,eye:Eye|null):VisionEvidence{
  if(!this.baseline&&this.lastFrame&&now-this.lastFrame>VISION_TRACKING_RULES.maxFrameGapMs){this.samples=[];this.baselineSince=0;}this.lastFrame=now;
  let p=model.landmarks.length===1?model.landmarks[0]:null;const native=!!p;let tracked=false;
  if(!p&&model.landmarks.length===0){p=this.followPixels(ctx,w,h);tracked=!!p;}
  const absent:EyePixelEvidence={state:'uncertain',ear:null,darkFraction:null,contrast:null,method:'no-reliable-eye-pixels'};
  if(!p){this.eyeHold.RIGHT.update('uncertain',now);this.eyeHold.LEFT.update('uncertain',now);this.distanceHold.update(null,now);}
  if(!p){const a:FaceAlignment={faceDetected:false,isMediaPipeActive:true,faceCount:model.landmarks.length,box:undefined,yaw:0,pitch:0,roll:0,scaleRatio:0,isAligned:false,guidanceTextTr:'Yüzünüzü kamera görüntüsünde tutun.'};return {alignment:a,quality:SkinAnalyzer.checkQuality(ctx,w,h,false),conditions:{observedAt:now,cameraLive:true,modelActive:true,faceCount:model.landmarks.length,qualityValid:false,positionValid:false,relativeScaleChange:null,right:absent,left:absent,distancePolicy:'head-anchors-hysteresis-v1',distanceState:'unknown',blocker:'face'},distanceSamples:this.samples.length,distanceRatios:[],inferenceMs:model.inferenceMs,width:w,height:h};}
  const xs=p.slice(0,468).map(v=>v.x),ys=p.slice(0,468).map(v=>v.y),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const templeWidth=Math.hypot((p[454].x-p[234].x)*w,(p[454].y-p[234].y)*h);
  // After neutral preparation, jaw opening cannot change the pitch denominator.
  const poseHeight=this.baselinePoseHeight?this.baselinePoseHeight*templeWidth/this.baselineTempleWidth:p[152].y-p[10].y;
  const yaw=(p[1].x-(p[33].x+p[263].x)/2)/Math.max(.01,Math.abs(p[33].x-p[263].x)),pitch=(p[1].y-p[10].y)/Math.max(.01,poseHeight),roll=Math.atan2((p[454].y-p[234].y)*h,(p[454].x-p[234].x)*w);
  const alignment:FaceAlignment={faceDetected:true,isMediaPipeActive:true,faceCount:1,box:{x:minX*w,y:minY*h,width:(maxX-minX)*w,height:(maxY-minY)*h},yaw,pitch,roll,scaleRatio:maxX-minX,isAligned:true,guidanceTextTr:'Yüz izleniyor',landmarks:p};
  const quality=visionFrameQuality(ctx,w,h,alignment,eye);
  const measurements=(['RIGHT','LEFT'] as Eye[]).map(side=>{const ids=eyeIds[side],q=ids.map(i=>p![i]),dist=(i:number,j:number)=>Math.hypot((q[i].x-q[j].x)*w,(q[i].y-q[j].y)*h);return {anatomicalSideValid:eyeOnAnatomicalSide(side,(q[0].x+q[3].x)/2,(q[0].y+q[3].y)/2,p![168],p![2]),ear:(dist(1,5)+dist(2,4))/(2*Math.max(1,dist(0,3))),narrow:patch(ctx,visionEyeRegion(p!,ids,w,h,.08)),wide:patch(ctx,visionEyeRegion(p!,ids,w,h,.40)),box:visionEyeRegion(p!,ids,w,h,.12),blink:side==='RIGHT'?model.blinkRight:model.blinkLeft};});
  const lengths=pairs.map(([a,b])=>Math.hypot((p![a].x-p![b].x)*w,(p![a].y-p![b].y)*h,((p![a].z||0)-(p![b].z||0))*w));
  const poseValid=Math.abs(yaw)<.38&&pitch>.30&&pitch<.80&&Math.abs(roll)<.55;
  // Display zoom and an arbitrary fraction of the full camera frame cannot
  // establish usable eye detail. Keep whole-face bounds and actual ROI pixels;
  // illumination/focus and the immutable relative head baseline still gate.
  const framed=sourceFaceFramed(minX,maxX,minY,maxY,measurements.every(v=>!!v.narrow&&!!v.wide));
  // A hand-covered ROI must never become the personal open-eye template,
  // even when the face model predicts plausible eyelid landmarks behind it.
  if(!this.baseline&&native&&poseValid&&framed&&quality.isValid&&measurements.every(v=>v.anatomicalSideValid&&v.narrow&&v.wide&&baselineEyeVisible(v.ear,v.blink,handCoverage(model.hands,v.box,w,h)))){
   if(!this.baselineSince)this.baselineSince=now;this.samples.push({ears:measurements.map(v=>v.ear),blinks:measurements.map(v=>v.blink!),narrow:measurements.map(v=>v.narrow!),wide:measurements.map(v=>v.wide!),lengths});
   if(now-this.baselineSince>=VISION_TRACKING_RULES.baselineMs&&this.samples.length>=6){this.baselinePoseHeight=p![152].y-p![10].y;this.baselineTempleWidth=templeWidth;this.baselinePairs=lengths.map((_,i)=>median(this.samples.map(s=>s.lengths[i])));const sample=this.samples[Math.floor(this.samples.length/2)];this.baseline={RIGHT:{ear:median(this.samples.map(s=>s.ears[0])),blink:median(this.samples.map(s=>s.blinks[0])),patch:sample.narrow[0],wide:sample.wide[0]},LEFT:{ear:median(this.samples.map(s=>s.ears[1])),blink:median(this.samples.map(s=>s.blinks[1])),patch:sample.narrow[1],wide:sample.wide[1]}};this.distance='stable';}
  }else if(!this.baseline){this.baselineSince=0;this.samples=[];}
  const ratios=this.baselinePairs?lengths.map((v,i)=>v/this.baselinePairs![i]-1):[];
  const reliableRatios=ratios.filter((_,i)=>!model.hands.some(hand=>pairs[i].some(id=>{const b={x:p![id].x*w-10,y:p![id].y*h-10,width:20,height:20};return hand.some(v=>inside(v,b,w,h));})));
  const relative=ratios.length&&(native||this.trackedScaleReliable)?headScaleConsensus(reliableRatios):null;
  const distanceReliable=relative!==null&&poseValid&&framed;
  if(this.baseline)this.distance=this.distanceHold.update(relative,now,distanceReliable);
  const states=measurements.map((v,i)=>{const side=(i===0?'RIGHT':'LEFT') as Eye,base=this.baseline?.[side];const cmp=base&&v.narrow?compare(base.patch,v.narrow):null,wide=base&&v.wide?compare(base.wide,v.wide):null;
   let candidate:EyePixelEvidence['state']='uncertain',method='personal-lid-geometry-and-blink';const palm=handCoverage(model.hands,v.box,w,h);
   if(v.anatomicalSideValid&&base&&cmp&&wide){const ratio=v.ear/base.ear;
    if(palm>.55&&(wide.change>.50||cmp.correlation<.25)&&wide.correlation<.55){candidate='covered';method='palm-over-eye-and-local-appearance';}
    else if(native&&palm<.25&&wide.change<.50&&nativeLidState(ratio,v.blink,base.blink)==='closed'){candidate='closed';}
    else if(opaqueEyeAppearance(wide.change,wide.correlation,cmp.correlation,cmp.change)){candidate='covered';method='opaque-local-appearance-and-visible-head';}
    else if(native&&palm<.25&&wide.change<.45&&nativeLidState(ratio,v.blink,base.blink)==='open'&&cmp.correlation>.20){candidate='open';}
    else if(tracked&&cmp.correlation>.78&&wide.change<.25){candidate='open';method='trusted-eye-template-and-visible-head';}
   }
   const held=this.eyeHold[side].update(candidate,now);
   return {...held,ear:native?v.ear:null,darkFraction:null,contrast:v.narrow?.gradient??null,method,occlusionKind:occlusionKind(method),baselineEar:base?.ear,blinkCoefficient:v.blink,appearanceChange:wide?.change,templateCorrelation:cmp?.correlation,palmCoverage:palm,wideTemplateCorrelation:wide?.correlation,candidateState:candidate} as EyePixelEvidence;
  });
  // Refresh only visible independent patches, excluding palms and suspect eyes.
  if(native&&poseValid){this.lastPoints=p;this.trustedPatches=anchors.filter(id=>!model.hands.some(hand=>hand.some(v=>Math.hypot(v.x-p![id].x,v.y-p![id].y)<.08))).map(id=>{const box={x:p![id].x*w-9,y:p![id].y*h-9,width:18,height:18};return {id,box,image:patch(ctx,box)!};}).filter(v=>v.image&&v.image.gradient>5);}
  const blocker=!framed?'framing':!poseValid?'pose':!quality.isValid?quality.status==='TOO_DARK'?'light':quality.status==='TOO_BRIGHT'?'bright':'blur':!this.baseline?'preparing':this.distance==='unknown'?'distance-unknown':this.distance==='near'?'recede':this.distance==='far'?'approach':null;
  return {alignment,quality,conditions:{observedAt:now,cameraLive:true,modelActive:true,faceCount:1,qualityValid:quality.isValid,positionValid:!blocker,relativeScaleChange:relative,right:states[0],left:states[1],distancePolicy:'head-anchors-hysteresis-v1',distanceState:this.distance,blocker,trackingMethod:native?'mediapipe-face-and-head-anchors':'visible-anchor-template-tracking'},distanceSamples:this.samples.length,distanceRatios:ratios,inferenceMs:model.inferenceMs,width:w,height:h};
 }
}
