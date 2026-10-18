"""Native-resolution, target-specific mask supervision, frozen once prepared.

Boxes and CSV presence never enter truth masks. A partial polygon contributes
positive pixels only. Exhaustive engineering ROIs are explicitly distinguished.
The old complete Pimple negatives now contribute real acne-negative pixels.
"""
import collections,json,sys
from pathlib import Path
import cv2,numpy as np
from expanded_sources import OUT,PREVIOUS,ROOT,mask,sha,write,LABELS
from selected_sources import TARGETS
from train_selected_local import reviewed,target_scope
from review_selected_sources import annotation_mask

def native_rects(m):
 h,w=m.shape;rects=[]
 # Native overlapping tiles. No global face downsampling, no fabricated detail.
 for y in sorted(set([*range(0,max(1,h-255),192),max(0,h-256)])):
  for x in sorted(set([*range(0,max(1,w-255),192),max(0,w-256)])):
   rect=(x,y,min(w,x+256),min(h,y+256))
   if m[rect[1]:rect[3],rect[0]:rect[2]].any():rects.append(rect)
 return rects

def prepare():
 if (OUT/'mask-data.json').exists():return json.loads((OUT/'mask-data.json').read_text('utf8'))
 c=json.loads((OUT/'candidates.json').read_text('utf8'))['rows'];ds=json.loads((OUT/'decisions.json').read_text('utf8'))['rows'];by={d['reviewKey']:d for d in ds}
 cache=OUT/'mask/tensors';cache.mkdir(parents=True,exist_ok=True);items=[];seen=set();facegroups={r['group'] for r in c if r['source']=='face'}
 def add(r,t,m,s,complete,origin):
  if not s.any():return
  image=cv2.imread(r['absolutePath']);assert image is not None and sha(Path(r['absolutePath']))==r['sha256'];j=TARGETS.index(t)
  for rect in native_rects(s):
   a,b,ex,ey=rect;signature=(r['decodedSHA256'] if 'decodedSHA256' in r else r['sha256'],t,rect)
   if signature in seen:continue
   seen.add(signature);h=ey-b;w=ex-a;x=np.full((256,256,3),114,np.uint8);x[:h,:w]=image[b:ey,a:ex,::-1]
   y=np.zeros((len(TARGETS),256,256),np.uint8);support=np.zeros_like(y);y[j,:h,:w]=m[b:ey,a:ex];support[j,:h,:w]=s[b:ey,a:ex]
   identifier=f'{len(items):06d}.npz';np.savez_compressed(cache/identifier,rgb=x,truth=y,support=support)
   split='train' if r['group'] in facegroups else r['split']
   items.append(dict(id=identifier,source=r['source'],sha256=r['sha256'],group=r['group'],split=split,target=t,rect=rect,positivePixels=int(y[j].sum()),knownNegativePixels=int((support[j]>y[j]).sum()),knownPixels=int(support[j].sum()),completeROI=complete,labelOrigin=origin,sourceNativeSize=[r['width'],r['height']],inputSize=256,noUpsampling=True,fullFaceRequired=False))
 for r in c:
  d=by.get(r['reviewKey'])
  if not d or not d['rightsEligible'] or d.get('excludedReason'):continue
  for t in d['acceptedTargets']:
   if t not in TARGETS:continue
   m=mask(r,t)
   if m.any():add(r,t,m,m,False,'reviewed genuine source polygon/RLE; unknown omitted')
 for r in reviewed():
  d=r['reviewDecision'];complete=set(d.get('completeMaskTargets',[]))
  if d.get('completePimpleROI') and d['appearanceLabels'].get('acne')=='negative':complete.add('acne')
  for t in complete:
   if t not in TARGETS:continue
   scope=target_scope(r,t);m=annotation_mask(r,t)*scope;add(r,t,m,scope,True,'complete visible anatomical engineering ROI; not expert or independent test')
 # A group must stay on one side, including all target-specific crops.
 training={r['group'] for r in items if r['split']=='train'}
 for r in items:
  if r['group'] in training:r['split']='train'
 assert not ({r['group'] for r in items if r['split']=='train'}&{r['group'] for r in items if r['split']=='validation'})
 counts={}
 for t in TARGETS:
  counts[t]={}
  for split in ['train','validation','test']:
   rs=[r for r in items if r['target']==t and r['split']==split]
   counts[t][split]=dict(images=len({r['sha256'] for r in rs}),groups=len({r['group'] for r in rs}),ROIs=len(rs),positiveImages=len({r['sha256'] for r in rs if r['positivePixels']}),fullyReviewedNegativeImages=len({r['sha256'] for r in rs if r['completeROI'] and not r['positivePixels']}),completeROIs=sum(r['completeROI'] for r in rs),partialPositiveROIs=sum(not r['completeROI'] for r in rs),positivePixels=sum(r['positivePixels'] for r in rs),knownNegativePixels=sum(r['knownNegativePixels'] for r in rs))
 result=dict(rows=items,counts=counts,candidatesSHA256=sha(OUT/'candidates.json'),decisionsSHA256=sha(OUT/'decisions.json'),oldReviewsSHA256=sha(PREVIOUS/'review/decisions.json'),sigmoidIndependent=True,unknownZero=True,boxesAreMasks=False,faceCollageValidationQuarantined=True,componentRelationsResolved=False,independentFinal=False)
 write('mask-data.json',result);write('mask/tensor-overlap.json',dict(rows=items));print(json.dumps(counts),flush=True);return result

if __name__=='__main__':prepare()
