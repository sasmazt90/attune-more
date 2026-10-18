from vehicle_controls import toggle_vehicle, vehicle_status
from continuous_vision_contract import selector_contract
"""Independent browser audit. Runs production app with genuine Chromium media APIs.
Face/audio files are controlled virtual-device fixtures, not clinical validation.
No real appointments, payments, API credentials or external writes are used.
"""
import json, math, os, pathlib, platform, re, time, traceback
import httpx
from playwright.sync_api import sync_playwright, expect

OUT = pathlib.Path(os.environ.get('ATTUNE_BROADER_OUT','audit-results/broader')); OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('ATTUNE_AUDIT_BASE','http://localhost:3000'); API=os.environ.get('ATTUNE_API_BASE','http://localhost:8000')
results=[]
INIT=r'''(() => {
 window.__audit={streams:[],tts:[],speech:[]};
 const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
 navigator.mediaDevices.getUserMedia=async(...args)=>{const s=await gum(...args);window.__audit.streams.push(s);return s;};
 if(window.speechSynthesis){const speak=speechSynthesis.speak.bind(speechSynthesis);speechSynthesis.speak=(u)=>{window.__audit.tts.push({text:u.text,lang:u.lang});return speak(u);};}
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(SR){const Wrapped=function(){const s=new SR();['start','audiostart','end','error','result'].forEach(k=>s.addEventListener(k,e=>window.__audit.speech.push({type:k,error:e.error||null,transcript:e.results?.[0]?.[0]?.transcript||null})));return s;};window.SpeechRecognition=Wrapped;window.webkitSpeechRecognition=Wrapped;}
})();'''

def check(name, fn):
    started=time.time()
    try:
        detail=fn(); item={'name':name,'status':'PASS','detail':detail}
    except Exception as exc:
        item={'name':name,'status':'FAIL','error':str(exc),'traceback':traceback.format_exc(limit=3)}
    item['seconds']=round(time.time()-started,2);results.append(item)
    print('AUDIT_RESULT '+json.dumps(item,ensure_ascii=False),flush=True)

def require(condition, message):
    if not condition: raise AssertionError(message)

def api(path, data=None):
    with httpx.Client(timeout=45,trust_env=False) as client:
        r=client.get(API+path) if data is None else client.post(API+path,json=data)
        r.raise_for_status();return r.json()

with sync_playwright() as pw:
    args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(pathlib.Path('audit-fixtures/valid-face.y4m').resolve()),'--autoplay-policy=no-user-gesture-required','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']
    channel=os.environ.get('ATTUNE_BROWSER_CHANNEL','chrome' if platform.system()=='Linux' else 'chromium')
    browser=pw.chromium.launch(channel=channel,headless=True,args=args+['--enable-speech-dispatcher'])
    def new(permissions=True, width=1600, height=1000):
        api('/api/vehicle/speed',{'speedKmH':0})
        c=browser.new_context(viewport={'width':width,'height':height},permissions=['camera','microphone'] if permissions else [],locale='tr-TR')
        c.add_init_script(INIT)
        if os.environ.get('ATTUNE_TRACE')=='1':c.tracing.start(screenshots=True,snapshots=True,sources=True)
        page=c.new_page();page.set_default_timeout(7000)
        page._audit_errors=[];page._audit_console=[];page._audit_requests=[]
        page.on('pageerror',lambda e:page._audit_errors.append(str(e)))
        page.on('console',lambda m:page._audit_console.append({'type':m.type,'text':m.text}))
        page.on('requestfailed',lambda r:page._audit_requests.append({'url':r.url,'failure':r.failure}))
        return c,page
    def go(page,path):
        response=page.goto(BASE+path,wait_until='domcontentloaded',timeout=30000)
        require(response.status==200,'HTTP '+str(response.status));page.wait_for_timeout(900)
    def snap(page,name):
        page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
        (OUT/(name+'.json')).write_text(json.dumps({'url':page.url,'body':page.locator('body').inner_text(),'buttons':page.get_by_role('button').all_text_contents(),'errors':page._audit_errors,'console':page._audit_console,'failedRequests':page._audit_requests,'storage':page.evaluate('Object.fromEntries(Object.entries(localStorage))'),'media':page.evaluate('({tracks:window.__audit.streams.flatMap(s=>s.getTracks().map(t=>({kind:t.kind,state:t.readyState}))),tts:window.__audit.tts,speech:window.__audit.speech})')},ensure_ascii=False,indent=2))
    def close(c,name):
        if os.environ.get('ATTUNE_TRACE')=='1':c.tracing.stop(path=str(OUT/(name+'.trace.zip')))
        c.close()
    def click_toggle(page):
        toggle_vehicle(page)
        page.wait_for_function("document.querySelector('[data-vehicle-status]')?.innerText.includes('SÜRÜŞ')")

    c,page=new()
    for route in ['/','/vision','/skin','/mental','/care','/profile','/privacy']:
        def route_test(route=route):
            page._audit_errors.clear();go(page,route);page.wait_for_timeout(1500 if route=='/care' else 200)
            name=route.strip('/') or 'dashboard';snap(page,'route-'+name)
            require(not page._audit_errors,'Uncaught JavaScript errors: '+str(page._audit_errors))
            return {'buttons':page.get_by_role('button').all_text_contents()}
        check('route '+route,route_test)
    close(c,'routes')

    c,page=new()
    def vision_setup():
        go(page,'/vision');page.get_by_role('button',name='Başlat').click();page.wait_for_timeout(1600);snap(page,'vision-camera')
        live=page.evaluate('window.__audit.streams.some(s=>s.getVideoTracks().some(t=>t.readyState==="live"))')
        require(live,'Application did not acquire a live video track')
        require(page.locator('video').evaluate('(v)=>v.videoWidth>0 && v.readyState>=2'),'Camera preview has no decoded frames')
        return 'Actual getUserMedia video track and decoded preview frames'
    check('vision camera acquisition and preview',vision_setup)
    def vision_complete():
        require(page.locator('[data-letter-optotype]').count()==0,'Unverified eye conditions permit presentation')
        require(not page.evaluate('localStorage.getItem("togg_health_latest_vision")'),'Unverified camera produced a result')
        page.goto(BASE+'/vision');return selector_contract(page,OUT,'vision-spoken-ui')
    check('vision continuous selector; unverified occlusion blocks measurement/persistence',vision_complete)
    def vision_profile():
        page.get_by_role('link',name='Sağlık Geçmişim').click();page.wait_for_timeout(600);snap(page,'vision-profile');require('Henüz tamamlanmış görme değerlendirmesi' in page.locator('body').inner_text(),'Practice falsely reported as a measured result')
    check('vision practice absent from measured health profile',vision_profile)
    close(c,'vision-flow')

    c,page=new()
    def vision_stop():
        go(page,'/vision');page.get_by_role('button',name='Başlat').click();page.wait_for_timeout(900);click_toggle(page);snap(page,'vision-driving')
        require(page.get_by_role('button',name='Başlat').count()==0,'No driving lock')
        require(not page.evaluate('window.__audit.streams.some(s=>s.getTracks().some(t=>t.readyState==="live"))'),'Camera remains LIVE after driving lock')
    check('vision driving lock stops active camera',vision_stop)
    def driving_sync():
        backend=api('/api/vehicle/state');require(backend['vehicleMoving'],'UI driving state is not synchronized to backend');return backend
    check('frontend backend driving state synchronization',driving_sync)
    close(c,'vision-driving');api('/api/vehicle/speed',{'speedKmH':0})

    c,page=new()
    def skin_real():
        go(page,'/skin');page.wait_for_timeout(9000);(page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button',name='Analizi Başlat',exact=True).click()
        try:page.wait_for_function('localStorage.getItem("togg_health_latest_skin")!==null',timeout=30000)
        finally:snap(page,'skin-real')
        record=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
        require(record and record.get('usedMediaPipe') is True,'Real MediaPipe result not saved')
        require(record.get('isBaseline') is True,'First real scan not marked baseline');require(len(record.get('regions',{}))==6,'Missing six anatomical regions')
        require(record['quality']['isValid'] and record['quality']['blurScore']>=4.0,'Fixture did not pass unchanged real quality threshold')
        require(record['highestChangePct']==0 and record['referralSuggested'] is False,'First real baseline invented change or referral')
        return record
    check('skin real camera MediaPipe six-region baseline',skin_real)
    def skin_second():
        previous=page.evaluate('localStorage.getItem("togg_health_latest_skin")')
        require(previous,'Baseline prerequisite not met')
        go(page,'/skin');page.wait_for_timeout(4000);(page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button',name='Analizi Başlat',exact=True).click()
        page.wait_for_function('(prev)=>localStorage.getItem("togg_health_latest_skin")!==prev',arg=previous,timeout=30000)
        record=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))');snap(page,'skin-repeat');require(record.get('isBaseline') is False,'Second scan still baseline')
        require(len(page.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_history"))'))==2,'Skin history not retained')
        baseline=page.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_baseline"))')
        for region,metrics in record['regions'].items():
            original=baseline[region]['rednessScore']
            delta=math.floor((metrics['rednessScore']-original)/original*100+.5) if original>0 else 0
            require(metrics['changeFromBaselinePct']==delta,'Repeat region does not compare to actual UI-generated baseline: '+region)
        return record
    check('skin second scan actual baseline comparison',skin_second)
    def skin_demo():
        before=page.evaluate('localStorage.getItem("togg_health_latest_skin")');go(page,'/skin?demo=1');(page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button',name='Analizi Başlat',exact=True).click()
        page.wait_for_function('localStorage.getItem("attune_demo_skin_result")!==null',timeout=12000);snap(page,'skin-demo')
        require(page.evaluate('localStorage.getItem("togg_health_latest_skin")')==before,'Demo overwrote real result')
        require(page.evaluate('JSON.parse(localStorage.getItem("attune_demo_skin_result")).usedMediaPipe') is False,'Demo incorrectly claims MediaPipe measurement')
    check('skin demo separated from real data',skin_demo)
    close(c,'skin-flow')

    c,page=new()
    def skin_stop():
        go(page,'/skin');(page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button',name='Analizi Başlat',exact=True).click();page.wait_for_timeout(500);click_toggle(page);snap(page,'skin-driving')
        require(page.get_by_text('Cilt Kontrolü Kilitlendi').is_visible(),'No skin driving lock')
        require(not page.evaluate('window.__audit.streams.some(s=>s.getTracks().some(t=>t.readyState==="live"))'),'Skin camera remains LIVE during driving')
    check('skin driving lock stops camera',skin_stop);close(c,'skin-driving')

    c,page=new()
    def privacy_camera():
        go(page,'/privacy');page.get_by_role('button',name='Erişimi Kapat',exact=True).first.click();require(page.evaluate('localStorage.getItem("attune_privacy_camera_allowed")')=='false','Camera preference not stored')
        page.get_by_role('link',name='Cilt Kontrolü',exact=True).click();page.wait_for_timeout(400);(page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button',name='Analizi Başlat',exact=True).click();snap(page,'privacy-camera-off');require('Gizlilik' in page.locator('body').inner_text(),'Missing privacy error')
        require(page.evaluate('window.__audit.streams.length')==0,'Camera acquired despite app refusal')
    check('privacy camera off prevents capture',privacy_camera);close(c,'privacy-camera')

    c,page=new(False)
    def camera_denied():
        session=c.new_cdp_session(page)
        info=session.send('Target.getTargetInfo')['targetInfo']
        session.send('Browser.setPermission',{'permission':{'name':'camera'},'setting':'denied','origin':BASE,'browserContextId':info['browserContextId']})
        go(page,'/privacy')
        require(page.evaluate('navigator.permissions.query({name:"camera"}).then(p=>p.state)')=='denied','Native camera permission was not denied')
        rejection=page.evaluate('async()=>{try{const s=await navigator.mediaDevices.getUserMedia({video:true});s.getTracks().forEach(t=>t.stop());return "unexpected acquisition";}catch(e){return e.name;}}')
        require(rejection=='NotAllowedError','Genuine browser denial missing: '+rejection)
        go(page,'/skin');page.wait_for_timeout(3000);(page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button',name='Analizi Başlat',exact=True).click();page.wait_for_timeout(1000);snap(page,'camera-browser-denied');require(not page.evaluate('localStorage.getItem("togg_health_latest_skin")'),'Result fabricated after denied camera')
        require('erişimi sağlanamadı' in page.locator('body').inner_text().lower() or 'motoru kullanılamıyor' in page.locator('body').inner_text().lower(),'No clear permission/model error')
    check('browser camera denial safe failure',camera_denied);close(c,'browser-denial')

    c,page=new()
    def mental_greeting():
        go(page,'/mental');snap(page,'mental-first-visit');require('son konuşmalarımızdaki' not in page.locator('body').inner_text().lower(),'First-time user is told fabricated past sleep history')
    check('mental first visit does not invent history',mental_greeting)
    def text_input(message, expect_crisis=False):
        page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
        old_count=page.locator('[data-chat-author="AI"]').count()
        box=page.get_by_role('textbox',name='Görüşme mesajı')
        expect(box).to_be_enabled(timeout=45000)
        box.fill(message);box.press('Enter')
        page.wait_for_function('(count)=>document.querySelectorAll("[data-chat-author=AI]").length===count||!!document.querySelector("[role=alert][aria-label]")',arg=old_count+1)
        if expect_crisis:
            alert=page.get_by_role('alert',name='Acil destek yanıtı',exact=True)
            expect(alert).to_be_visible(timeout=30000)
            expect(alert).to_contain_text('112')
            expect(alert.locator('[data-chat-author=AI]')).to_have_count(1)
        else:expect(page.locator('[data-chat-author="AI"]')).to_have_count(old_count+1)
        page.wait_for_timeout(1000)
    def mental_chat():
        text_input('Bugün yeni bir kitap okudum.');snap(page,'mental-text');require('Bugün yeni bir kitap okudum.' in page.locator('body').inner_text(),'Message missing')
        return {'body':page.locator('body').inner_text(),'tts':page.evaluate('window.__audit.tts')}
    check('mental typed message to actual backend and TTS request',mental_chat)
    def mental_crisis():
        text_input('kendime zarar vermek istiyorum',expect_crisis=True);snap(page,'mental-crisis');body=page.locator('body').inner_text();require('112' in body and '182' not in body,'Unsafe crisis escalation')
    check('mental crisis response 112 not appointment hotline',mental_crisis)
    def mental_mic():
        from broader_native_audio import native_speech
        return native_speech(pw,BASE,OUT,INIT,snap,require)
    check('mental real SpeechRecognition from Turkish audio fixture',mental_mic)
    close(c,'mental-flow')

    c,page=new()
    def no_summary():
        go(page,'/privacy');page.get_by_role('button',name='Devre Dışı Bırak',exact=True).click();page.get_by_role('link',name='Ruhsal İyi Oluş',exact=True).click();page.wait_for_timeout(500);text_input('Bugün iş yerinde stres yaşadım.');snap(page,'mental-privacy-off')
        require(page.evaluate('localStorage.getItem("togg_health_latest_mental")') is None,'Summary persisted against privacy preference')
    check('mental summary opt-out respected by UI',no_summary);close(c,'mental-privacy')

    c,page=new()
    def care_consent():
        go(page,'/care');page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True).wait_for(timeout=45000);page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True).click();snap(page,'care-consent')
        button=page.get_by_role('button',name='Onayla ve Devam Et',exact=True);require(button.is_disabled(),'Consent gate can be bypassed');page.get_by_role('checkbox').check();require(button.is_enabled(),'Consent checkbox does not enable handoff');button.click();snap(page,'care-handoff');require(page.get_by_text('Randevu Yönlendirmesi Hazırlandı',exact=True).is_visible(),'Handoff not prepared')
        return 'Internal handoff only; external booking link not clicked'
    check('care real API results consent gate safe handoff',care_consent)
    def care_driving():
        go(page,'/care')
        page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True).wait_for(timeout=45000)
        require(page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True).is_visible(),'Care driving prerequisite: appointment controls were never loaded')
        click_toggle(page);page.wait_for_timeout(500);snap(page,'care-driving')
        require(not page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True).is_visible(),'Interactive appointment selection still available while driving')
    check('care detailed appointment UI locked while driving',care_driving);close(c,'care-flow')

    c,page=new()
    def wipe():
        api('/api/mental/sessions',{'summaryText':'AUDIT ONLY synthetic session','recurringThemes':['audit'],'saveMentalSummaries':True})
        go(page,'/privacy');page.get_by_role('button',name='TÜM YEREL VERİLERİ SİL',exact=True).click();snap(page,'privacy-wipe-confirm')
        buttons=page.get_by_role('button').all_text_contents();print('WIPE_BUTTONS '+json.dumps(buttons,ensure_ascii=False),flush=True)
        confirmation=page.get_by_role('button',name=re.compile('Evet|KALICI|Kalıcı|Onayla|Sil ve'))
        require(confirmation.count()>0,'Cannot identify wipe confirmation button');confirmation.last.click();page.wait_for_timeout(700);snap(page,'privacy-wipe-done');require(api('/api/mental/sessions')==[],'Backend summaries remain after wipe')
    check('privacy UI deletion clears backend summaries',wipe);close(c,'privacy-wipe')

    for width,height in [(1280,800),(390,844)]:
        c,page=new(width=width,height=height)
        def responsive():
            go(page,'/');snap(page,'viewport-'+str(width));return page.evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth})')
        check('responsive dashboard '+str(width),responsive);close(c,'responsive-'+str(width))
    browser.close()

# API checks do not send health data to external services.
def negative_speed():
    with httpx.Client(trust_env=False) as c:
        r=c.post(API+'/api/vehicle/speed',json={'speedKmH':-20});require(r.status_code==422,'Negative speed accepted: '+r.text)
check('API rejects negative vehicle speed',negative_speed)
api('/api/vehicle/speed',{'speedKmH':0})
def explicit_consent():
    before=api('/api/mental/sessions');response=api('/api/mental/sessions',{'summaryText':'AUDIT ONLY no consent','recurringThemes':[]});after=api('/api/mental/sessions')
    require(len(after)==len(before),'Backend persists health summary when explicit consent omitted');return response
check('API requires explicit mental persistence consent',explicit_consent)
def origin_restriction():
    r=httpx.options(API+'/api/privacy/wipe',headers={'Origin':'https://untrusted.example','Access-Control-Request-Method':'POST'})
    require(r.headers.get('access-control-allow-origin') not in ['*','https://untrusted.example'],'Untrusted website permitted by CORS');return dict(r.headers)
check('API rejects untrusted cross-origin access',origin_restriction)
api('/api/privacy/wipe',{})
(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
summary={'passed':sum(r['status']=='PASS' for r in results),'failed':sum(r['status']=='FAIL' for r in results),'total':len(results)}
print('AUDIT_SUMMARY '+json.dumps(summary),flush=True)
raise SystemExit(1 if summary['failed'] else 0)
