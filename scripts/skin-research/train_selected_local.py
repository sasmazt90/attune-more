"""Finite joint-mask / YOLOX-S real-feature experiments on reviewed new photos.

Engineering ROI labels are not expert labels or an independent acceptance set.
No predictor-generated truth. All unknown targets/areas are masked from loss.
"""
import argparse, collections, json, random, time
import sys
import cv2, numpy as np, torch
from safetensors.torch import load_file,save_file
from selected_sources import OUT,ROOT,MAP,TARGETS,write,sha
from review_selected_sources import annotation_mask
from selected_mask_model import SkinUNet,masked_loss
from training_checkpoint import checkpoint,resume
sys.path.insert(0,str(ROOT/'services/core-api'))
from skin_mask_transform import mask_input,restore_mask

MEAN=np.array([.485,.456,.406],np.float32)[:,None,None]
STD=np.array([.229,.224,.225],np.float32)[:,None,None]

def reviewed():
 candidates=json.loads((OUT/'review/candidates.json').read_text('utf8'))
 assert candidates['manifestSHA256']==sha(OUT/'manifest.json')
 decisions=json.loads((OUT/'review/decisions.json').read_text('utf8'));by={d['sha256']:d for d in decisions['rows']}
 rows=[]
 for r in candidates['rows']:
  d=by.get(r['sha256'])
  if d and d.get('naturalEligible') and d.get('rightsEligible'):
   rows.append({**r,'reviewDecision':d})
 assert all(r['split']!='test' for r in rows)
 return rows

def mask_tensor(r):
 a,b,c,d=r['crop'];x,transform=mask_input(cv2.imread(r['absolutePath']),r['crop']);size=transform['inputSize'];nw,nh=transform['size'];ox,oy=transform['padding']
 y=np.zeros((len(TARGETS),size,size),np.float32);support=np.zeros_like(y)
 for j,t in enumerate(TARGETS):
  scope=target_scope(r,t)[b:d,a:c];mask=annotation_mask(r,t)[b:d,a:c]*scope;m=cv2.resize(mask,(nw,nh),interpolation=cv2.INTER_NEAREST);roi=cv2.resize(scope,(nw,nh),interpolation=cv2.INTER_NEAREST)
  y[j,oy:oy+nh,ox:ox+nw]=m
  if t in r['reviewDecision'].get('completeMaskTargets',[]):support[j,oy:oy+nh,ox:ox+nw]=roi
  else:support[j,oy:oy+nh,ox:ox+nw]=m  # positives only; unknown stays outside loss.
 return torch.from_numpy(x[0].copy()),torch.from_numpy(y),torch.from_numpy(support),transform

def target_scope(r,target):
 """Entire applicable anatomical ROI; no annotation-boundary-only evaluation."""
 sys_path=str(ROOT/'services/core-api')
 import sys
 if sys_path not in sys.path:sys.path.insert(0,sys_path)
 from skin_models import eye_rois
 from appearance_analysis import eye_skin_bands
 h,w=r['height'],r['width'];scope=np.zeros((h,w),np.uint8)
 if target in ['bags','dark']:
  for roi in eye_rois(r['landmarks'],w,h):
   a,b,c,d=roi['rect'];scope[b:d,a:c]=1
 elif target=='lines':scope=eye_skin_bands(r['landmarks'],(h,w),1,(0,0),(h,w))['lines'].astype(np.uint8)
 else:
  p=np.array([[v['x']*w,v['y']*h] for v in r['landmarks'][:468]],np.float32);cv2.fillConvexPoly(scope,cv2.convexHull(np.rint(p).astype(np.int32)),1)
 return scope

def mask_metrics(net,rows,threshold=.5):
 by=collections.defaultdict(list);net.eval()
 with torch.inference_mode():
  for r in rows:
   x,y,s,transform=mask_tensor(r);prediction=net(x[None]).sigmoid()[0].numpy();p=restore_mask(prediction,transform)>=threshold
   for j,t in enumerate(TARGETS):
    if t not in r['reviewDecision'].get('completeMaskTargets',[]):continue
    a,b,c,d=r['crop'];sup=target_scope(r,t)[b:d,a:c].astype(bool);yy=annotation_mask(r,t)[b:d,a:c].astype(bool)&sup;pp=p[j]&sup;i=int((pp&yy).sum());u=int((pp|yy).sum());neg=sup&~yy
    by[t].append(dict(sha256=r['sha256'],positivePixels=int(yy.sum()),Dice=2*i/max(1,int(pp.sum()+yy.sum())) if yy.any() else None,IoU=i/max(1,u) if yy.any() else None,negativePixels=int(neg.sum()),negativeFPR=float(pp[neg].mean()) if neg.any() else None,scope='entire engineering-reviewed visible source ROI; padding excluded'))
 return {t:dict(ROIs=len(v),positiveROIs=sum(r['positivePixels']>0 for r in v),Dice=float(np.mean([r['Dice'] for r in v if r['Dice'] is not None])) if any(r['Dice'] is not None for r in v) else None,IoU=float(np.mean([r['IoU'] for r in v if r['IoU'] is not None])) if any(r['IoU'] is not None for r in v) else None,negativeFPR=(float(np.mean([r['negativeFPR'] for r in v if r['negativeFPR'] is not None])) if any(r['negativeFPR'] is not None for r in v) else None),rows=v) for t,v in by.items()}

def main(task):
 torch.set_num_threads(2);cv2.setNumThreads(1);random.seed(20261011);torch.manual_seed(20261011);np.random.seed(20261011)
 folder=OUT/task;folder.mkdir(exist_ok=True);assert not (folder/'selection.json').exists(),'Completed run preserved'
 rows=reviewed();tr=[r for r in rows if r['split']=='train'];va=[r for r in rows if r['split']=='validation']
 if task=='mask':
  tr=[r for r in tr if r['reviewDecision'].get('completeMaskTargets') or any(a['validMask'] and MAP.get(r['source'],{}).get(a['label']) for a in r['annotations'])];va=[r for r in va if r['reviewDecision'].get('completeMaskTargets')]
  net=SkinUNet();proof_names=['encoder.layer4.0.conv1.weight','d4.0.weight','head.weight'];items=tr
  cache={r['sha256']:mask_tensor(r) for r in tr}
  items=[r for r in tr if bool(cache[r['sha256']][2].any())]
  def loss(batch):
   tensors=[cache[r['sha256']] for r in batch];x,y,s=[torch.stack([v[j] for v in tensors]) for j in range(3)];return masked_loss(net(x),y,s)
  def evaluate():return mask_metrics(net,va)
  def quality(m):return float(np.mean([v['Dice'] for v in m.values() if v['Dice'] is not None])) if any(v['Dice'] is not None for v in m.values()) else -1.
  batchsize=4;maximum_epochs=8;budget=1500
 else:
  from train_focused_local import yolo_model,acne_tiles,yolo_batch,predict
  from fast_detection_metrics import detection_metrics
  from selected_yolox_loss import KnownObjectnessBCE,known_cells
  def adapt(r):
   anns=[]
   for a in r['annotations']:
    if a['label']=='Pimple' and a['validBox']:
     x,y,w,h=a['bbox'];anns.append(dict(classId=0,box=[x,y,x+w,y+h],kind='box'))
   return {**r,'annotations':anns}
  tr=[adapt(r) for r in tr if r['reviewDecision'].get('pimpleBoxesReviewed')];va=[adapt(r) for r in va if r['reviewDecision'].get('pimpleBoxesReviewed')]
  net=yolo_model();warm=ROOT/'audit-results/skin-followup-20261011/yolox/selected.safetensors'
  if warm.exists():net.load_state_dict(load_file(str(warm)))
  for k,p in net.named_parameters():p.requires_grad=not k.startswith(('backbone.backbone.stem','backbone.backbone.dark2','backbone.backbone.dark3'))
  proof_names=['backbone.backbone.dark5.0.conv.weight','backbone.lateral_conv0.conv.weight','head.reg_convs.0.0.conv.weight'];items=acne_tiles(tr,training=False)
  roi_cache={r['sha256']:target_scope(r,'acne') for r in tr}
  obj_loss=KnownObjectnessBCE();net.head.bcewithlog_loss=obj_loss
  items=[t for t in items if t['boxes'] or t['row']['reviewDecision'].get('completePimpleROI') and bool(known_cells(roi_cache[t['row']['sha256']],t['rect'],True).any())]
  def loss(batch):
   obj_loss.known=torch.cat([known_cells(roi_cache[t['row']['sha256']],t['rect'],t['row']['reviewDecision'].get('completePimpleROI',False)) for t in batch]);x,y=yolo_batch(batch);return net(x,y)['total_loss']
  def evaluate():
   predictions=predict(net,'yolox',va);write('yolox/validation-predictions.json',dict(rows=[dict(sourceSHA256=r['sha256'],predictions=p,truth=r['annotations']) for r,p in zip(va,predictions)]))
   choices=[detection_metrics(va,predictions,t) for t in [.1,.25,.4,.55,.7]];return max(choices,key=lambda v:v['F1'])
  def quality(m):return m['F1']
  batchsize=2;maximum_epochs=8;budget=2100
 assert len(items)>=2 and va,'REVIEWED_TRAIN_AND_VALIDATION_REQUIRED'
 if task=='mask':
  overlap=[dict(sourceSHA256=r['sha256'],inputShape=list(cache[r['sha256']][0].shape),positivePixels={t:int(cache[r['sha256']][1][j].sum()) for j,t in enumerate(TARGETS)},knownPixels={t:int(cache[r['sha256']][2][j].sum()) for j,t in enumerate(TARGETS)},transform=cache[r['sha256']][3]) for r in items]
 else:
  overlap=[dict(sourceSHA256=t['row']['sha256'],nativeSourceRect=t['rect'],inputShape=[3,384,384],activePimpleBoxes=t['boxes'],knownNegativeROIReviewed=t['row']['reviewDecision'].get('completePimpleROI',False)) for t in items]
 write(task+'/tensor-target-overlap.json',dict(rows=overlap,sourceAnnotationTruth=True,predictorGeneratedTruth=False,paddingUnknown=True))
 proof_names=[n for n in proof_names if n in net.state_dict()];assert len(proof_names)==3
 before={k:net.state_dict()[k].clone() for k in proof_names}
 protocol=dict(task=task,architecture='ResNet18-small-U-Net' if task=='mask' else 'YOLOX-S Apache-2.0',sharedTargets=TARGETS if task=='mask' else ['active-Pimple-only'],sigmoidIndependent=task=='mask',partialLabelsLossMasked=True,boxIsPixelMask=False,trainingItems=len(items),validationPhotos=len(va),maximumEpochs=maximum_epochs,patience=3,maximumSeconds=budget,minimumDice=.65,minimumIoU=.5,maximumNegativeFPR=.05,minimumF1=.5,minimumPrecision=.6,minimumRecall=.4,requiredNaturalConfounderAcceptance=True,seed=20261011,expertLabels=False,independentFinalOpened=False,reviewSHA256=sha(OUT/'review/decisions.json'),manifestSHA256=sha(OUT/'manifest.json'),optimizer='AdamW',scheduler='cosine')
 write(task+'/protocol.json',protocol);identity=sha(folder/'protocol.json');initial={k:v.clone() for k,v in net.state_dict().items()}
 opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.0003 if task=='mask' else .0001,weight_decay=.0001);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,maximum_epochs)
 state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,seconds=0.,scheduler=sched.state_dict(),gradients={});started=time.monotonic();previous=0.
 def trainmode():
  net.train()
  for m in net.modules():
   if isinstance(m,torch.nn.BatchNorm2d):m.eval()
 def advance(batch):
  trainmode();opt.zero_grad();v=loss(batch);assert torch.isfinite(v);v.backward()
  for k,p in net.named_parameters():
   if k in proof_names and p.grad is not None:state['gradients'][k]=max(state['gradients'].get(k,0.),float(p.grad.abs().max()))
  torch.nn.utils.clip_grad_norm_(net.parameters(),10);opt.step();return float(v.detach())
 def save():
  state['seconds']=previous+time.monotonic()-started;state['scheduler']=sched.state_dict();checkpoint(folder,net,opt,state)
 if (folder/'CURRENT').exists():state=resume(folder,net,opt,identity);sched.load_state_dict(state['scheduler']);previous=state['seconds']
 else:
  tiny=items[:2] if task=='mask' else [t for t in items if t['boxes']][:2]
  assert len(tiny)==2,'TWO_REVIEWED_POSITIVE_LEARNING_ITEMS_REQUIRED'
  losses=[advance(tiny) for _ in range(40)]
  passed=float(np.mean(losses[-5:]))<.65*float(np.mean(losses[:5]));write(task+'/learning.json',dict(firstLoss=float(np.mean(losses[:5])),lastLoss=float(np.mean(losses[-5:])),passed=passed,trainOnly=True,steps=40,gradients=state['gradients']))
  assert passed,'REAL_LEARNING_CHAIN_FAILED'
  net.load_state_dict(initial);opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.0003 if task=='mask' else .0001,weight_decay=.0001);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,maximum_epochs);state['gradients']={};save()
 while state['epoch']<maximum_epochs and state['bad']<3:
  if previous+time.monotonic()-started>=budget:break
  epoch_start=time.monotonic()
  if not state['order']:state.update(order=torch.randperm(len(items)).tolist(),cursor=0,losses=[])
  last_save=time.monotonic()
  while state['cursor']<len(items):
   if previous+time.monotonic()-started>=budget:save();write(task+'/stop.json',dict(reason='FINITE_WALL_LIMIT',validatedEpochs=state['epoch'],partialEpochPreserved=True));return
   ids=state['order'][state['cursor']:state['cursor']+batchsize];state['losses'].append(advance([items[i] for i in ids]));state['cursor']+=len(ids);state['step']+=1
   if time.monotonic()-last_save>60:save();last_save=time.monotonic();print(task,'epoch',state['epoch']+1,'items',state['cursor'],len(items),flush=True)
  metric=evaluate();score=quality(metric);state['epoch']+=1
  entry=dict(epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=metric,epochSeconds=time.monotonic()-epoch_start,seconds=previous+time.monotonic()-started);state['history'].append(entry)
  if score>state['best']+1e-4:state['best']=score;state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'))
  else:state['bad']+=1
  sched.step();state.update(order=[],cursor=0);save();write(task+'/history.json',state['history']);print(task,'validated epoch',state['epoch'],'score',score,'seconds',entry['epochSeconds'],flush=True)
 assert state['history'],'NO_VALIDATED_EPOCH'
 selected=load_file(str(folder/'selected.safetensors'));changes={k:dict(maxAbs=float((selected[k]-before[k]).abs().max()),gradientMax=state['gradients'].get(k,0.)) for k in proof_names}
 assert all(v['maxAbs']>0 and v['gradientMax']>0 for v in changes.values()),'BACKBONE_NECK_DID_NOT_LEARN'
 best=max(state['history'],key=lambda h:quality(h['validation']));write(task+'/selection.json',dict(validation=best['validation'],selectedEpoch=best['epoch'],features=changes,accepted=False,reason='Engineering subset; independent unused test and natural confounder/score calibration acceptance pending',weightsSHA256=sha(folder/'selected.safetensors')))
 net.load_state_dict(selected);net.eval();path=folder/'candidate.onnx'
 if task=='mask':samples=[mask_tensor(r)[0][None] for r in va[:4]];inputname='rgb_face_roi';outname='mask_logits'
 else:
  from train_focused_local import tile_image
  samples=[tile_image(t)[None] for t in acne_tiles(va,training=False)[:4]];inputname='native_bgr_tile';outname='detections'
 # Primitive convolution prevents oneDNN backend rounding from dominating huge rejected widths.
 torch.backends.mkldnn.enabled=False
 torch.onnx.export(net,samples[0],str(path),input_names=[inputname],output_names=[outname],opset_version=17,dynamo=False)
 import onnxruntime as ort
 options=ort.SessionOptions();options.intra_op_num_threads=2;session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);errors=[]
 with torch.inference_mode():
  for x in samples:
   expected=net(x).numpy();actual=session.run(None,{inputname:x.numpy()})[0];np.testing.assert_allclose(actual,expected,rtol=1e-5,atol=.001);errors.append(float(np.abs(actual-expected).max()))
 source_parity=[]
 if task=='mask':
  with torch.inference_mode():
   for r,x in zip(va[:4],samples):
    _,transform=mask_input(cv2.imread(r['absolutePath']),r['crop']);actual=session.run(None,{inputname:x.numpy()})[0][0];expected=net(x).numpy()[0];aa=restore_mask(actual,transform);ee=restore_mask(expected,transform);source_parity.append(float(np.abs(aa-ee).max()))
    assert aa.shape==(len(TARGETS),r['crop'][3]-r['crop'][1],r['crop'][2]-r['crop'][0]);np.testing.assert_allclose(aa,ee,rtol=1e-5,atol=.001)
 else:
  class ORTDetector:
   def eval(self):return self
   def __call__(self,x):return torch.from_numpy(session.run(None,{inputname:x.numpy()})[0])
  expected_boxes=predict(net,'yolox',va[:4]);actual_boxes=predict(ORTDetector(),'yolox',va[:4])
  for expected,actual in zip(expected_boxes,actual_boxes):
   assert len(expected)==len(actual),'SOURCE_NMS_COUNT_PARITY_FAILED'
   if expected:
    ee=np.asarray(expected);aa=np.asarray(actual);np.testing.assert_allclose(aa,ee,rtol=1e-5,atol=.001);source_parity.append(float(np.abs(aa[:,:4]-ee[:,:4]).max()))
   else:source_parity.append(0.)
 write(task+'/export.json',dict(sha256=sha(path),maxAbsoluteError=max(errors),sourceCoordinateMaxAbsoluteError=max(source_parity,default=None),photosOrNativeTiles=len(samples),accepted=False,productionInstalled=False,preprocessing='RGB letterbox256 ImageNet' if task=='mask' else 'native384 BGR 114padding no resizing'))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('task',choices=['mask','yolox']);main(p.parse_args().task)
