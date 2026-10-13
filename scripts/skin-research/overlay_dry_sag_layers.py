"""Real browser points, current corridors/centers and independent boundary layers."""
import inspect,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A,instant_appearance as IA
OUT=ROOT/'audit-results/dry-sag-product-20261013';receipts=[]
for prefix in ('515cc548','c31892d1'):
 p=json.loads((OUT/(prefix+'-payload.json')).read_text('utf8'));calls=[];profiles=[];boundaries=[]
 proxy,curve,boundary=A.instant_proxy,IA.curve_profile,IA.boundary_support
 def capture(*args,**kw):
  result=proxy(*args,**kw)
  if args[3] in ('rightCheek','leftCheek','chin'):calls.append(dict(args=args,centers=list(result[1].get('_samplingCenters',[])),reason=result[-1]))
  return result
 def profile(*args,**kw):
  f=inspect.currentframe().f_back.f_locals;q=curve(*args,**kw)
  if q is not None and f.get('region') in ('rightCheek','leftCheek','chin'):profiles.append(dict(region=f['region'],side=f['side'],guide=args[2].copy(),target=f['eligible'].copy(),q=q))
  return q
 def edge(*args,**kw):
  f=inspect.currentframe().f_back.f_locals;q=boundary(*args,**kw)
  if f.get('region') in ('rightCheek','leftCheek','chin'):boundaries.append(dict(region=f['region'],guide=args[2].copy(),tracked=list(q['points']),supported=list(q.get('supported',[])),value=q['value'],coverage=q['coverage']))
  return q
 A.instant_proxy=capture;IA.curve_profile=profile;IA.boundary_support=edge
 try:result=A.analyze_skin(p)
 finally:A.instant_proxy=proxy;IA.curve_profile=curve;IA.boundary_support=boundary
 actual=json.loads((OUT/(prefix+'-normal-api.json')).read_text('utf8'));same=all(result[k]==actual[k] for k in ('measurements','maps','contours'));assert same
 image=A.decode_photo(p['photo'])[0];h,w=image.shape[:2];layers=[image.copy() for _ in range(4)]
 for v in p['landmarks']:cv2.circle(layers[0],(round(v['x']*w),round(v['y']*h)),1,(240,100,20),-1)
 scale=calls[0]['args'][5];origin=calls[0]['args'][6];shape=calls[0]['args'][0].shape
 def source(xy):return tuple(np.rint(np.asarray(xy)/scale+origin).astype(int))
 geometry=np.zeros(shape,bool)
 for region in ('rightCheek','leftCheek','chin'):
  m=p['meshes'][region];geometry|=A.closed_surface_mask(shape,m,scale,origin)
  for a,b in m['edges']:cv2.line(layers[1],(round(m['points'][a]['x']),round(m['points'][a]['y'])),(round(m['points'][b]['x']),round(m['points'][b]['y'])),(230,180,20),1)
 for box in p['exclusions']:cv2.rectangle(layers[1],(round(box['x']),round(box['y'])),(round(box['x']+box['w']),round(box['y']+box['h'])),(20,20,230),1)
 corners=[source([0,0]),source([shape[1]-1,shape[0]-1])];cv2.rectangle(layers[0],*corners,(20,240,240),1)
 for call in calls:
  args=call['args'];ys,xs=np.where(args[1]);
  for x,y in zip(xs[::5],ys[::5]):cv2.circle(layers[1],source([x,y]),1,(80,180,60),-1)
  for x,y,value in call['centers']:cv2.circle(layers[2],source([x,y]),2,(20,240,240) if value>0 else (230,120,20),-1)
 for v in profiles:
  ys,xs=np.where(v['target'])
  for x,y in zip(xs[::5],ys[::5]):cv2.circle(layers[2],source([x,y]),1,(90,150,70),-1)
  cv2.polylines(layers[2],[np.asarray([source(xy) for xy in v['guide']],np.int32)],False,(230,20,230),1)
 for call in calls:
  for x,y,value in call['centers']:cv2.circle(layers[2],source([x,y]),2,(20,240,240) if value>0 else (230,120,20),-1)
 for v in boundaries:
  cv2.polylines(layers[3],[np.asarray([source(xy) for xy in v['guide']],np.int32)],False,(230,20,230),1)
  for xy,supported in zip(v['tracked'],v['supported']):cv2.circle(layers[3],source(xy),1,(20,240,240) if supported else (20,20,230),-1)
 for i,title in enumerate(('real MP points / actual crop','actual selected cells / exposure exclusions','current guides / unique measured centers','independent jaw: tracked supported/rejected')):
  layers[i]=cv2.copyMakeBorder(layers[i],28,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20));cv2.putText(layers[i],title,(5,20),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1)
 cv2.imwrite(str(OUT/(prefix+'-current-layers.jpg')),np.concatenate([np.concatenate(layers[:2],axis=1),np.concatenate(layers[2:],axis=1)],axis=0))
 row=dict(source=prefix,actualAPIEqualsReplay=same,sourceShape=[w,h],analysisOrigin=list(origin),analysisScale=scale,realMPPointCount=len(p['landmarks']),conditions=p['conditions'],regions=[dict(region=v['args'][3],selectedVisibleSurfacePixels=int(v['args'][1].sum()),analysisHairPixels=int(v['args'][8].sum()),analysisClippedPixels=int(v['args'][10].sum()),uniqueObservedCenters=len(v['centers']),positiveCenters=sum(x[2]>0 for x in v['centers']),limitation=v['reason']) for v in calls],profileTargets=[dict(region=v['region'],side=v['side'],actualTargetCorridorPixels=int(v['target'].sum()),observedProfileSamples=int(v['q']['observedSamples'].sum()),allProfileSamples=len(v['q']['observedSamples'])) for v in profiles],boundaries=[{k:v[k] for k in ('region','value','coverage')} for v in boundaries])
 receipts.append(row);print(json.dumps(row),flush=True)
(OUT/'current-layer-receipt.json').write_text(json.dumps(receipts,indent=2),'utf8')
