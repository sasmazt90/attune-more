"""Exact selected native texture export, without severity or product staging."""
import argparse,json,sys
from pathlib import Path
import cv2,numpy as np,torch,onnxruntime as ort
from safetensors.torch import load_file
from expanded_sources import ROOT,OUT,PREVIOUS,sha,write
from train_dry_texture import TextureNet

def main(phase='dry-texture'):
 torch.set_num_threads(1);cv2.setNumThreads(1);folder=OUT/phase;data=json.loads((folder/'data.json').read_text('utf8'));selection=json.loads((folder/'selection.json').read_text('utf8'));weights=folder/'selected.safetensors';assert sha(weights)==selection['weightsSHA256'];net=TextureNet();net.load_state_dict(load_file(str(weights)));net.eval();pixels=np.load(folder/'pixels.npy');rows=data['rows'];sources=json.loads((PREVIOUS/'manifest.json').read_text('utf8'))['rows'];by={r['sha256']:r for r in sources};chosen=[]
 for label in [0,1]:
  candidates=[i for i,r in enumerate(rows) if r['split']=='validation' and r['label']==label]
  if phase=='negative-dry-presence' and label==0:
   old=json.loads((OUT/'dry-texture/data.json').read_text('utf8'));oldphotos={r['sha256'] for r in old['rows']}
   candidates=[i for i in candidates if rows[i]['sha256'] not in oldphotos]+[i for i in candidates if rows[i]['sha256'] in oldphotos]
  groups=set()
  for i in candidates:
   if rows[i]['group'] in groups:continue
   groups.add(rows[i]['group']);chosen.append(i)
   if len(groups)==3:break
 x=torch.from_numpy(pixels[chosen[0]][None,None].copy()).float()/255;path=folder/'candidate.onnx';torch.onnx.export(net,x,str(path),input_names=['native_gray_texture'],output_names=['presence_logits'],opset_version=17,dynamo=False);options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1;session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider']);checks=[]
 for i in chosen:
  r=rows[i];source=by[r['sha256']];assert sha(Path(source['absolutePath']))==r['sha256'];gray=cv2.cvtColor(cv2.imread(source['absolutePath']),cv2.COLOR_BGR2GRAY);a,b,c,d=r['nativeRect'];assert min(c-a,d-b)>=64;real=cv2.resize(gray[b:d,a:c],(64,64),interpolation=cv2.INTER_AREA);assert np.array_equal(real,pixels[i]);x=torch.from_numpy(real[None,None].copy()).float()/255
  with torch.no_grad():expected=net(x).numpy()
  actual=session.run(None,{'native_gray_texture':x.numpy()})[0];assert np.allclose(actual,expected,atol=1e-5,rtol=1e-5);checks.append(dict(sha256=r['sha256'],nativeROI=r['nativeRect'],label=r['label'],maximumAbsoluteLogitDifference=float(abs(actual-expected).max()),noUpsampling=True))
 write(phase+'/export-parity.json',dict(sha256=sha(path),weightsSHA256=sha(weights),numericalParity=True,realImagePreprocessingParity=True,sourceCoordinateParity=True,checks=checks,normalAPIStaged=False,presenceOnly=True,confidenceNotSeverity=True,sourceProcessingConfounderUnresolved=True));print('Selected weak texture actual native-source parity passed',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['dry-texture','negative-dry-presence'],default='dry-texture');main(p.parse_args().phase)
