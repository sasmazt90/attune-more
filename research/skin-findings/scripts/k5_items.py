import json,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
exec(open('build_items.py').read().split("lm=vision")[0])
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=TASK),num_faces=1))
import os; CP=os.environ.get('CP','cp5'); BASE=int(os.environ.get('BASE','20000')); OUT=os.environ.get('TAG','_k5')
P=json.load(open(f'{S}/{CP}/prep.json')); items=[]
for k,v in sorted(P.items()):
  if not v.get('face'): print('noface',k); continue
  p=f"{S}/{CP}/crop/{v['crop']}"; bgr=cv2.imread(p); h,w=bgr.shape[:2]
  r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)))
  if not r.face_landmarks: print('noface2',k); continue
  Pt=np.array([[q.x*w,q.y*h] for q in r.face_landmarks[0]])
  items.append(dict(id=BASE+len(items),key=k,set='k',split='k',path=p,w=w,h=h,regions={kk:Pt[vv].round(1).tolist() for kk,vv in REG.items()},holes={kk:Pt[vv].round(1).tolist() for kk,vv in HOLES.items()},gt={},classes=[],faceW=round(float(Pt[:,0].max()-Pt[:,0].min()),1),yaw=v['yawDeg']))
json.dump(items,open(f'{S}/rf/items{OUT}.json','w')); print(len(items))
