import datetime, hashlib, json, re, socket, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PRODUCT=ROOT.parent/'attune-live-test';OUT=ROOT/'research/preacceptance'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args]).decode().strip()
base='f8f08d98cf23eb23c5a171b5b50411364d79adf6'
if sys.argv[1]=='verify':
    auth=read('openai-readonly-proof.json');normal=read('normal-shortcut-proof.json');deps=read('dependency-proof.json')
    assert auth['httpStatus']==200 and auth['authentication']=='PASS' and auth['modelGenerationRequests']==auth['ttsRequests']==auth['summaryRequests']==0
    assert normal['status']=='PASS' and normal['freshProcess'] and normal['permissionSettingsPreserved'] and normal['unrelatedChromeWindowsPreserved']
    ui=normal['actualProductionUI']
    controls=['defaultCloudAndSpeechOff','cloudTTSRequiresConsentAndConfiguredKey','speechOffPreventsNativeCapture','revokedCloudTTSCannotDispatchAndActualTextRemains','configuredKeyWithCloudOffUsesActualLocalDemo','cloudRevocationCancelsSession','appMicrophoneOffBlocksCaptureDespiteSpeechConsent']
    assert all(ui[c] for c in controls) and ui['captureAttempts']==ui['blockedUnauthorizedRequests']==0
    assert ui['generationRequests']==[{'path':'mental/converse','cloudConsent':False}]
    assert deps['fullAudit']['high']==7 and deps['productionAudit']['total']==0 and deps['patchedVersions']==[None]
    assert read('current-lint-inventory.json')['unchanged'] and read('preservation-before.json')==read('preservation-after.json')
    assert read('pr-state.json')['isDraft'] and read('pr-state.json')['headRefOid']==base and read('pr-state.json')['mergedAt'] is None
    assert git('diff',base,'--name-only','--','package.json','package-lock.json','apps','services','tests','scripts','.github')==''
    key=''
    for line in (PRODUCT/'.env.local').read_text(encoding='utf-8').splitlines():
        name,separator,value=line.partition('=')
        if separator and name.strip()=='OPENAI_API_KEY':key=value.strip().strip('"').strip("'")
    assert key
    pattern=re.compile(rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}')
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name not in ['completion-proof.json','research-immutable.patch','immutable-diff.json']]
    build=[p for p in (PRODUCT/'apps/vehicle-app/.next').rglob('*') if p.is_file()]
    leaks=[]
    for p in files:
        data=p.read_bytes()
        if key.encode() in data or pattern.search(data):leaks.append(str(p.relative_to(ROOT)))
    for p in build:
        if key.encode() in p.read_bytes():leaks.append('frontend-build-file')
    assert not leaks,'Secret presence detected; no secret value output'
    for port in [3000,8000]:
        with socket.socket() as s:assert s.connect_ex(('127.0.0.1',port))!=0
    visuals=[{'file':name,'sha256':sha(OUT/name),'openedForReview':True,'review':'Actual local demo/provider label and denied microphone boundary; synthetic book text only'} for name in ['ui-consent-local-only.png','ui-microphone-off.png']]
    summary={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'productSource':base,'freshUIBoundaryChecksPassed':7,'imagesOpenedAndReviewed':visuals,
        'readOnlyProviderAuthentication':'PASS','keyMetadataDistinction':'UNVERIFIED','keyRevocation':'USER_REPORTED_NOT_ADMIN_VERIFIED',
        'candidateApplied':False,'newExperimentCI':None,'providerIncidentRetentionDeletion':'UNVERIFIED','newPaidRequests':0,'physicalMicrophoneCapture':0,'providerMessagesSent':0,
        'leakScan':{'newEvidenceAndScriptsFiles':len(files),'existingFrontendBuildFiles':len(build),'currentKeyValueMatches':0,'newEvidenceKeyPatternMatches':0,'plaintextRecorded':False},
        'preservation':'PASS','productPromotionReady':False}
    (OUT/'verification-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))
else:
    assert sys.argv[1]=='stamp' and git('status','--porcelain')==''
    head=git('rev-parse','HEAD');changed=git('diff','--name-only',base,head).splitlines()
    assert changed and all(p.startswith('research/preacceptance/') for p in changed)
    patch=subprocess.check_output(['git','-C',str(ROOT),'diff','--binary',base,head]);(OUT/'research-immutable.patch').write_bytes(patch)
    manifest={p:sha(ROOT/p) for p in changed}
    delivery={'researchHead':head,'sourceProductHead':base,'branch':git('branch','--show-current'),'changedFiles':manifest,'patchSha256':sha(OUT/'research-immutable.patch'),'runtimeDependencyConfigDiff':[],'candidateApplied':False,'experimentPushed':False,'experimentCI':None,'productPromotionReady':False,'summary':read('verification-summary.json')}
    (OUT/'completion-proof.json').write_text(json.dumps(delivery,indent=2),encoding='utf-8')
    (OUT/'immutable-diff.json').write_text(json.dumps({'base':base,'head':head,'patchSha256':delivery['patchSha256'],'files':manifest},indent=2),encoding='utf-8')
    print(json.dumps({'researchHead':head,'sourceProductHead':base,'changedFiles':len(changed),'patchSha256':delivery['patchSha256'],'productPromotionReady':False}))
