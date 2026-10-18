"""Fresh normal-service final targets; unsupported old FRONT replay stays diagnostic."""
import hashlib,importlib.util,json,sys,time,urllib.request
from pathlib import Path
import cv2,numpy as np
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
OUT=ROOT/'audit-results/dry-sag-native-followup-20261013'
saved={n:sys.modules[n] for n in ('instant_appearance','skin_general')}
for n in ['instant_appearance','skin_general','appearance_analysis']:
 alias=n if n!='appearance_analysis' else 'final_frozen';spec=importlib.util.spec_from_file_location(alias,ROOT/'.runtime/dry-sag-native-baseline-20261013'/(n+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[alias]=m;spec.loader.exec_module(m)
 if n=='appearance_analysis':B=m
sys.modules.update(saved)
deadline=time.monotonic()+45
while True:
 try:
  with urllib.request.urlopen('http://127.0.0.1:8000/api/vehicle/state',timeout=3) as response:assert response.status==200
  break
 except OSError:
  if time.monotonic()>deadline:raise
  time.sleep(.5)
audit.request('http://127.0.0.1:8000/api/vehicle/speed',{'speedKmH':0})
ui=json.loads((OUT/'actual-ui-scan.json').read_text('utf8'))
cases=[('515cc548',json.loads((OUT/'515cc548-payload.json').read_text('utf8')),'prior natural source; FRONT/LEFT automatic pose rejected'),
       ('d3e8bb60-front-replay',json.loads((ROOT/'audit-results/dry-sag-product-20261013/d3e8bb60-payload.json').read_text('utf8')),'existing transformed regression; prior FRONT API-only replay'),
       ('0642d4ab-automatic-front',ui['requests'][0],'completed real browser automatic FRONT; native-source YUV camera fixture')]
proof=[]
for name,p,scope in cases:
 assert not p['hostedProcessingConsent'];expected=A.analyze_skin(p);actual=audit.request('http://127.0.0.1:8000/api/local-health/skin',p);before=B.analyze_skin(p)
 assert all(actual[k]==expected[k] for k in ['measurements','maps','contours'])
 if name=='0642d4ab-automatic-front':assert actual['measurements']==ui['responses'][0]['measurements'] and actual['maps']==ui['responses'][0]['maps']
 (OUT/(name+'-normal-api.json')).write_text(json.dumps(actual,ensure_ascii=False),'utf8');(OUT/(name+'-payload.json')).write_text(json.dumps(p,ensure_ascii=False),'utf8');targets=[]
 for region in ['overview','chin','rightCheek','leftCheek']:
  current=actual['general']['measurements'] if region=='overview' else actual['measurements'][region];old=before['general']['measurements'] if region=='overview' else before['measurements'][region]
  for row in current:
   if row['id'] not in ('dry','sag'):continue
   original=next(r for r in old if r['id']==row['id']);shape=(actual['sourceHeight'],actual['sourceWidth'],3)
   targets.append(dict(region=region,id=row['id'],before=original['value'],after=row['value'],beforeActiveSourcePixels=int((audit.project_map_alpha(before['maps'].get(region+':'+row['id']),shape)>0).sum()),activeSourcePixels=int((audit.project_map_alpha(actual['maps'].get(region+':'+row['id']),shape)>0).sum()),limitation=row['limitationCode'],normalizationVersion=row['normalizationVersion']))
 proof.append(dict(source=name,scope=scope,payloadSHA256=hashlib.sha256(json.dumps(p,ensure_ascii=False).encode()).hexdigest(),sourcePhotoId=p['photoId'],freshNormalAPIEqualsSource=actual['measurements']==expected['measurements'],targets=targets));print(json.dumps(dict(source=name,targets=[t for t in targets if t['region']=='overview'])),flush=True)
(OUT/'final-target-receipt.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8')
