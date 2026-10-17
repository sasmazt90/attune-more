"""Read-only source/build/served-byte and protected-checkout verification."""
import hashlib,json,subprocess
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/hearing-technical-closeout-20261017'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
git=lambda tree,*args:subprocess.check_output(['git','-C',str(tree),*args],text=True)
build=json.loads((OUT/'build-receipt.json').read_text('utf8'));assert (ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()==build['BUILD_ID']
served=[]
for row in build['files']:
 rel=row['path'].replace('\\','/');assert sha(ROOT/rel)==row['sha256'],rel
 if '/.next/static/' in rel:
  suffix=rel.split('.next/static/',1)[1];response=requests.get('http://127.0.0.1:3309/_next/static/'+suffix,timeout=10);assert response.status_code==200 and hashlib.sha256(response.content).hexdigest()==row['sha256'],suffix
  for test_only in [b'controlled-other-owner',b'savedOldSubmit',b'dinReference',b'CONTROLLED_START_FAILURE']:assert test_only not in response.content
  served.append(dict(path=suffix,bytes=len(response.content),sha256=row['sha256']))
assets=json.loads((OUT/'local-assets.json').read_text('utf8'))
for row in assets:assert sha(ROOT/row['path'])==row['sha256'] and sha(ROOT.parent/'attune-cdc-health-ui-20261017'/row['path'])==row['sha256']
protected=[]
for prior in json.loads((OUT/'protected-start.json').read_text('utf8')):
 tree=ROOT.parent/prior['checkout'];head=git(tree,'rev-parse','HEAD').strip();status=git(tree,'status','--porcelain=v1');assert head==prior['sha'] and status==prior['status'],prior['checkout'];protected.append(dict(checkout=prior['checkout'],sha=head,status=status))
diff=git(ROOT,'diff','7fe773c1f87e0e45dd3386c6e08d13fda6f2cba7','--name-only').splitlines()
runtime=[p for p in diff if p.startswith(('apps/vehicle-app/src/','services/core-api/','apps/vehicle-app/public/'))]
assert set(runtime)=={'apps/vehicle-app/src/app/hearing/page.tsx','apps/vehicle-app/src/utils/hearingAudio.ts','apps/vehicle-app/src/utils/hearingProgress.ts'},runtime
assert not git(ROOT,'diff','7fe773c1f87e0e45dd3386c6e08d13fda6f2cba7','--','apps/vehicle-app/src/utils/hearingProtocol.ts','apps/vehicle-app/src/utils/playbackMeter.ts','apps/vehicle-app/src/utils/serviceConsent.ts','services/core-api')
ledger=requests.get('http://127.0.0.1:8309/__test__/ledger',timeout=10).status_code;assert ledger==404
value=dict(BUILD_ID=build['BUILD_ID'],servedJS=served,sourceFilesVerified=len(build['files']),assetsVerified=len(assets),protected=protected,runtimeChanged=runtime,testLedgerStatus=ledger,physicalHeadphoneAcceptance=False)
t=OUT/'served-protection-receipt.tmp';t.write_text(json.dumps(value,indent=2),'utf8');t.replace(OUT/'served-protection-receipt.json')
print(json.dumps(dict(BUILD_ID=build['BUILD_ID'],servedJS=len(served),sources=len(build['files']),assets=len(assets),protectedTrees=len(protected))))
