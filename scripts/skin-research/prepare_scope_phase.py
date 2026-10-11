"""Separate immutable phase: explicit reviewed negatives, positive-preserving skin.
No active ledger rewrite. Native rows/order indices remain a stable prefix.
"""
import collections,json,os
from pathlib import Path
import cv2,numpy as np,psutil
from PIL import Image,ImageDraw
from expanded_sources import ROOT,OUT,PREVIOUS,sha,write
from source_skin_support import anatomical_skin_scope,known_skin_scope
from expanded_mask_data import native_rects
from prepare_continuation_masks import TARGETS as DATA_TARGETS,augmentation_unknown
from selected_sources import TARGETS

# Reviewed source and eye detail boards, not class directory names or predictions.
# These are visible photographic absence judgments, never clinical healthy labels.
NEG={
 'dark':{4,9,14,49,57,58,62,67,69,70},
 'tone':{4,9,28,50,57,58,60,62,67,69,70,82,98},
 'redness':{4,9,28,50,57,58,62,67,69,70,82,98},
 'oil':{9,28,57,58,60,62,67,70,82,98}}

def main():
 for p in psutil.process_iter(['cmdline','cwd']):
  args=p.info['cmdline'] or []
  if any(Path(a).name in ['train_continuation_mask.py','train_expanded_detector.py','resume-and-monitor.py','train_scope_phase.py'] for a in args) and Path(p.info['cwd'] or '.').resolve()==ROOT:raise RuntimeError('ACTIVE_TRAINER_OWNERSHIP; preserve inputs')
 dest=OUT/'scope-v3-mask-data.json'
 if dest.exists():print('Immutable scope-v2 ledger preserved');return
 parent=OUT/'negative-expanded-mask-data.json';data=json.loads(parent.read_text());rows=[];folder=OUT/'scope-v3-native/tensors';folder.mkdir(parents=True,exist_ok=True)
 raw=json.loads((OUT/'continuation-mask-data.json').read_text());byraw={r['id']:r for r in raw['rows']}
 source={r['sha256']:r for r in json.loads((PREVIOUS/'review/candidates.json').read_text())['rows']}
 removed=collections.Counter();restored=collections.Counter();pending=[]
 for r in data['rows']:
  src=OUT/data['tensorFolder']/r['id'];target=folder/r['id']
  if r['target'] not in TARGETS or not r['completeROI'] or r.get('engineeringNegativeROIReviewed') is True:
   if not target.exists():os.link(src,target)
   rows.append(r);continue
  with np.load(src) as f:rgb=f['rgb'].copy();truth=f['truth'].copy();support=f['support'].copy()
  j=DATA_TARGETS.index(r['target']);prior=support.copy()
  # Approximate inherited negative support has no completed whole-skin review.
  # Keep labelled positives; all unreviewed pixels become unknown.
  if r['id'] in byraw and r['sha256'] in source:
   with np.load(OUT/raw.get('tensorFolder','continuation-mask/tensors')/r['id']) as f:y=f['truth'][j].copy()
   s=source[r['sha256']];im=cv2.imread(s['absolutePath']);assert sha(Path(s['absolutePath']))==r['sha256']
   if len(s.get('landmarks',[]))>=468:
    a,b,c,d=r['rect'];anatomy=anatomical_skin_scope(s,im)[b:d,a:c]>0
    y[:d-b,:c-a]&=anatomy.astype(np.uint8)
    restored[(r['target'],r['split'])]+=int(((y>0)&(truth[j]==0)).sum());truth[j]=y
  support[j]=truth[j];removed[(r['target'],r['split'])]+=int((prior[j]>support[j]).sum())
  np.savez_compressed(target,rgb=rgb,truth=truth,support=support)
  rows.append({**r,'positivePixels':int(truth[j].sum()),'knownNegativePixels':0,'completeROI':False,
    'labelOrigin':'inherited labelled positive pixels only; anatomical non-skin excluded; filament cannot erase skin positives',
    'wholeValidSkinROIEngineeringReviewed':False,'negativeScopePending':True})
  pending.append(r['id'])
 details=json.loads((OUT/'interim-diagnosis/negative-review-v2/selected.json').read_text())['rows'];oldreview={r['sha256']:r for r in json.loads((OUT/'negative-expansion/review.json').read_text())['rows']}
 previous_negative={(r['sha256'],r['target']) for r in rows if r.get('engineeringNegativeROIReviewed') and r['knownNegativePixels']}
 reviews=[];added=[];preview=[]
 for r in details:
  index=r['reviewIndex'];assert oldreview[r['sha256']]['rightsEligible'] is True;assert sha(Path(r['absolutePath']))==r['sha256'];im=cv2.imread(r['absolutePath']);h,w=im.shape[:2]
  p=np.array([[v['x']*w,v['y']*h] for v in r['landmarks']]);skin=known_skin_scope(r,im).astype(bool)&~augmentation_unknown(im)
  for t,ids in NEG.items():
   if index not in ids or (r['sha256'],t) in previous_negative:continue
   scope=np.zeros((h,w),np.uint8)
   if t=='dark':
    # Lower lid skin only. Eye opening/lash line and brow remain unknown.
    for left,right in [(33,133),(263,362)]:
     span=abs(p[left,0]-p[right,0]);cx=p[[left,right],0].mean();cy=max(p[left,1],p[right,1]);cv2.rectangle(scope,(int(cx-.65*span),int(cy+.12*span)),(int(cx+.65*span),int(cy+.65*span)),1,-1)
    region='reviewed normal lower-lid skin, including ordinary crease/shadow confounders'
   else:
    ids_forehead=[108,151,337,296,9,66]
    cv2.fillConvexPoly(scope,cv2.convexHull(np.rint(p[ids_forehead]).astype(np.int32)),1);region='reviewed homogeneous central forehead; cheeks, spots, cosmetics and ambiguous shine outside unknown'
   support=(scope>0)&skin
   if support.sum()<100:continue
   review=dict(sha256=r['sha256'],group=r['group'],split=r['split'],sourcePath=r['absolutePath'],reviewIndex=index,target=t,
    negativeScope=region,expertLabels=False,wholePhotographHealthy=False,sourceClassUsed=False,predictionsUsed=False,
    rightsBasis=oldreview[r['sha256']]['rightsBasis'],reviewBoardSHA256=sha(OUT/'interim-diagnosis/negative-review-v2'/f'detail-{details.index(r)//6}.png'),supportPixels=int(support.sum()))
   reviews.append(review);j=DATA_TARGETS.index(t)
   for rect in native_rects(support):
    a,b,c,d=rect;rgb=np.full((256,256,3),114,np.uint8);rgb[:d-b,:c-a]=im[b:d,a:c,::-1];truth=np.zeros((8,256,256),np.uint8);known=np.zeros_like(truth);known[j,:d-b,:c-a]=support[b:d,a:c];identifier=f'{len(rows):06d}.npz';np.savez_compressed(folder/identifier,rgb=rgb,truth=truth,support=known)
    rows.append(dict(id=identifier,sha256=r['sha256'],group=r['group'],split=r['split'],source=r['source'],target=t,rect=rect,sourceNativeSize=[w,h],positivePixels=0,knownNegativePixels=int(known[j].sum()),completeROI=True,engineeringNegativeROIReviewed=True,expertLabels=False,labelOrigin=region,inputSize=256,noUpsampling=True))
   pic=im[:,:,::-1].copy();pic[support]=(.65*pic[support]+.35*np.array([0,255,255])).astype(np.uint8);preview.append((review,pic));added.append((t,r['split'],r['sha256']))
 # All old training records remain in exactly the same order, and new rows append.
 assert all(all(a[k]==b[k] for k in ['id','sha256','group','split','target','rect']) for a,b in zip(data['rows'],rows))
 assert not {r['group'] for r in rows if r['split']=='train'}&{r['group'] for r in rows if r['split']=='validation'}
 summary={t:{s:len({h for tt,ss,h in added if tt==t and ss==s}) for s in ['train','validation']} for t in TARGETS}
 review_receipt=dict(version='regional-negative-engineering-review-v2',rows=reviews,counts=summary,allOriginalAndFourDetailBoardsViewed=True,positiveAndNegativeTaskSpecific=True,finalPixelsOpened=False,ambiguousOilCauseNotLabelled=True,stockCosmeticProcessedLowDetailExcluded=True)
 review_receipt.update(version='regional-negative-engineering-review-v3',rejectedAfterSupportOverlayReview={78:'FOREHEAD_OCCLUDED_BY_HAIR',79:'DETAIL_INSUFFICIENT_FOR_CONFIDENT_NEGATIVE',85:'DETAIL_INSUFFICIENT_FOR_CONFIDENT_NEGATIVE',94:'DETAIL_INSUFFICIENT_FOR_CONFIDENT_NEGATIVE'},allNegativeSupportOverlaysRequireReview=True)
 write('interim-diagnosis/negative-review-v2/review-v3.json',review_receipt)
 for start in range(0,len(preview),12):
  sheet=Image.new('RGB',(1440,1400),'#0c1220');draw=ImageDraw.Draw(sheet)
  for i,(r,im) in enumerate(preview[start:start+12]):
   pic=Image.fromarray(im);pic.thumbnail((450,290));x=i%3*480;y=i//3*350;sheet.paste(pic,(x,y));draw.text((x,y+300),str(r['reviewIndex'])+' '+r['target']+' '+r['split'],fill='white')
  sheet.save(OUT/'interim-diagnosis/negative-review-v2'/f'support-v3-{start//12}.png')
 write('scope-v3-mask-data.json',{**data,'version':'reviewed-regional-negative-positive-preserving-v3','rows':rows,'tensorFolder':'scope-v3-native/tensors','parentLedgerSHA256':sha(parent),
  'negativeReviewV3SHA256':sha(OUT/'interim-diagnosis/negative-review-v2/review-v3.json'),'addedNegativeSourceCounts':summary,
  'unreviewedLegacyNegativeRowsNowUnknown':pending,'restoredSkinPositivePixels':[dict(target=t,split=s,pixels=n) for (t,s),n in restored.items()],
  'stableOldTrainingOrderPrefix':True,'oldCheckpointOptimizerOrderCursorRNGMustBePreserved':True,'finalOpened':False})
 print('NEW IMMUTABLE DATA',json.dumps(summary),flush=True)

if __name__=='__main__':main()
