import sys,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
sys.argv=[sys.argv[0]]
import tech_proto as T
from PIL import Image,ImageDraw,ImageFont
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
CASES=[('K-040',dict(forehead='oily',nose='oily',chin='normal',rightCheek='normal',leftCheek='normal'),['forehead','chin']),
 ('K-091',dict(forehead='oily',nose='oily',chin='normal',rightCheek='unmeasured',leftCheek='dry'),['nose','leftCheek'])]
f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',20); fs=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
rows=[]
for lang,title in (('tr','TR'),('en','EN'),('de','DE')):
  tiles=[]
  for kid,st,sens in CASES:
    img=cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png'); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
    out=cv2.resize(T.render(img,r.face_landmarks[0],st,set(sens),lang,(112,912),'combo')[250:1250,112:912],(480,600))
    pb=Image.new('RGB',(480,40),(11,16,26)); ImageDraw.Draw(pb).text((10,8),title,font=f,fill=(255,255,255))
    tiles.append(np.vstack([cv2.cvtColor(np.array(pb),cv2.COLOR_RGB2BGR),out]))
  rows.append(np.hstack(tiles))
img=np.vstack([np.hstack(rows[0:1]+[rows[1][:, :480]])] ) if False else np.vstack([np.hstack([rows[0],rows[1]]),np.hstack([rows[2],np.full_like(rows[2],12)])])
sw=Image.new('RGB',(img.shape[1],120),(11,16,26)); d=ImageDraw.Draw(sw)
items=[('Yağlı',(34,197,94)),('Kuru',(59,130,246)),('Dengeli',(250,204,21)),('Ölçülemedi (çizgi)',(148,163,184)),
       ('Yağlı + hassas',(20,184,166)),('Kuru + hassas',(106,90,249)),('Dengeli + hassas',(249,115,22))]
for i,(n,c) in enumerate(items):
  x=20+(i%4)*470; y=12+(i//4)*52
  d.rounded_rectangle([x,y,x+40,y+38],8,fill=c); d.text((x+52,y+9),n,font=fs,fill=(230,230,230))
cv2.imwrite('/mnt/user-data/outputs/hassas_renk_kodlari.jpg',np.vstack([img,cv2.cvtColor(np.array(sw),cv2.COLOR_RGB2BGR)]),[cv2.IMWRITE_JPEG_QUALITY,90]); print('ok')
