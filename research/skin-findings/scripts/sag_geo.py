import json, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
from sklearn.metrics import roc_auc_score
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
st={p['id']:p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status']=='approved' and int(p['id'][2:])>=181}
E={'L':dict(inner=133,outer=33,up=159,lo=145,brow=105,crease=27),'R':dict(inner=362,outer=263,up=386,lo=374,brow=334,crease=257)}
rows={}
for kid,p in sorted(st.items()):
  img=cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png'); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  if not r.face_landmarks: continue
  h,w=img.shape[:2]; P=np.array([[q.x*w,q.y*h] for q in r.face_landmarks[0]])
  c=(P[33]+P[263])/2; v=P[263]-P[33]; ang=np.arctan2(v[1],v[0]); R=np.array([[np.cos(-ang),-np.sin(-ang)],[np.sin(-ang),np.cos(-ang)]]); Q=(P-c)@R.T
  iod=np.linalg.norm(v); f={}
  for s,e in E.items():
    ew=abs(Q[e['outer'],0]-Q[e['inner'],0]); sgn=1
    f.setdefault('tilt',[]).append((Q[e['inner'],1]-Q[e['outer'],1])/ew)          # >0: outer corner higher
    f.setdefault('aperture',[]).append((Q[e['lo'],1]-Q[e['up'],1])/ew)
    f.setdefault('brow_lid',[]).append((Q[e['up'],1]-Q[e['brow'],1])/ew)
    f.setdefault('crease_lid',[]).append((Q[e['up'],1]-Q[e['crease'],1])/ew)
  f={k:float(np.mean(v)) for k,v in f.items()}
  # cheek / midface: mouth corner and cheek low point vs eye line, nasolabial
  f['mouth_corner_drop']=float(((Q[61,1]+Q[291,1])/2-(Q[0,1]))/iod)
  f['cheek_low']=float(((Q[205,1]+Q[425,1])/2)/iod)
  f['jaw_width_ratio']=float(abs(Q[172,0]-Q[397,0])/abs(Q[234,0]-Q[454,0]))
  rows[kid]=dict(f=f,ex=p['extras'])
json.dump(rows,open(f'{S}/rf/sag_geo.json','w'),ensure_ascii=False)
for lab in ['sarkma: göz','sarkma: göz dış köşe','sarkma: yanak']:
  ks=list(rows); y=np.array([lab in rows[k]['ex'] for k in ks])
  print(lab,'pozitif',y.sum(),'/',len(ks),' '.join(f"{n}={max(roc_auc_score(y,[rows[k]['f'][n] for k in ks]),1-roc_auc_score(y,[rows[k]['f'][n] for k in ks])):.2f}" for n in rows[ks[0]]['f']))
