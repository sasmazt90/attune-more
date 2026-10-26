import sys,json,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
sys.argv=[sys.argv[0]]
from tech_proto import render
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
TYPE={'tr':{'Karma ve hassas':'Karma ve hassas','Karma':'Karma','Yağlı':'Yağlı'},'en':{'Karma ve hassas':'Combination & sensitive','Karma':'Combination','Yağlı':'Oily'},'de':{'Karma ve hassas':'Mischhaut, empfindlich','Karma':'Mischhaut','Yağlı':'Fettige Haut'}}
TYPE['de2']=TYPE['de']
CASES=[('K-040','Karma ve hassas',dict(forehead='oily',nose='oily',chin='normal',rightCheek='normal',leftCheek='normal'),['forehead','chin']),
 ('K-091','Karma ve hassas',dict(forehead='oily',nose='oily',chin='normal',rightCheek='unmeasured',leftCheek='dry'),['nose','leftCheek']),
 ('K-160','Karma',dict(forehead='oily',nose='oily',chin='normal',rightCheek='dry',leftCheek='unmeasured'),[]),
 ('K-144','Yağlı',dict(forehead='oily',nose='oily',chin='oily',rightCheek='unmeasured',leftCheek='oily'),[])]
rows=[]
for lang in ('tr','en','de','de2'):
 tiles=[]
 for kid,name,st,sens in CASES:
  name=TYPE[lang][name]
  img=cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png'); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  out=render(img,r.face_landmarks[0],st,set(sens),lang,(112,912))[250:1250,112:912]; out=cv2.resize(out,(480,600))
  bar=np.full((44,480,3),(26,16,11),np.uint8)
  from PIL import Image,ImageDraw,ImageFont
  pb=Image.fromarray(cv2.cvtColor(bar,cv2.COLOR_BGR2RGB)); d=ImageDraw.Draw(pb); f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',22)
  d.text((10,9),f"{'DE (kısa)' if lang=='de2' else lang.upper()} · {name}",font=f,fill=(255,255,255)); tiles.append(np.vstack([cv2.cvtColor(np.array(pb),cv2.COLOR_RGB2BGR),out]))
 rows.append(np.hstack(tiles))
cv2.imwrite('/mnt/user-data/outputs/bolgesel_boyama_tr_en_de.jpg',np.vstack(rows),[cv2.IMWRITE_JPEG_QUALITY,90]); print('ok')
