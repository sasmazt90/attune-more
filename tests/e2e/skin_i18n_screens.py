"""Screenshots of the skin result screen in TR, EN and DE with the sample-data record of
current_skin_findings_sample_ui.py (fixture values, not model output). Checks that no Turkish skin-UI text is visible
in EN/DE (letters çğışİ) and that no text overflows its button/tab/pill. Requires the built app on :3000 and core-api.
usage: SKIN_I18N_DIR=out python tests/e2e/skin_i18n_screens.py --chromium"""
import os, re, sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
sys.argv = [a for a in sys.argv]
SRC = Path(__file__).with_name('current_skin_findings_sample_ui.py').read_text('utf8')
fixture = SRC[:SRC.index('with sync_playwright() as pw:')]
ns = {'__file__': __file__}; exec(compile(fixture, 'fixture', 'exec'), ns)
OUT = Path(os.environ.get('SKIN_I18N_DIR', 'audit-results/skin-i18n')); OUT.mkdir(parents=True, exist_ok=True)
TURKISH = re.compile('[çğışİÇĞŞ]')
OVERFLOW_JS = """()=>[...document.querySelectorAll('button,[role=tab],[data-skin-region-tab],[data-skin-overview-finding] span')].filter(e=>e.offsetParent&&(e.scrollWidth>e.clientWidth+1)).map(e=>e.innerText.slice(0,60))"""
report = {}
L = {'tr': {'rec': 'Öneriler', 'next': 'Sonraki bulgu'}, 'en': {'rec': 'Suggestions', 'next': 'Next finding'}, 'de': {'rec': 'Empfehlungen', 'next': 'Nächster Befund'}}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, **ns['CHANNEL'])
    for lang in ('tr', 'en', 'de'):
        c = b.new_context(viewport={'width': 1600, 'height': 1000}); p = c.new_page(); errors = []; p.on('pageerror', lambda e: errors.append(str(e)))
        assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed', data={'speedKmH': 0}).ok
        p.goto('http://127.0.0.1:3000/skin')
        consent = p.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.')
        consent.wait_for(timeout=10000); consent.check(); p.get_by_role('button', name='İzin ver ve devam et').click()
        p.evaluate('([l,h,lang])=>{localStorage.setItem("togg_health_latest_skin",JSON.stringify(l));localStorage.setItem("togg_health_skin_history",JSON.stringify(h));localStorage.setItem("attune.language.v1",lang);}', [ns['current'], ns['history'], lang])
        p.goto('http://127.0.0.1:3000/skin?view=latest'); expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
        texts, overflow = [], []
        def snap(name):
            texts.append(p.locator('main').inner_text()); overflow.extend(p.evaluate(OVERFLOW_JS)); p.screenshot(path=str(OUT / f'{lang}-{name}.png'), full_page=True)
        snap('overview')
        p.locator('[data-skin-region-tab="forehead"]').click()
        for _ in range(6):
            if p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') == 'acne': break
            p.get_by_role('button', name=L[lang]['next']).click()
        p.locator('[data-skin-acne-subtypes] button').first.click(); snap('tzone-acne')
        p.get_by_role('button', name=L[lang]['rec'], exact=True).click()
        texts.append(p.get_by_role('dialog').inner_text()); p.screenshot(path=str(OUT / f'{lang}-recommendations.png')); p.keyboard.press('Escape')
        p.locator('[data-skin-findings-unmeasured]').first.click()
        texts.append(p.get_by_role('dialog').inner_text()); p.screenshot(path=str(OUT / f'{lang}-unmeasured.png')); p.keyboard.press('Escape')
        text = '\n'.join(texts)
        bad = sorted({ln.strip() for ln in text.splitlines() if TURKISH.search(ln)}) if lang != 'tr' else []
        report[lang] = {'turkishLines': bad, 'overflowing': sorted(set(overflow)), 'pageErrors': errors}
        c.close()
    b.close()
(OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
print(json.dumps(report, ensure_ascii=False, indent=1))
assert all(not r['turkishLines'] and not r['pageErrors'] for r in report.values())
assert all(not r['overflowing'] for r in report.values()), 'text overflow'
print('PASS: skin result screen TR/EN/DE')
