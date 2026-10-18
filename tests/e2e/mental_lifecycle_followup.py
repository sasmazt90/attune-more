from vehicle_controls import toggle_vehicle, vehicle_status
"""Production UI, actual keyless FastAPI replies; controlled transport delays test races.
This file makes no native-STT, native-TTS, or live-provider capability claim.
"""
import json
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright, expect

sys.stdout.reconfigure(encoding='utf-8')
OUT = Path('audit-results/mental-followup'); OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:3000'
results = []

def record(name, fn):
    try:
        result = {'name': name, 'status': 'PASS', 'detail': fn()}
    except Exception as error:
        result = {'name': name, 'status': 'FAIL', 'error': str(error)}
    results.append(result); print(json.dumps(result, ensure_ascii=False), flush=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    def fresh():
        context = browser.new_context(viewport={'width': 1600, 'height': 1000}, locale='tr-TR')
        context.request.post('http://localhost:8000/api/vehicle/speed', data={'speedKmH': 0})
        page = context.new_page(); page.goto(BASE + '/mental')
        expect(page.get_by_role('button', name='Görüşmeyi Başlat', exact=True)).to_be_disabled();page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();expect(page.get_by_role('button', name='Görüşmeyi Başlat', exact=True)).to_be_enabled()
        return context, page
    def text_start(page):
        page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button', name='İsterseniz yazabilirsiniz', exact=True).click()
        mute = page.get_by_role('button', name='Sesli yanıtı kapat', exact=True)
        if mute.count(): mute.click()
    def send(page, text):
        count = page.locator('[data-chat-author="AI"]').count()
        box = page.get_by_role('textbox', name='Görüşme mesajı'); expect(box).to_be_enabled()
        box.fill(text); box.press('Enter')
        expect(page.locator('[data-chat-author="AI"]')).to_have_count(count + 1)
        expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase', 'ready')
    def storage(page): return page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history") || "[]")')
    def finish(page):
        page.get_by_role('button', name='Görüşmeyi Bitir', exact=True).click()
        expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase', 'completed')
        page.get_by_role('dialog',name='Görüşme tamamlandı',exact=True).get_by_role('button',name='Tamam',exact=True).click()

    def three_text_turns():
        context, page = fresh(); requests = []
        try:
            page.on('request', lambda r: requests.append(r.post_data_json) if r.url.endswith('/mental/converse') else None)
            page.screenshot(path=str(OUT/'before-session.png'), full_page=True)
            text_start(page)
            expect(page.locator('[data-live-transcript]')).to_be_visible()
            assert page.locator('[data-live-transcript]').bounding_box()['x'] > page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).bounding_box()['x']
            for text in ['Bugün yeni bir kitap okudum.', 'Kitabın konusu arkadaşlık üzerineydi.', 'Arkadaşlarımla bu konuyu konuşmak iyi geldi.']:
                send(page, text); assert storage(page) == []
            assert [len(r['history']) for r in requests] == [0, 2, 4], requests
            assert requests[2]['history'][0]['content'] == 'Bugün yeni bir kitap okudum.'
            assert page.locator('[data-chat-author="USER"]').count() == page.locator('[data-chat-author="AI"]').count() == 3
            page.screenshot(path=str(OUT/'three-turn-text.png'), full_page=True)
            finish(page); saved = storage(page)
            assert len(saved) == 1 and saved[0]['completed'] and saved[0]['consented'] and saved[0]['schemaVersion'] == 3 and saved[0]['startedAt'] < saved[0]['completedAt'] and 'transcript' not in saved[0]
            expect(page.get_by_role('img', name='Görüşme tema payları')).to_be_visible()
            page.locator('[data-session-rows] button[aria-haspopup=dialog]').first.click()
            assert not any(code in page.get_by_role('dialog',name='Görüşme kaydı').inner_text() for code in ['STRESSED','TIRED','RELAXED','NEUTRAL'])
            page.keyboard.press('Escape')
            assert page.locator('[data-current-summary]').count()==0
            page.screenshot(path=str(OUT/'after-session.png'), full_page=True)
            page.reload(); expect(page.locator('[data-mental-record-panel]')).to_contain_text('1 kayıtlı görüşme')
            return {'turns': 3, 'historyLengths': [0,2,4], 'records': 1, 'nativeAudioClaim': False}
        finally: context.close()
    record('Three synthetic fixture text turns preserve history; one summary only at finish', three_text_turns)

    def no_consent():
        context, page = fresh()
        try:
            page.evaluate('localStorage.setItem("togg_privacy_mental_summary_allowed","false")')
            text_start(page); send(page, 'Bugün güzel bir kitap okudum.'); finish(page)
            assert storage(page) == []
            expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
            assert page.locator('[data-current-summary]').count()==0
            return {'summaryCreated': True, 'saved': False}
        finally: context.close()
    record('Summary generation and storage permission are independent', no_consent)

    def revoke_during_summary():
        context, page = fresh(); pending = []
        try:
            text_start(page); send(page, 'Bugün ailemle güzel zaman geçirdim.')
            page.route('**/api/mental/analyze-session', lambda r: pending.append(r))
            page.get_by_role('button', name='Görüşmeyi Bitir', exact=True).click()
            page.wait_for_timeout(200); assert len(pending) == 1
            page.evaluate('localStorage.setItem("togg_privacy_mental_summary_allowed","false");window.dispatchEvent(new Event("attune-privacy"))')
            response = pending[0].fetch(); pending[0].fulfill(response=response)
            expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
            page.get_by_role('dialog',name='Görüşme tamamlandı',exact=True).get_by_role('button',name='Tamam',exact=True).click()
            assert storage(page) == []; return {'lateSaveBlocked': True}
        finally: context.close()
    record('Revocation while analysis is pending blocks persistence', revoke_during_summary)

    def late_response():
        context, page = fresh(); pending = []
        try:
            text_start(page); page.route('**/api/mental/converse', lambda r: pending.append(r))
            page.get_by_role('textbox',name='Görüşme mesajı').fill('Sentetik gecikmiş tur'); page.get_by_role('button',name='Gönder',exact=True).click()
            page.wait_for_timeout(200); assert len(pending) == 1
            page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click()
            pending[0].fulfill(json={'reply': 'GEÇ OLAY', 'providerType':'LIVE_OPENAI'})
            page.wait_for_timeout(500)
            assert 'GEÇ OLAY' not in page.locator('body').inner_text()
            assert storage(page) == []
            assert page.locator('[data-conversation-phase]').get_attribute('data-conversation-phase') == 'error'
            return {'lateReplyIgnored': True, 'partialConversationSaved': False}
        finally: context.close()
    record('Finish invalidates delayed replies and incomplete conversations', late_response)

    def crisis():
        context, page = fresh(); normal = []
        try:
            text_start(page)
            page.on('request',lambda r: normal.append(r.url) if r.url.endswith('/mental/converse') else None)
            page.get_by_role('textbox',name='Görüşme mesajı').fill('ÖLMEK İSTİYORUM')
            page.get_by_role('button',name='Gönder',exact=True).click()
            expect(page.locator('[data-chat-author="AI"]')).to_contain_text('112')
            expect(page.get_by_role('button',name='Görüşmeyi Başlat',exact=True)).to_be_visible()
            assert normal == [] and storage(page) == []
            assert '182' not in page.locator('[data-chat-author="AI"]').inner_text()
            return {'normalProviderCalled': False, 'emergency': '112', 'saved': False}
        finally: context.close()
    record('Turkish uppercase crisis ends normal conversation and uses 112', crisis)

    def driving():
        context, page = fresh(); pending = []
        try:
            text_start(page); page.route('**/api/mental/converse',lambda r: pending.append(r))
            page.get_by_role('textbox',name='Görüşme mesajı').fill('Sentetik sürüş geçişi');page.get_by_role('button',name='Gönder',exact=True).click()
            page.wait_for_timeout(200);toggle_vehicle(page)
            expect(page.get_by_text('Sürüş geçişinde görüşme güvenle kapatıldı.',exact=False)).to_be_visible()
            pending[0].fulfill(json={'reply':'GEÇ SÜRÜŞ OLAYI','providerType':'LIVE_OPENAI'})
            page.wait_for_timeout(400);assert 'GEÇ SÜRÜŞ OLAYI' not in page.locator('body').inner_text() and storage(page)==[]
            return {'drivingCancelled': True}
        finally: context.request.post('http://localhost:8000/api/vehicle/speed', data={'speedKmH':0});context.close()
    record('Driving transition cancels pending work and prevents restart', driving)

    def empty_finish():
        context, page = fresh()
        try:
            text_start(page); finish(page); assert storage(page)==[]
            assert page.locator('[data-current-summary]').count()==0
            return {'saved':False}
        finally:context.close()
    record('Empty conversation produces no successful record',empty_finish)

    def navigation():
        context, page = fresh(); pending = []
        try:
            text_start(page); page.route('**/api/mental/converse',lambda r: pending.append(r))
            page.get_by_role('textbox',name='Görüşme mesajı').fill('Sentetik navigasyon turu');page.get_by_role('button',name='Gönder',exact=True).click()
            page.wait_for_timeout(200);assert len(pending)==1
            page.get_by_role('link',name='Sağlık Geçmişim',exact=True).click()
            pending[0].fulfill(json={'reply':'GEÇ NAVİGASYON OLAYI','providerType':'LIVE_OPENAI'})
            page.get_by_role('link',name='Ruhsal İyi Oluş',exact=True).click()
            expect(page.get_by_role('button',name='Görüşmeyi Başlat',exact=True)).to_be_visible()
            assert page.locator('[data-chat-author]').count()==0 and storage(page)==[]
            return {'unmountedWorkIgnored':True,'saved':False}
        finally:context.close()
    record('Navigation/unmount invalidates pending conversation work',navigation)

    def revoked_cloud():
        context, page = fresh(); pending=[]
        try:
            page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();text_start(page)
            page.route('**/api/mental/converse',lambda r:pending.append(r))
            page.get_by_role('textbox',name='Görüşme mesajı').fill('Sentetik izin geri çekme');page.get_by_role('button',name='Gönder',exact=True).click()
            page.wait_for_timeout(200);page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).uncheck()
            expect(page.get_by_role('button',name='Görüşmeyi Başlat',exact=True)).to_be_visible()
            pending[0].fulfill(json={'reply':'GEÇ BULUT OLAYI','providerType':'LIVE_OPENAI'});page.wait_for_timeout(400)
            assert 'GEÇ BULUT OLAYI' not in page.locator('body').inner_text() and storage(page)==[]
            return {'revokedCloudCancelled':True}
        finally:context.close()
    record('Revoking cloud transfer consent cancels pending replies',revoked_cloud)

    def reading_scroll():
        context, page = fresh()
        try:
            text_start(page)
            for i in range(6):send(page,f'Sentetik kitap sohbeti tur {i}')
            transcript=page.locator('[data-conversation-transcript]')
            assert transcript.evaluate('e=>e.scrollHeight>e.clientHeight+60')
            transcript.evaluate('e=>{e.scrollTop=0;e.dispatchEvent(new Event("scroll"))}')
            send(page,'Son sentetik kitap turu')
            assert transcript.evaluate('e=>e.scrollTop')<10
            assert page.locator('[data-chat-author="USER"]').count()==page.locator('[data-chat-author="AI"]').count()==7
            return {'fullTranscriptPreserved':True,'readingPositionPreserved':True}
        finally:context.close()
    record('Reading earlier messages does not force scroll; all turns remain visible',reading_scroll)

    def driving_during_summary():
        context,page=fresh();pending=[]
        try:
            text_start(page);send(page,'Sentetik tamamlanmış kitap turu')
            page.route('**/api/mental/analyze-session',lambda r:pending.append(r))
            page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();page.wait_for_timeout(200);assert len(pending)==1
            toggle_vehicle(page)
            expect(page.get_by_text('Sürüş geçişinde görüşme güvenle kapatıldı.',exact=False)).to_be_visible()
            pending[0].fulfill(json={'summaryText':'GEÇ ÖZET','themes':['kitap'],'moodTrend':'NEUTRAL','providerType':'LIVE_OPENAI'})
            page.wait_for_timeout(400);assert storage(page)==[] and 'GEÇ ÖZET' not in page.locator('body').inner_text()
            return {'lateSummaryIgnoredAfterDriving':True}
        finally:context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});context.close()
    record('Driving during final analysis cancels the summary and prevents late storage',driving_during_summary)

    def corrupt_history():
        context,page=fresh()
        try:
            text_start(page);send(page,'Sentetik ilk kitap görüşmesi');finish(page)
            latest=page.evaluate('localStorage.getItem("togg_health_latest_mental")')
            page.evaluate('localStorage.setItem("togg_health_mental_history","invalid-history-json")')
            text_start(page);send(page,'Sentetik ikinci kitap görüşmesi')
            page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click()
            expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','error')
            assert page.evaluate('localStorage.getItem("togg_health_mental_history")')=='invalid-history-json'
            assert page.evaluate('localStorage.getItem("togg_health_latest_mental")')==latest
            return {'unreadableHistoryPreserved':True,'previousLatestPreserved':True}
        finally:context.close()
    record('Unreadable existing history is never silently overwritten by a new summary',corrupt_history)
    def audio_notice_recovery():
        context,page=fresh();mode=['failure'];calls=[]
        try:
            page.evaluate('''()=>{window.nativePlayback=[];window.physicalAttempts=0;const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){window.testAudio=this;for(const type of ['playing','ended','error'])this.addEventListener(type,()=>window.nativePlayback.push(type));return play.call(this);};navigator.mediaDevices.getUserMedia=()=>{window.physicalAttempts++;throw Error('Physical capture forbidden');};const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=()=>{window.physicalAttempts++;throw Error('Physical STT forbidden');};}''')
            def speech(route):
                calls.append(mode[0])
                if mode[0]=='failure':route.fulfill(status=503,json={'detail':'Controlled unavailable speech'})
                else:route.fulfill(content_type='audio/mpeg',body=Path('tests/fixtures/synthetic-tone.mp3').read_bytes())
            page.route('**/api/mental/speech',speech)
            page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
            box=page.get_by_role('textbox',name='Görüşme mesajı');box.fill('Bugün yeni bir kitap okudum.');box.press('Enter')
            expect(page.locator('[data-voice-state]')).to_have_attribute('data-voice-state','failed')
            warning=page.get_by_text('Microsoft tr-TR-EmelNeural seslendirmesine ulaşılamadı. Sesli yanıt başarısız. Yanıtı metin olarak okuyabilirsiniz.',exact=True);expect(warning).to_be_visible()
            mode[0]='tone';box.fill('Bugün yeni bir film izledim.');box.press('Enter')
            page.wait_for_function('window.nativePlayback.includes("playing")');expect(warning).not_to_be_visible()
            expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready',timeout=15000)
            mode[0]='failure';box.fill('Bugün yeni bir şarkı dinledim.');box.press('Enter');expect(page.locator('[data-voice-state]')).to_have_attribute('data-voice-state','failed');expect(warning).to_be_visible()
            page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click();expect(warning).not_to_be_visible();send(page,'Bugün yeni bir kitap okudum.');expect(warning).not_to_be_visible()
            finish(page);page.wait_for_function('window.testAudio.paused && !window.testAudio.getAttribute("src")')
            assert page.evaluate('window.physicalAttempts')==0 and calls==['failure','tone','failure']
            return {'staleWarningClearedOnMuteAndSuccess':True,'nativePlaybackEvents':page.evaluate('window.nativePlayback'),'syntheticTone':True,'liveAcceptance':False,'physicalCapture':0,'finishReleasesAudioSource':True}
        finally:context.close()
    record('Audio failure warning clears on mute and subsequent actual MPEG playback',audio_notice_recovery)
    browser.close()

(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(1 if any(r['status']!='PASS' for r in results) else 0)
