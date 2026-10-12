"""Detector box support is anatomical skin, independent of presentation triangles."""
import hashlib,math
import cv2,numpy as np

VERSION='source-box-anatomical-support-v2'
REGIONS=('forehead','rightCheek','leftCheek','nose','chin')

def region_envelopes(meshes,shape,scale,origin):
 result={}
 for name in REGIONS:
  if name not in meshes:continue
  points=((np.array([[v['x'],v['y']] for v in meshes[name]['points']],np.float32)-np.asarray(origin,np.float32))*scale).astype(np.float32)
  mask=np.zeros(shape,np.uint8);cv2.fillConvexPoly(mask,cv2.convexHull(points).astype(np.int32),255);result[name]=mask>0
 return result

def accepted_boxes(boxes,envelopes,skin_support,hair,exclusion,photo,scale,origin):
 assigned={k:[] for k in envelopes};rejected=[];h,w=skin_support.shape;x0,y0=origin
 for bx,by,ex,ey,confidence in boxes:
  a=max(0,int((bx-x0)*scale));b=max(0,int((by-y0)*scale));c=min(w,int(math.ceil((ex-x0)*scale)));d=min(h,int(math.ceil((ey-y0)*scale)))
  if c<=a or d<=b:rejected.append(dict(reason='OUTSIDE_SOURCE_SUPPORT'));continue
  cx=min(w-1,max(0,int(((bx+ex)/2-x0)*scale)));cy=min(h-1,max(0,int(((by+ey)/2-y0)*scale)))
  if exclusion[cy,cx] or hair[cy,cx] or float((exclusion[b:d,a:c]>0).mean())>.05:rejected.append(dict(reason='ANATOMICAL_HOLE_OR_HAIR'));continue
  owners=[k for k in REGIONS if k in envelopes and float((envelopes[k]&skin_support)[b:d,a:c].mean())>=.65]
  if not owners:rejected.append(dict(reason='INSUFFICIENT_ANATOMICAL_SKIN_SUPPORT'));continue
  assigned[owners[0]].append(dict(x=bx,y=by,width=ex-bx,height=ey-by,confidence=confidence,candidateId=hashlib.sha256(f'{photo}:{bx:.3f}:{by:.3f}:{ex:.3f}:{ey:.3f}'.encode()).hexdigest()[:24],coordinateSpace='source-pixels',localization='detection-box'))
 return assigned,rejected

def box_area(boxes,shape,scale,origin):
 area=np.zeros(shape,bool);x0,y0=origin
 for box in boxes:
  a=max(0,int((box['x']-x0)*scale));b=max(0,int((box['y']-y0)*scale));c=min(shape[1],int(math.ceil((box['x']+box['width']-x0)*scale)));d=min(shape[0],int(math.ceil((box['y']+box['height']-y0)*scale)))
  if c>a and d>b:area[b:d,a:c]=True
 return area
