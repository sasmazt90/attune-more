"""Bounded production build in this isolated worktree only."""
import hashlib,json,os,subprocess,sys
import psutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/health-final-technical-closeout-20261017'
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from heavy_job_lease import HeavyJobLease
os.environ.update(NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8311',NEXT_TELEMETRY_DISABLED='1',CI='1',NEXT_PUBLIC_ATTUNE_ACNE_V5='1',NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT='8311')
# Prior complete build measured 650 MiB summed RSS including children. Reserve
# 900 MiB for this build; the shared lease still enforces 400 MiB system reserve.
# Start budget = measured 650 + reserve 400 + 150 MiB margin, no model work.
with HeavyJobLease('CDC-health-final-build',peak_mib=900,minimum_available_mib=1200,include_children=True,memory_metric='rss') as lease:
 with (OUT/'build.log').open('w',encoding='utf8') as log:
  child=subprocess.Popen([r'C:\nvm4w\nodejs\node.exe',str(ROOT/'node_modules/next/dist/bin/next'),'build'],cwd=ROOT/'apps/vehicle-app',stdout=log,stderr=subprocess.STDOUT,env=os.environ)
  birth=psutil.Process(child.pid).create_time()
  try:
   while True:
    try:code=child.wait(timeout=.5);break
    except subprocess.TimeoutExpired:lease.check()
  except BaseException:
   # A guard failure must not leave our own build running after releasing the
   # lease. Match each exact child identity/CWD; never terminate other jobs.
   parent=psutil.Process(child.pid)
   if parent.create_time()==birth:
    owned=[(p,p.create_time()) for p in parent.children(recursive=True)]
    for process,started in reversed(owned):
     try:
      if process.create_time()==started and Path(process.cwd()).resolve().is_relative_to(ROOT):process.terminate()
     except psutil.NoSuchProcess:pass
    child.terminate();child.wait(timeout=10)
   raise
  if code:raise RuntimeError(f'Build failed: {code}')
 sources=[str(p.relative_to(ROOT)) for p in (ROOT/'apps/vehicle-app/src').rglob('*') if p.suffix in ('.ts','.tsx','.css')]+[str(p.relative_to(ROOT)) for p in (ROOT/'services/core-api').glob('*.py')]+['apps/vehicle-app/next.config.mjs','apps/vehicle-app/public/audio/guidance/manifest.json','package.json','package-lock.json','apps/vehicle-app/package.json']
 files=[ROOT/p for p in sources]+list((ROOT/'apps/vehicle-app/.next/static').rglob('*.js'))
 value=dict(BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),apiPort=8311,frontendPort=3311,files=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],resource=lease.receipt())
 tmp=OUT/'build-receipt.tmp';tmp.write_text(json.dumps(value,indent=2),'utf8');tmp.replace(OUT/'build-receipt.json');print('BUILD_OK',value['BUILD_ID'])
