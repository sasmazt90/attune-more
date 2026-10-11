"""Additional native supervision; never rewrite an active training ledger.

Diffuse Care acne is photo/field presence, not individual lesion pixel truth.
Black augmentation rectangles stay unknown. Boxes and CSV zeros are not masks.
"""
import collections,json
from pathlib import Path
import cv2,numpy as np
from expanded_sources import OUT,PREVIOUS,mask,sha,write
from expanded_mask_data import native_rects
TARGETS=['acne','oil','dry','redness','tone','lines','dark','bags']

def augmentation_unknown(image):
 raw=(image.max(2)<5).astype(np.uint8);n,labels,stats,_=cv2.connectedComponentsWithStats(raw);excluded=np.zeros(raw.shape,bool)
 for i in range(1,n):
  x,y,w,h,a=stats[i]
  if 7<=w<=100 and 7<=h<=100 and .75<=w/max(h,1)<=1.33 and a/max(w*h,1)>.92:excluded|=labels==i
 return excluded

def valid_skin_scope(r):
 # Visible face oval, with actual eye/lip/nostril surfaces removed. This is an
 # anatomical support, not a full-face quality gate for local target training.
 h,w=r['height'],r['width'];p=np.array([[v['x']*w,v['y']*h] for v in r['landmarks']],np.float32);s=np.zeros((h,w),np.uint8)
 oval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
 cv2.fillPoly(s,[np.rint(p[oval]).astype(np.int32)],1)
 for ids in [[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327]]:cv2.fillPoly(s,[np.rint(p[ids]).astype(np.int32)],0)
 return s

def main():
 ledger=OUT/'continuation-mask-data.json'
 if ledger.exists():print('Immutable continuation pool preserved');return
 cv2.setNumThreads(1);rows=[];decisions=[];receipts={}
 for name in ['', 'supplement/']:
  cp=OUT/(name+'candidates.json');dp=OUT/(name+'decisions.json');rows+=json.loads(cp.read_text('utf8'))['rows'];decisions+=json.loads(dp.read_text('utf8'))['rows'];receipts[name+'candidates']=sha(cp);receipts[name+'decisions']=sha(dp)
 by={d['reviewKey']:d for d in decisions};items=[];fields=[];seen=set();folder=OUT/'continuation-mask/tensors';folder.mkdir(parents=True,exist_ok=True)
 def add(r,t,m,s,complete,origin):
  im=cv2.imread(r['absolutePath']);assert im is not None and sha(Path(r['absolutePath']))==r['sha256'];unknown=augmentation_unknown(im);s=s.astype(bool)&~unknown;m=m.astype(bool)&s
  j=TARGETS.index(t)
  for rect in native_rects(s):
   a,b,c,d=rect;identity=(r.get('decodedSHA256',r['sha256']),t,rect)
   if identity in seen:continue
   seen.add(identity);rgb=np.full((256,256,3),114,np.uint8);rgb[:d-b,:c-a]=im[b:d,a:c,::-1];y=np.zeros((8,256,256),np.uint8);support=np.zeros_like(y);y[j,:d-b,:c-a]=m[b:d,a:c];support[j,:d-b,:c-a]=s[b:d,a:c]
   identifier=f'{len(items):06d}.npz';np.savez_compressed(folder/identifier,rgb=rgb,truth=y,support=support)
   items.append(dict(id=identifier,source=r['source'],sha256=r['sha256'],group=r['group'],split='train' if r['source']=='face' else r['split'],target=t,rect=rect,positivePixels=int(y.sum()),knownNegativePixels=int((support>y).sum()),completeROI=complete,labelOrigin=origin,sourceNativeSize=[r['width'],r['height']],inputSize=256,noUpsampling=True,fullFaceRequired=False,augmentationSquaresUnknownPixels=int(unknown.sum())))
 for r in rows:
  d=by[r['reviewKey']]
  if not d['rightsEligible'] or d.get('excludedReason'):continue
  for t in d['acceptedTargets']:
   if t not in TARGETS:continue
   if r['source']=='care' and t=='acne':
    fields.append(dict(sha256=r['sha256'],group=r['group'],split=r['split'],source=r['source'],absolutePath=r['absolutePath'],supervision='weak affected-field/photo presence only',individualPimpleCountTruth=False,pixelMaskTruth=False));continue
   m=mask(r,t)
   if m.any():add(r,t,m,m,False,'reviewed source polygon/RLE partial positive; unknown has zero loss')
 # Preserve actual complete previous native support; append an eighth unknown
 # channel instead of converting old photo labels into pixel negatives.
 old=json.loads((OUT/'mask-data.json').read_text('utf8'));oldtargets=['acne','oil','redness','tone','lines','dark','bags']
 for r in old['rows']:
  if not r['completeROI']:continue
  with np.load(OUT/'mask/tensors'/r['id']) as v:
   oldj=oldtargets.index(r['target']);j=TARGETS.index(r['target']);truth=np.zeros((8,256,256),np.uint8);support=np.zeros_like(truth);truth[j]=v['truth'][oldj];support[j]=v['support'][oldj];rgb=v['rgb'].copy()
  identifier=f'{len(items):06d}.npz';np.savez_compressed(folder/identifier,rgb=rgb,truth=truth,support=support);items.append({**r,'id':identifier,'inheritedWholeROIScope':'previous approximate engineering anatomical ROI; skin-hole re-review remains pending'})
 trgroups={r['group'] for r in items if r['split']=='train'}
 for r in items:
  if r['group'] in trgroups:r['split']='train'
 assert not trgroups&{r['group'] for r in items if r['split']=='validation'}
 counts={t:{s:dict(photos=len({r['sha256'] for r in items if r['target']==t and r['split']==s}),groups=len({r['group'] for r in items if r['target']==t and r['split']==s}),tiles=sum(r['target']==t and r['split']==s for r in items)) for s in ['train','validation','test']} for t in TARGETS}
 write('continuation-mask-data.json',dict(rows=items,targets=TARGETS,counts=counts,reviewReceipts=receipts,parentTrainingLedgerSHA256=sha(OUT/'mask-data.json'),weakAcneFields=fields,boxesAreMasks=False,CSVZerosArePixelNegatives=False,independentFinal=False,dryMeaning='visible source-labelled local flaking/texture, not physical moisture',requiresWholeValidSkinROIRecheck=True,trainingStarted=False));print(json.dumps(dict(counts=counts,weakAcneFields=len(fields))),flush=True)

if __name__=='__main__':main()
