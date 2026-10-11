"""Regularized, streamed RGB feature training; no source class relabelling.

The old exposed test stays excluded. Same-group class conflicts fail preparation.
The four source labels are hypotheses about appearance, not clinical truth.
"""
import argparse,collections,json,random,time
import cv2,numpy as np,torch
from torch import nn
from safetensors.torch import load_file,save_file
from expanded_sources import OUT,PREVIOUS,write,sha
from train_focused_type import model,image,scores,CLASSES
from training_checkpoint import checkpoint,resume

def main(seconds):
 torch.set_num_threads(1);cv2.setNumThreads(1);torch.manual_seed(20261011);np.random.seed(20261011);random.seed(20261011)
 source=PREVIOUS.parent/'skin-followup-20261011/development-manifest-v2.json'
 original=json.loads(source.read_text('utf8'));rows=[r for r in original['rows'] if r.get('typeEligible') and r['split'] in ('train','validation')]
 groups=collections.defaultdict(set)
 for r in rows:groups[r['group']].add(r['class'])
 assert all(len(v)==1 for v in groups.values()),'SOURCE_GROUP_CLASS_CONFLICT'
 tr=[r for r in rows if r['split']=='train'];va=[r for r in rows if r['split']=='validation'];folder=OUT/'type';folder.mkdir(parents=True,exist_ok=True)
 if (folder/'selection.json').exists():print('Completed type continuation preserved');return
 protocol=dict(version='regularized-rgb-feature-type-v1',sourceSHA256=sha(source),classes=CLASSES,sourceLabelSemanticsVerified=False,combinationLabelOrigin='source directory; no invented expert relabel',sourceClassConflictGroups=0,trainCounts=dict(collections.Counter(r['class'] for r in tr)),validationCounts=dict(collections.Counter(r['class'] for r in va)),trainImages=len(tr),validationImages=len(va),trainGroups=len({r['group'] for r in tr}),validationGroups=len({r['group'] for r in va}),maximumEpochs=32,minimumEpochs=12,patience=8,batch=8,threads=1,featureLR=.00005,classifierLR=.0002,weightDecay=.05,labelSmoothing=.1,dropout=.4,scheduler='cosine',preprocessing='source camera-crop-v1 RGB224 INTER_AREA ImageNet',featureTraining=['features.6','features.7','features.8','classifier'],oldOpenedTestExcluded=True,validationScope='source-group development only',independentFinalAvailable=False,streamedPixelBatches=True)
 write('type/protocol.json',protocol);identity=sha(folder/'protocol.json');net=model('efficientnet_b0');net.classifier[0].p=.4
 for k,p in net.named_parameters():p.requires_grad_(k.startswith(('features.6','features.7','features.8','classifier')))
 initial={k:v.clone() for k,v in net.state_dict().items()};proof=['features.6.0.block.0.0.weight','features.7.0.block.0.0.weight','features.8.0.weight','classifier.1.weight']
 def optimizer():return torch.optim.AdamW([dict(params=[p for k,p in net.named_parameters() if p.requires_grad and k.startswith('features.')],lr=.00005),dict(params=list(net.classifier.parameters()),lr=.0002)],weight_decay=.05)
 opt=optimizer();sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32)
 state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,seconds=0.,gradientMax={},scheduler=sched.state_dict());started=time.monotonic();previous=0.
 counts=torch.tensor([sum(r['class']==c for r in tr) for c in CLASSES]);assert (counts>0).all();weights=(counts.sum()/(4*counts.float())).sqrt()
 def advance(ids,tiny=False):
  net.train();net.classifier[0].p=0. if tiny else .4
  for m in net.modules():
   if isinstance(m,nn.BatchNorm2d):m.eval()
  x=torch.stack([image(tr[i],flip=not tiny and random.random()<.5) for i in ids]);y=torch.tensor([CLASSES.index(tr[i]['class']) for i in ids]);opt.zero_grad()
  loss=nn.functional.cross_entropy(net(x),y,weight=weights,label_smoothing=0. if tiny else .1);assert torch.isfinite(loss);loss.backward()
  for k,p in net.named_parameters():
   if k in proof and p.grad is not None:state['gradientMax'][k]=max(state['gradientMax'].get(k,0.),float(p.grad.abs().max()))
  nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step();return float(loss.detach())
 def evaluate(rs):
  net.eval();values=[]
  with torch.inference_mode():
   for start in range(0,len(rs),8):values.append(net(torch.stack([image(r) for r in rs[start:start+8]])).numpy())
  return np.concatenate(values)
 def save():
  state['seconds']=previous+time.monotonic()-started;state['scheduler']=sched.state_dict();checkpoint(folder,net,opt,state)
 if (folder/'CURRENT').exists():state=resume(folder,net,opt,identity);sched.load_state_dict(state['scheduler']);previous=state['seconds']
 else:
  tiny=[i for c in CLASSES for i in [j for j,r in enumerate(tr) if r['class']==c][:2]];losses=[]
  for step in range(160):
   losses.append(advance(tiny,True))
   if (step+1)%40==0:print('regularized type learning',step+1,float(np.mean(losses[-5:])),flush=True)
  logits=evaluate([tr[i] for i in tiny]);accuracy=float((logits.argmax(1)==np.array([CLASSES.index(tr[i]['class']) for i in tiny])).mean());passed=accuracy>=.875
  write('type/learning.json',dict(trainOnly=True,images=8,steps=160,firstLoss=float(np.mean(losses[:5])),lastLoss=float(np.mean(losses[-5:])),accuracy=accuracy,passed=passed,resetBeforeExpanded=True));assert passed,'TYPE_FEATURE_LEARNING_CHAIN_FAILED'
  net.load_state_dict(initial);net.classifier[0].p=.4;opt=optimizer();sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32);state['gradientMax']={};save_file({k:initial[k].contiguous() for k in proof},str(folder/'feature-initial.safetensors'));save()
 truth=np.array([CLASSES.index(r['class']) for r in va])
 while state['epoch']<32 and (state['epoch']<12 or state['bad']<8):
  start=time.monotonic();last=time.monotonic()
  if not state['order']:state.update(order=random.sample(range(len(tr)),len(tr)),cursor=0,losses=[])
  while state['cursor']<len(tr):
   if time.monotonic()-started>=seconds:save();write('type/stop.json',dict(reason='RESUMABLE_INVOCATION_TIME_SLICE',trainingComplete=False,validatedEpochs=state['epoch'],partialEpochPreserved=True));return
   ids=state['order'][state['cursor']:state['cursor']+8];state['losses'].append(advance(ids));state['cursor']+=len(ids);state['step']+=1
   if time.monotonic()-last>60:save();last=time.monotonic();print('expanded type',state['epoch']+1,state['cursor'],len(tr),flush=True)
  logits=evaluate(va);metrics=scores(truth,logits);state['epoch']+=1;elapsed=time.monotonic()-start;state['history'].append(dict(epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=metrics,epochSeconds=elapsed))
  if metrics['macroF1']>state['best']+1e-5:state['best']=metrics['macroF1'];state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'));np.save(folder/'validation-logits.npy',logits,allow_pickle=False)
  else:state['bad']+=1
  sched.step();state.update(order=[],cursor=0);save();write('type/history.json',state['history']);write('type/eta.json',dict(epochsCompleted=state['epoch'],measuredEpochSeconds=elapsed,remainingUpperBoundSeconds=elapsed*(32-state['epoch']),CPUOnly=True));print('expanded type epoch',state['epoch'],metrics['macroF1'],'seconds',elapsed,flush=True)
 selected=load_file(str(folder/'selected.safetensors'));before=load_file(str(folder/'feature-initial.safetensors'));changes={k:dict(maxAbs=float((selected[k]-before[k]).abs().max()),gradientMax=state['gradientMax'].get(k,0.)) for k in proof};assert all(v['maxAbs']>0 and v['gradientMax']>0 for v in changes.values())
 best=max(state['history'],key=lambda h:h['validation']['macroF1']);write('type/selection.json',dict(trainingComplete=True,epochsCompleted=state['epoch'],selectedEpoch=best['epoch'],validation=best['validation'],features=changes,weightsSHA256=sha(folder/'selected.safetensors'),stopReason='VALIDATION_PLATEAU' if state['epoch']<32 else 'PLANNED_UPPER_BOUND',acceptanceDecisionRequired=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=14400);main(p.parse_args().seconds)
