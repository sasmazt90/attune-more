"""One frozen offline appearance-candidate alternative; no weights or diagnosis.
OpenCV float32 BGR[0,1] -> Lab L[0,100], a/b signed approximately[-127,127].
Positive local a* response does not establish coverage of pale/white lesions.
"""
import cv2
import numpy as np
VERSION='acne-lab-dog-mad-native-v1'
CONFIG=dict(sigmaFaceFractions=[.0035,.006,.010],surroundRatio=1.6,
 localSurroundFaceFraction=.025,madK=3.5,madScale=1.4826,minimumAResponse=.8,
 minimumLocalA=.8,minimumROIFaceArea=.005,minAreaFaceSquared=.000025,
 maxAreaFaceSquared=.002,aspect=[.45,2.2],minFill=.38,borderFaceFraction=.004,minimumL=20.)

def detect(bgr,eligible,face_width):
 if bgr.dtype!=np.uint8 or bgr.ndim!=3 or bgr.shape[2]!=3:raise ValueError('NATIVE_BGR_UINT8_REQUIRED')
 if eligible.shape!=bgr.shape[:2] or not np.isfinite(face_width) or face_width<=0:raise ValueError('INVALID_SOURCE_GEOMETRY')
 eligible=eligible.astype(bool);empty=np.zeros(eligible.shape,bool)
 if eligible.sum()<max(100,int(face_width**2*CONFIG['minimumROIFaceArea'])):return [],empty,dict(valid=False,reason='INSUFFICIENT_VISIBLE_ROI')
 lab=cv2.cvtColor(bgr.astype(np.float32)/255.,cv2.COLOR_BGR2LAB);a=lab[:,:,1]
 local=a-cv2.GaussianBlur(a,(0,0),max(.6,face_width*CONFIG['localSurroundFaceFraction']))
 response=np.zeros(a.shape,np.float32);sigmas=[max(.6,face_width*v) for v in CONFIG['sigmaFaceFractions']]
 for sigma in sigmas:
  dog=cv2.GaussianBlur(a,(0,0),sigma)-cv2.GaussianBlur(a,(0,0),sigma*CONFIG['surroundRatio']);np.maximum(response,dog,out=response)
 values=response[eligible];median=float(np.median(values));mad=float(np.median(np.abs(values-median)))
 # MAD=0 retains a physical a* floor; no epsilon-normalized false confidence.
 threshold=max(CONFIG['minimumAResponse'],median+CONFIG['madK']*CONFIG['madScale']*mad)
 radius=max(1,int(round(face_width*CONFIG['borderFaceFraction'])))
 interior=cv2.erode(eligible.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*radius+1,2*radius+1)))>0
 binary=(response>threshold)&(local>CONFIG['minimumLocalA'])&eligible
 n,labels,stats,_=cv2.connectedComponentsWithStats(binary.astype(np.uint8));objects=[];union=empty.copy();rejected={}
 for i in range(1,n):
  x,y,w,h,count=map(int,stats[i]);patch=labels[y:y+h,x:x+w]==i;reason=None
  if not max(3,face_width**2*CONFIG['minAreaFaceSquared'])<=count<=face_width**2*CONFIG['maxAreaFaceSquared']:reason='SIZE'
  elif not CONFIG['aspect'][0]<=w/max(h,1)<=CONFIG['aspect'][1] or count/(w*h)<CONFIG['minFill']:reason='SHAPE'
  elif not interior[y:y+h,x:x+w][patch].all():reason='BOUNDARY_OR_EXCLUSION'
  elif float(lab[y:y+h,x:x+w,0][patch].mean())<CONFIG['minimumL']:reason='DARK'
  if reason:rejected[reason]=rejected.get(reason,0)+1;continue
  union[y:y+h,x:x+w]|=patch
  objects.append(dict(x=x,y=y,width=w,height=h,areaPixels=count,localA=float(local[y:y+h,x:x+w][patch].mean()),peakDoG=float(response[y:y+h,x:x+w][patch].max()),pixels=np.column_stack(np.where(patch))[:,::-1]+[x,y]))
 return objects,union,dict(valid=True,median=median,mad=mad,threshold=threshold,sigmas=sigmas,rawComponents=n-1,rejections=rejected,channelContract='float32 BGR/255 -> Lab L0..100,a/b signed',madZeroBehavior='fixed physical a* floor',roiPixels=int(eligible.sum()))

def match_boxes(truth,pred,minimum_iou=.5):
 candidates=[]
 for i,a in enumerate(truth):
  for j,b in enumerate(pred):
   inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
   if union>0 and inter/union>=minimum_iou:candidates.append((inter/union,i,j))
 used_t=set();used_p=set();pairs=[]
 for score,i,j in sorted(candidates,key=lambda v:(-v[0],v[1],v[2])):
  if i not in used_t and j not in used_p:used_t.add(i);used_p.add(j);pairs.append([i,j,score])
 return pairs

def candidate_result(objects,shape,origin=(0,0),scale=1.):
 """The same list owns count, boxes and exact map. No history/baseline input."""
 mask=np.zeros(shape,bool);rows=[]
 for obj in objects:
  pixels=np.asarray(obj['pixels'],int);mask[pixels[:,1],pixels[:,0]]=True
  rows.append({**{k:v for k,v in obj.items() if k!='pixels'},'x':float(obj['x']/scale+origin[0]),'y':float(obj['y']/scale+origin[1]),'width':float(obj['width']/scale),'height':float(obj['height']/scale),'areaPixels':float(obj['areaPixels']/scale**2)})
 return dict(candidates=rows,candidateCount=len(rows),activePixels=int(mask.sum())),mask