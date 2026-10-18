"""New final CLI: real gates and success/failure archives, keyless fixtures only."""
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('new_final',ROOT/'scripts/final-provider-acceptance.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
before=runner.historical_hashes();rows=[]
env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')};env.update(ATTUNE_LOAD_LOCAL_ENV='0',OPENAI_API_KEY='',NEXT_TELEMETRY_DISABLED='1')
for mode in ['success','failure']:
 run_id=f'prep-guided-{mode}-{time.time_ns()}'
 result=subprocess.run([sys.executable,str(ROOT/'scripts/final-provider-acceptance.py'),'--run-id',run_id,'--fixture',mode],cwd=ROOT,env=env)
 assert result.returncode==0,mode
 out=ROOT/'audit-results/live-provider'/run_id
 ui=json.loads((out/'ui-proof.json').read_text());back=json.loads((out/'egress-proof.json').read_text());cleanup=json.loads((out/'cleanup-proof.json').read_text())
 assert not ui['liveAcceptance'] and back['realHTTPDispatchCalls']==0 and set(back['sdkMaxRetries'])=={0}
 assert cleanup['ownedProcessesExited'] and cleanup['temporaryStorageRemoved'] and cleanup['historicalPairedEvidenceUnchanged']
 assert ui['captureAttempts']==0 and 'productionTiming' in ui and 'transferEvents' in ui
 if mode=='success':
  assert ui['status']=='PASS' and back['counts']=={'conversation':3,'tts':3,'summary':1} and ui['recordsObserved']==1
  for turn in (1,2,3):
   assert all(any(e['turn']==turn and e['stage']==stage for e in ui['productionTiming']) for stage in ['send','chat-response','tts-request','tts-headers','chunk','body-end','playing','ended','cleanup'])
 else:
  assert ui['status']=='EXPECTED_FAILURE_PREPARATION_PASS' and back['originalSendCalls']==1 and back['closed'] and ui['recordsObserved']==0
  assert ui['sendStarts'] and ui['productionTiming'] and ui['transferEvents']==[]
 rows.append({'mode':mode,'runId':run_id,'status':'PASS','realProviderDispatches':0})
assert before==runner.historical_hashes()
(ROOT/'audit-results/final-provider-preparation.json').write_text(json.dumps({'status':'PASS','rows':rows,'previousPairedEvidenceUnchanged':True,'liveAcceptance':False},indent=2),encoding='utf-8')
print('PASS: new final CLI success/failure clocks and cleanup; zero provider dispatch')
