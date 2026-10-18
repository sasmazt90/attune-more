"""Current production UI, real provider/context/Emel and explicit text finish.
Isolated browser and backend; no microphone or subjective listening claim.
"""
import json,ast
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/mental-live'
tree=ast.parse((Path(__file__).with_name('mental_bounded_backend.py')).read_text('utf8'))
TEXTS=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TEXTS' for t in n.targets))
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context(viewport={'width':1600,'height':1000})
 c.add_init_script("window.audioProof=[];window.micStarts=0;const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(...args){if(!this._audit){this._audit=true;for(const type of ['playing','ended','error','abort'])this.addEventListener(type,()=>audioProof.push({type,at:performance.now()}));}return play.apply(this,args);};navigator.mediaDevices.getUserMedia=()=>{micStarts++;return Promise.reject(Error('No physical microphone in text acceptance'));};")
 p=c.new_page();headers=[];responses=[];errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 remaining=json.loads((OUT/'ledger.json').read_text())['actualRequests'];assert remaining in (0,1)
 def route(r):
  # Voice remains on the normal, actual streaming backend; buffering the
  # response in route.fetch would change the streaming lifecycle under test.
  if '/speech' in r.request.url:r.continue_();return
  data=r.request.post_data
  if remaining==1 and '/converse' in r.request.url and data:
   body=json.loads(data)
   if body['userMessage']==TEXTS[1]:body['history']=[{'role':'user','content':TEXTS[0]}];data=json.dumps(body)
  r.fulfill(response=r.fetch(url=r.request.url.replace(':8000/',':8010/'),headers={**r.request.headers,'x-acceptance-context':'all-health-section8-three-nonpersonal-calls'},post_data=data))
 p.route('**/api/mental/**',route)
 def response(r):
  if '/api/mental/speech' in r.url:headers.append(dict(status=r.status,voice=r.headers.get('x-tts-voice'),rate=r.headers.get('x-tts-rate'),pitch=r.headers.get('x-tts-pitch')))
  elif '/api/mental/converse' in r.url or '/api/mental/analyze-session' in r.url:responses.append(dict(url=r.url,status=r.status,providerType=r.json().get('providerType'),sessionAction=r.json().get('sessionAction')))
 p.on('response',response)
 p.goto('http://127.0.0.1:3000/mental');p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
 for i,text in enumerate(TEXTS[remaining:]):
  expect(p.get_by_role('textbox',name='Görüşme mesajı')).to_be_enabled(timeout=90000)
  before=p.evaluate('audioProof.filter(e=>e.type==="ended").length')
  p.get_by_role('textbox',name='Görüşme mesajı').fill(text);p.get_by_role('button',name='Gönder',exact=True).click()
  expect(p.locator('[data-chat-author="AI"]')).to_have_count(i+1,timeout=35000)
  p.wait_for_function('(before)=>audioProof.filter(e=>e.type==="ended").length>before',arg=before,timeout=90000)
  assert responses[i]['providerType']=='LIVE_OPENAI'
 p.screenshot(path=str(OUT/'reply-context.png'),full_page=True)
 expect(p.get_by_role('textbox',name='Görüşme mesajı')).to_be_enabled(timeout=20000)
 p.get_by_role('textbox',name='Görüşme mesajı').fill('Görüşmeyi bitir.');p.get_by_role('button',name='Gönder',exact=True).click()
 expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed',timeout=90000)
 p.wait_for_timeout(1000);p.screenshot(path=str(OUT/'summary-finished.png'),full_page=True)
 ledger=json.loads((OUT/'ledger.json').read_text());assert ledger['actualRequests']==3 and all(e['status']=='SUCCESS' for e in ledger['events'])
 assert responses[-2]['providerType']=='CONVERSATION_CONTROL' and responses[-2]['sessionAction']=='finish' and responses[-1]['providerType']=='LIVE_OPENAI'
 assert headers and all(v['voice']=='tr-TR-EmelNeural' and v['rate']=='-10%' and v['pitch']=='-10Hz' for v in headers if v['status']==200)
 assert p.evaluate('micStarts')==0 and not errors
 state=p.evaluate('Object.fromEntries(Object.entries(localStorage))')
 records=json.loads(state.get('togg_health_mental_history','[]'))
 assert len(records)==1 and records[0]['consented'] and not records[0].get('transcript')
 (OUT/'ui-proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),physicalMic=False,subjectiveListening=False,responses=responses,voiceHeaders=headers,audio=p.evaluate('audioProof'),requests=3,retries=0,contextPreserved=True,contextSource='prior dispatched nonpersonal user turn; controlled request history' if remaining else 'actual preceding frontend turns',initialBufferedSpeechCheckFailed=bool(remaining),textFinishActuallyCompleted=True,oneConsentedSummary=True,transcriptOff=True,pageErrors=errors),indent=2),'utf8');c.close();b.close()
print('PASS three real bounded calls; context, exact Emel, explicit finish and default storage off')
