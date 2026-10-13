"""Local export parity and uncached native request profiling; no fit or cloud."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
import hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
import material_component_features as M
import native_dry_path as N
import appearance_analysis as A
cv2.setNumThreads(1)
PREV=ROOT/'audit-results/native-material-contour-20261013'
WEIGHTS=ROOT/'audit-results/focused-skin-20261010/pretrained/efficientnet_b0_rwightman-7f5810bc.pth.safetensors'
PATHS=[ROOT/'audit-results/dry-sag-component-followup-20261013/product/9bab7ab2/9bab7ab2-automatic-payload.json',ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json',ROOT/'audit-results/native-dry-scale-20261013/e1646fda-native-payload.json']

def export():
    import torch,onnxruntime as ort
    encoder=M.FrozenMaterialEncoder(WEIGHTS);path=OUT/'material-encoder.onnx'
    if not path.exists():
        torch.onnx.export(encoder.net,torch.zeros(2,3,224,224),str(path),input_names=['crops'],output_names=['features'],dynamic_axes={'crops':{0:'batch'},'features':{0:'batch'}},opset_version=17,dynamo=False)
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider'])
    tests=[]
    for payload_path in PATHS:
        payload=json.loads(payload_path.read_text('utf8'));image,_=A.decode_photo(payload['photo']);h,w=image.shape[:2]
        # Real source crops at both small and broad material scales, no labels.
        crops=[]
        for rect in [[w//3,h//3,8,6],[w//2,h//2,60,40]]:
            views,_=M.component_crops(image,{'rect':rect},1.);crops.extend(views)
        t=time.monotonic();expected=encoder.extract(crops);torch_s=time.monotonic()-t;t=time.monotonic();actual=session.run(['features'],{'crops':np.stack(crops)})[0];ort_s=time.monotonic()-t
        tests.append(dict(source=payload_path.name[:8],maximumAbsoluteDifference=float(np.max(np.abs(expected-actual))),allclose=bool(np.allclose(expected,actual,rtol=2e-4,atol=2e-5)),torchSeconds=torch_s,onnxSeconds=ort_s))
    receipt=dict(sourceEncoderSHA256=M.ENCODER_SHA,onnxSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),featureParity=all(r['allclose'] for r in tests),tests=tests,input='RGB224/ImageNet-standardized, unchanged square source crops',providers=session.get_providers(),sourceWeightsUnchanged=True)
    (OUT/'encoder-parity.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True);assert receipt['featureParity']

def profile():
    balanced='--balanced' in sys.argv
    head=json.loads((PREV/('encoder-material-balanced-head.json' if balanced else 'encoder-material-head.json')).read_text('utf8'));encoder=M.OnnxMaterialEncoder(OUT/'material-encoder.onnx',OUT/'encoder-parity.json');rows=[]
    for path in (PATHS[:2] if balanced else PATHS):
        payload=json.loads(path.read_text('utf8'));assert not payload['hostedProcessingConsent'];details=[];stages={};start=time.monotonic()
        result=N.analyze_native_dry(payload,lambda image,field,metric:M.filter_material_support_streamed(image,field,metric,encoder,head,details=details),profile=stages)
        seconds=time.monotonic()-start;old=json.loads((PREV/(path.name[:8]+'-encoder-native-result.json')).read_text('utf8'))
        same=all(result['measurements'][k]['value']==old['measurements'][k]['value'] for k in result['measurements']) and result['maps']==old['maps']
        suffix='-balanced' if balanced else ''
        (OUT/(path.name[:8]+suffix+'-native-result.json')).write_text(json.dumps(result),'utf8');(OUT/(path.name[:8]+suffix+'-components.json')).write_text(json.dumps(details),'utf8')
        row=dict(source=path.name[:8],seconds=seconds,stages=stages,material=result['nativeMetadata'],scores={k:v['value'] for k,v in result['measurements'].items()},previousScoreAndMapsExact=same,featureCacheRead=False,within45Seconds=seconds<45)
        rows.append(row);print(json.dumps(row),flush=True);(OUT/('balanced-product-profile.json' if balanced else 'profile.json')).write_text(json.dumps(dict(rows=rows,normalProductEnabled=False),indent=2),'utf8')

if __name__=='__main__':
    if '--export' in sys.argv:export()
    else:profile()
