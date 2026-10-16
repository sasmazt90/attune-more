"""Build only the isolated opt-in preview, recording the exact served artifact chain."""
from pathlib import Path
import sys,os,json,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'cdc-progress/acne-v5-integration-20261017'
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from heavy_job_lease import HeavyJobLease
os.environ.update(NEXT_PUBLIC_ATTUNE_ACNE_V5='1',NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT='8305',NEXT_TELEMETRY_DISABLED='1',CI='1')
with HeavyJobLease('CDC-acne-v5-isolated-preview-build',peak_mib=2100,minimum_available_mib=1600,include_children=True,memory_metric='private') as lease:
 cmd=[r'C:\nvm4w\nodejs\node.exe',str(ROOT/'node_modules/next/dist/bin/next'),'build'];log=OUT/'preview-build.log'
 with log.open('w',encoding='utf8') as f:
  p=subprocess.Popen(cmd,cwd=ROOT/'apps/vehicle-app',stdout=f,stderr=subprocess.STDOUT,env=os.environ)
  while True:
   try:code=p.wait(timeout=.5);break
   except subprocess.TimeoutExpired:lease.check()
  assert code==0,('PREVIEW_BUILD_FAILED',code)
 files=[ROOT/x for x in ['apps/vehicle-app/next.config.mjs','apps/vehicle-app/src/app/skin/page.tsx','apps/vehicle-app/src/components/skin/ExperimentalAcnePhoto.tsx','apps/vehicle-app/src/components/skin/SkinFacePanel.tsx','apps/vehicle-app/src/context/VehicleContext.tsx','apps/vehicle-app/src/utils/previewLocalApi.ts','apps/vehicle-app/src/utils/skinEyewear.ts','apps/vehicle-app/src/utils/skinSnapshot.ts']]
 files+=list((ROOT/'apps/vehicle-app/.next/static').rglob('*.js'))
 receipt=dict(BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),experimentalFlag=True,ports=dict(API=8305,frontend=3305),files=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],resource=lease.receipt())
 temp=OUT/'build-receipt.tmp';temp.write_text(json.dumps(receipt,indent=2),encoding='utf8');temp.replace(OUT/'build-receipt.json');print('BUILD_OK',receipt['BUILD_ID'])
