from vehicle_controls import toggle_vehicle, vehicle_status
from continuous_vision_contract import selector_contract, manual_calibration_contract
"""Behavior-level backlog regressions against the built app and actual local API."""
import argparse
import json
import os
from pathlib import Path
import re
import traceback
import unicodedata

from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('ATTUNE_AUDIT_BASE', 'http://localhost:3000')
API = os.environ.get('ATTUNE_API_BASE', 'http://localhost:8000')
OUT = Path(os.environ.get('ATTUNE_BACKLOG_OUT', 'audit-results/backlog'))
OUT.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('--phase', required=True)
phase = parser.parse_args().phase
results = []


def record(name, fn):
    try:
        detail = fn()
        row = {'name': name, 'status': 'PASS', 'detail': detail}
    except Exception as error:
        row = {'name': name, 'status': 'FAIL', 'error': str(error), 'traceback': traceback.format_exc()}
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)


def enter_text(page, text):
    page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button', name='İsterseniz yazabilirsiniz', exact=True).click()
    mute=page.get_by_role('button',name='Sesli yanıtı kapat',exact=True)
    if mute.count(): mute.click()
    old_count=page.locator('[data-chat-author="AI"]').count()
    box=page.get_by_role('textbox',name='Görüşme mesajı')
    expect(box).to_be_enabled(timeout=45000)
    box.fill(text);box.press('Enter')
    expect(page.locator('[data-chat-author="AI"]')).to_have_count(old_count+1)
    return page.locator('[data-chat-author="AI"]').last.locator('p').nth(1).inner_text()


def finish_conversation(page):
    page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click()
    expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
    page.get_by_role('dialog',name='Görüşme tamamlandı',exact=True).get_by_role('button',name='Tamam',exact=True).click()


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chromium', headless=True)
    if phase == 'crisis':
        phrases = ['intihar', 'İNTİHAR', 'İntihar', 'iNtIhAr', 'INTIHAR', 'i\u0307ntihar',
                   'CANIMA KIYMAK', 'ÖLMEK İSTİYORUM', 'KeNdİmE ZaRaR',
                   unicodedata.normalize('NFD', 'YAŞAMAK İSTEMİYORUM')]
        for text in phrases + ['Bugün yeni bir kitap okudum.', 'İyi hissediyorum, ailemle görüştüm.']:
            def check(text=text):
                context = browser.new_context()
                try:
                    page = context.new_page()
                    page.goto(BASE + '/mental')
                    reply = enter_text(page, text)
                    if text in phrases:
                        assert '112' in reply and '182' not in reply, reply
                    else:
                        assert '112' not in reply, reply
                    return {'input': text, 'actualReply': reply}
                finally:
                    context.close()
            record('Actual frontend crisis reply: ' + text, check)
    elif phase == 'privacy':
        for local_available, backend_available in [(True, True), (True, False), (False, True), (False, False)]:
            def deletion(local_available=local_available, backend_available=backend_available):
                # Actual browser capability and an aborted network request: no fabricated responses.
                test_browser = pw.chromium.launch(channel='chromium', headless=True,
                    args=[] if local_available else ['--disable-local-storage'])
                context = test_browser.new_context()
                try:
                    created = context.request.post(API + '/api/mental/sessions', data={
                        'summaryText': 'Synthetic deletion capability check',
                        'recurringThemes': [], 'saveMentalSummaries': True})
                    assert created.ok and created.json()['persisted'] is True
                    page = context.new_page()
                    page.goto(BASE + '/privacy')
                    if not local_available:
                        assert page.evaluate('window.localStorage') is None
                    if not backend_available:
                        page.route('**/api/privacy/wipe', lambda route: route.abort())
                    page.get_by_role('button', name='TÜM YEREL VERİLERİ SİL', exact=True).click()
                    page.get_by_role('button', name='Evet, Tüm Verileri Sil', exact=True).click()
                    status = page.locator('[role="status"]').filter(has_text='Tarayıcıdaki sağlık kayıt')
                    expect(status).to_be_visible()
                    text = status.inner_text()
                    assert ('Tarayıcıdaki sağlık kayıtları silindi.' in text) is local_available
                    assert ('Yerel sunucudaki seans özetlerinin silindiği doğrulandı.' in text) is backend_available
                    body = page.locator('body').inner_text()
                    assert ('Tüm yerel veriler başarıyla temizlendi.' in body) is (local_available and backend_available)
                    if not local_available and not backend_available:
                        assert 'Silme işlemi tamamlanamadı.' in text
                    elif local_available != backend_available:
                        assert 'Silme işlemi kısmen tamamlandı.' in text
                    remaining = context.request.get(API + '/api/mental/sessions').json()
                    assert bool(remaining) is (not backend_available)
                    page.screenshot(path=str(OUT / f'privacy-{local_available}-{backend_available}.png'))
                    return {'localAvailable': local_available, 'backendAvailable': backend_available,
                            'actualStatus': text, 'remainingServerRecords': len(remaining)}
                finally:
                    context.request.post(API + '/api/privacy/wipe')
                    context.close()
                    test_browser.close()
            record(f'Deletion truthfulness local={local_available} backend={backend_available}', deletion)
    elif phase == 'vehicle':
        def transitions():
            face = str(Path('audit-fixtures/face.y4m').resolve())
            camera_browser = pw.chromium.launch(channel='chromium', headless=True, args=[
                '--use-fake-device-for-media-stream', '--use-file-for-fake-video-capture=' + face,
                '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            context = camera_browser.new_context(permissions=['camera'])
            try:
                assert context.request.post(API+'/api/vehicle/speed', data={'speedKmH':0}).ok
                page = context.new_page()
                page.add_init_script("""window.cameraStreams=[];const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{const stream=await gum(...args);window.cameraStreams.push(stream);return stream;};""")
                page.goto(BASE+'/vision')
                toggle = vehicle_status(page)
                expect(toggle).to_contain_text('PARK')
                page.get_by_role('button',name='Başlat',exact=True).click()
                page.wait_for_function('window.cameraStreams.some(s=>s.getVideoTracks().some(t=>t.readyState==="live"))')
                toggle_vehicle(page)
                expect(toggle).to_contain_text('SÜRÜŞ')
                expect(page.get_by_role('button',name='Başlat',exact=True)).to_have_count(0)
                assert page.evaluate('window.cameraStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
                driving = context.request.get(API+'/api/vehicle/state').json()
                assert driving['vehicleMoving'] is True and driving['currentSpeed'] == 75
                reply = context.request.post(API+'/api/mental/converse',data={'userMessage':'Bugün kitap okudum'}).json()
                assert reply['isDriving'] is True
                toggle_vehicle(page)
                expect(toggle).to_contain_text('PARK')
                parked = context.request.get(API+'/api/vehicle/state').json()
                assert parked['vehicleMoving'] is False and parked['currentSpeed'] == 0
                expect(page.get_by_role('button',name='Başlat',exact=True)).to_be_enabled()
                page.get_by_role('button',name='Başlat',exact=True).click()
                page.wait_for_function('window.cameraStreams.some(s=>s.getVideoTracks().some(t=>t.readyState==="live"))')
                page.get_by_role('link',name='Gizlilik & İzinler',exact=True).click()
                page.wait_for_function('window.cameraStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
                return {'driving':driving,'parked':parked,'drivingReply':reply,'tracksEndedOnNavigation':True}
            finally:
                context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
                context.close()
                camera_browser.close()
        record('Vision capture stops; frontend transitions govern backend safety decisions',transitions)
        def outage():
            context = browser.new_context()
            try:
                context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
                page = context.new_page()
                page.route('**/api/vehicle/state',lambda route:route.abort())
                page.goto(BASE+'/vision')
                notice = page.get_by_role('alert').filter(has_text='Araç durumu doğrulanamıyor')
                expect(notice).to_be_visible()
                expect(page.get_by_role('button',name='Başlat',exact=True)).to_have_count(0)
                return {'actualSafetyNotice':notice.inner_text()}
            finally:
                context.close()
        record('Unverified vehicle state keeps visual controls locked',outage)
    elif phase == 'vision':
        def geometry():
            context = browser.new_context()
            try:
                context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
                page = context.new_page()
                result = selector_contract(page, OUT, 'vision-continuous')
                result['calibration'] = manual_calibration_contract(page)
                return result
            finally:
                context.close()
        record('Continuous selector and physical size preserve coordinate/scale contract; measurement blocked',geometry)
    elif phase == 'mental':
        def evidence():
            context = browser.new_context()
            try:
                context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
                page = context.new_page()
                page.goto(BASE+'/mental')
                panel = page.locator('[data-mental-history]')
                expect(page.locator('[data-mental-record-panel]')).to_contain_text('0 kayıtlı görüşme')
                body = page.locator('body').inner_text()
                for invented in ['son konuşmalarımızdaki','4 Seans Analiz Edildi','%75','%60','Sabah saatlerinde odaklanma']:
                    assert invented not in body, body
                enter_text(page,'Bugün çocukları okuldan aldım; ailece güzel zaman geçirdik.')
                expect(panel).to_have_count(0)  # Active right column shows the full transcript.
                assert page.evaluate('localStorage.getItem("togg_health_mental_history")') is None
                finish_conversation(page)
                expect(page.locator('[data-mental-record-panel]')).to_contain_text('1 kayıtlı görüşme')
                expect(panel).to_contain_text('sosyal ilişkiler')
                first_history = page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history"))')
                assert len(first_history)==1
                enter_text(page,'Ailemle konuşmak iyi geldi.')
                expect(panel).to_have_count(0)
                assert len(page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history"))'))==1
                finish_conversation(page)
                expect(page.locator('[data-mental-record-panel]')).to_contain_text('2 kayıtlı görüşme')
                page.reload()
                expect(page.locator('[data-mental-record-panel]')).to_contain_text('2 kayıtlı görüşme')
                expect(panel).to_contain_text('sosyal ilişkiler')
                saved = page.evaluate('localStorage.getItem("togg_health_mental_history")')
                page.route('**/api/mental/converse',lambda route:route.abort())
                reply=enter_text(page,'Bugün yeni bir kitap okudum.')
                assert 'bağlantı' in reply.lower() and 'son konuşmalarımızda' not in reply.lower(),reply
                assert page.evaluate('localStorage.getItem("togg_health_mental_history")')==saved
                page.goto(BASE+'/mental?demo=1')
                expect(page.get_by_text('Demo / Örnek içerik — gerçek görüşme geçmişiniz değildir.',exact=True)).to_be_visible()
                assert page.locator('[data-mental-history]').count()==0
                assert page.evaluate('localStorage.getItem("togg_health_mental_history")')==saved
                fresh=context.browser.new_context()
                try:
                    another=fresh.new_page();another.goto(BASE+'/mental')
                    expect(another.locator('[data-mental-record-panel]')).to_contain_text('0 kayıtlı görüşme')
                finally:
                    fresh.close()
                return {'storedRealSummaries':json.loads(saved),'outageReply':reply,'demoSeparated':True,'newBrowserHasNoHistory':True}
            finally:
                context.close()
        record('Fresh, recorded, outage and explicit demo mental-history truthfulness',evidence)
    elif phase == 'hydration':
        def hydration():
            context = browser.new_context()
            try:
                context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
                page = context.new_page()
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                for route in ['/','/profile']:
                    page.goto(BASE+route)
                    expect(vehicle_status(page)).to_contain_text('PARK')
                    assert not errors,errors
                page.goto(BASE+'/mental')
                enter_text(page,'Ailemle bugün güzel vakit geçirdik.')
                finish_conversation(page)
                expect(page.locator('[data-mental-record-panel]')).to_contain_text('1 kayıtlı görüşme')
                for route in ['/','/profile']:
                    page.goto(BASE+route)
                    expect(page.get_by_text('sosyal ilişkiler',exact=True).first).to_be_visible()
                    assert not errors,errors
                for route in ['/?demo=1','/profile?demo=1']:
                    page.goto(BASE+route)
                    expect(page.get_by_text('20/30 • 20/24',exact=True).first).to_be_visible()
                    assert not errors,errors
                return {'emptyAndStoredRoutesWithoutErrors':True,'demoAfterHydrationWithoutErrors':True,'pageerrors':errors}
            finally:
                context.close()
        record('Dashboard and profile hydrate deterministically and then load real/demo data',hydration)
    elif phase == 'skin':
        def model_retry():
            camera_browser=pw.chromium.launch(channel='chromium',headless=True,args=[
                '--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/face.y4m').resolve()),
                '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            context=camera_browser.new_context(permissions=['camera'])
            try:
                assert context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0}).ok
                page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.route('**/face_landmarker.task',lambda route:route.abort())
                page.route('**/wasm/**',lambda route:route.abort())
                page.goto(BASE+'/skin')
                expect(page.locator('[role="alert"]').filter(has_text='başlatılamadı')).to_be_visible(timeout=20000)
                page.get_by_role('button',name='Analizi Başlat',exact=True).click()
                expect(page.get_by_text('Cilt Kontrolü Başlatılamadı',exact=True)).to_be_visible()
                assert not page.evaluate('localStorage.getItem("togg_health_latest_skin")')
                page.unroute('**/face_landmarker.task');page.unroute('**/wasm/**')
                page.get_by_role('button',name='Tekrar Dene',exact=True).click()
                page.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeReady==="true"',timeout=30000)
                page.get_by_role('button',name='Analizi Başlat',exact=True).click()
                page.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeActive==="true" && Number(document.querySelector("canvas")?.dataset.landmarkCount)>=400',timeout=30000)
                assert not page.evaluate('localStorage.getItem("togg_health_latest_skin")'), 'Original blurry negative fixture should remain rejected'
                assert not errors,errors
                return {'failedModelDidNotPersist':True,'retryLoadedActualModel':True,'engine':page.locator('canvas').evaluate('(c)=>c.dataset')}
            finally:
                context.close();camera_browser.close()
        record('Model outage is truthful and retry loads actual MediaPipe after network restoration',model_retry)
    elif phase == 'care':
        def care_safety():
            context=browser.new_context()
            try:
                assert context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0}).ok
                page=context.new_page();page.goto(BASE+'/care')
                examine=page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True)
                examine.wait_for(timeout=45000);examine.click()
                page.get_by_role('checkbox').check()
                expect(page.get_by_role('button',name='Onayla ve Devam Et',exact=True)).to_be_enabled()
                assert context.request.post(API+'/api/vehicle/speed',data={'speedKmH':75}).json()['vehicleMoving'] is True
                expect(page.get_by_text('Randevu İşlemleri Kilitlendi',exact=True)).to_be_visible()
                assert page.get_by_role('button',name='Onayla ve Devam Et',exact=True).count()==0
                assert examine.count()==0
                assert context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0}).ok
                expect(examine).to_be_visible()
                examine.click()
                assert not page.get_by_role('checkbox').is_checked()
                assert page.get_by_role('button',name='Onayla ve Devam Et',exact=True).is_disabled()
                page.route('**/api/vehicle/state',lambda route:route.abort())
                page.reload()
                expect(page.get_by_text('Randevu İşlemleri Kilitlendi',exact=True)).to_be_visible()
                assert examine.count()==0
                return {'parkedSelection':True,'drivingRemovesControls':True,'consentNotReused':True,'unknownStateLocked':True}
            finally:
                context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
                context.close()
        record('Care driving and unknown-state guard clears pending consent',care_safety)
    else:
        raise ValueError('Unknown regression phase: ' + phase)
    browser.close()

(OUT / (phase + '.json')).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
raise SystemExit(1 if any(row['status'] != 'PASS' for row in results) else 0)
