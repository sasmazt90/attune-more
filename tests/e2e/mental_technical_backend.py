"""Test-only provider/audio seams on the real API. Never used by delivery launcher.
No credentials, provider calls, personal text or raw audio are logged.
"""
import hashlib,json,os,sys,time
from pathlib import Path
from threading import Event,RLock
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'cdc-progress/mental-technical-closeout-20261017'
os.environ.update(ATTUNE_LOAD_LOCAL_ENV='0',ATTUNE_TRUSTED_ORIGINS='http://127.0.0.1:3307',ATTUNE_DATA_DIR=str(OUT/'fixture-backend-data'),OPENAI_API_KEY='noncredential-test-fixture')
sys.path.insert(0,str(ROOT/'services/core-api'))
import main,mental_provider
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
MODE={'reply':'normal','summary':'normal','speech':'normal'};release=Event();lock=RLock();events=[]
def log(kind,**values):
 with lock:
  events.append(dict(kind=kind,**values));p=OUT/'fixture-ledger.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(dict(evidence='controlled provider seam, real backend routes',realProviderCalls=0,events=events),indent=2),'utf8');t.replace(p)
def hashes(messages):return [dict(role=m['role'],sha256=hashlib.sha256(m['content'].encode()).hexdigest()) for m in messages]
def forbidden(*a,**k):raise AssertionError('A live provider is forbidden in fixture server')
mental_provider.get_openai_client=forbidden
class Provider:
 def get_provider_name(self):return 'CONTROLLED_PROVIDER_SEAM'
 def is_live_llm(self):return False
 def generate_reply(self,user_message,is_driving,history,driver_name=''):
  log('converse',history=hashes(history),userSHA256=hashlib.sha256(user_message.encode()).hexdigest())
  mode=MODE['reply']
  if mode=='delay':release.wait(8)
  if mode=='error':raise HTTPException(503,'PROVIDER_UNAVAILABLE')
  return dict(reply='Kontrollü teknik yanıt. Bu kayıtlı test yanıtıdır.',providerType='LOCAL_DEMO' if mode=='wrong-provider' else 'LIVE_OPENAI')
class Analyzer:
 def analyze_session(self,messages):
  log('summary',messages=hashes(messages))
  if MODE['summary']=='delay':release.wait(8)
  if MODE['summary']=='error':raise HTTPException(503,'PROVIDER_UNAVAILABLE')
  return dict(summaryText='Kişisel olmayan teknik kontrol görüşmesi tamamlandı.',themes=['teknik kontrol'],moodTrend=None,providerType='LIVE_OPENAI')
main.get_active_mental_provider=lambda:Provider();main.get_active_session_analyzer=lambda:Analyzer()
manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/guidance/manifest.json').read_text('utf8'));entry=manifest['entries']['mental-complete'];audio=ROOT/'apps/vehicle-app/public'/entry['url'].lstrip('/')
assert (entry['voice'],entry['rate'],entry['pitch'])==('tr-TR-EmelNeural','-10%','-10Hz')
raw=audio.read_bytes();assert hashlib.sha256(raw).hexdigest()==entry['sha256']
async def recorded_speech(text,moving):
 log('recorded-audio',sha256=entry['sha256'],bytes=len(raw))
 if MODE['speech']=='error':raise HTTPException(503,'CONTROLLED_AUDIO_FAILURE')
 async def chunks():
  for i in range(0,len(raw),16384):
   if not moving():yield raw[i:i+16384]
 return StreamingResponse(chunks(),media_type='audio/mpeg',headers={'X-TTS-Voice':entry['voice'],'X-TTS-Rate':entry['rate'],'X-TTS-Pitch':entry['pitch'],'X-TTS-Source':'recorded-Emel-fixture'})
main.edge_mental_speech=recorded_speech
@main.app.post('/__test__/mode')
def mode(payload:dict):
 MODE.update({k:v for k,v in payload.items() if k in MODE});release.clear()
 if payload.get('release'):release.set()
 return {'fixtureOnly':True,'mode':MODE}
@main.app.get('/__test__/ledger')
def ledger():return {'events':events,'realProviderCalls':0}
if __name__=='__main__':
 import uvicorn
 uvicorn.run(main.app,host='127.0.0.1',port=8307,access_log=False)
