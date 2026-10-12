"""Captured same-input bag centers and sparse impulse proximity; no runtime edits."""
import json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A,instant_appearance as IA
OUT=ROOT/'audit-results/lines-bags-followup-20261012'
import importlib.util
def frozen(name,file):
 spec=importlib.util.spec_from_file_location(name,file);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
baseline=ROOT/'.runtime/lines-v4-frozen-20261012/baseline'
A=frozen('delivered_photometry',baseline/'appearance_analysis.py')
IA=frozen('delivered_profile',baseline/'instant_appearance.py')
A.instant_proxy=IA.instant_proxy

rows=[]
for prefix in audit.PREFIXES:
 p=json.loads((ROOT/'audit-results/bag-label-followup-20261012'/(prefix+'-v2-payload.json')).read_text('utf8'))
 captures=[];profiles=[];proxy=A.instant_proxy;curve=IA.curve_profile
 def capture(*args,**kw):
  if args[3]=='periorbital':captures.append(args)
  return proxy(*args,**kw)
 def capture_curve(*args,**kw):
  q=curve(*args,**kw)
  if kw.get('center_support') is not None:profiles.append(q)
  return q
 A.instant_proxy=capture;IA.curve_profile=capture_curve
 try:r=A.analyze_skin(p)
 finally:A.instant_proxy=proxy;IA.curve_profile=curve
 gray,eligible,_,_,_,scale,origin,shape,*_=captures[0]
 bgr=A.decode_photo(p['photo'])[0];native=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY);median=cv2.medianBlur(native,3)
 residual=np.abs(native.astype(float)-median)/255
 suspect=residual>.35
 n,labels,stats,_=cv2.connectedComponentsWithStats(suspect.astype('uint8'),8)
 tiny=np.isin(labels,np.where((stats[:,cv2.CC_STAT_AREA]<=2)&(np.arange(n)>0))[0])
 nearby=cv2.dilate(tiny.astype('uint8'),np.ones((7,7),np.uint8))>0
 image=bgr.copy();centers=[]
 for q in profiles:
  for xy,supported,val,edge in zip(q['tracked'],q['support'],q['values'],q['edgeValues']):
   if not supported:continue
   x,y=np.rint(np.asarray(xy)/scale+origin).astype(int)
   centers.append(dict(x=int(x),y=int(y),fold=float(val),edge=float(edge),nearImpulse=bool(nearby[y,x])))
   cv2.circle(image,(x,y),2,(0,0,255) if nearby[y,x] else (0,255,0),1)
 image[tiny]=(255,0,255)
 cv2.imwrite(str(OUT/(prefix+'-impulses-centers.png')),image)
 bag=next(v for v in r['measurements']['periorbital'] if v['id']=='bags')
 row=dict(source=prefix,value=bag['value'],sourceImpulsePixels=int(tiny.sum()),supportedCenters=len(centers),nearImpulseCenters=sum(v['nearImpulse'] for v in centers),centers=centers)
 rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='centers'}),flush=True)
(OUT/'noise-proximity.json').write_text(json.dumps(rows,indent=2),'utf8')
