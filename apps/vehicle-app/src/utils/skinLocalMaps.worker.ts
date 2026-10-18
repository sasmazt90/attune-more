import { analyzeSurface,surfaceColor } from './skinSurfaceAnalysis';
import type { SkinMesh } from './skinMesh';
async function png(width:number,height:number,pixels:Uint8ClampedArray){
 const c=new OffscreenCanvas(width,height),ctx=c.getContext('2d')!;ctx.putImageData(new ImageData(pixels as Uint8ClampedArray<ArrayBuffer>,width,height),0,0);
 const blob=await c.convertToBlob({type:'image/png'}),bytes=new Uint8Array(await blob.arrayBuffer());let binary='';for(const b of bytes)binary+=String.fromCharCode(b);return 'data:image/png;base64,'+btoa(binary);
}
self.postMessage({ready:true});
self.onmessage=async({data})=>{
 const start=performance.now();
 try {
  const photoId=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data.pixels.buffer))).map(v=>v.toString(16).padStart(2,'0')).join('');
  const maps:Record<string,unknown>={};let allocatedBytes=data.pixels.byteLength;
  for(const [region,mesh] of Object.entries(data.meshes as Record<string,SkinMesh>)){
   if(region==='periorbital')continue;
   const grid=analyzeSurface({...data,region,mesh},false);allocatedBytes+=grid.allocatedBytes;
   if(grid.validSamples<100||grid.width<16||grid.height<16)continue;
   const rgba=new Uint8ClampedArray(grid.width*grid.height*4),mask=new Uint8ClampedArray(rgba.length);
   for(let i=0;i<grid.valid.length;i++){rgba.set(surfaceColor(grid.redness[i],!!grid.valid[i]),i*4);mask.set([255,255,255,grid.valid[i]],i*4);}
   allocatedBytes+=rgba.byteLength+mask.byteLength;
   maps[region]={criterion:'redness',region,pose:data.pose,photoId,sourceWidth:data.width,sourceHeight:data.height,x:grid.x,y:grid.y,step:grid.step,width:grid.width,height:grid.height,unit:'color-index-0-100',method:'rgb-redness-pixel-v1',validation:'analytic-pixel-index',colorMapping:'cyan-fixed-100-v1',dataUrl:await png(grid.width,grid.height,rgba),validMaskUrl:await png(grid.width,grid.height,mask),sampleCount:grid.validSamples,values:grid.redness,validMask:grid.valid};
  }
  self.postMessage({id:data.id,photoId,maps,analysisMs:performance.now()-start,allocatedBytes});
 } catch(error){self.postMessage({id:data.id,error:error instanceof Error?error.message:'LOCAL_MAP_FAILED'});}
};
