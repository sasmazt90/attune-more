"""Bounded local verification with owned processes and disposable health storage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--postmeeting-paid',action='store_true');parser.add_argument('--provider-admission',action='store_true');parser.add_argument('--live-run-id');parser.add_argument('--harness-fixture',choices=['success','failure']);parser.add_argument('--contract-provider',action='store_true');parser.add_argument('scripts',nargs='+');args=parser.parse_args()
if args.postmeeting_paid:
    assert args.live and not args.provider_admission and not args.contract_provider and not args.harness_fixture
    assert args.scripts==['tests/e2e/postmeeting_paid_ui.py'], 'Only the latest authorized two-request scenario is admitted'
assert not args.contract_provider or (not args.live and not args.provider_admission), 'Synthetic UI fixture cannot load a key or claim live acceptance'
if args.harness_fixture:
    assert not args.live and args.provider_admission and args.live_run_id and args.live_run_id.startswith('prep-')
if args.provider_admission:
    assert (args.live or args.harness_fixture) and args.scripts==['tests/e2e/live_provider_voice_followup.py --approved-additional-text-run'+(' --run-id '+args.live_run_id if args.live_run_id else '')+(' --fixture '+args.harness_fixture if args.harness_fixture else '')], 'Admission server only supports the explicitly authorized bounded text/TTS run'
root=Path(__file__).resolve().parents[1];out=root/'audit-results';out.mkdir(exist_ok=True)
for port in [3000,8000]:
    with socket.socket() as sock:
        assert sock.connect_ex(('127.0.0.1',port))!=0,'Port occupied; refusing to adopt or stop another application'
env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}
runtime=root/'.runtime/security-20261008'
assert (runtime/'fastapi').is_dir(), 'Install the isolated security runtime before verification'
env['PYTHONPATH']=str(runtime)+os.pathsep+env.get('PYTHONPATH','')
env.update(OPENAI_API_KEY='',ATTUNE_LOAD_LOCAL_ENV='1' if args.live else '0',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
if args.harness_fixture:
    env['OPENAI_API_KEY']='attune-keyless-fixture-not-a-credential'
processes=[];logs=[];results=[]
data=None
try:
    with tempfile.TemporaryDirectory(prefix='attune-followup-') as data:
        env['ATTUNE_DATA_DIR']=data
        try:
            backend_command = [sys.executable, str(root/'tests/e2e/live_provider_backend.py'), '--approved-additional-text-run'] if args.provider_admission else [sys.executable,'-m','uvicorn','main:app','--app-dir',str(root/'services/core-api'),'--host','127.0.0.1','--port','8000']
            if args.contract_provider: backend_command = [sys.executable, str(root/'tests/e2e/ui_contract_backend.py')]
            if args.postmeeting_paid: backend_command = [sys.executable, str(root/'tests/e2e/postmeeting_paid_backend.py'), '--authorized-current-section10']
            if args.provider_admission and args.live_run_id:backend_command += ['--run-id',args.live_run_id]
            if args.harness_fixture:backend_command += ['--fixture',args.harness_fixture]
            for name,command in [('backend',backend_command),('frontend',[shutil.which('node'),str(root/'node_modules/next/dist/bin/next'),'start',str(root/'apps/vehicle-app'),'--hostname','127.0.0.1','-p','3000'])]:
                service_env={**env,'ATTUNE_LOAD_LOCAL_ENV':'0','OPENAI_API_KEY':''} if name=='frontend' else env
                log=(out/(name+'-followup.log')).open('w',encoding='utf-8');logs.append(log)
                processes.append(subprocess.Popen(command,cwd=root,env=service_env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
            for url in ['http://127.0.0.1:8000/api/health','http://127.0.0.1:3000']:
                deadline=time.monotonic()+60
                while True:
                    try:
                        with urllib.request.urlopen(url,timeout=2) as response:assert response.status==200
                        break
                    except Exception:
                        assert time.monotonic()<deadline,'Service startup failed'
                        time.sleep(.25)
            for script in args.scripts:
                name=Path(script.split()[0]).stem+('-'+hashlib.sha256(script.encode()).hexdigest()[:8] if len(script.split())>1 else '')
                with (out/(name+'-followup.log')).open('w',encoding='utf-8') as log:
                    result=subprocess.run([sys.executable,*script.split()],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
                results.append({'script':script,'exitCode':result.returncode,'generationFixture':bool(args.contract_provider),'liveAcceptance':False if args.contract_provider or not args.live else None});print(json.dumps(results[-1]),flush=True)
        finally:
            for process in reversed(processes):
                if process.poll() is None:process.terminate()
                process.wait(timeout=15)
            for log in logs:log.close()
except Exception as error:
    results.append({'script':'owned-service-orchestration','exitCode':1,'failureCategory':type(error).__name__})
finally:
    cleanup={'runId':args.live_run_id,'ownedProcessesExited':all(p.poll() is not None for p in processes),'temporaryStorageRemoved':data is None or not Path(data).exists()}
    if args.provider_admission:
        (out/'live-provider'/(args.live_run_id or 'controlled-text')/'cleanup-proof.json').write_text(json.dumps(cleanup,indent=2),encoding='utf-8')
(out/('live-matrix.json' if args.live else 'local-matrix.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
raise SystemExit(1 if any(r['exitCode'] for r in results) else 0)
