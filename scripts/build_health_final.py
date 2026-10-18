"""Bounded production build in this isolated worktree only."""
import hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'tooling'))
from finite_job import run_tool
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.environ.get('ATTUNE_BUILD_EVIDENCE_DIR',str(ROOT.parent/'cdc-progress/skin-type-local-20261017')))
if not OUT.resolve().is_relative_to((ROOT.parent/'cdc-progress').resolve()):raise ValueError('Build evidence must stay inside the workspace progress directory')
os.environ.update(NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8311',NEXT_TELEMETRY_DISABLED='1',CI='1',NEXT_PUBLIC_ATTUNE_ACNE_V5='1',NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT='8311')
def build():
 with (OUT/'build.log').open('w',encoding='utf8') as log:
  guarded=run_tool('build',stdout=log,stderr=log)
  if guarded['exitCode']:raise RuntimeError(f"Build failed under finite guard: {guarded['reason']} / {guarded['exitCode']}")
 sources=[str(p.relative_to(ROOT)) for p in (ROOT/'apps/vehicle-app/src').rglob('*') if p.suffix in ('.ts','.tsx','.css')]+[str(p.relative_to(ROOT)) for p in (ROOT/'services/core-api').glob('*.py')]+['apps/vehicle-app/next.config.mjs','apps/vehicle-app/public/audio/guidance/manifest.json','package.json','package-lock.json','apps/vehicle-app/package.json']
 files=[ROOT/p for p in sources]+list((ROOT/'apps/vehicle-app/.next/static').rglob('*.js'))
 value=dict(BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),apiPort=8311,frontendPort=3000,files=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],resource=guarded['rssLease'],finiteJob=guarded)
 tmp=OUT/'build-receipt.tmp';tmp.write_text(json.dumps(value,indent=2),'utf8');tmp.replace(OUT/'build-receipt.json');print('BUILD_OK',value['BUILD_ID'])

if __name__=='__main__':build()
