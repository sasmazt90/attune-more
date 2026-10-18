"""Attribute saved matched-box losses to actual numerical support stages.
Reuses saved predictions and landmarks, without inference or live API edits.
"""
import json,sys,subprocess,shutil
import cv2,numpy as np
from expanded_sources import ROOT,OUT,write,sha
sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import polygon_mask,elongated_dark_mask

def read(p):return json.loads(p.read_text('utf8'))
def main():
 d=OUT/'interim-diagnosis';results=[];sources={r['sha256']:r for r in read(OUT/'negative-expanded-detector-data.json')['rows']}
 for row in read(d/'front-filter-control.json')['rows']:
  r=sources[row['sha256']];im=cv2.imread(r['absolutePath']);assert sha(__import__('pathlib').Path(r['absolutePath']))==r['sha256'];h,w=im.shape[:2];points=row['landmarks'];mesh=json.loads(subprocess.check_output([shutil.which('node'),str(ROOT/'scripts/skin-research/focused_meshes.cjs')],input=json.dumps([dict(sha256=r['sha256'],landmarks=points,width=w,height=h)]).encode(),cwd=ROOT))[0]['meshes']
  face_pixels=abs(points[454]['x']-points[234]['x'])*w;scale=min(1,320/max(face_pixels,1));p=np.array([[v['x'],v['y']] for m in mesh.values() for v in m['points']]);pad=max(20,face_pixels*.1);x0=max(0,int(p[:,0].min()-pad));y0=max(0,int(p[:,1].min()-pad));x1=min(w,int(p[:,0].max()+pad+1));y1=min(h,int(p[:,1].max()+pad+1));image=cv2.resize(im[y0:y1,x0:x1],None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA);gray8=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);gray=gray8/255;clipping=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)[:,:,2]/255>.975;hair=elongated_dark_mask(gray8);exclusion=np.zeros(gray.shape,np.uint8)
  def poly(ids):return np.array([[(points[i]['x']*w-x0)*scale,(points[i]['y']*h-y0)*scale] for i in ids],np.int32)
  for ids in [[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327,294],[70,63,105,66,107,55,65,52],[300,293,334,296,336,285,295,282]]:cv2.fillPoly(exclusion,[poly(ids)],255)
  edge=max(2,round(4*scale));exclusion[:edge]=255;exclusion[-edge:]=255;exclusion[:,:edge]=255;exclusion[:,-edge:]=255
  masks={k:polygon_mask(gray.shape,m,scale,(x0,y0)) for k,m in mesh.items()};overall=np.logical_or.reduce(list(masks.values()))&(exclusion==0)&~hair&~clipping&(gray>.12);records=[]
  for v in row['decoder']['rows']:
   if v['category']!='matched_source_box':continue
   bx,by,ex,ey,_=v['box'];a=max(0,int((bx-x0)*scale));b=max(0,int((by-y0)*scale));c=min(gray.shape[1],int(np.ceil((ex-x0)*scale)));e=min(gray.shape[0],int(np.ceil((ey-y0)*scale)));assert a<c and b<e
   region={k:float(m[b:e,a:c].mean()) for k,m in masks.items() if k!='periorbital'};max_support=max(float((m&overall)[b:e,a:c].mean()) for k,m in masks.items() if k!='periorbital');known_visibility=(exclusion==0)&~hair&~clipping&(gray>.12)
   records.append(dict(truthIndex=v['matchedTruth'],box=v['box'],anatomicalMeshFractions=region,bestMeshFraction=max(region.values()),bestActualEligibleFraction=max_support,explicitHoleFraction=float((exclusion[b:e,a:c]>0).mean()),hairFraction=float(hair[b:e,a:c].mean()),clippedFraction=float(clipping[b:e,a:c].mean()),darkFraction=float((gray[b:e,a:c]<=.12).mean()),qualityIndependentKnownVisibilityFraction=float(known_visibility[b:e,a:c].mean()),removed=v['matchedTruth'] in row['removedMatchedTruth'],reason='sparse presentation mesh support' if max(region.values())<.65 else 'hair/exposure/explicit-hole support exclusion' if max_support<.65 else 'eligible'))
  results.append(dict(sha256=r['sha256'],isAligned=row['alignment']['isAligned'],records=records,filterCoverageThreshold=.65,productionCodeUnchanged=True))
 write('interim-diagnosis/product-box-support-attribution.json',dict(rows=results,noNewInference=True,sourceCoordinateTransformReconstructed=True,acceptanceThresholdsChanged=False));print('BOX SUPPORT ATTRIBUTION',[(r['sha256'][:12],[(v['truthIndex'],v['reason'],v['hairFraction'],v['clippedFraction']) for v in r['records']]) for r in results],flush=True)
if __name__=='__main__':main()
