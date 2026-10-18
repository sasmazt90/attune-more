"""Finite real B0 upper-feature fine tuning on the hash-bound clean development set.

No old final is re-opened. A development success cannot authorize deployment.
Transactional optimizer/scheduler/RNG/cursor resume uses safe local tensors.
"""
import json, random, time
import numpy as np
import torch
from torch import nn
from safetensors.torch import save_file, load_file
from selected_sources import OUT, ROOT, write, sha
from train_focused_type import model, image, scores, CLASSES
from training_checkpoint import checkpoint, resume

def main():
 torch.set_num_threads(2);torch.manual_seed(20261011);random.seed(20261011);np.random.seed(20261011)
 folder=OUT/'type';folder.mkdir(parents=True,exist_ok=True)
 assert not (folder/'selection.json').exists(),'Completed run preserved'
 source=ROOT/'audit-results/skin-followup-20261011/development-manifest-v2.json'
 data=json.loads(source.read_text('utf8'));rows=[r for r in data['rows'] if r.get('typeEligible') and r['split']!='test']
 tr=[r for r in rows if r['split']=='train'];va=[r for r in rows if r['split']=='validation'];assert tr and va
 protocol=dict(architecture='EfficientNet-B0',featuresTrained=['features.6','features.7','features.8','classifier'],maximumEpochs=12,patience=4,maximumSeconds=2400,seed=20261011,batch=12,optimizer='AdamW',lr=.0002,scheduler='cosine',minimumMacroF1=.6,minimumClassF1=.4,confidencePrecision=.7,confidenceMinimumSupport=10,selection='development validation only',independentFinalAvailable=False,oldTestNeverOpened=True,sourceManifestSHA256=sha(source),classOrder=CLASSES,normalization='actual RGB224 camera-crop-v1 ImageNet; pixel cache, no frozen feature cache')
 write('type/protocol.json',protocol);identity=sha(folder/'protocol.json')
 net=model('efficientnet_b0')
 for k,p in net.named_parameters():p.requires_grad=k.startswith(('features.6','features.7','features.8','classifier'))
 initial={k:v.clone() for k,v in net.state_dict().items()};proof_keys=['features.6.0.block.0.0.weight','features.7.0.block.0.0.weight','features.8.0.weight','classifier.1.weight']
 proof_keys=[k for k in proof_keys if k in initial];before={k:initial[k].clone() for k in proof_keys}
 y=torch.tensor([CLASSES.index(r['class']) for r in tr]);vy=np.array([CLASSES.index(r['class']) for r in va]);counts=torch.bincount(y,minlength=4);weights=counts.sum()/(4*counts.float())
 started=time.monotonic();X=torch.stack([image(r) for r in tr]);VX=torch.stack([image(r) for r in va])
 opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.0002,weight_decay=.01);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,protocol['maximumEpochs'])
 state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,seconds=0.,scheduler=sched.state_dict(),gradientMax={})
 def trainmode():
  net.train()
  for m in net.modules():
   if isinstance(m,nn.BatchNorm2d):m.eval()
 def advance(ids):
  trainmode();opt.zero_grad();xx=X[ids]
  if random.random()<.5:xx=xx.flip(-1)
  loss=nn.functional.cross_entropy(net(xx),y[ids],weight=weights);assert torch.isfinite(loss)
  loss.backward()
  for k,p in net.named_parameters():
   if k in proof_keys and p.grad is not None:state['gradientMax'][k]=max(state['gradientMax'].get(k,0.),float(p.grad.abs().max()))
  nn.utils.clip_grad_norm_(net.parameters(),5);opt.step();return float(loss.detach())
 def save():
  state['seconds']=previous+time.monotonic()-started;state['scheduler']=sched.state_dict();checkpoint(folder,net,opt,state)
 if (folder/'CURRENT').exists():
  state=resume(folder,net,opt,identity);sched.load_state_dict(state['scheduler']);previous=state['seconds']
 else:
  previous=0.
  tiny=torch.tensor([int((y==c).nonzero()[i]) for c in range(4) for i in range(2)])
  losses=[advance(tiny) for _ in range(50)]
  net.eval()
  with torch.inference_mode():acc=float((net(X[tiny]).argmax(1)==y[tiny]).float().mean())
  write('type/learning.json',dict(trainOnly=True,images=8,firstLoss=float(np.mean(losses[:5])),lastLoss=float(np.mean(losses[-5:])),accuracy=acc,passed=acc>=.875,gradients=state['gradientMax']))
  assert acc>=.875,'REAL_FEATURE_LEARNING_CHAIN_FAILED'
  net.load_state_dict(initial);opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.0002,weight_decay=.01);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,protocol['maximumEpochs']);state['gradientMax']={};save()
 while state['epoch']<protocol['maximumEpochs'] and state['bad']<protocol['patience']:
  if previous+time.monotonic()-started>=protocol['maximumSeconds']:break
  epoch_start=time.monotonic()
  if not state['order']:state['order']=torch.randperm(len(tr)).tolist();state['cursor']=0;state['losses']=[]
  last_save=time.monotonic()
  while state['cursor']<len(tr):
   if previous+time.monotonic()-started>=protocol['maximumSeconds']:save();write('type/stop.json',dict(reason='FINITE_WALL_LIMIT',validatedEpochs=state['epoch'],partialEpochPreserved=True));return
   ids=state['order'][state['cursor']:state['cursor']+12];v=advance(ids);state['losses'].append(v);state['cursor']+=len(ids);state['step']+=1
   if time.monotonic()-last_save>60:save();last_save=time.monotonic();print('type',state['epoch']+1,state['cursor'],len(tr),flush=True)
  net.eval();logits=[]
  with torch.inference_mode():
   for i in range(0,len(va),12):logits.append(net(VX[i:i+12]).numpy())
  logits=np.concatenate(logits);m=scores(vy,logits);state['epoch']+=1
  entry=dict(epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=m,epochSeconds=time.monotonic()-epoch_start,seconds=previous+time.monotonic()-started);state['history'].append(entry)
  if m['macroF1']>state['best']+1e-5:
   state['best']=m['macroF1'];state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'));np.save(folder/'validation-logits.npy',logits,allow_pickle=False)
  else:state['bad']+=1
  sched.step();state.update(order=[],cursor=0);save();write('type/history.json',state['history']);print('type epoch',state['epoch'],'macroF1',m['macroF1'],'seconds',entry['epochSeconds'],flush=True)
 assert state['history'],'NO_VALIDATED_EPOCH'
 selected=load_file(str(folder/'selected.safetensors'));changes={k:dict(maxAbs=float((selected[k]-before[k]).abs().max()),changed=not torch.equal(selected[k],before[k]),gradientMax=state['gradientMax'].get(k,0.)) for k in proof_keys}
 assert all(v['changed'] and v['gradientMax']>0 for v in changes.values()),'REQUIRED_FEATURES_DID_NOT_LEARN'
 net.load_state_dict(selected);net.eval();best=max(state['history'],key=lambda h:h['validation']['macroF1'])
 write('type/selection.json',dict(validation=best['validation'],selectedEpoch=best['epoch'],featureEvidence=changes,weightsSHA256=sha(folder/'selected.safetensors'),accepted=False,reason='No unused four-class source holdout; clean source labels/camera domain unaccepted',seconds=previous+time.monotonic()-started))
 path=folder/'candidate.onnx';x=VX[0:1];torch.onnx.export(net,x,str(path),input_names=['rgb'],output_names=['type_logits'],opset_version=17,dynamo=False)
 import onnxruntime as ort
 options=ort.SessionOptions();options.intra_op_num_threads=2;session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);errors=[]
 with torch.inference_mode():
  for xx in VX[:6].split(1):errors.append(float(np.abs(session.run(None,{'rgb':xx.numpy()})[0]-net(xx).numpy()).max()))
 assert max(errors)<.001
 write('type/export.json',dict(sha256=sha(path),maxAbsoluteError=max(errors),realDevelopmentPhotos=len(errors),accepted=False,productionInstalled=False))

if __name__=='__main__':main()
