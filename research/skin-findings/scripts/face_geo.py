"""Eye-bag and sagging appearance proxies on light-corrected front photos.
bags: under-eye band darker / more shadowed than the cheek below it (after light correction) + lower-lid bulge depth (3D).
sag : jowl/lower-face descent from 3D landmarks: how far the jaw contour lies below/behind the cheek line, scaled by face size."""
import json,sys,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
import light as Lt
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
LID={'L':[33,7,163,144,145,153,154,155,133],'R':[263,249,390,373,374,380,381,382,362]}
ORB={'L':[226,111,117,118,119,120,121,128,245],'R':[446,340,346,347,348,349,350,357,465]}
CHK={'L':[117,118,119,100,142,203,206,216,212,214,192,213,147,123],'R':[346,347,348,329,371,423,426,436,432,434,416,433,376,352]}
st=[p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status']=='approved']; rows=[]
for p in st:
  img=cv2.imread(f"{S}/gen/approved/{p['id']}/{p['id']}-front.png"); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  if not r.face_landmarks: continue
  R=Lt.analyze(img,r.face_landmarks[0]); T=Lt.lab(R['corr'][...,::-1]); L=T[0]; P=R['P']; H,W=L.shape; ok=R['img'].max(-1)<0.97
  fw=P[:,0].max()-P[:,0].min(); f={}
  bands=[];zb=[]
  for s in 'LR':
    band=np.zeros((H,W),np.uint8); cv2.fillPoly(band,[np.vstack([P[LID[s],:2],P[ORB[s][::-1],:2]]).astype(np.int32)],1)
    ck=np.zeros((H,W),np.uint8); cv2.fillPoly(ck,[P[CHK[s],:2].astype(np.int32)],1)
    b=(band>0)&ok; c=(ck>0)&ok
    if b.sum()>50 and c.sum()>50: bands.append(np.median(L[c])-np.median(L[b]))
    # bulge: lower lid points vs orbital rim depth (z toward camera is negative in MediaPipe)
    zb.append((P[ORB[s],2].mean()-P[LID[s],2].mean())/fw)
  f['bag_dark']=float(np.mean(bands)) if bands else None; f['bag_bulge']=float(np.mean(zb))
  # sagging: jaw contour points vs cheekbone; jowl = lower-face width near mouth corners relative to jaw angle width
  jaw=[172,136,150,149,176,148,152,377,400,378,379,365,397]; cheek=[234,454]; mouth=[61,291]
  f['sag_lowwidth']=float(np.linalg.norm(P[58,:2]-P[288,:2])/np.linalg.norm(P[234,:2]-P[454,:2]))
  f['sag_chin']=float((P[152,1]-P[2,1])/fw)
  f['sag_jawdepth']=float((P[jaw,2].mean()-P[cheek,2].mean())/fw)
  rows.append(dict(id=p['id'],age=p['age'],bags='göz altı torbası' in p['extras'],f=f))
json.dump(rows,open(f'{S}/rf/face_geo.json','w')); print('rows',len(rows))
