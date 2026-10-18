"""Bounded build of the isolated vision delivery, preserving ordinary API defaults."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/vision-technical-closeout-20261017'
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from heavy_job_lease import HeavyJobLease
os.environ.update(NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8306',NEXT_TELEMETRY_DISABLED='1',CI='1')
with HeavyJobLease('CDC-vision-technical-build',peak_mib=2100,minimum_available_mib=1600,include_children=True,memory_metric='rss') as lease:
    with (OUT/'build.log').open('w',encoding='utf8') as log:
        child=subprocess.Popen([r'C:\nvm4w\nodejs\node.exe',str(ROOT/'node_modules/next/dist/bin/next'),'build'],cwd=ROOT/'apps/vehicle-app',stdout=log,stderr=subprocess.STDOUT,env=os.environ)
        while True:
            try:code=child.wait(timeout=.5);break
            except subprocess.TimeoutExpired:lease.check()
        if code:raise RuntimeError(f'Isolated build failed: {code}')
    sources=['apps/vehicle-app/src/app/vision/page.tsx','apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','apps/vehicle-app/src/context/VehicleContext.tsx','apps/vehicle-app/src/utils/localBackend.ts','apps/vehicle-app/src/utils/visionFlow.ts','apps/vehicle-app/src/utils/visionTracking.ts','apps/vehicle-app/src/utils/visionResponseGate.ts','apps/vehicle-app/src/utils/visionInference.worker.ts','apps/vehicle-app/src/utils/visionInference.ts','apps/vehicle-app/src/utils/visionAnswerMemory.ts','apps/vehicle-app/src/utils/spokenVision.ts','apps/vehicle-app/src/utils/streamSpeech.ts','apps/vehicle-app/src/components/LetterStimulus.tsx','apps/vehicle-app/src/components/LetterVisionResult.tsx','apps/vehicle-app/src/components/CameraPreparation.tsx','apps/vehicle-app/src/components/VisionFrame.ts']
    files=[ROOT/p for p in sources]+list((ROOT/'apps/vehicle-app/.next/static').rglob('*.js'))
    receipt=dict(BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),apiPort=8306,frontendPort=3306,files=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],resource=lease.receipt())
    temp=OUT/'build-receipt.tmp';temp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');temp.replace(OUT/'build-receipt.json')
    print('BUILD_OK',receipt['BUILD_ID'])
