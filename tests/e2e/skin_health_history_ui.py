"""SAMPLE-DATA UI test of Sağlık Geçmişim for skin (fixture values, not model output, not a camera test).

Uses the records of current_skin_findings_sample_ui.py (three scans with findings). Checks: the skin module card shows
the average of the last scans, the record table lists every analysis with date, time, module, summary and a delete
icon, a row opens the detail window compared with the scan just before it, 'Sonuç ekranında aç' opens that record on
the result screen, and the delete icon asks for confirmation. Screenshots in TR, EN and DE.
Requires the built app on 127.0.0.1:3000 and core-api on 127.0.0.1:8000. usage: SKIN_HISTORY_UI_DIR=out python ... --chromium
"""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

SRC = Path(__file__).with_name('current_skin_findings_sample_ui.py').read_text('utf8')
ns = {'__file__': __file__}; exec(compile(SRC[:SRC.index('with sync_playwright() as pw:')], 'fixture', 'exec'), ns)
OUT = Path(os.environ.get('SKIN_HISTORY_UI_DIR', 'audit-results/skin-history-ui')); OUT.mkdir(parents=True, exist_ok=True)
current, history = ns['current'], ns['history']
OPEN = {'tr': 'Sonucu Aç', 'en': 'Open result', 'de': 'Ergebnis öffnen'}
TURKISH = re.compile('[çğışİÇĞŞ]')

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, **ns['CHANNEL'])
    report = {}
    for lang in ('tr', 'en', 'de'):
        c = b.new_context(viewport={'width': 1600, 'height': 1000}); p = c.new_page(); errors = []; p.on('pageerror', lambda e: errors.append(str(e)))
        assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed', data={'speedKmH': 0}).ok
        p.goto('http://127.0.0.1:3000/skin')
        consent = p.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.')
        consent.wait_for(timeout=10000); consent.check(); p.get_by_role('button', name='İzin ver ve devam et').click()
        p.evaluate('([l,h,lang])=>{localStorage.setItem("togg_health_latest_skin",JSON.stringify(l));localStorage.setItem("togg_health_skin_history",JSON.stringify(h));localStorage.setItem("attune.language.v1",lang);}', [current, history, lang])
        p.goto('http://127.0.0.1:3000/profile')
        rows = p.locator('[data-record-table] [data-record-category="skin"]'); expect(rows).to_have_count(3, timeout=20000)
        # module card: average of the last 3 scans with findings
        card = p.locator('[data-skin-averages]'); expect(card).to_have_attribute('data-skin-averages', '3')
        if lang == 'tr':
            text = card.inner_text()
            assert 'Son 3 taramanın ortalaması' in text and 'Karma' in text, text
            assert re.search(r'Sivilce\s+7,3 sivilce', text), text          # (7 + 4 + 11) / 3
            assert re.search(r'Rozasea eğilimi\s+%52', text), text          # (62 + 55 + 40) / 3
            # table: newest first, date + time + module + summary, delete icon per row
            first = rows.nth(0).inner_text()
            assert 'Cilt Sağlığı' in first and 'Sivilce 7' in first and 'Rozasea eğilimi %62' in first, first
            assert rows.nth(0).get_by_role('button', name=re.compile('kaydını sil')).count() == 1
        p.screenshot(path=str(OUT / f'{lang}-profile.png'), full_page=True)
        texts = [p.locator('main').inner_text()]
        # a row opens the detail window, compared with the scan just before it (D-3 22:00), never an average
        rows.nth(0).click()
        dlg = p.get_by_role('dialog'); expect(dlg.locator('[data-skin-record-comparison]')).to_have_count(1)
        assert dlg.locator('[data-skin-compare-with]').get_attribute('data-skin-compare-with') == 'previous'
        ch = {r.get_attribute('data-skin-compare-row'): r.get_attribute('data-skin-compare-change') for r in dlg.locator('[data-skin-compare-row]').all()}
        assert ch == {'acne': 'up', 'rosacea': 'up', 'melasma': 'new', 'mole': 'new'}, ch   # 4 -> 7, 55 -> 62; melasma/mole measured but not seen before
        if lang == 'tr':
            t = dlg.inner_text()
            assert '↑ 3' in t and 'önceki 4' in t and '↑ 7 puan' in t and 'önceki %55' in t, t
        texts.append(dlg.inner_text())
        p.screenshot(path=str(OUT / f'{lang}-detail.png'))
        # the oldest scan has nothing before it
        p.keyboard.press('Escape'); rows.nth(2).click()
        expect(p.get_by_role('dialog').locator('[data-skin-compare-with]')).to_have_attribute('data-skin-compare-with', 'none')
        # 'Sonuç ekranında aç' opens that very record on the result screen
        p.get_by_role('dialog').locator('[data-skin-open-result]').click()
        expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
        assert 'view=record' in p.url and history[2]['id'] in p.url, p.url
        p.screenshot(path=str(OUT / f'{lang}-opened-record.png'), full_page=True)
        # delete icon asks first (cancelled here)
        p.goto('http://127.0.0.1:3000/profile'); expect(rows).to_have_count(3, timeout=20000)
        rows.nth(1).locator('button').last.click()
        expect(p.get_by_role('dialog')).to_be_visible(); texts.append(p.get_by_role('dialog').inner_text())
        p.screenshot(path=str(OUT / f'{lang}-delete-confirm.png')); p.keyboard.press('Escape'); expect(rows).to_have_count(3)
        bad = sorted({ln.strip() for ln in '\n'.join(texts).splitlines() if TURKISH.search(ln)}) if lang != 'tr' else []
        bad = [ln for ln in bad if not ln.startswith('Siz')]
        report[lang] = {'turkishLines': bad, 'pageErrors': errors}
        c.close()
    b.close()
(OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
print(json.dumps(report, ensure_ascii=False, indent=1))
assert all(not r['turkishLines'] and not r['pageErrors'] for r in report.values())
print('PASS: Sağlık Geçmişim skin (averages card, analysis table, compared detail, open record, delete confirm) TR/EN/DE')
