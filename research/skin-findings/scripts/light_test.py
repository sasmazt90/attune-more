"""(a) stability: relight each front photo synthetically (other light direction, colour cast, vignette) and compare
tone metrics with/without correction; (b) pigment discrimination: melasma/sun-spot labelled vs not."""
import json,sys,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
from sklearn.metrics import roc_auc_score
import light as Lt
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
st=[p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status']=='approved']
N=int(sys.argv[1]) if len(sys.argv)>1 else len(st)
def metric(R,corrected=True):
  if not corrected: R=dict(R,corr=R['lin'])
  T=Lt.tone_maps(R); M=Lt.region_masks(R); out={}
  for k,m in M.items():
    if m.sum()<200: continue
    out[k]=dict(pig=float(T['pigment'][m].mean()),dark=float(((T['dev']<-6)&m)[m].mean()),Lsd=float(np.std(T['L'][m])))
  return out
rng=np.random.default_rng(0); rows=[]
for p in st[:N]:
  img=cv2.imread(f"{S}/gen/approved/{p['id']}/{p['id']}-front.png"); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  if not r.face_landmarks: continue
  R=Lt.analyze(img,r.face_landmarks[0])
  # synthetic relight in the same frame: new directional light from a random side + colour cast + vignette
  H,W=R['skin'].shape; l=np.array([rng.choice([-1,1])*rng.uniform(.5,.9),rng.uniform(-.3,.3),.6]); l/=np.linalg.norm(l)
  shade=np.clip(.35+.9*np.clip((R['N']@l),0,None),0.2,1.6)
  yy,xx=np.mgrid[0:H,0:W]; vig=1-.35*(((xx-W/2)/(W/2))**2+((yy-H/2)/(H/2))**2)
  cast=np.array([rng.uniform(.85,1.1),1,rng.uniform(.85,1.1)])
  lin2=np.clip(R['lin']*(shade*vig)[...,None]*cast,0,1)
  R2=Lt.fit(lin2,R['N'],R['skin'],R['P'])
  m0,m1=metric(R),metric(R2); n0,n1=metric(R,False),metric(R2,False)
  pig=('melazma (yanaklarda)' in p['extras'] or 'güneş lekesi' in p['extras'])
  rows.append(dict(id=p['id'],pig=pig,tone=p['tone'],c0=m0,c1=m1,n0=n0,n1=n1,light=R['light'].tolist()))
json.dump(rows,open(f'{S}/rf/light_test.json','w'))
def stab(a,b,key):
  d=[abs(a[k][key]-b[k][key]) for k in a if k in b]; return np.mean(d)
print('n',len(rows))
for key in ('pig','dark'):
  print(f"{key}: ortalama değişim yapay ışıkla | düzeltmeli={np.mean([stab(r['c0'],r['c1'],key) for r in rows]):.3f} düzeltmesiz={np.mean([stab(r['n0'],r['n1'],key) for r in rows]):.3f}")
for mode in ('c0','c1','n0','n1'):
  y=[r['pig'] for r in rows]; s=[np.mean([r[mode][k]['pig'] for k in ('cheek_imgL','cheek_imgR','forehead') if k in r[mode]]) for r in rows]
  print(mode,'leke AUC',round(roc_auc_score(y,s),3),'pozitif',sum(y))
