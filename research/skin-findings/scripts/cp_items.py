import json,os,numpy as np,cv2,mediapipe as mp,re
from mediapipe.tasks.python import vision, BaseOptions
exec(open('build_items.py').read().split("lm=vision")[0])
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=TASK),num_faces=1))
P=json.load(open(f'{S}/cp/prep.json')); P2=json.load(open(f'{S}/cp2/prep.json'))
src={k:f"{S}/cp/crop/{v['crop']}" for k,v in P.items() if v.get('face')}
for k,v in P2.items():
  base=k.replace('_v2','').rsplit('.',1)[0]
  for old in [o for o in list(src) if o.rsplit('.',1)[0].replace('_png','')==base]: src.pop(old)
  src[k]=f"{S}/cp2/crop/{v['crop']}"
items=[]
for k,p in sorted(src.items()):
  bgr=cv2.imread(p); h,w=bgr.shape[:2]; r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)))
  if not r.face_landmarks: continue
  Pt=np.array([[q.x*w,q.y*h] for q in r.face_landmarks[0]])
  items.append(dict(id=len(items),key=k,set='cp',split='cp',path=p,w=w,h=h,regions={kk:Pt[v].round(1).tolist() for kk,v in REG.items()},holes={kk:Pt[v].round(1).tolist() for kk,v in HOLES.items()},gt={},classes=[],faceW=round(float(Pt[:,0].max()-Pt[:,0].min()),1),yaw=(P.get(k) or P2.get(k))['yawDeg']))
json.dump(items,open(f'{S}/rf/items_cp.json','w')); print(len(items))
