"""One full real-factory HTTP candidate call; only dry callback is replaced.
No payload metadata edits, user storage, normal process changes or model fit.
"""
import asyncio,copy,hashlib,json,os,socket,sys,threading,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'cdc-progress/skin-dryness-dualscale-20261018'
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
os.environ.update(ATTUNE_LOAD_LOCAL_ENV='0',ATTUNE_DATA_DIR=str(OUT/'factory-data'),ATTUNE_EXPERIMENTAL_ACNE_V5='1',ATTUNE_TRUSTED_ORIGINS='http://localhost:3000,http://127.0.0.1:3000')
for name in list(os.environ):
 if name.startswith(('OPENAI_','ROBOFLOW_','ATTUNE_ROBOFLOW')):os.environ.pop(name,None)
os.environ.pop('ATTUNE_ACNE_V5_VALIDATION',None)
sys.path.insert(0,str(ROOT/'.runtime/edge-tts'));sys.path.insert(0,str(ROOT/'services/core-api'));sys.path.insert(0,str(ROOT/'scripts/skin-research'))
import psutil
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,v):
 p=OUT/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8');os.replace(t,p)
RESUME='--resume-resource-admission' in sys.argv;PREFIX='factory-resumed' if RESUME else 'factory'
assert not (OUT/'factory-request-start.json').exists(),'The one actual full candidate POST budget is already used'
if RESUME:
 prior=read(OUT/'factory-checks.json')
 assert prior['fullCandidatePosts']==0 and prior.get('blocker','').startswith('RuntimeError: AVAILABLE_RAM_BELOW_2500_MIB'),'Resume only the pre-import resource rejection'
assert not (OUT/(PREFIX+'-plan.json')).exists(),'Do not repeat this bounded factory attempt'
index=read(OUT/'runtime-input-index.json');row=next(r for r in index['inputs'] if r.get('eligibleForThirdCheck'))
source=Path(row['payloadPath']);assert sha(source)==row['payloadSHA256'];value=read(source)[row['payloadWrapperKey']]
canonical=lambda p:hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
original_canonical=canonical(value)
plan=dict(atUTC=now(),maximumFullCandidatePosts=1,photoId=value['photoId'],payloadWrapperSHA256=row['payloadSHA256'],payloadCanonicalSHA256=original_canonical,meshSHA256=row['meshSHA256'],sourceSize=row['sourceSize'],metadataChanges=[],selectorSeam='Test process only: product_dryness.analyze_product -> analyze_product_candidate; original factory main.app, router and all models retained',baseFactory=str(ROOT/'services/core-api/main.py'),helperSHA256=sha(ROOT/'services/core-api/dry_dualscale_runtime_staging.py'),sourceUnionSHA256=sha(ROOT/'services/core-api/dry_dualscale_support.py'),minimumAvailableMiB=2500,deadlineSeconds=45,originalNormalSource='4942f3d553a1a813570ff060820190c9ffad6636',originalNormalBUILD_ID='2jbDtwhL9OHe3Smz0IZqf',normalUserDataDirUsed=False,persistentPhotoCache=False)
save(PREFIX+'-plan.json',plan)
result=dict(atUTC=now(),fullCandidatePosts=0,normalServingAPICalls=0,metadataUnchanged=True,preacceptance='not-run',normalRuntimeTouched=False,userHistoryWritten=False,externalHostedCalls=0)
server=None;thread=None;sock=None;original=None;P=None;lease=None
try:
 available=round(psutil.virtual_memory().available/2**20);result['availableBeforeMiB']=available
 if available<2500:raise RuntimeError('AVAILABLE_RAM_BELOW_2500_MIB; no wait or other-app stop')
 if value.get('hostedProcessingConsent') is not False:raise RuntimeError('UNCHANGED_PAYLOAD_HOSTED_PERMISSION_NOT_FALSE; no hosted call allowed')
 from heavy_job_lease import HeavyJobLease
 with HeavyJobLease('CDC-DRY-01-one-full-factory-candidate',peak_mib=2000,minimum_available_mib=2500,include_children=True,memory_metric='rss') as lease:
  import uvicorn,httpx,numpy as np,cv2
  import main,local_health as L,product_dryness as P
  from fastapi import HTTPException
  from starlette.requests import Request
  from appearance_analysis import decode_photo
  from experimental_acne_v5 import gate
  from dry_dualscale_runtime_staging import analyze_product_candidate,METHOD,NORMALIZATION
  from local_skin_type import finalize_product_type
  assert L.parked(),'Actual factory is not parked; no override'
  raw=json.dumps(value).encode();sent=False
  async def receive():
   nonlocal_dummy=None
   return {'type':'http.request','body':raw,'more_body':False}
  request=Request({'type':'http','method':'POST','path':'/api/local-health/skin','headers':[(b'content-type',b'application/json')]},receive)
  admitted=asyncio.run(L.payload(request));L.skin_geometry(admitted);lease.check()
  eye=L.skin_capture_preflight(admitted);lease.check()
  bgr,identity=decode_photo(admitted['photo']);assert identity==admitted['photoId']
  if admitted.get('experimentalAcneV5') is True:gate(admitted,bgr)
  result['preacceptance']='passed-original-factory-payload-geometry-eyewear-and-V5-pure-gates'
  save(PREFIX+'-preacceptance.json',dict(atUTC=now(),passed=True,payloadCanonicalSHA256=canonical(value),unchanged=canonical(value)==original_canonical,eyewearStatus=eye['status'],eyewearModelHash=eye['modelHash'],actualFactoryParked=L.parked(),expressionAndPoseCurrentProductPassed=True))
  original=P.analyze_product
  def candidate_call(v,b,c):
   def check():c();lease.check()
   return analyze_product_candidate(v,b,check,promoted=False)
  P.analyze_product=candidate_call
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=port,log_level='error',access_log=False))
  thread=threading.Thread(target=lambda:server.run(sockets=[sock]),name='owned-dry-factory-server');thread.start()
  deadline=time.monotonic()+12
  while not server.started:
   if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('OWN_FACTORY_START_FAILED')
   time.sleep(.05)
  lease.check();save('factory-request-start.json',dict(atUTC=now(),count=1,photoId=value['photoId'],payloadCanonicalSHA256=original_canonical,apiPort=port))
  result['fullCandidatePosts']=1;started=time.monotonic()
  with httpx.Client(timeout=48) as client:response=client.post(f'http://127.0.0.1:{port}/api/local-health/skin',json=value,headers={'Origin':'http://127.0.0.1:3000'})
  elapsed=time.monotonic()-started;data=response.json();result.update(http=response.status_code,seconds=elapsed)
  save('factory-response.json',data)
  assert response.status_code==200,(response.status_code,data.get('detail'))
  assert elapsed<45 and canonical(value)==original_canonical and data['photoId']==value['photoId']
  dry=data['drynessRuntime'];assert dry['nonDryPreservation']['equal'] and dry['analysisResize'] is True
  assert dry['nativeBranchAnalysisResize'] is False and dry['halfBranchAnalysisResize'] is True and [x['factor'] for x in dry['analysisScales']]==[1.,.5]
  assert data.get('acneRuntime',{}).get('nonAcnePreservation',{}).get('equal',True)
  checks=[]
  for region,rows in data['measurements'].items():
   r=next(x for x in rows if x['id']=='dry');layer=data['maps'].get(region+':dry')
   if r['value'] is None:assert layer is None;continue
   assert r['methodVersion']==METHOD and r['normalizationVersion']==NORMALIZATION
   assert r['value']==100*r['components']['acceptedMaterialSourcePixels']/r['components']['uniqueVisibleSourcePixels']
   assert layer['photoId']==data['photoId'] and layer['scoreMethodVersion']==METHOD and layer['calibrationVersion']==r['calibrationVersion']
   assert 'nativeAnalysisResize' not in r['components'] and r['components']['analysisScales']==[1.,.5]
   checks.append(dict(region=region,value=r['value'],accepted=r['components']['acceptedMaterialSourcePixels'],denominator=r['components']['uniqueVisibleSourcePixels'],method=r['methodVersion']))
  again=finalize_product_type(copy.deepcopy(data));assert again==data
  save('factory-json-roundtrip.json',dict(responseCanonicalSHA256=canonical(data),jsonRoundtripEqual=json.loads(json.dumps(data))==data,finalKarmaIdempotent=again==data,qualityNullMapsConsistent=True,scoreMapMethodReceiptConsistent=True,metadataScalesExplicit=True))
  result.update(status='FULL_FACTORY_CANDIDATE_PASSED',checks=checks,nonDrySameCallPreservation=dry['nonDryPreservation'],finalKarmaIdempotent=True,photoId=data['photoId'],sourceUnion=dry['sourceUnion'],otherModels='Normal configured pipeline only; no independent model experiment',acneStatus=data.get('acneRuntime',{}).get('status'),normalProductEnabled=False)
  result['resource']=lease.receipt()
except Exception as ex:
 result.update(status='FULL_FACTORY_CANDIDATE_NOT_ACCEPTED',blocker=type(ex).__name__+': '+str(ex))
 if result['preacceptance']=='not-run':save(PREFIX+'-preacceptance.json',dict(atUTC=now(),passed=False,reason=result['blocker'],metadataChanges=[]))
finally:
 if server is not None:server.should_exit=True
 if thread is not None:thread.join(12);result['serverThreadClosed']=not thread.is_alive()
 if sock is not None:sock.close()
 if P is not None and original is not None:P.analyze_product=original
 result['callbackRestored']=P is None or original is None or P.analyze_product is original
 if lease is not None and hasattr(lease,'identity'):result['resource']=lease.receipt()
 result.update(finishedAtUTC=now(),listenerClosed=sock is None or sock.fileno()==-1,normalBuilds=0,normalRestarts=0)
 save(PREFIX+'-checks.json',result)
 print(json.dumps({k:result.get(k) for k in ('status','preacceptance','http','seconds','fullCandidatePosts','blocker','serverThreadClosed','callbackRestored','availableBeforeMiB')}),flush=True)
