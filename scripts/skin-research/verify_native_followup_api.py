"""Normal API equality and actual raster/support receipt on pinned product inputs."""
import base64,hashlib,json,sys,time,urllib.request
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
OUT=ROOT/'audit-results/dry-sag-native-followup-20261013';proof=[]
deadline=time.monotonic()+60
while True:
 try:
  with urllib.request.urlopen('http://127.0.0.1:8000/api/vehicle/state',timeout=3) as ready:assert ready.status==200
  break
 except (OSError,AssertionError):
  if time.monotonic()>deadline:raise
  time.sleep(.5)
audit.request('http://127.0.0.1:8000/api/vehicle/speed',{'speedKmH':0})
for source in json.loads((OUT/'source-selection.json').read_text('utf8')):
 prefix=source['sha256'][:8];f=OUT/(prefix+'-payload.json')
 if not f.exists():continue
 p=json.loads(f.read_text('utf8'));assert not p.get('hostedProcessingConsent')
 captures=[];original=A.map_result
 def capture(values,mask,region,criterion,*args):
  layer=original(values,mask,region,criterion,*args)
  if criterion in ('dry','sag') and layer:
   captures.append(dict(key=region+':'+criterion,mask=mask.copy(),signal=values.copy(),layer=layer,scale=args[3],origin=args[6]))
  return layer
 A.map_result=capture
 try:expected=A.analyze_skin(p)
 finally:A.map_result=original
 stored='--stored-responses' in sys.argv
 actual=json.loads((OUT/(prefix+'-normal-api.json')).read_text('utf8')) if stored else audit.request('http://127.0.0.1:8000/api/local-health/skin',p)
 same=all(actual[k]==expected[k] for k in ('measurements','maps','contours'));assert same,(prefix,'source/API drift')
 g1,g2=actual.get('general',{}),expected.get('general',{})
 for g in (g1,g2):
  for m in g.get('modelInference',{}).values():m.pop('loadMs',None);m.pop('inferenceMs',None)
 assert g1==g2
 geometry=[]
 for c in captures:
  layer=c['layer'];image=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)
  valid=cv2.imdecode(np.frombuffer(base64.b64decode(layer['validMaskUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)>0
  # Actual API grid offset and step, using the identical production raster.
  origin=c['origin'];scale=c['scale'];x=int(round((layer['x']-origin[0])*scale));y=int(round((layer['y']-origin[1])*scale))
  support=c['mask'][y:y+valid.shape[0],x:x+valid.shape[1]]
  outside=int((valid&~support).sum());assert outside==0
  region=c['key'].split(':')[0];meshes=p['meshes'].values() if region=='overview' else [p['meshes'][region]]
  anatomy=np.logical_or.reduce([A.closed_surface_mask(c['mask'].shape,m,scale,origin) for m in meshes])
  outside_selected=int((valid&~anatomy[y:y+valid.shape[0],x:x+valid.shape[1]]).sum());assert outside_selected==0
  excluded=np.zeros(c['mask'].shape,np.uint8)
  for box in p['exclusions']:
   bx=int((box['x']-origin[0])*scale);by=int((box['y']-origin[1])*scale);bw=int(box['w']*scale);bh=int(box['h']*scale);cv2.rectangle(excluded,(max(0,bx),max(0,by)),(max(0,bx+bw),max(0,by+bh)),255,-1)
  holes=[[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327,294],[70,63,105,66,107,55,65,52],[300,293,334,296,336,285,295,282]]
  for indices in holes:
   coords=np.asarray([[(p['landmarks'][i]['x']*actual['sourceWidth']-origin[0])*scale,(p['landmarks'][i]['y']*actual['sourceHeight']-origin[1])*scale] for i in indices],np.int32);cv2.fillPoly(excluded,[coords],255)
  active_excluded=int(((image[:,:,3]>0)&(excluded[y:y+valid.shape[0],x:x+valid.shape[1]]>0)).sum());assert active_excluded==0
  geometry.append(dict(key=c['key'],outsideActualMeasurementSupportPixels=outside,outsideSelectedClosedCellPixels=outside_selected,activeExcludedEyeLipNostrilBrowOrAutoRectPixels=active_excluded,analysisMapValidPixels=int(valid.sum()),rawAcceptedSignalPixels=int(((c['signal']>.04)&c['mask']).sum()),encodedNonzeroPixels=int((image[:,:,3]>0).sum()),sourceX=layer['x'],sourceY=layer['y'],step=layer['step'],gridShape=[layer['width'],layer['height']]))
 (OUT/(prefix+'-normal-api.json')).write_text(json.dumps(actual,ensure_ascii=False),'utf8')
 row=dict(sourceSHA256=source['sha256'],payloadSHA256=hashlib.sha256(f.read_bytes()).hexdigest(),responseSource='previous-real-normal-api-response' if stored else 'fresh-normal-api-response',actualAPIEqualsWorkingSource=same,sourcePhotoMatches=actual['photoId']==p['photoId'],geometry=geometry)
 proof.append(row);print(json.dumps({'source':prefix,'matches':same,'maps':len(geometry)}),flush=True)
(OUT/'normal-api-receipt.json').write_text(json.dumps(proof,indent=2),'utf8')
