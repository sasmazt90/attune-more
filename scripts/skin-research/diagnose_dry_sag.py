"""Bounded source/analysis texture and tracked-center audit on real payloads."""
import inspect,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
from load_dry_sag_baseline import load_baseline
A,IA,_=load_baseline()
OUT=ROOT/'audit-results/dry-sag-product-20261013';rows=[]
sources=json.loads((OUT/'source-selection.json').read_text('utf8'))
for source in sources:
 prefix=source['sha256'][:8];file=OUT/(prefix+'-payload.json')
 if not file.exists():continue
 payload=json.loads(file.read_text('utf8'));calls=[];profiles=[];proxy=A.instant_proxy;curve=IA.curve_profile
 def capture(*args,**kw):
  if args[3] in ('rightCheek','leftCheek','chin'):calls.append(args)
  return proxy(*args,**kw)
 def capture_curve(*args,**kw):
  frame=inspect.currentframe().f_back;region=frame.f_locals.get('region');target=frame.f_locals.get('eligible')
  q=curve(*args,**kw)
  if region in ('rightCheek','leftCheek','chin'):
   local=curve(*args,center_support=target)
   profiles.append(dict(region=region,old=q,local=local,target=target.copy(),guide=args[2].copy(),normal=args[3].copy(),offsets=args[4].copy(),width=args[5]))
  return q
 A.instant_proxy=capture;IA.curve_profile=capture_curve
 try:result=A.analyze_skin(payload)
 finally:A.instant_proxy=proxy;IA.curve_profile=curve
 bgr=A.decode_photo(payload['photo'])[0];face=abs(payload['landmarks'][454]['x']-payload['landmarks'][234]['x'])*bgr.shape[1];scale=min(1,320/max(face,1));pts=np.asarray([[p['x'],p['y']] for m in payload['meshes'].values() for p in m['points']],np.float32);pad=max(20,face*.1);x0=max(0,int(pts[:,0].min()-pad));y0=max(0,int(pts[:,1].min()-pad));x1=min(bgr.shape[1],int(pts[:,0].max()+pad+1));y1=min(bgr.shape[0],int(pts[:,1].max()+pad+1));image=cv2.resize(bgr[y0:y1,x0:x1],None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA);gray8=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
 accepted,raw,contrast,lbp,dark,high=A.compute_dryness_signal(gray8)
 native=A.compute_dryness_signal(cv2.cvtColor(bgr[y0:y1,x0:x1],cv2.COLOR_BGR2GRAY))
 clipped=image.max(axis=2)>255*.975;luma_clipped=gray8>255*.975
 row=dict(sourceSHA256=source['sha256'],imageCategory=source['imageCategory'],origin=[x0,y0],scale=scale,textureStages=dict(nativeCandidatePixels=int((native[1]>.04).sum()),nativeAcceptedPixels=int((native[0]>.04).sum()),analysisCandidatePixels=int((raw>.04).sum()),analysisAcceptedPixels=int((accepted>.04).sum()),darkRingRemovedPixels=int(((raw>.04)&dark).sum()),channelMaxClippedPixels=int(clipped.sum()),lumaClippedPixels=int(luma_clipped.sum()),colorClippedButLumaDetailedPixels=int((clipped&~luma_clipped).sum())),profiles=[])
 panels=[]
 def panel(title,mask,color=(0,255,255)):
  z=image.copy();z[mask]=(z[mask]*.4+np.asarray(color)*.6).astype('uint8');z=cv2.resize(z,(420,440));z=cv2.copyMakeBorder(z,28,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20));cv2.putText(z,title,(5,20),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1);panels.append(z)
 panel('raw DoG / LBP / contrast',raw>.04);panel('accepted islands before anatomy',accepted>.04,(0,255,0));panel('blackhat ring exclusion',dark,(0,0,255));panel('max-channel clipping',clipped,(255,0,255));panel('luma clipping',luma_clipped,(255,0,255))
 for q in profiles:
  old,local=q['old'],q['local'];entry=dict(region=q['region'],before={k:old[k] for k in ['strength','edge','coverage','continuity','trackingResidual']},targetCenters={k:local[k] for k in ['strength','edge','coverage','continuity','trackingResidual']})
  actualXY=np.rint(old['tracked']).astype(int);inside=[]
  for xy,supported in zip(actualXY,old['support']):
   if supported:inside.append(bool(q['target'][xy[1],xy[0]]))
  entry['oldSupportedCenters']=len(inside);entry['oldSupportedCentersOutsideActualTarget']=sum(not v for v in inside);row['profiles'].append(entry)
  panel(q['region']+' selected target corridor',q['target'],(0,255,0))
  z=image.copy()
  for kind,color in [('old',(0,0,255)),('local',(0,255,0))]:
   for xy,supported in zip(q[kind]['tracked'],q[kind]['support']):
    if supported:cv2.circle(z,tuple(np.rint(xy).astype(int)),1,color,-1)
  z=cv2.resize(z,(420,440));z=cv2.copyMakeBorder(z,28,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20));cv2.putText(z,q['region']+' context red / local green',(5,20),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1);panels.append(z)
 while len(panels)%3:panels.append(panels[-1]*0)
 cv2.imwrite(str(OUT/(prefix+'-diagnosis.jpg')),np.concatenate([np.concatenate(panels[i:i+3],axis=1) for i in range(0,len(panels),3)],axis=0))
 rows.append(row);print(json.dumps({'source':prefix,'texture':row['textureStages'],'sagProfileCounts':[(v['region'],v['oldSupportedCentersOutsideActualTarget'],v['targetCenters']['coverage']) for v in row['profiles']]}),flush=True)
(OUT/'diagnosis.json').write_text(json.dumps(rows,indent=2),'utf8')
