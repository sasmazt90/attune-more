"""Repeat baseline audit with an independently verified media-capable browser.
The application version under audit is never changed by this harness.
Virtual camera frames are not a clinical or physical-device validation.
"""
import pathlib,json,time,traceback,os,platform
from playwright.sync_api import sync_playwright
OUT=pathlib.Path(os.environ.get('ATTUNE_BROADER_OUT','audit-results/broader')); OUT.mkdir(parents=True,exist_ok=True)
face=str(pathlib.Path('audit-fixtures/valid-face.y4m').resolve())
audio=str(pathlib.Path('audit-fixtures/speech.wav').resolve())
baseargs=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+face,'--autoplay-policy=no-user-gesture-required','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--enable-speech-dispatcher']
preflight=[]; chosen=None
with sync_playwright() as pw:
 preferred='chrome' if platform.system()=='Linux' else 'chromium'
 for channel,headless in [(preferred,True),('chromium' if preferred=='chrome' else 'chrome',True),('chromium',False)]:
  b=None
  try:
   b=pw.chromium.launch(channel=channel,headless=headless,args=baseargs)
   c=b.new_context(permissions=['camera','microphone']); p=c.new_page();p.goto(os.environ.get('ATTUNE_AUDIT_BASE','http://localhost:3000')+'/privacy')
   d=p.evaluate('''async()=>{const timeout=(f)=>Promise.race([f,new Promise((_,r)=>setTimeout(()=>r(Error('media timeout')),8000))]); const out={ua:navigator.userAgent,devices:await navigator.mediaDevices.enumerateDevices().then(ds=>ds.map(d=>({kind:d.kind,label:d.label}))),supported:navigator.mediaDevices.getSupportedConstraints()};for(const kind of ['video','audio']){try{const s=await timeout(navigator.mediaDevices.getUserMedia({[kind]:true}));out[kind]={tracks:s.getTracks().map(t=>({kind:t.kind,state:t.readyState,settings:t.getSettings()}))};if(kind==='video'){const v=document.createElement('video');v.muted=true;v.srcObject=s;document.body.append(v);await timeout(v.play());out.video.width=v.videoWidth;out.video.height=v.videoHeight;}s.getTracks().forEach(t=>t.stop());}catch(e){out[kind]={error:e.name+': '+e.message};}}return out;}''')
   d.update(channel=channel,headless=headless,version=b.version);preflight.append(d);print('MEDIA_PREFLIGHT '+json.dumps(d),flush=True)
   if d.get('video',{}).get('width',0)>0 and chosen is None:chosen={'channel':channel,'headless':headless}
  except Exception as e:preflight.append({'channel':channel,'headless':headless,'error':str(e)})
  finally:
   if b:b.close()
(OUT/'media-preflight.json').write_text(json.dumps(preflight,indent=2))
source=pathlib.Path('tests/e2e/audit_browser.py').read_text()
if chosen is None:
 chosen={'channel':'chromium','headless':True}
 print('MEDIA_NOT_VERIFIED: continue negative tests; do not claim camera E2E passed',flush=True)
os.environ['ATTUNE_BROWSER_CHANNEL']=chosen['channel']
source=source.replace("{'name':'videoCapture'}","{'name':'camera'}")
source=source.replace("page.wait_for_timeout(900);click_toggle(page);snap(page,'vision-driving')", "page.wait_for_timeout(900);require(page.evaluate('window.__audit.streams.some(s=>s.getVideoTracks().some(t=>t.readyState===\"live\"))'),'PRECONDITION: no active camera before driving');click_toggle(page);snap(page,'vision-driving')")
source=source.replace("window.__audit.speech.push({type:k,error:e.error||null,transcript:e.results?.[0]?.[0]?.transcript||null})", "window.__audit.speech.push({type:k,error:e.error||null,transcript:e.results?.[0]?.[0]?.transcript||null})")
extra=r'''
    # Additional actual-user and negative-path regression checks.
    c,page=new()
    def vision_geometry():
        from continuous_vision_contract import manual_calibration_contract
        return manual_calibration_contract(page)
    check('vision manual calibrated symbol without floor; no clinical or practice persistence',vision_geometry);close(c,'vision-geometry')

    c,page=new()
    def mental_fabricated_panels():
        go(page,'/mental');body=page.locator('body').inner_text();snap(page,'mental-panels');require('4 Seans Analiz Edildi' not in body,'Four nonexistent analyzed sessions shown to a first-time user');require('75' not in body,'Unmeasured theme percentage shown')
    check('mental fresh-user insight panels contain no invented statistics',mental_fabricated_panels)
    def mental_api_outage():
        page.route('**/api/mental/converse',lambda r:r.abort());text_input('Bugün yeni bir kitap okudum.');snap(page,'mental-api-outage');body=page.locator('body').inner_text().lower();require('son konuşmalarımızda' not in body,'API failure fallback invents prior patient history');require('bağlantı' in body or 'ulaşılamıyor' in body,'API outage not disclosed')
    check('mental API outage transparently disclosed without invented history',mental_api_outage)
    close(c,'mental-negative')

    c,page=new()
    def mental_upper_crisis():
        go(page,'/mental?demo=1')
        # Crisis content/guard remain real; the requested TTS transport is denied
        # by the keyless fixture, never replaced by an alternate production voice.
        text_input('İNTİHAR ETMEK İSTİYORUM',expect_crisis=True)
        snap(page,'mental-uppercase-crisis')
        require('112' in page.locator('[data-chat-author="AI"]').last.inner_text(),'Uppercase Turkish crisis not escalated in actual reply')
        require(page.locator('[data-chat-author="AI"]').count()==1,'Crisis duplicated a response')
    check('mental Turkish uppercase crisis escalation',mental_upper_crisis);close(c,'mental-upper')

    c,page=new()
    def wipe_outage():
        api('/api/mental/sessions',{'summaryText':'AUDIT ONLY backend deletion outage','recurringThemes':[],'saveMentalSummaries':True})
        go(page,'/privacy');page.route('**/api/privacy/wipe',lambda r:r.abort());page.get_by_role('button',name='TÜM YEREL VERİLERİ SİL',exact=True).click();page.get_by_role('button',name='Evet, Tüm Verileri Sil',exact=True).click();page.wait_for_timeout(700);snap(page,'privacy-wipe-outage')
        records=api('/api/mental/sessions');require(not records or 'Tüm yerel veriler başarıyla temizlendi.' not in page.locator('body').inner_text(),'Deletion success claimed while backend health summaries remain')
    check('privacy deletion failure not falsely reported as success',wipe_outage);close(c,'privacy-outage');api('/api/privacy/wipe',{})

    c,page=new()
    def skin_missing_model():
        page.route('**/face_landmarker.task',lambda r:r.abort());page.route('**/wasm/**',lambda r:r.abort());go(page,'/skin');page.wait_for_timeout(3000);page.get_by_role('button',name='Analizi Başlat',exact=True).click();page.wait_for_timeout(2500);snap(page,'skin-model-offline');require(not page.evaluate('localStorage.getItem("togg_health_latest_skin")'),'Fabricated result persisted without model');require('başlatılamadı' in page.locator('body').inner_text().lower(),'Model failure has no clear retry/error state')
    check('skin model network failure safe with no measurement persistence',skin_missing_model);close(c,'skin-offline')

    c,page=new()
    def corrupt_storage():
        go(page,'/privacy');page.evaluate('localStorage.setItem("togg_health_latest_skin","{");localStorage.setItem("togg_health_latest_vision","{");localStorage.setItem("togg_health_latest_mental","{")');go(page,'/');snap(page,'corrupt-storage');require('Application error' not in page.locator('body').inner_text(),'Corrupted user storage crashes app')
    check('corrupt persisted JSON does not crash dashboard',corrupt_storage);close(c,'corrupt-data')

    c,page=new()
    def privacy_mic():
        go(page,'/privacy');page.get_by_role('button',name='Erişimi Kapat',exact=True).nth(1).click();page.get_by_role('link',name='Ruhsal İyi Oluş',exact=True).click();page.wait_for_timeout(800);page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click();snap(page,'privacy-mic-off');require('Mikrofon kullanım izni Gizlilik ayarlarında kapalıdır' in page.locator('body').inner_text(),'App microphone preference ignored');require(not page.evaluate('window.__audit.speech.some(e=>e.type==="start")'),'Recognition starts without app permission')
    check('privacy microphone off blocks listening and offers typing',privacy_mic);close(c,'privacy-mic')
'''
source=source.replace('    browser.close()\n',extra+'\n    browser.close()\n')
(OUT/'executed-harness.py').write_text(source)
exec(compile(source,'audit_browser_v2_expanded.py','exec'),{'__name__':'__main__'})
