"""Production controller races/permissions/history with declared provider fixtures.
No provider requests, microphone hardware or speech recognition accuracy claim.
The separate bounded ledger is the only live-provider evidence.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/mental-control';OUT.mkdir(parents=True,exist_ok=True)
proof=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True)
 for mode in ['summary-only','transcript','storage-off','late-response','provider-error','bye','permission-revoke']:
  c=b.new_context(viewport={'width':1600,'height':1000});p=c.new_page();calls=[];pending=[];errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  def route(r):
   path=r.request.url.split('?')[0];body=r.request.post_data_json if r.request.post_data else {}
   if path.endswith('/converse'):
    calls.append(body)
    if mode in ['late-response','permission-revoke']:pending.append(r);return
    if mode=='provider-error':r.fulfill(status=503,json={'detail':'PROVIDER_NETWORK'});return
    if body['userMessage']=='Görüşmeyi bitir.':r.fulfill(json={'reply':'Görüşme sonlandırılıyor.','providerType':'CONVERSATION_CONTROL','sessionAction':'finish'});return
    # LIVE_OPENAI is the controller's expected label, deliberately fixture-only.
    r.fulfill(json={'reply':'Kontrollü sağlayıcı yanıtı.','providerType':'LIVE_OPENAI'})
   elif path.endswith('/analyze-session'):r.fulfill(json={'summaryText':'Kişisel olmayan kontrollü oturum.','themes':['kitap'],'moodTrend':'NEUTRAL','providerType':'LIVE_OPENAI'})
   elif path.endswith('/provider-status'):r.fulfill(json={'isLiveLLM':True,'providerName':'CONTROLLED FIXTURE','apiKeyConfigured':False})
   else:r.abort()
  p.route('**/api/mental/**',route)
  c.add_init_script("navigator.mediaDevices.getUserMedia=()=>Promise.reject(Error('Physical device forbidden'));window.__controlledProvider=true;")
  p.goto('http://127.0.0.1:3000/privacy')
  if mode=='transcript':p.get_by_label('Tam konuşma dökümünü bu cihazda sakla',exact=True).check()
  if mode=='storage-off':p.evaluate('localStorage.setItem("togg_privacy_mental_summary_allowed","false")')
  p.goto('http://127.0.0.1:3000/mental');p.get_by_label('TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click();p.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click()
  box=p.get_by_role('textbox',name='Görüşme mesajı')
  for i,text in enumerate(['Bugün bir kitap okudum.','Kitap hakkında konuşmayı sürdürüyorum.','Bu kontrollü bir kullanım denemesidir.'] if mode in ['summary-only','transcript','storage-off'] else ['Görüşmeyi bitir.' if mode=='bye' else 'Kontrollü gecikme veya hata denemesi.']):
   box.fill(text);p.get_by_role('button',name='Gönder',exact=True).click()
   if mode in ['late-response','permission-revoke','provider-error','bye']:break
   expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');assert p.evaluate('!localStorage.getItem("togg_health_mental_history")')
  if mode in ['summary-only','transcript','storage-off']:
   assert [len(v['history']) for v in calls]==[0,2,4]
   p.get_by_role('button',name='Duraklat',exact=True).click();expect(box).to_be_disabled();p.get_by_role('button',name='Devam et',exact=True).click();expect(box).to_be_enabled()
  if mode=='permission-revoke':
   p.get_by_label('TOGG Attune hizmet onayı',exact=True).uncheck();pending[0].fulfill(json={'reply':'UNWANTED LATE FIXTURE','providerType':'LIVE_OPENAI'});p.wait_for_timeout(200);assert 'UNWANTED LATE FIXTURE' not in p.locator('body').inner_text()
  elif mode=='late-response':
   p.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();pending[0].fulfill(json={'reply':'UNWANTED LATE FIXTURE','providerType':'LIVE_OPENAI'});p.wait_for_timeout(200);assert 'UNWANTED LATE FIXTURE' not in p.locator('body').inner_text()
  elif mode=='provider-error':expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','error')
  else:
   if mode!='bye':p.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click()
   expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
   p.get_by_role('dialog',name='Görüşme tamamlandı').get_by_role('button',name='Tamam',exact=True).click()
  records=p.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]")')
  expect_saved=mode in ['summary-only','transcript','bye'];assert len(records)==int(expect_saved)
  if records:assert records[0]['completed'] and records[0]['consented'] and bool(records[0].get('transcript'))==(mode=='transcript')
  p.screenshot(path=str(OUT/(mode+'.png')),full_page=True)
  if records:
   p.goto('http://127.0.0.1:3000/mental');record=p.locator('[data-record-id="'+records[0]['id']+'"]');record.get_by_text('Sil',exact=True).click();p.get_by_role('button',name='Evet, sil',exact=True).click();p.reload();assert p.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]").length')==0
  assert not errors;proof.append(dict(mode=mode,passed=True,frontendHistoryLengths=[len(v.get('history',[])) for v in calls],saved=int(expect_saved),providerFixture=True,liveAPI=False,physicalMic=False));c.close()
 b.close()
(OUT/'proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),cases=proof),indent=2),'utf8');print(json.dumps(proof))
