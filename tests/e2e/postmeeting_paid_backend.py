"""Current pasted request section 10: at most two nonpersonal text calls.
Real production provider and existing project key; no key output or TTS migration.
Run only after local checks. Independent, consumed admission marker forbids reruns.
"""
import json,os,sys,time
from pathlib import Path
import uvicorn
from openai.resources.chat.completions import Completions

assert '--authorized-current-section10' in sys.argv
assert os.getenv('ATTUNE_LOAD_LOCAL_ENV')=='1'
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/postmeeting/paid';OUT.mkdir(parents=True,exist_ok=True)
MARKER=OUT/'consumed.json'
assert not MARKER.exists(),'Finite acceptance already consumed; no automatic rerun'
TEXT='Bu kişisel olmayan bir kabul testidir. Kısa bir dinlenme molası hakkında iki sakin cümle söyler misiniz?'
TOKEN='postmeeting-section10-nonpersonal-two-text-calls'
events=[];failed=False;reply=None
def save():
    (OUT/'ledger.json').write_text(json.dumps({'authorization':'current pasted request section 10 overrides earlier no-paid restriction','model':'gpt-4o-mini','maximumRequests':2,'maxRetries':0,'inputTokenBoundPerRequest':20000,'outputTokenBounds':[250,400],'estimatedScenarioMaximumUSD':.00639,'reportedBillingUSD':None,'actualRequests':len(events),'failed':failed,'events':events},indent=2),'utf8')
original=Completions.create
def bounded(self,*args,**kw):
    global failed,reply
    assert not failed and not args and len(events)<2
    assert self._client.max_retries==0 and kw['model']=='gpt-4o-mini'
    summary=kw.get('response_format')=={'type':'json_object'}
    assert summary==(len(events)==1)
    assert kw['max_tokens']<= (400 if summary else 250)
    messages=kw['messages'];assert all(isinstance(m['content'],str) for m in messages)
    byte_bound=sum(len(m['content'].encode('utf8'))+200 for m in messages)
    assert byte_bound<=20000
    if not summary:assert [m['content'] for m in messages if m['role']=='user']==[TEXT]
    else:assert TEXT in messages[-1]['content'] and reply and reply in messages[-1]['content']
    if not events:
        with MARKER.open('x',encoding='utf8') as f:json.dump({'authorization':'Pasted text section 10','maxCalls':2,'retry':0},f)
    event={'kind':'summary' if summary else 'conversation','requestDispatched':True,'inputByteTokenBound':byte_bound};events.append(event);save();start=time.monotonic()
    try:
        result=original(self,**kw)
        event.update(seconds=round(time.monotonic()-start,3),requestId=result._request_id,usage=result.usage.model_dump(),status='SUCCESS')
        event['estimatedTokenCostUSD']=(result.usage.prompt_tokens*.15+result.usage.completion_tokens*.6)/1e6
        if not summary:reply=result.choices[0].message.content.strip()
        save();return result
    except Exception as error:
        failed=True;event.update(status='FAILED_NO_RETRY',category=type(error).__name__);save();raise
Completions.create=bounded
sys.path.insert(0,str(ROOT/'services/core-api'))
import main
from fastapi.responses import JSONResponse
@main.app.middleware('http')
async def finite_context(request,call_next):
    if request.url.path.startswith('/api/mental/') and request.headers.get('x-acceptance-context')!=TOKEN:
        return JSONResponse({'detail':'Acceptance context required'},403)
    return await call_next(request)
save()
uvicorn.run(main.app,host='127.0.0.1',port=8000,log_level='warning')
