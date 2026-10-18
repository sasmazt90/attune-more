import type { Eye } from './spokenVision';
import type { VisionEvidence } from './visionTracking';
export class VisionInference {
 private worker=new Worker(new URL('./visionInference.worker.ts',import.meta.url));private sequence=0;private closed=false;private firstFrame=true;
 private pending=new Map<number,{resolve:(value:any)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
 constructor(){this.worker.onmessage=event=>{const p=this.pending.get(event.data.id);if(!p)return;this.pending.delete(event.data.id);clearTimeout(p.timer);event.data.error?p.reject(Error(event.data.error)):p.resolve(event.data);};this.worker.onerror=event=>this.close(event.message||'Görme worker başlatılamadı');}
 private request(type:string,frame?:ImageBitmap,frameTime?:number,eye?:Eye|null):Promise<any>{if(this.closed){frame?.close();return Promise.reject(Error('Görme motoru kapatıldı'));}return new Promise((resolve,reject)=>{const id=++this.sequence,timer=setTimeout(()=>{this.pending.delete(id);reject(Error('Görme motoru zamanında yanıt vermedi'));},type==='initialize'?45000:this.firstFrame?30000:10000);this.pending.set(id,{resolve,reject,timer});this.worker.postMessage({id,type,frame,frameTime,eye},frame?[frame]:[]);});}
 async initialize(){await this.request('initialize');}
 async assess(canvas:HTMLCanvasElement,frameTime:number,eye:Eye|null):Promise<VisionEvidence>{const result=await this.request('frame',await createImageBitmap(canvas),frameTime,eye);this.firstFrame=false;return result.evidence;}
 close(reason='Görme motoru kapatıldı'){if(this.closed)return;this.closed=true;this.worker.terminate();for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error(reason));}this.pending.clear();}
}
