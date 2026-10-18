"""Bounded existing integration only: <=2 conversation, <=1 summary, <=1 Edge check.
This instrumentation is not imported by the product launcher. No text/key logging.
"""
import hashlib,importlib.util,json,sys,time
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'cdc-progress/mental-technical-closeout-20261017';LEDGER=OUT/'live-ledger.json';lock=RLock()
spec=importlib.util.spec_from_file_location('launcher',ROOT/'scripts/mental-technical-api.py');launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher);launcher.load_existing_configuration()
import main,mental_provider
from fastapi import HTTPException
from fastapi.responses import JSONResponse
state=json.loads(LEDGER.read_text('utf8')) if LEDGER.exists() else dict(conversation=0,summary=0,tts=0,failed=False,events=[],maxRetries=0,maximumConversation=2,maximumSummary=1,maximumTTS=1)
def save():
 t=LEDGER.with_suffix('.tmp');t.write_text(json.dumps(state,indent=2),'utf8');t.replace(LEDGER)
real_client=mental_provider.get_openai_client
def bounded_client(*args):
 client=real_client(*args)
 def create(**kwargs):
  kind='summary' if 'response_format' in kwargs else 'conversation'
  with lock:
   if state['failed'] or state[kind]>=(1 if kind=='summary' else 2):raise HTTPException(503,'BOUNDED_EVIDENCE_LIMIT')
   state[kind]+=1;event=dict(kind=kind,model=kwargs['model'],dispatched=True,messages=[dict(role=m['role'],sha256=hashlib.sha256(m['content'].encode()).hexdigest()) for m in kwargs['messages']]);state['events'].append(event);save()
  start=time.monotonic()
  try:
   response=client.chat.completions.create(**kwargs)
   with lock:event.update(status='SUCCESS',seconds=round(time.monotonic()-start,3),requestId=getattr(response,'_request_id',None),replySHA256=hashlib.sha256(response.choices[0].message.content.encode()).hexdigest(),usage=response.usage.model_dump() if response.usage else None);save()
   return response
  except Exception:
   with lock:state['failed']=True;event.update(status='FAILED',seconds=round(time.monotonic()-start,3));save()
   raise
 return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
mental_provider.get_openai_client=bounded_client
@main.app.middleware('http')
async def bounded_speech(request,call_next):
 if request.url.path=='/api/mental/speech' and request.method=='POST':
  with lock:
   if state['tts']>=1:return JSONResponse(status_code=503,content={'detail':'BOUNDED_EVIDENCE_LIMIT'})
   state['tts']+=1;save()
 return await call_next(request)
if __name__=='__main__':
 import uvicorn
 uvicorn.run(main.app,host='127.0.0.1',port=8307,access_log=False)
