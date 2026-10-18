"""Real licensed fixture sensitivity, source-coordinate/map bounds and negatives.
No expert lesion labels and no clinical accuracy claims.
"""
import base64,copy,hashlib,json,sys,time
from collections import Counter
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import analyze_skin,decode_photo
OUT=ROOT/'audit-results/combined-health-20261008';cv2.setNumThreads(1)
def transformed(payload,image,factor=1.,gain=1.):
 value=copy.deepcopy(payload);im=cv2.resize(image,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA);im=np.clip(im.astype(float)*gain,0,255).astype(np.uint8)
 ok,data=cv2.imencode('.png',im);assert ok
 value['photo']='data:image/png;base64,'+base64.b64encode(data).decode();value['photoId']=hashlib.sha256(cv2.cvtColor(im,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
 for mesh in value['meshes'].values():
  for p in mesh['points']:p['x']*=factor;p['y']*=factor
 for box in value['exclusions']:
  for k in ('x','y','w','h'):box[k]*=factor
 return value
def concise(result):
 return {region:{r['id']:{'value':r['value'],'unit':r['unit'],'limitationCode':r['limitationCode']} for r in rows} for region,rows in result['measurements'].items()}
build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
source_hash=hashlib.sha256((ROOT/'services/core-api/appearance_analysis.py').read_bytes()).hexdigest()
proof={'buildId':build,'analysisSourceSHA256':source_hash,'clinicalValidation':False,'expertLesionLabels':False,'physicalCamera':False,'engineeringSensitivity':True,'whiteClippingNegatives':0,'runs':[]}
for file in sorted((OUT/'skin').glob('appearance-0-*.json')):
 payload=json.loads(file.read_text('utf8'));image,_=decode_photo(payload['photo'])
 for name,scale,gain in [('baseline',1.,1.),('source-scale-075',.75,1.),('source-scale-125',1.25,1.),('source-detail-050',.5,1.),('exposure-085',1.,.85),('exposure-115',1.,1.15)]:
  value=transformed(payload,image,scale,gain);start=time.perf_counter();result=analyze_skin(value)
  for layer in result['maps'].values():
   raw=base64.b64decode(layer['dataUrl'].split(',')[1]);rgba=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED)
   mask=cv2.imdecode(np.frombuffer(base64.b64decode(layer['validMaskUrl'].split(',')[1]),np.uint8),cv2.IMREAD_GRAYSCALE)
   assert np.max(rgba[:,:,3])<=100 and not np.any(rgba[:,:,3][mask==0]),'Fixed-scale alpha must not leave evaluated skin'
   assert layer['photoId']==value['photoId'] and layer['x']>=0 and layer['y']>=0
   assert layer['x']+layer['width']*layer['step']<=result['sourceWidth']+2 and layer['y']+layer['height']*layer['step']<=result['sourceHeight']+2
  proof['runs'].append({'captureFile':file.name,'captureFileSHA256':hashlib.sha256(file.read_bytes()).hexdigest(),'baselinePhotoId':payload['photoId'],'transformedPhotoId':value['photoId'],'condition':name,'seconds':time.perf_counter()-start,'measurements':concise(result),'mapCount':len(result['maps'])})
 # A controlled white clipping perturbation must not become healthy zero.
 white=transformed(payload,np.full_like(image,255));result=analyze_skin(white)
 assert all(r['value'] is None for rows in result['measurements'].values() for r in rows)
 proof['whiteClippingNegatives']+=1
 (OUT/'proxy-sensitivity.json').write_text(json.dumps(proof,indent=2),'utf8')
baselines={run['captureFile']:run for run in proof['runs'] if run['condition']=='baseline'}
assert len(baselines)==6 and len(proof['runs'])==36
maximum={};missing=Counter()
for run in proof['runs']:
 baseline=baselines[run['captureFile']]['measurements']
 for region,values in run['measurements'].items():
  for criterion,item in values.items():
   if item['value'] is None:
    missing[(run['condition'],item['limitationCode'])]+=1;continue
   base=baseline.get(region,{}).get(criterion)
   if not base or base['value'] is None:continue
   change=abs(item['value']-base['value'])
   if criterion not in maximum or change>maximum[criterion]['maximumAbsoluteChange']:
    maximum[criterion]=dict(criterion=criterion,unit=item['unit'],maximumAbsoluteChange=change,case=[change,run['condition'],region])
summary=dict(buildId=build,analysisSourceSHA256=source_hash,
 scope='Engineering resize/exposure perturbations of six public licensed source captures; no expert clinical truth',
 baselineCaptures=len(baselines),conditionRuns=len(proof['runs']),whiteClippingNegatives=proof['whiteClippingNegatives'],
 maximumAbsoluteChanges=list(maximum.values()),
 unavailableByConditionAndReason=[dict(condition=condition,reason=reason,count=count) for (condition,reason),count in sorted(missing.items())])
(OUT/'proxy-sensitivity-summary.json').write_text(json.dumps(summary,indent=2),'utf8')
print('PASS actual fixture scale/exposure sensitivity and source/map masking; results uncalibrated')
