"""Current production controller and ASR callbacks; provider/audio fixtures.
No paid call, microphone hardware, ASR accuracy or auditory acceptance claim.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/mental-asr';OUT.mkdir(parents=True,exist_ok=True)
INIT='''window.asr=[];window.audioProbe=[];class R {start(){this.started=true;asr.push(this);this.onstart?.();}abort(){this.aborted=true;this.onend?.();}emit(text,final=true){this.onresult?.({resultIndex:0,results:[Object.assign([{transcript:text,confidence:.95}],{isFinal:final})]});}}window.SpeechRecognition=window.webkitSpeechRecognition=R;
 const Original=window.Audio;window.Audio=class extends Original{constructor(...v){super(...v);audioProbe.push(this);}};'''
manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/guidance/manifest.json').read_text());asset=next(e for k,e in manifest['entries'].items() if k.startswith('mental-'))
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context();c.add_init_script(INIT);p=c.new_page();calls=[];errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 def route(r):
  path=r.request.url.split('?')[0]
  if path.endswith('/provider-status'):r.fulfill(json={'isLiveLLM':True,'providerName':'CONTROLLED FIXTURE','apiKeyConfigured':False})
  elif path.endswith('/speech'):r.fulfill(path=str(ROOT/'apps/vehicle-app/public'/asset['url'].lstrip('/')),content_type='audio/mpeg')
  elif path.endswith('/converse'):
   calls.append(r.request.post_data_json);r.fulfill(json={'reply':'Kontrollü ses yaşam döngüsü yanıtı.','providerType':'LIVE_OPENAI'})
  elif path.endswith('/analyze-session'):r.fulfill(json={'summaryText':'Kontrollü yaşam döngüsü.','themes':['kontrollü'],'providerType':'LIVE_OPENAI'})
  else:r.abort()
 p.route('**/api/mental/**',route);p.goto('http://127.0.0.1:3000/mental');p.get_by_label('TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click()
 p.wait_for_function('asr.length===1&&asr[0].started');p.evaluate('asr[0].emit("Eksik geçici",false)');p.wait_for_timeout(100);assert not calls
 p.evaluate('asr[0].emit("Kişisel olmayan tamamlanmış yanıt.")');expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','speaking');assert len(calls)==1 and calls[0]['userMessage']=='Kişisel olmayan tamamlanmış yanıt.'
 p.evaluate('asr[0].emit("Sistemin kendi sesi veya geç gelen sonuç.")');p.wait_for_timeout(100);assert len(calls)==1
 p.wait_for_function('asr.length===2',timeout=30000);assert p.evaluate('asr[0].aborted');p.get_by_role('button',name='Duraklat',exact=True).click();p.evaluate('asr[1].emit("Duraklatılmış eski olay.")');assert len(calls)==1
 p.get_by_role('button',name='Devam et',exact=True).click();p.wait_for_function('asr.length===3');p.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed');p.evaluate('asr[2].emit("Bitmiş görüşmenin eski olayı.")');assert len(calls)==1
 p.get_by_role('dialog',name='Görüşme tamamlandı').get_by_role('button',name='Tamam',exact=True).click();p.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click();p.wait_for_function('asr.length===4');p.evaluate('asr[2].emit("Önceki görüşmeden gecikmiş.")');assert len(calls)==1
 p.get_by_label('TOGG Attune hizmet onayı',exact=True).uncheck();p.evaluate('asr[3].emit("İzin geri çekildikten sonra.")');assert len(calls)==1;assert p.evaluate('audioProbe.every(a=>a.paused&&!a.getAttribute("src"))')
 p.screenshot(path=str(OUT/'revoked.png'),full_page=True);assert not errors
 (OUT/'proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),controlledASRCallbacks=True,interimIgnored=True,finalAccepted=True,oldEventsBlocked=True,systemAudioNoCapture=True,pauseResume=True,endCleanup=True,consentRevoke=True,providerFixture=True,paidCalls=0,physicalMic=False,recognitionAccuracyAccepted=False,errors=errors),indent=2),'utf8');c.close();b.close()
print('PASS current ASR lifecycle, final/interim, echo isolation, pause/end/revoke and late-session callbacks')
