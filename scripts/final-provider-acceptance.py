"""Prepare or execute ONE separately approved final seven-request run.

Default is preparation only. Old paired evidence is never a writable destination.
Fixtures are explicitly keyless and deny all non-loopback sockets.
"""
import argparse,atexit,hashlib,json,os,re,shutil,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
def replace_once(source,old,new):
    assert source.count(old)==1,old[:80]
    return source.replace(old,new)
def historical_hashes():
    base=ROOT/'audit-results/live-provider/paired-20261004'
    return {str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*') if p.is_file()}

def prepare(out):
    # Reuse immutable checked-in gate/stream observer generation, not previous
    # generated run files. No old ledger, media or clock evidence is overwritten.
    source=(ROOT/'scripts/paired-provider-acceptance.py').read_text(encoding='utf-8')
    start=source.index('backend=(ROOT/');end=source.index('for name,source in',start)
    scope=dict(globals(),OUT=out,args=SimpleNamespace(phase='after'))
    exec(compile(source[start:end],'paired-template-preparation','exec'),scope)
    backend,ui=scope['backend'],scope['ui']
    # One prewarmed AST process per observer, rather than one fresh process per
    # request. JSON-lines carries only the already-authorized synthetic reply.
    (out/'normalize-reply.mjs').write_text("import{spokenText}from './spokenText.mjs';import readline from 'node:readline';for await(const line of readline.createInterface({input:process.stdin})){process.stdout.write(JSON.stringify(spokenText(JSON.parse(line)))+'\\n');}",encoding='utf-8')
    definition=scope['definition']
    persistent=f'''import atexit
normalizer = subprocess.Popen([{shutil.which('node')!r},{str(out/'normalize-reply.mjs')!r}],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1,env={{k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}})
(OUT/('normalizer-'+Path(__file__).stem+'.json')).write_text(json.dumps({{'pid':normalizer.pid,'script':{str(out/'normalize-reply.mjs')!r}}}),encoding='utf-8')
def close_normalizer():
    if normalizer.poll() is None:normalizer.terminate()
    normalizer.wait(timeout=5)
atexit.register(close_normalizer)
def normalized_reply(value):
    normalizer.stdin.write(json.dumps(value,ensure_ascii=False)+'\\n');normalizer.stdin.flush()
    return json.loads(normalizer.stdout.readline())
assert normalized_reply('**Türkçe**') == 'Türkçe'
'''
    # UI template initially imports only argparse/json/time; supply subprocess/os.
    ui='import subprocess,os\n'+ui;backend='import subprocess\n'+backend
    assert definition in ui and definition in backend
    ui=ui.replace(definition,persistent);backend=backend.replace(definition,persistent)
    old=";assert playing['time']<transfer['bodyCompleteAt'], 'First sound did not precede completed response body; stop remaining paid requests'"
    assert old in ui;ui=ui.replace(old,'')
    ui=ui.replace('window.transferProof=[];', "window.transferProof=[];window.productionTiming=[];window.addEventListener('attune-speech-timing',e=>window.productionTiming.push(e.detail));")
    ui=ui.replace("proof['browserAdmission']=gate.proof();", "proof['productionTiming']=page.evaluate('window.productionTiming');proof['clockDefinitions']={'browser':'performance.now milliseconds since this page time origin','backend':'monotonic durations since each dispatch; never subtracted from browser values'};proof['browserAdmission']=gate.proof();")
    ui=ui.replace("proof['records']=0 if args.run_id.endswith('-before') else 1;", "proof['records']=1;proof['streamingCriterion']='controlled incremental production path verified separately; real fast-body order measured, not forced';")
    ui=ui.replace("assert gate.counts=={'conversation':3,'tts':3,'summary':1} and proof['historyLengths']==[0,2,4]", "assert gate.counts=={'conversation':3,'tts':3,'summary':1} and proof['historyLengths']==[0,2,4]\n  assert all(any(e['stage']==stage and e['turn']==i for e in page.evaluate('window.productionTiming')) for i in (1,2,3) for stage in ('send','chat-response','tts-request','tts-headers','chunk','body-end','playing','ended','cleanup'))")
    for name,content in [('backend.py',backend),('ui.py',ui)]:
        compile(content,str(out/name),'exec');(out/name).write_text(content,encoding='utf-8')
    return backend,ui

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--fixture',choices=['success','failure']);parser.add_argument('--approved-final-run',action='store_true');parser.add_argument('--preflight',type=Path);args=parser.parse_args()
    assert re.fullmatch(r'(prep-guided|guided-final)-[a-z0-9-]{3,48}',args.run_id),'New distinct authorization identity required'
    out=ROOT/'audit-results/live-provider'/args.run_id
    assert not any((out/n).exists() for n in ('launch-consumed.json','run-consumed.json')),'Consumed run immutable; no retry'
    if not args.prepare_only and not args.fixture:raise SystemExit('Historical OpenAI TTS acceptance superseded by Edge-only product; zero provider dispatch')
    if not args.prepare_only and not args.fixture and not args.approved_final_run:raise SystemExit('No new approval: zero provider dispatch')
    assert not args.fixture or args.run_id.startswith('prep-guided-')
    before=historical_hashes();out.mkdir(parents=True,exist_ok=True);prepare(out)
    if args.prepare_only:
        assert before==historical_hashes();print('Prepared and compiled; zero dispatch; old paired evidence unchanged');return
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
    if not args.fixture:
        assert args.preflight and args.preflight.is_file(),'Explicit reviewed preflight required'
        pre=json.loads(args.preflight.read_text(encoding='utf-8'))
        assert pre['sourceHead']==head and pre['windowsBuild']==build and pre['maxProviderRequests']==7
        assert pre['retry']==0 and pre['targetBudgetUSD']<=1 and not pre['accountSpendingCapGuaranteed']
        assert subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()==''
    for port in (3000,8000):
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))!=0,'Other process owns port'
    with (out/'launch-consumed.json').open('x',encoding='utf-8') as f:json.dump({'runId':args.run_id,'mode':'KEYLESS_FIXTURE' if args.fixture else 'SEPARATELY_APPROVED_FINAL','head':head,'build':build,'maxRequests':7,'retry':0},f)
    env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')};env.update(ATTUNE_LOAD_LOCAL_ENV='0' if args.fixture else '1',OPENAI_API_KEY='attune-keyless-fixture-not-a-credential' if args.fixture else '',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    processes=[];logs=[];data=None;status={'runId':args.run_id,'sourceHead':head,'build':build,'liveAcceptance':not bool(args.fixture),'status':'FAIL_NO_RETRY'}
    try:
        with tempfile.TemporaryDirectory(prefix='attune-guided-final-') as data:
            env['ATTUNE_DATA_DIR']=data
            commands=[('backend',[sys.executable,str(out/'backend.py'),'--approved-additional-text-run','--run-id',args.run_id]+(['--fixture',args.fixture] if args.fixture else [])),('frontend',[shutil.which('node'),str(ROOT/'node_modules/next/dist/bin/next'),'start',str(ROOT/'apps/vehicle-app'),'--hostname','127.0.0.1','-p','3000'])]
            for name,command in commands:
                log=(out/(name+'.log')).open('w',encoding='utf-8');logs.append(log)
                child={**env,'OPENAI_API_KEY':'','ATTUNE_LOAD_LOCAL_ENV':'0'} if name=='frontend' else env
                processes.append(subprocess.Popen(command,cwd=ROOT,env=child,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
            for url in ['http://localhost:8000/api/health','http://localhost:3000']:
                deadline=time.monotonic()+60
                while True:
                    try:
                        with urllib.request.urlopen(url,timeout=2) as response:assert response.status==200
                        break
                    except Exception:
                        assert time.monotonic()<deadline and all(p.poll() is None for p in processes);time.sleep(.25)
            with (out/'ui.log').open('w',encoding='utf-8') as log:
                result=subprocess.run([sys.executable,str(out/'ui.py'),'--approved-additional-text-run','--run-id',args.run_id]+(['--fixture',args.fixture] if args.fixture else []),cwd=ROOT,env={**env,'OPENAI_API_KEY':'','ATTUNE_LOAD_LOCAL_ENV':'0'},stdout=log,stderr=subprocess.STDOUT,timeout=400)
            status['uiExitCode']=result.returncode;status['status']='PASS' if result.returncode==0 else 'FAIL_NO_RETRY'
    except Exception as error:status['failureCategory']=type(error).__name__
    finally:
        for process in reversed(processes):
            if process.poll() is None:process.terminate()
            process.wait(timeout=15)
        for log in logs:log.close()
        # Windows terminate does not execute atexit; stop only the recorded
        # child PID whose current command still names this owned normalizer.
        for record in out.glob('normalizer-*.json'):
            item=json.loads(record.read_text());pid=item['pid'];script=item['script']
            if os.name=='nt':
                literal=script.replace("'","''")
                command=f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; if ($p -and $p.CommandLine.Contains('{literal}')) {{ Stop-Process -Id {pid} -Force }}"
                subprocess.run(['powershell','-NoProfile','-Command',command],check=True,capture_output=True)
            else:
                proc=Path(f'/proc/{pid}/cmdline')
                if proc.exists() and script.encode() in proc.read_bytes():os.kill(pid,15)
        status.update(ownedProcessesExited=all(p.poll() is not None for p in processes),temporaryStorageRemoved=data is None or not Path(data).exists(),historicalPairedEvidenceUnchanged=before==historical_hashes())
        (out/'cleanup-proof.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    assert status['historicalPairedEvidenceUnchanged'];print(json.dumps(status));raise SystemExit(0 if status['status']=='PASS' else 1)
if __name__=='__main__':main()
