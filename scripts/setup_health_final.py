"""Initialize this isolated delivery using verified existing local assets only."""
import hashlib,json,os,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent/'attune-cdc-dental-technical-20261017';OUT=ROOT.parent/'cdc-progress/health-final-technical-closeout-20261017'
OUT.mkdir(parents=True,exist_ok=True)
git=lambda p,*a:subprocess.check_output(['git','-C',str(p),*a],text=True)
assert git(BASE,'rev-parse','HEAD').strip()=='09d3cd159c1c614f27cb9911e975b7b1eb0d52d9' and not git(BASE,'status','--porcelain=v1')
protected=[]
for name in ['attune-cdc-dental-technical-20261017','attune-cdc-hearing-technical-20261017','attune-cdc-health-ui-20261017','attune-live-test','attune-cdc-acne-v5-integration','attune-cdc-vision-technical-20261017','attune-cdc-mental-technical-20261017','attune-antigravity-skin','attune-claude-acne-audit']:
 p=ROOT.parent/name;protected.append(dict(checkout=name,sha=git(p,'rev-parse','HEAD').strip(),status=git(p,'status','--porcelain=v1')))
assert not (OUT/'protected-start.json').exists(),'Already initialized; preserve original snapshot'
(OUT/'protected-start.json').write_text(json.dumps(protected,indent=2),'utf8')
assets=json.loads((ROOT.parent/'cdc-progress/dental-technical-closeout-20261017/local-assets.json').read_text('utf8'))
for row in assets:
 source=BASE/row['path'];target=ROOT/row['path'];assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
 if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
 assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']
(OUT/'preserved-assets.json').write_text(json.dumps(assets,indent=2),'utf8')
shutil.copytree(BASE/'.runtime/edge-tts',ROOT/'.runtime/edge-tts',dirs_exist_ok=True)
for target,source in [(ROOT/'node_modules',BASE/'node_modules'),(ROOT/'apps/vehicle-app/node_modules',BASE/'apps/vehicle-app/node_modules')]:
 if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);subprocess.run(['powershell','-NoProfile','-Command',f"New-Item -ItemType Junction -Path '{target}' -Target '{source}' | Out-Null"],check=True)
value=dict(time=datetime.now(timezone.utc).isoformat(),stage='baseline-and-portraits',checkout=str(ROOT),branch=git(ROOT,'branch','--show-current').strip(),startCommit=git(BASE,'rev-parse','HEAD').strip(),currentCommit=git(ROOT,'rev-parse','HEAD').strip(),completed=['verified latest clean combined HEAD','separate worktree','93 original assets verified and reused','protected checkout snapshots'],remaining=['unified five-module entry layout and portraits','bounded common lifecycle/privacy/history/referral checks','current dependency audit','typecheck/build/served identities','local commit and report'],blocker=None,BUILD_ID=None,physicalUserAcceptance=False)
t=OUT/'status.tmp';t.write_text(json.dumps(value,indent=2),'utf8');t.replace(OUT/'status.json')
print(json.dumps(dict(assets=len(assets),protected=len(protected),checkout=str(ROOT))))
