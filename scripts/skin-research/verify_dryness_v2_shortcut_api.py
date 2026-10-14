"""Cold/warm full API through the actual normal shortcut backend; no records."""
import json,time,urllib.request,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dryness-integration-v2-20261014';LAUNCH=Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/.launcher')
with HeavyJobLease('CDC-normal-shortcut-cold-warm-API',peak_mib=150,minimum_available_mib=650) as lease:
 import psutil
 state=json.loads((LAUNCH/'session.json').read_text('utf8'));assert state['status']=='running' and state['verification'] is False
 backend=psutil.Process(state['backend_pid']);assert Path(backend.cwd()).resolve()==ROOT
 payload=json.loads((ROOT/'audit-results/material-closeout-20261013/new-camera-normal-payload.json').read_text('utf8'));payload['hostedProcessingConsent']=False;data=json.dumps(payload).encode();rows=[]
 for phase in ['cold','warm']:
  lease.check();before=backend.memory_info().rss;t=time.monotonic();request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',data,{'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(request,timeout=48) as response:status=response.status;actual=json.loads(response.read())
  except urllib.error.HTTPError as error:status=error.code;actual=json.loads(error.read())
  elapsed=time.monotonic()-t;row=dict(phase=phase,status=status,seconds=elapsed,backendRSSBeforeMiB=before/2**20,backendRSSAfterMiB=backend.memory_info().rss/2**20,backendPID=backend.pid,backendStarted=backend.create_time(),firstColdIncludesDryEncoderLoad=phase=='cold',persistentPhotoCache=False);rows.append(row);print(json.dumps(row),flush=True)
  (OUT/('normal-shortcut-'+phase+'-result.json')).write_text(json.dumps(actual),'utf8')
  (OUT/'normal-shortcut-api.json').write_text(json.dumps(dict(rows=rows,normalShortcut=True,userRecordsWritten=False,sourcePayloadSHA256=hashlib.sha256(data).hexdigest()),indent=2),'utf8')
  assert status==200 and elapsed<45,(status,actual)
  assert actual['drynessRuntime']['headSHA256']=='7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1'
  if phase=='cold':first=actual
  else:assert actual['maps']==first['maps'] and actual['measurements']==first['measurements']
