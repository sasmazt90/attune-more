"""Read actual saved browser inputs; preserve all original profile coordinates."""
import hashlib, importlib.util, inspect, json, subprocess, sys
from pathlib import Path
import cv2, numpy as np
from scipy.ndimage import gaussian_filter1d
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/dry-sag-proposal-tracking-20261013';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
# Read the starting commit, even when this diagnostic is rerun after promotion.
saved={n:sys.modules.get(n) for n in ['instant_appearance','skin_general']};loaded={}
for name in ['instant_appearance','skin_general','appearance_analysis']:
 source=subprocess.check_output(['git','show','5a40a1276c9eccc6bd099d42775dcd7eb4e3e604:services/core-api/'+name+'.py'],cwd=ROOT)
 alias=name if name!='appearance_analysis' else 'tracking_frozen_baseline'
 module=type(sys)(alias);module.__file__=str(ROOT/'services/core-api'/(name+'.py'));sys.modules[alias]=module
 exec(compile(source,module.__file__,'exec'),module.__dict__);loaded[name]=module
for name,module in saved.items():
 if module is None:sys.modules.pop(name,None)
 else:sys.modules[name]=module
A=loaded['appearance_analysis'];I=loaded['instant_appearance']
cv2.setNumThreads(1)

def runs(mask):
 edges=np.diff(np.r_[False,mask,False].astype(int));return [(int(a),int(b)) for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1))]

def residual(selected,line,width,mask):
 pieces=[]
 for start,end in runs(mask):
  if end-start<5:continue
  displacement=selected[start:end]-line[start:end]
  errors=np.linalg.norm(displacement-gaussian_filter1d(displacement,2,axis=0),axis=1)/(width/320)
  pieces.extend(errors.tolist())
 return float(np.mean(pieces)) if pieces else None

original=I.curve_profile;cases=[];profiles=[]
def probe(gray,eligible,guide,normal,offsets,width,center_support=None):
 q=original(gray,eligible,guide,normal,offsets,width,center_support)
 caller=inspect.currentframe().f_back;region=caller.f_locals.get('region')
 if q is None or region!='chin':return q
 guide=np.asarray(guide,np.float32);distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))]
 t=np.linspace(0,distance[-1],64);line=np.column_stack([np.interp(t,distance,guide[:,i]) for i in (0,1)])
 observed=q['observedSamples'];fold=q['support']&observed;scale=caller.f_locals['scale'];origin=np.asarray(caller.f_locals['origin'])
 selected=q['tracked'];source=selected/scale+origin;source_line=line/scale+origin
 profiles.append(dict(side=caller.f_locals['side'],region=region,coverage=q['coverage'],continuity=q['continuity'],
  oldResidual=q['trackingResidual'],observedOnlyResidual=residual(selected,line,width,observed),
  actualFoldRunResidual=residual(selected,line,width,fold),observedRows=int(observed.sum()),foldRows=int(fold.sum()),
  invalidRows=int((~observed).sum()),observedRuns=runs(observed),foldRuns=runs(fold),
  sourceGuide=source_line.tolist(),sourceSelectedIncludingInvalid=source.tolist(),observed=observed.tolist(),foldSupport=fold.tolist(),
  trackingResidualThreshold=2.5,sourceFaceWidth=width/scale,
  coordinateMeaning='Old selected point on an invalid/non-fold row is an argmax artifact, not a measured fold'))
 return q
I.curve_profile=probe
for prefix in ['f90e68f8','40d781eb','64b02ede','99f82af5','24031977']:
 folder=ROOT/'audit-results/dry-sag-source-census-20261013/product'/prefix
 path=folder/(prefix+'-automatic-payload.json')
 if prefix=='24031977':path=folder/'attempt-2'/(prefix+'-automatic-payload.json')
 payload=json.loads(path.read_text('utf8'));assert not payload['hostedProcessingConsent'];profiles=[]
 result=A.analyze_skin(payload);(OUT/(prefix+'-baseline-api.json')).write_text(json.dumps(result,ensure_ascii=False),'utf8')
 chin=next(v for v in result['measurements']['chin'] if v['id']=='sag')
 bgr,_=A.decode_photo(payload['photo']);image=bgr.copy()
 for profile in profiles:
  for xy in profile['sourceGuide']:cv2.circle(image,tuple(np.rint(xy).astype(int)),1,(255,128,0),-1)
  for xy,observed,fold in zip(profile['sourceSelectedIncludingInvalid'],profile['observed'],profile['foldSupport']):
   cv2.circle(image,tuple(np.rint(xy).astype(int)),3,(0,255,0) if fold else (0,180,255) if observed else (0,0,255),-1)
 cv2.imwrite(str(OUT/(prefix+'-old-tracking-source.png')),image)
 cases.append(dict(sourcePrefix=prefix,payloadPath=str(path.relative_to(ROOT)),payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),
  photoId=payload['photoId'],baselineValue=chin['value'],baselineLimitation=chin['limitationCode'],profiles=profiles))
I.curve_profile=original
(OUT/'tracking-baseline-diagnosis.json').write_text(json.dumps(dict(cases=cases,productionChanged=False),ensure_ascii=False,indent=2),'utf8')
print(json.dumps([dict(source=c['sourcePrefix'],baseline=c['baselineLimitation'],profiles=[{k:q[k] for k in ['side','oldResidual','observedOnlyResidual','actualFoldRunResidual','observedRows','foldRows','invalidRows','foldRuns']} for q in c['profiles']]) for c in cases]))
