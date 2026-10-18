"""Bounded versioned continuation of an exact paused native checkpoint.

No fresh initialization, original phase mutation, holdout access or promotion.
The inherited unfinished order/cursor is completed before any new sampling.
"""
import argparse,collections,copy,json,os,random,shutil,time
from pathlib import Path
import cv2,numpy as np,psutil,torch
from expanded_sources import OUT,ROOT,sha,write
from training_checkpoint import checkpoint,resume
from storage_guard import checkpoint_storage_pause
from selected_sources import TARGETS
from prepare_continuation_masks import TARGETS as DATA_TARGETS
from selected_mask_model import SkinUNet,masked_loss
from mask_scope_metrics import SourceScopes,RULE,global_score
from train_focused_local import yolo_model,acne_tiles,yolo_batch,predict
from selected_yolox_loss import KnownObjectnessBCE,known_cells
from source_skin_support import known_skin_scope
from yolox_numeric import install_bounds
from fast_detection_metrics import detection_metrics

MEAN=torch.tensor([.485,.456,.406])[:,None,None]
STD=torch.tensor([.229,.224,.225])[:,None,None]
PHASE={'mask':'corrected-scope-mask-v4','yolox':'corrected-scope-yolox-v2'}
OLD={'mask':'negative-mask-continuation','yolox':'negative-yolox'}

def read(p):return json.loads(p.read_text('utf8'))

def scheduler_step(scheduler):
 """Preserve inherited cosine state, stop at its original minimum."""
 if scheduler.last_epoch<scheduler.T_max:scheduler.step()
 # Never step through the upward half of an inherited cosine cycle.
 return scheduler.last_epoch

def own(kind):
 for p in psutil.process_iter(['pid','cmdline','cwd']):
  args=p.info['cmdline'] or [];cmd=' '.join(args)
  if p.pid==os.getpid() or not args or Path(args[0]).name.lower() not in ['python.exe','pythonw.exe','python3.exe'] or Path(p.info['cwd'] or '.').resolve()!=ROOT:continue
  if ('train_corrected_scope.py' in cmd and '--kind' in args and args[args.index('--kind')+1]==kind) or (('train_continuation_mask.py' if kind=='mask' else 'train_expanded_detector.py') in cmd):raise RuntimeError('EXISTING_OWNED_TRAINER')

def main(kind,seconds=14400):
 own(kind);torch.set_num_threads(1 if kind=='mask' else 2);cv2.setNumThreads(1)
 folder=OUT/PHASE[kind];folder.mkdir(exist_ok=True);original=OUT/OLD[kind]
 if (folder/'selection.json').exists():print('CORRECTED PHASE COMPLETE',kind,flush=True);return
 ledger=OUT/('scope-v4-mask-data.json' if kind=='mask' else 'negative-expanded-detector-data.json');data=read(ledger)
 oldgen=(original/'CURRENT').read_text('utf8').strip();parent=original/oldgen;parent_state=read(parent/'state.json')
 assert (original/'STORAGE_PAUSE').exists(),'ORIGINAL_PHASE_MUST_REMAIN_PAUSED'
 if kind=='mask':
  prior=read(OUT/'negative-expanded-mask-data.json')
  assert len(data['rows'])>=len(prior['rows'])
  for a,b in zip(prior['rows'],data['rows']):assert all(a[k]==b[k] for k in ['id','sha256','group','split','target','rect','sourceNativeSize'])
  tr=[r for r in data['rows'] if r['split']=='train'];va=[r for r in data['rows'] if r['split']=='validation' and r['target'] in TARGETS]
  net=SkinUNet()
  for k,p in net.encoder.named_parameters():p.requires_grad_(not k.startswith(('conv1.','bn1.','layer1.','layer2.')))
  opt=torch.optim.AdamW(net.parameters(),lr=.0001,weight_decay=.001)
  def tensors(r):
   with np.load(OUT/data['tensorFolder']/r['id']) as f:return (torch.from_numpy(f['rgb'].copy().transpose(2,0,1)).float()/255-MEAN)/STD,torch.from_numpy(f['truth'][[DATA_TARGETS.index(t) for t in TARGETS]].copy()).float(),torch.from_numpy(f['support'][[DATA_TARGETS.index(t) for t in TARGETS]].copy()).float()
  def advance(ids):
   values=[tensors(tr[i]) for i in ids];x,y,s=[torch.stack([v[j] for v in values]) for j in range(3)]
   if not bool(s.any()):return None
   logits=net(x);loss=masked_loss(logits,y,s,balanced=True)
   return loss
  def evaluate():
   scopes=SourceScopes()
   with torch.inference_mode():
    for r in va:
     x,y,s=tensors(r);j=TARGETS.index(r['target']);scopes.add(r,net(x[None]).sigmoid()[0,j].numpy()>=.5,y[j].numpy(),s[j].numpy())
   metrics=scopes.finish(TARGETS);return metrics,global_score(metrics,TARGETS)
  def order():
   result=[]
   for t in TARGETS:
    positives=collections.defaultdict(list);negatives=collections.defaultdict(list)
    for i,r in enumerate(tr):
     if r['target']!=t:continue
     if r['positivePixels']:positives[r['group']].append(i)
     elif r['knownNegativePixels'] and r.get('engineeringNegativeROIReviewed') is True:negatives[r['group']].append(i)
    queues=state.setdefault('targetQueues',{});queues[t]=[g for g in queues.get(t,[]) if g in positives];chosen=[]
    for _ in range(min(128,len(positives))):
     if not queues[t]:queues[t]=random.sample([g for g in sorted(positives) if g not in chosen],len(positives)-len(chosen))
     g=queues[t].pop();chosen.append(g);key=t+':'+g;tiles=state.setdefault('groupTileQueues',{});tiles[key]=[i for i in tiles.get(key,[]) if i in positives[g]]
     if not tiles[key]:tiles[key]=random.sample(positives[g],len(positives[g]))
     i=tiles[key].pop()
     q=state.setdefault('negativeGroupQueues',{});q[t]=[g for g in q.get(t,[]) if g in negatives]
     if negatives:
      if not q[t]:q[t]=random.sample(sorted(negatives),len(negatives))
      ng=q[t].pop();nk=t+':'+ng;nt=state.setdefault('negativeTileQueues',{});nt[nk]=[i for i in nt.get(nk,[]) if i in negatives[ng]]
      if not nt[nk]:nt[nk]=random.sample(negatives[ng],len(negatives[ng]))
      result.append([i,nt[nk].pop()])
     else:result.append([i,i])
   random.shuffle(result);return result
 else:
  tr=[r for r in data['rows'] if r['split']=='train'];va=[r for r in data['rows'] if r['split']=='validation'];items=[]
  for t in acne_tiles(tr,training=False):
   r=t['row'];scope=np.zeros((r['height'],r['width']),np.uint8)
   if r['negativeROI']:
    pts=np.array([[p['x']*r['width'],p['y']*r['height']] for p in r['landmarks'][:468]],np.float32);cv2.fillConvexPoly(scope,cv2.convexHull(np.rint(pts).astype(np.int32)),1)
   if t['boxes'] or r['negativeROI'] and known_cells(scope,t['rect'],True).any():
    t['known']=known_cells(known_skin_scope(r,cv2.imread(r['absolutePath'])) if r['negativeROI'] else scope,t['rect'],bool(r['negativeROI']));items.append(t)
  olditems=read(original/'tensor-overlap.json')['rows'];assert len(items)==len(olditems)
  for t,r in zip(items,olditems):assert list(t['rect'])==r['rect'] and t['row']['sha256']==r['sha256'] and np.array_equal(t['boxes'],r['boxes']),'NATIVE_ITEM_ORDER_CHANGED'
  net=yolo_model();install_bounds(net)
  for k,p in net.named_parameters():p.requires_grad_(not k.startswith(('backbone.backbone.stem','backbone.backbone.dark2')))
  obj=KnownObjectnessBCE();net.head.bcewithlog_loss=obj;opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.00015,weight_decay=.001)
  def advance(ids):
   batch=[items[i] for i in ids];obj.known=torch.cat([t['known'] for t in batch]);x,y=yolo_batch(batch);return net(x,y)['total_loss']
  def evaluate():
   metrics=detection_metrics(va,predict(net,'yolox',va),.7);return metrics,metrics['F1']
  def order():
   pos=[i for i,t in enumerate(items) if t['boxes']];neg=collections.defaultdict(list)
   for i,t in enumerate(items):
    if not t['boxes']:neg[t['row']['group']].append(i)
   queue=state.setdefault('negativeGroupQueue',[]);queue[:]=[g for g in queue if g in neg];extra=[]
   for _ in range(max(sum(map(len,neg.values())),len(pos)//2)):
    if not queue:queue.extend(random.sample(sorted(neg),len(neg)))
    extra.append(random.choice(neg[queue.pop()]))
   result=pos+extra;random.shuffle(result);return result
 protocol=dict(version=PHASE[kind],kind=kind,parentPhase=OLD[kind],parentCheckpoint=oldgen,parentProtocolSHA256=parent_state['identity'],dataSHA256=sha(ledger),maximumNewValidations=2,finishInheritedCursorFirst=True,optimizerSchedulerRNGOrderPreserved=True,curvesSeparate=True,minimumOld12EpochRuleInvalidated=True,acceptanceThresholdsChanged=False,finalOpened=False,scheduler='inherited cosine clamped at original T_max; no upward rebound',loss='original balanced masked loss' if kind=='mask' else 'shape fail-closed known objectness BCE',selection=RULE if kind=='mask' else dict(threshold=.7,matchingIoU=.5,score='annotation-relative source development F1; unmatched is not expert false diagnosis'),codeSHA256=sha(Path(__file__)),learningSuccessRequiresDevelopmentEvidence=True)
 protocol['consumedCodeSHA256']={name:sha(Path(__file__).parent/name) for name in ['selected_mask_model.py','selected_yolox_loss.py','mask_scope_metrics.py','training_checkpoint.py','source_skin_support.py','yolox_numeric.py','train_focused_local.py','fast_detection_metrics.py','storage_guard.py']}
 pp=folder/'protocol.json'
 if pp.exists():assert read(pp)==protocol,'FROZEN_CORRECTED_PROTOCOL_CHANGED'
 else:write(PHASE[kind]+'/protocol.json',protocol)
 identity=sha(pp);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32);started=time.monotonic()
 if (folder/'CURRENT').exists():state=resume(folder,net,opt,identity)
 else:
  frozen=folder/'frozen-parent';frozen.mkdir(exist_ok=True);dest=frozen/oldgen;dest.mkdir(exist_ok=True)
  for name in ['model.safetensors','optimizer.safetensors','state.json']:
   if not (dest/name).exists():os.link(parent/name,dest/name)
  (frozen/'CURRENT').write_text(oldgen,'utf8');state=resume(frozen,net,opt,parent_state['identity'])
  inherited=dict(epoch=state['epoch'],cursor=state['cursor'],order=copy.deepcopy(state['order']),step=state['step'],scheduler=state['scheduler'],modelSHA256=state['modelSHA256'],optimizerSHA256=state['optimizerSHA256'])
  write(PHASE[kind]+'/transition.json',dict(parentCheckpoint=oldgen,parentProtocolSHA256=state['identity'],identity=identity,inherited=inherited,originalHistoryPreservedInFrozenState=True,modelOptimizerRNGLoadedExactly=True,originalParentUnchanged=True,newLossComparisonSelectionNotInstalled=True))
  state.update(identity=identity,phaseEpochs=0,history=[],phaseLosses=[],targetBest={},best=None,bad=0,phaseOriginalPartialCursor=state['cursor'])
  state=checkpoint(folder,net,opt,state)
 sched.load_state_dict(state['scheduler']);last_save=time.monotonic();first=False;prior_elapsed=state.get('phaseElapsedSeconds',0)
 def save():
  state['scheduler']=sched.state_dict();state['phaseElapsedSeconds']=prior_elapsed+time.monotonic()-started;checkpoint(folder,net,opt,state)
 while state['phaseEpochs']<2:
  if not state['order']:state.update(order=order(),cursor=0,phaseLosses=[])
  while state['cursor']<len(state['order']):
   pause=checkpoint_storage_pause(folder)
   if pause or time.monotonic()-started>=seconds:
    save();write(PHASE[kind]+'/stop.json',dict(reason='SAFE_RESOURCE_PAUSE' if pause else 'RESUMABLE_TIME_SLICE',phaseEpochs=state['phaseEpochs'],epoch=state['epoch'],cursor=state['cursor'],trainingComplete=False,resource=pause));return
   net.train()
   for m in net.modules():
    if isinstance(m,torch.nn.BatchNorm2d):m.eval()
   ids=state['order'][state['cursor']] if kind=='mask' else state['order'][state['cursor']:state['cursor']+2];opt.zero_grad();loss=advance(ids)
   if loss is not None:
    assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step();state['step']+=1;state['phaseLosses'].append(float(loss.detach()))
   else:state['allUnknownUpdatesSkipped']=state.get('allUnknownUpdatesSkipped',0)+1
   state['actualConsumedTileIDs']=sorted(set(state.get('actualConsumedTileIDs',[]))|set(ids));state['cursor']+=1 if kind=='mask' else len(ids)
   if not first and loss is not None:
    write(PHASE[kind]+'/first-update.json',dict(pid=os.getpid(),parentCheckpoint=oldgen,fromEpoch=parent_state['epoch'],fromCursor=parent_state['cursor'],afterCursor=state['cursor'],afterStep=state['step'],actualGradientUpdate=True,weightsNotReset=True,optimizerSchedulerRNGOrderPreserved=True,protocolSHA256=identity));first=True
   if time.monotonic()-last_save>=1800:save();last_save=time.monotonic()
  net.eval();metrics,score=evaluate();state['epoch']+=1;state['phaseEpochs']+=1;scheduler_step(sched);state.update(order=[],cursor=0)
  entry=dict(phase=PHASE[kind],phaseEpoch=state['phaseEpochs'],inheritedEpoch=state['epoch'],validation=metrics,developmentScore=score,onlyNewPhaseLoss=float(np.mean(state['phaseLosses'])) if state['phaseLosses'] else None);state['history'].append(entry);save();generation=(folder/'CURRENT').read_text('utf8');refs=read(folder/'target-best-checkpoints.json') if (folder/'target-best-checkpoints.json').exists() else {}
  if kind=='mask':
   for t,m in metrics.items():
    if m['rankingUsable'] and (t not in refs or m['developmentScore']>refs[t]['score']):refs[t]=dict(checkpoint=generation,modelSHA256=sha(folder/generation/'model.safetensors'),channel=TARGETS.index(t),score=m['developmentScore'],metrics=m,weightsMixed=False)
  elif score is not None and (not refs or score>refs['acne']['score']):refs['acne']=dict(checkpoint=generation,modelSHA256=sha(folder/generation/'model.safetensors'),score=score,metrics=metrics)
  write(PHASE[kind]+'/target-best-checkpoints.json',refs);write(PHASE[kind]+'/history.json',state['history']);print('CORRECTED VALIDATION',kind,state['phaseEpochs'],score,flush=True)
 write(PHASE[kind]+'/selection.json',dict(trainingComplete=True,stopReason='FINITE_TWO_VALIDATION_BOUND_REQUIRES_REVIEW',perTargetFullModels=refs,phaseEpochs=state['phaseEpochs'],acceptanceDecisionRequired=True,productionInstalled=False,finalOpened=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=list(PHASE),required=True);p.add_argument('--seconds',type=int,default=14400);a=p.parse_args();main(a.kind,a.seconds)
