"""Three explicitly authorized nonpersonal calls; original production provider.
Existing secure server config only. No retries, credentials or personal messages.
"""
import json,os,sys,time
from pathlib import Path
import uvicorn
from openai.resources.chat.completions import Completions
assert '--authorized-current-section8' in sys.argv
assert os.getenv('ATTUNE_LOAD_LOCAL_ENV')=='1'
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/all-health-20261010/mental-live';OUT.mkdir(parents=True,exist_ok=True)
TEXTS=['Bu kişisel olmayan bir kabul testidir. Kısa bir dinlenme molası hakkında iki sakin cümle söyler misiniz?','Önceki dinlenme molası konusunu sürdürün; aynı öneriyi tekrar etmeden kısa bir Türkçe cümle ekleyin.']
TOKEN='all-health-section8-three-nonpersonal-calls'
previous=json.loads((OUT/'ledger.json').read_text()) if (OUT/'ledger.json').exists() else {}
events=previous.get('events',[]);failed=previous.get('failed',False);replies=[]
assert len(events)<3 and not failed,'Existing finite budget exhausted or provider failed'
def save():
 (OUT/'ledger.json').write_text(json.dumps(dict(authorization='Current request section 8',model='gpt-4o-mini',maximumRequests=3,maxRetries=0,actualRequests=len(events),failed=failed,events=events,estimatedTokenCostUSD=sum(e.get('estimatedTokenCostUSD',0) for e in events),reportedBillingUSD=None),indent=2),'utf8')
original=Completions.create
def bounded(self,*args,**kw):
 global failed
 assert not failed and not args and len(events)<3 and self._client.max_retries==0
 assert kw['model']=='gpt-4o-mini'
 summary=kw.get('response_format')=={'type':'json_object'}
 assert summary==(len(events)==2) and kw['max_tokens']<=(400 if summary else 250)
 messages=kw['messages'];assert all(isinstance(m['content'],str) for m in messages)
 byte_bound=sum(len(m['content'].encode('utf8'))+200 for m in messages);assert byte_bound<=20000
 if not summary:
  users=[m['content'] for m in messages if m['role']=='user'];assert users==TEXTS[:len(events)+1]
  if events and replies:assert replies[0] in [m['content'] for m in messages if m['role']=='assistant']
 else:assert TEXTS[-1] in messages[-1]['content'] and all(t in messages[-1]['content'] for t in replies)
 if not events:
  with (OUT/'consumed.json').open('x',encoding='utf8') as f:json.dump(dict(maxCalls=3,retries=0),f)
 event=dict(kind='summary' if summary else 'conversation',requestDispatched=True,inputByteTokenBound=byte_bound,priorContextVerified=len(events)==1);events.append(event);save();start=time.monotonic()
 try:
  result=original(self,**kw);event.update(seconds=round(time.monotonic()-start,3),requestId=result._request_id,usage=result.usage.model_dump(),status='SUCCESS')
  event['estimatedTokenCostUSD']=(result.usage.prompt_tokens*.15+result.usage.completion_tokens*.6)/1e6
  if not summary:replies.append(result.choices[0].message.content.strip())
  save();return result
 except Exception as error:
  failed=True;event.update(status='FAILED_NO_RETRY',category=type(error).__name__);save();raise
Completions.create=bounded
sys.path.insert(0,str(ROOT/'services/core-api'))
import main
from fastapi.responses import JSONResponse
@main.app.middleware('http')
async def finite_context(request,call_next):
 if request.url.path.startswith('/api/mental/') and request.headers.get('x-acceptance-context')!=TOKEN:return JSONResponse({'detail':'Acceptance context required'},403)
 return await call_next(request)
save();uvicorn.run(main.app,host='127.0.0.1',port=8010,log_level='warning')
