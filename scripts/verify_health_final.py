"""Streaming byte identity of this isolated runtime and protected-tree snapshots."""
import hashlib,json,re,subprocess,urllib.request
import psutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'cdc-progress/health-approved-assets-menu-20261017'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(65536),b''):h.update(block)
 return h.hexdigest()
def remote(url):
 h=hashlib.sha256();size=0
 with urllib.request.urlopen(url,timeout=30) as r:
  for block in iter(lambda:r.read(65536),b''):h.update(block);size+=len(block)
 return h.hexdigest(),size
assets=json.loads((OUT/'local-assets.json').read_text('utf8'))
build=json.loads((OUT/'build-receipt.json').read_text('utf8'))
baseline=json.loads((OUT/'baseline.json').read_text('utf8'))
old=OUT.parent/'health-final-technical-closeout-20261017'
assert all(digest(old/name)==value for name,value in baseline['oldEvidence'].items()),'Previous delivery evidence changed'
assert digest(ROOT/'shared/healthModules.json')==baseline['sharedModules'],'Shared order changed'
assert digest(ROOT/'package-lock.json')==baseline['dependencyLock'],'Dependency lock changed'
ownership=[]
state=json.loads((OUT/'processes.json').read_text('utf-8-sig'))
assert state['workspace']==str(ROOT) and state['BUILD_ID']==build['BUILD_ID']
for row in state['processes']:
 p=psutil.Process(row['pid'])
 expected=datetime.fromisoformat(row['startedUTC'].replace('Z','+00:00')).timestamp()
 assert abs(p.create_time()-expected)<.01,'Process start identity changed'
 cwd=Path(p.cwd()).resolve()
 if row['role']=='owned-console-helper':assert p.ppid()==row['parentPid'] and p.name()=='conhost.exe'
 else:assert cwd.is_relative_to(ROOT),'Runtime CWD outside this checkout'
 ownership.append(dict(pid=p.pid,role=row['role'],cwd=str(cwd),start=p.create_time()))
for row in build['files']:assert digest(ROOT/row['path'])==row['sha256'],row['path']
served=[]
for row in assets:
 p=ROOT/row['path'];assert digest(p)==row['sha256']
 if not p.is_relative_to(ROOT/'apps/vehicle-app/public'):
  served.append(dict(path=row['path'],sha256=row['sha256'],bytes=p.stat().st_size,backendLocalOnly=True));continue
 rel=p.relative_to(ROOT/'apps/vehicle-app/public').as_posix()
 actual,size=remote('http://127.0.0.1:3311/'+rel)
 assert actual==row['sha256'],rel
 served.append(dict(path=rel,sha256=actual,bytes=size))
chunks=set();pages=[]
for route in ['/','/skin','/vision','/mental','/hearing','/dental','/profile','/privacy','/care']:
 with urllib.request.urlopen('http://127.0.0.1:3311'+route,timeout=30) as r:html=r.read().decode()
 chunks.update(re.findall(r'(?:src|href)="([^"?]+\.js)(?:\?[^\"]*)?"',html))
 pages.append(dict(route=route,status=200))
for rel in sorted(chunks):
 assert rel.startswith('/_next/static/')
 p=ROOT/'apps/vehicle-app/.next/static'/rel.split('/_next/static/',1)[1]
 actual,size=remote('http://127.0.0.1:3311'+rel);assert actual==digest(p)
 served.append(dict(path=rel,sha256=actual,bytes=size))
git=lambda p,*a:subprocess.check_output(['git','-C',str(p),*a],text=True)
protected=[]
for row in json.loads((OUT/'protected-start.json').read_text('utf8')):
 p=ROOT.parent/row['checkout'];now=dict(checkout=row['checkout'],sha=git(p,'rev-parse','HEAD').strip(),status=git(p,'status','--porcelain=v1'))
 protected.append({**now,'matchesStart':row==now})
(OUT/'protected-final.json').write_text(json.dumps(protected,indent=2),'utf8')
manifest=json.loads((ROOT/'services/core-api/models/skin-focused.json').read_text('utf8'))
acne=manifest['models']['acne'];assert acne['accepted'] is False and acne['file'] is None
result=dict(at=datetime.now(timezone.utc).isoformat(),checkout=str(ROOT),commit=git(ROOT,'rev-parse','HEAD').strip(),BUILD_ID=build['BUILD_ID'],sourceFilesVerified=len(build['files']),preservedAssets=len(assets)-5,newPortraits=5,served=served,pages=pages,protected=protected,physicalUserAcceptance=False,normalWindowsShortcutChanged=False,acneManifest=acne)
result['launcherFiles']=[dict(path=p,sha256=digest(ROOT/p)) for p in ['Start-Health-Final.ps1','Stop-Health-Final.ps1','scripts/health-final-api.py','scripts/build_health_final.py']]
result['dependencyLockSHA256']=digest(ROOT/'package-lock.json')
result['ownership']=ownership
result['previousEvidenceUnchanged']=True
result['sharedOrderUnchanged']=True
result['buildReceiptSHA256']=digest(OUT/'build-receipt.json')
result['workingTreeStatus']=git(ROOT,'status','--porcelain=v1')
temp=OUT/'delivery.tmp';temp.write_text(json.dumps(result,indent=2),'utf8');temp.replace(OUT/'delivery.json')
print(json.dumps(dict(BUILD_ID=result['BUILD_ID'],sourceFiles=len(build['files']),servedFiles=len(served),protectedUnchanged=all(r['matchesStart'] for r in protected))))
