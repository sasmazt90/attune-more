import json,re,collections,numpy as np,cv2,sys
sys.argv=['x']; import importlib.util
from paint_proto import render, PAINT
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
I={it['id']:it for it in json.load(open('items_cp.json'))}; F=json.load(open('feats_cp.json'))
To,Td=0.25,0.10
f=lambda r,k:r['f'][k]
O=lambda r:(f(r,'skinmap_Oily_max')+f(r,'regional_oily_max')+f(r,'findings_Yagli_Cilt_max')+min(1,f(r,'cv_shine')*8))/4
Dd=lambda r:f(r,'findings_Kuru_Cilt_max')
SENS=lambda r:(f(r,'skinmap_Redness_max')+f(r,'findings_Rozasea_max'))/2
INFL=lambda r:f(r,'acnes_papule_n35')+f(r,'acnes_pustule_n35')+f(r,'acnes_nodule_n35')
by=collections.defaultdict(dict)
for r in F: by[r['id']][r['region']]=r
def state(r):
  if r is None: return 'unmeasured'
  o,d=O(r),Dd(r); return 'oily' if o>=To else ('dry' if d>=Td else 'normal')
def subject(k):
  b=re.sub(r'(_v2)?\.(jpg|png)$','',k); b=re.sub(r'_png$','',b); return re.sub(r'_(front|left|right|side_1|side_2)$','',b)
subs=collections.defaultdict(list)
for i,it in I.items(): subs[subject(it['key'])].append(i)
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
out={}; tiles=[]
fs=cv2.FONT_HERSHEY_SIMPLEX
for s,ids in sorted(subs.items()):
  front=min(ids,key=lambda i:abs(I[i]['yaw'])); pos=[i for i in ids if I[i]['yaw']>10.5]; neg=[i for i in ids if I[i]['yaw']<-10.5]
  src={'forehead':(front,'forehead'),'nose':(front,'nose'),'chin':(front,'chin'),'rightCheek':(pos[0] if pos else front,'cheek_imgL'),'leftCheek':(neg[0] if neg else front,'cheek_imgR')}
  reg={}
  for rid,(i,rn) in src.items():
    r=by[i].get(rn); reg[rid]=dict(state=state(r),sensitive=bool(r and (SENS(r)>=0.45 or INFL(r)>=2)),oily=round(O(r),3) if r else None,dry=round(Dd(r),3) if r else None,sens=round(SENS(r),3) if r else None,infl=INFL(r) if r else None,src=I[i]['key'])
  st=[v['state'] for v in reg.values() if v['state']!='unmeasured']
  if len(st)<4: typ=None
  elif 'oily' in st and any(x in('dry','normal') for x in st): typ='Karma'
  elif all(x=='oily' for x in st): typ='Yağlı'
  elif 'dry' in st: typ='Kuru'
  else: typ='Normal'
  sens=any(v['sensitive'] for v in reg.values())
  label=(typ or 'Belirlenemedi')+(' ve hassas' if sens and typ else '')
  out[s]=dict(type=label,regions=reg)
  img=cv2.imread(I[front]['path']); res=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  im=render(img,res.face_landmarks[0],{k:v['state'] for k,v in reg.items()},{k for k,v in reg.items() if v['sensitive']})
  im=cv2.resize(im,(400,400)); txt=f"{s[:22]}: {label}"
  cv2.putText(im,txt,(6,22),fs,0.55,(0,0,0),3); cv2.putText(im,txt,(6,22),fs,0.55,(255,255,255),1); tiles.append(im)
  print(f"{s:28s} {label:18s}",{k:(v['state'][:2],'S' if v['sensitive'] else '') for k,v in reg.items()})
json.dump(out,open('cp_decisions.json','w'),ensure_ascii=False,indent=1)
while len(tiles)%4: tiles.append(np.full((400,400,3),255,np.uint8))
for p in range(0,len(tiles),12):
  T=tiles[p:p+12]
  while len(T)%4: T.append(np.full((400,400,3),255,np.uint8))
  cv2.imwrite(f'cp_paint_{p//12+1}.jpg',np.vstack([np.hstack(T[i:i+4]) for i in range(0,len(T),4)]),[cv2.IMWRITE_JPEG_QUALITY,85])
