"""Prototype of the soft regional paint (same geometry as the TS overlay), for visual checks."""
import json,sys,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
TASK=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
PAINT={
 'forehead':[21,54,103,67,109,10,338,297,332,284,251,301,293,334,296,336,9,107,66,105,63,71],
 'nose':[9,336,285,417,465,412,343,437,420,429,358,327,326,2,97,98,129,209,198,217,114,188,245,193,55,107],
 'rightCheek':[143,127,234,93,132,58,172,136,150,169,210,202,57,186,92,165,203,129,209,198,217,114,188,245,128,121,120,119,118,117,111],
 'leftCheek':[372,356,454,323,361,288,397,365,379,394,430,422,287,410,322,391,423,358,429,420,437,343,412,465,357,350,349,348,347,346,340],
 'chin':[57,202,204,194,201,200,421,418,424,422,287,430,394,379,378,400,377,152,148,176,149,150,169,210],
 'periorbital_r':[143,111,117,118,119,120,121,128,245,193,55,65,52,53,46,124,35],
 'periorbital_l':[372,340,346,347,348,349,350,357,465,417,285,295,282,283,276,353,265]}
TOP={21:0.35,54:0.7,103:0.9,67:1,109:1,10:1,338:1,297:1,332:0.9,284:0.7,251:0.35}
EYE={'periorbital_r':[33,246,161,160,159,158,157,173,133,155,154,153,145,144,163,7],'periorbital_l':[263,466,388,387,386,385,384,398,362,382,381,380,374,373,390,249]}
def catmull(pts,n=8):
  P=np.array(pts,float); out=[]
  for i in range(len(P)):
    p0,p1,p2,p3=P[i-1],P[i],P[(i+1)%len(P)],P[(i+2)%len(P)]
    for t in np.linspace(0,1,n,endpoint=False):
      t2,t3=t*t,t*t*t
      out.append(0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t2+(-p0+3*p1-3*p2+p3)*t3))
  return np.array(out)
COL={'oily':(34,197,94),'dry':(59,130,246),'normal':(250,204,21),'unmeasured':(148,163,184)}
def render(img_bgr,lms,states,sens=set(),alpha=0.38):
  h,w=img_bgr.shape[:2]; P=np.array([[p.x*w,p.y*h] for p in lms]); fw=P[:,0].max()-P[:,0].min()
  layer=np.zeros((h,w,3),np.float32); a=np.zeros((h,w),np.float32); pink=np.zeros((h,w),np.float32); hatch=np.zeros((h,w),np.float32)
  for rid,st in states.items():
    if st is None: continue
    pts=P[PAINT[rid]].copy()
    if rid=='forehead':
      up=(P[10]-P[9])*0.42
      for j,ix in enumerate(PAINT[rid]):
        if ix in TOP: pts[j]+=up*TOP[ix]
    m=np.zeros((h,w),np.uint8); cv2.fillPoly(m,[catmull(pts).astype(np.int32)],255)
    if rid in EYE: cv2.fillPoly(m,[catmull(P[EYE[rid]]).astype(np.int32)],0)
    mf=cv2.GaussianBlur(m.astype(np.float32)/255,(0,0),fw/90)
    c=np.array(COL[st][::-1],np.float32); layer=layer*(1-mf[...,None])+c*mf[...,None]; a=np.maximum(a,mf)
    if rid in sens: pink=np.maximum(pink,mf)
    if st=='unmeasured': hatch=np.maximum(hatch,mf)
  out=img_bgr.astype(np.float32)*(1-alpha*a[...,None])+layer*alpha*a[...,None]
  if pink.max()>0:  # soft dot texture, not boxes
    yy,xx=np.mgrid[0:h,0:w]; step=fw/30; r=fw/210
    dots=(((xx%step)-step/2)**2+((yy+(xx//step%2)*step/2)%step-step/2)**2<r*r).astype(np.float32)
    dots=cv2.GaussianBlur(dots,(0,0),r/2.5)*pink
    edge=cv2.GaussianBlur(np.clip(cv2.morphologyEx((pink>0.5).astype(np.uint8),cv2.MORPH_GRADIENT,np.ones((3,3))).astype(np.float32)*1.0,0,1),(0,0),fw/400)
    pk=np.array((236,72,153)[::-1],np.float32); k=np.clip(dots*0.7+edge*0.9,0,0.9)[...,None]; out=out*(1-k)+pk*k
  if hatch.max()>0:
    yy,xx=np.mgrid[0:h,0:w]; st=(((xx+yy)%(fw/22))<fw/180).astype(np.float32)*hatch; k=(st*0.45)[...,None]; out=out*(1-k)+np.array((100,116,139),np.float32)*k
  return np.clip(out,0,255).astype(np.uint8)
if __name__=='__main__':
  lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=TASK),num_faces=1))
  img=cv2.imread(sys.argv[1]); r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  st=json.loads(sys.argv[3]) if len(sys.argv)>3 else {'forehead':'oily','nose':'oily','rightCheek':'normal','leftCheek':'dry','chin':'normal','periorbital_r':'unmeasured','periorbital_l':'unmeasured'}
  sens=set(json.loads(sys.argv[4])) if len(sys.argv)>4 else {'chin'}
  cv2.imwrite(sys.argv[2],render(img,r.face_landmarks[0],st,sens))
