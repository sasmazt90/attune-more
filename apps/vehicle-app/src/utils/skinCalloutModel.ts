import type {SkinSnapshot} from './skinSnapshot';
import {FINDING_ANCHOR,FINDING_DEFS,VIEW_REGIONS,anchorPoint,findingColor,markersOnPhoto,regionView,type FindingViewId,type SkinFinding,type SkinFindingId} from './skinFindings';
import type {FindingCallout} from '../components/skin/SkinFindingCallouts';

export type SkinCaptureIdentities=Partial<Record<string,{captureId:string;pose:string;sourceWidth:number;sourceHeight:number}>>;
export type SkinSourceFrames=Partial<Record<SkinSnapshot['angle'],SkinSnapshot>>;
const bound=(frame:SkinSnapshot|undefined,captures:SkinCaptureIdentities|undefined)=>{
 const source=frame&&captures?.[frame.angle];return !!frame?.photoId&&!!source&&source.captureId===frame.photoId&&source.pose===frame.angle&&source.sourceWidth===frame.width&&source.sourceHeight===frame.height;
};
/** The finding can be decided on a different pose from the region's default photo. */
export function findingSnapshot(findings:SkinFinding[]|undefined,view:'overview'|FindingViewId,selected:SkinFindingId|null,frames:SkinSourceFrames|undefined,captures:SkinCaptureIdentities|undefined,fallback:SkinSnapshot|undefined,sourceKey?:string|null):SkinSnapshot|undefined{
 if(!selected||!frames)return fallback;
 const rows=(findings||[]).filter(f=>f.id===selected&&f.status==='seen'&&(view==='overview'||VIEW_REGIONS[view].includes(f.region)));
 if(sourceKey)rows.sort((a,b)=>Number(`${b.region}:${b.id}`===sourceKey)-Number(`${a.region}:${a.id}`===sourceKey));
 for(const f of rows){
  const pose=FINDING_DEFS[f.id].kind==='count'?(f.countPose||f.markers?.find(m=>m.pose)?.pose||f.pose):f.pose;
  const frame=pose&&frames[pose];if(frame&&bound(frame,captures))return frame;
 }
 return fallback;
}
/** Never infer a lesion location from another pose, session or a generic face. */
export function sourceBoundCallouts(findings:SkinFinding[]|undefined,snapshot:SkinSnapshot|undefined,captures:SkinCaptureIdentities|undefined,view:'overview'|FindingViewId,selected:SkinFindingId|null):FindingCallout[]{
 if(!snapshot?.photoId||snapshot.visualError)return [];
 if(!bound(snapshot,captures))return [];
 return (findings||[]).flatMap(f=>{
  if(f.status!=='seen'||!(f.id in FINDING_DEFS)||(view!=='overview'&&!VIEW_REGIONS[view].includes(f.region)))return [];
  const marker=markersOnPhoto(f,snapshot.angle)[0];
  const anatomical=FINDING_ANCHOR[f.id][regionView(f.region)],lm=snapshot.landmarks;
  // Anatomical presence labels refer to the measured region, not an invented lesion.
  const anchor=marker?{x:marker.x,y:marker.y}:f.pose===snapshot.angle&&FINDING_DEFS[f.id].kind!=='count'&&lm&&lm.length>=468&&anatomical!==undefined?anchorPoint(anatomical,lm,snapshot.width,snapshot.height):null;
  if(!anchor||!Number.isFinite(anchor.x)||!Number.isFinite(anchor.y)||anchor.x<0||anchor.y<0||anchor.x>snapshot.width||anchor.y>snapshot.height)return [];
  return [{key:`${f.region}:${f.id}`,id:f.id,label:FINDING_DEFS[f.id].label,color:findingColor(f.id),anchor,active:f.id===selected}];
 });
}
