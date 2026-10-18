"""Finite isolated trials on pinned development photos; no service mutation."""
import base64,hashlib,importlib.util,json,sys,time
from pathlib import Path
import cv2,numpy as np
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
OUT=ROOT/'audit-results/dry-sag-native-followup-20261013'
BASE=ROOT/'.runtime/dry-sag-native-baseline-20261013'
def load(name,source):
 m=type(sys)(name);m.__file__=str(BASE/(name+'.py'));sys.modules[name]=m;exec(compile(source,m.__file__,'exec'),m.__dict__);return m
def methods(lower=False):
 s=(BASE/'instant_appearance.py').read_text('utf8')
 if lower:s=s.replace("paths=[('mental',[201,200,421])]","paths=[('lower-chin',[170,208,199,428,395])]")
 I=load('instant_appearance',s);G=load('skin_general',(BASE/'skin_general.py').read_text('utf8'));A=load('trial_analysis',(BASE/'appearance_analysis.py').read_text('utf8'))
 def fast_components(signal,eligible):
  count,labels,stats,_=cv2.connectedComponentsWithStats(((signal>.04)&eligible).astype(np.uint8));keep=np.zeros(count,bool)
  for label in range(1,count):
   _,_,w,h,pixels=stats[label];keep[label]=3<=pixels<=80 and .3<=w/max(h,1)<=3.3 and pixels/max(w*h,1)>.25
  return signal*eligible*keep[labels]
 A.eligible_flake_components=fast_components
 return A,I
rows=json.loads((OUT/'probe-selection.json').read_text('utf8'))
if '--local-only' in sys.argv:rows=rows[:6]
reports=[];start=time.monotonic()
for r in rows:
 prefix=r['sha256'][:8];source=cv2.imread(r['absolutePath']);assert hashlib.sha256(Path(r['absolutePath']).read_bytes()).hexdigest()==r['sha256']
 probe=json.loads((OUT/(prefix+'-probe.json')).read_text('utf8'));frame=probe['snapshot']
 local=[]
 for ann in r['annotations']:
  if ann['label'] not in ('PUL','pul','Dry-Skin'):continue
  x,y,w,h=ann['bbox'];x,y=int(x),int(y);w,h=int(w),int(h)
  if w<4 or h<4:continue
  # Context around a partial positive box is unknown, never healthy negative.
  roi=source[max(0,y-12):min(source.shape[0],y+h+12),max(0,x-12):min(source.shape[1],x+w+12)]
  if not roi.size:continue
  A,_=methods();gray=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY);native=A.compute_dryness_signal(gray)[0]
  face_width=abs(frame['landmarks'][454]['x']-frame['landmarks'][234]['x'])*source.shape[1] if frame else max(source.shape[:2])
  scale=min(1,320/max(face_width,1));small=cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
  old=A.compute_dryness_signal(small)[0];project=cv2.resize((old>.04).astype('uint8'),(gray.shape[1],gray.shape[0]),interpolation=cv2.INTER_NEAREST)>0
  local.append(dict(box=ann['bbox'],label=ann['label'],scale=scale,nativeAccepted=int((native>.04).sum()),normalizedAcceptedSourcePixels=int(project.sum()),nativeCandidate=int((A.compute_dryness_signal(gray)[1]>.04).sum())))
 if local:
  if source.shape[0]*source.shape[1]<1_000_000:
   overlay=source.copy();gray=cv2.cvtColor(source,cv2.COLOR_BGR2GRAY);A,_=methods();signal=A.compute_dryness_signal(gray)[0];active=signal>.04;overlay[active]=(overlay[active]*.3+np.array([0,255,255])*.7).astype('uint8');cv2.imwrite(str(OUT/(prefix+'-native-local.png')),overlay)
 products={}
 if frame and '--local-only' not in sys.argv:
  p=dict(processingConsent=True,hostedProcessingConsent=False,photo=frame['dataUrl'],photoId=frame['photoId'],pose=frame['angle'],meshes=frame['meshes'],exclusions=frame['exclusions'],landmarks=frame['landmarks'],qualityValid=probe['quality']['isValid'],conditions=probe['conditions'],temporal=[])
  (OUT/(prefix+'-payload.json')).write_text(json.dumps(p,ensure_ascii=False),'utf8')
  for name,lower in [('baseline',False),('lower-chin',True)]:
   A,I=methods(lower);tic=time.monotonic();response=A.analyze_skin(p)
   (OUT/(prefix+'-'+name+'.json')).write_text(json.dumps(response,ensure_ascii=False),'utf8')
   products[name]=dict(seconds=time.monotonic()-tic,regional={k:[dict(id=v['id'],value=v['value'],limitation=v['limitationCode'],components=v['components']) for v in values if v['id'] in ('dry','sag')] for k,values in response['measurements'].items()},general=[dict(id=v['id'],value=v['value'],limitation=v['limitationCode']) for v in response.get('general',{}).get('measurements',[]) if v['id'] in ('dry','sag')])
 reports.append(dict(source=prefix,sourceSHA256=r['sha256'],role=r['taskRole'],quality=probe['quality'],angles=probe['supportedAngles'],automaticPoseCapture=probe['poseCaptureCompleted'],localPartialBoxes=local,products=products));print(json.dumps(dict(source=prefix,boxes=local,products={k:dict(general=v['general'],regional={region:next((i['value'] for i in items if i['id']=='sag'),None) for region,items in v['regional'].items()}) for k,v in products.items()})),flush=True)
(OUT/('trial-pul-local.json' if '--local-only' in sys.argv else 'trial-native-local-and-chin.json')).write_text(json.dumps(dict(seconds=time.monotonic()-start,sources=reports),ensure_ascii=False,indent=2),'utf8')
