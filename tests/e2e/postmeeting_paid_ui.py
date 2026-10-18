"""One nonpersonal production UI reply + summary, actual Edge Emel playback.
No physical microphone, no generated image and no conversation retry.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/postmeeting/paid');OUT.mkdir(parents=True,exist_ok=True)
TEXT='Bu kişisel olmayan bir kabul testidir. Kısa bir dinlenme molası hakkında iki sakin cümle söyler misiniz?'
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context(viewport={'width':1600,'height':1000})
 c.add_init_script("window.audioProof=[];const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(...args){if(!this._audit){this._audit=true;for(const type of ['playing','ended','error','abort'])this.addEventListener(type,()=>window.audioProof.push({type,at:performance.now()}));}return play.apply(this,args);};navigator.mediaDevices.getUserMedia=()=>Promise.reject(Error('No physical microphone in text acceptance'));")
 p=c.new_page();headers=[];responses=[]
 p.route('**/api/mental/**',lambda r:r.continue_(headers={**r.request.headers,'x-acceptance-context':'postmeeting-section10-nonpersonal-two-text-calls'}))
 def response(r):
  if '/api/mental/speech' in r.url:headers.append({'status':r.status,'voice':r.headers.get('x-tts-voice'),'rate':r.headers.get('x-tts-rate'),'pitch':r.headers.get('x-tts-pitch')})
  elif '/api/mental/converse' in r.url or '/api/mental/analyze-session' in r.url:responses.append({'url':r.url,'status':r.status,'providerType':r.json().get('providerType')})
 p.on('response',response)
 c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
 p.goto('http://127.0.0.1:3000/mental');p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
 p.get_by_role('textbox',name='Görüşme mesajı').fill(TEXT);p.get_by_role('button',name='Gönder',exact=True).click()
 expect(p.locator('[data-chat-author="AI"]')).to_have_count(1,timeout=35000)
 p.wait_for_function('window.audioProof.some(e=>e.type==="ended")',timeout=90000)
 assert responses[0]['providerType']=='LIVE_OPENAI'
 assert headers and all(v['voice']=='tr-TR-EmelNeural' and v['rate']=='-10%' and v['pitch']=='-10Hz' for v in headers if v['status']==200)
 p.screenshot(path=str(OUT/'reply.png'),full_page=True)
 p.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed',timeout=35000)
 p.wait_for_timeout(500);p.screenshot(path=str(OUT/'summary.png'),full_page=True)
 ledger=json.loads((OUT/'ledger.json').read_text());assert ledger['actualRequests']==2 and all(e['status']=='SUCCESS' for e in ledger['events'])
 audio=p.evaluate('window.audioProof');assert any(e['type']=='playing' for e in audio) and any(e['type']=='ended' for e in audio) and not any(e['type']=='error' for e in audio)
 (OUT/'ui-proof.json').write_text(json.dumps({'status':'PASS','physicalMic':False,'subjectiveListening':False,'responses':responses,'voiceHeaders':headers,'audio':audio,'paidRequests':2,'retries':0},indent=2),'utf8')
 c.close();b.close()
print('PASS: two real text calls; production Edge Emel playing/ended; physical mic and listening OPEN')
