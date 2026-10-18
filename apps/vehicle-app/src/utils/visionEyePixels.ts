import type { FaceAlignment } from './skinAnalyzer';
import type { EyePixelEvidence } from './spokenVision';
/** Pixel evidence is required in addition to model coordinates. Uncertain patches
 * never satisfy occlusion. Ordinary blinks block scoring immediately; UI warnings
 * use separate persistence hysteresis, so they don't become repeated dialogs.
 */
export function assessEyePixels(ctx:CanvasRenderingContext2D,width:number,height:number,alignment:FaceAlignment) {
 const eye=(indices:number[]):EyePixelEvidence=>{
  const empty:EyePixelEvidence={state:'uncertain',ear:0,darkFraction:0,contrast:0,method:'lid-geometry-and-current-pixels'};
  const l=alignment.landmarks;if(!l||l.length<468||!alignment.isMediaPipeActive||alignment.faceCount!==1)return empty;
  const p=indices.map(i=>({x:l[i].x*width,y:l[i].y*height}));
  const dist=(a:{x:number;y:number},b:{x:number;y:number})=>Math.hypot(a.x-b.x,a.y-b.y);
  const span=dist(p[0],p[3]);if(span<12)return empty;
  const ear=(dist(p[1],p[5])+dist(p[2],p[4]))/(2*span);
  const x=Math.max(0,Math.floor(Math.min(...p.map(v=>v.x)))),y=Math.max(0,Math.floor(Math.min(...p.map(v=>v.y))-span*.08));
  const w=Math.min(width-x,Math.ceil(span)),h=Math.min(height-y,Math.max(4,Math.ceil(span*.38)));
  if(w<12||h<4)return empty;
  const data=ctx.getImageData(x,y,w,h).data;const gray:number[]=[];
  for(let i=0;i<data.length;i+=4)gray.push(.299*data[i]+.587*data[i+1]+.114*data[i+2]);
  const mean=gray.reduce((a,b)=>a+b,0)/gray.length;
  const contrast=Math.sqrt(gray.reduce((a,b)=>a+(b-mean)**2,0)/gray.length),darkFraction=gray.filter(v=>v<mean*.55).length/gray.length;
  // Not a calibrated clinical detector: conservative visible-eye evidence only.
  const state=mean<40||mean>220||contrast<5?'uncertain':ear>.22&&darkFraction>.04?'open':ear<.16&&darkFraction<.16?'closed':'uncertain';
  return {state,ear,darkFraction,contrast,method:'lid-geometry-and-current-pixels'};
 };
 // MediaPipe 33..133 = anatomical RIGHT in unmirrored frames.
 return {right:eye([33,160,158,133,153,144]),left:eye([362,385,387,263,373,380])};
}
