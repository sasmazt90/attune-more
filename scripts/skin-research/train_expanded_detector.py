"""Resumable, native-detail YOLOX continuation on a frozen expanded source pool."""
import argparse,collections,json,random,time
import cv2,numpy as np,torch
from safetensors.torch import load_file,save_file
from expanded_sources import OUT,ROOT,PREVIOUS,write,sha
from expanded_detector_data import prepare
from train_focused_local import yolo_model,acne_tiles,yolo_batch,predict
from fast_detection_metrics import detection_metrics
from selected_yolox_loss import KnownObjectnessBCE,known_cells
from training_checkpoint import checkpoint,resume
from storage_guard import checkpoint_storage_pause
from yolox_numeric import install_bounds
from source_skin_support import known_skin_scope

def main(seconds, negative_phase=False, parent_checkpoint=None, until_epoch=None):
 torch.set_num_threads(2);cv2.setNumThreads(1);torch.manual_seed(20261011);random.seed(20261011);np.random.seed(20261011)
 folder_name='negative-yolox' if negative_phase else 'yolox'
 folder=OUT/folder_name;folder.mkdir(exist_ok=True)
 if (folder/'selection.json').exists():print('Completed expanded run preserved');return
 data=json.loads((OUT/'negative-expanded-detector-data.json').read_text('utf8')) if negative_phase else prepare();tr=[r for r in data['rows'] if r['split']=='train'];va=[r for r in data['rows'] if r['split']=='validation']
 scopes={};original_scopes={}
 for r in tr:
  scope=np.zeros((r['height'],r['width']),np.uint8)
  if r['negativeROI']:
   pts=np.array([[p['x']*r['width'],p['y']*r['height']] for p in r['landmarks'][:468]],np.float32)
   cv2.fillConvexPoly(scope,cv2.convexHull(np.rint(pts).astype(np.int32)),1)
  original_scopes[r['sha256']]=scope
  scopes[r['sha256']]=known_skin_scope(r,cv2.imread(r['absolutePath'])) if r['negativeROI'] else scope
  assert np.all(scopes[r['sha256']]<=scope)
 items=[t for t in acne_tiles(tr,training=False) if t['boxes'] or t['row']['negativeROI'] and known_cells(original_scopes[t['row']['sha256']],t['rect'],True).any()]
 for t in items:t['known']=known_cells(scopes[t['row']['sha256']],t['rect'],bool(t['row']['negativeROI']))
 native=[dict(sha256=t['row']['sha256'],rect=t['rect'],boxes=t['boxes'],boxSizes=[[b[2]-b[0],b[3]-b[1]] for b in t['boxes']],knownNegativeCells=int(t['known'].sum()),inputSize=384,noSourceUpsampling=True) for t in items]
 write(folder_name+'/tensor-overlap.json',dict(rows=native))
 protocol=dict(version='expanded-native-pimple-v1',dataSHA256=sha(OUT/('negative-expanded-detector-data.json' if negative_phase else 'detector-data.json')),maximumEpochs=32,minimumEpochs=12,patience=8,batch=2,threads=2,optimizer='AdamW',learningRate=.00015,weightDecay=.001,scheduler='cosine',unknownPixelsExcluded=True,sourceGroupsNotPersons=True,testOpened=False,naturalAcceptanceRequired=True,initialization='licensed general vs previous failed checkpoint; equal 60-step development comparison then reset')
 if negative_phase:
  (folder/'PRESERVE_ALL_CHECKPOINTS').touch(exist_ok=True)
  protocol.update(version='active-pimple-negative-photo-expansion-v1',maximumEpochs=20,parentDataSHA256=data['parentDataSHA256'],newNegativeReviewSHA256=data['negativeReviewSHA256'],phaseCurvesSeparate=True,checkpointSeconds=1800,negativeSourceGroupBalanced=True,initialization='exact inherited optimizer/scheduler/RNG checkpoint; no reset')
 old_protocol=json.loads((folder/'protocol.json').read_text('utf8')) if (folder/'protocol.json').exists() else None
 old_identity=sha(folder/'protocol.json') if old_protocol else None
 parent_protocol=folder/'numerical-parent-protocol.json'
 support_parent=folder/'support-parent-protocol.json'
 if old_protocol and 'numericalRegressionBounds' in old_protocol and 'pixelSupportExclusions' not in old_protocol and not support_parent.exists():
  import shutil
  shutil.copy2(folder/'protocol.json',support_parent)
 if old_protocol and 'numericalRegressionBounds' not in old_protocol and not parent_protocol.exists():
  write(folder_name+'/numerical-parent-protocol.json',old_protocol);assert sha(parent_protocol)==old_identity
 protocol['numericalRegressionBounds']=dict(version='native-exp-dimension-bounds-v1',minimumPixels=.1,maximumPixels=768)
 protocol['pixelSupportExclusions']='observed-face-oval-eye-lip-nostril-brow-long-filament-v1; same tile rows/order, new negative cells never added'
 write(folder_name+'/protocol.json',protocol);identity=sha(folder/'protocol.json');net=yolo_model();install_bounds(net)
 for k,p in net.named_parameters():p.requires_grad=not k.startswith(('backbone.backbone.stem','backbone.backbone.dark2'))
 obj=KnownObjectnessBCE();net.head.bcewithlog_loss=obj
 proof=['backbone.backbone.dark3.0.conv.weight','backbone.lateral_conv0.conv.weight','head.reg_convs.0.0.conv.weight']
 initial={k:v.clone() for k,v in net.state_dict().items()};before={k:initial[k].clone() for k in proof}
 opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=protocol['learningRate'],weight_decay=.001);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,protocol['maximumEpochs'])
 started=time.monotonic();prior=0.;state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,seconds=0.,gradients={},scheduler=sched.state_dict())
 def trainmode():
  net.train()
  for m in net.modules():
   if isinstance(m,torch.nn.BatchNorm2d):m.eval()
 def advance(batch):
  trainmode();opt.zero_grad();obj.known=torch.cat([t['known'] for t in batch]);x,y=yolo_batch(batch);value=net(x,y)['total_loss'];assert torch.isfinite(value);value.backward()
  for k,p in net.named_parameters():
   if k in proof and p.grad is not None:state['gradients'][k]=max(state['gradients'].get(k,0.),float(p.grad.abs().max()))
  norm=torch.nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step();return float(value.detach())
 def evaluate(rows):
  predictions=predict(net,'yolox',rows);choices=[detection_metrics(rows,predictions,t) for t in [.1,.25,.4,.55,.7]]
  return max(choices,key=lambda m:m['F1'])
 def save():
  state['seconds']=prior+time.monotonic()-started;state['scheduler']=sched.state_dict();checkpoint(folder,net,opt,state)
 if (folder/'CURRENT').exists():
  generation=folder/(folder/'CURRENT').read_text('utf8');saved=json.loads((generation/'state.json').read_text('utf8'))
  migration=saved['identity']!=identity
  support_migration=False
  if migration:
   support_migration=support_parent.exists() and saved['identity']==sha(support_parent)
   old_identity=sha(support_parent if support_migration else parent_protocol);parent=json.loads((support_parent if support_migration else parent_protocol).read_text('utf8'))
   expected={k:v for k,v in protocol.items() if k!='pixelSupportExclusions' and (support_migration or k!='numericalRegressionBounds')}
   assert saved['identity']==old_identity and parent==expected,'UNAUTHORIZED_PROTOCOL_DRIFT'
  state=resume(folder,net,opt,old_identity if migration else identity);prior=state['seconds'];sched.load_state_dict(state['scheduler'])
  if support_migration:
   import shutil
   pinned=folder/'frozen-support-parent'/generation.name;pinned.mkdir(parents=True,exist_ok=True)
   for name in ['model.safetensors','optimizer.safetensors','state.json']:shutil.copy2(generation/name,pinned/name)
   write(folder_name+'/support-migration.json',dict(parentIdentity=state['identity'],identity=identity,epoch=state['epoch'],cursor=state['cursor'],order=state['order'],modelSHA256=state['modelSHA256'],optimizerSHA256=state['optimizerSHA256'],optimizerSchedulerRNGAndSourceOrderPreserved=True,validationInputsAndInferenceUnchanged=True,negativeCellsAdded=0,removedNegativeCells=int(sum(known_cells(original_scopes[t['row']['sha256']],t['rect'],bool(t['row']['negativeROI'])).sum()-t['known'].sum() for t in items))))
   state['identity']=identity;save()
  elif migration:
   write(folder_name+'/numerical-prior-history.json',state['history']);current={k:v.clone() for k,v in net.state_dict().items()};selected=load_file(str(folder/'selected.safetensors'));net.load_state_dict(selected);metrics=evaluate(va);net.load_state_dict(current)
   winner=max(state['history'],key=lambda e:e['validation']['F1']);state.update(identity=identity,best=metrics['F1'],bad=0,history=[dict(epoch=winner['epoch'],validation=metrics,epochSeconds=0.,numericalCorrectionRevalidation=True)])
   write(folder_name+'/numerical-correction.json',dict(parentIdentity=old_identity,identity=identity,dataSHA256=protocol['dataSHA256'],epoch=state['epoch'],cursor=state['cursor'],optimizerPreserved=True,schedulerPreserved=True,RNGPreserved=True,sourceOrderPreserved=True,reason='Replayed source batch at cursor570: ExpBackward0 NaN, raw log dimensions137.129; bound decoded native size before exp in training and export',gradientFiniteChecksStillRequired=True));save()
 elif negative_phase:
  assert parent_checkpoint,'FROZEN_PARENT_CHECKPOINT_REQUIRED'
  import shutil
  parent=OUT/'yolox';generation=parent/parent_checkpoint;parent_state=json.loads((generation/'state.json').read_text('utf8'));assert parent_state['cursor']==0 and not parent_state['order'],'PARENT_EPOCH_BOUNDARY_REQUIRED'
  frozen=folder/'frozen-parent';frozen.mkdir(exist_ok=True);dest=frozen/generation.name;dest.mkdir(exist_ok=True)
  for name in ['model.safetensors','optimizer.safetensors','state.json']:
   if not (dest/name).exists():(dest/name).hardlink_to(generation/name)
  (frozen/'CURRENT').write_text(generation.name,'utf8');inherited=resume(frozen,net,opt,parent_state['identity']);sched.load_state_dict(inherited['scheduler']);prior=inherited['seconds'];state['step']=inherited['step']
  save_file({k:net.state_dict()[k].contiguous() for k in proof},str(folder/'feature-initial.safetensors'))
  write(folder_name+'/parent-receipt.json',dict(checkpoint=generation.name,modelSHA256=inherited['modelSHA256'],optimizerSHA256=inherited['optimizerSHA256'],parentHistory=inherited['history'],parentValidatedEpochs=inherited['epoch'],modelOptimizerSchedulerRNGPreserved=True,newDataPhaseCountersStartAtZero=True,noWeightReset=True));save()
 else:
  tiny=([t for t in items if t['boxes']][:8]+[t for t in items if not t['boxes']][:4]);diagnostic=va[:8];comparison=[]
  existing=folder/'initialization-comparison.json'
  if existing.exists():comparison=json.loads(existing.read_text('utf8'))['rows']
  for name in ([] if comparison else ['licensed-general','previous-failed-warm']):
   warm=PREVIOUS/'yolox/selected.safetensors';net.load_state_dict(initial if name=='licensed-general' else load_file(str(warm)))
   opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=protocol['learningRate'],weight_decay=.001);losses=[]
   for step in range(60):losses.append(advance([tiny[(step*2)%len(tiny)],tiny[(step*2+1)%len(tiny)]]))
   m=evaluate(diagnostic);comparison.append(dict(initialization=name,trainImages=len({t['row']['sha256'] for t in tiny}),steps=60,firstLoss=float(np.mean(losses[:6])),lastLoss=float(np.mean(losses[-6:])),development=m))
   print('initialization comparison',name,m['F1'],flush=True)
  write(folder_name+'/initialization-comparison.json',dict(rows=comparison,independentTest=False,resetAfterComparison=True))
  winner=max(comparison,key=lambda r:r['development']['F1']);startweights=initial if winner['initialization']=='licensed-general' else load_file(str(PREVIOUS/'yolox/selected.safetensors'))
  net.load_state_dict(startweights);before={k:startweights[k].clone() for k in proof};save_file({k:v.contiguous() for k,v in before.items()},str(folder/'feature-initial.safetensors'))
  # A small train-only overfit check is reset before the expanded run.
  tiny=tiny[:2];opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.00015,weight_decay=.001);losses=[]
  for step in range(160):
   losses.append(advance(tiny))
   if step%20==19:print('train-only native learning',step+1,losses[-1],flush=True)
  passed=float(np.mean(losses[-8:]))<float(np.mean(losses[:8]))*.5
  write(folder_name+'/learning.json',dict(passed=passed,firstLoss=float(np.mean(losses[:8])),lastLoss=float(np.mean(losses[-8:])),steps=len(losses),trainOnly=True,resetBeforeExpandedTraining=True,initialization=winner['initialization'],learningRate=.00015,nonFiniteGradientsRejected=True))
  assert passed,'REAL_NATIVE_LEARNING_CHAIN_FAILED'
  net.load_state_dict(startweights);opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=protocol['learningRate'],weight_decay=.001);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,protocol['maximumEpochs']);state['gradients']={};save()
 before=load_file(str(folder/'feature-initial.safetensors'))
 resume_proof=dict(checkpoint=(folder/'CURRENT').read_text('utf8').strip(),epoch=state['epoch'],cursor=state['cursor'],step=state['step'],protocolSHA256=state['identity'],dataSHA256=protocol['dataSHA256'],modelSHA256=state.get('modelSHA256'),optimizerSHA256=state.get('optimizerSHA256'),optimizerSchedulerRNGPreserved=True) if negative_phase else None
 resume_proof_written=False
 while state['epoch']<protocol['maximumEpochs'] and (state['epoch']<protocol['minimumEpochs'] or state['bad']<protocol['patience'] or until_epoch is not None and state['epoch']<until_epoch):
  epochstart=time.monotonic();lastsave=time.monotonic()
  if not state['order']:
   # Repeat negative tiles to contribute in ~1/3 of steps; unknown lesion
   # tiles never become negative. Order is persisted for exact resume.
   pos=[i for i,t in enumerate(items) if t['boxes']];neg=[i for i,t in enumerate(items) if not t['boxes']]
   if negative_phase:
    bygroup=collections.defaultdict(list)
    for i in neg:bygroup[items[i]['row']['group']].append(i)
    negatives=[];queue=state.setdefault('negativeGroupQueue',[])
    for _ in range(max(len(neg),len(pos)//2)):
     if not queue:queue.extend(random.sample(sorted(bygroup),len(bygroup)))
     group=queue.pop();negatives.append(random.choice(bygroup[group]))
   else:negatives=random.choices(neg,k=max(len(neg),len(pos)//2))
   order=pos+negatives;random.shuffle(order);state.update(order=order,cursor=0,losses=[])
  while state['cursor']<len(state['order']):
   storage_pause=checkpoint_storage_pause(folder) if negative_phase else None
   if storage_pause:
    save();write(folder_name+'/stop.json',dict(reason='RESUMABLE_DISK_RESERVE',trainingComplete=False,partialEpochPreserved=True,epoch=state['epoch'],cursor=state['cursor'],noCheckpointDeleted=True,**storage_pause));print('Saved resumable disk reserve',flush=True);return
   if time.monotonic()-started>=seconds:
    save();write(folder_name+'/stop.json',dict(reason='RESUMABLE_INVOCATION_TIME_SLICE',validatedEpochs=state['epoch'],partialEpochPreserved=True,trainingComplete=False,totalSeconds=state['seconds']));print('Saved resumable slice',state['epoch'],state['cursor'],flush=True);return
   ids=state['order'][state['cursor']:state['cursor']+2];state['actualConsumedTileIDs']=sorted(set(state.get('actualConsumedTileIDs',[]))|set(ids));state['losses'].append(advance([items[i] for i in ids]));state['cursor']+=len(ids);state['step']+=1
   if negative_phase and not resume_proof_written:
    write(folder_name+'/storage-resume-first-update.json',dict(**resume_proof,pid=__import__('os').getpid(),afterStep=state['step'],afterCursor=state['cursor'],actualFirstGradientUpdateCompleted=True));resume_proof_written=True
   if time.monotonic()-lastsave>(1800 if negative_phase or until_epoch is not None else 60):save();lastsave=time.monotonic();print('expanded YOLOX',state['epoch']+1,state['cursor'],len(state['order']),flush=True)
  metrics=evaluate(va);state['epoch']+=1;elapsed=time.monotonic()-epochstart;entry=dict(dataScopeVersion=protocol['version'],dataSHA256=protocol['dataSHA256'],phase=folder_name,epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=metrics,epochSeconds=elapsed,totalSeconds=prior+time.monotonic()-started);state['history'].append(entry)
  if metrics['F1']>state['best']+1e-5:state['best']=metrics['F1'];state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'))
  else:state['bad']+=1
  sched.step();state.update(order=[],cursor=0);save();
  if until_epoch is not None and state['epoch']>=until_epoch:
   write(folder_name+'/phase-boundary.json',dict(reason='NATURAL_EPOCH_BOUNDARY_FOR_NEW_DATA_PHASE',trainingComplete=False,epoch=state['epoch'],cursor=0,weightsOptimizerSchedulerRNGPreserved=True));return
  write(folder_name+'/history.json',state['history']);write(folder_name+'/eta.json',dict(epochsCompleted=state['epoch'],measuredEpochSeconds=elapsed,remainingUpperBoundSeconds=elapsed*(protocol['maximumEpochs']-state['epoch']),CPUOnly=not torch.cuda.is_available(),sourceCounts=data['counts'],trainingTiles=len(items),validationIsDevelopment=True));print('expanded YOLOX epoch',state['epoch'],'F1',metrics['F1'],'seconds',elapsed,flush=True)
 winner=max(state['history'],key=lambda e:e['validation']['F1']);selected=load_file(str(folder/'selected.safetensors'));feature={k:dict(maxAbs=float((selected[k]-before[k]).abs().max()),gradientMax=state['gradients'].get(k,0.)) for k in proof};assert all(v['maxAbs']>0 and v['gradientMax']>0 for v in feature.values())
 write(folder_name+'/selection.json',dict(trainingComplete=True,selectedEpoch=winner['epoch'],validation=winner['validation'],featureEvidence=feature,weightsSHA256=sha(folder/'selected.safetensors'),epochsCompleted=state['epoch'],stopReason='VALIDATION_PLATEAU' if state['epoch']<protocol['maximumEpochs'] else 'PLANNED_UPPER_BOUND',acceptanceDecisionRequired=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=3600);p.add_argument('--negative-phase',action='store_true');p.add_argument('--parent-checkpoint');p.add_argument('--until-epoch',type=int);a=p.parse_args();main(a.seconds,a.negative_phase,a.parent_checkpoint,a.until_epoch)
