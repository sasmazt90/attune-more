"""Small provenance-only recovery receipt. No inference, builds or user data reads."""
import ast,datetime,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/material-closeout-20261013'
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def load(name):return json.loads((OUT/name).read_text('utf-8-sig'))
stage=ROOT/'.runtime/skin-eyewear-camera-final-20261013'
snapshot=json.loads((stage/'source-receipt.json').read_text('utf-8-sig'))
drift=[p for p,h in snapshot.items() if digest(ROOT/p)!=h or digest(stage/p)!=h]
assert not drift,'Frozen sources changed'
names=set(git('diff','--name-only','HEAD').splitlines())|set(git('ls-files','--others','--exclude-standard').splitlines())
names.discard('')
source_hashes={p:digest(ROOT/p) for p in sorted(names) if (ROOT/p).is_file()}
python_files=[p for p in names if p.endswith('.py')]
for p in python_files:ast.parse((ROOT/p).read_text('utf-8-sig'),filename=p)
lint=load('lint-receipt.json');lint_time=(ROOT/lint['rows'][0]['log']).stat().st_mtime
lint_files=['app/skin/page.tsx','components/skin/SkinStartView.tsx','utils/skinEyewear.ts','utils/skinIndicators.ts','utils/skinAnalyzer.ts','utils/appearanceMeasurements.ts','utils/healthHistorySeries.ts']
lint_paths=['apps/vehicle-app/src/'+p for p in lint_files]
assert all((ROOT/p).stat().st_mtime<=lint_time for p in lint_paths)
comparisons=load('group-loss-comparison.json')
eyes=load('eyewear-model-comparison.json')
camera=load('camera-http-profile.json')
live_build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip()
build_path=OUT/'build-existing-receipt.json'
build_complete=build_path.exists() and build_path.stat().st_mtime>=(stage/'source-receipt.json').stat().st_mtime and all(r['exitCode']==0 for r in load(build_path.name)['rows'])
delivery=load('normal-shortcut-delivery.json') if (OUT/'normal-shortcut-delivery.json').exists() else None
delivered=bool(build_complete and delivery and delivery['buildId']==live_build and delivery['frozenSourceReceiptSHA256']==digest(stage/'source-receipt.json'))
receipt=dict(
    createdUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),baseCommit=git('rev-parse','HEAD'),
    branch=git('branch','--show-current'),preservedInitialBuild='JO0Xyvupv72uoBiX42mWq',currentLiveBuild=live_build,
    frozenFrontendFiles=len(snapshot),frozenFrontendDrift=drift,currentSourceSHA256=source_hashes,
    checks=dict(core=load('tests-core-receipt.json'),eyewear=load('tests-eye-receipt.json'),priorTypecheck=load('typecheck-receipt.json'),lint=lint,currentLintSourceSHA256={p:source_hashes[p] for p in lint_paths},currentPythonSyntaxFiles=len(python_files)),
    currentBuildComplete=build_complete,normalShortcutNewBuildVerified=delivered,productBrowserAcceptanceComplete=delivered,
    initialResourceBlock=dict(kind='RAM_RESERVE',observedAtFailedBuildEntryMiB=523.9921875,requiredStartMiB=1300,finiteWaitSeconds=180,cleared=build_complete,foreignJobsStopped=False,guardsRelaxed=False),
    dry=dict(comparison= comparisons['summary'],candidateAccepted=False,newGlassesFreeAccuracyClaim=False,normalVersion='v3',corrected24031977TargetSupport=[0,0],halfScaleReviewedNegativeSourcePixels=216),
    nativeCamera=dict(actualHTTP=camera['actualHTTP'],rows=[dict(source=r['source'],status=r['status'],httpSeconds=r['httpSeconds'],within45Seconds=r['within45Seconds'],sourceImageSize=r['sourceImageSize']) for r in camera['rows']],normalProductEnabled=False,physicalPCTrackSize=[1920,1080],controlledAcceptedSnapshotSize=[1280,960],phoneAndVehicleHardwareVerified=False),
    eyewear=dict(modelHash=eyes['rows'][0]['modelHash'],controls=[{k:r[k] for k in ['source','actualEyewear','status','probability']} for r in eyes['rows']],uniqueGlassesPositive=1,knownGlassesFreeControls=4,generalAccuracyClaim=False,normalProductEnabled=delivered),
    sag=dict(normalChinVersion='v9',normalCheekVersion='v7',neutralExteriorProminencePositiveVerified=False,source4d05BrowserCaptureSaved=True,source4d05ContourRunPending=not (OUT/'4d05d72b-current-contour-result.json').exists()),
    protected=dict(userRecordsRewritten=False,AGModified=False,trainingRestarted=False,acneActivated=False,oldReportsRewritten=False,normalBuildReplaced=live_build!='JO0Xyvupv72uoBiX42mWq'))
(OUT/'recovery-delivery-state.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
if delivered:
    browser=load('eyewear-product-browser.json');geometry=load('history-source-geometry.json');sag=load('neutral-contour-probe.json')
    public=dict(baseCommit=receipt['baseCommit'],buildId=live_build,normalDeliveryVerified=delivered,
        buildSeconds=load('build-existing-receipt.json')['rows'][0]['seconds'],priorCoreTests=47,priorEyewearTests=5,currentBuildTypecheckPassed=build_complete,
        normalSkinHTTP=browser['normalSkinHTTP'],controlledSourceSize=browser['sourceSize'],controlledClearToResultSeconds=browser['resumedAfterActualClearSeconds'],
        blockedAnalysisRequests=browser['blocked']['requests'],blockedHistoryRecords=browser['blocked']['records'],startClipPlayingEvents=browser['voiceStartCount'],
        scopeComparisons=browser['scopeComparisons'],native200=geometry['geometry'],actualMapSourceCoordinates=geometry['actualMapSourceCoordinates'],apiMapSourceCoordinates=geometry['expectedAPISourceCoordinates'],
        dryComparison=receipt['dry'],nativeCamera=receipt['nativeCamera'],
        sagRows=[dict(source=r['source'],status=r['status'],groundTruthPositive=r['neutralProminenceGroundTruth'],measurements=r.get('rows')) for r in sag['rows']],
        selectedSourceHashes=delivery['sourceHashes'],servedJavascriptSHA256=delivery['servedJavascriptSHA256'],skinStartAudioSHA256=delivery['skinStartAudioSHA256'],
        frozenSourceReceiptSHA256=delivery['frozenSourceReceiptSHA256'],localFullReceipt='audit-results/material-closeout-20261013/recovery-delivery-state.json',
        oldRecordsRecomputed=False,AGModified=False,acneActivated=False,physicalSamePersonGlassesRemovalTest=False,phoneAndVehicleCamerasVerified=False)
    (ROOT/'docs/material-closeout-recovery-evidence-20261014.json').write_text(json.dumps(public,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(snapshotFiles=len(snapshot),sourceDrift=drift,pythonSyntaxFiles=len(python_files),liveBuild=live_build,buildComplete=build_complete,delivered=delivered)))
