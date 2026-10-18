"""Metadata-only local evidence. Never copies conversation text, keys or raw media."""
import hashlib,json,re,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/mental-technical-closeout-20261017';BROWSER=ROOT/'output/playwright/mental'
def read(p):return json.loads(p.read_text('utf-8-sig'))
def atomic(p,value):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8');t.replace(p)
def main():
 report=ROOT/'docs/mental-technical-closeout-20261017.md';text=report.read_text('utf8')
 features=[dict(id=i,name=n,status=s,evidence=e) for i,n,s,e in re.findall(r'^\| (F\d{3}) (.*?) \| (.*?) \| (.*?) \|$',text,re.M)]
 assert {f['id'] for f in features}=={f'F{i:03}' for i in range(89,107)} and len(features)==18
 suite=ET.parse(OUT/'focused-tests.xml').getroot().find('testsuite');assert suite.attrib['failures']==suite.attrib['errors']=='0'
 tests={(t.attrib['classname'],t.attrib['name']) for t in suite.findall('testcase')};assert len(tests)==68
 names=['pause-pending-before','pause-pending-after','conversation-proof','controls-proof','permissions-proof','live-proof']
 names+=['lifecycle-'+name for name in ('asr-errors','permission-start-cancel','provider-error','speech-error','summary-error','summary-cancel','summary-consent-revoke','microphone-revoke','drive-lock','route-cleanup','old-session-response')]
 browser={name:read(BROWSER/(name+'.json')) for name in names}
 for name in names:
  assert browser[name]['physicalUserAcceptance'] is False
 ledger=read(OUT/'live-ledger.json');assert (ledger['conversation'],ledger['summary'],ledger['tts'])==(2,1,1)
 assert len(ledger['events'])==3 and all(e['status']=='SUCCESS' for e in ledger['events'])
 first,second=ledger['events'][:2];assert second['messages'][-3]['sha256']==first['messages'][-1]['sha256'] and second['messages'][-2]['sha256']==first['replySHA256']
 tts=read(OUT/'live-tts-observation.json');assert tts['httpStatus']==503 and not tts['retryPerformed']
 assert browser['live-proof']['summary']['sameHistory'] and not browser['live-proof']['summary']['transcriptStored']
 before=browser['pause-pending-before'];after=browser['pause-pending-after'];assert before['finalPhase']=='error' and after['finalPhase']=='completed'
 files=[report,OUT/'focused-tests.xml',OUT/'baseline-tests.xml',OUT/'before-context.xml',OUT/'typecheck.log',OUT/'build.log',OUT/'build-receipt.json',OUT/'controller-build-receipt.json',OUT/'served-protection-receipt.json',OUT/'live-ledger.json',OUT/'live-tts-observation.json',OUT/'controller-fixture-ledger.json',OUT/'permissions-fixture-ledger.json']+[BROWSER/(name+'.json') for name in names]
 files+=[BROWSER/name for name in ('desktop-conversation.png','desktop-history.png','narrow-conversation.png','narrow-history.png','desktop-history-viewport.png','narrow-history-viewport.png')]
 value=dict(timeUTC=datetime.now(timezone.utc).isoformat(),sourceCommit=read(OUT/'start.json')['startCommit'],branch='research/mental-technical-closeout-20261017',BUILD_ID=read(OUT/'build-receipt.json')['BUILD_ID'],technicalStatus='CONTROLLED_COMPLETE_LIVE_TTS_BLOCKED',physicalUserAcceptance=False,uniqueFocusedTests=68,features=features,browser=browser,liveProvider=ledger,liveTTS=tts,served=read(OUT/'served-protection-receipt.json'),evidenceFiles=[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])
 atomic(ROOT/'docs/mental-technical-closeout-20261017.json',value);atomic(OUT/'evidence.json',value)
 temp=OUT/'report.tmp';temp.write_text(text,'utf8');temp.replace(OUT/'report.md')
 state=read(OUT/'status.json');state.update(timeUTC=value['timeUTC'],stage='local-commit-pending-live-tts-blocked',provider='LIVE_OPENAI (gpt-4o-mini)',voice='tr-TR-EmelNeural / -10% / -10Hz',remaining=['Local commit and clean-tree/protected-runtime receipt','Live Emel HTTP503 remains unresolved; physical acceptance only at end of all modules']);state['completed']+=['Same pending turn and speech resume verified; malformed context bounds verified','68 focused tests; standalone typecheck/current production build','Explicit pause/mute/farewell path verified on final build','38 served JS and exact existing Emel hashes; protected checkouts unchanged','Metadata-only report and F089-F106 table saved'];atomic(OUT/'status.json',state)
 print('COLLECTED',len(tests),'tests,',len(features),'features; real calls 2+1; live TTS 503 remains')
if __name__=='__main__':main()
