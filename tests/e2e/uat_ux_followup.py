from vehicle_controls import toggle_vehicle, vehicle_status
from continuous_vision_contract import selector_contract, manual_calibration_contract
"""Keyless UAT: actual production UI/API, explicit UI saving consent and UX faults.
Controlled delays/permission faults are labelled; no fake provider/STT/MediaPipe success.
"""
import argparse,json,os,subprocess,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
assert not os.getenv('OPENAI_API_KEY') and os.getenv('ATTUNE_LOAD_LOCAL_ENV')=='0'
OUT=Path('audit-results/uat-20261003')/('before-states' if args.baseline else 'after');OUT.mkdir(parents=True,exist_ok=True)
BASE='http://localhost:3000';API='http://localhost:8000';results=[];screens=[]
INIT='''window.captureAttempts=0;const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=function(){window.captureAttempts++;throw new DOMException('Controlled denied microphone','NotAllowedError')};navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new DOMException('Controlled denied media','NotAllowedError'))};'''
def snap(page,name,full=False):
 if not page.locator('[aria-modal="true"]').count():
  page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(100)
 if page.locator('[aria-modal="true"]').count():full=False
 page.screenshot(path=str(OUT/(name+'.png')),full_page=full,animations='disabled');screens.append({'file':name+'.png','route':page.url.removeprefix(BASE),'viewport':page.viewport_size,'actualImageReviewPending':True})
def record(name,fn):
 try:detail=fn();result={'name':name,'status':'PASS','detail':detail}
 except Exception as error:result={'name':name,'status':'FAIL','error':str(error),'traceback':traceback.format_exc()}
 results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required'])
 def fresh(width=1280,height=900):
  context=browser.new_context(viewport={'width':width,'height':height},locale='tr-TR');context.add_init_script(INIT)
  context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0});page=context.new_page();return context,page
 def start(page):
  page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
  mute=page.get_by_role('button',name='Sesli yanıtı kapat',exact=True)
  if mute.count():mute.click()
 def send(page,text):
  old=page.locator('[data-chat-author="AI"]').count();box=page.get_by_role('textbox',name='Görüşme mesajı');expect(box).to_be_enabled();box.fill(text);box.press('Enter')
  expect(page.locator('[data-chat-author="AI"]')).to_have_count(old+1);expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready')
 def finish(page):
  page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
  page.get_by_role('dialog',name='Görüşme tamamlandı',exact=True).get_by_role('button',name='Tamam',exact=True).click()
 def history(page):return page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]")')
 def modal_checks(page,caller,title,name):
  caller.click();dialog=page.get_by_role('dialog',name=title,exact=True)
  if not args.baseline:
   expect(dialog).to_be_visible();page.wait_for_function('document.querySelector("[role=dialog]")?.contains(document.activeElement)');snap(page,name+'-focus')
   rect=dialog.bounding_box();assert rect['y']>=15 and rect['y']+rect['height']<=page.viewport_size['height']-15, {'dialog':rect,'viewport':page.viewport_size}
   for _ in range(12):page.keyboard.press('Tab');assert dialog.evaluate('e=>e.contains(document.activeElement)')
   page.keyboard.press('Shift+Tab');assert dialog.evaluate('e=>e.contains(document.activeElement)')
  snap(page,name);page.keyboard.press('Escape')
  if not args.baseline:expect(dialog).to_have_count(0);assert caller.evaluate('e=>e===document.activeElement')

 def routes():
  evidence=[]
  for w,h in [(1280,900),(390,844),(820,900)]:
   c,page=fresh(w,h)
   try:
    for route in ['','skin','vision','mental','profile','privacy','care']:
     page.goto(BASE+'/'+route);expect(vehicle_status(page)).to_contain_text('PARK');page.wait_for_timeout(400)
     assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
     brand=page.locator('header a').filter(has=page.get_by_alt_text('Togg',exact=True)).bounding_box();park=vehicle_status(page).bounding_box()
     overlap=brand['x']<park['x']+park['width'] and brand['x']+brand['width']>park['x'] and brand['y']<park['y']+park['height'] and brand['y']+brand['height']>park['y']
     if not args.baseline:assert not overlap
     snap(page,f'{route or "home"}-empty-{w}',True);evidence.append({'route':'/'+route,'viewport':[w,h],'brandParkOverlap':overlap})
    assert page.evaluate('window.captureAttempts')==0
   finally:c.close()
  return evidence
 record('Seven routes at desktop small and intermediate widths; bounded header',routes)

 def consent():
  c,page=fresh(390,844)
  try:
   page.goto(BASE+'/privacy');page.get_by_role('button',name='Devre Dışı Bırak',exact=True).click();assert page.evaluate('localStorage.getItem("togg_privacy_mental_summary_allowed")')=="false"
   snap(page,'privacy-saving-off',True)
   page.goto(BASE+'/mental');start(page);send(page,'Bugün yeni bir kitap okudum.');assert history(page)==[];finish(page);assert history(page)==[];snap(page,'mental-completed-saving-off',True)
   page.goto(BASE+'/privacy');page.get_by_role('button',name='Etkinleştir',exact=True).click();snap(page,'privacy-saving-explicit-on',True)
   for i,text in enumerate(['Ailemle güzel bir kitap okudum.','İş projemi bitirdim ve ailemle sohbet ettim.']):
    page.goto(BASE+'/mental');start(page);send(page,text);assert len(history(page))==i;finish(page);saved=history(page);assert len(saved)==i+1 and saved[-1]['completed'] and saved[-1]['consented'] and saved[-1]['schemaVersion']==3 and 'transcript' not in saved[-1]
    page.wait_for_timeout(250);assert len(history(page))==i+1
   snap(page,'mental-two-completed-390',True)
   page.get_by_role('button',name='sosyal ilişkiler:',exact=False).click();expect(page.locator('[data-selected-theme]')).to_contain_text('sosyal ilişkiler');snap(page,'mental-selected-theme-390',True)
   statsText=page.locator('[data-mental-history]').inner_text();assert '2 tamamlanmış izinli görüşme' in statsText and '3 tema kaydı' in statsText
   page.goto(BASE+'/privacy');snap(page,'privacy-two-records',True)
   if not args.baseline:expect(page.get_by_text('Görüşme Özetleri',exact=True).locator('..')).to_contain_text('2')
   page.goto(BASE+'/profile');modal_checks(page,page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True),'Hekim Paylaşım Özeti','profile-two-record-modal') if not args.baseline else None
   page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click();assert page.get_by_role('checkbox').evaluate_all('(a)=>a.every(i=>!i.checked)')
   page.get_by_label('Ruhsal iyi oluş',exact=True).check();preview=page.locator('[data-share-preview]').inner_text();assert 'Ruhsal iyi oluş' in preview and 'Cilt' not in preview and 'Görme' not in preview;snap(page,'profile-selected-mental-only',True)
   return {'savingOffCompletedRecords':0,'explicitUIOnCompletedRecords':2,'noDuplicateSummary':True,'themes':3,'captureAttempts':page.evaluate('window.captureAttempts'),'actualValidationStorageBackend':True,'generationFixture':True,'liveAcceptance':False}
  finally:c.close()
 record('Local saving OFF and explicit ON through actual privacy UI; exact chart and export selection',consent)

 def revoke():
  c,page=fresh();pending=[]
  try:
   page.goto(BASE+'/mental');start(page);send(page,'Ailemle güzel bir kitap okudum.')
   page.route('**/api/mental/analyze-session',lambda route:pending.append(route));page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();page.wait_for_timeout(100);assert len(pending)==1
   other=c.new_page();other.goto(BASE+'/privacy');other.get_by_role('button',name='Devre Dışı Bırak',exact=True).click()
   response=pending[0].fetch();pending[0].fulfill(response=response);expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed');assert history(page)==[]
   page.get_by_role('dialog',name='Görüşme tamamlandı',exact=True).get_by_role('button',name='Tamam',exact=True).click()
   snap(page,'mental-ui-revoked-before-save');return {'lateUIRevocationPreventedStorage':True,'summaryActualBackend':True}
  finally:c.close()
 record('Privacy UI in another tab revokes saving while actual summary is pending',revoke)

 def summary_cancel():
  c,page=fresh();pending=[]
  try:
   page.goto(BASE+'/mental');start(page);send(page,'Bugün yeni bir kitap okudum.');page.route('**/api/mental/analyze-session',lambda route:pending.append(route));page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();page.wait_for_timeout(100);assert len(pending)==1;snap(page,'mental-summary-wait')
   if args.baseline:return {'previousCancelVisible':page.get_by_role('button',name='Özet hazırlamayı iptal et',exact=True).count()==1}
   page.get_by_role('button',name='Özet hazırlamayı iptal et',exact=True).click();response=pending[0].fetch();pending[0].fulfill(response=response);page.wait_for_timeout(300);expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');assert history(page)==[] and page.locator('[data-current-summary]').count()==0;snap(page,'mental-summary-cancelled');return {'lateSummaryIgnored':True}
  finally:c.close()
 record('Final summary can be cancelled and late response cannot restore it',summary_cancel)

 def waiting_audio():
  c,page=fresh();chat=[];tts=[]
  try:
   page.route('**/api/mental/provider-status',lambda route:route.fulfill(json={'apiKeyConfigured':True,'providerName':'UI capability fixture only; no key','isLiveLLM':False}))
   page.goto(BASE+'/mental');page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
   page.route('**/api/mental/converse',lambda route:chat.append(route));page.route('**/api/mental/speech',lambda route:tts.append(route));page.get_by_role('textbox',name='Görüşme mesajı').fill('Bugün yeni bir kitap okudum.');page.get_by_role('button',name='Gönder',exact=True).click();page.wait_for_timeout(100);assert len(chat)==1;snap(page,'mental-chat-wait')
   expect(page.locator('[data-conversation-phase]')).to_contain_text('Yanıt hazırlanıyor')
   response=chat[0].fetch();assert response.json()['providerType']=='LIVE_OPENAI';chat[0].fulfill(response=response);expect(page.locator('[data-chat-author="AI"]')).to_have_count(1);page.wait_for_timeout(100);assert len(tts)==1
   snap(page,'mental-audio-wait')
   if not args.baseline:expect(page.locator('[data-conversation-phase]')).to_contain_text('Ses hazırlanıyor')
   text=page.locator('[data-chat-author="AI"]').inner_text();assert 'LOCAL_DEMO' not in text and 'LIVE_OPENAI' not in text;assert page.locator('[data-provider-kind=LIVE_OPENAI]').count()==1
   response=tts[0].fetch();assert response.status==503;tts[0].fulfill(response=response);expect(page.locator('[data-voice-state]')).to_have_attribute('data-voice-state','failed');assert page.locator('[data-chat-author="AI"]').inner_text()==text;snap(page,'mental-audio-error-text-retained')
   return {'actualChat':'KEYLESS_GENERATION_FIXTURE','actualTTSHTTP':503,'textRetained':True,'UIConfiguredFixtureNotLiveProof':True,'captureAttempts':page.evaluate('window.captureAttempts')}
  finally:c.close()
 record('Chat wait and voice wait are distinct; actual keyless TTS failure retains text',waiting_audio)

 def mute_pending():
  c,page=fresh();pending=[]
  try:
   page.route('**/api/mental/provider-status',lambda route:route.fulfill(json={'apiKeyConfigured':True,'isLiveLLM':False}));page.goto(BASE+'/mental');page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
   page.route('**/api/mental/speech',lambda route:pending.append(route));page.get_by_role('textbox',name='Görüşme mesajı').fill('Bugün yeni bir kitap okudum.');page.get_by_role('button',name='Gönder',exact=True).click();expect(page.locator('[data-chat-author="AI"]')).to_have_count(1);page.wait_for_timeout(100);assert len(pending)==1
   page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');pending[0].abort();page.wait_for_timeout(200);expect(page.locator('[data-voice-state]')).to_have_attribute('data-voice-state','ready');assert len(history(page))==0;return {'voiceCancelledWithoutTextLoss':True}
  finally:c.close()
 record('Muting during TTS preparation cancels waiting work without late error',mute_pending)

 def short_modals():
  c,page=fresh(390,500)
  try:
   page.goto(BASE+'/profile');modal_checks(page,page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True),'Hekim Paylaşım Özeti','profile-modal-short')
   page.goto(BASE+'/skin?demo=1');page.get_by_role('button',name='Analizi Başlat',exact=True).click();expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=45000)
   for button,title,name in [('Gözlem Notu','Gözlem Notu','skin-note-short'),('Zaman İçinde Değişim','Zaman İçinde Değişim','skin-trend-short'),('Önerilen Aksiyonlar','Önerilen Aksiyonlar','skin-actions-short')]:modal_checks(page,page.get_by_role('button',name=button,exact=True),title,name)
   return {'viewport':[390,500],'escapeTrapAndReturn':not args.baseline,'skinFixture':'Explicit demo only, not actual baseline evidence'}
  finally:c.close()
 record('Four short-height modals fit; focus trapped, Escape and focus return',short_modals)

 def errors_driving():
  c,page=fresh(390,844)
  try:
   page.goto(BASE+'/privacy');buttons=page.get_by_role('button',name='Erişimi Kapat',exact=True);buttons.nth(0).click();page.get_by_role('button',name='Erişimi Kapat',exact=True).click();snap(page,'privacy-app-media-off',True)
   page.goto(BASE+'/skin');page.get_by_role('button',name='Analizi Başlat',exact=True).click();expect(page.get_by_role('button',name='Tekrar Dene',exact=True)).to_be_visible();snap(page,'skin-permission-off',True)
   page.goto(BASE+'/mental');page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click();expect(page.get_by_text('Mikrofon kullanım izni Gizlilik ayarlarında kapalıdır.',exact=False)).to_be_visible();assert page.evaluate('window.captureAttempts')==0
   page.route('**/api/mental/converse',lambda r:r.abort());page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click();page.get_by_role('textbox',name='Görüşme mesajı').fill('Sentetik kesinti kontrolü');page.get_by_role('button',name='Gönder',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','error');snap(page,'mental-api-outage',True)
   page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();assert history(page)==[]
   toggle_vehicle(page);expect(vehicle_status(page)).to_contain_text('SÜRÜŞ')
   for route in ['skin','vision','mental','care','profile']:
    page.goto(BASE+'/'+route);snap(page,route+'-driving',True)
   assert page.evaluate('window.captureAttempts')==0;return {'failedRecords':0,'captureAttempts':0,'drivingRoutes':5}
  finally:c.request.post(API+'/api/vehicle/speed',data={'speedKmH':0});c.close()
 record('UI media denial, actual API outage and driving states preserve empty records',errors_driving)

 def care_states():
  c,page=fresh(390,844);pending=[]
  try:
   page.route('**/api/care/match',lambda route:pending.append(route));page.goto(BASE+'/care');page.wait_for_timeout(500);assert pending, 'Care request did not start';snap(page,'care-loading',True)
   if not args.baseline:expect(page.get_by_role('status')).to_contain_text('Uzman seçenekleri hazırlanıyor')
   pending.pop(0).abort();expect(page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True)).to_be_visible();snap(page,'care-service-error-demo',True)
   if not args.baseline:expect(page.get_by_text('Uzman arama hizmetine ulaşılamadı.',exact=False)).to_be_visible()
   modal_checks(page,page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True),'Kullanıcı Onayı ve Sevk Bağlamı','care-consent-modal')
   return {'controlledActualNetworkFailure':True,'demoDistinguished':not args.baseline}
  finally:c.close()
 record('Care loading/error/demo and consent modal states',care_states)

 def vision_long_reflow():
  c,page=fresh(390,844)
  try:
   layouts=[]
   for width in [390,820,1280]:
    page.set_viewport_size({'width':width,'height':844 if width==390 else 900})
    result=selector_contract(page,OUT,f'vision-active-{width}')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    layouts.append({'width':width,'spokenLetterUI':result['spokenLetterUI'],'manualCardRemoved':result['manualCardRemoved'],'scoresCreated':result['scoresCreated']})
   page.set_viewport_size({'width':1280,'height':900});page.goto(BASE+'/mental');start(page)
   text='Sentetik uzun görüşme kontrolü. '+('Ailemle bir kitap okuduk ve günümüzü konuştuk. '*18)
   for i in range(4):send(page,text+str(i))
   assert page.locator('[data-chat-author="USER"]').count()==4 and page.locator('[data-chat-author="AI"]').count()==4;snap(page,'mental-long-transcript-1280',True);finish(page);snap(page,'mental-long-completed-1280',True)
   page.set_viewport_size({'width':390,'height':844});snap(page,'mental-long-completed-390',True)
   page.set_viewport_size({'width':1280,'height':900})
   for route in ['mental','profile','privacy']:
    page.goto(BASE+'/'+route);page.evaluate('document.body.style.zoom="2"');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');snap(page,route+'-css-reflow-200',True);page.evaluate('document.body.style.zoom=""')
   return {'visionLayouts':layouts,'longTurns':4,'reflow':'200% CSS zoom layout check; not OS/browser zoom acceptance','provider':'keyless synthetic generation fixture'}
  finally:c.close()
 record('Measured vision panels at three widths; long actual transcript and 200 percent reflow',vision_long_reflow)
 browser.close()
(OUT/'results.json').write_text(json.dumps({'results':results,'screenshots':screens,'liveProviderEvidence':False,'sourceHead':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'productionBuildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'actualSourceVersion':'baseline build' if args.baseline else 'current production build'},ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(1 if any(r['status']=='FAIL' for r in results) else 0)
