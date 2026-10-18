"""Execute checked-in CLI entrypoints and both gates; strictly keyless preparation."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'audit-results/live-provider'
def ledgers():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in OUT.glob('*/*.json') if not p.parent.name.startswith('prep-')}
before = ledgers()
results = []
env = {k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}
env.update(ATTUNE_LOAD_LOCAL_ENV='0',PYTHONUTF8='1')
for mode in ['success','failure']:
    identity = f'prep-{mode}-{time.time_ns()}'
    script = f'tests/e2e/live_provider_voice_followup.py --approved-additional-text-run --run-id {identity} --fixture {mode}'
    code = subprocess.call([sys.executable,str(ROOT/'scripts/run-followup-checks.py'),'--provider-admission',
        '--harness-fixture',mode,'--live-run-id',identity,script],cwd=ROOT,env=env)
    assert code == 0
    directory = OUT/identity
    def read(name):return json.loads((directory/name).read_text(encoding='utf-8'))
    ui, backend, marker, cleanup = [read(n+'.json') for n in ['ui-proof','egress-proof','run-consumed','cleanup-proof']]
    assert all(p['runId'] == identity for p in [ui,backend,marker,cleanup])
    assert backend['mode']==ui['mode']=='KEYLESS_FIXTURE_PREPARATION' and not ui['liveAcceptance']
    assert backend['transportFamily'] in ['httpx','httpx2'] and backend['blockedSocketConnections']==0
    assert backend['realHTTPDispatchCalls']==0 and backend['sdkMaxRetries'] and set(backend['sdkMaxRetries'])=={0}
    assert cleanup['ownedProcessesExited'] and cleanup['temporaryStorageRemoved']
    assert ui['localSavingExplicitUIToggle'] is True
    assert ui['physicalMicrophone']=='denied' and ui['captureAttempts']==0
    if mode=='success':
        expected=['conversation','tts']*3+['summary']
        assert ui['status']=='PASS' and backend['counts']==ui['browserAdmission']['counts']=={'conversation':3,'tts':3,'summary':1}
        assert backend['originalSendCalls']==backend['fixtureTransportCalls']==backend['httpResponses']==7
        assert [e['kind'] for e in backend['events']]==ui['admissionCompletedBeforeUI']==expected
        assert all(e['markerBeforeDispatch'] and e['admissionCompletedBeforeBackendReturn'] for e in backend['events'])
        assert ui['historyLengths']==[0,2,4] and ui['recordsObserved']==1 and ui['allThreePlaybacksEnded']
        assert len(list(directory.glob('synthetic-reply-*.mp3')))==3
    else:
        assert ui['status']=='EXPECTED_FAILURE_PREPARATION_PASS' and backend['closed'] and ui['browserAdmission']['closed']
        assert ui['secondBrowserAdmissionBlocked'] and ui['secondBackendProbeCompleted'] and ui['recordsObserved']==0
        assert backend['originalSendCalls']==backend['fixtureTransportCalls']==backend['httpResponses']==1
        assert backend['admissionAttempts']==2 and backend['counts']=={'conversation':1,'tts':0,'summary':0}
        assert backend['events'][0]['httpStatus']==503 and backend['events'][-1]['dispatchStarted'] is False
    for port in [3000,8000]:
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))!=0
    results.append({'mode':mode,'runId':identity,'status':'PASS','realProviderHTTPDispatches':0})
assert before==ledgers(), 'Previous authorization/consumption ledgers changed'
proof={'status':'PASS','mode':'KEYLESS_FIXTURE_PREPARATION','liveAcceptance':False,'entrypointsAndDualGates':results,
    'previousLedgersUnchanged':True,'previousLedgerHashes':before,'ownedPortsFree':True,'sdkRetries':0}
(ROOT/'audit-results/live-harness-preparation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof))
