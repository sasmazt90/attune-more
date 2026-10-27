"""Step 1: image list + MediaPipe regions (incl. periorbital) + region-level GT from box/polygon labels."""
import json,glob,os,sys,collections,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
from PIL import Image
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
TASK=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
REG={'forehead':[54,103,67,109,10,338,297,332,284,293,334,296,336,9,107,66,105,63],
 'nose':[168,193,245,188,174,236,198,209,49,48,64,98,97,2,326,327,294,278,279,429,420,456,399,412,465,417],
 'cheek_imgL':[116,117,118,119,100,142,203,206,216,212,214,192,213,147,123],
 'cheek_imgR':[345,346,347,348,329,371,423,426,436,432,434,416,433,376,352],
 'chin':[43,106,182,83,18,313,406,335,273,422,430,394,395,369,396,175,171,140,170,169,210,202],
 # periorbital ring (app eyeBands outer ring), eye opening removed at mask time
 'eye_imgL':[35,46,65,55,193,128,120,111],'eye_imgR':[265,276,295,285,417,357,349,340]}
HOLES={'eye_imgL':[33,160,158,133,153,145,163],'eye_imgR':[263,387,385,362,380,374,390]}
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=TASK),num_faces=1,min_face_detection_confidence=0.5))
SETS=[ # name, dir, splits, label mode
 ('parin',f'{S}/regional_ds/data',['valid','test'],'box'),
 ('skinmap',f'{S}/evalds/skinmap',['valid','test'],'box'),
 ('findings',f'{S}/evalds/findings',['valid','test'],'box'),
 ('a7el6',f'{S}/ds/a7el6',['train','valid','test'],'poly'),
 ('orhyy',f'{S}/ds/orhyy',['train','valid','test'],'poly'),
 ('ka1tj',f'{S}/ds/ka1tj',['valid','test'],'poly')]
items=[]; cnt=collections.Counter()
for name,d,splits,mode in SETS:
  for sp in splits:
    J=json.load(open(f'{d}/{sp}/_annotations.coco.json')); cats={c['id']:c['name'] for c in J['categories']}
    by=collections.defaultdict(list)
    for a in J['annotations']: by[a['image_id']].append(a)
    for im in J['images']:
      p=f"{d}/{sp}/{im['file_name']}"; rgb=np.array(Image.open(p).convert('RGB')); h,w=rgb.shape[:2]
      r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb)))
      if not r.face_landmarks: cnt[(name,'noface')]+=1; continue
      P=np.array([[q.x*w,q.y*h] for q in r.face_landmarks[0]])
      fw=P[:,0].max()-P[:,0].min()
      if fw<0.25*w and fw<180: cnt[(name,'smallface')]+=1; continue
      regs={k:P[v].round(1).tolist() for k,v in REG.items()}; holes={k:P[v].round(1).tolist() for k,v in HOLES.items()}
      gt={}
      for k in REG:
        m=np.zeros((h,w),np.uint8); cv2.fillPoly(m,[np.array(regs[k],np.int32)],1)
        if k in holes: cv2.fillPoly(m,[np.array(holes[k],np.int32)],0)
        A=m.sum()
        if A<200: continue
        U={}
        for a in by[im['id']]:
          c=cats[a['category_id']]; mm=U.setdefault(c,np.zeros((h,w),np.uint8))
          if mode=='poly' and a.get('segmentation'):
            for seg in a['segmentation']: cv2.fillPoly(mm,[np.array(seg).reshape(-1,2).astype(np.int32)],1)
          else:
            x,y,bw,bh=a['bbox']; mm[max(0,int(y)):int(y+bh),max(0,int(x)):int(x+bw)]=1
        gt[k]={c:round(float((mm&m).sum()/A),3) for c,mm in U.items() if (mm&m).sum()>0}
      allc=sorted({cats[a['category_id']] for a in by[im['id']]})
      items.append(dict(id=len(items),set=name,split=sp,path=p,w=w,h=h,regions=regs,holes=holes,gt=gt,classes=allc,faceW=round(float(fw),1)))
      cnt[(name,sp)]+=1
  print(name,{k:v for k,v in cnt.items() if k[0]==name},flush=True)
os.makedirs(f'{S}/rf',exist_ok=True); json.dump(items,open(f'{S}/rf/items.json','w'))
print('total',len(items))
