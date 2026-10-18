"""Real HTTP router cold/warm admission and selective fold-gate comparison."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import json,sys,time,threading,subprocess,types,hashlib,socket
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dryness-integration-v2-20261014';sys.path.insert(0,str(ROOT/'services/core-api'))
with HeavyJobLease('CDC-normal-dry-v2-HTTP-admission',peak_mib=650,minimum_available_mib=1100) as lease:
 import cv2,numpy as np,httpx,uvicorn
 from fastapi import FastAPI
 import local_health as L,appearance_analysis as A,instant_appearance as I
 cv2.setNumThreads(1);L.parked=lambda:True;app=FastAPI();app.include_router(L.router)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=18015,log_level='error'));thread=threading.Thread(target=server.run);thread.start()
 def read(name):return json.loads((ROOT/name).read_text('utf8'))
 def request(client,p,name):
  lease.check();p['hostedProcessingConsent']=False;t=time.monotonic();r=client.post('http://127.0.0.1:18015/api/local-health/skin',json=p);elapsed=time.monotonic()-t
  data=r.json();(OUT/(name+'-api.json')).write_text(json.dumps(data),'utf8');print(json.dumps(dict(case=name,status=r.status_code,seconds=elapsed)),flush=True)
  assert r.status_code==200,(r.status_code,data)
  assert elapsed<45
  return data,elapsed
 try:
  deadline=time.monotonic()+15
  while not server.started:
   if time.monotonic()>deadline:raise RuntimeError('OWN_HTTP_START_FAILED')
   time.sleep(.05)
  with httpx.Client(timeout=50) as client:
   p=read('audit-results/material-closeout-20261013/new-camera-normal-payload.json')
   cold,ct=request(client,p,'cold-normal-camera');warm,wt=request(client,p,'warm-normal-camera')
   assert cold['maps']==warm['maps'] and cold['measurements']==warm['measurements']
   assert cold['drynessRuntime']['headSHA256']=='7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1'
   rows=[r for values in cold['measurements'].values() for r in values if r['id']=='dry'];overview=next(r for r in cold['general']['measurements'] if r['id']=='dry')
   for row in rows+[overview]:
    if row['value'] is not None:assert abs(row['value']-100*row['components']['acceptedMaterialSourcePixels']/row['components']['uniqueVisibleSourcePixels'])<1e-10
   oldmod=types.ModuleType('pinned_previous_instant');exec(compile(subprocess.check_output(['git','show','72b90172084711cd200637cedab831f80e3fb973:services/core-api/instant_appearance.py']),'previous_instant','exec'),oldmod.__dict__)
   sag=[]
   paths=[('29cc4ba7','audit-results/native-camera-scope-20261013/29cc4ba7-current-capture-payload.json'),('4d05d72b','audit-results/material-closeout-20261013/4d05d72b-payload.json'),('dedbb492','audit-results/native-dry-scale-20261013/sag-targeted/dedbb492-payload.json')]
   for name,path in paths:
    payload=read(path);payload['hostedProcessingConsent']=False
    if name=='dedbb492':new,seconds=request(client,payload,name)
    else:
     t=time.monotonic();new=A.analyze_skin(payload);seconds=time.monotonic()-t
    current=A.instant_proxy
    def previous(*args,**kw):kw.pop('expression_observation',None);kw.pop('photo_id',None);return oldmod.instant_proxy(*args,**kw)
    try:A.instant_proxy=previous;old=A.analyze_skin(payload)
    finally:A.instant_proxy=current
    (OUT/(name+'-fold-before.json')).write_text(json.dumps(old),'utf8');(OUT/(name+'-fold-after.json')).write_text(json.dumps(new),'utf8')
    oldrows={reg:next((r for r in rr if r['id']=='sag'),None) for reg,rr in old['measurements'].items()}
    newrows={reg:next((r for r in rr if r['id']=='sag'),None) for reg,rr in new['measurements'].items()}
    for reg,rr in old['measurements'].items():
     for row in rr:
      if row['id'] not in ('dry','sag'):
       other=next(v for v in new['measurements'][reg] if v['id']==row['id']);before={**row,'captureConditions':{k:v for k,v in row['captureConditions'].items() if k not in ('skinCapturePolicy','skinEyewearModelHash')}};after={**other,'captureConditions':{k:v for k,v in other['captureConditions'].items() if k not in ('skinCapturePolicy','skinEyewearModelHash')}};assert before==after,(name,reg,row['id'])
    for key,layer in old['maps'].items():
     if not key.endswith((':dry',':sag')):assert layer==new['maps'][key],(name,key)
    comparisons=[dict(region=reg,before=row['value'],beforeReason=row['limitationCode'],after=newrows[reg]['value'],afterReason=newrows[reg]['limitationCode']) for reg,row in oldrows.items() if row]
    if name!='dedbb492':assert all(not r['afterReason'] or not r['afterReason'].startswith('EXPRESSION') for r in comparisons if r['region'] in ('chin','rightCheek','leftCheek'))
    if name=='dedbb492':assert all(r['before']==r['after'] and r['beforeReason']==r['afterReason'] for r in comparisons)
    print(json.dumps(dict(source=name,foldComparisons=comparisons)),flush=True)
    sag.append(dict(fullAPI=name=='dedbb492',scope='same original native product payload; fold analyzer only for high-resolution stress sources' if name!='dedbb492' else 'normal full router',source=name,photoId=payload['photoId'],payloadSHA256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),rows=comparisons,seconds=seconds,otherCriteriaAndMapsExact=True))
   additional=[]
   for name,path in [('camera-1280x960','audit-results/material-closeout-20261013/camera-native-payload.json'),('24031977','audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json')]:
    data,seconds=request(client,read(path),name);additional.append(dict(source=name,sourceSize=[data['sourceWidth'],data['sourceHeight']],seconds=seconds,overview=next(r for r in data['general']['measurements'] if r['id']=='dry')))
   receipt=dict(additional=additional,actualNormalRouter=True,analyzerSubstituted=False,firstColdIncludesEncoderLoad=True,coldSeconds=ct,warmSeconds=wt,persistentPhotoCache=False,sourceSize=[cold['sourceWidth'],cold['sourceHeight']],drynessRuntime=cold['drynessRuntime'],overview=dict(value=overview['value'],reason=overview['limitationCode'],accepted=overview['components']['acceptedMaterialSourcePixels'],denominator=overview['components']['uniqueVisibleSourcePixels']),sag=sag,resource=lease.receipt())
   (OUT/'normal-api-admission.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)
 finally:server.should_exit=True;thread.join(10);assert not thread.is_alive()
