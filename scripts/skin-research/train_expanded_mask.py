"""Resumable target-balanced U-Net training on native reviewed local tiles."""
import argparse,collections,json,random,time
import cv2,numpy as np,torch
from safetensors.torch import load_file,save_file
from expanded_sources import OUT,write,sha
from expanded_mask_data import prepare
from selected_mask_model import SkinUNet,masked_loss
from selected_sources import TARGETS
from training_checkpoint import checkpoint,resume
MEAN=torch.tensor([.485,.456,.406])[:,None,None];STD=torch.tensor([.229,.224,.225])[:,None,None]

def main(seconds):
 torch.set_num_threads(1);cv2.setNumThreads(1);torch.manual_seed(20261011);np.random.seed(20261011);random.seed(20261011)
 data=prepare();folder=OUT/'mask';tr=[r for r in data['rows'] if r['split']=='train'];va=[r for r in data['rows'] if r['split']=='validation' and r['completeROI']]
 if (folder/'selection.json').exists():print('Completed expanded mask run preserved');return
 protocol=dict(version='target-balanced-native-mask-v2',dataSHA256=sha(OUT/'mask-data.json'),maximumEpochs=32,minimumEpochs=12,patience=8,threads=1,batch=2,learningRate=.0001,optimizer='AdamW',weightDecay=.001,scheduler='cosine',sigmoidIndependent=True,targets=TARGETS,nativeTile=256,partialUnknownExcluded=True,perTargetBest=True,negativePairSampling=True,positiveTilesPerTargetPerEpoch=200,freezeEarlyEncoder=True,expertLabels=False,validationScope='engineering development, source-group separated; not unused independent final')
 write('mask/protocol.json',protocol);identity=sha(folder/'protocol.json');net=SkinUNet()
 proof=['encoder.layer4.0.conv1.weight','d4.0.weight','head.weight'];initial={k:v.clone() for k,v in net.state_dict().items()}
 for name,p in net.encoder.named_parameters():
  if name.startswith(('conv1.','bn1.','layer1.','layer2.')):p.requires_grad_(False)
 opt=torch.optim.AdamW(net.parameters(),lr=.0001,weight_decay=.001);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32)
 state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,seconds=0.,gradients={},targetBest={},scheduler=sched.state_dict());started=time.monotonic();previous=0.
 def tensors(r):
  with np.load(folder/'tensors'/r['id']) as v:
   return (torch.from_numpy(v['rgb'].copy().transpose(2,0,1)).float()/255-MEAN)/STD,torch.from_numpy(v['truth'].copy()).float(),torch.from_numpy(v['support'].copy()).float()
 def advance(ids):
  net.train()
  for m in net.modules():
   if isinstance(m,torch.nn.BatchNorm2d):m.eval()
  values=[tensors(tr[i]) for i in ids];x,y,s=[torch.stack([r[j] for r in values]) for j in range(3)];opt.zero_grad();v=masked_loss(net(x),y,s,balanced=True);assert torch.isfinite(v);v.backward()
  for k,p in net.named_parameters():
   if k in proof:state['gradients'][k]=max(state['gradients'].get(k,0.),float(p.grad.abs().max()))
  torch.nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step();return float(v.detach())
 def evaluate():
  net.eval();sources={}
  with torch.inference_mode():
   for r in va:
    x,y,s=tensors(r);j=TARGETS.index(r['target']);p=net(x[None]).sigmoid()[0,j].numpy()>=.5;a,b,c,d=r['rect'];k=(r['sha256'],r['target'])
    if k not in sources:
     w,h=r['sourceNativeSize'];sources[k]=[np.zeros((h,w),bool),np.zeros((h,w),bool),np.zeros((h,w),bool)]
    pp,yy,ss=sources[k];pp[b:d,a:c]|=p[:d-b,:c-a];yy[b:d,a:c]|=y[j].numpy()[:d-b,:c-a]>0;ss[b:d,a:c]|=s[j].numpy()[:d-b,:c-a]>0
  rows=collections.defaultdict(list)
  for (key,t),(p,y,s) in sources.items():
   p&=s;y&=s;negative=s&~y;i=int((p&y).sum());total=int((p|y).sum())
   rows[t].append(dict(sha256=key,Dice=2*i/max(1,int(p.sum()+y.sum())) if y.any() else None,IoU=i/max(1,total) if y.any() else None,positivePixels=int(y.sum()),negativePixels=int(negative.sum()),negativeFPR=float(p[negative].mean()) if negative.any() else None,wholeReviewedROI=True))
  return {t:dict(Dice=float(np.mean([r['Dice'] for r in rs if r['Dice'] is not None])) if any(r['Dice'] is not None for r in rs) else None,IoU=float(np.mean([r['IoU'] for r in rs if r['IoU'] is not None])) if any(r['IoU'] is not None for r in rs) else None,negativeFPR=float(np.mean([r['negativeFPR'] for r in rs if r['negativeFPR'] is not None])),positiveROIs=sum(r['positivePixels']>0 for r in rs),negativeROIs=sum(r['positivePixels']==0 for r in rs),rows=rs,scope='complete engineering reviewed visible anatomical ROI, development only') for t,rs in rows.items()}
 def save():
  state['seconds']=previous+time.monotonic()-started;state['scheduler']=sched.state_dict();checkpoint(folder,net,opt,state)
 if (folder/'CURRENT').exists():state=resume(folder,net,opt,identity);sched.load_state_dict(state['scheduler']);previous=state['seconds']
 else:
  tiny=[i for i,r in enumerate(tr) if r['completeROI'] and r['positivePixels']][:2];assert len(tiny)==2
  old=folder/'learning.json'
  if old.exists():old.replace(folder/f'learning-previous-{int(time.time())}.json')
  losses=[]
  for step in range(160):
   losses.append(advance(tiny))
   if (step+1)%40==0:print('native mask learning',step+1,float(np.mean(losses[-6:])),flush=True)
  passed=np.mean(losses[-6:])<np.mean(losses[:6])*.65;write('mask/learning.json',dict(firstLoss=float(np.mean(losses[:6])),lastLoss=float(np.mean(losses[-6:])),passed=bool(passed),steps=160,trainOnly=True,resetBeforeExpanded=True));assert passed,'NATIVE_MASK_LEARNING_CHAIN_FAILED'
  net.load_state_dict(initial);save_file({k:initial[k].contiguous() for k in proof},str(folder/'feature-initial.safetensors'));opt=torch.optim.AdamW(net.parameters(),lr=.0001,weight_decay=.001);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32);state['gradients']={};save()
 pos={t:[i for i,r in enumerate(tr) if r['target']==t and r['positivePixels']] for t in TARGETS};neg={t:[i for i,r in enumerate(tr) if r['target']==t and r['knownNegativePixels'] and r['completeROI']] for t in TARGETS}
 write('mask/sampling.json',dict(positiveTiles={t:len(v) for t,v in pos.items()},knownNegativeTiles={t:len(v) for t,v in neg.items()},positiveTilesPerTargetPerEpoch=200,cycleThroughEveryTileBeforeReshuffling=True,areaBalancedLoss=True,targetWeights={t:1 for t in TARGETS},selectionUsesDevelopmentOnly=True))
 while state['epoch']<32 and (state['epoch']<12 or state['bad']<8):
  start=time.monotonic();last=time.monotonic()
  if not state['order']:
   queues=state.setdefault('targetQueues',{});order=[]
   for _ in range(200):
    for t,v in pos.items():
     if not v:continue
     if not queues.get(t):queues[t]=random.sample(v,len(v))
     i=queues[t].pop();order.append([i,random.choice(neg[t]) if neg[t] else i])
   for t,v in neg.items():
    if not pos[t]:order.extend([[i,i] for i in v])
   state.update(order=order,cursor=0,losses=[])
  while state['cursor']<len(state['order']):
   if time.monotonic()-started>=seconds:
    save();write('mask/stop.json',dict(reason='RESUMABLE_INVOCATION_TIME_SLICE',validatedEpochs=state['epoch'],partialEpochPreserved=True,trainingComplete=False));return
   state['losses'].append(advance(state['order'][state['cursor']]));state['cursor']+=1;state['step']+=1
   if time.monotonic()-last>60:save();last=time.monotonic();print('expanded mask',state['epoch']+1,state['cursor'],len(state['order']),flush=True)
  metrics=evaluate();available=[v['Dice']-v['negativeFPR'] for v in metrics.values() if v['Dice'] is not None];score=float(np.mean(available));state['epoch']+=1;elapsed=time.monotonic()-start;entry=dict(epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=metrics,epochSeconds=elapsed);state['history'].append(entry)
  for t,m in metrics.items():
   value=(m['Dice'] if m['Dice'] is not None else 0)-m['negativeFPR']
   if value>state['targetBest'].get(t,{}).get('score',-2):
    state['targetBest'][t]=dict(epoch=state['epoch'],score=value,metrics=m);save_file(net.state_dict(),str(folder/f'best-{t}.safetensors'))
  if score>state['best']+1e-5:state['best']=score;state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'))
  else:state['bad']+=1
  sched.step();state.update(order=[],cursor=0);save();write('mask/history.json',state['history']);write('mask/eta.json',dict(epochsCompleted=state['epoch'],measuredEpochSeconds=elapsed,remainingUpperBoundSeconds=elapsed*(32-state['epoch']),CPUOnly=True,counts=data['counts']));print('expanded mask epoch',state['epoch'],score,'seconds',elapsed,flush=True)
 before=load_file(str(folder/'feature-initial.safetensors'));selected=load_file(str(folder/'selected.safetensors'));features={k:dict(maxAbs=float((selected[k]-before[k]).abs().max()),gradientMax=state['gradients'].get(k,0)) for k in proof};assert all(v['maxAbs']>0 and v['gradientMax']>0 for v in features.values())
 write('mask/selection.json',dict(trainingComplete=True,epochsCompleted=state['epoch'],perCriterionBest=state['targetBest'],features=features,weightsSHA256=sha(folder/'selected.safetensors'),stopReason='VALIDATION_PLATEAU' if state['epoch']<32 else 'PLANNED_UPPER_BOUND',acceptanceDecisionRequired=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=7200);main(p.parse_args().seconds)
