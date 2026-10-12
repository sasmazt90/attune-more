"""Measure connected support geometry; no thresholds fitted or runtime edits."""
import importlib.util,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
spec=importlib.util.spec_from_file_location('sampled_lines',ROOT/'.runtime/lines-impulse-20261012/native-only.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
OUT=ROOT/'audit-results/lines-impulse-20261012';rows=[]
for prefix in ('a94f1646','02386f86','5bd42346'):
 f=ROOT/'audit-results/lines-bags-followup-20261012'/(prefix+'-payload.json')
 if not f.exists():f=ROOT/'audit-results/bag-label-followup-20261012'/(prefix+'-v2-payload.json')
 p=json.loads(f.read_text('utf8'));captured=[];original=A.map_result;responses=[];gabor=A.gabor
 def record(values,mask,region,criterion,*args,**kwargs):
  if criterion=='lines':captured.append((values.copy(),mask.copy(),args))
  return original(values,mask,region,criterion,*args,**kwargs)
 def filter_response(gray,frequency,theta):
  real,imag=gabor(gray,frequency=frequency,theta=theta);responses.append(np.hypot(real,imag));return real,imag
 A.map_result=record;A.gabor=filter_response
 try:A.analyze_skin(p)
 finally:A.map_result=original;A.gabor=gabor
 values,mask,args=captured[0];rad=np.max([v for i,v in enumerate(responses) if i%6<3],axis=0);ortho=np.max([v for i,v in enumerate(responses) if i%6>=3],axis=0)
 field=np.clip((rad-.0125)/.055,0,1)*np.clip((rad/np.maximum(ortho,.005)-1.22)/.35,0,1)
 np.savez_compressed(OUT/(prefix+'-line-fields.npz'),values=values,mask=mask,field=field)
 for stage,bits in [('accepted',values>0),('full-field',field>0)]:
  n,labels,stats,_=cv2.connectedComponentsWithStats(bits.astype('uint8'),8);parts=[]
  for label in range(1,n):
   component=labels==label
   if not (component&mask).any():continue
   y,x=np.where(component);points=np.column_stack([x,y]).astype(float);eigen=np.linalg.eigvalsh(np.cov(points.T)) if len(points)>2 else [0,0]
   parts.append(dict(area=int(component.sum()),acceptedArea=int((component&mask).sum()),bbox=stats[label,:4].tolist(),principalStd=float(np.sqrt(max(eigen))),axisRatio=float(np.sqrt(max(eigen)/max(min(eigen),.25)))))
  rows.append(dict(source=prefix,stage=stage,components=parts));print(json.dumps(rows[-1]),flush=True)
(OUT/'coherence-components.json').write_text(json.dumps(rows,indent=2),'utf8')
