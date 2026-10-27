"""Regional dry/normal/oily scoring with a locally run RF-DETR detector + 3-pose fusion."""
import json,sys,os,numpy as np,cv2
from PIL import Image
REGIONS=['forehead','nose','cheek_imgL','cheek_imgR','chin']
def load_model(weights):
  from rfdetr import RFDETRSmall
  return RFDETRSmall(pretrain_weights=weights)
def detect(model,img_rgb,thr=0.05):
  d=model.predict(Image.fromarray(img_rgb),threshold=thr)
  return [(int(c),float(s),[float(v) for v in b]) for b,s,c in zip(d.xyxy,d.confidence,d.class_id)]
def region_cover(dets,poly,shape,cls_map,thr):
  H,W=shape[:2]; m=np.zeros((H,W),np.uint8); cv2.fillPoly(m,[np.array(poly,np.int32)],1); A=m.sum()
  out={}
  for name in ('dry','oily'):
    cm=np.zeros((H,W),np.float32)
    for c,s,(x0,y0,x1,y1) in dets:
      if cls_map.get(c)!=name or s<thr: continue
      x0,y0,x1,y1=map(lambda v:int(round(v)),(max(0,x0),max(0,y0),min(W,x1),min(H,y1)))
      cm[y0:y1,x0:x1]=np.maximum(cm[y0:y1,x0:x1],s)
    cov=float(((cm>0)&(m>0)).sum()/max(A,1)); conf=float(cm[m>0].max()) if A else 0.0
    out[name]={'coverage':round(cov,3),'maxConf':round(conf,3)}
  out['areaPx']=int(A); return out
def label(rc,cov_thr):
  d,o=rc['dry']['coverage'],rc['oily']['coverage']
  if max(d,o)<cov_thr: return 'normal'
  return 'oily' if o>=d else 'dry'
