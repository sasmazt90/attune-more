"""Free local test: does skin-type-l6qra (v5, un-augmented) improve dry-vs-normal on OUR region testbed?
Train: DINOv2-small features of masked region crops (faces) or centre crop (close-ups), label = image label,
'Sensitif' excluded. Near-duplicates of testbed images removed (dHash) to avoid leakage."""
import json,glob,os,sys,collections,numpy as np,cv2,torch
from PIL import Image
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0,f'{S}/rf')
REG={'forehead':[54,103,67,109,10,338,297,332,284,293,334,296,336,9,107,66,105,63],
 'nose':[168,193,245,188,174,236,198,209,49,48,64,98,97,2,326,327,294,278,279,429,420,456,399,412,465,417],
 'cheek_imgL':[116,117,118,119,100,142,203,206,216,212,214,192,213,147,123],
 'cheek_imgR':[345,346,347,348,329,371,423,426,436,432,434,416,433,376,352],
 'chin':[43,106,182,83,18,313,406,335,273,422,430,394,395,369,396,175,171,140,170,169,210,202]}
def dhash(im,n=8):
  g=np.array(im.convert('L').resize((n+1,n))); return sum(1<<i for i,v in enumerate((g[:,1:]>g[:,:-1]).flatten()) if v)
items=json.load(open(f'{S}/rf/items.json')); test_h=[dhash(Image.open(it['path'])) for it in items]
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
def crop_poly(rgb,poly,size=224):
  m=np.zeros(rgb.shape[:2],np.uint8); cv2.fillPoly(m,[poly.astype(np.int32)],1)
  x0,y0=poly.min(0).astype(int); x1,y1=poly.max(0).astype(int); x0,y0=max(0,x0),max(0,y0); x1,y1=min(rgb.shape[1],x1),min(rgb.shape[0],y1)
  if x1-x0<24 or y1-y0<24: return None
  c=rgb[y0:y1,x0:x1].copy(); mm=m[y0:y1,x0:x1]
  if mm.mean()<0.3: return None
  c[mm==0]=0; return cv2.resize(c,(size,size),interpolation=cv2.INTER_AREA)
rows=[]; crops=[]; skipped=collections.Counter()
for sp in ('train','valid','test'):
  for cdir in glob.glob(f'{S}/ds/l6qra/v5/{sp}/*'):
    lab=os.path.basename(cdir).lower()
    if lab not in ('dry','normal','oily'): skipped[lab]+=len(os.listdir(cdir)); continue
    for f in sorted(os.listdir(cdir)):
      im=Image.open(f'{cdir}/{f}').convert('RGB'); h=dhash(im)
      if min(bin(h^t).count('1') for t in test_h)<=4: skipped['dup_of_testbed']+=1; continue
      rgb=np.array(im); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb)))
      if r.face_landmarks:
        H,W=rgb.shape[:2]; P=np.array([[q.x*W,q.y*H] for q in r.face_landmarks[0]])
        for rn,idx in REG.items():
          c=crop_poly(rgb,P[idx])
          if c is not None: crops.append(c); rows.append(dict(split=sp,label=lab,file=f,kind='region:'+rn))
      else:
        H,W=rgb.shape[:2]; s=min(H,W); c=cv2.resize(rgb[(H-s)//2:(H+s)//2,(W-s)//2:(W+s)//2],(224,224),interpolation=cv2.INTER_AREA)
        crops.append(c); rows.append(dict(split=sp,label=lab,file=f,kind='closeup'))
print('rows',len(rows),collections.Counter((r['split'],r['label'],r['kind'].split(':')[0]) for r in rows),'skipped',dict(skipped),flush=True)
from transformers import AutoImageProcessor, AutoModel
proc=AutoImageProcessor.from_pretrained('facebook/dinov2-small'); dm=AutoModel.from_pretrained('facebook/dinov2-small').eval(); torch.set_num_threads(2)
F=[]
with torch.no_grad():
  for i in range(0,len(crops),32):
    o=dm(**proc(images=[Image.fromarray(c) for c in crops[i:i+32]],return_tensors='pt')).last_hidden_state
    F.append(torch.cat([o[:,0],o[:,1:].mean(1)],1).numpy())
np.save(f'{S}/rf/l6qra_dino.npy',np.concatenate(F)); json.dump(rows,open(f'{S}/rf/l6qra_rows.json','w')); print('done')
