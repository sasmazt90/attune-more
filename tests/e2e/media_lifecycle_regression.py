from vehicle_controls import toggle_vehicle, vehicle_status
"""Production browser regressions using decoded frames, actual MediaPipe and native permission denial."""
import json
import os
import pathlib
import sys
from playwright.sync_api import sync_playwright, expect

out = pathlib.Path('audit-results')
out.mkdir(exist_ok=True)
base = os.environ.get('ATTUNE_AUDIT_BASE', 'http://localhost:3000')
results = []
sys.stdout.reconfigure(encoding='utf-8')

def run(name, check):
    try:
        detail = check()
        result = {'name': name, 'status': 'PASS', 'detail': detail}
    except Exception as error:
        result = {'name': name, 'status': 'FAIL', 'error': str(error)}
    results.append(result)
    print(json.dumps(result, ensure_ascii=False), flush=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chromium', headless=True, args=[
        '--use-fake-device-for-media-stream',
        '--use-file-for-fake-video-capture=' + str(pathlib.Path('audit-fixtures/face.y4m').resolve()),
        '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'
    ])
    context = browser.new_context(permissions=['camera'], locale='tr-TR')
    context.add_init_script('''window.__streams=[];const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{const s=await gum(...args);window.__streams.push(s);return s;};window.__draws=0;const draw=CanvasRenderingContext2D.prototype.drawImage;CanvasRenderingContext2D.prototype.drawImage=function(...args){window.__draws++;return draw.apply(this,args);};''')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def scan():
        page.goto(base + '/skin')
        (page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button', name='Analizi Başlat', exact=True).click()
        page.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeActive==="true" && window.__draws>2', timeout=30000)
        before = page.evaluate('window.__draws')
        # Native inference/accepted-frame segmentation is asynchronous; require
        # actual continuing draws without asserting a synthetic 600ms frame rate.
        page.wait_for_function('(before)=>window.__draws>before',arg=before,timeout=10000)
        after = page.evaluate('window.__draws')
        assert after > before, (before, after)
        assert page.evaluate('window.__streams.some(s=>s.getTracks().some(t=>t.readyState==="live"))')
        assert not errors, errors
        return {'beforeDraws': before, 'afterDraws': after, 'engine': page.locator('canvas').evaluate('(c)=>c.dataset')}

    run('RAF continues across React alignment and quality updates', scan)

    def exit_route():
        page.get_by_role('link', name='Gizlilik & İzinler', exact=True).click()
        expect(page).to_have_url(base + '/privacy')
        page.wait_for_timeout(300)
        assert page.evaluate('window.__streams.length>0 && window.__streams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
        draws = page.evaluate('window.__draws')
        page.wait_for_timeout(600)
        assert page.evaluate('window.__draws') == draws
        return {'drawsAfterExit': draws, 'tracksEnded': True}

    run('Navigation ends camera tracks and stops canvas work', exit_route)
    run('Second scan starts after route cleanup', scan)

    def driving():
        toggle_vehicle(page)
        expect(page.get_by_text('Cilt Kontrolü Kilitlendi', exact=True)).to_be_visible()
        page.wait_for_timeout(300)
        assert page.evaluate('window.__streams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
        assert not errors, errors
        toggle_vehicle(page)
        expect(page.get_by_role('button', name='Analizi Başlat', exact=True)).to_be_visible()
        return {'tracksEnded': True, 'parkRestored': True}

    run('Driving cancels analysis and park restores ready view without hook-order errors', driving)

    def microphone_denial():
        page.goto(base + '/mental')
        session = context.new_cdp_session(page)
        target = session.send('Target.getTargetInfo')['targetInfo']
        session.send('Browser.setPermission', {'permission': {'name': 'microphone'}, 'setting': 'denied', 'origin': base, 'browserContextId': target['browserContextId']})
        assert page.evaluate('navigator.permissions.query({name:"microphone"}).then(p=>p.state)') == 'denied'
        page.get_by_role('checkbox', name='TOGG Attune hizmet onayı', exact=True).check()
        page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button', name='Görüşmeyi Başlat', exact=True).click()
        expect(page.get_by_text('Ses girişine izin verilmedi.', exact=False)).to_be_visible(timeout=15000)
        expect(page.get_by_role('textbox',name='Görüşme mesajı')).to_be_visible()
        expect(page.get_by_role('button', name='Görüşmeyi Bitir', exact=True)).to_be_visible()
        assert not errors, errors
        return {'nativePermission': 'denied', 'visibleFallback': True}

    run('Native microphone denial is visible and does not claim listening', microphone_denial)
    context.close()
    browser.close()

(out / 'media-lifecycle-regressions.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
raise SystemExit(1 if any(result['status'] != 'PASS' for result in results) else 0)
