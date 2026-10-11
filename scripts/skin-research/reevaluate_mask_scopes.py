"""Reevaluate all development native tiles for pinned, preserved full checkpoints."""
import collections, json, sys, time
from pathlib import Path
import cv2, numpy as np, torch
from safetensors.torch import load_file
from expanded_sources import OUT, sha
from selected_sources import TARGETS
from prepare_continuation_masks import TARGETS as DATA_TARGETS
from selected_mask_model import SkinUNet
from mask_scope_metrics import SourceScopes, RULE, global_score

D=OUT/'interim-diagnosis'/'scope-v2'; D.mkdir(parents=True,exist_ok=True)
def read(p): return json.loads(p.read_text('utf-8-sig'))
def write(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n','utf8');t.replace(p)

def main():
 torch.set_num_threads(1);cv2.setNumThreads(1)
 ledger=OUT/'negative-expanded-mask-data.json';data=read(ledger)
 rows=[r for r in data['rows'] if r['split']=='validation' and r['target'] in TARGETS]
 assert not {r['group'] for r in rows}&{r['group'] for r in data['rows'] if r['split']=='train'}
 parent=OUT/'negative-mask-continuation'
 refs={str(parent/(parent/'CURRENT').read_text().strip()), *[str(parent/r['checkpoint']) for r in read(parent/'target-best-checkpoints.json').values()]}
 refs.add(str(parent/'frozen-parent'/(parent/'frozen-parent/CURRENT').read_text().strip()))
 models=[]
 for path in sorted(refs):
  p=Path(path);s=read(p/'state.json');assert sha(p/'model.safetensors')==s['modelSHA256']
  models.append(dict(folder=str(p),sha256=s['modelSHA256'],epoch=s['epoch'],cursor=s['cursor'],step=s['step']))
 freeze=dict(**RULE,ledgerSHA256=sha(ledger),models=models,validationTiles=len(rows),
             finalOpened=False,acceptanceThresholdsChanged=False,sourceAnnotationExpertise='engineering, not clinical',
             fullROIRequiresExplicitReview=True,oldCurveNotMerged=True)
 if (D/'protocol.json').exists(): assert read(D/'protocol.json')==freeze,'REEVALUATION_FREEZE_CHANGED'
 else:write(D/'protocol.json',freeze)
 inventory={}
 current=read(parent/(parent/'CURRENT').read_text().strip()/'state.json')
 train=[r for r in data['rows'] if r['split']=='train'];used=[train[i] for i in current['actualConsumedTileIDs']]
 for t in TARGETS:
  inventory[t]={}
  for label,rs in [('train',train),('validation',rows),('actuallyConsumed',used)]:
   rs=[r for r in rs if r['target']==t]
   inventory[t][label]=dict(photos=len({r['sha256'] for r in rs}),groups=len({r['group'] for r in rs}),
    positivePhotos=len({r['sha256'] for r in rs if r['positivePixels']}),
    negativeSupportPhotos=len({r['sha256'] for r in rs if r['knownNegativePixels']}),
    negativeOnlyTilePhotos=len({r['sha256'] for r in rs if not r['positivePixels'] and r['knownNegativePixels']}),
    tiles=len(rs),positiveTiles=sum(r['positivePixels']>0 for r in rs),
    negativeSupportTiles=sum(r['knownNegativePixels']>0 for r in rs),
    explicitReviewedTiles=sum(r.get('engineeringNegativeROIReviewed') is True or r.get('wholeValidSkinROIEngineeringReviewed') is True for r in rs))
 write(D/'inventory.json',inventory)
 net=SkinUNet();net.eval();mean=torch.tensor([.485,.456,.406])[:,None,None];std=torch.tensor([.229,.224,.225])[:,None,None]
 results=[]
 for model in models:
  output=D/(model['sha256']+'.json')
  if output.exists(): results.append(read(output));continue
  net.load_state_dict(load_file(str(Path(model['folder'])/'model.safetensors')))
  scopes=SourceScopes();start=time.monotonic()
  with torch.inference_mode():
   for i,r in enumerate(rows):
    with np.load(OUT/data['tensorFolder']/r['id']) as v:
     x=(torch.from_numpy(v['rgb'].copy().transpose(2,0,1)).float()/255-mean)/std
     j=DATA_TARGETS.index(r['target']);y=v['truth'][j].copy();s=v['support'][j].copy()
    p=net(x[None]).sigmoid()[0,TARGETS.index(r['target'])].numpy()>=RULE['threshold']
    scopes.add(r,p,y,s)
    if i%100==0:
     write(D/'progress.json',dict(model=model,completedTiles=i+1,totalTiles=len(rows),elapsedSeconds=time.monotonic()-start));print('scope-v2',model['epoch'],i+1,len(rows),flush=True)
  metrics=scopes.finish(TARGETS);result=dict(model=model,protocolSHA256=sha(D/'protocol.json'),metrics=metrics,globalScore=global_score(metrics,TARGETS),elapsedSeconds=time.monotonic()-start)
  write(output,result);results.append(result)
 selections={}
 for t in TARGETS:
  eligible=[r for r in results if r['metrics'][t]['rankingUsable']]
  best=max(eligible,key=lambda r:r['metrics'][t]['developmentScore']) if eligible else None
  selections[t]=dict(selectedFullModel=best['model'] if best else None,channel=TARGETS.index(t),
   metrics=best['metrics'][t] if best else None,reason='source-macro positive recall and reviewed negative suppression' if best else 'insufficient evidence; no selected model',
   exportRequiresFullModel=True,weightsMixed=False,productAccepted=False)
 write(D/'selection.json',dict(protocolSHA256=sha(D/'protocol.json'),targets=selections,evaluatedModels=models,allValidationTilesEvaluated=True,finalOpened=False,productionInstalled=False))
 print('ALL VALIDATION SCOPE V2 COMPLETE',flush=True)

if __name__=='__main__':main()
