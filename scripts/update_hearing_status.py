import json,sys,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/hearing-technical-closeout-20261017'
p=OUT/'status.json';value=json.loads(p.read_text('utf8'))
value.update(time=datetime.now(timezone.utc).isoformat(),stage=sys.argv[1],currentCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),physicalHeadphoneAcceptance=False)
if len(sys.argv)>2:value['completed'].append(sys.argv[2])
if (OUT/'build-receipt.json').exists():value['BUILD_ID']=json.loads((OUT/'build-receipt.json').read_text('utf8'))['BUILD_ID']
t=p.with_suffix('.tmp');t.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8');t.replace(p)
print(value['stage'])
