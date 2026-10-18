"""One human-approved before/after experiment. No retry and no real capture.

Every phase has exclusive launch/dispatch markers. The final phase requires a
successful before phase. Original evidence is never overwritten. Instrumentation
observes real HTTP bytes and media events; it does not replace or delay output.
"""
import argparse, hashlib, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'audit-results/live-provider/paired-20261004'
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['before','after']);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
OUT=BASE/args.phase
if any((OUT/name).exists() for name in ('launch-consumed.json','run-consumed.json')):
    raise SystemExit('Consumed experiment is immutable: no preparation overwrite or retry')
OUT.mkdir(parents=True,exist_ok=True)

def replace_once(source, old, new):
    assert source.count(old)==1,old[:100]
    return source.replace(old,new)

# Reuse the existing strict synthetic-content admission, including exact history,
# provider destination, output-token/input-character budgets, voice and no retry.
backend=(ROOT/'tests/e2e/live_provider_backend.py').read_text(encoding='utf-8')
backend=replace_once(backend,"OUT = live_run_output(ROOT,args.run_id)",f"OUT = Path({str(OUT)!r})")
backend=replace_once(backend,"ROOT = Path(__file__).resolve().parents[2]",f"ROOT = Path({str(ROOT)!r})")
backend=replace_once(backend,"from live_provider_admission import LiveAdmission,live_run_output,claim_live_run",f"sys.path.insert(0, {str(ROOT/'tests/e2e')!r})\nfrom live_provider_admission import LiveAdmission,live_run_output,claim_live_run")
backend=replace_once(backend,"expected_model = os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts') if request.url.path.endswith('/speech') else os.getenv('OPENAI_MODEL', 'gpt-4o-mini')", "expected_model = 'gpt-4o-mini-tts' if request.url.path.endswith('/speech') else 'gpt-4o-mini'\n        if request.url.path.endswith('/speech') and len((data.get('input','')+data.get('instructions','')).encode('utf-8'))>2000:gate.reject('TTS_BYTE_BUDGET')\n        if request.url.path.endswith('/completions') and len(json.dumps(data.get('messages',[]),ensure_ascii=False).encode('utf-8'))>56000:gate.reject('CONTEXT_BYTE_BUDGET')")
if args.phase=='before':
    backend=replace_once(backend,"kind = gate.admit(request.url.path, data)","if data.get('response_format') == {'type':'json_object'}: gate.reject('NO_BASELINE_SUMMARY_AUTHORIZED')\n        kind = gate.admit(request.url.path, data)")
start=backend.index('        response.read()\n')
end=backend.index('        return response\n',start)
backend=backend[:start]+'''        event = {'kind':kind,'httpStatus':response.status_code,'headersMs':round((headers_ready-start)*1000,1),'requestId':response.headers.get('x-request-id'),'markerBeforeDispatch':CONSUMED.exists(),'chunks':[]}
        events.append(event)
        if kind == 'tts' and response.is_success:
            original_stream=response.stream
            class ObservedStream(httpx.SyncByteStream):
                def __iter__(self):
                    chunks=[]
                    try:
                        for chunk in original_stream:
                            event['chunks'].append({'atMs':round((time.monotonic()-start)*1000,1),'bytes':len(chunk)})
                            chunks.append(chunk)
                            save()
                            yield chunk
                        event['bodyCompleteMs']=round((time.monotonic()-start)*1000,1)
                        (OUT/f"synthetic-reply-{gate.counts['tts']}.mp3").write_bytes(b''.join(chunks))
                        gate.complete(kind,None,True)
                        save()
                    except BaseException:
                        gate.failed=True;event['streamFailed']=True;save();raise
                def close(self):
                    original_stream.close()
                    if gate.pending==kind:gate.failed=True;event['streamClosedBeforeComplete']=True;save()
            response.stream=ObservedStream()
        else:
            response.read()
            event['bodyCompleteMs']=round((time.monotonic()-start)*1000,1)
            reply=response.json()['choices'][0]['message']['content'] if kind=='conversation' and response.is_success else None
            gate.complete(kind,reply,response.is_success)
        save()
''' +backend[end:]

ui=(ROOT/'tests/e2e/live_provider_voice_followup.py').read_text(encoding='utf-8')
ui=replace_once(ui,'from live_provider_admission import LiveAdmission,TEXTS,forward_admitted_response,live_run_output',f"import sys\nsys.path.insert(0,{str(ROOT/'tests/e2e')!r})\nfrom live_provider_admission import LiveAdmission,TEXTS,forward_admitted_response,live_run_output")
ui=replace_once(ui,'OUT=live_run_output(Path.cwd(),args.run_id);',f'OUT=Path({str(OUT)!r});')
ui=replace_once(ui,'headless=True','headless=False')
ui=replace_once(ui,'window.audioProof=[];window.captureAttempts=0;', '''window.audioProof=[];window.captureAttempts=0;window.transferProof=[];window.uiPhases=[];
setInterval(()=>window.uiPhases.push({at:performance.now(),phase:document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase,capture:window.captureAttempts}),50);
const fetchOriginal=window.fetch;window.fetch=async function(...a){const start=performance.now();const response=await fetchOriginal.apply(this,a);if(String(a[0]).endsWith('/speech')){const entry={requestAt:start,headersAt:performance.now(),chunks:[]};window.transferProof.push(entry);const blob=response.blob.bind(response);response.blob=async()=>{const result=await blob();entry.bodyCompleteAt=performance.now();return result;};if(response.body){const get=response.body.getReader.bind(response.body);response.body.getReader=(...b)=>{const reader=get(...b),read=reader.read.bind(reader);reader.read=async()=>{const part=await read();if(part.done)entry.bodyCompleteAt=performance.now();else entry.chunks.push({at:performance.now(),bytes:part.value.byteLength});return part;};return reader;};}}return response;};''')
ui=replace_once(ui,"if not forward_admitted_response(route,gate,kind,record):proof['status']='PROVIDER_FAILURE_NO_RETRY'", "if kind=='tts':\n    route.continue_();return\n   if not forward_admitted_response(route,gate,kind,record):proof['status']='PROVIDER_FAILURE_NO_RETRY'")
ui=replace_once(ui,"page.route('**/api/mental/**',route_guard)","page.route('**/api/mental/**',route_guard)\n def speech_headers(response):\n  if response.request.method=='POST' and response.url.endswith('/speech'):\n   gate.complete('tts',None,response.ok);tts_ready.append(page.evaluate('performance.now()'))\n page.on('response',speech_headers)")
ui=replace_once(ui,"page.wait_for_function('(n)=>window.audioProof.filter(e=>e.type===\"ended\").length===n',arg=i+1,timeout=90000)","page.screenshot(path=str(OUT/f'turn-{i+1}-playing.png'),full_page=True)\n   page.wait_for_function('(n)=>window.audioProof.filter(e=>e.type===\"ended\").length===n',arg=i+1,timeout=90000)")
finish_start=ui.index("  page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();")
finish_end=ui.index("  proof['audioEvents']=",finish_start)
if args.phase=='before':
    ui=ui[:finish_start]+"  assert gate.counts=={'conversation':3,'tts':3,'summary':0}\n  proof['baselineNoSummary']=True\n"+ui[finish_end:]
if args.phase=='after':
    ui=replace_once(ui,"page.wait_for_function('(n)=>window.audioProof.filter(e=>e.type===\"ended\").length===n',arg=i+1,timeout=90000)","page.wait_for_function('(n)=>window.audioProof.filter(e=>e.type===\"ended\").length===n',arg=i+1,timeout=90000)\n   transfer=page.evaluate('window.transferProof')[i];playing=page.evaluate('window.audioProof.filter(e=>e.type===\"playing\")')[i];assert playing['time']<transfer['bodyCompleteAt'], 'First sound did not precede completed response body; stop remaining paid requests'")
ui=replace_once(ui,"proof['records']=1;proof['status']='PASS'","proof['records']=0 if args.run_id.endswith('-before') else 1;proof['transferEvents']=page.evaluate('window.transferProof');proof['uiPhases']=page.evaluate('window.uiPhases');proof['status']='PASS'")
# Archive raw media events before any reload/teardown, and retain that archive.
ui=replace_once(ui,"proof['browserAdmission']=gate.proof();proof['audioEvents']=page.evaluate('window.audioProof');", "proof['browserAdmission']=gate.proof();proof['audioEvents']=page.evaluate('window.audioProof');proof['transferEvents']=page.evaluate('window.transferProof');proof['uiPhases']=page.evaluate('window.uiPhases');proof['sendStarts']=starts;proof['speechStarts']=speech_starts;proof['speechHeaders']=tts_ready;")
ui=replace_once(ui,"(OUT/'ui-proof.json').write_text", "proof['rawEventsArchivedBeforeCleanup']=True\n  (OUT/'raw-audio-events.json').write_text(json.dumps(proof['audioEvents'],indent=2),encoding='utf-8')\n  (OUT/'ui-proof.json').write_text")
if args.phase=='after':
    # Apply the same real production Markdown AST to the current verified reply.
    # Raw provider history is still required byte-for-byte for chat and summary.
    module=OUT/'spokenText.mjs'
    transpiler="const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync(process.argv[1],'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText)"
    module.write_text(subprocess.check_output([shutil.which('node'),'-e',transpiler,str(ROOT/'apps/vehicle-app/src/utils/spokenText.ts')],cwd=ROOT,text=True,encoding='utf-8'),encoding='utf-8')
    normalizer=OUT/'normalize-reply.mjs'
    normalizer.write_text("import{spokenText}from './spokenText.mjs';let text='';for await(const part of process.stdin)text+=part;process.stdout.write(spokenText(text));",encoding='utf-8')
    definition=f"def normalized_reply(value):\n    import subprocess\n    return subprocess.check_output([{shutil.which('node')!r},{str(normalizer)!r}],input=value,text=True,encoding='utf-8',timeout=5)\n"
    backend=replace_once(backend,'gate = LiveAdmission(source_verified=True)',definition+'gate = LiveAdmission(source_verified=True,spoken_reply=normalized_reply)')
    ui=replace_once(ui,'gate=LiveAdmission(False);',definition+'gate=LiveAdmission(False,spoken_reply=normalized_reply);')
for name,source in [('backend.py',backend),('ui.py',ui)]:
    compile(source,str(OUT/name),'exec');(OUT/name).write_text(source,encoding='utf-8')
if args.prepare_only:
    print('Prepared and compiled; zero provider dispatch');raise SystemExit(0)

preflight=BASE/'preflight.json'
assert preflight.exists(),'Price/input/output preflight must precede any launch'
if args.phase=='after':
    assert json.loads((BASE/'before/cleanup-proof.json').read_text())['status']=='PASS'
    assert json.loads((BASE/'before/egress-proof.json').read_text())['counts']=={'conversation':3,'tts':3,'summary':0}
assert not (OUT/'launch-consumed.json').exists() and not (OUT/'run-consumed.json').exists()
for port in (3000,8000):
    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))!=0,'Other process owns test port'
with (OUT/'launch-consumed.json').open('x') as f:json.dump({'phase':args.phase,'retry':0,'approval':'human approved 13-call paired experiment 2026-10-04'},f)
env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')};env.update(OPENAI_API_KEY='',ATTUNE_LOAD_LOCAL_ENV='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
processes=[];logs=[];result={'phase':args.phase,'sourceHead':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'status':'FAIL_NO_RETRY'}
try:
    with tempfile.TemporaryDirectory(prefix='attune-paired-') as data:
        env['ATTUNE_DATA_DIR']=data
        try:
            for name,command in [('backend',[sys.executable,str(OUT/'backend.py'),'--approved-additional-text-run','--run-id','paired-20261004-'+args.phase]),('frontend',[shutil.which('node'),str(ROOT/'node_modules/next/dist/bin/next'),'start',str(ROOT/'apps/vehicle-app'),'--hostname','127.0.0.1','-p','3000'])]:
                log=(OUT/(name+'.log')).open('w',encoding='utf-8');logs.append(log)
                service_env={**env,'OPENAI_API_KEY':'','ATTUNE_LOAD_LOCAL_ENV':'0'} if name=='frontend' else env
                processes.append(subprocess.Popen(command,cwd=ROOT,env=service_env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW))
            for url in ['http://localhost:8000/api/health','http://localhost:3000']:
                deadline=time.monotonic()+60
                while True:
                    try:
                        with urllib.request.urlopen(url,timeout=2) as response:assert response.status==200
                        break
                    except Exception:
                        assert time.monotonic()<deadline and all(p.poll() is None for p in processes)
                        time.sleep(.25)
            with (OUT/'ui.log').open('w',encoding='utf-8') as log:
                done=subprocess.run([sys.executable,str(OUT/'ui.py'),'--approved-additional-text-run','--run-id','paired-20261004-'+args.phase],cwd=ROOT,env={**env,'OPENAI_API_KEY':'','ATTUNE_LOAD_LOCAL_ENV':'0'},stdout=log,stderr=subprocess.STDOUT,timeout=500)
            result['status']='PASS' if done.returncode==0 else 'FAIL_NO_RETRY';result['uiExitCode']=done.returncode
        finally:
            for p in reversed(processes):
                if p.poll() is None:p.terminate()
                p.wait(timeout=20)
            for log in logs:log.close()
except Exception as error:result['failureCategory']=type(error).__name__
finally:
    result['ownedProcessesExited']=all(p.poll() is not None for p in processes)
    (OUT/'cleanup-proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
raise SystemExit(0 if result['status']=='PASS' else 1)
