"""Prepare criterion-specific genuine negative support as a new frozen phase.

Does not modify the running ledger, checkpoint, source order or user records.
"""
import collections,json,sys
from pathlib import Path
import cv2,numpy as np
from expanded_sources import ROOT,OUT,sha,write
from expanded_mask_data import native_rects
from source_skin_support import known_skin_scope
from prepare_continuation_masks import augmentation_unknown

def main():
 dest=OUT/'negative-expanded-mask-data.json'
 if dest.exists():print('Existing phase ledger preserved');return
 sys.path.insert(0,str(ROOT/'.runtime/python-packages'))
 import mediapipe as mp
 from mediapipe.tasks.python import BaseOptions
 from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions
 detector=FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')),num_faces=2))
 previous=OUT/'continuation-valid-skin-data.json';data=json.loads(previous.read_text('utf8'));rows=data['rows'].copy();targets=data['targets'];folder=OUT/'negative-expanded-native/tensors';folder.mkdir(parents=True,exist_ok=True)
 sources=json.loads((OUT/'negative-expansion/candidates.json').read_text('utf8'))['rows'];decisions=json.loads((OUT/'negative-expansion/review.json').read_text('utf8'))['rows'];by={r['sha256']:r for r in sources};prepared=[];rejected=[]
 # Links preserve the exact original tensors without doubling their disk use.
 for r in rows:
  src=OUT/data['tensorFolder']/r['id'];link=folder/r['id']
  if not link.exists():__import__('os').link(src,link)
 for d in decisions:
  if not d['rightsEligible'] or not d['negativeTargets']:continue
  r=by[d['sha256']];assert r['split']!='test' and sha(Path(r['absolutePath']))==r['sha256'];im=cv2.imread(r['absolutePath']);h,w=im.shape[:2]
  found=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
  if len(found.face_landmarks)!=1:rejected.append(dict(sha256=r['sha256'],reason='SINGLE_FACE_NOT_OBSERVED'));continue
  p=[dict(x=v.x,y=v.y,z=v.z) for v in found.face_landmarks[0]];face_width=abs(p[454]['x']-p[234]['x'])*w
  if face_width<180:rejected.append(dict(sha256=r['sha256'],reason='INSUFFICIENT_NATIVE_FACE_DETAIL',nativeFaceWidth=face_width));continue
  r={**r,'landmarks':p,'height':h,'width':w};skin=known_skin_scope(r,im).astype(bool)&~augmentation_unknown(im)
  pp=np.array([[v['x']*w,v['y']*h] for v in p]);eyes=np.zeros((h,w),np.uint8)
  for left,right in [(33,133),(263,362)]:
   span=abs(pp[left,0]-pp[right,0]);cx=pp[[left,right],0].mean();cy=max(pp[left,1],pp[right,1]);cv2.rectangle(eyes,(int(cx-.8*span),int(cy-.15*span)),(int(cx+.8*span),int(cy+.85*span)),1,-1)
  accepted=[]
  for t in d['negativeTargets']:
   if t not in targets:continue
   # Eye targets have reviewed eye corridors only, never the whole face.
   support=skin&(eyes>0) if t in {'lines','bags','dark'} else skin
   if support.sum()<100:continue
   j=targets.index(t);count=0
   for rect in native_rects(support):
    a,b,c,e=rect;rgb=np.full((256,256,3),114,np.uint8);rgb[:e-b,:c-a]=im[b:e,a:c,::-1];truth=np.zeros((len(targets),256,256),np.uint8);known=np.zeros_like(truth);known[j,:e-b,:c-a]=support[b:e,a:c]
    identifier=f'{len(rows):06d}.npz';np.savez_compressed(folder/identifier,rgb=rgb,truth=truth,support=known)
    rows.append(dict(id=identifier,source=r['source'],sha256=r['sha256'],group=r['group'],split=r['split'],target=t,rect=rect,positivePixels=0,knownNegativePixels=int(known.sum()),completeROI=True,wholeValidSkinExpertReviewed=False,engineeringNegativeROIReviewed=True,negativePhotoForTarget=True,labelOrigin='actual criterion-specific visible absence engineering review; other targets unknown',sourceNativeSize=[w,h],inputSize=256,noUpsampling=True,fullFaceRequired=False));count+=1
   if count:accepted.append(t)
  prepared.append(dict(sha256=r['sha256'],group=r['group'],split=r['split'],targets=accepted,landmarks=p,nativeFaceWidth=face_width,negativePhotoForTarget=True))
 detector.close()
 train_groups={r['group'] for r in rows if r['split']=='train'};validation_groups={r['group'] for r in rows if r['split']=='validation'};assert not train_groups&validation_groups
 counts={t:{s:dict(addedNegativePhotos=len({r['sha256'] for r in rows[len(data['rows']):] if r['target']==t and r['split']==s}),addedNegativeROIs=sum(r['target']==t and r['split']==s for r in rows[len(data['rows']):])) for s in ['train','validation']} for t in targets}
 write('negative-expanded-mask-data.json',{**data,'version':'native-target-negative-expansion-phase-v1','rows':rows,'tensorFolder':'negative-expanded-native/tensors','parentLedgerSHA256':sha(previous),'negativeReviewSHA256':sha(OUT/'negative-expansion/review.json'),'addedNegativeCounts':counts,'counts':{t:{s:dict(photos=len({r['sha256'] for r in rows if r['target']==t and r['split']==s}),groups=len({r['group'] for r in rows if r['target']==t and r['split']==s}),tiles=sum(r['target']==t and r['split']==s for r in rows)) for s in ['train','validation','test']} for t in targets},'preparedNegativePhotos':prepared,'rejectedPhotos':rejected,'trainingExposure':False,'phaseChangeRequired':True,'sourceOrderMayNotBeChangedMidEpoch':True,'newFinalTestOpened':False})
 print(json.dumps(counts),flush=True)
if __name__=='__main__':main()
