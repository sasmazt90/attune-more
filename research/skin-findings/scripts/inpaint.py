"""Hair (beard/stubble) + wrinkle-line masks; inpaint them so models see only bare skin. Saves clean image + mask."""
import json,os,sys,numpy as np,cv2
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
TAG=os.environ.get('TAG',''); I=json.load(open(f'{S}/rf/items{TAG}.json'))
os.makedirs(f'{S}/rf/clean{TAG}',exist_ok=True)
FACE=['forehead','nose','cheek_imgL','cheek_imgR','chin']
def hair_mask(bgr,it):
  """Beard/stubble only: dense dark strokes in the lower face (below the nose base), contrast relative to own skin."""
  fw=it['faceW']; L=cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB)[...,0].astype(np.float32)
  k=max(5,int(fw/45)|1); bh=cv2.morphologyEx(L,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k)))
  face=np.zeros(L.shape,np.uint8)
  for r in FACE: cv2.fillPoly(face,[np.array(it['regions'][r],np.int32)],1)
  upper=np.zeros(L.shape,np.uint8); cv2.fillPoly(upper,[np.array(it['regions']['forehead'],np.int32)],1)
  ref=bh[upper>0] if upper.sum()>50 else bh[face>0]
  Lm=float(np.median(L[face>0])) if face.any() else 128.0
  t=max(np.percentile(ref,97),0.10*Lm,8.0)   # stroke must be stronger than forehead texture (no beard there)
  m=((bh>t)&(L<Lm*0.92)).astype(np.uint8)
  ys=[p[1] for p in it['regions']['nose']]; ybase=max(ys)-0.02*fw
  m[:int(max(0,ybase)),:]=0
  dens=cv2.blur(m.astype(np.float32),(k*3+1,k*3+1))
  return ((m>0)&(dens>0.12)&(face>0)).astype(np.uint8)
if __name__=='__main__':
 for it in I:
  fn=f"{S}/rf/clean{TAG}/{it['id']}_m.png"
  if os.path.exists(fn): continue
  bgr=cv2.imread(it['path']); h,w=bgr.shape[:2]
  wm=cv2.imread(f"{S}/rf/wmask{TAG}/{it['id']}.png",0); wm=(wm>0).astype(np.uint8) if wm is not None else np.zeros((h,w),np.uint8)
  hm=hair_mask(bgr,it)
  cv2.imwrite(fn,(wm*1+hm*2).astype(np.uint8))   # bit0 wrinkle, bit1 beard
 print('done',len(I))
