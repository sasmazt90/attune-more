"""Detector box support is anatomical skin, independent of presentation triangles."""
import hashlib,math
import cv2,numpy as np

VERSION='source-box-anatomical-support-v4'
REGIONS=('forehead','rightCheek','leftCheek','nose','chin')

def region_envelopes(meshes,shape,scale,origin):
 result={}
 for name in REGIONS:
  if name not in meshes:continue
  points=((np.array([[v['x'],v['y']] for v in meshes[name]['points']],np.float32)-np.asarray(origin,np.float32))*scale).astype(np.float32)
  mask=np.zeros(shape,np.uint8);cv2.fillConvexPoly(mask,cv2.convexHull(points).astype(np.int32),255);result[name]=mask>0
 return result

def accepted_boxes(boxes,envelopes,skin_support,hair,exclusion,photo,scale,origin,visible_regions=None,landmarks=None):
 assigned={k:[] for k in envelopes};rejected=[];h,w=skin_support.shape;x0,y0=origin
 candidate_regions=[k for k in REGIONS if k in envelopes and (visible_regions is None or k in visible_regions)]
 skin_pts=np.where(skin_support)
 face_width=float(skin_pts[1].max()-skin_pts[1].min()) if len(skin_pts[0])>0 else float(w)
 face_width=max(10.0,face_width)
 midline_x=float(landmarks[1]['x']*(w/scale)-x0)*scale if (landmarks and len(landmarks)>=2 and isinstance(landmarks[1],dict) and 'x' in landmarks[1]) else float(w/2)
 dist_maps={}
 for bx,by,ex,ey,confidence in boxes:
  a=max(0,int((bx-x0)*scale));b=max(0,int((by-y0)*scale));c=min(w,int(math.ceil((ex-x0)*scale)));d=min(h,int(math.ceil((ey-y0)*scale)))
  if c<=a or d<=b:rejected.append(dict(box=[bx,by,ex,ey,confidence],reason='OUTSIDE_SOURCE_SUPPORT'));continue
  cx=min(w-1,max(0,int(((bx+ex)/2-x0)*scale)));cy=min(h-1,max(0,int(((by+ey)/2-y0)*scale)))
  if exclusion[cy,cx] or hair[cy,cx] or float((exclusion[b:d,a:c]>0).mean())>.25:rejected.append(dict(box=[bx,by,ex,ey,confidence],reason='ANATOMICAL_HOLE_OR_HAIR'));continue
  box_skin=float(skin_support[b:d,a:c].mean())
  if box_skin<.50 or not skin_support[cy,cx]:rejected.append(dict(box=[bx,by,ex,ey,confidence],reason='INSUFFICIENT_SKIN_SUPPORT'));continue
  reg_overlaps=[(float((envelopes[k]&skin_support)[b:d,a:c].mean()),k) for k in candidate_regions]
  reg_overlaps.sort(reverse=True)
  if reg_overlaps and reg_overlaps[0][0]>=.15:
   owner=reg_overlaps[0][1];assign_reason='ENVELOPE_OVERLAP'
  else:
   best_dist=float('inf');best_candidate=None
   for k in candidate_regions:
    if k=='leftCheek' and cx<midline_x-face_width*.05:continue
    if k=='rightCheek' and cx>midline_x+face_width*.05:continue
    if k not in dist_maps:
     dist_maps[k]=cv2.distanceTransform((~envelopes[k]).astype(np.uint8),cv2.DIST_L2,3)
    d_val=float(dist_maps[k][cy,cx])
    if d_val<best_dist:best_dist=d_val;best_candidate=k
   norm_dist=best_dist/face_width if best_candidate else float('inf')
   if best_candidate is not None and norm_dist<=.15:
    owner=best_candidate;assign_reason=f'ANATOMICAL_DISTANCE_FALLBACK(norm_dist={norm_dist:.3f})'
   else:
    rejected.append(dict(box=[bx,by,ex,ey,confidence],reason='UNCERTAIN_ANATOMICAL_REGION',norm_dist=round(norm_dist,4) if best_candidate else None));continue
  assigned[owner].append(dict(x=bx,y=by,width=ex-bx,height=ey-by,confidence=confidence,region=owner,assignmentReason=assign_reason,candidateId=hashlib.sha256(f'{photo}:{bx:.3f}:{by:.3f}:{ex:.3f}:{ey:.3f}'.encode()).hexdigest()[:24],coordinateSpace='source-pixels',localization='detection-box'))
 return assigned,rejected

def box_area(boxes,shape,scale,origin):
 area=np.zeros(shape,bool);x0,y0=origin
 for box in boxes:
  a=max(0,int((box['x']-x0)*scale));b=max(0,int((box['y']-y0)*scale));c=min(shape[1],int(math.ceil((box['x']+box['width']-x0)*scale)));d=min(shape[0],int(math.ceil((box['y']+box['height']-y0)*scale)))
  if c>a and d>b:area[b:d,a:c]=True
 return area
