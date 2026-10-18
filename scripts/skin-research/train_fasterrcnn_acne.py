"""Native-tile Faster R-CNN / ResNet50-FPN research, separate from product.
Learning chain check precedes bounded validation training and protected test.
Image/label/permission manifests remain private local files. No upload or service.
"""
from pathlib import Path
import argparse,importlib.util,json,time,random,hashlib
import numpy as np
import torch
from safetensors.torch import load_file
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection.anchor_utils import AnchorGenerator
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native',Path(__file__).with_name('train_native_acne.py'));native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
OUT=ROOT/'audit-results/all-health-20261010/fasterrcnn'
STARTUP=OUT
def create():
 rights=json.loads((STARTUP/'startup-rights.json').read_text());path=STARTUP/'model.safetensors';assert native.sha(path)==rights['sha256']['model.safetensors']
 model=fasterrcnn_resnet50_fpn(weights=None,weights_backbone=None,min_size=256,max_size=256,rpn_anchor_generator=AnchorGenerator(((8,),(16,),(32,),(64,),(128,)),((.5,1.,2.),)*5),rpn_pre_nms_top_n_train=600,rpn_post_nms_top_n_train=200,rpn_pre_nms_top_n_test=600,rpn_post_nms_top_n_test=200,box_detections_per_img=100,box_score_thresh=.01)
 state=load_file(str(path));model.backbone.body.load_state_dict({k:v for k,v in state.items() if not k.startswith('fc.')},strict=True)
 model.roi_heads.box_predictor=FastRCNNPredictor(model.roi_heads.box_predictor.cls_score.in_features,2)
 # Freeze pretrained low-level stages; train layer4, FPN, RPN and task heads.
 for name,p in model.backbone.body.named_parameters():p.requires_grad=name.startswith('layer4')
 return model
def samples(rows,images):
 result=[]
 for row,image in zip(rows,images):
  h,w=image.shape[:2]
  for y in range(0,h,192):
   for x in range(0,w,192):
    tile=np.full((256,256,3),128,np.uint8);part=image[y:y+256,x:x+256];tile[:part.shape[0],:part.shape[1]]=part
    boxes=[]
    for a,b,c,d in row['boxes']:
     if x<=(a+c)/2<x+part.shape[1] and y<=(b+d)/2<y+part.shape[0]:
      box=[max(0,a-x),max(0,b-y),min(part.shape[1],c-x),min(part.shape[0],d-y)]
      if min(box[2]-box[0],box[3]-box[1])>=2:boxes.append(box)
    # Unknown/ignored areas must not teach background labels.
    if any(a<x+part.shape[1] and c>x and b<y+part.shape[0] and d>y for a,b,c,d in row['ignore']):continue
    tensor=torch.from_numpy(tile.transpose(2,0,1).copy()).float()/255
    target={'boxes':torch.tensor(boxes,dtype=torch.float32).reshape(-1,4),'labels':torch.ones(len(boxes),dtype=torch.int64)}
    result.append((tensor,target,row['index'],(x,y)))
 return result
def predictions(model,rows,images):
 result=[];model.eval()
 with torch.no_grad():
  for row,image in zip(rows,images):
   h,w=image.shape[:2];pred=[]
   for y in range(0,h,192):
    for x in range(0,w,192):
     tile=np.full((256,256,3),128,np.uint8);part=image[y:y+256,x:x+256];tile[:part.shape[0],:part.shape[1]]=part
     output=model([torch.from_numpy(tile.transpose(2,0,1).copy()).float()/255])[0]
     if not all(torch.isfinite(output[k]).all() for k in ('boxes','scores')):raise RuntimeError('INVALID_MODEL_OUTPUT')
     for box,score in zip(output['boxes'].tolist(),output['scores'].tolist()):
      a,b,c,d=box;a+=x;c+=x;b+=y;d+=y
      if (a+c)/2>=w or (b+d)/2>=h:continue
      pred.append({'box':[max(0,a),max(0,b),min(w,c),min(h,d)],'confidence':score})
   result.append(pred)
 return result
def step(model,optimizer,sample):
 model.train()
 # Running pretrained BN statistics are fixed in tiny batch CPU fine-tuning.
 for m in model.modules():
  if isinstance(m,torch.nn.BatchNorm2d):m.eval()
 image,target,*_=sample;optimizer.zero_grad();losses=model([image],[target]);loss=sum(losses.values())
 if not torch.isfinite(loss):raise RuntimeError('NONFINITE_TRAINING_LOSS')
 loss.backward();gradient=sum(float(p.grad.abs().sum()) for p in model.roi_heads.box_predictor.parameters() if p.grad is not None)
 if gradient<=0:raise RuntimeError('MISSING_HEAD_GRADIENT')
 torch.nn.utils.clip_grad_norm_(model.parameters(),5.);optimizer.step();return {k:float(v.detach()) for k,v in losses.items()},gradient
def main():
 global OUT
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['learning','train','test']);ap.add_argument('--balanced-roi',action='store_true');args=ap.parse_args()
 if args.balanced_roi:
  if OUT==STARTUP:OUT=STARTUP.parent/'fasterrcnn-balanced'
  # The first run collapsed to background on small lesions. This bounded
  # correction uses training-set class balance, never protected-test outcomes.
  from torchvision.models.detection import roi_heads
  from torch.nn import functional as F
  def balanced_loss(logits,boxes,labels,targets):
   labels=torch.cat(labels);targets=torch.cat(targets)
   classification=F.cross_entropy(logits,labels,weight=logits.new_tensor([1.,16.]))
   positive=torch.where(labels>0)[0];n=logits.shape[0]
   boxes=boxes.reshape(n,boxes.shape[-1]//4,4)
   regression=F.smooth_l1_loss(boxes[positive,labels[positive]],targets[positive],beta=1/9,reduction='sum')/labels.numel()
   return classification,regression
  roi_heads.fastrcnn_loss=balanced_loss
 OUT.mkdir(parents=True,exist_ok=True)
 torch.set_num_threads(2);torch.manual_seed(20261010);random.seed(20261010)
 previous=ROOT/'audit-results/acne-trained-20261010';manifest=json.loads((previous/'annotations-private.json').read_text());train,images=native.load_rows(manifest,'train');val,vimages=native.load_rows(manifest,'validation');model=create();optimizer=torch.optim.SGD([p for p in model.parameters() if p.requires_grad],lr=.005,momentum=.9,weight_decay=.0005)
 if args.balanced_roi:
  model.roi_heads.fg_bg_sampler.batch_size_per_image=64
  model.roi_heads.fg_bg_sampler.positive_fraction=.5
 if args.mode=='learning':
  if (OUT/'learning.json').exists():
   previous_check=json.loads((OUT/'learning.json').read_text())
   assert not previous_check['passed'] and not (OUT/'learning-attempt-1.json').exists(),'Retain bounded learning attempts'
   (OUT/'learning-attempt-1.json').write_text(json.dumps(previous_check,indent=2),'utf8')
  subset=[s for s in samples(train,images) if len(s[1]['boxes'])][:2];start=time.monotonic();history=[];first=None
  for n in range(100):
   losses,gradient=step(model,optimizer,subset[n%2]);total=sum(losses.values());first=total if first is None else first;history.append(dict(step=n+1,losses=losses,gradient=gradient))
   # Background classification can fall before localization learns. A falling
   # aggregate loss is not a valid early stopping signal for this chain check.
   if time.monotonic()-start>300:break
  model.eval();checks=[]
  with torch.no_grad():
   for image,target,index,origin in subset:
    output=model([image])[0];p=[dict(box=b,confidence=s) for b,s in zip(output['boxes'].tolist(),output['scores'].tolist()) if s>=.3];up,ug=native.matches(p,target['boxes'].tolist());checks.append(dict(index=index,origin=origin,truth=len(target['boxes']),matched=len(ug),predictions=p))
  passed=history[-1]['gradient']>0 and history[-1]['losses']['loss_box_reg']<history[0]['losses']['loss_box_reg'] and sum(v['matched'] for v in checks)>0
  (OUT/'learning.json').write_text(json.dumps(dict(passed=passed,seconds=time.monotonic()-start,history=history,checks=checks,scope='learning chain only; not independent accuracy'),indent=2),'utf8');print(json.dumps({'learningPassed':passed,'steps':len(history),'seconds':time.monotonic()-start}),flush=True)
 elif args.mode=='train':
  assert json.loads((OUT/'learning.json').read_text())['passed'];assert not (OUT/'selection.json').exists();assert not (OUT/'test.json').exists()
  criteria=dict(maxEpochs=15,maxSeconds=1800,patience=4,selection='validation F1 only',minimumPrecision=.8,minimumRecall=.8,maximumNegativeFP=1,clinicalExpertLabelRequired=False,knownDerivativeDisjointRequired=True,balancedROI=args.balanced_roi,foregroundLossWeight=16 if args.balanced_roi else 1)
  (OUT/'acceptance.json').write_text(json.dumps(criteria,indent=2),'utf8');training=samples(train,images);start=time.monotonic();best=-1.;stale=0;history=[]
  if args.balanced_roi:
   positive=[s for s in training if len(s[1]['boxes'])];negative=[s for s in training if not len(s[1]['boxes'])]
   training=positive+random.sample(negative,min(len(positive),len(negative)))
  for epoch in range(criteria['maxEpochs']):
   random.shuffle(training);losses=[]
   for sample in training:
    loss,gradient=step(model,optimizer,sample);losses.append(sum(loss.values()))
   p=predictions(model,val,vimages);thresholds=[.1,.2,.3,.4,.5,.6,.7,.8,.9];threshold=max(thresholds,key=lambda t:(native.metrics(val,p,t)['F1'],t));metric=native.metrics(val,p,threshold);history.append(dict(epoch=epoch+1,loss=float(np.mean(losses)),validation={k:v for k,v in metric.items() if k!='details'},threshold=threshold,seconds=time.monotonic()-start));print(json.dumps(history[-1]),flush=True)
   if metric['F1']>best+1e-4:best=metric['F1'];stale=0;torch.save(model.state_dict(),OUT/'selected.pt');selected=dict(epoch=epoch+1,threshold=threshold,validationF1=best)
   else:stale+=1
   if stale>=criteria['patience'] or time.monotonic()-start>criteria['maxSeconds']:break
  selected.update(history=history,modelSHA256=native.sha(OUT/'selected.pt'),manifestSHA256=native.sha(previous/'annotations-private.json'),productionAccepted=False)
  (OUT/'selection.json').write_text(json.dumps(selected,indent=2),'utf8')
 else:
  assert not (OUT/'test.json').exists(),'Do not retune after protected test';selection=json.loads((OUT/'selection.json').read_text());assert native.sha(OUT/'selected.pt')==selection['modelSHA256'];assert native.sha(previous/'annotations-private.json')==selection['manifestSHA256'];model.load_state_dict(torch.load(OUT/'selected.pt',weights_only=True));rows,images=native.load_rows(manifest,'test');start=time.monotonic();p=predictions(model,rows,images);metric=native.metrics(rows,p,selection['threshold']);report=dict(metrics=metric,modelSHA256=selection['modelSHA256'],seconds=time.monotonic()-start,productionAccepted=False,scope='7 previously examined engineering crops; not new population or subject-independent evaluation',heldoutNotUsedForSelection=True)
  (OUT/'test.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in metric.items() if k!='details'}),flush=True)
if __name__=='__main__':main()
