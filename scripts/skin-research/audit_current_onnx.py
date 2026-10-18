"""Real development PyTorch/ONNX raw, score, native decode and adapter parity.
Never installs a candidate or accesses a final test/user record.
"""
import json,sys,time
from pathlib import Path
import cv2,numpy as np,torch,onnxruntime as ort
from safetensors.torch import load_file
from expanded_sources import ROOT,OUT,sha
from train_focused_local import yolo_model,tile_image,acne_tiles
from yolox_numeric import install_bounds
from selected_mask_model import SkinUNet
from selected_sources import TARGETS
D=OUT/'interim-diagnosis';E=D/'export-v2';E.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
import skin_models as M
from skin_native_mask import CONTRACT,tensor,infer_native_mask
def read(p):return json.loads(p.read_text('utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,indent=2),'utf8')

class RawYOLO(torch.nn.Module):
 def __init__(self,net):
  super().__init__();self.net=net;self.raw={}
  for name,convs in [('reg',net.head.reg_preds),('obj',net.head.obj_preds),('cls',net.head.cls_preds)]:
   for i,conv in enumerate(convs):conv.register_forward_hook(lambda m,x,y,name=name,i=i:self.capture(name,i,y))
  install_bounds(net)
 def capture(self,name,i,y):self.raw[(name,i)]=y.flatten(2).permute(0,2,1)
 def forward(self,x):
  decoded=self.net(x)
  return (decoded,*[torch.cat([self.raw[(name,i)] for i in range(3)],1) for name in ['reg','obj','cls']])

class PTSession:
 def __init__(self,net):self.net=net
 def run(self,names,inputs):
  with torch.inference_mode():v=self.net(torch.from_numpy(next(iter(inputs.values()))))
  return [a.numpy() for a in v] if isinstance(v,tuple) else [v.numpy()]

def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);start=read(D/'start.json');checks=[]
 options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
 for kind in ['negative-yolox','negative-mask-continuation']:
  snap=start['phaseSnapshots'][kind];weights=Path(snap['snapshot']);assert sha(weights)==snap['modelSHA256']
  net=yolo_model() if kind=='negative-yolox' else SkinUNet();net.load_state_dict(load_file(str(weights)));net.eval()
  model=RawYOLO(net) if kind=='negative-yolox' else net;model.eval();name='native_bgr_tile' if kind=='negative-yolox' else 'native_rgb_tile';path=E/(kind+'.onnx')
  if kind=='negative-yolox':
   data=read(OUT/'negative-expanded-detector-data.json');selected=read(D/'detector-source-selection.json')['rows'];rs=[next(r for r in data['rows'] if r['sha256']==s['sha256']) for s in selected];tiles=[acne_tiles([r],False)[0] for r in rs];inputs=[tile_image(t)[None].numpy() for t in tiles]
   names=['decoded_boxes','raw_regression','raw_objectness','raw_class']
  else:
   data=read(OUT/'negative-expanded-mask-data.json');rs=[];inputs=[]
   for target in TARGETS:
    for positive in [True,False]:
     row=next((r for r in data['rows'] if r['split']=='validation' and r['target']==target and bool(r['positivePixels'])==positive),None)
     if row:
      with np.load(OUT/data['tensorFolder']/row['id']) as f:rgb=f['rgb'].copy()
      inputs.append(((rgb.transpose(2,0,1).astype(np.float32)/255-M.MEAN)/M.STD)[None].copy());rs.append(row)
   names=['shared_mask_logits']
  if not path.exists():torch.onnx.export(model,torch.from_numpy(inputs[0]),str(path),input_names=[name],output_names=names,opset_version=17,dynamo=False)
  session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider']);pt=PTSession(model);details=[];numerical_pass=True
  for r,x in zip(rs,inputs):
   expected=pt.run(None,{name:x});actual=session.run(None,{name:x});diff=[]
   for output_name,a,b in zip(names,expected,actual):
    passed=np.isfinite(b).all() and np.allclose(a,b,atol=.003,rtol=1e-4)
    if kind=='negative-yolox' and output_name=='decoded_boxes':
     # Decode near zero subtracts large grid-offset logits: relative error in
     # the final coordinate is not relative error in the underlying logit.
     # Prove the propagated raw-logit bound, and separately check real boxes.
     strides=np.concatenate([np.full((384//s)**2,s,np.float32) for s in [8,16,32]])[None,:,None]
     error_bound=strides*abs(expected[1][:,:,:2]-actual[1][:,:,:2])+2*abs(np.spacing(a[:,:,:2]))+.003
     passed=np.isfinite(b).all() and bool(np.all(abs(a[:,:,:2]-b[:,:,:2])<=error_bound)) and np.allclose(a[:,:,2:],b[:,:,2:],atol=.003,rtol=1e-4)
    if not passed:
     index=np.unravel_index(np.argmax(abs(a-b)),a.shape)
     failure=dict(kind=kind,sha256=r['sha256'],output=output_name,maximumDifference=float(abs(a-b).max()),index=[int(i) for i in index],expected=float(a[index]),actual=float(b[index]),finite=bool(np.isfinite(b).all()),failedElements=int((abs(a-b)>(.003+1e-4*abs(b))).sum()))
     failures_path=E/(kind+'-parity-failures.json');failures=read(failures_path) if failures_path.exists() else [];failures.append(failure);write(failures_path,failures);print(json.dumps(failure),flush=True)
     numerical_pass=False
    assert np.isfinite(b).all(),'NONFINITE_ONNX_OUTPUT'
    diff.append(float(abs(a-b).max()))
   if kind=='negative-yolox':
    obj=1/(1+np.exp(-np.clip(actual[2],-80,80)));cls=1/(1+np.exp(-np.clip(actual[3],-80,80)))
    assert np.allclose(obj*cls,actual[0][:,:,4:5]*actual[0][:,:,5:6],atol=1e-6)
    assert actual[0][:,:,2:4].min()>=.099 and actual[0][:,:,2:4].max()<=768.01
   details.append(dict(sha256=r['sha256'],rect=r.get('rect'),maximumAbsoluteDifferences=diff))
  adapter=[]
  if kind=='negative-yolox':
   product=read(D/'positive-product-chain.json')['rows'];saved=M.load
   try:
    for row in product:
     if 'realDerivedLandmarks' not in row:continue
     r=next(r for r in rs if r['sha256']==row['sha256']);bgr=cv2.imread(r['absolutePath']);values=[]
     for source in [pt,session]:
      M.load=lambda source=source:{'sessions':{'acne':dict(session=source,metadata=dict(sha256=sha(path),version='isolated-export-v2',confidenceThreshold=.7),loadMs=0)}}
      v=M.infer_acne(bgr,row['realDerivedLandmarks'],True);assert v['valid'];values.append(v)
     a,b=[np.array(v['boxes']) for v in values];assert a.shape==b.shape and np.allclose(a,b,atol=.05,rtol=2e-4),'PRODUCT_SOURCE_BOX_PARITY_FAILED'
     adapter.append(dict(sha256=r['sha256'],boxCount=len(a),maximumBoxDifference=float(abs(a-b).max()) if a.size else 0,normalProductDecoder=True))
   finally:M.load=saved
  else:
   # Real native tensor pixels and source rect, including small padded edge tiles.
   for target,r,x in zip([r['target'] for r in rs],rs,inputs):
    with np.load(OUT/data['tensorFolder']/r['id']) as f:rgb=f['rgb'].copy()
    bgr=rgb[:,:,::-1].copy();support=np.ones((256,256),np.uint8);meta=dict(sha256=sha(path),channel=TARGETS.index(target),preprocessing=CONTRACT)
    a=infer_native_mask(bgr,pt,meta,target,[0,0,256,256],support);b=infer_native_mask(bgr,session,meta,target,[0,0,256,256],support)
    disagreements=int((a['mask']!=b['mask']).sum());assert disagreements<=2,'NATIVE_MASK_BINARY_PARITY_FAILED'
    adapter.append(dict(target=target,sha256=r['sha256'],sourceRect=r['rect'],binaryDisagreementPixels=disagreements,nativeTensorPreprocessingParity=np.allclose(tensor(bgr,[0,0,256,256]),x,atol=1e-7),densityUsesVisibleArea=True))
   assert all(r['nativeTensorPreprocessingParity'] for r in adapter)
  record=dict(kind=kind,weightsSHA256=snap['modelSHA256'],modelSHA256=sha(path),outputNames=names,numericalParity=numerical_pass,strictNumericalFailureBlocksPromotion=not numerical_pass,realImagePreprocessingParity=True,sourceCoordinateParity=True if kind=='negative-yolox' else None,checks=details,adapter=adapter,normalAPIInstalled=False,productAccepted=False,acceptanceThresholdsChanged=False,onnxRuntimeGraphOptimization='default normal product CPU',numericTolerance=dict(atol=.003,rtol=.0001),decodedCenterRawErrorPropagationChecked=kind=='negative-yolox')
  write(E/(kind+'-receipt.json'),record);checks.append(record);print('ONNX REAL COMPARISON',kind,len(details),numerical_pass,flush=True)
 write(E/'receipt.json',dict(models=checks,finalOpened=False,normalProductRegistryUnchanged=True));print('ONNX COMPLETE',flush=True)
if __name__=='__main__':main()
