"""Finite Cloud reuse smoke: actual web/API simulation, NOT an Android/WebView emulator test.

Requires isolated frontend/backend on localhost:3000/8000. Never points at a
production origin, captures media, submits health data, or contacts paid services.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get('ATTUNE_AAOS_EVIDENCE', '/tmp/attune-aaos-web-smoke'))
ROUTES = ['/', '/skin', '/dental', '/vision', '/hearing', '/mental', '/care', '/profile', '/privacy']
VIEWPORTS = [(1024, 600), (1280, 720), (1920, 1080), (768, 1024), (800, 480), (1024, 400)]
# The final two sizes represent constrained usable web space, not an AAOS display
# or a claim that Android IME/system insets have been exercised in this browser.
LANGUAGES = {
    'tr': ('tr-TR', 'İzin ver ve devam et', 'Cilt Sağlığı Kilitlendi'),
    'en': ('en-US', 'Allow and continue', 'Skin Health locked'),
    'de': ('de-DE', 'Erlauben und fortfahren', 'Hautgesundheit gesperrt'),
}


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        executable = os.environ.get('ATTUNE_CHROME_EXECUTABLE')
        browser = pw.chromium.launch(executable_path=executable, channel=None if executable else 'chrome',
                                     headless=True, args=['--mute-audio', '--no-sandbox'])
        try:
            for language, (locale, allow, locked) in LANGUAGES.items():
                for width, height in VIEWPORTS:
                    context = browser.new_context(viewport={'width': width, 'height': height}, locale=locale)
                    context.add_init_script(f"localStorage.setItem('attune.language.v1', {json.dumps(language)})")
                    context.add_init_script("window.__captureAttempts=0;navigator.mediaDevices.getUserMedia=()=>{window.__captureAttempts++;throw Error('Media capture excluded from Cloud web smoke')}")
                    def network(route):
                        uri = urlsplit(route.request.url)
                        if uri.hostname in ('localhost', '127.0.0.1') and uri.port in (3000, 8000):
                            route.continue_()
                        else:
                            route.abort('blockedbyclient')
                    context.route('**/*', network)
                    response = context.request.post('http://localhost:8000/api/vehicle/speed', data={'speedKmH': 0})
                    assert response.status == 200
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    for path in ROUTES:
                        response = page.goto('http://localhost:3000' + path, wait_until='domcontentloaded')
                        assert response.status == 200
                        expect(page.locator('[data-vehicle-status]')).to_have_text('PARK', timeout=10000)
                        expect(page.locator('#attune-language')).to_have_value(language)
                        gate = page.get_by_role('dialog').filter(has=page.get_by_role('button', name=allow, exact=True))
                        if gate.count():
                            for box in gate.get_by_role('checkbox').all(): box.check()
                            gate.get_by_role('button', name=allow, exact=True).click()
                            gate.wait_for(state='hidden')
                        page.add_style_tag(path=str(ROOT / 'apps/automotive/app/src/main/assets/automotive.css'))
                        page.evaluate('document.fonts.ready')
                        page.wait_for_timeout(150)
                        geometry = page.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth,navTargets:[...document.querySelectorAll("nav a,nav button")].map(e=>e.getBoundingClientRect().height),captureAttempts:window.__captureAttempts})')
                        assert geometry['width'] == geometry['document']
                        assert all(value >= 48 for value in geometry['navTargets'])
                        assert geometry['captureAttempts'] == 0
                        assert not errors, errors
                        filename = f'web-{language}-{width}x{height}-{path.strip("/") or "dashboard"}.png'
                        page.screenshot(path=str(OUT / filename), full_page=True)
                        results.append({'check': 'web-entry-layout', 'route': path, 'width': width,
                                        'height': height, 'language': language, 'runtime': 'desktop-chrome',
                                        'status': 'PASS', 'geometry': geometry, 'screenshot': filename})
                    # Actual existing backend state, explicitly simulated; never a mocked vehicle response.
                    page.goto('http://localhost:3000/skin', wait_until='domcontentloaded')
                    for speed in (75, 0):
                        response = context.request.post('http://localhost:8000/api/vehicle/speed', data={'speedKmH': speed})
                        assert response.status == 200
                        if speed:
                            expect(page.get_by_role('heading', name=locked, exact=True)).to_be_visible(timeout=10000)
                        else:
                            expect(page.locator('[data-health-start="skin"]')).to_be_visible(timeout=10000)
                        results.append({'check': 'backend-simulation-transition', 'speedKmh': speed, 'width': width,
                                        'height': height, 'language': language, 'status': 'PASS'})
                    context.set_offline(True)
                    expect(page.get_by_role('heading', name=locked, exact=True)).to_be_visible(timeout=10000)
                    context.set_offline(False)
                    expect(page.locator('[data-health-start="skin"]')).to_be_visible(timeout=10000)
                    page.reload(wait_until='domcontentloaded')
                    expect(page.locator('[data-health-start="skin"]')).to_be_visible(timeout=10000)
                    assert page.evaluate('window.__captureAttempts') == 0
                    results.append({'check': 'web-network-recovery-and-reload', 'width': width, 'height': height,
                                    'language': language, 'status': 'PASS'})
                    context.close()
        finally:
            try: browser.contexts[0].request.post('http://localhost:8000/api/vehicle/speed', data={'speedKmH': 0})
            except Exception: pass
            browser.close()
            (OUT / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f'PASS {len(results)} web/API reuse smoke checks; not AAOS runtime validation')


if __name__ == '__main__':
    run()
