"""One bounded human session on the exact production build, real camera/STT.

The blue cue is a test protocol, never an answer or camera/flow override.
Only numeric conditions, parsed answer metadata and glyph geometry are saved.
Camera frames, audio and raw transcripts are not retained. Start via stdin.
"""
import json, math, queue, re, subprocess, sys, tempfile, threading, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit-results/vision-acceptance-20261008'
OUT.mkdir(parents=True, exist_ok=True)
commands = queue.Queue()
threading.Thread(target=lambda: [commands.put(s.strip()) for s in sys.stdin], daemon=True).start()

INIT = r"""
window.acceptStreams=[];window.acceptTimings=[];window.acceptASR=[];window.acceptAudio=[];
const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia=async(...args)=>{const s=await gum(...args);acceptStreams.push(s);return s};
addEventListener('attune-vision-speech-timing',e=>acceptTimings.push(e.detail));
let recognitionSequence=0;
for(const key of ['SpeechRecognition','webkitSpeechRecognition']){
 const Native=window[key];if(!Native)continue;
 function ObservedRecognition(){const r=new Native(),instance=++recognitionSequence,presentationId=document.querySelector('[data-vision-trial]')?.dataset.visionTrial;
  const observe=(kind,extra={})=>acceptASR.push({kind,instance,atMs:performance.now(),presentationId,...extra});
  for(const event of ['start','speechstart','speechend','end','error'])r.addEventListener(event,e=>observe(event,{error:e.error||null}));
  r.addEventListener('result',e=>{for(let i=e.resultIndex;i<e.results.length;i++)if(e.results[i].isFinal){const text=e.results[i][0].transcript,parsed=acceptParse(text),normalized=text.toLocaleLowerCase('tr-TR');let order=null;
   if(parsed.letter&&parsed.orientation){const city={A:'ankara',B:'bursa',E:'edirne',F:'fatsa',P:'polatlı',R:'rize'}[parsed.letter];const a=normalized.search(new RegExp('(^| )('+parsed.letter.toLocaleLowerCase('tr-TR')+'|'+city+')( |$)'));const d=normalized.search(/baş aşağı|sağ|sol|düz|aynalı/);if(a>=0&&d>=0)order=a<d?'letter-first':'direction-first';}
   observe('final',{confidence:e.results[i][0].confidence,wordCount:text.trim().split(/\s+/).length,parsed,order,instructionEcho:acceptEcho(text)});
  }});
  return r;
 }
 ObservedRecognition.prototype=Native.prototype;Object.setPrototypeOf(ObservedRecognition,Native);window[key]=ObservedRecognition;
}
const nativePlay=HTMLMediaElement.prototype.play;let audioSequence=0;
HTMLMediaElement.prototype.play=function(...args){if(this.tagName==='AUDIO'&&!this.acceptObserved){this.acceptObserved=true;const instance=++audioSequence,presentationId=document.querySelector('[data-vision-trial]')?.dataset.visionTrial;for(const kind of ['playing','pause','ended','emptied'])this.addEventListener(kind,()=>acceptAudio.push({kind,instance,presentationId,atMs:performance.now()}));}return nativePlay.apply(this,args)};
"""
READ = r"""()=>({at:performance.now(),stage:document.querySelector('[data-vision-stage]')?.dataset.visionStage,
presentationId:document.querySelector('[data-vision-trial]')?.dataset.visionTrial,
answer:JSON.parse(document.querySelector('canvas')?.dataset.visionAnswer||'null'),
notice:document.querySelector('[data-vision-answer-notice]')?.textContent,
progress:document.querySelector('[data-letter-area]')?.parentElement?.querySelector('p')?.textContent,
readiness:document.querySelector('[data-vision-readiness]')?.textContent,
evidence:JSON.parse(document.querySelector('canvas')?.dataset.visionEvidence||'null'),
letter:!!document.querySelector('[data-letter-optotype]'),
geometry:document.querySelector('[data-letter-optotype]')?.getBoundingClientRect().toJSON(),
resultTables:[...document.querySelectorAll('[data-letter-result] table')].map(t=>[...t.querySelectorAll('tbody tr')].map(r=>[...r.cells].map(c=>c.textContent))),
layout:{innerWidth,innerHeight,outerWidth,dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth,cssZoom:getComputedStyle(document.documentElement).zoom},
error:document.querySelector('[role=alert]')?.textContent,
device:document.querySelector('video')?.srcObject?.getVideoTracks().map(t=>({label:t.label,...t.getSettings(),readyState:t.readyState}))})"""

def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)

def cue(page, text):
    page.evaluate(r"""text=>{let el=document.querySelector('[data-acceptance-cue]');if(!el){el=document.createElement('div');el.dataset.acceptanceCue='protocol-only';el.style.cssText='position:fixed;top:0;left:0;right:0;height:28px;line-height:28px;font-size:12px;padding:0 8px;background:#164e63;color:white;z-index:9999;pointer-events:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis';document.body.append(el)}el.textContent=text} """, text)

def table_counts(tables):
    return [sum(int(re.search(r'/([0-9]+)', row[1])[1]) for row in table) for table in tables]

source = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
build = (ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
hashes = __import__('hashlib')
compiled = subprocess.check_output(['node','-e',"const ts=require('typescript'),fs=require('fs');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/spokenVision.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)"],cwd=ROOT,text=True,encoding='utf-8')
parser_observer='(()=>{const exports={};'+compiled+';window.acceptParse=exports.parseLetterAnswer;window.acceptEcho=exports.isLetterInstructionEcho;})();'
protected = ['apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','apps/vehicle-app/src/utils/visionTracking.ts','apps/vehicle-app/src/utils/spokenVision.ts','package-lock.json']
provenance = {'sourceSHA':source,'sourceDirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),'buildId':build,'sourceHashes':{p:hashes.sha256((ROOT/p).read_bytes()).hexdigest() for p in protected}}
rows=[];accepted=[];errors=[];phases=[];started=False;phase='waiting';phase_at=0;last_emit=0;last_progress=None;echo_until=None
with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix='attune-physical-acceptance-') as profile:
    default=Path(profile)/'Default';default.mkdir()
    (default/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}),encoding='utf-8')
    c=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,permissions=['camera','microphone'],args=['--start-maximized','--autoplay-policy=no-user-gesture-required'])
    c.add_init_script(parser_observer+INIT);p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
    deadline=time.monotonic()+1200
    try:
        p.goto('http://127.0.0.1:3000/vision');p.get_by_role('button',name='Başlat',exact=True).wait_for();p.bring_to_front()
        cue(p,'DOĞRULAMA: Hazır olduğunuzda bu sohbetten belirtin; kamera henüz açılmadı.')
        emit({'readyWindow':True,**provenance,'nativeZoom':p.evaluate('({dpr:devicePixelRatio,innerWidth,outerWidth,cssZoom:getComputedStyle(document.documentElement).zoom})')})
        while time.monotonic()<deadline:
            p.wait_for_timeout(200)
            while not commands.empty():
                command=commands.get()
                if command=='start' and not started:
                    p.get_by_role('button',name='Başlat',exact=True).click();started=True;phase='baseline';phase_at=time.monotonic()
                    cue(p,'DOĞRULAMA: İki göz açık; başlangıç konumunuz öğreniliyor.')
                elif command=='stop':deadline=0
                elif command=='front':p.bring_to_front()
            row=p.evaluate(READ);row['protocolPhase']=phase;rows.append(row)
            if not started and row['stage']=='preparing':
                started=True;phase='baseline';phase_at=time.monotonic();cue(p,'DOĞRULAMA: İki göz açık; başlangıç konumunuz öğreniliyor.')
            condition=(row.get('evidence') or {}).get('conditions') or {}
            if phase=='baseline' and condition.get('positionValid'):
                phase='near';phase_at=time.monotonic();cue(p,'DOĞRULAMA: İki göz açıkken belirgin yaklaşın; yüzün tamamı kadrajda kalsın.')
            elif phase=='near' and time.monotonic()-phase_at>8:
                phase='recover-near';phase_at=time.monotonic();cue(p,'DOĞRULAMA: Başlangıç konumunuza geri dönün; iki göz açık.')
            elif phase=='recover-near' and condition.get('distanceState')=='stable' and time.monotonic()-phase_at>3:
                phase='far';phase_at=time.monotonic();cue(p,'DOĞRULAMA: İki göz açıkken belirgin uzaklaşın; yüzünüz görünür kalsın.')
            elif phase=='far' and time.monotonic()-phase_at>8:
                phase='recover-far';phase_at=time.monotonic();cue(p,'DOĞRULAMA: Başlangıç konumunuza geri dönün; iki göz açık.')
            elif phase=='recover-far' and condition.get('distanceState')=='stable' and time.monotonic()-phase_at>3:
                phase='trials';phase_at=time.monotonic()
            if phase=='trials' and row.get('progress'):
                progress=row['progress'];match=re.search(r'([0-9]+)/12',progress)
                n=int(match[1]) if match else 1;other='Sol' if progress.startswith('Sağ') else 'Sağ'
                method='eyelid' if n<=4 else 'hand' if n<=8 else 'object'
                row['protocolMethod']=method
                instruction=f'{other} gözü '+('yumun' if method=='eyelid' else 'elinizle örtün' if method=='hand' else 'opak cisimle örtün')
                style=['harf → yön, tek cümle','yön → harf, tek cümle','harf, kısa durak, yön','yön, kısa durak, harf'][(n-1)%4]
                if last_progress and progress!=last_progress:
                    previous=next((r for r in reversed(rows[:-1]) if r.get('progress')==last_progress and 'işlendi' in (r.get('notice') or '')),None)
                    accepted.append({'previousProgress':last_progress,'nextProgress':progress,'evidenceRow':previous,'atMs':row['at']})
                    emit({'progressed':progress,'previous':last_progress})
                last_progress=progress
                if n==1 and progress.startswith('Sağ') and row['letter'] and echo_until is None:
                    echo_until=time.monotonic()+6
                silent=echo_until is not None and time.monotonic()<echo_until
                row['silentEchoWindow']=silent
                cue(p,'DOĞRULAMA: '+instruction+('. Henüz yanıt vermeyin; sistem sesi kontrolü.' if silent else '. '+style+'; yönerge sürerken söyleyin.'))
            if row['stage']=='result':
                emit({'completedResult':True,'perEyeCounts':table_counts(row['resultTables'])});break
            if time.monotonic()-last_emit>10:
                emit({'phase':phase,'stage':row['stage'],'progress':row['progress'],'blocker':condition.get('blocker'),'distance':condition.get('distanceState'),'relative':condition.get('relativeScaleChange'),'eyes':{s:condition.get(s,{}).get('state') for s in ['right','left']},'notice':row['notice'],'error':row['error']});last_emit=time.monotonic()
            (OUT/'live.json').write_text(json.dumps({**provenance,'rows':rows,'acceptedTransitions':accepted,'errors':errors},ensure_ascii=False),encoding='utf-8')
    finally:
        timings=p.evaluate('window.acceptTimings');asr=p.evaluate('window.acceptASR');audio=p.evaluate('window.acceptAudio')
        final=p.evaluate(READ)
        if p.get_by_role('button',name='Bitir',exact=True).count():
            p.get_by_role('button',name='Bitir',exact=True).click()
        tracks=p.evaluate('acceptStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
        proof={**provenance,'physicalCamera':started,'fixtureVideo':False,'fakeSTTEvents':0,'cameraFramesSaved':0,'rawAudioSaved':0,'rawTranscriptsSaved':0,'paidCalls':0,'rows':rows,'acceptedTransitions':accepted,'timings':timings,'nativeASR':asr,'nativeAudio':audio,'final':final,'perEyeCounts':table_counts(final['resultTables']),'tracksEnded':tracks,'pageErrors':errors}
        (OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');emit({k:proof[k] for k in ['buildId','physicalCamera','perEyeCounts','tracksEnded','pageErrors']});c.close()
