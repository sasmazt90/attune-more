"""One small dry-path staging check on the locked existing real inputs.
No normal API/server, user record, new photo, threshold or live-gate override.
"""
import copy,hashlib,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'cdc-progress/skin-dryness-dualscale-20261018'
sys.path.insert(0,str(ROOT/'services/core-api'));sys.path.insert(0,str(ROOT/'scripts/skin-research'))
import psutil
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,v):
 p=OUT/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8');os.replace(t,p)
assert read(OUT/'results.json')['summary']['opticalDevelopmentCandidatePass']
RESUME='--resume-third-wrapper' in sys.argv
THIRD='--third-only' in sys.argv or RESUME;PREFIX='runtime-third-resumed' if RESUME else 'runtime-third' if THIRD else 'runtime'
if RESUME:
 failed=read(OUT/'runtime-third-checks.json')
 assert failed.get('blocker')=="KeyError: 'photo'" and not failed['rows'],'Only the proven pre-decode wrapper failure can resume'
assert not (OUT/(PREFIX+'-start.json')).exists(),'Do not repeat this fixed runtime check'
locked=read(OUT/'runtime-input-index.json');eligible=[];held=[]
for row in locked['inputs']:
 if THIRD and not row.get('eligibleForThirdCheck'):continue
 assert sha(Path(row['payloadPath']))==row['payloadSHA256'] and sha(Path(row['savedResultPath']))==row['savedResultSHA256']
 if row['currentExpressionIssue'] is None and row['sourceFramedComputedByCurrentProduct'] and row['posePassWithOnlyRecordedCaptureFields'] and row['qualityValid'] and row['glassesFreePolicyRecorded']:eligible.append(row)
 else:held.append(dict(photoId=row['photoId'],reason=row['currentExpressionIssue'] or 'CAPTURE_ADMISSION_UNPROVEN'))
assert len(eligible)<=(1 if THIRD else 2)
plan=dict(atUTC=now(),inputs=[r['photoId'] for r in eligible],held=held,scope='Actual current native dry analyzer and one half path with shared session; NOT full normal API or fresh other-model evaluation',coordinateHelperSHA256=sha(ROOT/'services/core-api/dry_dualscale_support.py'),runtimeHelperSHA256=sha(ROOT/'services/core-api/dry_dualscale_runtime_staging.py'),halfCropContract='same original crop/origin; cv2 INTER_AREA fx=fy=.5; metric and pixel_density *.5; same frozen head/encoder; original native valid masks own original source pixels',maximumPhotoInputs=2,minimumAvailableMiB=2500,deadlineSeconds=45,fitCount=0,normalRuntimeActivation=False,normalCurrentPositiveInputAvailable=any(r.get('preexistingNativeSupportRegionSum',0)>0 or r['scope'].find('nonzero')>=0 for r in eligible))
save(PREFIX+'-plan.json',plan);save(PREFIX+'-start.json',dict(atUTC=now(),logicalRun=1,continuationOnlyNewThirdInput=THIRD))
result=dict(atUTC=now(),plan=plan,availableBeforeMiB=round(psutil.virtual_memory().available/2**20),rows=[],heldInputs=held,fitCount=0,normalAPICalls=0,otherModelCalls=0,normalProductEnabled=False)
lease=None;encoder=None
try:
 if result['availableBeforeMiB']<2500:
  result.update(status='NOT_RUN_RESOURCE_RESERVE',blocker='Minimum2500MiB model start reserve not met; no retry/wait/other app stop')
 elif not eligible:result.update(status='NOT_RUN_NO_CURRENT_ADMITTED_INPUT',blocker='No locked input satisfies current capture admission')
 else:
  from heavy_job_lease import HeavyJobLease
  from native_material_budget import NativeRequestBudget
  with HeavyJobLease('CDC-DRY-01-fixed-dualscale-runtime',peak_mib=2000,minimum_available_mib=2500,include_children=True,memory_metric='rss') as lease:
   import numpy as np,cv2
   from dry_dualscale_runtime_staging import analyze_staging,METHOD,NORMALIZATION
   import product_dryness as P,material_component_features as M
   from skin_measurement_contract import attach_result_receipts
   from local_skin_type import finalize_product_type
   for row in eligible:
    started=time.monotonic();scope=NativeRequestBudget()
    def check():scope.check();lease.check()
    check();head,encoder=P.runtime(check)
    document=read(Path(row['payloadPath']));payload=document[row['payloadWrapperKey']] if row.get('payloadWrapperKey') else document
    old=read(Path(row['savedResultPath']))
    staged=analyze_staging(payload,head,encoder,check);check()
    native=staged['native'];candidate=staged['candidate'];support=staged['support']
    assert native['photoId']==candidate['photoId']==row['photoId'] and [native['sourceWidth'],native['sourceHeight']]==row['sourceSize']
    identity=hashlib.sha256((P.HEAD_SHA+P.ORT_SHA+M.ENCODER_SHA).encode()).hexdigest()
    combined=P.replace_dryness(copy.deepcopy(old),copy.deepcopy(candidate),identity)
    for rows in combined['measurements'].values():
     for r in rows:
      if r['id']=='dry':r.update(methodVersion=METHOD,normalizationVersion=NORMALIZATION);r['components']['samplingSupportVersion']=candidate['nativeMetadata']['dualscaleVersion']
    if combined.get('general'):
     for r in combined['general']['measurements']:
      if r['id']=='dry':r.update(methodVersion=METHOD,normalizationVersion=NORMALIZATION);r['components']['samplingSupportVersion']=candidate['nativeMetadata']['dualscaleVersion']
    for key,layer in combined['maps'].items():
     if key.endswith(':dry'):layer.update(method=METHOD,normalizationVersion=NORMALIZATION,samplingSupportVersion=candidate['nativeMetadata']['dualscaleVersion'])
    combined['drynessRuntime']['normalProductEnabled']=False
    combined=finalize_product_type(combined);once=copy.deepcopy(combined);combined=finalize_product_type(combined);idempotent=combined==once
    nondry=lambda v:{reg:[r for r in rr if r['id']!='dry'] for reg,rr in v['measurements'].items()}
    assert nondry(combined)==nondry(old)
    assert {k:v for k,v in old['maps'].items() if not k.endswith(':dry')}=={k:v for k,v in combined['maps'].items() if not k.endswith(':dry')}
    masks=[];source_map=[];scores=[]
    for region,n in native['measurements'].items():
     c=candidate['measurements'][region]
     assert c['evaluatedArea']==n['evaluatedArea'] and c['quality']==n['quality'] and c['limitationCode']==n['limitationCode']
     if n['value'] is None:assert c['value'] is None and region+':dry' not in candidate['maps'];continue
     layer=candidate['maps'][region+':dry'];raw=cv2.imdecode(np.frombuffer(__import__('base64').b64decode(layer['dataUrl'].split(',',1)[1]),np.uint8),cv2.IMREAD_UNCHANGED)
     mask=cv2.imdecode(np.frombuffer(__import__('base64').b64decode(layer['validMaskUrl'].split(',',1)[1]),np.uint8),cv2.IMREAD_GRAYSCALE)>0
     assert not (raw[:,:,3][~mask]>0).any()
     assert c['value']==100*c['components']['acceptedMaterialSourcePixels']/max(1,c['components']['uniqueVisibleSourcePixels'])
     scores.append(dict(region=region,before=n['value'],candidate=c['value'],beforeAccepted=n['components']['acceptedMaterialSourcePixels'],candidateAccepted=c['components']['acceptedMaterialSourcePixels'],originalDenominator=c['components']['uniqueVisibleSourcePixels']))
     source_map.append(dict(region=region,x=layer['x'],y=layer['y'],step=layer['step'],width=layer['width'],height=layer['height'],outsideValidPixels=0,expectedSourcePhoto=layer['photoId']==row['photoId']))
    check();elapsed=time.monotonic()-started
    assert elapsed<45
    # Preserve source crops and overlays only outside Git for finite review.
    x,y=staged['origin'];crop=staged['crop'].copy();h,w=crop.shape[:2]
    added=((support.combined>.04)&~(support.native>.04))[y:y+h,x:x+w]
    overlay=crop.copy();overlay[added]=(.4*overlay[added]+.6*np.array([0,0,255])).astype(np.uint8)
    prefix=row['photoId'][:8];cv2.imwrite(str(OUT/(prefix+'-source-crop.png')),crop);cv2.imwrite(str(OUT/(prefix+'-added-support.png')),overlay)
    save(prefix+'-staging-result.json',combined)
    np.savez_compressed(OUT/(prefix+'-runtime-supports.npz'),native=support.native,combined=support.combined,visible=staged['visible'])
    result['rows'].append(dict(photoId=row['photoId'],sourceSize=row['sourceSize'],meshSHA256=row['meshSHA256'],exclusionSHA256=row['exclusionSHA256'],sourceIdentityPreserved=True,currentCaptureAdmission=True,sameNativeAnalyzer=True,sharedEncoderSession=True,headSHA256=P.HEAD_SHA,encoderSHA256=P.ORT_SHA,sourceEncoderSHA256=M.ENCODER_SHA,nativePublishedSupportPixels=int((support.native>.04).sum()),nativePositiveSupportObserved=bool((support.native>.04).any()),nativeSupportLostPixels=support.metadata['nativeLostSourcePixels'],candidateAcceptedSourcePixels=support.metadata['combinedAcceptedSourcePixels'],addedSourcePixels=support.metadata['addedAcceptedSourcePixels'],outsideOriginalVisiblePixels=int(((support.combined>.04)&~staged['visible']).sum()),scores=scores,maps=source_map,otherCriteriaAndMapsPreserved='Cached non-dry snapshot byte/value preservation; no fresh other-module inference',karmaFinalizerIdempotent=idempotent,karmaActualLocalInferenceKind=(old.get('general',{}).get('skinType') or {}).get('inferenceKind'),historyMethodChanged=METHOD!=P.METHOD and NORMALIZATION!=P.NORMALIZATION,profile=staged['profile'],halfContract=staged['halfContract'],dryOnlyColdSeconds=elapsed,fullNormalAPIDeadlineProven=False,encoderCalls=encoder.calls))
    save(PREFIX+'-checks.json',result)
   result.update(status='DRY_PATH_CHECK_COMPLETE_STAGING_ONLY',blocker='Full normal API/history integration and full45s cost not proven' if THIRD else 'Current admitted native-positive control missing (locked nonzero source has OPEN_MOUTH); full normal API/history integration and full45s cost not proven')
   result['resource']=lease.receipt()
except Exception as ex:
 result.update(status='BLOCKED_FINITE_RUNTIME_CHECK',blocker=type(ex).__name__+': '+str(ex))
finally:
 if lease is not None and hasattr(lease,'identity'):result['resource']=lease.receipt()
 # ONNX work is synchronous; the lease context closes its observer/ownership.
 if encoder is not None:
  result['onnxSessionReleasedOnProcessExit']=True
  try:encoder.session=None
  except Exception:pass
  import product_dryness as P;P._runtime=None
 result.update(finishedAtUTC=now(),normalRuntimeTouched=False,normalRestartOrBuild=0)
 save(PREFIX+'-checks.json',result)
 print(json.dumps(dict(status=result.get('status'),rows=[{k:r[k] for k in ('photoId','nativePublishedSupportPixels','candidateAcceptedSourcePixels','addedSourcePixels','outsideOriginalVisiblePixels','dryOnlyColdSeconds')} for r in result['rows']],heldInputs=held,blocker=result.get('blocker'),availableBeforeMiB=result['availableBeforeMiB'])),flush=True)
