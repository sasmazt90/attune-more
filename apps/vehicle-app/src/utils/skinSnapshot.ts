import { FaceAlignment, SkinAnalyzer } from './skinAnalyzer';
import { SkinAngle } from './skinMultiAngle';
import { buildSkinMesh, supportedSkinMesh, SkinMesh } from './skinMesh';
import { cameraCrop, type Crop } from './cameraStability';
/** Source photo contract. Numeric writers never receive it; the separate local
 * photo store requires explicit photo retention consent. */
export interface SkinSnapshot {
  experimentalAcneV5?:boolean;
  captureFaceCount?:number;
  general?:import('./skinOverview').SkinOverview;
  dataUrl:string; width:number; height:number; angle:SkinAngle;
  visualError?:string; segmentationMs?:number; maskWidth?:number; maskHeight?:number; meshes:Record<string,SkinMesh>;
  rois:{id:string;nameTr:string;x:number;y:number;w:number;h:number}[];
  exclusions:{x:number;y:number;w:number;h:number;id?:string}[];
  exclusionPolygons?:{id:string;points:{x:number;y:number}[]}[];
  faceContour:{x:number;y:number}[];
  contours:Record<string,{x:number;y:number}[]>;
  crop:{x:number;y:number;width:number;height:number};
  /** Normalized display rectangle only; source pixels and measurement stay full-frame. */
  previewCrop?:Crop;
  photoId?:string;
  expressionScores?:Record<string,number>;
  landmarks?:{x:number;y:number;z?:number}[];
  contoursMeasured?:Record<string,{points:{x:number;y:number}[];lines?:{x:number;y:number}[][];features:number[]}>;
  localMaps?:Record<string,import('./skinLocalMaps').SkinLocalMap>;
  acneCandidates?:Record<string,{x:number;y:number;width:number;height:number;areaPixels?:number;canonicalClass?:string;confidence?:number;candidateId?:string;pointSource?:'box_centroid'|'lesion_center';photoId?:string;modelVersion?:string;providerModelId?:string}[]>;
  localAnalysis?:{loadMs:number;analysisMs:number;allocatedBytes:number};
}
// Anatomical indices in the unmirrored accepted MediaPipe frame. Sampling ROIs
// remain unchanged; presentation graphs are NOT clipped to sampling ROIs.
export const FACE_OUTLINE=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109];
export const SKIN_CONTOURS:Record<string,number[]>={
  forehead:[109,67,103,54,21,71,63,105,66,107,9,336,296,334,293,301,251,284,332,297,338,10,109],
  rightCheek:[50,101,205,187,147,123,116,111,117,118,119,100,126,142,36,50],
  leftCheek:[280,330,349,348,347,346,340,345,352,376,411,425,321,280],
  nose:[168,6,197,195,5,4,1,19,94,2,98,97,129,209,49,48,115,220,45,51,3,196,168,419,248,281,275,440,344,278,279,429,358,327,326,2],
  periorbital:[33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246,33,130,247,30,29,27,28,56,190,243,112,26,22,23,24,110,25,130,263,249,390,373,374,380,381,382,362,398,384,385,386,387,388,466,263],
  chin:[61,146,91,181,84,17,314,405,321,375,291,422,424,418,421,200,201,194,204,202,61,176,148,152,377,400,378,149,176]
};
export function snapshotSkinFrame(canvas:HTMLCanvasElement, alignment:FaceAlignment, angle:SkinAngle, segmentation?:HeadSegmentation):SkinSnapshot {
  const {roiDefinitions,exclusionBoxes,exclusionPolygons}=SkinAnalyzer.regionGeometry(canvas.width,canvas.height,alignment);
  const allowed=angle==='FRONT'?['forehead','nose','chin','periorbital','rightCheek','leftCheek']:[angle==='RIGHT'?'leftCheek':'rightCheek'];
  const rois=roiDefinitions.filter(r=>allowed.includes(r.id)).map(r=>{
    const x=Math.max(0,Math.ceil(r.x)),y=Math.max(0,Math.ceil(r.y));
    return {...r,x,y,w:Math.min(canvas.width,Math.floor(r.x+r.w))-x,h:Math.min(canvas.height,Math.floor(r.y+r.h))-y};
  });
  if(rois.some(r=>r.w<4||r.h<4))throw new Error('INVALID_ROI');
  const landmarks=alignment.landmarks;
  if(!landmarks||landmarks.length<468)throw new Error('MISSING_FACE_CONTOUR');
  const points=(indices:number[])=>indices.map(i=>({x:landmarks[i].x*canvas.width,y:landmarks[i].y*canvas.height}));
  const faceContour=points(FACE_OUTLINE);
  assertCompleteFace(alignment,canvas.width,canvas.height);
  const meshes=Object.fromEntries(allowed.map(id=>[id,supportedSkinMesh(buildSkinMesh(id,landmarks,canvas.width,canvas.height),landmarks,canvas.width,canvas.height)]));
  const metadata={width:canvas.width,height:canvas.height,angle,rois,exclusions:exclusionBoxes,exclusionPolygons,faceContour,meshes,contours:Object.fromEntries(Object.entries(SKIN_CONTOURS).map(([id,indices])=>[id,points(indices)]))};
  // Legacy explicit matte API, retained for compatibility and historical tests.
  // The current product exclusively calls snapshotRawSkinFrame below.
  if(!segmentation)return {...metadata,dataUrl:'',crop:{x:0,y:0,width:canvas.width,height:canvas.height},visualError:'Arka plan ayrıştırılamadı. Sayısal sonuçlar korundu; yeni taramayla görüntüyü tekrar alabilirsiniz.'};
  try {
    const {alpha,bounds}=segmentation.alpha ? {alpha:segmentation.alpha,bounds:alphaBounds(segmentation.alpha,canvas.width,canvas.height)} : headAlpha(segmentation,alignment,canvas.width,canvas.height);
    const skinSupport=new Uint8Array(alpha.length);
    for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++){const i=y*canvas.width+x,m=Math.min(segmentation.height-1,Math.floor(y*segmentation.height/canvas.height))*segmentation.width+Math.min(segmentation.width-1,Math.floor(x*segmentation.width/canvas.width));skinSupport[i]=alpha[i]>230 && (segmentation.faceConfidence ? segmentation.faceConfidence[m]>.35 : segmentation.categories[m]===3) ? 255 : 0;}
    metadata.meshes=Object.fromEntries(Object.entries(meshes).map(([id,mesh])=>[id,supportedSkinMesh(mesh,landmarks,canvas.width,canvas.height,skinSupport)]));
    const output=document.createElement('canvas');output.width=canvas.width;output.height=canvas.height;
    const ctx=output.getContext('2d');if(!ctx)throw Error('SEGMENTATION_CANVAS');
    const pixels=canvas.getContext('2d')!.getImageData(0,0,canvas.width,canvas.height);
    // Change alpha only. Accepted RGB pixels and numerical source remain intact.
    for(let i=0;i<alpha.length;i++)pixels.data[i*4+3]=alpha[i];ctx.putImageData(pixels,0,0);
    const all=[...faceContour,...Object.values(meshes).flatMap(m=>m.points),{x:bounds.x,y:bounds.y},{x:bounds.x+bounds.width,y:bounds.y+bounds.height}];
    const pad=Math.max(bounds.width,bounds.height)*.065;
    const x=Math.min(...all.map(p=>p.x))-pad,y=Math.min(...all.map(p=>p.y))-pad;
    const bottom=bounds.y+bounds.height;
    // The source neck tapers to transparent inside the portrait, never a hard
    // horizontal crop. Padding preserves the whole real head at both zooms.
    const crop={x,y,width:Math.max(...all.map(p=>p.x))-x+pad,height:bottom-y+pad};
    return {...metadata,dataUrl:output.toDataURL('image/png'),crop,segmentationMs:segmentation.elapsedMs,maskWidth:segmentation.width,maskHeight:segmentation.height};
  } catch {return {...metadata,dataUrl:'',crop:{x:0,y:0,width:canvas.width,height:canvas.height},visualError:'Baş görüntüsü güvenilir ayrıştırılamadı. Sayısal sonuçlar korundu; görüntüyü yeni taramayla tekrar alabilirsiniz.'};}

}
/** V3 photo contract: full source rectangle, unchanged RGB and alpha. No mask,
 * segmenter, neck fade, beauty operation or display crop enters this path. */
export function snapshotRawSkinFrame(canvas:HTMLCanvasElement,alignment:FaceAlignment,angle:SkinAngle):SkinSnapshot {
 const metadata=snapshotSkinFrame(canvas,alignment,angle);
 return {...metadata,captureFaceCount:alignment.faceCount,expressionScores:alignment.expressionScores?{...alignment.expressionScores}:undefined,landmarks:alignment.landmarks?.map(p=>({...p})),visualError:undefined,dataUrl:canvas.toDataURL('image/png'),crop:{x:0,y:0,width:canvas.width,height:canvas.height},previewCrop:cameraCrop(alignment.landmarks)};
}
export function snapshotAngleForRegion(id:string,threeAngle:boolean):SkinAngle {
  return !threeAngle?'FRONT':id==='rightCheek'?'LEFT':id==='leftCheek'?'RIGHT':'FRONT';
}
export const REGION_COLORS:Record<string,string>={forehead:'#67e8f9',rightCheek:'#c4b5fd',leftCheek:'#fda4af',nose:'#fcd34d',chin:'#86efac',periorbital:'#93c5fd'};

export interface HeadSegmentation {width:number;height:number;categories:Uint8Array;confidence?:Float32Array;neckConfidence?:Float32Array;faceConfidence?:Float32Array;alpha?:Uint8Array;elapsedMs:number;loadMs?:number;refinementMs?:number;refinementBytes?:number;modelMaskWidth?:number;modelMaskHeight?:number}
/** API masks may already be enlarged to the photo size. Connectivity must run
 * on the actual semantic grid, not millions of duplicated mask pixels. */
export function compactSkinMask(width:number,height:number,categories:Uint8Array,hair:Float32Array,face:Float32Array,neck:Float32Array):HeadSegmentation {
 const w=256,h=256,c=new Uint8Array(w*h),confidence=new Float32Array(w*h),faceConfidence=new Float32Array(w*h),neckConfidence=new Float32Array(w*h);
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=y*w+x,k=Math.min(height-1,Math.floor((y+.5)*height/h))*width+Math.min(width-1,Math.floor((x+.5)*width/w));c[i]=categories[k];confidence[i]=Math.min(1,hair[k]+face[k]);faceConfidence[i]=face[k];neckConfidence[i]=neck[k];}
 return {width:w,height:h,categories:c,confidence,faceConfidence,neckConfidence,elapsedMs:0};
}
export function alphaBounds(alpha:Uint8Array,width:number,height:number){let minX=width,minY=height,maxX=-1,maxY=-1;for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(alpha[y*width+x]>0){minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);}if(maxX<0)throw Error('EMPTY_ALPHA');return {x:minX,y:minY,width:maxX-minX+1,height:maxY-minY+1};}
/** Presentation completeness only; never manufactures missing forehead pixels. */
export function assertCompleteFace(a:FaceAlignment,width:number,height:number) {
 const lm=a.landmarks;if(!lm||lm.length<468)throw Error('MISSING_FACE_CONTOUR');
 const outline=FACE_OUTLINE.map(i=>lm[i]);
 if(outline.some(p=>p.x<=.018||p.x>=.982||p.y<=.018||p.y>=.982))throw Error('INCOMPLETE_HEAD_FRAME');
 const faceHeight=(Math.max(...outline.map(p=>p.y))-Math.min(...outline.map(p=>p.y)))*height;
 if(lm[10].y*height<faceHeight*.06||height-lm[152].y*height<faceHeight*.035)throw Error('INCOMPLETE_HEAD_FRAME');
}
/** Semantic hair/face component seeded on the actual accepted nose landmark. */
export function headAlpha(mask:HeadSegmentation,a:FaceAlignment,width:number,height:number) {
 const {width:mw,height:mh,categories}=mask;
 if(mw<8||mh<8||categories.length!==mw*mh)throw Error('INVALID_SEGMENTATION');
 const lm=a.landmarks!;const seen=new Uint8Array(mw*mh),queue:number[]=[];
 for(const index of [1,4,9,200]){const p=lm[index],x=Math.min(mw-1,Math.max(0,Math.floor(p.x*mw))),y=Math.min(mh-1,Math.max(0,Math.floor(p.y*mh))),i=y*mw+x;if(categories[i]===3){seen[i]=1;queue.push(i);}}
 for(let q=0;q<queue.length;q++){const i=queue[q],x=i%mw,y=Math.floor(i/mw);for(const [nx,ny] of [[x-1,y],[x+1,y],[x,y-1],[x,y+1]])if(nx>=0&&nx<mw&&ny>=0&&ny<mh){const n=ny*mw+nx;if(!seen[n]&&(categories[n]===1||categories[n]===3)){seen[n]=1;queue.push(n);}}}
 if(queue.length<30)throw Error('NO_HEAD_COMPONENT');
 // Retain only a short actual skin neck, bounded by this frame's jaw geometry.
 // Body segmentation cannot introduce a room, clothing or invented neck.
 const faceTop=Math.min(...FACE_OUTLINE.map(i=>lm[i].y)),faceBottom=lm[152].y,faceHeight=faceBottom-faceTop;
 const neckCenter=(lm[148].x+lm[377].x)/2,neckHalf=Math.abs(lm[172].x-lm[397].x)*.65;
 const neckTop=Math.min(lm[172].y,lm[397].y)-faceHeight*.12,neckBottom=faceBottom+faceHeight*.32;
 const neck=new Uint8Array(mw*mh);
 if(mask.neckConfidence){
   if(mask.neckConfidence.length!==mw*mh)throw Error('INVALID_NECK_CONFIDENCE');
   for(let y=Math.max(0,Math.floor(neckTop*mh));y<Math.min(mh,Math.floor(neckBottom*mh));y++)for(let x=Math.max(0,Math.floor((neckCenter-neckHalf)*mw));x<Math.min(mw,Math.ceil((neckCenter+neckHalf)*mw));x++){
     const i=y*mw+x;if(categories[i]===2 && mask.neckConfidence[i]>.5){seen[i]=1;neck[i]=1;}
   }
 }
 // Confidence-independent category raster: holes in face (eyes, mouth) retain
 // original pixels only when completely enclosed by the semantic head. Flood
 // outside first; do not include neck/body classes connected to the outside.
 const outside=new Uint8Array(mw*mh),flood:number[]=[];
 const add=(i:number)=>{if(!seen[i]&&!outside[i]){outside[i]=1;flood.push(i);}};
 for(let x=0;x<mw;x++){add(x);add((mh-1)*mw+x);}for(let y=0;y<mh;y++){add(y*mw);add(y*mw+mw-1);}
 for(let q=0;q<flood.length;q++){const i=flood[q],x=i%mw,y=Math.floor(i/mw);if(x>0)add(i-1);if(x<mw-1)add(i+1);if(y>0)add(i-mw);if(y<mh-1)add(i+mw);}
 for(let i=0;i<seen.length;i++)if(!outside[i])seen[i]=1;
 // A poor mask must not silently truncate accepted forehead or chin.
 for(const index of [10,151,152,148,377,1]){const p=lm[index],x=Math.floor(p.x*mw),y=Math.floor(p.y*mh);let found=false;for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++)if(x+dx>=0&&x+dx<mw&&y+dy>=0&&y+dy<mh&&seen[(y+dy)*mw+x+dx])found=true;if(!found)throw Error('INCOMPLETE_HEAD_MASK');}
 // Bilinear confidence matte, not nearest-neighbour hard category edges.
 // Transition is restricted to uncertain boundary pixels. Interior RGB is
 // untouched; no colour decontamination, outline, beauty filter or broad blur.
 const confidence=mask.confidence;
 if(confidence && confidence.length!==mw*mh)throw Error('INVALID_CONFIDENCE_MASK');
 const edgeRadius=Math.max(1,Math.round(mw/256*2));
 const probability=(x:number,y:number)=>{x=Math.max(0,Math.min(mw-1,x));y=Math.max(0,Math.min(mh-1,y));const i=y*mw+x;if(!seen[i])return 0;
 // Enclosed face/eye/lip pixels stay fully opaque. Confidence softening applies
 // only to the narrow silhouette boundary, never to the facial texture.
 const r=edgeRadius,interior=x>=r&&x<mw-r&&y>=r&&y<mh-r&&seen[i-r]&&seen[i+r]&&seen[i-mw*r]&&seen[i+mw*r];
 if(neck[i] || (categories[i]===3 && y/mh>faceBottom))return neck[i] ? mask.neckConfidence![i] : confidence?.[i]??1;
 return interior?1:(confidence?.[i]??1);};
 // Probability depends only on semantic cells. Evaluate it once instead of
 // repeating four neighborhood checks for every full-resolution output pixel.
 const grid=new Float32Array(mw*mh);
 for(let y=0;y<mh;y++)for(let x=0;x<mw;x++)grid[y*mw+x]=probability(x,y);
 const cached=(x:number,y:number)=>grid[Math.max(0,Math.min(mh-1,y))*mw+Math.max(0,Math.min(mw-1,x))];
 const alpha=new Uint8Array(width*height);let minX=width,minY=height,maxX=-1,maxY=-1;
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const sx=(x+.5)*mw/width-.5,sy=(y+.5)*mh/height-.5,x0=Math.floor(sx),y0=Math.floor(sy),fx=sx-x0,fy=sy-y0;
   const p=(cached(x0,y0)*(1-fx)+cached(x0+1,y0)*fx)*(1-fy)+(cached(x0,y0+1)*(1-fx)+cached(x0+1,y0+1)*fx)*fy;
   // Remove low confidence background fringe instead of retaining pale pixels.
   const t=Math.max(0,Math.min(1,(p-.45)/.4));let value=Math.round(255*t*t*(3-2*t));
   // Layout alpha is applied AFTER semantic confidence thresholding. Otherwise
   // that threshold chops the lower half of the neck fade back into a cap.
   if(y/height>faceBottom){const nx=(x/width-neckCenter)/Math.max(neckHalf,.01),portraitEnd=Math.min(neckBottom,1-.008),end=portraitEnd-Math.max(0,portraitEnd-faceBottom)*.75*Math.min(1,nx*nx),fade=Math.max(0,Math.min(1,(end-y/height)/Math.max(.0001,end-faceBottom)));value=Math.round(value*fade*fade*(3-2*fade));}
   alpha[y*width+x]=value;if(value>0){minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);}
 }

 return {alpha,bounds:{x:minX,y:minY,width:maxX-minX+1,height:maxY-minY+1}};
}
