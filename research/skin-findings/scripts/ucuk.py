import json,numpy as np,cv2,collections,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
I=[it for it in json.load(open('items.json')) if it['set']=='findings']; P=json.load(open('pred_findings.json'))
cats={}
for sp in ('valid','test'):
  J=json.load(open(f'{S}/evalds/findings/{sp}/_annotations.coco.json')); cats=J['categories']
  for im in J['images']:
    for it in I:
      if it['path'].endswith(f"/{sp}/{im['file_name']}"): it['gtb']=[(next(c['name'] for c in cats if c['id']==a['category_id']),[a['bbox'][0],a['bbox'][1],a['bbox'][0]+a['bbox'][2],a['bbox'][1]+a['bbox'][3]]) for a in J['annotations'] if a['image_id']==im['id']]
UC=[c['id'] for c in cats if c['name']=='Ucuk']
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
LIPS=[61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146]
def iou(p,q):
  ix=max(0,min(p[2],q[2])-max(p[0],q[0]));iy=max(0,min(p[3],q[3])-max(p[1],q[1]));i=ix*iy
  return i/max((p[2]-p[0])*(p[3]-p[1])+(q[2]-q[0])*(q[3]-q[1])-i,1e-9)
from PIL import Image
res={}
for thr in (0.3,0.45):
 for filt in (False,True):
  tp=fp=fn=0; gtin=gtout=0
  for it in I:
    img=np.array(Image.open(it['path']).convert('RGB')); h,w=img.shape[:2]
    r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(img)))
    if not r.face_landmarks: continue
    Pt=np.array([[q.x*w,q.y*h] for q in r.face_landmarks[0]]); fw=Pt[:,0].max()-Pt[:,0].min()
    zone=np.zeros((h,w),np.uint8); cv2.fillPoly(zone,[Pt[LIPS].astype(np.int32)],1); zone=cv2.dilate(zone,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(int(fw*0.24)|1,int(fw*0.24)|1)))
    inz=lambda b:zone[min(h-1,max(0,int((b[1]+b[3])/2))),min(w-1,max(0,int((b[0]+b[2])/2)))]>0
    G=[b for c,b in it.get('gtb',[]) if c=='Ucuk']
    gtin+=sum(inz(b) for b in G); gtout+=sum(not inz(b) for b in G)
    Pp=[b for c,s,b in P[str(it['id'])] if c in UC and s>=thr and (not filt or inz(b))]; used=set()
    for b in Pp:
      best=max(((iou(b,g),j) for j,g in enumerate(G) if j not in used),default=(0,-1))
      if best[0]>=0.3: tp+=1; used.add(best[1])
      else: fp+=1
    fn+=len(G)-len(used)
  Pr=tp/max(tp+fp,1); R=tp/max(tp+fn,1)
  print(f"thr={thr} lipFilter={filt} tp={tp} fp={fp} fn={fn} P={Pr:.3f} R={R:.3f} F1={2*Pr*R/max(Pr+R,1e-9):.3f} | GT uçuk in lip zone={gtin} outside={gtout}")
