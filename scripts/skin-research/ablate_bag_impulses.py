"""Bounded photometric ablation: only isolated native one/two-pixel impulses.

No source rewrite, geometry change, threshold change, or running-code patch.
"""
import json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
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
 bgr=A.decode_photo(p['photo'])[0];gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY);med=cv2.medianBlur(gray,3)
 suspect=(np.abs(gray.astype(float)-med)/255)>.35
 n,labels,stats,_=cv2.connectedComponentsWithStats(suspect.astype('uint8'),8)
 tiny=np.isin(labels,np.where((stats[:,cv2.CC_STAT_AREA]<=2)&(np.arange(n)>0))[0])
 corrected=bgr.copy();corrected[tiny]=cv2.medianBlur(bgr,3)[tiny]
 before=[];original=A.instant_proxy
 def sample(*args,**kwargs):
  if args[3]!='periorbital':return original(*args,**kwargs)
  before.append(original(*args,**kwargs)[0])
  _,_,_,_,_,scale,(x0,y0),_,*_=args
  # Reproduce exactly the production source crop/INTER_AREA, not a guessed grid.
  face=abs(p['landmarks'][454]['x']-p['landmarks'][234]['x'])*bgr.shape[1]
  pts=np.asarray([[v['x'],v['y']] for m in p['meshes'].values() for v in m['points']],np.float32);pad=max(20,face*.1)
  x1=min(bgr.shape[1],int(pts[:,0].max()+pad+1));y1=min(bgr.shape[0],int(pts[:,1].max()+pad+1))
  image=cv2.resize(corrected[y0:y1,x0:x1],None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
  g=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)/255
  assert g.shape==args[0].shape
  return original(g,*args[1:],**kwargs)
 A.instant_proxy=sample
 try:r=A.analyze_skin(p)
 finally:A.instant_proxy=original
 bag=next(v for v in r['measurements']['periorbital'] if v['id']=='bags')
 row=dict(source=prefix,before=before[0],after=bag['value'],reason=bag['limitationCode'],sourceImpulsePixels=int(tiny.sum()),sides=bag['components'].get('sides'))
 rows.append(row);print(json.dumps(row),flush=True)
(OUT/'noise-ablation.json').write_text(json.dumps(rows,indent=2),'utf8')
