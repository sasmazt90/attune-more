import sys,os,cv2,numpy as np,mediapipe as mp
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR']=f'{S}/rv3bundle'; sys.path.insert(0,f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R
from mediapipe.tasks.python import vision, BaseOptions
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
def run(img,pose,tag):
  r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  m=R.analyze_photo(img,[dict(x=q.x,y=q.y) for q in r.face_landmarks[0]],pose=pose)
  print(tag,{k:(v['state'],v.get('causes')) for k,v in m['regions'].items()})
img=cv2.imread(f'{S}/gen/approved/K-091/K-091-front.png'); run(img,'FRONT','K-091 front')
# half-face shadow: darken the image-left half
sh=img.copy().astype(np.float32); w=img.shape[1]; ramp=np.clip(np.linspace(0.35,1.0,w)[None,:,None]*1.0,0,1); sh=(sh*ramp).astype(np.uint8); run(sh,'FRONT','K-160-like shadow K-091')
side=cv2.imread(f'{S}/gen/approved/K-091/K-091-side_1.png'); run(side,'FRONT','side photo sent as FRONT')
