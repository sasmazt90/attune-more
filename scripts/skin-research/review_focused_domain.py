"""Frozen candidate outputs on rights-recorded independent public portraits.

This is a private research process. It exercises the exact production ORT crop,
tile/NMS and ROI functions, with an in-memory candidate session registry. No
normal installed registry, user photo, history, camera or microphone is used.
Visual review is recorded separately; model output never labels itself.
"""
import argparse,base64,io,json,sys,time
from pathlib import Path
import cv2,numpy as np,onnxruntime as ort,psutil
from PIL import Image,ImageDraw
from prepare_focused_data import ROOT,OUT,sha,write
sys.path.insert(0,str(ROOT/'services/core-api'))
import skin_models
from appearance_analysis import analyze_skin

def main(task):
    folder=OUT/('yolox' if task=='acne' else 'bags')
    frozen=json.loads((folder/'frozen-selection.json').read_text())
    exported=json.loads((folder/'export.json').read_text())
    model=folder/'candidate.onnx';assert sha(model)==exported['sha256']
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    before=psutil.Process().memory_info().rss;started=time.perf_counter()
    session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider']);cold=(time.perf_counter()-started)*1000
    meta=dict(sha256=exported['sha256'],version='frozen-'+task,confidenceThreshold=frozen['threshold'],probabilityThreshold=frozen['threshold'])
    skin_models.load=lambda:{'sessions':{task:{'session':session,'metadata':meta,'loadMs':cold}}}
    sources=ROOT/'audit-results/all-health-20261010/natural-skin'
    measurements=json.loads((sources/'measurements-private.json').read_text())
    # Two independent NASA portraits plus two declared same-person video
    # frames. Video frames are never counted as different people or HD poses.
    chosen=[r for r in measurements if r['index'] in [0,1,3,5] and 'photoId' in r]
    runs=[];dest=OUT/'domain-review'/task;dest.mkdir(parents=True,exist_ok=True)
    for row in chosen:
        payload=json.loads((sources/f"{row['index']}-payload-private.json").read_text())
        image=Image.open(io.BytesIO(base64.b64decode(payload['photo'].split(',')[1]))).convert('RGB');bgr=np.array(image)[:,:,::-1].copy()
        started=time.perf_counter();result=(skin_models.infer_acne if task=='acne' else skin_models.infer_bags)(bgr,payload['landmarks'],payload['qualityValid']);elapsed=(time.perf_counter()-started)*1000
        public={k:v for k,v in (result or {}).items() if k!='layers'};canvas=image.copy();draw=ImageDraw.Draw(canvas)
        production=analyze_skin(payload)
        production_rows={k:[v for v in values if v['id']==('acne' if task=='acne' else 'bags')] for k,values in production['measurements'].items()}
        if task=='acne':
            product_canvas=image.copy();product_draw=ImageDraw.Draw(product_canvas);accepted={b['candidateId']:b for values in production_rows.values() for value in values for b in value['components'].get('bounds',[])}
            for box in accepted.values():product_draw.rectangle([box['x'],box['y'],box['x']+box['width'],box['y']+box['height']],outline=(0,210,245),width=3)
            product_canvas.save(dest/f"{row['index']}-product-owned-candidates.png")
        if task=='acne':
            for box in public.get('boxes',[]):draw.rectangle(box[:4],outline=(255,105,150),width=3)
        else:
            public['layers']=[]
            for layer in (result or {}).get('layers',[]):
                a,b,c,d=layer['rect'];mask=cv2.resize(layer['mask'],(c-a,d-b),interpolation=cv2.INTER_NEAREST)>0
                arr=np.array(canvas);pixels=arr[b:d,a:c];pixels[mask]=(pixels[mask]*.6+np.array([0,210,245])*.4).astype(np.uint8);arr[b:d,a:c]=pixels;canvas=Image.fromarray(arr)
                public['layers'].append({k:v for k,v in layer.items() if k!='mask'}|{'maskFraction':float(mask.mean()),'nativePixels':int(mask.sum())})
                Image.fromarray(layer['mask']*255).save(dest/f"{row['index']}-{layer['eye']}-mask.png")
        # Full native output and crop preserve inspectable pores/eye boundaries.
        canvas.save(dest/f"{row['index']}-source-overlay.png")
        _,crop=skin_models.photo_input(bgr,payload['landmarks']);x,y=crop['x'],crop['y'];canvas.crop((x,y,x+crop['width'],y+crop['height'])).save(dest/f"{row['index']}-face-overlay.png")
        runs.append(dict(source=row['source'],sourceSHA256=row['sourceSHA256'],captureId=row['photoId'],index=row['index'],natural=True,physicalUserAcceptance=False,independentPersonGroup=0 if row['index']==0 else 1 if row['index']==1 else 2,candidate=public,productionSourceFunction=production_rows,productionSourceIsNotNormalInstalledAPI=True,inferenceMs=elapsed,sourceTransform=crop))
    write(f'domain-review/{task}/outputs.json',dict(modelHash=exported['sha256'],frozenThreshold=frozen['threshold'],coldLoadMs=cold,rssBefore=before,rssAfter=psutil.Process().memory_info().rss,modelBytes=model.stat().st_size,runs=runs,groundTruthFromOutputs=False,clinicalLabels=False,accepted=False,reason='Independent visual ratings and sufficient positive/negative confounders required'))
    print(json.dumps(dict(task=task,modelHash=exported['sha256'],images=len(runs),sourcePersonGroups=len({r['independentPersonGroup'] for r in runs}),output=str(dest),accepted=False)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('task',choices=['acne','bags']);main(p.parse_args().task)
