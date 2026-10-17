"""Reversible install for the explicitly authorized existing normal shortcut.
No profile/data/credential copy. The .lnk itself remains byte-identical.
"""
import hashlib,json,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT.parent/'cdc-progress/health-normal-launcher-20261017'
ORIGINAL=ROOT.parent/'cdc-progress/health-approved-assets-menu-20261017'
HOME=Path(r'C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG\.launcher')
LINK=HOME.parent/'TOGG Başlat.lnk'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for b in iter(lambda:stream.read(65536),b''):h.update(b)
 return h.hexdigest()
def atomic(path,value):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2),'utf8');temp.replace(path)
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 BACKUP=OUT/'backup'
 assert not BACKUP.exists(),'Never overwrite the original rollback backup'
 BACKUP.mkdir()
 names=['start_togg.pyw','backend_host.py','session.json','last-start.json']
 before=[]
 for name in names:
  source=HOME/name
  if source.exists():shutil.copyfile(source,BACKUP/name);before.append(dict(path=str(source),backup=str(BACKUP/name),sha256=digest(source)))
 shutil.copyfile(LINK,BACKUP/LINK.name)
 before.append(dict(path=str(LINK),backup=str(BACKUP/LINK.name),sha256=digest(LINK)))
 data=[dict(nameHash=hashlib.sha256(p.name.encode()).hexdigest(),sha256=digest(p),bytes=p.stat().st_size) for p in sorted((HOME/'data').glob('*')) if p.is_file()]
 atomic(OUT/'before.json',dict(at=datetime.now(timezone.utc).isoformat(),files=before,origin='http://127.0.0.1:3000',profile=str(HOME/'chrome-profile'),dataDirectory=str(HOME/'data'),dataFingerprints=data))
 build=json.loads((ORIGINAL/'build-receipt.json').read_text('utf8'))
 assets=json.loads((ORIGINAL/'local-assets.json').read_text('utf8'))
 changed='services/core-api/models/skin-type-hosted.json'
 files={row['path']:dict(path=row['path'],sha256=row['sha256']) for row in build['files']+assets}
 for name,row in files.items():
  if Path(name).as_posix().replace('\\','/')==changed:row['sha256']=digest(ROOT/name)
  assert digest(ROOT/name)==row['sha256'],name
 for name in ['start_togg.pyw','backend_host.py']:
  source=ROOT/'scripts/windows-launcher'/name;target=HOME/name
  temp=HOME/(name+'.install.tmp');shutil.copyfile(source,temp);temp.replace(target)
 descriptor=dict(sourceCommit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),checkout=str(ROOT),BUILD_ID=build['BUILD_ID'],frontendOrigin='http://127.0.0.1:3000',apiPort=8311,files=list(files.values()),launcherFiles=[dict(name=n,sha256=digest(HOME/n)) for n in ['start_togg.pyw','backend_host.py']])
 atomic(HOME/'deployment.json',descriptor)
 assert digest(LINK)==before[-1]['sha256']
 atomic(OUT/'deployment-receipt.json',dict(sourceCommit=descriptor['sourceCommit'],BUILD_ID=descriptor['BUILD_ID'],shortcutSHA256=digest(LINK),deploymentSHA256=digest(HOME/'deployment.json'),changedFiles=[dict(path=str(HOME/n),sha256=digest(HOME/n)) for n in ['start_togg.pyw','backend_host.py','deployment.json']],filesVerified=len(files),userDataCopied=False,shortcutModified=False))
 print(json.dumps(dict(filesVerified=len(files),BUILD_ID=descriptor['BUILD_ID'],shortcutModified=False,userDataCopied=False)))
if __name__=='__main__':main()
