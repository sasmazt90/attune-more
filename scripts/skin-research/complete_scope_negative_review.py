"""Append two already reviewed acne-negative source ROIs, without duplicate photos."""
import json,os
from pathlib import Path
import cv2,numpy as np
from PIL import Image
from expanded_sources import OUT,sha,write
from source_skin_support import known_skin_scope
from expanded_mask_data import native_rects

def main():
 dest=OUT/'scope-v4-mask-data.json'
 if dest.exists():print('Final immutable scope ledger preserved');return
 prior=OUT/'scope-v3-mask-data.json';data=json.loads(prior.read_text());rows=data['rows'].copy();folder=OUT/'scope-v4-native/tensors';folder.mkdir(parents=True,exist_ok=True)
 for r in rows:
  src=OUT/data['tensorFolder']/r['id'];dst=folder/r['id']
  if not dst.exists():os.link(src,dst)
 sources=json.loads((OUT/'negative-expanded-detector-data.json').read_text())['rows'];selected=json.loads((OUT/'interim-diagnosis/detector-source-selection.json').read_text())['rows'][2:];reviews=[]
 for i,s in enumerate(selected):
  r=next(r for r in sources if r['sha256']==s['sha256']);assert r['split']=='validation' and r['negativeROI'];assert sha(Path(r['absolutePath']))==r['sha256'];im=cv2.imread(r['absolutePath']);h,w=im.shape[:2];p=np.array([[v['x']*w,v['y']*h] for v in r['landmarks']]);region=np.zeros((h,w),np.uint8);cv2.fillConvexPoly(region,cv2.convexHull(np.rint(p[[108,151,337,296,9,66]]).astype(np.int32)),1);support=(region>0)&known_skin_scope(r,im).astype(bool)
  for rect in native_rects(support):
   a,b,c,d=rect;rgb=np.full((256,256,3),114,np.uint8);rgb[:d-b,:c-a]=im[b:d,a:c,::-1];y=np.zeros((8,256,256),np.uint8);known=np.zeros_like(y);known[0,:d-b,:c-a]=support[b:d,a:c];identifier=f'{len(rows):06d}.npz';np.savez_compressed(folder/identifier,rgb=rgb,truth=y,support=known)
   rows.append(dict(id=identifier,sha256=r['sha256'],source=r['source'],group=r['group'],split=r['split'],target='acne',sourceNativeSize=[w,h],rect=rect,positivePixels=0,knownNegativePixels=int(known.sum()),completeROI=True,engineeringNegativeROIReviewed=True,labelOrigin='visually reviewed central forehead without apparent active pimple; ordinary wrinkles/pigment remain acne-negative engineering confounders',expertLabels=False,inputSize=256,noUpsampling=True))
  pic=im[:,:,::-1].copy();pic[support]=(.65*pic[support]+.35*np.array([0,255,255])).astype(np.uint8);path=OUT/'interim-diagnosis/negative-review-v2'/f'acne-support-v4-{i}.png';Image.fromarray(pic).save(path)
  reviews.append(dict(sha256=r['sha256'],group=r['group'],split=r['split'],sourcePath=r['absolutePath'],reviewedNegativeSupportPixels=int(support.sum()),target='acne',wholePhotoHealthy=False,expertLabels=False,sourceClassUsed=False,predictionsUsedAsLabels=False,reviewBasis='original photo and existing interim crop/overlay; actual ROI overlay checked before exposure',supportOverlaySHA256=sha(path)))
 assert not {r['group'] for r in rows if r['split']=='train'}&{r['group'] for r in rows if r['split']=='validation'}
 write('interim-diagnosis/negative-review-v2/final-review-v4.json',dict(version='regional-negative-engineering-review-v4',parentReviewSHA256=sha(OUT/'interim-diagnosis/negative-review-v2/review-v3.json'),additionalAcneReviews=reviews,allSupportV3BoardsViewed=True,sourceFamilySplitPreserved=True,fullPositiveROIReviewStillPending=True,finalPixelsOpened=False))
 write('scope-v4-mask-data.json',{**data,'version':'reviewed-regional-negative-positive-preserving-v4','rows':rows,'tensorFolder':'scope-v4-native/tensors','parentPreparedLedgerSHA256':sha(prior),'finalNegativeReviewSHA256':sha(OUT/'interim-diagnosis/negative-review-v2/final-review-v4.json'),'addedAcneValidationNegativePhotos':len(reviews),'preparedButTrainingExposure':False})
 print('FINAL SCOPE DATA',len(rows),flush=True)
if __name__=='__main__':main()
