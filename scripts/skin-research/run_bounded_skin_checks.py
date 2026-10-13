"""Serial focused checks under both real ownership leases and RAM reserve."""
import os,sys,subprocess,json,time,shutil
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-closeout-20261013'
phase=sys.argv[1];env=os.environ.copy()
env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',RAYON_NUM_THREADS='1',SWC_THREADS='1',NODE_OPTIONS='--max-old-space-size=512')
tests=['test_skin_eyewear_capture.py','test_dual_compute_lease.py','test_contour_source_roi.py','test_native_roi_compute_contract.py','test_native_material_runtime.py','test_native_dry_path.py','test_material_contour_branches.py','test_local_health_boundary.py']
if phase in ['tests','tests-core','tests-eye']:
    selected=tests[1:] if phase=='tests-core' else tests[:1] if phase=='tests-eye' else tests
    commands=[([sys.executable,'-m','pytest',*[str(ROOT/'tests/unit'/n) for n in selected],'-q'],ROOT)]
    limit,reserve=(350,750) if phase=='tests-core' else (500,900) if phase=='tests-eye' else (700,1100)
elif phase=='typecheck':commands=[(['C:/nvm4w/nodejs/node.exe',str(ROOT/'node_modules/next/dist/bin/next'),'typegen'],ROOT/'apps/vehicle-app'),(['C:/nvm4w/nodejs/node.exe',str(ROOT/'node_modules/typescript/bin/tsc'),'--noEmit'],ROOT/'apps/vehicle-app')];limit=650;reserve=1000
elif phase=='lint':
    files=['src/app/skin/page.tsx','src/components/skin/SkinStartView.tsx','src/utils/skinEyewear.ts','src/utils/skinIndicators.ts','src/utils/skinAnalyzer.ts','src/utils/appearanceMeasurements.ts','src/utils/healthHistorySeries.ts']
    commands=[(['C:/nvm4w/nodejs/node.exe',str(ROOT/'node_modules/eslint/bin/eslint.js'),*files],ROOT/'apps/vehicle-app')];limit=250;reserve=650
elif phase=='build':
    # Typecheck's measured owned peak was 347.5 MiB. One build worker and
    # a smaller per-process JS heap bound this job separately from photo work.
    env['NODE_OPTIONS']='--max-old-space-size=256'
    shell=shutil.which('pwsh')
    if not shell:raise RuntimeError('Verified PowerShell Core runtime unavailable')
    commands=[([shell,'-NoProfile','-File',str(ROOT/'scripts/skin-research/prepare_selected_build.ps1'),'-BuildName','skin-eyewear-camera-final-20261013'],ROOT)];limit=600;reserve=1050
elif phase=='build-existing':
    stage=ROOT/'.runtime/skin-eyewear-camera-final-20261013'
    receipt=json.loads((stage/'source-receipt.json').read_text('utf-8-sig'))
    import hashlib
    if not all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest and hashlib.sha256((stage/name).read_bytes()).hexdigest()==digest for name,digest in receipt.items()):raise RuntimeError('Frozen build source drift')
    if not (OUT/'lint-receipt.json').exists():raise RuntimeError('Run focused lint before serial build verification')
    lint=json.loads((OUT/'lint-receipt.json').read_text('utf8'))
    lint_log=ROOT/lint['rows'][0]['log']
    lint_paths=['app/skin/page.tsx','components/skin/SkinStartView.tsx','utils/skinEyewear.ts','utils/skinIndicators.ts','utils/skinAnalyzer.ts','utils/appearanceMeasurements.ts','utils/healthHistorySeries.ts']
    if lint['rows'][0]['exitCode']!=0 or any((ROOT/'apps/vehicle-app/src'/p).stat().st_mtime>lint_log.stat().st_mtime for p in lint_paths):raise RuntimeError('Focused lint source coverage changed; no build claim')
    commands=[(['C:/nvm4w/nodejs/node.exe',str(ROOT/'node_modules/next/dist/bin/next'),'build','.','--no-lint'],stage/'apps/vehicle-app')];limit=850;reserve=1300
else:raise ValueError('Unknown bounded check')
if '--wait-resource' in sys.argv:
    # Wait after runtime imports, not in a second parent/spawn race. The real
    # lease still rechecks both owners, available RAM and the AG inventory.
    import psutil
    started=time.time();deadline=time.monotonic()+180;observations=[]
    while True:
        available=psutil.virtual_memory().available/2**20;observations.append(available)
        if available>=reserve+75 or time.monotonic()>=deadline:break
        time.sleep(1)
    (OUT/(phase+'-resource-wait.json')).write_text(json.dumps(dict(started=started,finished=time.time(),maximumWaitSeconds=180,minimumObservedAvailableMiB=min(observations),maximumObservedAvailableMiB=max(observations),finalAvailableMiB=available,requiredStartMiB=reserve,ready=available>=reserve+75,buildStarted=False),indent=2),'utf8')
with HeavyJobLease('CDC-skin-'+phase,peak_mib=limit,minimum_available_mib=reserve,include_children=True,memory_metric='private') as lease:
    rows=[]
    for args,cwd in commands:
        lease.check();start=time.monotonic();log=OUT/(phase+'-'+str(time.time_ns())+'-'+str(len(rows))+'.log')
        (OUT/(phase+'-progress.json')).write_text(json.dumps(dict(log=str(log.relative_to(ROOT)),started=time.time(),finished=False)),'utf8')
        with log.open('w',encoding='utf8') as output:
            process=subprocess.Popen(args,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0)
            import psutil
            birth=psutil.Process(process.pid).create_time()
            try:
                while process.poll() is None:time.sleep(.25);lease.check()
            except BaseException as error:
                failure=dict(errorType=type(error).__name__,error=str(error),log=str(log.relative_to(ROOT)),resource=lease.receipt(),availableMiB=psutil.virtual_memory().available/2**20,finished=True,success=False)
                (OUT/(phase+'-failure.json')).write_text(json.dumps(failure,indent=2),'utf8')
                print(json.dumps(dict(failedPhase=phase,error=str(error))),flush=True)
                # Only this check's actual Popen tree can be stopped. Never an
                # AG worker, trainer, browser belonging to the user, or old PID.
                children=lease.own_children()
                for child in reversed(children):
                    if child.pid==getattr(getattr(lease,'observer',None),'pid',None):continue
                    try:
                        if child.create_time()>=birth:child.terminate()
                    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                try:
                    if process.poll() is None and psutil.Process(process.pid).create_time()==birth:process.terminate()
                except psutil.NoSuchProcess:pass  # An already-exited owned parent needs no stop.
                except psutil.AccessDenied:print('Owned parent cleanup denied; no unverified PID stopped',flush=True)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:print('Owned parent drain timed out; original failure preserved',flush=True)
                raise
        rows.append(dict(commandPhase=phase,exitCode=process.returncode,seconds=time.monotonic()-start,log=str(log.relative_to(ROOT))))
        print(json.dumps(rows[-1]),flush=True)
        if process.returncode:raise RuntimeError('Focused check failed; inspect own log')
    (OUT/(phase+'-receipt.json')).write_text(json.dumps(dict(rows=rows,resource=lease.receipt()),indent=2),'utf8')
    (OUT/(phase+'-progress.json')).write_text(json.dumps(dict(log=str(log.relative_to(ROOT)),finished=True,success=True)),'utf8')
