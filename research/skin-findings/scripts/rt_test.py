import sys,os,json,time,numpy as np,cv2,mediapipe as mp
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR']=f'{S}/rv3bundle'
sys.path.insert(0,f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R
from mediapipe.tasks.python import vision, BaseOptions
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
st={p['id']:p for p in json.load(open(f'{S}/gen/state.json'))['plans']}
POSE={'front':'FRONT','side_1':'LEFT','side_2':'RIGHT'}
ok=n=0
for kid in sys.argv[1:]:
  maps={}
  for v,pose in POSE.items():
    bgr=cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{v}.png'); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)))
    pts=[dict(x=q.x,y=q.y) for q in r.face_landmarks[0]]; t=time.time()
    maps[pose]=R.analyze_photo(bgr,pts,pose=pose); dt=time.time()-t
  fz=R.fuse_maps(maps); lab=st[kid]['regions']
  print(kid,st[kid].get('intensity','belirgin'),st[kid]['pattern'],f'{dt:.1f}s/foto','| tip:',fz['skinType']['value'],'hassas' if fz['skinType']['sensitive'] else '')
  for a,e in fz['regions'].items():
    print(f"   {a:10s} beklenen={lab[a]:6s} sonuç={e['state']:10s} {'+H' if e.get('sensitive') else '  '} {e.get('scores')} views={e.get('views')}")
    if e['state']!='unmeasured': n+=1; ok+=e['state']==lab[a]
print('boyanan',n,'doğru',ok)
