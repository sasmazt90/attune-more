"""Bounded captured product-input geometry audit; local licensed sources only."""
import json,sys,itertools
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A,instant_appearance as IA
OUT=ROOT/'audit-results/bag-label-followup-20261012';OUT.mkdir(parents=True,exist_ok=True)
sources=json.loads((audit.OUT/'sources.json').read_text('utf8'))['sources']
def closed_cells(mesh):
 p=np.asarray([[v['x'],v['y']] for v in mesh['points']]);edges={tuple(sorted(e)) for e in mesh['edges']};cells={}
 for a,b,c,d in itertools.permutations(range(len(p)),4):
  if a!=min(a,b,c,d) or b>d:continue
  if all(tuple(sorted(e)) in edges for e in ((a,b),(b,c),(c,d),(d,a))) and (a,c) not in edges and tuple(sorted((b,d))) not in edges:
   polygon=p[[a,b,c,d]].astype(np.float32)
   if cv2.isContourConvex(polygon):cells[tuple(sorted((a,b,c,d)))]=[a,b,c,d]
 return list(cells.values())
rows=[]
for source in sources[:5]:
 prefix=source['sha256'][:8];captured=json.loads((audit.OUT/(prefix+'-browser-api.json')).read_text('utf8'));payload=json.loads((OUT/(prefix+'-v2-payload.json')).read_text('utf8')) if '--v2' in sys.argv else captured['productPayload'];calls=[];profiles=[]
 original=A.instant_proxy;profile=IA.curve_profile
 def capture(*args,**kwargs):
  if args[3]=='periorbital':calls.append(args)
  return original(*args,**kwargs)
 def capture_profile(*args,**kwargs):
  q=profile(*args,**kwargs)
  if kwargs.get('center_support') is not None:profiles.append(dict(local=q,broad=profile(*args),guide=args[2],normal=args[3],offsets=args[4],width=args[5]))
  return q
 A.instant_proxy=capture;IA.curve_profile=capture_profile
 try:actual=A.analyze_skin(payload)
 finally:A.instant_proxy=original;IA.curve_profile=profile
 gray,target,points,region,conditions,scale,origin,shape,hair,context,clipping,exposure=calls[0]
 bands=A.eye_skin_bands(points,gray.shape,scale,origin,shape);mesh=payload['meshes']['periorbital'];union=A.polygon_mask(gray.shape,mesh,scale,origin);cells=closed_cells(mesh);gaps=np.zeros(gray.shape,np.uint8)
 for cell in cells:
  poly=np.asarray([[(mesh['points'][i]['x']-origin[0])*scale,(mesh['points'][i]['y']-origin[1])*scale] for i in cell],np.int32);cv2.fillPoly(gaps,[poly],1)
 positive=audit.known_roi(source,shape,['acne','oil','dry','redness','tone','lines','dark','bags'],positive=source['sampleCategory']=='development_positive_polygon')
 native_positive=positive[origin[1]:origin[1]+round(gray.shape[0]/scale),origin[0]:origin[0]+round(gray.shape[1]/scale)];truth=cv2.resize(native_positive.astype('uint8'),(gray.shape[1],gray.shape[0]),interpolation=cv2.INTER_NEAREST)>0
 row=dict(source=prefix,origin=list(origin),scale=scale,analysisShape=list(gray.shape),missingDiagonalClosedCells=cells,oldUnionPixels=int(union.sum()),closedCellGapPixels=int(((gaps>0)&~union).sum()),positivePixels=int(truth.sum()),positiveInsideTriangleUnion=int((truth&union).sum()),positiveInsideClosedCellGap=int((truth&(gaps>0)&~union).sum()),positiveInsideBand=int((truth&bands['bags']).sum()),actualBag=next(v for v in actual['measurements']['periorbital'] if v['id']=='bags'),profiles=[])
 row['labelScope']='partial-positive-polygon' if source['sampleCategory']=='development_positive_polygon' else 'reviewed-negative-support-only'
 row['labelSupportBreakdown']=dict(knownPixels=int(truth.sum()),outsideBand=int((truth&~bands['bags']).sum()),inBand=int((truth&bands['bags']).sum()),insideEligible=int((truth&target).sum()),hairInBand=int((truth&bands['bags']&hair).sum()),clippedInBand=int((truth&bands['bags']&clipping).sum()),outsideOldTriangleUnionInBand=int((truth&bands['bags']&~union).sum()))
 smooth=cv2.GaussianBlur(gray,(0,0),8);ys,xs=np.where(target);design=np.column_stack([(xs-xs.min())/max(np.ptp(xs),1),(ys-ys.min())/max(np.ptp(ys),1),np.ones(len(xs))]);slope=np.linalg.lstsq(design,smooth[target],rcond=None)[0];row['shadowPlaneSlopeNorm']=float(np.linalg.norm(slope[:2]))
 panels=[];image=cv2.cvtColor(np.round(gray*255).astype('uint8'),cv2.COLOR_GRAY2BGR)
 def panel(label,mask,color=(0,255,255)):
  z=image.copy();z[mask]=z[mask]*.4+np.asarray(color)*.6;panels.append((label,z))
 panel('triangle-union',union,(0,255,0));panel('closed-cell gaps',gaps>0,(255,0,255));panel('lower-eye band',bands['bags']);panel('hair exclusion',hair,(0,0,255));panel('clipping',clipping,(255,255,255));panel('accepted support',target,(0,255,0));panel('partial positive only',truth,(255,0,0))
 boxes=np.zeros(gray.shape,np.uint8)
 for box in payload['exclusions']:
  x,y,w,h=[int(v*scale) for v in (box['x']-origin[0],box['y']-origin[1],box['w'],box['h'])];cv2.rectangle(boxes,(x,y),(x+w,y+h),1,-1)
 panel('automatic rectangles',boxes>0,(255,0,255));centers=image.copy();landmarks=image.copy()
 for i,p in enumerate(points):
  xy=tuple(np.rint([(p['x']*shape[1]-origin[0])*scale,(p['y']*shape[0]-origin[1])*scale]).astype(int));cv2.circle(landmarks,xy,1,(255,255,0),-1)
 panels.append(('browser landmarks',landmarks))
 corridors=np.zeros(gray.shape,np.uint8)
 for q in profiles:
  local,broad=q['local'],q['broad'];entry={kind:{k:v[k] for k in ('strength','continuity','coverage','trackingResidual')} for kind,v in [('local',local),('broad',broad)]};row['profiles'].append(entry)
  cv2.polylines(corridors,[np.rint(q['guide']).astype(np.int32)],False,1,max(1,int(np.ceil(2*max(abs(v) for v in q['offsets'])*q['width']/320+1))))
  for kind,prof,color in [('broad',broad,(0,0,255)),('local',local,(0,255,0))]:
   for xy,support in zip(prof['tracked'],prof['support']):
    if support:cv2.circle(centers,tuple(np.rint(xy).astype(int)),1,color,-1)
 panels.append(('tracked: context red / local green',centers))
 panel('tracking corridor (quality)',corridors>0,(255,255,0));panel('closed-cell bag support',A.bag_support_mask(gray.shape,mesh,scale,origin),(0,255,0))
 # Same eye crop for every layer, rather than a y-only anatomical test.
 xy=np.asarray([[(points[i]['x']*shape[1]-origin[0])*scale,(points[i]['y']*shape[0]-origin[1])*scale] for i in (33,263,120,349)])
 x0=max(0,int(xy[:,0].min()-30));x1=min(gray.shape[1],int(xy[:,0].max()+30));y0=max(0,int(xy[:,1].min()-25));y1=min(gray.shape[0],int(xy[:,1].max()+30))
 tiles=[]
 for label,z in panels:
  tile=cv2.resize(z[y0:y1,x0:x1],(500,220));tile=cv2.copyMakeBorder(tile,30,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20));cv2.putText(tile,label,(8,22),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1);tiles.append(tile)
 sheet=np.concatenate([np.concatenate(tiles[i:i+2],axis=1) for i in range(0,len(tiles),2)],axis=0);cv2.imwrite(str(OUT/(prefix+('-v2' if '--v2' in sys.argv else '')+'-layers.png')),sheet)
 rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ('actualBag','profiles','missingDiagonalClosedCells')}),flush=True)
(OUT/('support-diagnosis-v2.json' if '--v2' in sys.argv else 'support-diagnosis.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
