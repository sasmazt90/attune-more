import sys,cv2,numpy as np,os,json
kid=sys.argv[1]; d=f'pending/{kid}'
ims=[cv2.resize(cv2.imread(f'{d}/{kid}-{p}.png'),(400,600)) for p in ('side_2','front','side_1')]
cv2.imwrite(f'{d}/review.jpg',np.hstack(ims),[cv2.IMWRITE_JPEG_QUALITY,88])
s=json.load(open('state.json')); p=next(x for x in s['plans'] if x['id']==kid)
print(json.dumps({k:p[k] for k in ('tone','sex','age','beard','pattern','regions','sens','sensRegions','acne','acneRegions','extras','similarity')},ensure_ascii=False))
import math,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),output_facial_transformation_matrixes=True,num_faces=1))
yaws={}
for p in ('front','side_1','side_2'):
  im=cv2.imread(f'{d}/{kid}-{p}.png'); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
  if not r.face_landmarks: yaws[p]=None; continue
  m=np.array(r.facial_transformation_matrixes[0]).T.flatten(); yaws[p]=round(math.degrees(math.atan2(m[8],m[10])),1)
print('yaw',yaws, 'POSE_OK' if yaws['front'] is not None and abs(yaws['front'])<8 and yaws['side_1'] and yaws['side_2'] and abs(yaws['side_1'])>10.5 and abs(yaws['side_2'])>10.5 and yaws['side_1']*yaws['side_2']<0 else 'POSE_CHECK')
