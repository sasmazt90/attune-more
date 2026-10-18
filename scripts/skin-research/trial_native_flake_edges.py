"""One bounded multi-scale/coherent-edge hypothesis, no services or thresholds search."""
import importlib.util,json,sys,time
from pathlib import Path
import cv2,numpy as np
from skimage.feature import local_binary_pattern
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
OUT=ROOT/'audit-results/dry-sag-native-followup-20261013'
# The rejected prototype is an immutable local audit artifact. Never obtain
# this experimental pipeline from whatever happens to be live production code.
prototype=OUT/'rejected-native-prototype'
assert (prototype/'appearance_analysis.py').is_file(), 'Pinned rejected prototype artifact is required'
spec=importlib.util.spec_from_file_location('skin_general',prototype/'skin_general.py');general=importlib.util.module_from_spec(spec);sys.modules['skin_general']=general;spec.loader.exec_module(general)
spec=importlib.util.spec_from_file_location('rejected_native_appearance',prototype/'appearance_analysis.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
def edges(signal,eligible):
 candidate=(signal>.04)&eligible
 grouped=cv2.dilate(candidate.astype('uint8'),np.ones((3,3),np.uint8))&eligible.astype('uint8')
 n,labels,stats,_=cv2.connectedComponentsWithStats(grouped);keep=np.zeros(n,bool)
 for label in range(1,n):
  x,y,w,h,_=stats[label];m=(labels[y:y+h,x:x+w]==label)&candidate[y:y+h,x:x+w];ys,xs=np.where(m)
  if len(xs)<3 or max(np.ptp(xs),np.ptp(ys))<5:continue
  # Coherent bright edges, not compact round dots; grouping adds no painted pixels.
  covariance=np.linalg.eigvalsh(np.cov(np.stack([xs,ys])))
  keep[label]=covariance[-1]>3*max(covariance[0],.01) and len(xs)<=80
 return signal*candidate*keep[labels]
original=A.compute_dryness_signal
ordinary_components=A.eligible_flake_components
def multi(gray8,support_mask=None):
 _,raw,contrast,lbp,dark,high=original(gray8,support_mask)
 gray=gray8.astype('float32')/255
 broad_high=gray-cv2.GaussianBlur(gray,(0,0),2.4)
 broad=cv2.GaussianBlur(gray,(0,0),1.4)-cv2.GaussianBlur(gray,(0,0),4.6)
 c=np.sqrt(np.maximum(0,cv2.GaussianBlur(gray*gray,(0,0),4)-cv2.GaussianBlur(gray,(0,0),4)**2))
 coarse=np.clip((broad_high-.025)/.10,0,1)*np.clip((broad-.018)/.10,0,1)*(local_binary_pattern(gray8,8,2,'uniform')<8)*((c>.015)&(c<.14))
 if '--native-compact' not in sys.argv:raw=np.maximum(raw,coarse)
 if '--contrast-rms' in sys.argv:raw*=high>2*contrast
 support=np.ones(gray8.shape,bool) if support_mask is None else support_mask
 if '--pore-focus' in sys.argv:
  # Low-contrast compact dark pores can be below the old absolute 35/255 gate.
  focus=cv2.morphologyEx(gray8,cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>2*.015*255
  n,labels,stats,_=cv2.connectedComponentsWithStats(focus.astype('uint8'));keep=np.zeros(n,bool)
  for label in range(1,n):
   _,_,w,h,pixels=stats[label];keep[label]=3<=pixels<=80 and .5<=w/max(h,1)<=2 and pixels/max(w*h,1)>.4
  dark=dark|(cv2.dilate(keep[labels].astype('uint8'),np.ones((7,7),np.uint8))>0)
 return A.eligible_flake_components(raw,support&~dark),raw,contrast,lbp,dark,high
A.eligible_flake_components=ordinary_components if '--native-compact' in sys.argv else edges;A.compute_dryness_signal=multi
rows=json.loads((OUT/'probe-selection.json').read_text('utf8'));report=[];start=time.monotonic()
for r in rows:
 prefix=r['sha256'][:8]
 if prefix not in ['03605ddd','2cfbfb04','387e1700','aaec14eb','1b2914e2','594aadd0','e1646fda','0642d4ab','36e4010b','c31892d1','5bd42346']:continue
 source=cv2.imread(r['absolutePath']);gray=cv2.cvtColor(source,cv2.COLOR_BGR2GRAY);signal=multi(gray)[0];local=[]
 for ann in r['annotations']:
  if ann['label'] not in ('pul','Dry-Skin'):continue
  x,y,w,h=[int(v) for v in ann['bbox']];support=np.zeros(gray.shape,bool);support[max(0,y):y+h,max(0,x):x+w]=True
  local.append(dict(box=ann['bbox'],nativeActive=int(((signal>.04)&support).sum())))
 tag='contrast-rms' if '--contrast-rms' in sys.argv else 'native-compact' if '--native-compact' in sys.argv else 'pore-focus' if '--pore-focus' in sys.argv else 'coherent'
 overlay=source.copy();active=signal>.04;overlay[active]=(overlay[active]*.3+np.array([0,255,255])*.7).astype('uint8');cv2.imwrite(str(OUT/(prefix+'-'+tag+'-native.png')),overlay)
 product=None;file=OUT/(prefix+'-payload.json')
 if file.exists():
  p=json.loads(file.read_text('utf8'));response=A.analyze_skin(p);(OUT/(prefix+'-'+tag+'-working.json')).write_text(json.dumps(response,ensure_ascii=False),'utf8');shape=source.shape
  product=dict(rows=[dict(region=region,id=v['id'],value=v['value'],activeSourcePixels=int((audit.project_map_alpha(response['maps'].get(region+':'+v['id']),shape)>0).sum())) for region,items in [*response['measurements'].items(),('overview',response.get('general',{}).get('measurements',[]))] for v in items if v['id']=='dry'])
 row=dict(source=prefix,partialPositiveBoxes=local,product=product);report.append(row);print(json.dumps(row),flush=True)
(OUT/('trial-contrast-rms-native.json' if '--contrast-rms' in sys.argv else 'trial-native-compact.json' if '--native-compact' in sys.argv else 'trial-pore-focus-native.json' if '--pore-focus' in sys.argv else 'trial-coherent-native.json')).write_text(json.dumps(dict(seconds=time.monotonic()-start,sources=report),ensure_ascii=False,indent=2),'utf8')
