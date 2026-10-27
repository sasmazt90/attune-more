import sys,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
sys.argv=[sys.argv[0]]
from tech_proto import render
from PIL import Image,ImageDraw,ImageFont
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
CASES=[('K-040',dict(forehead='oily',nose='oily',chin='normal',rightCheek='normal',leftCheek='normal'),['forehead','chin']),
 ('K-091',dict(forehead='oily',nose='oily',chin='normal',rightCheek='unmeasured',leftCheek='dry'),['nose','leftCheek'])]
f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',20); tiles=[]
rows=[]
for mode,title in (('mix','A · Düz karışım rengi'),('grad','B · İki renk geçişi'),('ring','C · Kendi rengi + pembe kontur')):
  if len(tiles)==4: rows.append(np.hstack(tiles)); tiles=[]
  for kid,st,sens in CASES:
    img=cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png'); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
    out=cv2.resize(render(img,r.face_landmarks[0],st,set(sens),'tr',(112,912),mode)[250:1250,112:912],(480,600))
    pb=Image.new('RGB',(480,40),(11,16,26)); ImageDraw.Draw(pb).text((10,8),title,font=f,fill=(255,255,255))
    tiles.append(np.vstack([cv2.cvtColor(np.array(pb),cv2.COLOR_RGB2BGR),out]))
# swatches
sw=Image.new('RGB',(1920,70),(11,16,26)); d=ImageDraw.Draw(sw); fs=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
COL={'Yağlı':(34,197,94),'Kuru':(59,130,246),'Normal':(250,204,21)}; P=(236,72,153); x=20
for n,c in COL.items():
  m=tuple((a+b)//2 for a,b in zip(c,P))
  d.rounded_rectangle([x,15,x+40,55],8,fill=c); d.rounded_rectangle([x+45,15,x+85,55],8,fill=m); d.text((x+95,25),f'{n} → {n} + hassas',font=fs,fill=(230,230,230)); x+=420
cv2.imwrite('/mnt/user-data/outputs/hassas_renk_karisim.jpg',np.vstack([rows[0],np.hstack(tiles+[np.full((640,960,3),(26,16,11),np.uint8)])[:, :1920] if len(tiles)==2 else np.hstack(tiles),cv2.cvtColor(np.array(sw),cv2.COLOR_RGB2BGR)]),[cv2.IMWRITE_JPEG_QUALITY,90]); print('ok')
