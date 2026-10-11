"""Resumable target-balanced U-Net training on native reviewed local tiles."""
import argparse,collections,json,random,time
import cv2,numpy as np,torch
from safetensors.torch import load_file,save_file
from expanded_sources import OUT,write,sha
from prepare_continuation_masks import TARGETS as DATA_TARGETS
from selected_mask_model import SkinUNet,masked_loss
from selected_sources import TARGETS
from training_checkpoint import checkpoint,resume
from storage_guard import checkpoint_storage_pause
MEAN=torch.tensor([.485,.456,.406])[:,None,None];STD=torch.tensor([.229,.224,.225])[:,None,None]

def main(seconds, parent_checkpoint=None, refined_support=False, negative_phase=False, until_epoch=None):
 torch.set_num_threads(1);cv2.setNumThreads(1);torch.manual_seed(20261011);np.random.seed(20261011);random.seed(20261011)
 folder_name='negative-mask-continuation' if negative_phase else 'mask-continuation'
 ledger=OUT/('negative-expanded-mask-data.json' if negative_phase else 'continuation-valid-skin-data.json' if refined_support else 'continuation-mask-data.json');data=json.loads(ledger.read_text('utf8'));folder=OUT/folder_name;folder.mkdir(parents=True,exist_ok=True);tr=[r for r in data['rows'] if r['split']=='train'];va=[r for r in data['rows'] if r['split']=='validation' and r['completeROI'] and r['target'] in TARGETS]
 if (folder/'selection.json').exists():print('Completed expanded mask run preserved');return
 protocol=dict(version='source-group-balanced-native-mask-continuation-v1',dataSHA256=sha(ledger),maximumEpochs=30,minimumEpochs=12,patience=8,threads=1,batch=2,learningRate=.0001,optimizer='AdamW',weightDecay=.001,scheduler='cosine',sigmoidIndependent=True,targets=TARGETS,nativeTile=256,partialUnknownExcluded=True,perTargetBest=True,negativePairSampling=True,maximumPositiveGroupsPerTargetPerEpoch=128,freezeEarlyEncoder=True,expertLabels=False,validationScope='engineering development, source-group separated; not unused independent final')
 if negative_phase:
  (folder/'PRESERVE_ALL_CHECKPOINTS').touch(exist_ok=True)
  protocol.update(version='native-target-negative-expansion-phase-v1',maximumEpochs=20,parentDataSHA256=data['parentLedgerSHA256'],newNegativeReviewSHA256=data['negativeReviewSHA256'],phaseCurvesSeparate=True,checkpointSeconds=1800,weightsOptimizerSchedulerRNGPreserved=True,negativeSourceGroupBalanced=True)
 archived=folder/'support-parent-protocol.json'
 if refined_support and not archived.exists():
  import shutil
  shutil.copy2(folder/'protocol.json',archived)
 write(folder_name+'/protocol.json',protocol);identity=sha(folder/'protocol.json');net=SkinUNet()
 proof=['encoder.layer4.0.conv1.weight','d4.0.weight','head.weight'];initial={k:v.clone() for k,v in net.state_dict().items()}
 for name,p in net.encoder.named_parameters():
  if name.startswith(('conv1.','bn1.','layer1.','layer2.')):p.requires_grad_(False)
 opt=torch.optim.AdamW(net.parameters(),lr=.0001,weight_decay=.001);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32)
 state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,seconds=0.,gradients={},targetBest={},scheduler=sched.state_dict());started=time.monotonic();previous=0.
 def tensors(r):
  with np.load(OUT/data.get('tensorFolder','continuation-mask/tensors')/r['id']) as v:
   return (torch.from_numpy(v['rgb'].copy().transpose(2,0,1)).float()/255-MEAN)/STD,torch.from_numpy(v['truth'][[DATA_TARGETS.index(t) for t in TARGETS]].copy()).float(),torch.from_numpy(v['support'][[DATA_TARGETS.index(t) for t in TARGETS]].copy()).float()
 def advance(ids):
  net.train()
  for m in net.modules():
   if isinstance(m,torch.nn.BatchNorm2d):m.eval()
  values=[tensors(tr[i]) for i in ids];x,y,s=[torch.stack([r[j] for r in values]) for j in range(3)];opt.zero_grad();v=masked_loss(net(x),y,s,balanced=True);assert torch.isfinite(v);v.backward()
  for k,p in net.named_parameters():
   if k in proof:state['gradients'][k]=max(state['gradients'].get(k,0.),float(p.grad.abs().max()))
  torch.nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step();return float(v.detach())
 def evaluate():
  net.eval();sources={};roi_review={}
  with torch.inference_mode():
   for r in va:
    x,y,s=tensors(r);j=TARGETS.index(r['target']);p=net(x[None]).sigmoid()[0,j].numpy()>=.5;a,b,c,d=r['rect'];k=(r['sha256'],r['target'])
    roi_review[k]=True if roi_review.get(k,True) is True and (r.get('engineeringNegativeROIReviewed') is True or r.get('wholeValidSkinROIEngineeringReviewed') is True) else None
    if k not in sources:
     w,h=r['sourceNativeSize'];sources[k]=[np.zeros((h,w),bool),np.zeros((h,w),bool),np.zeros((h,w),bool)]
    pp,yy,ss=sources[k];pp[b:d,a:c]|=p[:d-b,:c-a];yy[b:d,a:c]|=y[j].numpy()[:d-b,:c-a]>0;ss[b:d,a:c]|=s[j].numpy()[:d-b,:c-a]>0
  rows=collections.defaultdict(list)
  for (key,t),(p,y,s) in sources.items():
   if not s.any():continue
   p&=s;y&=s;negative=s&~y;i=int((p&y).sum());total=int((p|y).sum())
   rows[t].append(dict(sha256=key,Dice=2*i/max(1,int(p.sum()+y.sum())) if y.any() else None,IoU=i/max(1,total) if y.any() else None,positivePixels=int(y.sum()),negativePixels=int(negative.sum()),negativeFPR=float(p[negative].mean()) if negative.any() else None,wholeReviewedROI=roi_review[(key,t)],manualWholeSkinBoundaryReviewPending=roi_review[(key,t)] is not True,reviewOrigin='engineering'))
  return {t:dict(Dice=float(np.mean([r['Dice'] for r in rs if r['Dice'] is not None])) if any(r['Dice'] is not None for r in rs) else None,IoU=float(np.mean([r['IoU'] for r in rs if r['IoU'] is not None])) if any(r['IoU'] is not None for r in rs) else None,negativeFPR=float(np.mean([r['negativeFPR'] for r in rs if r['negativeFPR'] is not None])),positiveROIs=sum(r['positivePixels']>0 for r in rs),negativeROIs=sum(r['positivePixels']==0 for r in rs),wholeVisibleROI=True if all(r['wholeReviewedROI'] is True for r in rs) else None,rows=rs,scope='complete engineering reviewed visible anatomical ROI, development only') for t,rs in rows.items()}
 def save():
  state['seconds']=previous+time.monotonic()-started;state['scheduler']=sched.state_dict();checkpoint(folder,net,opt,state)
 if (folder/'CURRENT').exists():
  generation=folder/(folder/'CURRENT').read_text('utf8');saved=json.loads((generation/'state.json').read_text('utf8'));migration=saved['identity']!=identity
  if migration:
   assert refined_support and archived.exists() and saved['epoch']==0,'UNAUTHORIZED_SUPPORT_MIGRATION'
   oldprotocol=json.loads(archived.read_text('utf8'));assert oldprotocol=={**protocol,'dataSHA256':data['parentLedgerSHA256']} and saved['identity']==sha(archived)
   olddata=json.loads((OUT/'continuation-mask-data.json').read_text('utf8'));assert len(olddata['rows'])==len(data['rows'])
   for old,new in zip(olddata['rows'],data['rows']):
    assert all(old[k]==new[k] for k in ['id','sha256','group','split','rect','target','sourceNativeSize'])
   import shutil
   pinned=folder/'frozen-support-parent'/generation.name;pinned.mkdir(parents=True,exist_ok=True)
   for name in ['model.safetensors','optimizer.safetensors','state.json']:shutil.copy2(generation/name,pinned/name)
  state=resume(folder,net,opt,sha(archived) if migration else identity);sched.load_state_dict(state['scheduler']);previous=state['seconds']
  if migration:
   write(folder_name+'/support-migration.json',dict(parentIdentity=state['identity'],identity=identity,oldCursor=state['cursor'],oldStep=state['step'],oldOrder=state['order'],oldDataSHA256=data['parentLedgerSHA256'],newDataSHA256=sha(ledger),weightsOptimizerSchedulerRNGPreserved=True,stableTensorRowsAndSourceCoordinates=True,negativeLabelsAdded=0,unknownSupportExcluded=True,partialEpochSelectionInvalidated=False,remainingMinimumEpochs=12))
   state['identity']=identity;save()
 else:
  assert parent_checkpoint, 'FROZEN_PARENT_CHECKPOINT_REQUIRED'
  parent=OUT/('mask-continuation' if negative_phase else 'mask');generation=parent/parent_checkpoint
  assert generation.resolve().parent==parent.resolve() and generation.is_dir()
  parent_state=json.loads((generation/'state.json').read_text('utf8'))
  assert parent_state['cursor']==0 and not parent_state['order'], 'PARENT_EPOCH_BOUNDARY_REQUIRED'
  # Use a pinned copy so later parent retention cannot delete a resume source.
  import shutil
  frozen=folder/'frozen-parent';frozen.mkdir(exist_ok=True)
  dest=frozen/parent_checkpoint;dest.mkdir(exist_ok=True)
  for name in ['model.safetensors','optimizer.safetensors','state.json']:
   if not (dest/name).exists():
    if negative_phase:(dest/name).hardlink_to(generation/name)
    else:shutil.copy2(generation/name,dest/name)
  (frozen/'CURRENT').write_text(parent_checkpoint,'utf8')
  inherited=resume(frozen,net,opt,parent_state['identity']);sched.load_state_dict(inherited['scheduler'])
  write(folder_name+'/parent-receipt.json',dict(checkpoint=parent_checkpoint,modelSHA256=inherited['modelSHA256'],optimizerSHA256=inherited['optimizerSHA256'],protocolSHA256=inherited['identity'],validatedEpochs=inherited['epoch'],globalStep=inherited['step'],parentHistory=inherited['history'],optimizerSchedulerRNGPreserved=True,newPoolPhaseMinimumEpochs=12,noWeightReset=True,oldSelectionNotFinalFailure=True))
  state.update(step=inherited['step'],gradients=inherited['gradients']);previous=inherited['seconds']
  if negative_phase:
   save_file({k:net.state_dict()[k].contiguous() for k in proof},str(folder/'feature-initial.safetensors'));state['gradients']={}
  else:shutil.copy2(parent/'feature-initial.safetensors',folder/'feature-initial.safetensors')
  save()
 pos={t:[i for i,r in enumerate(tr) if r['target']==t and r['positivePixels']] for t in TARGETS};neg={t:[i for i,r in enumerate(tr) if r['target']==t and r['knownNegativePixels'] and r['completeROI']] for t in TARGETS}
 def next_negative(target):
  if not negative_phase:return random.choice(neg[target])
  groups=collections.defaultdict(list)
  for i in neg[target]:groups[tr[i]['group']].append(i)
  queue=state.setdefault('negativeGroupQueues',{}).setdefault(target,[])
  if not queue:queue.extend(random.sample(sorted(groups),len(groups)))
  group=queue.pop();key=target+':'+group;tiles=state.setdefault('negativeTileQueues',{}).setdefault(key,[])
  if not tiles:tiles.extend(random.sample(groups[group],len(groups[group])))
  return tiles.pop()
 write(folder_name+'/sampling.json',dict(positiveTiles={t:len(v) for t,v in pos.items()},knownNegativeTiles={t:len(v) for t,v in neg.items()},maximumPositiveGroupsPerTargetPerEpoch=128,cycleThroughEveryGroupAndNativeTileBeforeReshuffling=True,areaBalancedLoss=True,targetWeights={t:1 for t in TARGETS},selectionUsesDevelopmentOnly=True))
 resume_proof=dict(checkpoint=(folder/'CURRENT').read_text('utf8').strip(),epoch=state['epoch'],cursor=state['cursor'],step=state['step'],protocolSHA256=state['identity'],dataSHA256=protocol['dataSHA256'],modelSHA256=state.get('modelSHA256'),optimizerSHA256=state.get('optimizerSHA256'),optimizerSchedulerRNGPreserved=True) if negative_phase else None
 resume_proof_written=False
 while state['epoch']<(20 if negative_phase else 30) and (state['epoch']<12 or state['bad']<8 or until_epoch is not None and state['epoch']<until_epoch):
  start=time.monotonic();last=time.monotonic()
  if not state['order']:
   queues=state.setdefault('targetQueues',{});order=[]
   for t,v in pos.items():
    bygroup=collections.defaultdict(list)
    for i in v:bygroup[tr[i]['group']].append(i)
    groupkeys=sorted(bygroup)
    queues[t]=[g for g in queues.get(t,[]) if g in bygroup]
    if not queues.get(t):queues[t]=random.sample(groupkeys,len(groupkeys))
    chosen=[]
    # Do not repeat a source group within an epoch. Queue retains unreached groups.
    for _ in range(min(128,len(groupkeys))):
     if not queues[t]:queues[t]=random.sample([g for g in groupkeys if g not in chosen],len(groupkeys)-len(chosen))
     g=queues[t].pop();chosen.append(g)
     tiles=state.setdefault('groupTileQueues',{});key=t+':'+g
     tiles[key]=[i for i in tiles.get(key,[]) if i in bygroup[g]]
     if not tiles.get(key):tiles[key]=random.sample(bygroup[g],len(bygroup[g]))
     i=tiles[key].pop();order.append([i,next_negative(t) if neg[t] else i])
   random.shuffle(order)
   for t,v in neg.items():
    if not pos[t]:order.extend([[i,i] for i in v])
   state.update(order=order,cursor=0,losses=[])
  while state['cursor']<len(state['order']):
   storage_pause=checkpoint_storage_pause(folder) if negative_phase else None
   if storage_pause:
    save();write(folder_name+'/stop.json',dict(reason='RESUMABLE_DISK_RESERVE',trainingComplete=False,partialEpochPreserved=True,epoch=state['epoch'],cursor=state['cursor'],noCheckpointDeleted=True,**storage_pause));print('Saved resumable disk reserve',flush=True);return
   if time.monotonic()-started>=seconds:
    save();write(folder_name+'/stop.json',dict(reason='RESUMABLE_INVOCATION_TIME_SLICE',validatedEpochs=state['epoch'],partialEpochPreserved=True,trainingComplete=False));return
   ids=state['order'][state['cursor']];state['actualConsumedTileIDs']=sorted(set(state.get('actualConsumedTileIDs',[]))|set(ids));state['losses'].append(advance(ids));state['cursor']+=1;state['step']+=1
   if negative_phase and not resume_proof_written:
    write(folder_name+'/storage-resume-first-update.json',dict(**resume_proof,pid=__import__('os').getpid(),afterStep=state['step'],afterCursor=state['cursor'],actualFirstGradientUpdateCompleted=True));resume_proof_written=True
   if time.monotonic()-last>(1800 if negative_phase or until_epoch is not None else 60):save();last=time.monotonic();print('expanded mask',state['epoch']+1,state['cursor'],len(state['order']),flush=True)
  metrics=evaluate();available=[v['Dice']-v['negativeFPR'] for v in metrics.values() if v['Dice'] is not None];score=float(np.mean(available));state['epoch']+=1;elapsed=time.monotonic()-start;entry=dict(dataScopeVersion=protocol['version'],dataSHA256=protocol['dataSHA256'],phase=folder_name,epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=metrics,epochSeconds=elapsed);state['history'].append(entry)
  changed_targets=[]
  for t,m in metrics.items():
   value=(m['Dice'] if m['Dice'] is not None else 0)-m['negativeFPR']
   if value>state['targetBest'].get(t,{}).get('score',-2):
    state['targetBest'][t]=dict(epoch=state['epoch'],score=value,metrics=m);changed_targets.append(t)
    if not negative_phase:save_file(net.state_dict(),str(folder/f'best-{t}.safetensors'))
  if score>state['best']+1e-5:state['best']=score;state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'))
  else:state['bad']+=1
  sched.step();state.update(order=[],cursor=0);save()
  if negative_phase:
   # Every complete epoch checkpoint is retained. Criteria improving in the
   # same epoch share its immutable tensor files, rather than seven copies.
   receipt_path=folder/'target-best-checkpoints.json';receipts=json.loads(receipt_path.read_text('utf8')) if receipt_path.exists() else {}
   generation=(folder/'CURRENT').read_text('utf8');weights=folder/generation/'model.safetensors'
   for target in changed_targets:receipts[target]=dict(epoch=state['epoch'],checkpoint=generation,modelSHA256=sha(weights),weightsFile=generation+'/model.safetensors')
   write(folder_name+'/target-best-checkpoints.json',receipts)

  if until_epoch is not None and state['epoch']>=until_epoch:
   write(folder_name+'/phase-boundary.json',dict(reason='NATURAL_EPOCH_BOUNDARY_FOR_NEW_DATA_PHASE',trainingComplete=False,epoch=state['epoch'],cursor=0,weightsOptimizerSchedulerRNGPreserved=True));return
  write(folder_name+'/history.json',state['history']);write(folder_name+'/eta.json',dict(epochsCompleted=state['epoch'],measuredEpochSeconds=elapsed,remainingUpperBoundSeconds=elapsed*(protocol['maximumEpochs']-state['epoch']),CPUOnly=True,counts=data['counts']));print('expanded mask epoch',state['epoch'],score,'seconds',elapsed,flush=True)
 before=load_file(str(folder/'feature-initial.safetensors'));selected=load_file(str(folder/'selected.safetensors'));features={k:dict(maxAbs=float((selected[k]-before[k]).abs().max()),gradientMax=state['gradients'].get(k,0)) for k in proof};assert all(v['maxAbs']>0 and v['gradientMax']>0 for v in features.values())
 write(folder_name+'/selection.json',dict(trainingComplete=True,epochsCompleted=state['epoch'],perCriterionBest=state['targetBest'],perCriterionWeights=json.loads((folder/'target-best-checkpoints.json').read_text('utf8')) if negative_phase else None,features=features,weightsSHA256=sha(folder/'selected.safetensors'),stopReason='VALIDATION_PLATEAU' if state['epoch']<protocol['maximumEpochs'] else 'PLANNED_UPPER_BOUND',acceptanceDecisionRequired=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=14400);p.add_argument('--parent-checkpoint');p.add_argument('--refined-support',action='store_true');p.add_argument('--negative-phase',action='store_true');p.add_argument('--until-epoch',type=int);a=p.parse_args();main(a.seconds,a.parent_checkpoint,a.refined_support,a.negative_phase,a.until_epoch)
