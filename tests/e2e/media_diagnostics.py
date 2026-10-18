"""Focused original-app audit. Native devices, actual model, no fabricated results.
The direct engine checks are integration tests, not a replacement for blocked UI E2E.
"""
import json,pathlib,subprocess,time,traceback,math,os,platform,threading,array,sys
from playwright.sync_api import sync_playwright, expect
OUT=pathlib.Path('audit-results');OUT.mkdir(exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')
BASE=os.environ.get('ATTUNE_AUDIT_BASE','http://localhost:3000');results=[]
class UnsupportedCapability(AssertionError):
 pass
def save(name,data):
 (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def require(ok,message):
 if not ok:raise AssertionError(message)
def record(name,fn):
 try:r={'name':name,'status':'PASS','capability':'SUPPORTED','detail':fn()}
 except Exception as e:r={'name':name,'status':'FAIL','capability':'UNSUPPORTED' if isinstance(e,UnsupportedCapability) else 'REAL_FAILURE','error':str(e),'traceback':traceback.format_exc(limit=3)}
 results.append(r);print('FOCUSED_RESULT '+json.dumps(r,ensure_ascii=False),flush=True)
INIT=r'''(()=>{window.__audit={streams:[],raf:[],cancel:[],draw:0,speech:[],tts:[]};const g=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...a)=>{const s=await g(...a);window.__audit.streams.push(s);return s;};const raf=requestAnimationFrame;window.requestAnimationFrame=(f)=>{let id=raf(t=>{window.__audit.raf.push({id,event:'fired'});return f(t);});window.__audit.raf.push({id,event:'scheduled'});return id;};const cancel=cancelAnimationFrame;window.cancelAnimationFrame=(id)=>{window.__audit.cancel.push(id);return cancel(id);};const draw=CanvasRenderingContext2D.prototype.drawImage;CanvasRenderingContext2D.prototype.drawImage=function(...a){window.__audit.draw++;return draw.apply(this,a);};const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR){const W=function(){const s=new SR();['start','audiostart','soundstart','speechstart','speechend','soundend','audioend','end','nomatch','error','result'].forEach(k=>s.addEventListener(k,e=>window.__audit.speech.push({type:k,time:performance.now(),error:e.error||null,transcript:e.results?.[0]?.[0]?.transcript||null})));['start','stop','abort'].forEach(method=>{const native=s[method].bind(s);s[method]=(...args)=>{window.__audit.speech.push({type:'call-'+method,time:performance.now(),lang:s.lang,continuous:s.continuous});return native(...args);};});return s;};window.SpeechRecognition=W;window.webkitSpeechRecognition=W;}const speak=speechSynthesis.speak.bind(speechSynthesis);speechSynthesis.speak=u=>{let item={text:u.text,lang:u.lang,events:[]};['start','end','error'].forEach(k=>u.addEventListener(k,e=>item.events.push({type:k,error:e.error||null})));window.__audit.tts.push(item);return speak(u);};})();'''
face=str(pathlib.Path('audit-fixtures/face.y4m').resolve())
def play_fixture():
 log=open(OUT/'pulse-playback.log','ab')
 player=subprocess.Popen(['bash','-c','while true; do paplay --device=audit_mic audit-fixtures/speech.wav || exit; sleep 1; done'],stdout=log,stderr=log,start_new_session=True)
 return player,log

def stop_fixture(player,log):
 import signal
 if player.poll() is None:os.killpg(player.pid,signal.SIGTERM)
 player.wait(timeout=5);log.close()

class PulseOutput:
 """Measure only the controlled output test, in memory; never export raw PCM."""
 def __enter__(self):
  self.peak=0.0;self.samples=0
  self.log=open(OUT/'pulse-output-capture.log','ab')
  self.process=subprocess.Popen(['parec','--device=audit_output.monitor','--format=s16le','--rate=48000','--channels=1'],stdout=subprocess.PIPE,stderr=self.log)
  def read():
   while True:
    chunk=self.process.stdout.read(4096)
    if not chunk:break
    values=array.array('h');values.frombytes(chunk[:len(chunk)//2*2])
    self.samples+=len(values)
    if values:self.peak=max(self.peak,max(abs(v) for v in values)/32768)
  self.thread=threading.Thread(target=read,daemon=True);self.thread.start();return self
 def __exit__(self,*args):
  self.process.terminate();self.process.wait(timeout=5);self.thread.join(timeout=5);self.log.close()

def run_native_audio(pw,headed,new,go,snap,browser_environment):
 names=['native PulseAudio spoken input amplitude headed='+str(headed),'original app actual Turkish speech recognition headed='+str(headed),'production MPEG native events and PCM (explicit tone fixture) headed='+str(headed)]
 if platform.system()!='Linux':
  def unsupported():raise UnsupportedCapability('The native PulseAudio/Speech Dispatcher diagnostic requires Linux; no personal microphone captured on this host.')
  for name in names:record(name,unsupported)
  return
 native_args=['--autoplay-policy=no-user-gesture-required','--use-fake-ui-for-media-stream','--enable-speech-dispatcher','--enable-logging=stderr','--vmodule=*speech*=2,*audio*=1','--log-net-log='+str((OUT/('chrome-netlog-'+str(headed)+'.json')).resolve())]
 try:
  # PulseOutput must receive real PCM; Playwright otherwise mutes headless audio.
  b=pw.chromium.launch(channel='chrome',headless=not headed,args=native_args,ignore_default_args=['--mute-audio'])
 except Exception as error:
  message=str(error)
  def unavailable():raise UnsupportedCapability('Native Chrome could not launch: '+message)
  for name in names:record(name,unavailable)
  return
 c,p=new(b);go(p,'/mental?demo=1');p.wait_for_timeout(1200)
 env=browser_environment(p,b,'native-browser-environment-'+str(headed));env['launchArgs']=native_args;save('native-browser-environment-'+str(headed),env)
 amplitude=None
 def audio_energy():
  nonlocal amplitude
  require(any(d['kind']=='audioinput' for d in env['devices']),'No eligible microphone enumerated by Chrome: '+json.dumps(env))
  player,log=play_fixture()
  try:
   require(player.poll() is None,'Fixture playback failed before capture')
   d=p.evaluate('''async()=>{const s=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});const a=new AudioContext();try{await a.resume();const src=a.createMediaStreamSource(s),an=a.createAnalyser();src.connect(an);const buf=new Float32Array(an.fftSize);let peak=0;for(let i=0;i<35;i++){an.getFloatTimeDomainData(buf);peak=Math.max(peak,...buf.map(Math.abs));await new Promise(r=>setTimeout(r,100));}return {peak,tracks:s.getTracks().map(t=>({kind:t.kind,settings:t.getSettings()}))};}finally{s.getTracks().forEach(t=>t.stop());await a.close();}}''')
   save('native-audio-amplitude-'+str(headed),d);require(d['peak']>.001,'No spoken PCM signal reached OS microphone');amplitude=d;return d
  finally:stop_fixture(player,log)
 record(names[0],audio_energy)
 def speech():
  require(amplitude is not None,'Native recognition not started: eligible microphone and PCM preflight did not pass')
  player=log=None
  try:
   # Feed a complete phrase only after the native capture device is listening.
   # Starting paplay before asynchronous Chrome capture clipped the first phrase.
   p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();(p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check(), p.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click())
   p.wait_for_function('window.__audit.speech.some(e=>e.type==="audiostart") || window.__audit.speech.some(e=>e.type==="error")',timeout=10000)
   if p.evaluate('window.__audit.speech.some(e=>e.type==="audiostart")'):player,log=play_fixture()
   p.wait_for_timeout(18000);d=snap(p,'native-speech-'+str(headed))
   app_result=any(e['type']=='result' and e['transcript'] for e in d['speech'])
   if not app_result:
    # Independent native control on a separate page, without the product or API wrappers.
    if player is not None:stop_fixture(player,log);player=log=None
    control_context=b.new_context(permissions=['microphone'],locale='tr-TR');control=control_context.new_page();control.route('**/native-speech-control',lambda route:route.fulfill(content_type='text/html',body='<button id="start">Start native recognition</button>'));control.goto(BASE+'/native-speech-control');control.evaluate('''()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;window.nativeEvents=[];if(!SR){window.nativeEvents.push({type:'unavailable'});return;}document.getElementById('start').onclick=()=>{const s=new SR();window.nativeRecognition=s;s.lang='tr-TR';for(const type of ['start','audiostart','soundstart','speechstart','result','nomatch','error','end'])s.addEventListener(type,e=>window.nativeEvents.push({type,error:e.error||null,transcript:e.results?.[0]?.[0]?.transcript||null}));s.start();};}''');control.get_by_role('button',name='Start native recognition').click()
    control.wait_for_function('window.nativeEvents.some(e=>e.type==="audiostart" || e.type==="error" || e.type==="unavailable")',timeout=10000)
    if control.evaluate('window.nativeEvents.some(e=>e.type==="audiostart")'):player,log=play_fixture()
    control.wait_for_timeout(18000);control_events=control.evaluate('window.nativeEvents');control_context.close()
    proof={'applicationEvents':d['speech'],'independentNativeEvents':control_events,'environment':env,'amplitude':amplitude};save('speech-runtime-control-'+str(headed),proof)
    control_result=any(e['type']=='result' and e.get('transcript') for e in control_events)
    native_errors={e.get('error') for e in control_events if e['type']=='error'}
    if not control_result and native_errors.intersection({'network','service-not-allowed','language-not-supported','not-allowed'}):
     raise UnsupportedCapability('Native recognition also fails without application code, despite visible eligible microphone and measured PCM: '+json.dumps(proof))
   require(app_result,'Native recognition failed to transcribe: '+json.dumps(d['speech']));require(any(e.get('transcript') and e['transcript'] in d['body'] for e in d['speech'] if e['type']=='result'),'Native transcript did not reach the application conversation');require('Ses girişi iptal edildi.' not in d['body'],'Successful recognition followed by intentional TTS cancellation displayed a failure');require(not d['errors'],'Uncaught speech application error');return d['speech']
  finally:
   if player is not None:stop_fixture(player,log)
 record(names[1],speech)
 def tts():
  # Explicit transport fixture, not an alternate production voice or pronunciation test.
  p.route('**/api/mental/speech',lambda r:r.fulfill(content_type='audio/mpeg',body=pathlib.Path('tests/fixtures/synthetic-tone.mp3').read_bytes()))
  p.evaluate("()=>{window.mpegEvents=[];const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){for(const type of ['playing','ended','error'])this.addEventListener(type,()=>window.mpegEvents.push({type,time:performance.now()}));return play.call(this)};}")
  p.get_by_role('button',name='İsterseniz yazabilirsiniz').click()
  with PulseOutput() as output:
   p.get_by_role('textbox',name='Görüşme mesajı').fill('Bugün yeni bir kitap okudum.');p.get_by_role('textbox',name='Görüşme mesajı').press('Enter')
   p.wait_for_function('window.mpegEvents.some(e=>e.type==="playing")')
   p.wait_for_function('window.mpegEvents.some(e=>e.type==="ended")',timeout=45000)
  events=p.evaluate('window.mpegEvents');evidence={'events':events,'transportFixture':'synthetic-tone','exactVoiceAcceptance':False,'outputPeak':output.peak,'outputSamples':output.samples};save('native-mpeg-output-'+str(headed),evidence)
  require(output.peak>.001,'Native MPEG events emitted but no PCM reached PulseAudio')
  require(not any(e['type']=='error' for e in events),'Native MPEG error event emitted')
  return evidence
 record(names[2],tts)
 c.close();b.close()

args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+face,'--autoplay-policy=no-user-gesture-required','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chromium',headless=True,args=args)
 def new(browser=b,granted=True):
  c=browser.new_context(viewport={'width':1600,'height':1000},permissions=['camera','microphone'] if granted else [],locale='tr-TR');c.add_init_script(INIT);p=c.new_page();p.set_default_timeout(8000);p._errors=[];p._console=[];p.on('pageerror',lambda e:p._errors.append(str(e)));p.on('console',lambda m:p._console.append({'type':m.type,'text':m.text}));return c,p
 def go(p,path):p.goto(BASE+path,wait_until='domcontentloaded');p.wait_for_timeout(1000)
 def state(p):return p.evaluate('({body:document.body.innerText,storage:Object.fromEntries(Object.entries(localStorage)),video:[...document.querySelectorAll("video")].map(v=>({w:v.videoWidth,h:v.videoHeight,time:v.currentTime,ready:v.readyState,paused:v.paused})),tracks:window.__audit.streams.flatMap(s=>s.getTracks().map(t=>({kind:t.kind,state:t.readyState}))),raf:window.__audit.raf,cancel:window.__audit.cancel,draw:window.__audit.draw,speech:window.__audit.speech,tts:window.__audit.tts,engine:document.querySelector("canvas")?.dataset,rafCounts:{scheduled:window.__audit.raf.filter(e=>e.event==="scheduled").length,fired:window.__audit.raf.filter(e=>e.event==="fired").length,cancelled:window.__audit.cancel.length}})')
 def snap(p,name):
  d=state(p);d.update(errors=p._errors,console=p._console);save(name,d);p.screenshot(path=str(OUT/(name+'.png')),full_page=True);return d
 def browser_environment(p,browser,name):
  d=p.evaluate('''async()=>{const out={ua:navigator.userAgent,secure:isSecureContext,devices:(await navigator.mediaDevices.enumerateDevices()).map(d=>({kind:d.kind,label:d.label,deviceId:d.deviceId})),permissions:{}};for(const name of ['camera','microphone']){try{out.permissions[name]=(await navigator.permissions.query({name})).state;}catch(e){out.permissions[name]=String(e);}}return out;}''')
  d.update(version=browser.version,platform=platform.platform());save(name,d);return d
 def deny_camera(c,p):
  s=c.new_cdp_session(p);info=s.send('Target.getTargetInfo');ctx=info['targetInfo'].get('browserContextId');payload={'permission':{'name':'camera'},'setting':'denied','origin':BASE}
  if ctx:payload['browserContextId']=ctx
  s.send('Browser.setPermission',payload)
  return p.evaluate('navigator.permissions.query({name:"camera"}).then(p=>p.state)')
 c,p=new()
 def stalled_scan():
  go(p,'/skin');browser_environment(p,b,'camera-browser-environment')
  p.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeReady==="true"',timeout=30000)
  p.get_by_role('button',name='Analizi Başlat',exact=True).click()
  # Observe live acquisition before the accepted frame is frozen for matting.
  # Actual inference is asynchronous; a 500ms redraw assumption is not FPS proof.
  p.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeActive==="true" && document.querySelector("canvas")?.dataset.faceDetected==="true" && window.__audit.draw>=3',timeout=30000)
  d=snap(p,'skin-live-loop-diagnostic')
  require(d['video'] and d['video'][0]['w']>0 and d['video'][0]['time']>0,'No actual decoded video')
  require(d['rafCounts']['fired']>1,'RAF did not repeatedly execute')
  require(int(d['engine']['landmarkCount'])>=400,'Live UI did not reach actual MediaPipe detection')
  require(not d['errors'],'Uncaught live analysis error')
  p.wait_for_function('(before)=>window.__audit.draw>before',arg=d['draw'],timeout=10000)
  later=state(p);require(later['draw']>d['draw'],'Canvas stopped drawing during live acquisition')
  require('togg_health_latest_skin' not in d['storage'] if d['engine']['qualityStatus']=='BLURRY' else True,'Rejected blurry fixture generated a real result')
  d['drawsAfterBoundedWait']=later['draw'];return d
 record('original skin live preview actually reaches frame analysis',stalled_scan)
 def route_cleanup():
  p.get_by_role('link',name='Gizlilik & İzinler',exact=True).click();expect(p).to_have_url(BASE+'/privacy');p.wait_for_timeout(800);d=snap(p,'skin-route-cleanup');require(all(t['state']=='ended' for t in d['tracks']),'Video track survives route exit')
 record('skin camera stops on navigation away',route_cleanup);c.close()
 c,p=new(granted=False)
 def genuine_denial():
  go(p,'/privacy');permission=deny_camera(c,p);require(permission=='denied','Browser denial not actually established: '+permission);go(p,'/skin');p.wait_for_timeout(2000);p.get_by_role('button',name='Analizi Başlat',exact=True).click();p.wait_for_timeout(600);d=snap(p,'native-camera-denied');require('Kamera erişimi sağlanamadı' in d['body'],'Missing denial message');require(not d['tracks'],'Camera acquired despite native denial');require('togg_health_latest_skin' not in d['storage'],'Result fabricated after denial')
 record('native browser camera rejection handled without fake result',genuine_denial)
 def demo_all_regions():
  go(p,'/skin?demo=1');p.get_by_role('button',name='Analizi Başlat',exact=True).click();p.get_by_text('Cilt Analizi Tamamlandı',exact=True).wait_for(timeout=10000);d=snap(p,'skin-demo-completed');require('attune_demo_skin_result' in d['storage'],'Demo record missing');require('togg_health_latest_skin' not in d['storage'],'Demo contaminated real storage')
  visited=[]
  for i in range(6):
   visited.append(p.locator('body').inner_text());p.get_by_role('button',name='Sonraki Bölge',exact=True).click();p.wait_for_timeout(200)
  require(len(set(visited))==6,'Six region pages are not distinct');snap(p,'skin-demo-six-regions');return 'Six distinct result regions; synthetic demo, not camera analysis'
 record('explicit demo completion isolation and six-region navigation',demo_all_regions)
 def demo_modals():
  buttons=p.get_by_role('button').all_text_contents();details=[]
  for word in ['Zaman','Gözlem','Aksiyon']:
   target=p.get_by_role('button').filter(has_text=word).first;target.click();p.wait_for_timeout(300);details.append({'word':word,'body':p.locator('body').inner_text()});snap(p,'skin-demo-modal-'+word);p.keyboard.press('Escape');p.wait_for_timeout(200)
  return details
 record('explicit demo trend observation action modals and escape',demo_modals)
 def demo_referral():
  p.get_by_role('button',name='Uzman Seçeneklerini Gör',exact=True).click();p.wait_for_timeout(2000);d=snap(p,'skin-demo-referral');require('/care' in p.url and 'Dermatoloji' in d['body'],'No dermatology handoff');require('togg_active_referral_context' not in d['storage'],'Demo referral contaminated real context');return 'Navigation only, no external booking'
 record('explicit demo skin to care referral separated from real record',demo_referral);c.close()
 # Execute original TypeScript SkinAnalyzer, changing only module URL resolution.
 source=pathlib.Path('apps/vehicle-app/src/utils/skinAnalyzer.ts').read_text()
 js=subprocess.check_output(['node','-e',"const ts=require('typescript');const fs=require('fs');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/skinAnalyzer.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ES2020,target:ts.ScriptTarget.ES2020}}).outputText)"]).decode().replace("'@mediapipe/tasks-vision'","'/audit-mediapipe.mjs'")
 (OUT/'actual-skin-engine.js').write_text(js,encoding='utf-8')
 c,p=new();p.route('**/audit-skin-engine.js',lambda r:r.fulfill(status=200,content_type='text/javascript',body=js));p.route('**/audit-mediapipe.mjs',lambda r:r.fulfill(status=200,content_type='text/javascript',body=pathlib.Path('node_modules/@mediapipe/tasks-vision/vision_bundle.mjs').read_text()))
 def actual_engine():
  go(p,'/privacy');d=p.evaluate('''async()=>{const {SkinAnalyzer:S}=await import('/audit-skin-engine.js');window.__S=S;await S.getFaceLandmarker();const stream=await navigator.mediaDevices.getUserMedia({video:true});const v=document.createElement('video');v.muted=true;v.srcObject=stream;document.body.append(v);await v.play();await new Promise(r=>setTimeout(r,500));const canvas=document.createElement('canvas');canvas.width=v.videoWidth;canvas.height=v.videoHeight;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(v,0,0);const align=S.assessAlignment(ctx,canvas.width,canvas.height);const quality=S.checkQuality(ctx,canvas.width,canvas.height,align.faceDetected);const regions=S.analyzeRegions(ctx,canvas.width,canvas.height,align);const baseline=S.compareWithBaseline(regions,null);const repeat=S.compareWithBaseline(regions,regions);window.__canvas=canvas;window.__regions=regions;stream.getTracks().forEach(t=>t.stop());return {modelReady:S.isMediaPipeReady(),align:{...align,landmarks:undefined,landmarkCount:align.landmarks?.length},quality,regions,baseline,repeat};}''')
  (OUT/'actual-mediapipe-engine-results.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8");require(d['modelReady'] and d['align']['isMediaPipeActive'] and d['align']['faceDetected'],'Actual model did not detect fixture face');require(len(d['regions'])==6,'Missing actual six anatomical regions');require(d['baseline']['isBaseline'] and d['repeat']['highestChangePct']==0,'Baseline/repeat consistency failed');return d
 record('integration actual MediaPipe face six regions baseline repeat (not UI E2E)',actual_engine)
 def engine_negatives():
  d=p.evaluate('''()=>{const S=window.__S,c=window.__canvas,x=c.getContext('2d',{willReadFrequently:true}),out={};for(const [name,col] of [['dark','black'],['bright','white'],['blank','rgb(120,120,120)']]){x.fillStyle=col;x.fillRect(0,0,c.width,c.height);const a=S.assessAlignment(x,c.width,c.height);out[name]={faceDetected:a.faceDetected,quality:S.checkQuality(x,c.width,c.height,a.faceDetected),qualityWithFace:S.checkQuality(x,c.width,c.height,true)};}return out;}''')
  (OUT/'actual-engine-negative-frames.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8");require(all(not v['faceDetected'] and not v['quality']['isValid'] for v in d.values()),'Blank frames accepted as valid face');require(d['dark']['qualityWithFace']['status']=='TOO_DARK' and d['bright']['qualityWithFace']['status']=='TOO_BRIGHT' and d['blank']['qualityWithFace']['status']=='BLURRY','Quality gates incorrect');return d
 record('integration actual engine rejects no-face dark bright textureless frames',engine_negatives);c.close();b.close()
 # Branded Chrome + real OS PulseAudio virtual microphone: no fake-device flags.
 for headed in [True,False]:
  run_native_audio(pw,headed,new,go,snap,browser_environment)
(OUT/'focused-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8");print('FOCUSED_SUMMARY '+json.dumps({'total':len(results),'pass':sum(r['status']=='PASS' for r in results),'fail':sum(r['status']=='FAIL' for r in results),'unsupported':sum(r.get('capability')=='UNSUPPORTED' for r in results)}),flush=True)
raise SystemExit(1 if any(r['status']=='FAIL' for r in results) else 0)
