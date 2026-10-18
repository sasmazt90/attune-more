"""Isolated native-mask product contract. Never imported by the normal API.
Visible predicted area is appearance density; partial labels are evaluation only.
"""
import cv2,numpy as np
from appearance_analysis import polygon_mask,elongated_dark_mask,map_result
from skin_native_mask import infer_native_mask,CONTRACT

def stage_mask(bgr,points,meshes,session,metadata,target,photo):
 h,w=bgr.shape[:2];gray8=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
 holes=np.zeros((h,w),np.uint8)
 for ids in [[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327,294],[70,63,105,66,107,55,65,52],[300,293,334,296,336,285,295,282]]:
  cv2.fillPoly(holes,[np.array([[points[i]['x']*w,points[i]['y']*h] for i in ids],np.int32)],255)
 oval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
 face=np.zeros((h,w),np.uint8);cv2.fillPoly(face,[np.array([[points[i]['x']*w,points[i]['y']*h] for i in oval],np.int32)],255)
 valid=(face>0)&(holes==0)&~elongated_dark_mask(gray8)&(bgr.max(2)<249)&(gray8>30)
 masks={name:polygon_mask((h,w),mesh,1) & valid for name,mesh in meshes.items() if name!='periorbital'}
 support=np.logical_or.reduce(list(masks.values()));ys,xs=np.where(support)
 if not len(xs):raise ValueError('NO_ANATOMICAL_STAGING_SUPPORT')
 crop=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
 output=infer_native_mask(bgr,session,metadata,target,crop,support);prediction=output['mask'];rows={};maps={}
 for name,mask in {**masks,'overview':support}.items():
  density=float(prediction[mask].mean()*100) if mask.any() else None
  row=dict(id=target,region=name,value=density,quality='valid' if density is not None else 'insufficient',unit='percent-visible-area',normalizationVersion='visible-predicted-mask-area-v2',modelHash=metadata['sha256'],fullWeightsSHA256=metadata['fullWeightsSHA256'],channel=metadata['channel'],clinicalSeverity=False,localMap=None)
  layer=map_result(cv2.GaussianBlur(prediction.astype(np.float32),(0,0),2)*mask,mask,name,target,photo,'FRONT',bgr.shape,1,'percent-visible-area',1)
  if layer:
   layer.update(method=CONTRACT['version'],modelHash=metadata['sha256'],calibrationVersion=row['normalizationVersion'],clinicalSeverity=False,stagingOnly=True)
   key=name+':'+target;maps[key]=layer;row['localMap']=dict(key=key,photoId=photo,region=name,criterion=target,coordinateSpace='source-pixels')
  rows[name]=row
 return dict(output=output,rows=rows,maps=maps,support=support,meshes=meshes,normalAPIInstalled=False,preprocessing=CONTRACT)
