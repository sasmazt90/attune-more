"""Reuse verified local assets; never write to another checkout or download."""
import hashlib,json,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'cdc-progress/hearing-technical-closeout-20261017'
BASE=ROOT.parent/'attune-cdc-health-ui-20261017'
OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'status.json').exists():raise RuntimeError('Existing evidence is preserved; setup is first-run only.')
def atomic(name,data):
    temp=OUT/(name+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');temp.replace(OUT/name)
assets=json.loads((ROOT.parent/'cdc-progress/health-ui-consent-audio-followup-20261017/local-assets.json').read_text('utf-8-sig'))
for row in assets:
    source=BASE/row['path'];target=ROOT/row['path']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Source asset drift: '+row['path'])
    if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Target asset drift: '+row['path'])
shutil.copytree(BASE/'.runtime/edge-tts',ROOT/'.runtime/edge-tts',dirs_exist_ok=True)
atomic('local-assets.json',assets)
protected=[]
for name in ['attune-cdc-health-ui-20261017','attune-live-test','attune-cdc-acne-v5-integration','attune-cdc-vision-technical-20261017','attune-cdc-mental-technical-20261017','attune-antigravity-skin','attune-claude-acne-audit']:
    p=ROOT.parent/name
    protected.append(dict(checkout=name,sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip(),status=subprocess.check_output(['git','status','--porcelain=v1'],cwd=p,text=True)))
atomic('protected-start.json',protected)
atomic('status.json',dict(time=datetime.now(timezone.utc).isoformat(),stage='baseline-reproduction',checkout=str(ROOT),branch='research/hearing-technical-closeout-20261017',startCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),currentCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),completed=['separate worktree from current clean combined HEAD','verified unchanged local assets','historic successful evidence reviewed'],remaining=['reproduce failures','targeted corrections','PCM and lifecycle checks','one full tone and DIN session','typecheck/build/source-chain','report/local commit'],blocker=None,BUILD_ID=None,bankIdentities=[r for r in assets if 'hearing' in r['path']],physicalHeadphoneAcceptance=False))
for old,new in [('Start-Health-UI.ps1','Start-Hearing-Technical.ps1'),('Stop-Health-UI.ps1','Stop-Hearing-Technical.ps1'),('scripts/build_health_ui.py','scripts/build_hearing_closeout.py')]:
    content=(ROOT/old).read_text('utf8').replace('health-ui-consent-audio-followup-20261017','hearing-technical-closeout-20261017').replace('3308','3309').replace('8308','8309').replace('health-ui-api.py','hearing-closeout-api.py').replace('CDC-health-ui-build','CDC-hearing-build')
    (ROOT/new).write_text(content,'utf8')
print('Local assets verified:',len(assets))
