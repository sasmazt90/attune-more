import type { SkinMesh } from './skinMesh';
import { bagCellTriangles,closedSurfaceCellTriangles } from './skinMesh';

export const SHINE_METHOD='surface-specular-candidate-v1';
export const SHINE_PARAMETERS={minValue:.60,maxSaturation:.42,minLocalContrast:.04,contrastSpan:.16,candidateThreshold:.15,maxClippedFraction:.03,maxSamples:128} as const;
export type SurfaceInput={width:number;height:number;pixels:Uint8ClampedArray;region:string;mesh:SkinMesh;exclusions:{x:number;y:number;w:number;h:number}[];qualityValid:boolean};
export type SurfaceGrid={x:number;y:number;step:number;width:number;height:number;valid:Uint8Array;redness:Float32Array;shine:Float32Array;validSamples:number;shineSamples:number;clippedFraction:number;shineAreaPercent:number|null;shineUnavailable:string|null;allocatedBytes:number};

/** Historical maps/contours retain their original triangle support. */
export function closedSurfaceSupportEnabled(criterion?:string|null,calibrationVersion?:string|null):boolean {
 return criterion==='dry'&&calibrationVersion==='eligible-flake-luma-union-v3'||criterion==='sag'&&['contour-fold-visible-region-unique-centers-v7','contour-fold-lower-chin-visible-region-v8','contour-fold-lower-chin-observed-runs-v9'].includes(calibrationVersion||'');
}

export function meshTriangles(mesh:SkinMesh,bagSupport=false,surfaceSupport=false):number[][] {
 const edges=new Set(mesh.edges.flatMap(([a,b])=>[`${a}:${b}`,`${b}:${a}`])),triangles:number[][]=[];
 for(let a=0;a<mesh.points.length;a++)for(let b=a+1;b<mesh.points.length;b++)if(edges.has(`${a}:${b}`))for(let c=b+1;c<mesh.points.length;c++)if(edges.has(`${a}:${c}`)&&edges.has(`${b}:${c}`))triangles.push([a,b,c]);
 return bagSupport ? [...triangles,...bagCellTriangles(mesh)] : surfaceSupport ? [...triangles,...closedSurfaceCellTriangles(mesh)] : triangles;
}
export function inTriangle(x:number,y:number,mesh:SkinMesh,tri:number[]) {
 const [a,b,c]=tri.map(i=>mesh.points[i]);const d=(v:typeof a,w:typeof a)=>(x-w.x)*(v.y-w.y)-(v.x-w.x)*(y-w.y);const u=d(a,b),v=d(b,c),w=d(c,a);
 return (u>=0&&v>=0&&w>=0)||(u<=0&&v<=0&&w<=0);
}
const clamp=(v:number)=>Math.max(0,Math.min(1,v));
/** Conservative appearance mask, not a clinical skin/tissue classifier. */
export function analyzeSurface(input:SurfaceInput,evaluateShine=false):SurfaceGrid {
 const {width,height,pixels,mesh,exclusions}=input;
 if(width<=0||height<=0||pixels.length!==width*height*4||!mesh.points.length)throw Error('INVALID_SURFACE_SOURCE');
 const x=Math.max(0,Math.floor(Math.min(...mesh.points.map(p=>p.x)))),y=Math.max(0,Math.floor(Math.min(...mesh.points.map(p=>p.y))));
 const right=Math.min(width,Math.ceil(Math.max(...mesh.points.map(p=>p.x)))),bottom=Math.min(height,Math.ceil(Math.max(...mesh.points.map(p=>p.y))));
 const step=Math.max(1,Math.ceil(Math.max(right-x,bottom-y)/SHINE_PARAMETERS.maxSamples));
 const gw=Math.max(1,Math.ceil((right-x)/step)),gh=Math.max(1,Math.ceil((bottom-y)/step)),n=gw*gh;
 const valid=new Uint8Array(n),redness=new Float32Array(n),shine=new Float32Array(n),values=new Float32Array(n),saturations=new Float32Array(n);
 const triangles=meshTriangles(mesh);let geometric=0,clipped=0,count=0;
 for(let gy=0;gy<gh;gy++)for(let gx=0;gx<gw;gx++){
  const sx=Math.min(width-1,x+gx*step+Math.floor(step/2)),sy=Math.min(height-1,y+gy*step+Math.floor(step/2)),k=gy*gw+gx;
  if(!triangles.some(t=>inTriangle(sx,sy,mesh,t))||exclusions.some(e=>sx>=e.x&&sx<e.x+e.w&&sy>=e.y&&sy<e.y+e.h))continue;
  geometric++;const i=(sy*width+sx)*4,r=pixels[i],g=pixels[i+1],b=pixels[i+2],v=Math.max(r,g,b)/255,s=v?(Math.max(r,g,b)-Math.min(r,g,b))/(v*255):0,l=.299*r+.587*g+.114*b;
  if(Math.max(r,g,b)>=250)clipped++;
  // Dark hair/beard, saturated makeup and bleached highlights are excluded
  // conservatively; remaining beard/makeup confounding requires real validation.
  if(!input.qualityValid||pixels[i+3]!==255||l<40||l>240||r<g*.95||r<b*.9||s>.72)continue;
  valid[k]=255;count++;values[k]=v;saturations[k]=s;redness[k]=Math.max(0,Math.min(100,(2*r-g-b)/255*100));
 }
 let shineSamples=0;const clippedFraction=clipped/Math.max(1,geometric);
 const unavailable=!evaluateShine?'not-requested':input.region==='periorbital'?'region-out-of-scope':!input.qualityValid?'invalid-source-quality':count<100?'insufficient-visible-skin':clippedFraction>SHINE_PARAMETERS.maxClippedFraction?'overexposed-region':null;
 if(evaluateShine&&!unavailable){
  for(let gy=0;gy<gh;gy++)for(let gx=0;gx<gw;gx++){
   const k=gy*gw+gx;if(!valid[k])continue;const neighbors:number[]=[];
   // Local background statistic, not per-photo min/max normalization.
   for(let yy=Math.max(0,gy-5);yy<=Math.min(gh-1,gy+5);yy++)for(let xx=Math.max(0,gx-5);xx<=Math.min(gw-1,gx+5);xx++){const j=yy*gw+xx;if(valid[j])neighbors.push(values[j]);}
   if(neighbors.length<16)continue;neighbors.sort((a,b)=>a-b);const baseline=neighbors[Math.floor(neighbors.length/2)],p=SHINE_PARAMETERS;
   const intensity=clamp((values[k]-p.minValue)/.35)*clamp((p.maxSaturation-saturations[k])/p.maxSaturation)*clamp((values[k]-baseline-p.minLocalContrast)/p.contrastSpan);
   shine[k]=intensity;if(intensity>=p.candidateThreshold)shineSamples++;
  }
 }
 return {x,y,step,width:gw,height:gh,valid,redness,shine,validSamples:count,shineSamples,clippedFraction,shineAreaPercent:unavailable?null:100*shineSamples/Math.max(1,count),shineUnavailable:unavailable,allocatedBytes:valid.byteLength+redness.byteLength+shine.byteLength+values.byteLength+saturations.byteLength};
}
/** Fixed mapping; zero/invalid is transparent, not "healthy". */
export function surfaceColor(value:number,valid:boolean,maximum=100):[number,number,number,number] {
 if(!valid||!Number.isFinite(value)||value<=0)return [0,0,0,0];const t=clamp(value/maximum);
 return [Math.round(54-40*t),Math.round(228-100*t),Math.round(241-95*t),Math.round(255*.32*t)];
}

export const RELATIVE_SHINE_METHOD='relative-chromatic-reflection-candidate-v2';
/** Research-only local brightening + desaturation. No absolute V threshold,
 * photo min/max, generated skin details, sebum claim or product admission.
 * Shares the exact source-coordinate mask/denominator with the V1 control.
 */
export function analyzeRelativeShine(input:SurfaceInput):SurfaceGrid {
 const grid=analyzeSurface(input,false),values=new Float64Array(grid.valid.length),saturation=new Float64Array(grid.valid.length);
 for(let gy=0;gy<grid.height;gy++)for(let gx=0;gx<grid.width;gx++){
  const k=gy*grid.width+gx;if(!grid.valid[k])continue;
  const sx=Math.min(input.width-1,grid.x+gx*grid.step+Math.floor(grid.step/2)),sy=Math.min(input.height-1,grid.y+gy*grid.step+Math.floor(grid.step/2)),i=(sy*input.width+sx)*4;
  const r=input.pixels[i],g=input.pixels[i+1],b=input.pixels[i+2],v=Math.max(r,g,b);values[k]=v/255;saturation[k]=v?(v-Math.min(r,g,b))/v:0;
 }
 const unavailable=input.region==='periorbital'?'region-out-of-scope':!input.qualityValid?'invalid-source-quality':grid.validSamples<100?'insufficient-visible-skin':grid.clippedFraction>SHINE_PARAMETERS.maxClippedFraction?'overexposed-region':null;
 let numerator=0;
 if(!unavailable)for(let gy=0;gy<grid.height;gy++)for(let gx=0;gx<grid.width;gx++){
  const k=gy*grid.width+gx;if(!grid.valid[k])continue;const v:number[]=[],s:number[]=[];
  for(let yy=Math.max(0,gy-5);yy<=Math.min(grid.height-1,gy+5);yy++)for(let xx=Math.max(0,gx-5);xx<=Math.min(grid.width-1,gx+5);xx++){
   const j=yy*grid.width+xx;if(grid.valid[j]){v.push(values[j]);s.push(saturation[j]);}
  }
  if(v.length<16)continue;v.sort((a,b)=>a-b);s.sort((a,b)=>a-b);
  const background=v[Math.floor(v.length/2)],backgroundS=s[Math.floor(s.length/2)];
  const brightening=values[k]/Math.max(background,1e-6)-1,desaturation=backgroundS-saturation[k];
  const response=clamp((brightening-.08)/.24)*clamp(desaturation/.25);
  grid.shine[k]=response;if(response>=SHINE_PARAMETERS.candidateThreshold)numerator++;
 }
 return {...grid,shineSamples:numerator,shineUnavailable:unavailable,shineAreaPercent:unavailable?null:100*numerator/Math.max(1,grid.validSamples),allocatedBytes:grid.allocatedBytes+values.byteLength+saturation.byteLength};
}
