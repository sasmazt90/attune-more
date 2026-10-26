import sys,os,json,base64,cv2,mediapipe as mp
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR']=f'{S}/rv3bundle'; sys.path.insert(0,f'{S}/repo/claude-skin/services/core-api'); os.chdir(f'{S}/repo/claude-skin/services/core-api')
from regional_attach import attach,fuse
from mediapipe.tasks.python import vision, BaseOptions
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
kid=sys.argv[1]; res={}
for v,pose in (('front','FRONT'),('side_1','LEFT'),('side_2','RIGHT')):
  p=f'{S}/gen/approved/{kid}/{kid}-{v}.png'; bgr=cv2.imread(p); bgr=cv2.resize(bgr,(768,1152))
  ok,buf=cv2.imencode('.png',bgr); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)))
  value=dict(photo='data:image/png;base64,'+base64.b64encode(buf.tobytes()).decode(),landmarks=[dict(x=q.x,y=q.y,z=q.z) for q in r.face_landmarks[0]],pose=pose)
  out={'general':{'skinType':{'value':'normal','quality':'valid'}}} if pose=='FRONT' else {}
  res[pose]=attach(out,value); print(pose,res[pose].get('regionalSkinMapStatus'),{k:v['state'] for k,v in res[pose]['regionalSkinMap']['regions'].items()})
fz=fuse({'general':{}},res['FRONT'],res['LEFT'],res['RIGHT'])
m=fz['general']['regionalSkinMap']; print('FUSED',m['pose'],m['skinType'],{k:(v['state'],v['sensitive'],v['sourcePose']) for k,v in m['regions'].items()})
# failure path: missing bundle must not break
os.environ['ATTUNE_REGIONAL_V3_DIR']='/nonexistent'
