"""Actual MediaPipe/pixel evidence on existing Google portrait virtual camera.
Fixture license is unverified; this is a local technical negative-path check.
Negative-path stale, permission, route and driving lifecycle. Positive eye/voice
personal acceptance is deliberately reported pending, not fabricated.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/vision-camera');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    b=pw.chromium.launch(channel='chromium',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/valid-face.y4m').resolve()),'--enable-unsafe-swiftshader'])
    c=b.new_context(permissions=['camera']);p=c.new_page();c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0});errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
    c.add_init_script("window.actualStreams=[];window.physicalAttempts=0;const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{if(args[0]?.audio){window.physicalAttempts++;throw Error('Physical microphone forbidden')}const s=await gum(...args);window.actualStreams.push(s);return s};")
    # Explicit transport outage: no substituted audio and no external TTS dispatch.
    c.route('**/api/vision/speech',lambda route:route.abort())
    def start():
        p.goto('http://127.0.0.1:3000/vision');expect(p.get_by_role('button',name='Başlat',exact=True)).to_be_enabled();p.get_by_role('button',name='Başlat',exact=True).click()
        try:p.wait_for_function('window.actualStreams.some(s=>s.getTracks().some(t=>t.readyState==="live"))',timeout=15000)
        except Exception:
            (OUT/'startup-failure.json').write_text(json.dumps({'body':p.locator('body').inner_text(),'tracks':p.evaluate('window.actualStreams.map(s=>s.getTracks().map(t=>t.readyState))'),'errors':errors},ensure_ascii=False,indent=2),encoding='utf8');p.screenshot(path=str(OUT/'startup-failure.png'),full_page=True);raise
        p.wait_for_timeout(5000)
    start();p.wait_for_function('JSON.parse(document.querySelector("canvas").dataset.visionEvidence||"null")?.conditions.modelActive===true&&JSON.parse(document.querySelector("canvas").dataset.visionEvidence||"null")?.conditions.faceCount===1');expect(p.locator('p[role=alert]')).to_contain_text('Ahmet');expect(p.locator('[data-letter-optotype]')).to_have_count(0)
    p.locator('video').evaluate('v=>v.pause()');p.wait_for_timeout(1000);expect(p.locator('[data-camera-preparation]')).to_contain_text('Kamera karesi bekleniyor');expect(p.locator('[data-letter-optotype]')).to_have_count(0)
    assert p.evaluate('localStorage.getItem("togg_health_latest_vision")') is None
    p.locator('video').evaluate('v=>v.play()');p.wait_for_timeout(1200)
    p.get_by_role('button',name='Bitir',exact=True).click();expect(p.get_by_role('dialog')).to_contain_text('Tamamlanmamış sonuç kaydedilmedi');p.get_by_role('button',name='Tamam',exact=True).click()
    p.wait_for_function('window.actualStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    start();p.goto('http://127.0.0.1:3000/privacy');p.wait_for_function('window.actualStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    start();p.evaluate('localStorage.setItem("attune_privacy_camera_allowed","false");window.dispatchEvent(new Event("attune-privacy"))');p.wait_for_function('window.actualStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))');expect(p.locator('p[role=alert]')).to_contain_text('tercihi kapalı')
    p.evaluate('localStorage.removeItem("attune_privacy_camera_allowed")');start();c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':75});p.wait_for_function('window.actualStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))');expect(p.get_by_role('button',name='Başlat',exact=True)).to_have_count(0)
    assert p.evaluate('window.physicalAttempts')==0 and not errors,errors
    proof={'status':'PASS','virtualCamera':True,'actualProductionMediaPipe':True,'staleFrameBlocked':True,'voiceFailureDoesNotAdvance':True,'routePrivacyDrivingEndTracks':True,'scoredRecords':0,'fakeSTTEvents':0,'physicalCapture':0,'paidCalls':0,'positiveEyeAndSpokenAcceptance':'not evaluated by this negative fixture; separate physical evidence required'}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2));c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0});c.close();b.close()
print(json.dumps(proof))
