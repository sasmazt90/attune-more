"""In-domain eye-bag and cold-sore classifiers: DINOv2-small embeddings of landmark crops (under-eye band per side,
lip zone), logistic regression, grouped by person (leave-persons-out). All 3 poses used; person score = max."""
import json,re,numpy as np,cv2,torch,mediapipe as mp
from PIL import Image
from mediapipe.tasks.python import vision, BaseOptions
from transformers import AutoImageProcessor, AutoModel
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'; torch.set_num_threads(4)
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
proc=AutoImageProcessor.from_pretrained('facebook/dinov2-small'); dm=AutoModel.from_pretrained('facebook/dinov2-small').eval()
UNDER={'L':[33,7,163,144,145,153,154,155,133,128,121,120,119,118,117,111,226],'R':[263,249,390,373,374,380,381,382,362,357,350,349,348,347,346,340,446]}
LIP=[61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146]
st=[p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status']=='approved']
def crop(img,P,idx,pad):
  x0,y0=P[idx].min(0); x1,y1=P[idx].max(0); fw=P[:,0].max()-P[:,0].min(); p=pad*fw
  c=img[int(max(0,y0-p)):int(y1+p),int(max(0,x0-p)):int(x1+p)]; return cv2.cvtColor(cv2.resize(c,(224,224)),cv2.COLOR_BGR2RGB)
rows=[]
for p in st:
  for v in ('front','side_1','side_2'):
    img=cv2.imread(f"{S}/gen/approved/{p['id']}/{p['id']}-{v}.png"); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks: continue
    h,w=img.shape[:2]; P=np.array([[q.x*w,q.y*h] for q in r.face_landmarks[0]])
    for s in ('L','R'): rows.append(dict(kid=p['id'],task='bag',crop=crop(img,P,UNDER[s],0.03)))
    rows.append(dict(kid=p['id'],task='lip',crop=crop(img,P,LIP,0.04)))
E=[]
with torch.no_grad():
  for i in range(0,len(rows),32):
    o=dm(**proc(images=[Image.fromarray(r['crop']) for r in rows[i:i+32]],return_tensors='pt')).last_hidden_state
    E.append(torch.cat([o[:,0],o[:,1:].mean(1)],1).numpy())
E=np.concatenate(E)
lab={'bag':lambda p:'göz altı torbası' in p['extras'],'lip':lambda p:'dudakta uçuk' in p['extras']}
AG={'18-25':0,'26-35':1,'36-45':2,'46-55':3,'56-65':4,'66+':5}; SP={p['id']:p for p in st}
for task in ('bag','lip'):
  ix=[i for i,r in enumerate(rows) if r['task']==task]; X=E[ix]; G=np.array([rows[i]['kid'] for i in ix]); y=np.array([lab[task](SP[g]) for g in G])
  oof=np.zeros(len(ix))
  for tr,te in GroupKFold(10).split(X,y,G):
    m=make_pipeline(StandardScaler(),LogisticRegression(C=0.02,max_iter=4000,class_weight='balanced')).fit(X[tr],y[tr]); oof[te]=m.predict_proba(X[te])[:,1]
  ks=sorted(set(G)); ps=np.array([oof[G==k].max() for k in ks]); yp=np.array([lab[task](SP[k]) for k in ks]); age=np.array([AG[SP[k]['age']] for k in ks])
  def p80(yy,ss):
    for t in np.sort(np.unique(ss)):
      kk=ss>=t
      if kk.sum()>=3 and yy[kk].mean()>=.8: return f'eşik {t:.2f} R={(kk&yy).sum()/yy.sum():.2f}'
    return 'yok'
  print(task,'kişi AUC',round(roc_auc_score(yp,ps),3),'| P≥0.8:',p80(yp,ps),'| pozitif',yp.sum())
  if task=='bag': o=age>=3; print('  yalnız 46+ AUC',round(roc_auc_score(yp[o],ps[o]),3),'| P≥0.8:',p80(yp[o],ps[o]))
