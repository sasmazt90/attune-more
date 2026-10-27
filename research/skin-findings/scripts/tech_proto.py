"""HUD-style regional paint prototype (mirrors the SVG overlay): dot-matrix fill with edge fade, glowing outline,
dashed outline for unmeasured, pink inner dashed ring + pink dots for sensitive, small region tags."""
import json,sys,numpy as np,cv2
from paint_proto import PAINT,EYE,TOP,catmull
COL={'oily':(34,197,94),'dry':(59,130,246),'normal':(250,204,21),'unmeasured':(148,163,184)}
PINK=(236,72,153)
COMBO={'oily':(20,184,166),'dry':(106,90,249),'normal':(249,115,22)}  # dedicated colour per 'X + hassas'
LABELS={'tr':{'oily':'Yağlı','dry':'Kuru','normal':'Dengeli','unmeasured':'Ölçüm notu','sens':'Hassas'},
 'en':{'oily':'Oily','dry':'Dry','normal':'Balanced','unmeasured':'Measurement note','sens':'Sensitive'},
 'de':{'oily':'Fettig','dry':'Trocken','normal':'Ausgeglichen','unmeasured':'Messhinweis','sens':'Empfindlich'},
 'de2':{'oily':'Fettig','dry':'Trocken','normal':'Unauffällig','unmeasured':'Messhinweis','sens':'Empfindlich'}}
LBL=LABELS['tr']
def outline(P,rid):
  pts=P[PAINT[rid]].copy()
  if rid=='forehead':
    up=(P[10]-P[9])*0.42
    for j,ix in enumerate(PAINT[rid]):
      if ix in TOP: pts[j]+=up*TOP[ix]
  return catmull(pts)
def dashed(img,poly,col,th,dash,gap):
  poly=np.vstack([poly,poly[:1]]); seg=np.linalg.norm(np.diff(poly,axis=0),axis=1); acc=0; on=True
  for i in range(len(poly)-1):
    if on: cv2.line(img,tuple(poly[i].astype(int)),tuple(poly[i+1].astype(int)),col,th,cv2.LINE_AA)
    acc+=seg[i]
    if acc>(dash if on else gap): acc=0; on=not on
def render(img,lms,states,sens,lang='tr',xb=None,smode='chip',untag=True):
  LBL=LABELS[lang]
  h,w=img.shape[:2]; P=np.array([[p.x*w,p.y*h] for p in lms]); fw=P[:,0].max()-P[:,0].min()
  base=img.astype(np.float32)
  # subtle "scan" look: slight desaturation + cool tint of the whole photo
  g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)[...,None].astype(np.float32); base=base*0.82+g*0.18
  out=base.copy(); glow=np.zeros_like(base); lines=np.zeros_like(base); la=np.zeros((h,w),np.float32)
  step=max(4,int(fw/60)); r=max(1,int(fw/330))
  yy,xx=np.mgrid[0:h,0:w]
  grid=((((xx%step)-step/2)**2+((yy%step)-step/2)**2)<=r*r).astype(np.float32)
  for rid,st in states.items():
    poly=outline(P,rid).astype(np.int32); m=np.zeros((h,w),np.uint8); cv2.fillPoly(m,[poly],1)
    c=np.array(COL[st][::-1],np.float32); sv=rid in sens and st!='unmeasured'; pk=np.array(PINK[::-1],np.float32)
    if sv and smode=='mix': c=(c+pk)/2
    if sv and smode=='combo': c=np.array(COMBO[st][::-1],np.float32)
    if sv and smode=='grad':
      ys,xs=np.where(m>0); t=((xx+yy)-(xs+ys).min())/max(1,((xs+ys).max()-(xs+ys).min())); t=np.clip(t,0,1)[...,None]
      cfield=c*(1-t)+pk*t
    else: cfield=None
    dist=cv2.distanceTransform(m,cv2.DIST_L2,5); edge=np.clip(1-dist/(fw*0.09),0,1)   # brighter near the edge, fades inward
    tint=m*(0.10+0.16*edge)
    cc_=cfield if cfield is not None else c
    out=out*(1-tint[...,None])+cc_*tint[...,None]
    dots=grid*m*(0.35+0.45*edge); out=out*(1-dots[...,None]*0.8)+cc_*dots[...,None]*0.8
    if st=='unmeasured': dashed(lines,poly,tuple(int(v) for v in c),max(1,int(fw/280)),fw/40,fw/60)
    elif sv and smode=='combo':
      cv2.polylines(lines,[poly],True,tuple(int(v) for v in c),max(1,int(fw/260)),cv2.LINE_AA)
      cv2.polylines(glow,[poly],True,tuple(int(v) for v in c),max(3,int(fw/70)),cv2.LINE_AA)
    elif sv and smode=='ring':
      cv2.polylines(lines,[poly],True,PINK[::-1],max(2,int(fw/170)),cv2.LINE_AA)
      cv2.polylines(glow,[poly],True,PINK[::-1],max(3,int(fw/70)),cv2.LINE_AA)
    elif cfield is not None:
      for col_,lay,th in ((None,lines,max(1,int(fw/260))),(None,glow,max(3,int(fw/70)))):
        tmp=np.zeros((h,w),np.uint8); cv2.polylines(tmp,[poly],True,255,th,cv2.LINE_8); a=(tmp>0)[...,None].astype(np.float32)
        lay[:]=np.maximum(lay,cfield*a)
    else:
      cv2.polylines(lines,[poly],True,tuple(int(v) for v in c),max(1,int(fw/260)),cv2.LINE_AA)
      cv2.polylines(glow,[poly],True,tuple(int(v) for v in c),max(3,int(fw/70)),cv2.LINE_AA)
    if rid in sens and st!='unmeasured' and smode=='chip':
      # sensitive: pink diagonal hatch over the whole region + solid pink inset contour (clearly different from the dot fill)
      gap=max(6,int(fw/24)); hatch=((((xx+yy)%gap)<max(1,int(fw/240)))).astype(np.float32)*m
      inner=cv2.erode(m,np.ones((int(fw/45),int(fw/45)),np.uint8))
      ha=hatch*inner*0.75; out=out*(1-ha[...,None])+np.array(PINK[::-1],np.float32)*ha[...,None]
      cs,_=cv2.findContours(inner,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
      cv2.drawContours(lines,cs,-1,PINK[::-1],max(2,int(fw/170)),cv2.LINE_AA)
  glow=cv2.GaussianBlur(glow,(0,0),fw/80); out=out+glow*0.35
  lm=lines.max(-1)>0; out[lm]=out[lm]*0.15+lines[lm]*0.85
  out=np.clip(out,0,255).astype(np.uint8)
  # region tags (pill with leader dot) — Turkish text needs PIL
  from PIL import Image,ImageDraw,ImageFont
  im=Image.fromarray(cv2.cvtColor(out,cv2.COLOR_BGR2RGB)); d=ImageDraw.Draw(im,'RGBA'); fs=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',max(12,int(fw/28)))
  anchor={'forehead':10,'nose':4,'rightCheek':205,'leftCheek':425,'chin':152}
  for rid,st in states.items():
    if st=='unmeasured' and untag: continue
    p=P[anchor[rid]]; c=COL[st]; txt=LBL[st]; sv=rid in sens and st!='unmeasured'
    if sv and smode!='chip':
      c=PINK if smode=='ring' else COMBO[st] if smode=='combo' else tuple(int((a+b)/2) for a,b in zip(COL[st],PINK)); txt=f"{LBL[st]} · {LBL['sens']}"; sv=False
    off={'forehead':(0,-fw*0.02),'nose':(fw*0.0,fw*0.05),'rightCheek':(-fw*0.12,0),'leftCheek':(fw*0.12,0),'chin':(0,fw*0.05)}[rid]
    pad=fs.size*0.45; tw=d.textlength(txt,font=fs); sw=d.textlength(LBL['sens'],font=fs)+2*pad if sv else 0
    total=tw+2*pad+(sw+pad*0.4 if sv else 0)
    tx,ty=p[0]+off[0]-total/2,p[1]+off[1]
    lo,hi=(xb if xb else (0,w)); tx=min(max(tx,lo+4),hi-total-4)
    box=[tx,ty-fs.size*0.75,tx+tw+2*pad,ty+fs.size*0.75]
    d.rounded_rectangle(box,radius=fs.size*0.7,fill=(10,18,32,180),outline=c+(230,),width=max(1,int(fw/400)))
    d.text((tx+pad,ty-fs.size*0.62),txt,font=fs,fill=(235,242,250,255))
    if sv:
      b2=[box[2]+pad*0.4,box[1],box[2]+pad*0.4+sw,box[3]]
      d.rounded_rectangle(b2,radius=fs.size*0.7,fill=PINK+(235,))
      d.text((b2[0]+pad,ty-fs.size*0.62),LBL['sens'],font=fs,fill=(255,255,255,255))
  return cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR)
if __name__=='__main__':
  import mediapipe as mp
  from mediapipe.tasks.python import vision, BaseOptions
  S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
  lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'),num_faces=1))
  img=cv2.imread(sys.argv[1]); res=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)))
  cv2.imwrite(sys.argv[2],render(img,res.face_landmarks[0],json.loads(sys.argv[3]),set(json.loads(sys.argv[4]))))
