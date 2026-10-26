import json,re,collections,sys,numpy as np,cv2
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0,f'{S}/repo/claude-skin/services/core-api')
from regional_skin_v3 import Decider,tone_group,skin_type_from_regions,APP_ID
from tech_proto import render
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
dec=Decider(json.load(open(f'{S}/repo/claude-skin/services/core-api/models/regional-skin-v3/params.json')))
I={it['id']:it for it in json.load(open('items_cp.json'))}; F=json.load(open('feats2_cp.json'))
by=collections.defaultdict(dict)
for r in F: by[r['id']][r['region']]=r
def subject(k):
  b=re.sub(r'(_v2)?\.(jpg|png)$','',k); b=re.sub(r'_png$','',b); return re.sub(r'_(front|left|right|side_1|side_2)$','',b)
subs=collections.defaultdict(list)
for i,it in I.items(): subs[subject(it['key'])].append(i)
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
TR={'combination':'Karma','oily':'Yağlı','dry':'Kuru','normal':'Normal'}
out={}; tiles=[]
from PIL import Image,ImageDraw,ImageFont
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',20)
for s,ids in sorted(subs.items()):
  front=min(ids,key=lambda i:abs(I[i]['yaw'])); pos=[i for i in ids if I[i]['yaw']>10.5]; neg=[i for i in ids if I[i]['yaw']<-10.5]
  src={'forehead':(front,'forehead'),'nose':(front,'nose'),'chin':(front,'chin'),'rightCheek':(pos[0] if pos else front,'cheek_imgL'),'leftCheek':(neg[0] if neg else front,'cheek_imgR')}
  reg={}
  for rid,(i,rn) in src.items():
    r=by[i].get(rn); tone=tone_group(r['f']['ita']) if r else 'light'
    reg[rid]=dict(dec.region(r['f'] if r else None,rn,tone),src=I[i]['key'],tone=tone)
  t=skin_type_from_regions(reg); label=(TR[t['value']]+(' ve hassas' if t['sensitive'] else '')) if t['value'] else 'Belirlenemedi'
  out[s]=dict(type=label,regions=reg)
  img=cv2.imread(I[front]['path']); res=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  im=render(img,res.face_landmarks[0],{k:v['state'] for k,v in reg.items()},{k for k,v in reg.items() if v['sensitive']})
  pil=Image.fromarray(cv2.cvtColor(cv2.resize(im,(420,420)),cv2.COLOR_BGR2RGB)); d=ImageDraw.Draw(pil)
  d.rectangle([0,0,420,30],fill=(10,18,32)); d.text((8,4),f"{s}: {label}",font=font,fill=(235,242,250))
  tiles.append(cv2.cvtColor(np.array(pil),cv2.COLOR_RGB2BGR))
  print(f"{s:24s} {label:18s} tone={reg['forehead']['tone']:6s}",{k:(v['state'][:3],'S' if v['sensitive'] else '') for k,v in reg.items()})
json.dump(out,open('cp_decisions2.json','w'),ensure_ascii=False,indent=1)
for p in range(0,len(tiles),12):
  T=tiles[p:p+12]
  while len(T)%4: T.append(np.full((420,420,3),255,np.uint8))
  cv2.imwrite(f'cp_tech_{p//12+1}.jpg',np.vstack([np.hstack(T[i:i+4]) for i in range(0,len(T),4)]),[cv2.IMWRITE_JPEG_QUALITY,86])
print(collections.Counter(v['type'] for v in out.values()))
