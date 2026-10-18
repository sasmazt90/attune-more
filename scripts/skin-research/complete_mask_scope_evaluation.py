"""Reuse proven identical evaluations; infer only changed/new source scopes.
All suitable validation records remain covered. No repeated interim diagnosis.
"""
import collections,json,time
from pathlib import Path
import cv2,numpy as np,torch
from safetensors.torch import load_file
from expanded_sources import OUT,sha,write
from selected_sources import TARGETS
from prepare_continuation_masks import TARGETS as DATA_TARGETS
from selected_mask_model import SkinUNet
from mask_scope_metrics import SourceScopes,RULE,global_score

def read(p):return json.loads(p.read_text('utf-8-sig'))
def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);base=OUT/'interim-diagnosis/scope-v2';dest=OUT/'interim-diagnosis/scope-v4';dest.mkdir(exist_ok=True)
 prior=read(OUT/'negative-expanded-mask-data.json');data=read(OUT/'scope-v4-mask-data.json');base_protocol=read(base/'protocol.json');changed=set();rgb_identical=0
 eligible=lambda r:r['split']=='validation' and r['target'] in TARGETS
 rows=[r for r in data['rows'] if eligible(r)]
 for a,b in zip(prior['rows'],data['rows']):
  assert all(a[k]==b[k] for k in ['id','sha256','group','split','target','rect','sourceNativeSize'])
  if not eligible(a):continue
  with np.load(OUT/prior['tensorFolder']/a['id']) as f:x=f['rgb'].copy();y=f['truth'].copy()
  with np.load(OUT/data['tensorFolder']/b['id']) as f:
   assert np.array_equal(x,f['rgb']),'SOURCE_INPUT_CHANGED_CANNOT_REUSE_PREDICTIONS'
   if not np.array_equal(y,f['truth']):changed.add((b['sha256'],b['target']))
  rgb_identical+=1
 for r in data['rows'][len(prior['rows']):]:
  if eligible(r):changed.add((r['sha256'],r['target']))
 delta=[r for r in rows if (r['sha256'],r['target']) in changed]
 protocol=dict(**RULE,ledgerSHA256=sha(OUT/'scope-v4-mask-data.json'),baseFullEvaluationProtocolSHA256=sha(base/'protocol.json'),oldNativeRGBInputsIdentical=rgb_identical,oldValidationTiles=base_protocol['validationTiles'],allValidationTiles=len(rows),recomputedSourceScopes=[list(k) for k in sorted(changed)],recomputedTiles=len(delta),finalOpened=False,acceptanceThresholdsChanged=False,models=base_protocol['models'],legacyFullROIFlagsNotTrusted=True)
 p=dest/'protocol.json'
 if p.exists():assert read(p)==protocol,'SCOPE_PROTOCOL_CHANGED'
 else:write('interim-diagnosis/scope-v4/protocol.json',protocol)
 mean=torch.tensor([.485,.456,.406])[:,None,None];std=torch.tensor([.229,.224,.225])[:,None,None];net=SkinUNet();net.eval();results=[]
 for model in protocol['models']:
  output=dest/(model['sha256']+'.json')
  if output.exists():results.append(read(output));continue
  baseline=read(base/(model['sha256']+'.json'));assert baseline['model']==model and sha(Path(model['folder'])/'model.safetensors')==model['sha256']
  net.load_state_dict(load_file(str(Path(model['folder'])/'model.safetensors')));scopes=SourceScopes();start=time.monotonic()
  with torch.inference_mode():
   for i,r in enumerate(delta):
    with np.load(OUT/data['tensorFolder']/r['id']) as f:
     x=(torch.from_numpy(f['rgb'].copy().transpose(2,0,1)).float()/255-mean)/std;j=DATA_TARGETS.index(r['target']);y=f['truth'][j].copy();s=f['support'][j].copy()
    pred=net(x[None]).sigmoid()[0,TARGETS.index(r['target'])].numpy()>=.5;scopes.add(r,pred,y,s)
  updated=scopes.finish(TARGETS);merged=collections.defaultdict(list)
  for t in TARGETS:
   for r in baseline['metrics'][t]['rows']:
    if (r['sha256'],t) not in changed:
     r=dict(r);r['falseComponentsOnReviewedNegative']=r.pop('falseNegativeSupportComponents',r.get('falseComponentsOnReviewedNegative'));merged[t].append(r)
   merged[t].extend(updated[t]['rows'])
  metrics=SourceScopes.summarize(merged,TARGETS);result=dict(model=model,protocolSHA256=sha(p),metrics=metrics,globalScore=global_score(metrics,TARGETS),identicalEvaluationRowsReused=True,allSuitableValidationRecordsCovered=True,newInferenceTiles=len(delta),elapsedSeconds=time.monotonic()-start)
  write('interim-diagnosis/scope-v4/'+output.name,result);results.append(result);print('COMPLETE SCOPE',model['epoch'],len(delta),result['globalScore'],flush=True)
 selections={}
 for t in TARGETS:
  candidates=[r for r in results if r['metrics'][t]['rankingUsable']];best=max(candidates,key=lambda r:r['metrics'][t]['developmentScore']) if candidates else None
  selections[t]=dict(selectedFullModel=best['model'] if best else None,channel=TARGETS.index(t),metrics=best['metrics'][t] if best else None,
                    reason='positive recall and reviewed negative FPR jointly measured' if best else 'missing positive or negative evidence; unranked',weightsMixed=False,productAccepted=False)
 global_best=max([r for r in results if r['globalScore'] is not None],key=lambda r:r['globalScore'],default=None)
 write('interim-diagnosis/scope-v4/selection.json',dict(protocolSHA256=sha(p),targets=selections,globalFullModel=global_best['model'] if global_best else None,globalScore=global_best['globalScore'] if global_best else None,allValidationTiles=len(rows),allSuitableValidationRecordsCovered=True,finalOpened=False,productionInstalled=False))
 print('SCOPE V4 ALL VALIDATION COMPLETE',flush=True)
if __name__=='__main__':main()
