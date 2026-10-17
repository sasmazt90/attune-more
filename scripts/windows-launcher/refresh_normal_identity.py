"""Refresh only the authorized launcher gate/receipt, retaining the owned runtime.
Frontend/backend and their user stores are not restarted or replaced. Original
rollback backups remain untouched; the prior gate and metadata get a new backup.
"""
import json,runpy,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT.parent/'cdc-progress/health-normal-launcher-20261017'
HOME=Path(r'C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG\.launcher')
def atomic(path,value):
 temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2),'utf8');temporary.replace(path)
def main():
 module=runpy.run_path(str(ROOT/'scripts/windows-launcher/start_togg.pyw'))
 globals=module['process_matches'].__globals__;globals['PROFILE']=HOME/'chrome-profile'
 state=json.loads((HOME/'session.json').read_text('utf8'))
 descriptor=json.loads((HOME/'deployment.json').read_text('utf8'))
 assert state['status']=='running' and state['workspace']==str(ROOT) and state['profile']==str(HOME/'chrome-profile') and state['url']==module['URL']
 assert state['sourceCommit']==descriptor['sourceCommit'] and state['BUILD_ID']==descriptor['BUILD_ID']
 assert len(state['processes'])==4 and {r['role'] for r in state['processes']}=={'launcher','backend','frontend','browser'}
 assert all(module['process_matches'](row) for row in state['processes']),'No ownership uncertainty is permitted'
 for row in descriptor['files']:assert module['sha256'](ROOT/row['path'])==row['sha256'],'Build/model/asset changed'
 for row in descriptor['launcherFiles']:assert module['sha256'](HOME/row['name'])==row['sha256'],'Prior deployment changed'
 backup=OUT/'backup-before-CWD-fix';assert not backup.exists(),'Never overwrite a rollback point'
 backup.mkdir()
 for name in ['start_togg.pyw','backend_host.py','deployment.json','session.json']:shutil.copyfile(HOME/name,backup/name)
 for name in ['report.md','status.json','deployment-receipt.json']:
  if (OUT/name).exists():shutil.copyfile(OUT/name,backup/name)
 source=ROOT/'scripts/windows-launcher/start_togg.pyw';temp=HOME/'start_togg.install.tmp'
 shutil.copyfile(source,temp);temp.replace(HOME/'start_togg.pyw')
 commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
 original=state['sourceCommit']
 descriptor['sourceCommit']=commit
 descriptor['launcherFiles']=[dict(name=name,sha256=module['sha256'](HOME/name)) for name in ['start_togg.pyw','backend_host.py']]
 atomic(HOME/'deployment.json',descriptor)
 state['runtimeOriginallyStartedFromCommit']=original;state['sourceCommit']=commit
 # The active supervisor/API source is unchanged by this gate-only fix. The
 # next .lnk invocation reads the updated gate; API/UI PIDs and startup remain.
 atomic(HOME/'session.json',state)
 receipt=json.loads((OUT/'deployment-receipt.json').read_text('utf8'))
 receipt.update(sourceCommit=commit,deploymentSHA256=module['sha256'](HOME/'deployment.json'),changedFiles=[dict(path=str(HOME/name),sha256=module['sha256'](HOME/name)) for name in ['start_togg.pyw','backend_host.py','deployment.json']],identityRule='role-specific-browser-v2',runtimeRetained=True,runtimeOriginallyStartedFromCommit=original,updatedAtUTC=datetime.now(timezone.utc).isoformat())
 assert module['sha256'](HOME.parent/'TOGG Başlat.lnk')==receipt['shortcutSHA256']
 atomic(OUT/'deployment-receipt.json',receipt)
 print(json.dumps(dict(sourceCommit=commit,BUILD_ID=descriptor['BUILD_ID'],runtimeRetained=True,backendPID=state['backend_pid'],frontendPID=state['frontend_pid'],sourceAssetHashesUnchanged=True)))
if __name__=='__main__':main()
