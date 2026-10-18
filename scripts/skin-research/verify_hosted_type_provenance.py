"""Local credential isolation and immutable AG evidence; no hosted photo calls."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[2];AG=ROOT.parent/'attune-antigravity-skin'
OUT=ROOT/'audit-results/skin-type-integration-20261012';OUT.mkdir(exist_ok=True,parents=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
from hosted_skin_credentials import load_existing_backend_key
assert not any(os.environ.get(n) for n in ('ATTUNE_ROBOFLOW_API_KEY','ROBOFLOW_API_KEY')),'UTILITY_ENV_UNEXPECTED'
os.environ['ATTUNE_LOAD_LOCAL_ENV']='1';assert load_existing_backend_key()
key=(os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ['ROBOFLOW_API_KEY']).encode()
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
paths=[ROOT/f for f in files if (ROOT/f).is_file()]+[p for p in (ROOT/'apps/vehicle-app/.next').rglob('*') if p.is_file() and 'cache' not in p.parts]
assert all(key not in p.read_bytes() for p in paths),'CREDENTIAL_LEAK_DETECTED'
ignored=subprocess.run(['git','check-ignore','.env.local'],cwd=AG,capture_output=True,text=True)
assert ignored.returncode==0
session=json.loads(Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/.launcher/session.json').read_text());assert session['status']=='running' and not session['verification']
process_env={}
for name in ('backend','frontend'):
 env=psutil.Process(session[name+'_pid']).environ()
 process_env[name]=dict(credentialPresent=any(bool(env.get(n)) for n in ('ATTUNE_ROBOFLOW_API_KEY','ROBOFLOW_API_KEY')),localEnvOptIn=env.get('ATTUNE_LOAD_LOCAL_ENV'))
assert not process_env['frontend']['credentialPresent']
assert process_env['backend']['localEnvOptIn']=='1'
# psutil on Windows may see only the initial process environment. Keep this
# observation distinct from the actual backend loader contract; never infer.
evidence={}
for name in ('skin-type-models-comparison.json','skin-type-crop-impact.json','skin-type-access-probe.json','skin-type-sdk-weights-check.json'):
 path=AG/'audit-results'/name
 evidence[name]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),sourceCommit='8b9db4649148d421c4495c657e76273a6f1cd006')
 # Keep the already recorded non-secret responses and comparison evidence.
 assert key not in path.read_bytes();(OUT/name).write_bytes(path.read_bytes())
result=dict(status='PASS',credentialCopied=False,credentialPrinted=False,credentialGitIgnored=True,keyLeakMatches=0,filesScanned=len(paths),normalProcesses=process_env,backendLoaderSourceSHA256=hashlib.sha256((ROOT/'services/core-api/hosted_skin_credentials.py').read_bytes()).hexdigest(),agEvidence=evidence,newLiveHostedPhotoRequests=0,localWeightsAvailable=False,sdkDownloadFailureCause='not differentiated')
(OUT/'provenance.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(result,indent=2))
