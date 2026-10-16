"""Post-freeze visual evidence only; no relabel, fit or metric rerun."""
import collections,sys
import numpy as np
from verifier_v4_round import *
from verifier_v4_dev import source_inventory,key

def main():
 import cv2
 from heavy_job_lease import HeavyJobLease
 r=read(OUT/'dev-results.json');L=read(SRC/'docs/acne-point-relabel-layer1-20261016.json')['photos'];photos=source_inventory();cases=[]
 for kind in ['gainedVsV3','lostVsV3']:
  for identity in r['targets']['v4'][kind]:
   ph,tid=identity.split('#');pt=next(p for p in L[ph]['points'] if p['id']==tid)
   cases.append(dict(kind=kind,photo=ph,targetID=tid,x=pt['x'],y=pt['y'],referenceCategory=pt['cat']))
 for ph,d in r['pointChangesVsV3'].items():
  for q in d['removedFalse']:
   b=q['box'];cases.append(dict(kind='removedFalse',photo=ph,box=b,x=(b[0]+b[2])/2,y=(b[1]+b[3])/2,referenceCategory='false in frozen reviewed skin',newClass=q['v4Class']))
 added=sorted(r['pointChangesVsV3'],key=lambda p:(-len(r['pointChangesVsV3'][p]['addedFalse']),p))[:3]
 for ph in added:
  for q in r['pointChangesVsV3'][ph]['addedFalse'][:2]:
   b=q['box'];cases.append(dict(kind='addedFalse',photo=ph,box=b,x=(b[0]+b[2])/2,y=(b[1]+b[3])/2,referenceCategory='false in frozen reviewed skin',priorClass=q['v3Class']))
 assert not (OUT/'visual-evidence.json').exists(),'VISUAL_EVIDENCE_ALREADY_CREATED'
 folder=OUT/'visual-evidence';folder.mkdir(exist_ok=True)
 colors={'matched':(40,215,40),'false':(20,20,240),'duplicate':(230,170,20),'onUncertain':(0,170,240),'onOther':(230,70,200)}
 def panel(im,ph,n,x,y,half):
  a,b=int(round(x-half)),int(round(y-half));size=max(2,int(round(2*half)));can=np.zeros((size,size,3),np.uint8);x0,y0=max(a,0),max(b,0);x1,y1=min(im.shape[1],a+size),min(im.shape[0],b+size);can[y0-b:y1-b,x0-a:x1-a]=im[y0:y1,x0:x1];scale=384/size;can=cv2.resize(can,(384,384),interpolation=cv2.INTER_CUBIC if size<384 else cv2.INTER_AREA)
  # Unchanged source pixels; coloured point symbols and target rings are evidence overlays only.
  for q in L[ph]['points']:
   if q['cat']=='TARGET' and a<=q['x']<a+size and b<=q['y']<b+size:
    pt=(round((q['x']-a)*scale),round((q['y']-b)*scale));cv2.circle(can,pt,max(3,round(.03*L[ph]['faceWidthPx']*scale)),(0,230,230),1)
  for bb,cl in zip(r['candidateBoxes'][n][ph],r['perPhotoClasses'][n][ph]['classes']):
   cx,cy=(bb[0]+bb[2])/2,(bb[1]+bb[3])/2
   if a<=cx<a+size and b<=cy<b+size:cv2.drawMarker(can,(round((cx-a)*scale),round((cy-b)*scale)),colors.get(cl,(180,180,180)),cv2.MARKER_CROSS,9,1)
  cv2.drawMarker(can,(round((x-a)*scale),round((y-b)*scale)),(255,255,255),cv2.MARKER_DIAMOND,18,1)
  return can,dict(sourceOrigin=[a,b],sourceSide=size,displayScale=scale,focus=[x,y],imageSize=[im.shape[1],im.shape[0]])
 with HeavyJobLease('CDC-verifier-v4-post-freeze-visual-evidence',peak_mib=900,minimum_available_mib=1600,memory_metric='private') as lease:
  cv2.setNumThreads(2)
  for i,c in enumerate(cases):
   lease.check();ph=c['photo'];im=cv2.imread(photos[ph]['file']);assert sha(photos[ph]['file'])==photos[ph]['sha256'];fw=L[ph]['faceWidthPx'];half=max(36,.12*fw)
   panels=[]
   for n in ['v3','v4']:
    p,transform=panel(im,ph,n,c['x'],c['y'],half);panels.append(p)
   full=np.zeros((384,384,3),np.uint8);ratio=min(384/im.shape[1],384/im.shape[0]);small=cv2.resize(im,None,fx=ratio,fy=ratio,interpolation=cv2.INTER_AREA);oy=(384-small.shape[0])//2;ox=(384-small.shape[1])//2;full[oy:oy+small.shape[0],ox:ox+small.shape[1]]=small;cv2.drawMarker(full,(round(c['x']*ratio+ox),round(c['y']*ratio+oy)),(0,255,255),cv2.MARKER_CROSS,12,1)
   sheet=np.full((444,1152,3),245,np.uint8);sheet[60:]=np.hstack([full]+panels);title=f'{i+1:02} {c["kind"]} {ph} {c.get("targetID","")}'
   cv2.putText(sheet,title,(6,20),cv2.FONT_HERSHEY_SIMPLEX,.56,(0,0,0),1)
   for name,offset in [('Full source + focus',0),('V3',384),('V4',768)]:cv2.putText(sheet,name,(offset+6,46),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,0,0),1)
   p=folder/f'case-{i+1:02}.jpg';cv2.imwrite(str(p),sheet,[cv2.IMWRITE_JPEG_QUALITY,95]);c.update(file=str(p),sha256=sha(p),sourceSHA256=photos[ph]['sha256'],sourceFile=photos[ph]['file'],cropTransform=transform)
  atomic('visual-evidence.json',dict(cases=cases,legend={'yellow circle':'frozen TARGET match radius, not a pixel mask','green cross':'matched prediction','red cross':'false point inside reviewed mask','blue cross':'duplicate','orange cross':'UNCERTAIN vicinity','white diamond':'case focus'},note='post-freeze inspection; does not change frozen labels or predictions; local images are not committed or uploaded',resource=lease.receipt()))
 print('VISUAL_CASES',len(cases))
if __name__=='__main__':main()
