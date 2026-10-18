"""From-scratch LOCAL CPU localization experiment, never loaded by the product.
Explicit engineering boxes and native RGB. No pseudo-labeling, pretrained weights,
redness proposals, face resize, identity linking, upload, or paid job.
Train/validation selection is separate from the single protected-test command.
"""
import argparse, copy, hashlib, json, math, random, time
from pathlib import Path
import cv2
import numpy as np
import torch
from torch import nn
ROOT=Path(__file__).resolve().parents[2]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class NativeDetector(nn.Module):
 def __init__(self):
  super().__init__()
  self.body=nn.Sequential(nn.Conv2d(3,16,5,stride=2,padding=2),nn.ReLU(),nn.Conv2d(16,24,3,stride=2,padding=1),nn.ReLU(),nn.Conv2d(24,32,3,padding=1),nn.ReLU(),nn.Conv2d(32,32,3,padding=2,dilation=2),nn.ReLU())
  self.center=nn.Conv2d(32,1,1);self.size=nn.Conv2d(32,2,1)
  nn.init.constant_(self.center.bias,-2.2)
 def forward(self,x):
  f=self.body(x);return self.center(f),self.size(f)

def iou(a,b):
 ix=max(0,min(a[2],b[2])-max(a[0],b[0]));iy=max(0,min(a[3],b[3])-max(a[1],b[1]));inter=ix*iy
 return inter/max(1,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)
def matches(pred,truth):
 pairs=sorted([(iou(p['box'],g),i,j) for i,p in enumerate(pred) for j,g in enumerate(truth)],reverse=True);usedp=set();usedg=set()
 for value,i,j in pairs:
  if value>=.3 and i not in usedp and j not in usedg:usedp.add(i);usedg.add(j)
 return usedp,usedg

def filtered(pred,threshold,ignore):
 candidates=sorted((p for p in pred if p['confidence']>=threshold),key=lambda p:p['confidence'],reverse=True);result=[]
 for p in candidates:
  x=(p['box'][0]+p['box'][2])/2;y=(p['box'][1]+p['box'][3])/2
  if any(a<=x<c and b<=y<d for a,b,c,d in ignore):continue
  if all(iou(p['box'],q['box'])<.3 for q in result):result.append(p)
 return result

def metrics(rows,predictions,threshold):
 tp=fp=fn=0;negative=[];details=[]
 for r,pred in zip(rows,predictions):
  p=filtered(pred,threshold,r['ignore']);up,ug=matches(p,r['boxes']);tp+=len(up);fp+=len(p)-len(up);fn+=len(r['boxes'])-len(ug)
  if not r['boxes']:negative.append(len(p))
  details.append({'index':r['index'],'tp':len(up),'fp':len(p)-len(up),'fn':len(r['boxes'])-len(ug),'predictions':p,'matchedPredictionIndexes':sorted(up),'matchedTruthIndexes':sorted(ug),'sourceOrigin':r['cropBox'][:2]})
 precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn)
 return {'tp':tp,'fp':fp,'fn':fn,'precision':precision,'recall':recall,'F1':2*precision*recall/max(1e-10,precision+recall),'positivePhotos':sum(bool(r['boxes']) for r in rows),'negativePhotos':len(negative),'meanFPPerNegativePhoto':float(np.mean(negative)) if negative else None,'details':details}

def infer(model,image):
 # Overlapping native 256-pixel tiles, 64-pixel overlap. Equal probability/size
 # averaging in overlaps, then one source-coordinate list and global NMS.
 if image.dtype!=np.uint8 or image.ndim!=3 or image.shape[2]!=3 or min(image.shape[:2])<16:raise ValueError('INVALID_NATIVE_RGB')
 h,w=image.shape[:2];ph=math.ceil(h/4)*4;pw=math.ceil(w/4)*4
 padded=cv2.copyMakeBorder(image,0,ph-h,0,pw-w,cv2.BORDER_REFLECT_101)
 score=np.zeros((ph//4,pw//4),np.float32);sizes=np.zeros((2,ph//4,pw//4),np.float32);count=np.zeros_like(score)
 for y in range(0,ph,192):
  for x in range(0,pw,192):
   tile=padded[y:min(ph,y+256),x:min(pw,x+256)]
   with torch.no_grad():s,z=model(torch.from_numpy(tile.transpose(2,0,1).copy()).float()[None]/255)
   if s.shape!=(1,1,tile.shape[0]//4,tile.shape[1]//4) or z.shape!=(1,2,tile.shape[0]//4,tile.shape[1]//4) or not torch.isfinite(s).all() or not torch.isfinite(z).all():raise RuntimeError('INVALID_MODEL_OUTPUT')
   s=torch.sigmoid(s)[0,0].numpy();z=torch.exp(torch.clamp(z[0],math.log(4),math.log(100))).numpy()
   yy,xx=y//4,x//4;th,tw=s.shape;score[yy:yy+th,xx:xx+tw]+=s;sizes[:,yy:yy+th,xx:xx+tw]+=z;count[yy:yy+th,xx:xx+tw]+=1
 score/=np.maximum(count,1);sizes/=np.maximum(count,1)
 maxima=(score==cv2.dilate(score,np.ones((3,3),np.uint8)))&(score>=.01)
 ys,xs=np.where(maxima);order=np.argsort(score[ys,xs])[::-1];pred=[]
 for i in order[:300]:
  x=int(xs[i])*4+2;y=int(ys[i])*4+2;bw,bh=map(float,sizes[:,ys[i],xs[i]])
  if x>=w or y>=h:continue
  pred.append({'box':[max(0,x-bw/2),max(0,y-bh/2),min(w,x+bw/2),min(h,y+bh/2)],'confidence':float(score[ys[i],xs[i]])})
 return pred

def load_rows(manifest,split):
 rows=[r for r in manifest['rows'] if r['split']==split];images=[]
 for r in rows:
  p=(ROOT/r['cropPath']).resolve();assert p.is_relative_to(ROOT/'audit-results');assert sha(p)==r['cropSHA256']
  source=(ROOT/r['source']['image_path']).resolve();assert source.is_relative_to(ROOT/'audit-results') and sha(source)==r['source']['sha256']
  native=cv2.cvtColor(cv2.imread(str(source)),cv2.COLOR_BGR2RGB);a,b,c,d=r['cropBox'];im=cv2.cvtColor(cv2.imread(str(p)),cv2.COLOR_BGR2RGB);assert np.array_equal(native[b:d,a:c],im), 'Crop changed source pixels'
  images.append(im)
 return rows,images

def tiles(rows,images,rng):
 X=[];Y=[];Z=[];M=[];V=[]
 for r,im in zip(rows,images):
  for n in range(8):
   h,w=im.shape[:2]
   if r['boxes'] and n<4:
    b=rng.choice(r['boxes']);cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2;x=round(cx-64+rng.randint(-35,35));y=round(cy-64+rng.randint(-35,35))
   else:x=rng.randrange(max(1,w-128));y=rng.randrange(max(1,h-128))
   x=min(max(0,x),w-128);y=min(max(0,y),h-128);tile=im[y:y+128,x:x+128]
   target=np.zeros((1,32,32),np.float32);size=np.zeros((2,32,32),np.float32);mask=np.zeros((1,32,32),np.float32);valid=np.ones((1,32,32),np.float32)
   for a,b,c,d in r['ignore']:
    valid[:,max(0,(b-y)//4):min(32,math.ceil((d-y)/4)),max(0,(a-x)//4):min(32,math.ceil((c-x)/4))]=0
   for a,b,c,d in r['boxes']:
    cx=(a+c)/2-x;cy=(b+d)/2-y
    if not(0<=cx<128 and 0<=cy<128):continue
    xx,yy=int(cx//4),int(cy//4);target[0,yy,xx]=1;size[:,yy,xx]=np.log([c-a,d-b]);mask[0,yy,xx]=1
   # Native crop flip augmentation preserves the label/box coordinates.
   if rng.random()<.5:tile=tile[:,::-1];target=target[:,:,::-1];size=size[:,:,::-1];mask=mask[:,:,::-1];valid=valid[:,:,::-1]
   X.append(tile.transpose(2,0,1).copy());Y.append(target.copy());Z.append(size.copy());M.append(mask.copy());V.append(valid.copy())
 return [torch.from_numpy(np.stack(a)).float() for a in [X,Y,Z,M,V]]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['train','test']);ap.add_argument('--out',default='audit-results/acne-trained-20261010');args=ap.parse_args()
 out=(ROOT/args.out).resolve();assert out.is_relative_to(ROOT/'audit-results');criteria=json.loads((out/'acceptance.json').read_text());manifest=json.loads((out/'annotations-private.json').read_text());torch.set_num_threads(2);torch.use_deterministic_algorithms(True);seed=criteria['training']['seed'];torch.manual_seed(seed);rng=random.Random(seed)
 for group in {r['group'] for r in manifest['rows']}:assert len({r['split'] for r in manifest['rows'] if r['group']==group})==1
 model=NativeDetector();checkpoint=out/'native-detector.pt'
 if args.mode=='train':
  train,images=load_rows(manifest,'train');val,vimages=load_rows(manifest,'validation');native_sizes=np.array([[b[2]-b[0],b[3]-b[1]] for r in train for b in r['boxes']]);model.size.bias.data.copy_(torch.tensor(np.log(np.median(native_sizes,axis=0)),dtype=torch.float32));start=time.perf_counter();optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01);history=[];best=-1;best_loss=float('inf');stale=0;best_threshold=.5
  for epoch in range(criteria['training']['maxEpochs']):
   model.train();X,Y,Z,M,V=tiles(train,images,rng);losses=[]
   for indexes in torch.randperm(len(X)).split(16):
    optimizer.zero_grad();logits,z=model(X[indexes]/255);p=torch.sigmoid(logits);positive=Y[indexes];valid=V[indexes];m=M[indexes]
    focal=-(positive*(1-p)**2*torch.log(torch.clamp(p,min=1e-6))+(1-positive)*p**2*torch.log(torch.clamp(1-p,min=1e-6)))
    loss=(focal*valid).sum()/max(1,float((positive*valid).sum()))+.1*(nn.functional.smooth_l1_loss(z,Z[indexes],reduction='none')*m).sum()/max(1,float(m.sum()))
    loss.backward();optimizer.step();losses.append(float(loss.detach()))
   model.eval();VX,VY,VZ,VM,VV=tiles(val,vimages,random.Random(seed+1));vloss=0.
   with torch.no_grad():
    for vi in torch.arange(len(VX)).split(16):
     vp,vz=model(VX[vi]/255)
     vprob=torch.sigmoid(vp)
     vf=-(VY[vi]*(1-vprob)**2*torch.log(torch.clamp(vprob,min=1e-6))+(1-VY[vi])*vprob**2*torch.log(torch.clamp(1-vprob,min=1e-6)))
     vloss+=float((vf*VV[vi]).sum())/max(1,float((VY[vi]*VV[vi]).sum()))
     vloss+=.1*float((nn.functional.smooth_l1_loss(vz,VZ[vi],reduction='none')*VM[vi]).sum())/max(1,float(VM[vi].sum()))
   pred=[infer(model,im) for im in vimages];thresholds=np.array([.01,.02,.04,.06,.08,.1,.15,.2,.3,.4,.5,.6,.7,.8,.9]);chosen=max(thresholds,key=lambda t:(metrics(val,pred,t)['F1'],t));metric=metrics(val,pred,chosen);record={'epoch':epoch+1,'loss':float(np.mean(losses)),'validation':{k:v for k,v in metric.items() if k!='details'},'threshold':float(chosen),'elapsedSeconds':time.perf_counter()-start,'validationLoss':vloss};history.append(record);print(json.dumps(record),flush=True)
   if metric['F1']>best+1e-5:
    best=metric['F1'];best_threshold=float(chosen);torch.save(model.state_dict(),checkpoint)
   if vloss<best_loss-1e-4:best_loss=vloss;stale=0
   else:stale+=1
   if stale>=criteria['training']['patience'] or time.perf_counter()-start>=criteria['training']['maxSeconds']:break
  selection={'trained':True,'pretrainedWeights':False,'productAccepted':False,'threshold':best_threshold,'validationF1':best,'modelSHA256':sha(checkpoint),'manifestSHA256':sha(out/'annotations-private.json'),'criteriaSHA256':sha(out/'acceptance.json'),'trainingCodeSHA256':sha(Path(__file__)),'history':history,'parameters':sum(p.numel() for p in model.parameters()),'trainingSeconds':time.perf_counter()-start,'stopReason':'validation-loss patience or frozen upper cap','validationAttempt':2,'maximumValidationAttempts':2,'initialSizeBias':'training-only median native bbox, not a pretrained weight','firstAttemptReason':'validation-only zero localization; untrained log-size started at one pixel and threshold grid excluded low learned scores; protected test remained unopened','license':'SCIN Data Use License preserved for research weights; application code separate','preprocess':'opaque native RGB / 255; 256px overlapping tiles, stride192; no face resize or redness gate','output':'trained center confidence + log width/height; source pixels; global IoU0.3 NMS; confidence is not severity'}
  (out/'selection.json').write_text(json.dumps(selection,indent=2),'utf8')
  model.load_state_dict(torch.load(checkpoint,weights_only=True));model.eval()
  torch.onnx.export(model,(torch.zeros(1,3,256,256),),str(out/'native-detector.onnx'),input_names=['native_rgb'],output_names=['center_logits','log_wh'],dynamic_axes={'native_rgb':{2:'height',3:'width'},'center_logits':{2:'out_height',3:'out_width'},'log_wh':{2:'out_height',3:'out_width'}},opset_version=17,dynamo=False)
  print('Training finished. Protected test not opened; product gate CLOSED.',flush=True)
 else:
  selection=json.loads((out/'selection.json').read_text());assert sha(checkpoint)==selection['modelSHA256'];assert sha(out/'annotations-private.json')==selection['manifestSHA256'];assert sha(out/'acceptance.json')==selection['criteriaSHA256'];assert not (out/'test-evaluation.json').exists(),'Protected test already evaluated; do not retune using it'
  model.load_state_dict(torch.load(checkpoint,weights_only=True));model.eval();rows,images=load_rows(manifest,'test');start=time.perf_counter();pred=[infer(model,im) for im in images];metric=metrics(rows,pred,selection['threshold']);elapsed=time.perf_counter()-start;reasons=[]
  for key,min_key in [('precision','minimumPrecision'),('recall','minimumRecall'),('F1','minimumF1'),('positivePhotos','minimumIndependentTestPositivePhotos'),('negativePhotos','minimumIndependentTestNegativePhotos')]:
   if metric[key]<criteria[min_key]:reasons.append(key+' below frozen minimum')
  if sum(len(r['boxes']) for r in rows)<criteria['minimumTestLesions']:reasons.append('too few independent local appearances')
  for key in ['subjectDisjointVerified','expertLocalizationVerified','nativeCameraDomainVerified']:
   if not manifest[key]:reasons.append(key+' not established')
  report={'productAccepted':False,'engineeringSetOnly':True,'thresholdFrozen':selection['threshold'],'modelSHA256':sha(checkpoint),'onnxSHA256':sha(out/'native-detector.onnx'),'testSeconds':elapsed,'metrics':metric,'reasons':reasons,'widthResize':False,'sourceDataUploaded':False}
  (out/'test-evaluation.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k!='metrics'}));print(json.dumps({k:v for k,v in metric.items() if k!='details'}))
  for r,im,detail in zip(rows,images,metric['details']):
   canvas=cv2.cvtColor(im,cv2.COLOR_RGB2BGR)
   for i,b in enumerate(r['boxes']):cv2.rectangle(canvas,tuple(map(round,b[:2])),tuple(map(round,b[2:])),(0,255,0) if i in detail['matchedTruthIndexes'] else (0,0,255),2)
   for i,p in enumerate(detail['predictions']):cv2.rectangle(canvas,tuple(map(round,p['box'][:2])),tuple(map(round,p['box'][2:])),(255,0,255),1)
   cv2.imwrite(str(out/f'test-{r["index"]}-review.png'),canvas)
if __name__=='__main__':main()
