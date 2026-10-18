import argparse,json,re,subprocess,xml.etree.ElementTree as ET
parser=argparse.ArgumentParser();parser.add_argument("--run",type=int,required=True);parser.add_argument("--artifact",required=True);args=parser.parse_args()
from pathlib import Path
root=Path.cwd();out=root/'audit-results';run=args.run
meta=json.loads((out/f'ci-{run}-status.json').read_text(encoding='utf-8-sig'))
assert meta['status']=='completed'
sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert sha==meta['headSha']
artifact=Path(args.artifact)
def load(name):return json.loads((artifact/name).read_text(encoding='utf-8'))
def passed(name,n):
 d=load(name);assert len(d)==n and all(x['status']=='PASS' for x in d);return d
passed('broader/results.json',39);passed('focused-results.json',14);passed('media-lifecycle-regressions.json',5);passed('skin-timing/timings.json',8);passed('mental-followup/results.json',12)
reg=[x for f in (artifact/'backlog').glob('*.json') for x in json.loads(f.read_text())];assert len(reg)==23 and all(x['status']=='PASS' for x in reg)
sec=load('dependency-security.json')['results'];assert len(sec)==5 and all(x['status']=='PASS' for x in sec)
for name,n in [('unit.xml',165),('focused-safety.xml',54)]:
 s=next(ET.parse(artifact/name).getroot().iter('testsuite'));assert s.get('tests')==str(n) and all(s.get(x)=='0' for x in ['failures','errors','skipped'])
multi=load('skin-multi-angle/results.json');assert multi['status']=='PASS' and not multi['poseMock'] and not multi['reusedFrameForAngles'] and len(multi['captures'])==2
voice=load('native-three-turn/results.json');assert voice['status']=='PASS' and voice['provider']=='LOCAL_DEMO' and not voice['openAIKeyUsed']
stt=voice['events']['stt'];tts=voice['events']['tts'];spoken=[x for x in stt if x['type']=='result'];starts=[x['time'] for x in tts if x['type']=='start'];ends=[x['time'] for x in tts if x['type']=='end'];restarts=[x['time'] for x in stt if x['type']=='start']
assert len(spoken)==len(starts)==len(ends)==3 and len(set(x['transcript'] for x in spoken))==3
assert all(not any(a<t<b for a,b in zip(starts,ends)) for t in restarts)
resume=[round(restarts[i+1]-ends[i],1) for i in range(2)]
full=load('npm-audit.json')['metadata']['vulnerabilities'];prod=load('npm-audit-production.json')['metadata']['vulnerabilities'];assert full['total']==7 and full['high']==7 and prod['total']==0
job=meta['jobs'][0];failed=[s['name'] for s in job['steps'] if s['conclusion']=='failure'];assert failed==['Security and environment reports']
assert all(s['conclusion']=='success' for s in job['steps'] if 5<=s['number']<=25 and s['name']!='Security and environment reports')
uat=load('uat-20261003/after/results.json');assert len(uat['results'])==10 and all(x['status']=='PASS' for x in uat['results'])
truth=load('uat-truthfulness/results.json');assert truth['sourceHead']==sha and not truth['beforeObservationOnly'] and truth['physicalCaptureAttempts']==0
assert len(truth['results'])==3 and all(x['status']=='PASS' and x['captureAttempts']==0 and x['printCalls']==1 for x in truth['results']) and len(truth['screenshots'])==30
assert load('live-followup/skin.json')['reminderEditDedupErrorCancel'] is True
prep=load('live-harness-preparation.json');assert prep['status']=='PASS' and not prep['liveAcceptance'] and len(prep['entrypointsAndDualGates'])==2 and prep['sdkRetries']==0 and prep['previousLedgersUnchanged'] and prep['ownedPortsFree']
summary={'head':sha,'runId':run,'jobId':job['databaseId'],'overall':meta['conclusion'],'onlyFailedStep':failed,'matrix':{'broader':39,'focused':14,'mediaLifecycle':5,'browserRegressions':23,'timing':8,'unit':165,'unitSkipped':0,'safety':54,'dependency':5,'mentalLifecycle':12,'nativeVoiceTurns':3,'multiAngleCompletedScans':2},'fullAudit':full,'productionAudit':prod,'nativeResumeAfterTTSEndMs':resume,'nativeSTTTranscripts':[s['transcript'] for s in spoken]}
(out/f'ci-{run}-matrix-proof.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

negative=load('live-harness-fail-closed.json');assert len(negative)==3 and all(x['status']=='PASS' and x['providerRequests']==0 and x['forwardedBackendRequests']==0 for x in negative)
ordering=load('live-harness-order.json');assert ordering['status']=='PASS' and ordering['realOpenAIRequests']==0 and ordering['realOpenAITTSRequests']==0
summary['matrix'].update(liveAdmissionUnit=30,failClosedUI=3,keylessOrdering=1,newSDKPoolUnit=5,uatUX=10,truthfulnessUX=3,reminderCalendarDays=28)
(out/f'ci-{run}-matrix-proof.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
final=load('final-user-flow-20261003/after/results.json');assert final['sourceHead']==sha and len(final['results'])==7 and all(r['status']=='PASS' for r in final['results']);summary['matrix']['finalServiceDeletion']=7
(out/f'ci-{run}-matrix-proof.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

print(json.dumps(summary,ensure_ascii=False))
