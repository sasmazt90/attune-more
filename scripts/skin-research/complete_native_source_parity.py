"""Complete source remapping proof without repeating the ONNX export suite."""
import sys,json,time
from pathlib import Path
import cv2,numpy as np,torch,onnxruntime as ort
from safetensors.torch import load_file
from expanded_sources import OUT,ROOT,sha,write
from selected_mask_model import SkinUNet
from selected_sources import TARGETS
sys.path.insert(0,str(ROOT/'services/core-api'))
from skin_native_mask import infer_native_mask,CONTRACT

def read(p):return json.loads(p.read_text('utf8'))
class Session:
 def __init__(self,n):self.n=n
 def run(self,names,inputs):
  with torch.inference_mode():return [self.n(torch.from_numpy(inputs['native_rgb_tile'])).numpy()]

def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);d=OUT/'interim-diagnosis/export-v2';receipt=read(d/'receipt.json');r=next(v for v in receipt['models'] if v['kind']=='negative-mask-continuation');rows=read(OUT/'scope-v4-mask-data.json')['rows'];sources={}
 for path in ['candidates.json','supplement/candidates.json','negative-expansion/candidates.json']:
  for v in read(OUT/path)['rows']:sources.setdefault(v['sha256'],v)
 for v in read(ROOT/'audit-results/skin-selected-20261011/review/candidates.json')['rows']:sources.setdefault(v['sha256'],v)
 weights=Path(read(OUT/'interim-diagnosis/start.json')['phaseSnapshots']['negative-mask-continuation']['snapshot']);assert sha(weights)==r['weightsSHA256'];net=SkinUNet();net.load_state_dict(load_file(str(weights)));net.eval();pt=Session(net)
 opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.inter_op_num_threads=1;onnx=d/'negative-mask-continuation.onnx';assert sha(onnx)==r['modelSHA256'];session=ort.InferenceSession(str(onnx),opt,providers=['CPUExecutionProvider']);checks=[]
 for t in TARGETS:
  row=next(v for v in rows if v['target']==t and v['split']=='validation' and v['positivePixels']);src=sources[row['sha256']];assert src['split']=='validation';path=Path(src['absolutePath']);assert sha(path)==row['sha256'];im=cv2.imread(str(path));h,w=im.shape[:2];assert [w,h]==row['sourceNativeSize'];a,b,c,e=row['rect'];crop=[max(0,a-17),max(0,b-13),min(w,c+81),min(h,e+67)];support=np.zeros((h,w),np.uint8);support[crop[1]:crop[3],crop[0]:crop[2]]=1;support[b:min(e,b+9),a:min(c,a+11)]=0;meta=dict(preprocessing=CONTRACT,channel=TARGETS.index(t),sha256=sha(onnx));v=[infer_native_mask(im,s,meta,t,crop,support) for s in [pt,session]];diff=int((v[0]['mask']!=v[1]['mask']).sum());assert diff<=2,'REAL_SOURCE_MASK_PARITY_FAILED';assert not v[0]['mask'][support==0].any();assert v[0]['predictedPixels']==int(v[0]['mask'].sum())
  checks.append(dict(target=t,sourceSHA256=row['sha256'],sourceSize=[w,h],crop=crop,tileCount=v[0]['tileCount'],sourceBinaryDisagreementPixels=diff,visiblePixels=v[0]['visiblePixels'],densityParity=abs(v[0]['appearanceDensityPercent']-v[1]['appearanceDensityPercent']),knownSupportExclusion=True,RGBNativeNoResize=True));print('REAL SOURCE PARITY',t,flush=True)
 proof=dict(modelSHA256=r['modelSHA256'],weightsSHA256=r['weightsSHA256'],adapterSHA256=sha(ROOT/'services/core-api/skin_native_mask.py'),checks=checks,sourceCoordinateParity=True,normalAPIInstalled=False,finalOpened=False)
 write('interim-diagnosis/export-v2/native-source-parity.json',proof);r['sourceCoordinateParity']=True;r['sourceCoordinateEvidenceSHA256']=sha(d/'native-source-parity.json');write('interim-diagnosis/export-v2/negative-mask-continuation-receipt.json',r);write('interim-diagnosis/export-v2/receipt.json',receipt)
if __name__=='__main__':main()
