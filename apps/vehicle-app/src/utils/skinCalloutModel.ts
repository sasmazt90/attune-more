import type {SkinSnapshot} from './skinSnapshot';
import {FINDING_ANCHOR,FINDING_DEFS,VIEW_REGIONS,anchorPoint,findingAreaPath,findingColor,isFindingView,markerSubtype,markersOnPhoto,regionView,type AcneSubtype,type FindingViewId,type SkinFinding,type SkinFindingId,type SkinFindingKind,type SkinFindingMarker} from './skinFindings';
import {paintPath,type PaintRegionId} from './skinTypePaint';
import type {FindingCallout} from '../components/skin/SkinFindingCallouts';
import type {CalloutRect} from './skinCalloutLayout';

export type SkinCaptureIdentities=Partial<Record<string,{captureId:string;pose:string;sourceWidth:number;sourceHeight:number}>>;
export type SkinSourceFrames=Partial<Record<SkinSnapshot['angle'],SkinSnapshot>>;
const bound=(frame:SkinSnapshot|undefined,captures:SkinCaptureIdentities|undefined)=>{
 const source=frame&&captures?.[frame.angle];return !!frame?.photoId&&!!source&&source.captureId===frame.photoId&&source.pose===frame.angle&&source.sourceWidth===frame.width&&source.sourceHeight===frame.height;
};
const inView=(f:SkinFinding,view:string)=>view==='overview'||(isFindingView(view)&&VIEW_REGIONS[view].includes(f.region));
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
/** One label per finding on this photo. A selected finding is the only one that keeps a label.
 * Never infer a lesion location from another pose, session or a generic face. */
export function sourceBoundCallouts(findings:SkinFinding[]|undefined,snapshot:SkinSnapshot|undefined,captures:SkinCaptureIdentities|undefined,view:'overview'|FindingViewId,selected:SkinFindingId|null):FindingCallout[]{
 if(!snapshot?.photoId||snapshot.visualError)return [];
 if(!bound(snapshot,captures))return [];
 const seen=new Set<SkinFindingId>();
 return (findings||[]).flatMap(f=>{
  if(f.status!=='seen'||!(f.id in FINDING_DEFS)||seen.has(f.id)||!inView(f,view)||(selected&&f.id!==selected))return [];
  const marker=markersOnPhoto(f,snapshot.angle)[0];
  const anatomical=FINDING_ANCHOR[f.id][regionView(f.region)],lm=snapshot.landmarks;
  // Anatomical presence labels refer to the measured region, not an invented lesion.
  const anchor=marker?{x:marker.x,y:marker.y}:f.pose===snapshot.angle&&FINDING_DEFS[f.id].kind!=='count'&&lm&&lm.length>=468&&anatomical!==undefined?anchorPoint(anatomical,lm,snapshot.width,snapshot.height):null;
  if(!anchor||!Number.isFinite(anchor.x)||!Number.isFinite(anchor.y)||anchor.x<0||anchor.y<0||anchor.x>snapshot.width||anchor.y>snapshot.height)return [];
  seen.add(f.id);
  return [{key:`${f.region}:${f.id}`,id:f.id,label:FINDING_DEFS[f.id].callout||FINDING_DEFS[f.id].label,color:findingColor(f.id),anchor,active:f.id===selected}];
 });
}
export type FindingLayer={id:SkinFindingId;color:string;kind:SkinFindingKind;area:string|null;markers:SkinFindingMarker[]};
/** What each finding draws on this photo: real markers of this photo, or the measured region's outline when the finding
 * was decided on this photo. A finding with neither draws nothing. */
export function findingLayers(findings:SkinFinding[]|undefined,snapshot:SkinSnapshot|undefined,view:string,selected:SkinFindingId|null,markerType:AcneSubtype|null=null):FindingLayer[]{
 if(!snapshot||snapshot.visualError)return [];
 const scoped=(findings||[]).filter(f=>f.status==='seen'&&f.id in FINDING_DEFS&&inView(f,view)&&(!selected||f.id===selected));
 const lm=snapshot.landmarks,located=!!lm&&lm.length>=468;
 return [...new Set(scoped.map(f=>f.id))].flatMap(id=>{
  const rows=scoped.filter(f=>f.id===id),kind=FINDING_DEFS[id].kind;
  const markers=rows.flatMap(f=>markersOnPhoto(f,snapshot.angle)).filter(m=>!markerType||markerSubtype(m)===markerType);
  const here=rows.filter(f=>f.pose===snapshot.angle);
  const area=kind!=='count'&&located&&here.length
   ?findingAreaPath(id,lm,snapshot.width,snapshot.height)||[...new Set(here.map(f=>f.region as PaintRegionId))].map(r=>paintPath(r,lm,snapshot.width,snapshot.height)).filter(Boolean).join('')||null
   :null;
  return area||markers.length?[{id,color:findingColor(id),kind,area,markers}]:[];
 });
}
/** Findings of this view with a value but nothing to draw on this photo. They stay in the results panel. */
export function unlocatedFindings(findings:SkinFinding[]|undefined,snapshot:SkinSnapshot|undefined,view:string,selected:SkinFindingId|null):SkinFindingId[]{
 const drawn=new Set(findingLayers(findings,snapshot,view,selected).map(l=>l.id));
 return [...new Set((findings||[]).filter(f=>f.status==='seen'&&f.id in FINDING_DEFS&&inView(f,view)&&(!selected||f.id===selected)&&!drawn.has(f.id)).map(f=>f.id))];
}
const FEATURES=[[33,133,159,145,70,63,105,107],[263,362,386,374,300,293,334,336],[168,6,197,195,5,4,1,19,94,2,98,327,129,358],[61,291,0,17,37,267,84,314]];
/** Eyes with brows, nose and mouth in source pixels: labels stay off them. */
export function faceFeatures(snapshot:SkinSnapshot|undefined):CalloutRect[]{
 const lm=snapshot?.landmarks;
 if(!snapshot||!lm||lm.length<468)return [];
 return FEATURES.map(indices=>{
  const xs=indices.map(i=>lm[i].x*snapshot.width),ys=indices.map(i=>lm[i].y*snapshot.height),x=Math.min(...xs),y=Math.min(...ys);
  return {x,y,w:Math.max(...xs)-x,h:Math.max(...ys)-y};
 });
}
/** Bounding box of the face in source pixels. */
export function faceBox(snapshot:SkinSnapshot|undefined):CalloutRect|null{
 const lm=snapshot?.landmarks;
 if(!snapshot||!lm||lm.length<468)return null;
 const x=lm[234].x*snapshot.width,right=lm[454].x*snapshot.width,y=lm[10].y*snapshot.height,bottom=lm[152].y*snapshot.height;
 return {x:Math.min(x,right),y,w:Math.abs(right-x),h:bottom-y};
}
