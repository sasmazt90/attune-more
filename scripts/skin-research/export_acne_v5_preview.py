"""Frozen Step0 export with same-forward PAFPN maps; research/export only."""
import sys,json,hashlib,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT.parent;OUT=BASE/'cdc-progress/acne-v5-integration-20261017';MODEL=ROOT/'services/core-api/models/acne-v5-preview'
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from heavy_job_lease import HeavyJobLease

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(n,d):
 p=OUT/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2),encoding='utf8');os.replace(t,p)
def main():
 protocol=json.loads((OUT/'protocol.json').read_text('utf8'));weights=BASE/'attune-live-test/audit-results/acne-takeover-20261015/models/step0.safetensors';assert sha(weights)==protocol['step0SHA256'];assert not (OUT/'export-stable-silu-receipt.json').exists(),'EXPORT_ALREADY_VERIFIED'
 with HeavyJobLease('CDC-acne-v5-feature-ONNX-export',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
  import torch,numpy as np,cv2,onnx,onnxruntime as ort
  from safetensors.torch import load_file
  sys.path.insert(0,str(ROOT/'.runtime/export-frozen-source'));from yolox_p2 import build_yolox_p2_model
  torch.set_num_threads(2);net=build_yolox_p2_model();net.load_state_dict(load_file(str(weights)),strict=True);net.eval()
  for p in net.parameters():p.requires_grad_(False)
  class WithMaps(torch.nn.Module):
   def __init__(self,base):super().__init__();self.backbone=base.backbone;self.head=base.head
   def forward(self,x):
    features=self.backbone(x);return (self.head(features),*features)
  wrapper=WithMaps(net).eval();photo=protocol['selectedSmokeSources'][0];image=cv2.imread(photo['file']);assert sha(photo['file'])==photo['photoSHA256']
  # Two fixed native real-source tiles; no label/model-output selection.
  h,w=image.shape[:2];tiles=[]
  for x,y in [(max(0,w//2-192),max(0,h//2-192)),(max(0,w//2-192),max(0,h//2))]:
   canvas=np.full((384,384,3),114,np.uint8);patch=image[y:min(h,y+384),x:min(w,x+384)];canvas[:patch.shape[0],:patch.shape[1]]=patch;tiles.append(canvas.transpose(2,0,1)[None].astype(np.float32))
  path=MODEL/'step0-with-features-stable-silu.onnx';started=time.perf_counter();names=['decoded_boxes','p2','p3','p4','p5']
  if not path.exists():torch.onnx.export(wrapper,torch.from_numpy(tiles[0]),str(path),input_names=['native_bgr_tile'],output_names=names,opset_version=17,dynamo=False,do_constant_folding=False)
  # The stable graph is built by stabilize_acne_v5_onnx.py, preserving weights.
  from stabilize_acne_v5_onnx import stabilize
  stabilize(path)
  lease.check();onnx.checker.check_model(str(path));opts=ort.SessionOptions();opts.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL;opts.intra_op_num_threads=2;opts.inter_op_num_threads=1;session=ort.InferenceSession(str(path),opts,providers=['CPUExecutionProvider']);checks=[]
  for i,x in enumerate(tiles):
   lease.check()
   with torch.inference_mode():a=[v.numpy() for v in wrapper(torch.from_numpy(x))];direct=net(torch.from_numpy(x)).numpy()
   assert np.array_equal(a[0],direct),'WRAPPER_CHANGED_DIRECT_STEP0'
   b=session.run(None,{'native_bgr_tile':x});rows=[]
   for n,aa,bb in zip(names,a,b):
    if n=='decoded_boxes':
     coordinateOk=bool(np.allclose(aa[:,:,:4],bb[:,:,:4],atol=protocol['tolerances']['sourceBoxesATol'],rtol=0));scoreOk=bool(np.allclose(aa[:,:,4:],bb[:,:,4:],atol=protocol['tolerances']['scoreATol'],rtol=0));ok=bool(np.isfinite(bb).all() and coordinateOk and scoreOk);detail=dict(coordinatesPassed=coordinateOk,scoresPassed=scoreOk,maxCoordinateAbs=float(np.max(np.abs(aa[:,:,:4]-bb[:,:,:4]))),maxScoreAbs=float(np.max(np.abs(aa[:,:,4:]-bb[:,:,4:]))),unitTolerances='sourceBoxesATol for source-pixel coordinates, scoreATol for probabilities; both pre-frozen')
    else:
     ok=bool(np.isfinite(bb).all() and np.allclose(aa,bb,atol=protocol['tolerances']['tensorsATol'],rtol=protocol['tolerances']['tensorsRTol']));detail={}
    rows.append(dict(name=n,shape=list(bb.shape),maxAbs=float(np.max(np.abs(aa-bb))),passed=ok,**detail));print('PARITY',i,rows[-1],flush=True)
   write('export-diagnostic-current.json',dict(checks=checks+[dict(tile=i,outputs=rows)],tolerancesUnchanged=protocol['tolerances']))
   assert all(v['passed'] for v in rows),('EXPORT_PARITY',i,rows)
   checks.append(dict(tile=i,outputs=rows,directStep0Exact=True))
  assert sha(weights)==protocol['step0SHA256']
  manifest=dict(version='experimental-step0-verifier-v5-local-preview-v1',accepted=False,coordinateSpace='source-pixels',detector=dict(file=path.name,sha256=sha(path),sourceStep0SHA256=protocol['step0SHA256'],input='native_bgr_tile',outputs=names,strides=[4,8,16,32],channels=[64,128,256,512],confidenceThreshold=.30,nms=.30),verifier=dict(file='verifier-v5.json',sha256=protocol['verifierSHA256'],threshold=protocol['threshold'],features=1920,featureVersion='acne-candidate-verifier-features-v1'),runtime='numpy and onnxruntime only',ortOptimization='disabled-preserve-unfused-BN')
  (MODEL/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');write('export-stable-silu-receipt.json',dict(modelPath=str(path),modelSHA256=sha(path),sourceStep0SHA256=sha(weights),protocolSHA256=sha(OUT/'protocol.json'),checks=checks,elapsedSec=time.perf_counter()-started,resource=lease.receipt(),trainingPerformed=False));print('EXPORT_OK',sha(path))
if __name__=='__main__':main()
