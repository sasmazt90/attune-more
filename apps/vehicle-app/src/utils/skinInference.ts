import type { FaceAlignment } from './skinAnalyzer';
import type { HeadSegmentation } from './skinSnapshot';

export class SkinInference {
  private worker = new Worker(new URL('./skinInference.worker.ts', import.meta.url));
  private sequence = 0;
  private closed = false;
  private segmentationReady?: Promise<void>;
  onPhase?: (phase:string)=>void;
  private pending = new Map<number, { resolve: (value: any) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout>; isCurrent:()=>boolean }>();

  constructor() {
    this.worker.onmessage = event => {
      if(event.data.phase){
        const request=this.pending.get(event.data.id);
        if(!request)return;
        // Refinement runs after actual model inference. Give this distinct
        // CPU stage and native bitmap transfer their own bounded budget.
        // A 15s client deadline dropped completed output under UI/IPC load.
        if(event.data.phase==='REFINEMENT'){
          clearTimeout(request.timer);
          request.timer=setTimeout(()=>{this.pending.delete(event.data.id);request.reject(new Error('Portre sınırları hazırlanamadı'));},30000);
        }
        if(request.isCurrent())this.onPhase?.(event.data.phase);return;
      }
      const request = this.pending.get(event.data.id);
      if (!request) return;
      clearTimeout(request.timer);
      this.pending.delete(event.data.id);
      if (event.data.error) request.reject(new Error(event.data.error));
      else request.resolve(event.data);
    };
    this.worker.onerror = () => this.close();
  }

  private request(type: string, frame?: ImageBitmap, alignment?: FaceAlignment, isCurrent:()=>boolean=()=>true): Promise<any> {
    if (this.closed) {
      frame?.close();
      return Promise.reject(new Error('Cilt analiz motoru kapatıldı'));
    }
    return new Promise((resolve, reject) => {
      const id = ++this.sequence;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('Cilt analiz motoru yanıt vermiyor'));
      }, (type === 'initialize' || type === 'segment' || type === 'initializeSegmentation') ? 30000 : 15000);
      this.pending.set(id, { resolve, reject, timer, isCurrent });
      this.worker.postMessage({ id, type, frame, alignment }, frame ? [frame] : []);
    });
  }

  async initialize(): Promise<void> {
    // Prepare the on-device face model while the user reads instructions.
    await this.request('initialize');
    // Background removal is disabled. Do not load its presentation-only model.
  }

  private prepareSegmentation():Promise<void>{
    if(!this.segmentationReady)this.segmentationReady=this.request('initializeSegmentation').then(()=>{}).catch(error=>{this.segmentationReady=undefined;throw error;});
    return this.segmentationReady;
  }

  async assessAlignment(canvas: HTMLCanvasElement): Promise<FaceAlignment> {
    const frame = await createImageBitmap(canvas);
    return (await this.request('frame', frame)).alignment;
  }

  async segmentHead(canvas: HTMLCanvasElement, alignment?:FaceAlignment, isCurrent:()=>boolean=()=>true): Promise<HeadSegmentation> {
    // Freeze the accepted pixels before loading the presentation model. Model
    // loading and inference each have a bounded deadline; cold loading must
    // not consume the native-resolution inference budget.
    const frame = await createImageBitmap(canvas);
    this.onPhase?.('MODEL');
    try { await this.prepareSegmentation(); }
    catch (error) { frame.close(); throw error; }
    if(!isCurrent()){frame.close();throw new Error('Cilt taraması iptal edildi');}
    this.onPhase?.('INFERENCE');
    return (await this.request('segment', frame, alignment, isCurrent)).segmentation;
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.worker.terminate();
    for (const request of this.pending.values()) {
      clearTimeout(request.timer);
      request.reject(new Error('Cilt analiz motoru kapatıldı'));
    }
    this.pending.clear();
  }
}
