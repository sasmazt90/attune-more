"""Frozen development YOLOX export and exact production adapter exercise.

Never installs a candidate, writes user records, or reopens an old final.
Public NASA portraits were already exposed; these are engineering checks.
"""
import base64,io,json,sys,time
import cv2,numpy as np,torch,onnxruntime as ort,psutil
from PIL import Image,ImageDraw
from safetensors.torch import load_file
from train_focused_local import detector,setup,acne_tiles,tile_image,postprocess
from fast_detection_metrics import detection_metrics
from diagnose_followup import NEW,OLD,write
from prepare_focused_data import ROOT,sha

def main():
    torch.set_num_threads(2);cv2.setNumThreads(1)
    folder=NEW/'yolox';result=json.loads((folder/'result.json').read_text());assert result['complete']
    selected=max(result['history'],key=lambda h:h['development']['F1']);threshold=selected['development']['threshold']
    net=detector('yolox');net.load_state_dict(load_file(str(folder/'selected.safetensors')));net.eval()
    tiles=acne_tiles(setup('acne')['train']);x=tile_image(tiles[0])[None];path=folder/'candidate.onnx'
    if not path.exists():torch.onnx.export(net,x,str(path),input_names=['native_bgr_tile'],output_names=['detections'],opset_version=17,dynamo=False)
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    memory=psutil.Process().memory_info().rss;start=time.perf_counter();session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);cold=time.perf_counter()-start
    actual=session.run(None,{'native_bgr_tile':x.numpy()})[0]
    # Compare exported primitive convolution with PyTorch's primitive CPU
    # reference. oneDNN fused convolution is a distinct float32 reduction path.
    with torch.backends.mkldnn.flags(enabled=False),torch.no_grad():expected=net(x).numpy()
    error=float(np.abs(actual-expected).max())
    # Raw decoded exp(width/height) includes rejected boxes thousands of pixels
    # wide. Float32 relative error is the relevant raw-coordinate comparison;
    # verify retained NMS output with the original absolute .01 pixel bound.
    assert np.allclose(actual[:,:,:4],expected[:,:,:4],rtol=1e-5,atol=.001)
    assert np.allclose(actual[:,:,4:],expected[:,:,4:],rtol=0,atol=1e-5)
    a=postprocess(torch.from_numpy(actual.copy()),1,threshold,.45,class_agnostic=True)[0]
    b=postprocess(torch.from_numpy(expected.copy()),1,threshold,.45,class_agnostic=True)[0]
    assert (a is None)==(b is None)
    retained_error=0 if a is None else float(torch.abs(a-b).max());assert retained_error<.01
    timings=[]
    for _ in range(5):
        start=time.perf_counter();session.run(None,{'native_bgr_tile':x.numpy()});timings.append(time.perf_counter()-start)
    write('yolox/export.json',dict(sha256=sha(path),weightsSHA256=sha(folder/'selected.safetensors'),bytes=path.stat().st_size,maxRawAbsParity=error,retainedNMSMaxAbsParity=retained_error,rawCoordinateTolerance={'relative':1e-5,'absolutePixels':.001},rawScoreAbsoluteTolerance=1e-5,retainedOutputAbsoluteTolerance=.01,pytorchReference='primitive CPU convolution; oneDNN fusion disabled only for reference',coldLoadSeconds=cold,warmSeconds=timings,rssBefore=memory,rssAfter=psutil.Process().memory_info().rss,threshold=threshold,productAccepted=False,fullBackboneConverged=False,oldFinalOpened=False))
    # Compare on the same DEVELOPMENT images. Improvement/worsening selection
    # is explicit, cannot be mistaken for a blind final performance estimate.
    dev=setup('acne')['validation'];old=json.loads((OLD/'yolox/validation-predictions.json').read_text());new=json.loads((folder/'validation-predictions.json').read_text());a={r['path']:r for r in old['rows']};b={r['path']:r for r in new['rows']};deltas=[]
    for row in dev:
        before=detection_metrics([row],[a[row['path']]['predictions']],old['metrics']['threshold']);after=detection_metrics([row],[b[row['path']]['predictions']],threshold)
        deltas.append(dict(path=row['path'],sha256=row['sha256'],deltaF1=after['F1']-before['F1'],before=before,after=after))
    ranked=sorted(deltas,key=lambda r:(r['deltaF1'],r['sha256']));chosen=ranked[-3:]+ranked[:3];sheet=Image.new('RGB',(1024,6*440),(12,18,30));draw=ImageDraw.Draw(sheet);by_path={r['path']:r for r in dev}
    for k,d in enumerate(chosen):
        row=by_path[d['path']];source=Image.open(row['absolutePath']).convert('RGB')
        for side,pred,t,color in [(0,a[d['path']]['predictions'],old['metrics']['threshold'],'#ff6996'),(1,b[d['path']]['predictions'],threshold,'#00d2ef')]:
            canvas=source.copy();painter=ImageDraw.Draw(canvas)
            for label in row['annotations']:
                if label['classId']==0:painter.rectangle(label['box'],outline='#ffdc00',width=2)
            for box in pred:
                if box[4]>=t:painter.rectangle(box[:4],outline=color,width=2)
            canvas=canvas.crop(tuple(row['crop']));canvas.thumbnail((500,392));sheet.paste(canvas,(side*512,k*440));draw.text((side*512+5,k*440+396),('OLD' if side==0 else 'NEW')+' dev F1 '+str(round(d['before' if side==0 else 'after']['F1'],3)),fill='white');draw.text((side*512+5,k*440+414),d['sha256'][:16]+' / GT yellow / native model 384',fill='white')
    sheet.save(NEW/'yolox/development-before-after.png');write('yolox/development-before-after.json',dict(allRows=deltas,displayed=chosen,selection='three largest and three smallest development F1 deltas',unannotatedAreasNotKnownHealthy=True,oldFinalOpened=False))
    sys.path.insert(0,str(ROOT/'services/core-api'));import skin_models
    from appearance_analysis import analyze_skin
    skin_models.load=lambda:{'sessions':{'acne':{'session':session,'metadata':dict(sha256=sha(path),version='research-yolox-followup-20261011',confidenceThreshold=threshold),'loadMs':cold*1000}}}
    runs=[];samples=ROOT/'audit-results/all-health-20261010/natural-skin';dest=folder/'product-adapter';dest.mkdir(exist_ok=True)
    for i in [0,1]:
        payload=json.loads((samples/f'{i}-payload-private.json').read_text());image=Image.open(io.BytesIO(base64.b64decode(payload['photo'].split(',')[1]))).convert('RGB');bgr=np.array(image)[:,:,::-1].copy();start=time.perf_counter();candidate=skin_models.infer_acne(bgr,payload['landmarks'],payload['qualityValid']);elapsed=time.perf_counter()-start;analysis=analyze_skin(payload);canvas=image.copy();painter=ImageDraw.Draw(canvas)
        for box in (candidate or {}).get('boxes',[]):painter.rectangle(box[:4],outline='#00d2ef',width=3)
        _,crop=skin_models.photo_input(bgr,payload['landmarks']);canvas.crop((crop['x'],crop['y'],crop['x']+crop['width'],crop['y']+crop['height'])).save(dest/f'{i}-face-overlay.png')
        rows={region:[v for v in values if v['id']=='acne'] for region,values in analysis['measurements'].items()}
        runs.append(dict(index=i,captureId=payload['photoId'],candidate={k:v for k,v in (candidate or {}).items() if k!='layers'},productionAdapterRows=rows,inferenceSeconds=elapsed,normalInstalledAPI=False,independentFinal=False,physicalUserAcceptance=False))
    write('yolox/product-adapter/receipt.json',dict(runs=runs,modelSHA256=sha(path),candidateRegistryPrivateToProcess=True,installedRegistryChanged=False,normalHistoryWritten=False,productAccepted=False))
    print(json.dumps(dict(exportParity=error,modelBytes=path.stat().st_size,selectedDevelopment=selected['development'],adapterRuns=len(runs),accepted=False)),flush=True)

if __name__=='__main__':main()
