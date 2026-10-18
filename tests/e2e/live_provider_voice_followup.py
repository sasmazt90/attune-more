"""Explicitly authorized synthetic TEXT -> real backend/provider -> OpenAI TTS.
Physical capture denied. Exact messages/history checked in browser and HTTP egress.
"""
import argparse,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from live_provider_admission import LiveAdmission,TEXTS,forward_admitted_response,live_run_output
parser=argparse.ArgumentParser();parser.add_argument('--approved-additional-text-run',action='store_true');parser.add_argument('--run-id');parser.add_argument('--fixture',choices=['success','failure']);args=parser.parse_args()
if not args.approved_additional_text_run:raise SystemExit('No authorization: zero provider requests')
if not args.fixture:raise SystemExit('Historical paid TTS harness superseded; zero dispatch')
OUT=live_run_output(Path.cwd(),args.run_id);OUT.mkdir(parents=True,exist_ok=True)
INIT=r'''(()=>{window.audioProof=[];window.captureAttempts=0;
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR){SR.prototype.start=function(){window.captureAttempts++;throw new DOMException('Capture forbidden in text-only audit','NotAllowedError');};}
const gum=navigator.mediaDevices?.getUserMedia;if(gum)navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new DOMException('Capture forbidden in text-only audit','NotAllowedError'));};
const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(...a){if(!this.__observed){this.__observed=true;for(const type of ['playing','ended','error','pause','abort'])this.addEventListener(type,()=>window.audioProof.push({type,time:performance.now(),error:this.error?.code||null,duration:Number.isFinite(this.duration)?this.duration:null,currentTime:this.currentTime}));}return play.apply(this,a);};})();'''
proof={'mode':'KEYLESS_FIXTURE_PREPARATION' if args.fixture else 'LIVE_ATTEMPT','liveAcceptance':False,'runId':args.run_id or 'controlled-text','status':'NOT_RUN','input':'synthetic written text','nativeVoiceInputTested':False,'subjectiveListeningPerformed':False,'responses':[],'historyLengths':[],'failedContentRetained':False}
gate=LiveAdmission(False);starts=[];speech_starts=[];tts_ready=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
 context=browser.new_context(viewport={'width':1600,'height':1000},locale='tr-TR');context.add_init_script(INIT)
 page=context.new_page();cdp=context.new_cdp_session(page)
 cdp.send('Browser.setPermission',{'permission':{'name':'microphone'},'setting':'denied','origin':'http://localhost:3000','browserContextId':cdp.send('Target.getTargetInfo')['targetInfo']['browserContextId']})
 def route_guard(route):
  req=route.request
  if req.method=='GET':route.continue_();return
  try:
   if page.evaluate('window.captureAttempts')!=0:gate.reject('CAPTURE_ATTEMPT_BEFORE_DISPATCH')
   if page.evaluate('navigator.permissions.query({name:"microphone"}).then(p=>p.state)')!='denied':gate.reject('MICROPHONE_NOT_DENIED')
   data=req.post_data_json;path=req.url.rsplit('/',1)[-1]
   if data.get('cloudConsent') is not True:gate.reject('CLOUD_CONSENT_NOT_EXPLICIT')
   if path=='converse':
    transformed={'messages':[{'role':'system','content':'Sen Togg araç içi Ruhsal İyi Oluş Asistanısın.'}]+data.get('history',[])+[{'role':'user','content':data.get('userMessage')}]}
    kind=gate.admit('/v1/chat/completions',transformed);starts.append(page.evaluate('performance.now()'));proof['historyLengths'].append(len(data['history']))
   elif path=='speech':
    kind=gate.admit('/v1/audio/speech',{'input':data.get('text'),'voice':'coral','response_format':'mp3'});speech_starts.append(page.evaluate('performance.now()'))
   elif path=='analyze-session':
    transformed={'response_format':{'type':'json_object'},'messages':[{'role':'user','content':'Aşağıdaki kullanıcı-asistan araç içi konuşmasını analiz et\nKonuşma Geçmişi:\n'+'\n'.join(f"{m['role']}: {m['content']}" for m in data.get('messages',[]))}]}
    kind=gate.admit('/v1/chat/completions',transformed)
   else:gate.reject('UNEXPECTED_UI_POST')
   def record(kind,data,response):
    assert gate.pending is None
    proof.setdefault('admissionCompletedBeforeUI',[]).append(kind)
    proof.setdefault('backendTimings',[]).append({'kind':kind,'serverTiming':response.headers.get('server-timing'),'responseReceivedAtMs':round(page.evaluate('performance.now()'),1)})
    if kind=='tts':tts_ready.append(page.evaluate('performance.now()'))
    if data is not None:
     proof['responses'].append({'kind':kind,'providerType':data.get('providerType'),'responseMs':round(page.evaluate('performance.now()')-starts[-1],1) if kind=='conversation' else None})
   if not forward_admitted_response(route,gate,kind,record):proof['status']='PROVIDER_FAILURE_NO_RETRY'
  except Exception:
   proof['status']='BLOCKED_BEFORE_BACKEND';route.abort()
 page.route('**/api/mental/**',route_guard)
 try:
  context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
  page.goto('http://localhost:3000/privacy')
  page.get_by_role('button',name='Devre Dışı Bırak',exact=True).click()
  assert page.evaluate('localStorage.getItem("togg_privacy_mental_summary_allowed")')=='false'
  page.get_by_role('button',name='Etkinleştir',exact=True).click()
  assert page.evaluate('localStorage.getItem("togg_privacy_mental_summary_allowed")')=='true'
  proof['localSavingExplicitUIToggle']=True
  page.goto('http://localhost:3000/mental')
  permission=page.evaluate('navigator.permissions.query({name:"microphone"}).then(p=>p.state)');assert permission=='denied'
  assert page.evaluate('localStorage.getItem("togg_health_mental_history")') is None
  expect(page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True)).not_to_be_checked()
  gate.source_verified=True;proof['physicalMicrophone']=permission
  page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check()

  page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
  for i,text in enumerate(TEXTS):
   box=page.get_by_role('textbox',name='Görüşme mesajı');expect(box).to_be_enabled();box.fill(text);page.get_by_role('button',name='Gönder',exact=True).click()
   expect(page.locator('[data-chat-author="AI"]')).to_have_count(i+1,timeout=35000)
   assert proof['responses'][i]['providerType']=='LIVE_OPENAI'
   page.wait_for_function('(n)=>window.audioProof.filter(e=>e.type==="playing").length===n',arg=i+1,timeout=35000)
   page.wait_for_function('(n)=>window.audioProof.filter(e=>e.type==="ended").length===n',arg=i+1,timeout=90000)
   assert page.evaluate('localStorage.getItem("togg_health_mental_history")') is None
  assert [x['content'] for x in gate.messages if x['role']=='user']==list(TEXTS)
  replies=page.locator('[data-chat-author="AI"]').all_text_contents();assert len(replies)==len(set(replies))==3
  assert len({m['content'] for m in gate.messages if m['role']=='assistant'})==3
  assert page.locator('[data-chat-author="USER"]').count()==3
  page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed',timeout=35000)
  saved=page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history"))');assert len(saved)==1 and saved[0]['consented'] and saved[0]['providerType']=='LIVE_OPENAI'
  assert gate.counts=={'conversation':3,'tts':3,'summary':1} and proof['historyLengths']==[0,2,4]
  page.wait_for_timeout(1200);assert gate.counts=={'conversation':3,'tts':3,'summary':1}
  proof['audioEvents']=page.evaluate('window.audioProof');playing=[e for e in proof['audioEvents'] if e['type']=='playing'];ended=[e for e in proof['audioEvents'] if e['type']=='ended'];pauses=[e for e in proof['audioEvents'] if e['type']=='pause']
  assert len(playing)==3 and len(ended)==3 and not [e for e in proof['audioEvents'] if e['type']=='error']
  proof['allThreePlaybacksEnded']=True
  assert page.evaluate('window.captureAttempts')==0;proof['captureAttempts']=0
  proof['playbackFromUserSendMs']=[round(e['time']-starts[i],1) for i,e in enumerate(playing)]
  proof['playbackFromTTSRequestMs']=[round(e['time']-speech_starts[i],1) for i,e in enumerate(playing)]
  proof['bufferedTTSBackendToPlayingMs']=[round(e['time']-tts_ready[i],1) for i,e in enumerate(playing)]
  proof['records']=1;proof['status']='PASS';proof['liveAcceptance']=not bool(args.fixture);page.screenshot(path=str(OUT/'completed.png'),full_page=True)
 except Exception as error:
  proof['status']='FAIL';proof['failureCategory']=type(error).__name__
  if args.fixture=='failure' and gate.failed:
   from live_provider_admission import AdmissionRejected
   try:
    gate.admit('/v1/chat/completions',{})
    raise AssertionError('Closed browser gate accepted another request')
   except AdmissionRejected:pass
   # Separate backend probe bypasses the browser gate; the closed egress gate must block it.
   response=context.request.post('http://localhost:8000/api/mental/converse',data={'userMessage':TEXTS[0],'history':[],'cloudConsent':True})
   assert response.status==503 and 'providerType' not in response.json()
   proof['secondBrowserAdmissionBlocked']=True;proof['secondBackendProbeCompleted']=True;proof['status']='EXPECTED_FAILURE_PREPARATION_PASS'
  else:raise
 finally:
  proof['browserAdmission']=gate.proof();proof['audioEvents']=page.evaluate('window.audioProof');proof['captureAttempts']=page.evaluate('window.captureAttempts');proof['recordsObserved']=page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]").length')
  (OUT/'ui-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
  context.close();browser.close()
print(json.dumps(proof,ensure_ascii=False))
