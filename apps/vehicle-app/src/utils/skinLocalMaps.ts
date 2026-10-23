import type { SkinSnapshot } from './skinSnapshot';
export type SkinLocalMap={linePaths?:{x:number;y:number}[][];criterion:string;region:string;pose:string;photoId:string;sourceWidth:number;sourceHeight:number;x:number;y:number;step:number;width:number;height:number;unit:string;method:string;modelHash?:string;calibrationVersion?:string|null;mapType?:'source-pixel-signal'|'predicted-presence-mask';validation:'analytic-pixel-index'|'appearance-proxy';colorMapping:'cyan-fixed-100-v1';dataUrl:string;validMaskUrl:string;sampleCount:number;values:Float32Array;validMask:Uint8Array};
export class SkinLocalAnalysis {
 private worker?:Worker;private sequence=0;private started=0;private loadMs=0;
 private pending=new Map<number,{resolve:(v:any)=>void;reject:(e:Error)=>void;timer:ReturnType<typeof setTimeout>;current:()=>boolean;expected?:string}>();
 private start(){
  if(this.worker)return;
  this.started=performance.now();this.worker=new Worker(new URL('./skinLocalMaps.worker.ts',import.meta.url));
  this.worker.onmessage=({data})=>{if(data.ready){this.loadMs=performance.now()-this.started;return;}const p=this.pending.get(data.id);if(!p)return;clearTimeout(p.timer);this.pending.delete(data.id);if(!p.current()||p.expected&&p.expected!==data.photoId)p.reject(Error('STALE_SOURCE'));else if(data.error)p.reject(Error(data.error));else p.resolve({...data,loadMs:this.loadMs});};
  this.worker.onerror=()=>this.cancel();
 }
 async analyze(snapshot:SkinSnapshot,pixels:Uint8ClampedArray,qualityValid:boolean,current:()=>boolean,expected?:string):Promise<{photoId:string;maps:Record<string,SkinLocalMap>;analysisMs:number;allocatedBytes:number;loadMs:number}> {
  this.start();const id=++this.sequence;
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{this.cancel();},2500);this.pending.set(id,{resolve,reject,timer,current,expected});
   this.worker!.postMessage({id,width:snapshot.width,height:snapshot.height,pose:snapshot.angle,pixels,meshes:snapshot.meshes,exclusions:snapshot.exclusions,qualityValid},[pixels.buffer as ArrayBuffer]);
  });
 }
 cancel(){this.worker?.terminate();this.worker=undefined;for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('CANCELLED_OR_TIMEOUT'));}this.pending.clear();}
}
