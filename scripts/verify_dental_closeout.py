"""Read-only source/build/model/served bytes and protected-checkout verification."""
import hashlib,json,subprocess
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/dental-technical-closeout-20261017'
BASE='e82cc2ffe8739d14b99dc68f02fec33875fc465c'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
git=lambda tree,*args:subprocess.check_output(['git','-C',str(tree),*args],text=True)
build=json.loads((OUT/'build-receipt.json').read_text('utf8'));assert (ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()==build['BUILD_ID']
served=[]
for row in build['files']:
 rel=row['path'].replace('\\','/');assert sha(ROOT/rel)==row['sha256'],rel
 if '/.next/static/' in rel:
  suffix=rel.split('.next/static/',1)[1];r=requests.get('http://127.0.0.1:3310/_next/static/'+suffix,timeout=10)
  assert r.status_code==200 and hashlib.sha256(r.content).hexdigest()==row['sha256'],suffix
  for test_only in [b'releaseOldFrame',b'routeHeld',b'dental-camera-final',b'Physical camera forbidden']:assert test_only not in r.content
  served.append(dict(path=suffix,bytes=len(r.content),sha256=row['sha256']))
assets=json.loads((OUT/'local-assets.json').read_text('utf8'))
for row in assets:assert sha(ROOT/row['path'])==row['sha256']==sha(ROOT.parent/'attune-cdc-hearing-technical-20261017'/row['path'])
protected=[]
for prior in json.loads((OUT/'protected-start.json').read_text('utf8')):
 tree=ROOT.parent/prior['checkout'];head=git(tree,'rev-parse','HEAD').strip();status=git(tree,'status','--porcelain=v1')
 assert head==prior['sha'] and status==prior['status'],prior['checkout']
 protected.append(dict(checkout=prior['checkout'],sha=head,status=status))
diff=set(git(ROOT,'diff',BASE,'--name-only').splitlines())|set(git(ROOT,'ls-files','--others','--exclude-standard').splitlines())
runtime=sorted(p for p in diff if p.startswith(('apps/vehicle-app/src/','services/core-api/','apps/vehicle-app/public/')))
expected={'apps/vehicle-app/src/app/dental/page.tsx','apps/vehicle-app/src/app/privacy/page.tsx','apps/vehicle-app/src/components/DentalRecordDetail.tsx','apps/vehicle-app/src/components/DentalSourceView.tsx','apps/vehicle-app/src/components/RecordHistory.tsx','apps/vehicle-app/src/utils/dentalCapture.ts','apps/vehicle-app/src/utils/dentalPhotoHistory.ts','apps/vehicle-app/src/utils/dentalResult.ts','apps/vehicle-app/src/utils/healthRecords.ts','services/core-api/dental_analysis.py','services/core-api/dental_upload.py','services/core-api/local_health.py'}
assert set(runtime)==expected,runtime
preserved=['apps/vehicle-app/src/app/hearing','apps/vehicle-app/src/app/vision','apps/vehicle-app/src/app/mental','apps/vehicle-app/src/app/skin','apps/vehicle-app/src/utils/hearingAudio.ts','apps/vehicle-app/src/utils/hearingProgress.ts','apps/vehicle-app/src/utils/hearingProtocol.ts','apps/vehicle-app/src/utils/playbackMeter.ts','apps/vehicle-app/src/utils/audioGuidance.ts','apps/vehicle-app/src/utils/serviceConsent.ts','apps/vehicle-app/src/components/HealthConsentGate.tsx','services/core-api/appearance_analysis.py','services/core-api/contour_appearance.py','services/core-api/instant_appearance.py','services/core-api/experimental_acne_v5.py','services/core-api/main.py','apps/vehicle-app/next.config.mjs']
assert not git(ROOT,'diff',BASE,'--',*preserved)
cfg=json.loads((ROOT/'services/core-api/models/dental-yolox-s.json').read_text('utf8'));model=ROOT/'services/core-api/models/dental-yolox-s.onnx'
assert sha(model)==cfg['modelHash']=='eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03'
assert cfg['classes']==['D','d'] and cfg['confidenceThreshold']==.35 and cfg['inputSize']==320
assert requests.get('http://127.0.0.1:8310/__test__/ledger',timeout=10).status_code==404
value=dict(commit=git(ROOT,'rev-parse','HEAD').strip(),BUILD_ID=build['BUILD_ID'],servedJS=served,sourceAndBuildFiles=len(build['files']),assetsVerified=len(assets),protected=protected,runtimeChanged=runtime,preservedPaths=preserved,modelHash=cfg['modelHash'],classes=cfg['classes'],confidenceThreshold=.35,nmsThreshold=.45,testLedgerStatus=404,physicalCameraAcceptance=False)
t=OUT/'served-protection-receipt.tmp';t.write_text(json.dumps(value,indent=2),'utf8');t.replace(OUT/'served-protection-receipt.json')
print(json.dumps(dict(BUILD_ID=build['BUILD_ID'],servedJS=len(served),sourceAndBuildFiles=len(build['files']),assets=len(assets),protectedTrees=len(protected))))
