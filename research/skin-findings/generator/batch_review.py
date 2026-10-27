import sys,os,json,cv2,numpy as np,math,subprocess
from PIL import Image,ImageDraw,ImageFont
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),output_facial_transformation_matrixes=True,num_faces=1))
s=json.load(open('state.json')); P=[x for x in s['plans'] if x['status']=='pending']
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15); fb=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',16)
TR={'oily':'Y','dry':'K','normal':'N'}
rows=[]
for p in P:
  d=f"pending/{p['id']}"; ims=[]; yaws={}
  for pose in ('side_2','front','side_1'):
    im=cv2.imread(f"{d}/{p['id']}-{pose}.png"); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
    if r.face_landmarks:
      m=np.array(r.facial_transformation_matrixes[0]).T.flatten(); yaws[pose]=round(math.degrees(math.atan2(m[8],m[10])),1)
    else: yaws[pose]=None
    ims.append(cv2.resize(im,(300,450)))
  ok=yaws['front'] is not None and abs(yaws['front'])<8 and all(yaws[k] is not None and abs(yaws[k])>10.5 for k in('side_1','side_2')) and yaws['side_1']*yaws['side_2']<0
  strip=Image.fromarray(cv2.cvtColor(np.hstack(ims),cv2.COLOR_BGR2RGB)); c=Image.new('RGB',(900,520),(10,18,32)); c.paste(strip,(0,0)); dr=ImageDraw.Draw(c)
  reg=' '.join(f"{k[:2]}:{TR[v]}" for k,v in p['regions'].items())
  dr.text((6,454),f"{p['id']} FST {p['tone']} {p['sex']} {p['age']} sakal:{p['beard']}  sim {p['similarity']}  yaw {yaws} {'POZ OK' if ok else 'POZ ?'}",font=fb,fill=(235,242,250))
  dr.text((6,476),f"{p['pattern']} [{p.get('intensity','belirgin')}] | {reg} | hassas: {p['sens']} {p['sensRegions']} | sivilce: {p['acne']} {p['acneRegions']}",font=font,fill=(250,204,21))
  dr.text((6,496),f"diğer: {p['extras']}",font=font,fill=(180,200,220))
  rows.append(np.array(c)); print(p['id'],yaws,'POZ OK' if ok else 'POZ ?',p['similarity'])
Image.fromarray(np.vstack(rows)).save('pending/batch_review.jpg',quality=80)
