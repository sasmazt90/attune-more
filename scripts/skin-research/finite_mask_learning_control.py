"""Three serial 12-update controls from one exact preserved optimizer/RNG state.
No active trainer, no final pixels, no promotion, no architecture replacement.
"""
import json,time
from pathlib import Path
import cv2,numpy as np,torch,psutil
from expanded_sources import ROOT,OUT,sha,write
from training_checkpoint import resume,checkpoint
from selected_mask_model import SkinUNet,masked_loss
from selected_sources import TARGETS
from prepare_continuation_masks import TARGETS as DATA_TARGETS
from storage_guard import checkpoint_storage_pause

FOCUS=['oil','redness','tone','dark'];D=OUT/'interim-diagnosis/finite-learning-v2'
MEAN=torch.tensor([.485,.456,.406])[:,None,None];STD=torch.tensor([.229,.224,.225])[:,None,None]
def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);D.mkdir(exist_ok=True)
 for p in psutil.process_iter(['cmdline','cwd']):
  if any(Path(a).name in ['train_continuation_mask.py','train_expanded_detector.py','train_scope_phase.py'] for a in p.info['cmdline'] or []) and Path(p.info['cwd'] or '.').resolve()==ROOT:raise RuntimeError('DO_NOT_DUPLICATE_ACTIVE_TRAINING')
 parent=OUT/'negative-mask-continuation';generation=parent/(parent/'CURRENT').read_text().strip();saved=json.loads((generation/'state.json').read_text());ledger=OUT/'scope-v4-mask-data.json';data=json.loads(ledger.read_text());rows=data['rows']
 def choose(t,split,pos):
  candidates=sorted([r for r in rows if r['target']==t and r['split']==split and (r['positivePixels']>0 if pos else r.get('engineeringNegativeROIReviewed') is True and r['knownNegativePixels']>0)],key=lambda r:(r['sha256'],-r['positivePixels']))
  chosen=[];seen=set()
  for r in candidates:
   if r['sha256'] in seen:continue
   seen.add(r['sha256']);chosen.append(r)
   if len(chosen)==3:break
  return chosen
 examples={t:{'positive':choose(t,'train',True),'negative':choose(t,'train',False),'validationPositive':choose(t,'validation',True)[:1],'validationNegative':choose(t,'validation',False)[:1]} for t in FOCUS}
 assert all(all(v for v in pools.values()) for pools in examples.values())
 manifest=dict(parentCheckpoint=str(generation),parentModelSHA256=saved['modelSHA256'],parentOptimizerSHA256=saved['optimizerSHA256'],ledgerSHA256=sha(ledger),stepsPerArm=12,serialArms=['repeat-negative-original-loss','diverse-negative-original-loss','diverse-negative-image-balanced-loss'],finalOpened=False,examples={t:{k:[dict(**r,tensorSHA256=sha(OUT/data['tensorFolder']/r['id'])) for r in rs] for k,rs in pools.items()} for t,pools in examples.items()})
 write('interim-diagnosis/finite-learning-v2/protocol.json',manifest)
 def tensors(r):
  with np.load(OUT/data['tensorFolder']/r['id']) as f:
   x=(torch.from_numpy(f['rgb'].copy().transpose(2,0,1)).float()/255-MEAN)/STD;y=torch.from_numpy(f['truth'][[DATA_TARGETS.index(t) for t in TARGETS]].copy()).float();s=torch.from_numpy(f['support'][[DATA_TARGETS.index(t) for t in TARGETS]].copy()).float()
  return x,y,s
 def metrics(net):
  net.eval();out={}
  with torch.inference_mode():
   for t,pools in examples.items():
    vals={}
    for label,key in [('positiveRecall','validationPositive'),('negativeFPR','validationNegative')]:
     r=pools[key][0];x,y,s=tensors(r);j=TARGETS.index(t);p=net(x[None]).sigmoid()[0,j]>=.5;m=(y[j]>0) if label=='positiveRecall' else ((s[j]>0)&(y[j]==0));vals[label]=float(p[m].float().mean()) if m.any() else None;vals[label+'Source']=r['sha256']
    out[t]=vals
  return out
 results=[]
 for arm in manifest['serialArms']:
  folder=D/arm;folder.mkdir(exist_ok=True)
  if (folder/'receipt.json').exists():results.append(json.loads((folder/'receipt.json').read_text()));continue
  net=SkinUNet()
  for k,p in net.encoder.named_parameters():p.requires_grad_(not k.startswith(('conv1.','bn1.','layer1.','layer2.')))
  opt=torch.optim.AdamW(net.parameters(),lr=.0001,weight_decay=.001)
  if (folder/'CURRENT').exists():
   state=resume(folder,net,opt,saved['identity']);assert state['controlProtocolSHA256']==sha(D/'protocol.json') and state['controlArm']==arm;before=state['controlBefore'];updates=state['controlUpdates'];start_step=state['controlStep']
  else:
   state=resume(parent,net,opt,saved['identity']);before=metrics(net);updates=[];start_step=0
  started=time.monotonic()
  for step in range(start_step,12):
   if checkpoint_storage_pause(folder) or time.monotonic()-started>900:
    state.update(controlStep=step,controlArm=arm,controlBefore=before,controlUpdates=updates,controlProtocolSHA256=sha(D/'protocol.json'));checkpoint(folder,net,opt,state);raise RuntimeError('CONTROL_SAFELY_PAUSED; resumable full state preserved')
   t=FOCUS[step%4];round_index=step//4;pool=examples[t];pos=pool['positive'][round_index%len(pool['positive'])];neg=pool['negative'][0 if arm.startswith('repeat') else round_index%len(pool['negative'])];values=[tensors(r) for r in [pos,neg]];x,y,s=[torch.stack([v[i] for v in values]) for i in range(3)]
   net.train()
   for m in net.modules():
    if isinstance(m,torch.nn.BatchNorm2d):m.eval()
   opt.zero_grad();logits=net(x);logits.retain_grad();loss=masked_loss(logits,y,s,balanced=True,image_balanced=arm.endswith('image-balanced-loss'));assert torch.isfinite(loss);loss.backward();grad=logits.grad;j=TARGETS.index(t);known=s>0;positive=known&(y>0);negative=known&~positive
   assert bool((grad[~known]==0).all());assert grad[positive].abs().sum()>0 and grad[negative].abs().sum()>0
   updates.append(dict(step=step,target=t,positiveSource=pos['sha256'],negativeSource=neg['sha256'],loss=float(loss.detach()),unknownGradientMax=float(grad[~known].abs().max()),positiveGradientMean=float(grad[positive].abs().mean()),negativeGradientMean=float(grad[negative].abs().mean()),predictedKnownPositiveFraction=float((logits.sigmoid()[positive]>=.5).float().mean()),predictedKnownNegativeFraction=float((logits.sigmoid()[negative]>=.5).float().mean())))
   torch.nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step()
  after=metrics(net);state.update(controlStep=12,controlArm=arm,controlProtocolSHA256=sha(D/'protocol.json'),controlOnlyNoProduction=True);checkpoint(folder,net,opt,state)
  result=dict(arm=arm,before=before,after=after,updates=updates,optimizerRNGInherited=True,originalResumeCursorUnchanged=saved['cursor'],originalPhaseUntouched=True,finalOpened=False,installed=False,elapsedSeconds=time.monotonic()-started,conclusionsLimitedToSmallDevelopmentControls=True)
  (folder/'receipt.json').write_text(json.dumps(result,indent=2),'utf8');results.append(result);print('FINITE CONTROL COMPLETE',arm,flush=True);del net,opt
 write('interim-diagnosis/finite-learning-v2/receipt.json',dict(arms=results,stepsPerArm=12,serialOneTrainerProcess=True,clinicalPerformanceProven=False,longExtraTrainingStarted=False));print('FINITE LEARNING COMPLETE',flush=True)
if __name__=='__main__':main()
