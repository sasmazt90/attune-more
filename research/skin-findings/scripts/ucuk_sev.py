"""Cold sore size: lesion pixels on/around the lips (redder than the lip median or crusty texture), front + 20° photos."""
import json, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
from scipy.stats import spearmanr
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
OUT=[61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146]
R=json.load(open(f'{S}/rate/ratings.json')); K=json.load(open(f'{S}/rate/key.json'))
def feats(path):
    img=cv2.imread(path)
    if img is None: return None
    r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks: return None
    h,w=img.shape[:2]; P=np.array([[q.x*w,q.y*h] for q in r.face_landmarks[0]]); fw=P[:,0].max()-P[:,0].min()
    s=400/fw; img=cv2.resize(img,None,fx=s,fy=s); P*=s; h,w=img.shape[:2]
    lab=cv2.cvtColor(img,cv2.COLOR_BGR2LAB).astype(np.float32); L,a,b=lab[...,0],lab[...,1],lab[...,2]
    lip=np.zeros((h,w),np.uint8); cv2.fillPoly(lip,[P[OUT].astype(np.int32)],1)
    INN=[78,191,80,81,82,13,312,311,310,415,308,324,318,402,317,14,87,178,88,95]
    mline=np.zeros((h,w),np.uint8); cv2.polylines(mline,[P[INN].astype(np.int32)],True,1,7)
    zone=(cv2.dilate(lip,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))>0)&(mline==0); lipb=(lip>0)&(mline==0)
    am,bm,Lm=np.median(a[lipb]),np.median(b[lipb]),np.median(L[lipb]); asd=np.std(a[lipb])+1e-3; bsd=np.std(b[lipb])+1e-3
    mu=cv2.blur(L,(5,5)); sd=np.sqrt(np.maximum(cv2.blur(L*L,(5,5))-mu*mu,0)); tm=np.median(sd[lipb])+1e-3
    score=np.maximum((a-am)/asd,0)+np.maximum((b-bm)/bsd,0)+np.maximum(sd/tm-1,0)
    les=(zone&(score>3.0)).astype(np.uint8)
    les=cv2.morphologyEx(les,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
    n,cc,st,_c=cv2.connectedComponentsWithStats(les); la=lipb.sum(); big=0; tot=0
    for i in range(1,n):
        ar=st[i,cv2.CC_STAT_AREA]; bw,bh=st[i,cv2.CC_STAT_WIDTH],st[i,cv2.CC_STAT_HEIGHT]
        if ar<6 or ar/(bw*bh)<0.3 or max(bw,bh)/max(1,min(bw,bh))>4: les[cc==i]=0; continue
        big=max(big,ar); tot+=ar
    globals().update(dbg=(img,les,zone))
    return dict(frac=float(tot/la), big=float(big/la), smax=float(np.percentile(score[zone],99.5)), smean=float(score[les>0].mean()) if tot else 0.0)
out={}
for k in K['ucuk']:
    fs=[feats(f'{S}/gen/approved/{k}/{k}-{p}.png') for p in ('front','side_1','side_2')]
    fs=[f for f in fs if f]
    out[k]={n:float(np.mean([f[n] for f in fs])) for n in fs[0]}
    out[k].update({n+'_f':fs[0][n] for n in fs[0]})
json.dump(out,open(f'{S}/rf/ucuk_sev.json','w'))
y=np.array(R['ucuk'])
for n in out[K['ucuk'][0]]:
    v=np.array([out[k][n] for k in K['ucuk']]); print(f'{n:8s} rho={spearmanr(y,v).correlation:+.2f}')
