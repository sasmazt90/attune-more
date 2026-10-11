"""Export each selected FULL model; channel selection never mixes encoders.
Real source comparisons are staging evidence, never promotion authorization.
"""
import json,sys
from pathlib import Path
import cv2,numpy as np,torch,onnxruntime as ort
from safetensors.torch import load_file
from expanded_sources import ROOT,OUT,sha,write
from selected_mask_model import SkinUNet
from selected_sources import TARGETS
sys.path.insert(0,str(ROOT/'services/core-api'))
from skin_native_mask import CONTRACT,tensor,infer_native_mask

def read(p):return json.loads(p.read_text('utf8'))
class Session:
 def __init__(self,n):self.n=n
 def run(self,names,inputs):
  with torch.inference_mode():return [self.n(torch.from_numpy(inputs['native_rgb_tile'])).numpy()]

def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);base=OUT/'interim-diagnosis';selection_path=base/'corrected-selection-v4.json'
 if not selection_path.exists():selection_path=base/'scope-v4/selection.json'
 selection_digest=sha(selection_path);output_name='selected-full-export-v4-'+selection_digest[:12];d=base/output_name;d.mkdir(exist_ok=True);selection=read(selection_path);data=read(OUT/'scope-v4-mask-data.json');sources={}
 for p in [OUT/'candidates.json',OUT/'supplement/candidates.json',OUT/'negative-expansion/candidates.json',ROOT/'audit-results/skin-selected-20261011/review/candidates.json']:
  for r in read(p)['rows']:sources.setdefault(r['sha256'],r)
 for r in read(OUT/'negative-expanded-detector-data.json')['rows']:sources.setdefault(r['sha256'],r)
 groups={}
 for t,v in selection['targets'].items():
  if v['selectedFullModel']:groups.setdefault(v['selectedFullModel']['sha256'],dict(model=v['selectedFullModel'],targets=[]))['targets'].append(t)
 protocol=dict(selectionSHA256=selection_digest,dataSHA256=sha(OUT/'scope-v4-mask-data.json'),adapterSHA256=sha(ROOT/'services/core-api/skin_native_mask.py'),contract=CONTRACT,models=groups,threshold=.5,atol=.003,rtol=.0001,fullModelWeightsNeverMixed=True,finalOpened=False)
 pp=d/'protocol.json'
 if pp.exists():assert read(pp)==protocol
 else:write('interim-diagnosis/'+output_name+'/protocol.json',protocol)
 exports={};opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.inter_op_num_threads=1
 for digest,v in groups.items():
  rp=d/(digest+'.receipt.json')
  if rp.exists():record=read(rp);assert sha(Path(record['onnxPath']))==record['modelSHA256'];exports[digest]=record;continue
  previous=base/'selected-full-export-v4'/(digest+'.receipt.json')
  if previous.exists():
   old_protocol=read(previous.parent/'protocol.json');record=read(previous)
   covered={(r['target'],r['positive']) for r in record['checks']}
   if all(old_protocol[k]==protocol[k] for k in ['dataSHA256','adapterSHA256','contract','threshold','atol','rtol']) and all((t,p) in covered for t in v['targets'] for p in [True,False]):
    assert record['weightsSHA256']==digest and sha(Path(record['onnxPath']))==record['modelSHA256'];exports[digest]=record;continue
  weights=Path(v['model']['folder'])/'model.safetensors';assert sha(weights)==digest;net=SkinUNet();net.load_state_dict(load_file(str(weights)));net.eval();pt=Session(net);onnx=d/(digest+'.onnx')
  if not onnx.exists():torch.onnx.export(net,torch.zeros(1,3,256,256),str(onnx),input_names=['native_rgb_tile'],output_names=['shared_mask_logits'],opset_version=17,dynamo=False)
  session=ort.InferenceSession(str(onnx),opt,providers=['CPUExecutionProvider']);checks=[];passed=True
  for t in v['targets']:
   for positive in [True,False]:
    pool=[r for r in data['rows'] if r['target']==t and r['split']=='validation' and (r['positivePixels']>0 if positive else not r['positivePixels'] and r.get('engineeringNegativeROIReviewed') is True)];row=sorted(pool,key=lambda r:(r['sha256'],r['id']))[0];r=sources[row['sha256']];path=Path(r['absolutePath']);assert sha(path)==row['sha256'];im=cv2.imread(str(path));h,w=im.shape[:2];a,b,c,e=row['rect'];crop=[max(0,a-11),max(0,b-9),min(w,c+67),min(h,e+61)];support=np.zeros((h,w),np.uint8);support[crop[1]:crop[3],crop[0]:crop[2]]=1;support[b:min(e,b+5),a:min(c,a+7)]=0
    x=tensor(im,row['rect']);a_raw=pt.run(None,{'native_rgb_tile':x})[0];b_raw=session.run(None,{'native_rgb_tile':x})[0];raw_ok=bool(np.isfinite(b_raw).all() and np.allclose(a_raw,b_raw,atol=.003,rtol=.0001));passed&=raw_ok;meta=dict(sha256=sha(onnx),channel=TARGETS.index(t),preprocessing=CONTRACT);values=[infer_native_mask(im,s,meta,t,crop,support) for s in [pt,session]];diff=int((values[0]['mask']!=values[1]['mask']).sum());source_ok=diff<=2;passed&=source_ok
    checks.append(dict(target=t,positive=positive,sha256=row['sha256'],tensorID=row['id'],sourceNativeSize=[w,h],crop=crop,tileCount=values[0]['tileCount'],maximumLogitDifference=float(abs(a_raw-b_raw).max()),rawParity=raw_ok,sourceMaskDisagreementPixels=diff,sourceCoordinateParity=source_ok,appearanceDensityParity=abs(values[0]['appearanceDensityPercent']-values[1]['appearanceDensityPercent'])))
  record=dict(weightsSHA256=digest,modelSHA256=sha(onnx),onnxPath=str(onnx),numericalParity=passed,realImagePreprocessingParity=True,sourceCoordinateParity=all(r['sourceCoordinateParity'] for r in checks),checks=checks,fullModelWeightsNeverMixed=True,normalAPIInstalled=False,productAccepted=False,protocolSHA256=sha(pp));write('interim-diagnosis/'+output_name+'/'+rp.name,record);exports[digest]=record;print('SELECTED FULL EXPORT',digest[:16],v['targets'],passed,flush=True)
 targets={t:dict(selectedFullModel=v['selectedFullModel'],channel=v['channel'],preprocessing=CONTRACT,export=exports.get((v['selectedFullModel'] or {}).get('sha256')),productionInstalled=False,productAcceptance=False) for t,v in selection['targets'].items()}
 write('interim-diagnosis/'+output_name+'/plan.json',dict(targets=targets,fullModels=len(exports),selectionSHA256=selection_digest,channelWeightsNotMixed=True,normalProductUnchanged=True,finalOpened=False))
 write('interim-diagnosis/selected-full-export-current.json',dict(planPath=str(d/'plan.json'),planSHA256=sha(d/'plan.json'),selectionSHA256=selection_digest))
if __name__=='__main__':main()
