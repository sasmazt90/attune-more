import { SkinAnalyzer } from './skinAnalyzer';
import { FilesetResolver, ImageSegmenter } from '@mediapipe/tasks-vision';
import { headAlpha, compactSkinMask } from './skinSnapshot';
import { refineSkinMatte } from './skinMatte';

let segmenterPromise:Promise<ImageSegmenter>|undefined;
let loadMs=0;
async function getSegmenter() {
  if (!segmenterPromise) {const start=performance.now();segmenterPromise = (async()=>ImageSegmenter.createFromOptions(
    await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm'),
    { baseOptions: { modelAssetPath: '/models/selfie_multiclass_256x256.tflite', delegate: 'CPU' }, runningMode: 'IMAGE', outputCategoryMask: true, outputConfidenceMasks: true }))().then(model=>{loadMs=performance.now()-start;return model;}).catch(error=>{segmenterPromise=undefined;throw error;});}
  return segmenterPromise;
}

// Dedicated worker: the unchanged model and gates run away from cockpit input.
self.onmessage = async (event: MessageEvent) => {
  const { id, type, frame, alignment } = event.data;
  try {
    if (type === 'initialize') {
      const model = await SkinAnalyzer.getFaceLandmarker();
      if (!model) throw new Error('MediaPipe başlatılamadı');
      self.postMessage({ id, ready: true });
      return;
    }
    if (type === 'initializeSegmentation') {
      await getSegmenter();
      self.postMessage({ id, ready: true });
      return;
    }
    const canvas = new OffscreenCanvas(frame.width, frame.height);
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) throw new Error('Analiz tuvali başlatılamadı');
    ctx.drawImage(frame, 0, 0);
    if (type === 'segment') {
      const model = await getSegmenter();
      const start = performance.now();
      // The model has a 256-square semantic tensor. Asking the SDK to resize
      // six confidence maps to a multi-megapixel photo adds no model detail.
      // Keep accepted RGB/metrics at native resolution and guide the matte
      // with that source; only the segmentation input is the actual grid.
      const modelInput=new OffscreenCanvas(256,256),modelCtx=modelInput.getContext('2d');
      if(!modelCtx)throw Error('SEGMENTATION_INPUT_CANVAS');
      modelCtx.drawImage(canvas,0,0,256,256);
      const result = model.segment(modelInput);
      let masksClosed=false;
      try {
        const mask = result.categoryMask;
        if (!mask) throw Error('SEGMENTATION_EMPTY');
        const confidenceMasks = result.confidenceMasks;
        if (!confidenceMasks || confidenceMasks.length !== 6) throw Error('SEGMENTATION_CONFIDENCE_MISSING');
        const hair = confidenceMasks[1].getAsFloat32Array(), face = confidenceMasks[3].getAsFloat32Array();
        const compact=compactSkinMask(mask.width,mask.height,mask.getAsUint8Array(),hair,face,confidenceMasks[2].getAsFloat32Array());
        const {categories,confidence,neckConfidence,faceConfidence}=compact;
        const segmentation={...compact,elapsedMs:performance.now()-start,loadMs,modelMaskWidth:mask.width,modelMaskHeight:mask.height};
        // All retained mask arrays now own small buffers. Release native
        // confidence maps before source-resolution alpha processing.
        result.close();masksClosed=true;
        const refinementStart=performance.now();
        self.postMessage({id,phase:'REFINEMENT'});
        const coarse=headAlpha(segmentation,alignment,canvas.width,canvas.height).alpha;
        const refined=refineSkinMatte(ctx.getImageData(0,0,canvas.width,canvas.height).data,coarse,canvas.width,canvas.height,256);
        // The lower portrait taper is layout, not an uncertain hair edge. Keep
        // only the actual segmented neck; refinement cannot grow the torso.
        for(let y=Math.ceil(alignment.landmarks[152].y*canvas.height);y<canvas.height;y++)for(let x=0;x<canvas.width;x++){const i=y*canvas.width+x;refined.alpha[i]=coarse[i];}
        self.postMessage({ id, segmentation: {...segmentation,alpha:refined.alpha,refinementMs:performance.now()-refinementStart,refinementBytes:refined.workingBytes} }, { transfer: [categories.buffer, confidence!.buffer,neckConfidence!.buffer,faceConfidence!.buffer,refined.alpha.buffer] });
      } finally { if(!masksClosed)result.close(); }
      return;
    }
    // Both canvas types have the pixel/drawing operations used by this analyzer.
    const measuredAlignment = SkinAnalyzer.assessAlignment(ctx as unknown as CanvasRenderingContext2D, canvas.width, canvas.height);
    self.postMessage({ id, alignment:measuredAlignment });
  } catch (error) {
    self.postMessage({ id, error: error instanceof Error ? error.message : String(error) });
  } finally {
    frame?.close();
  }
};
