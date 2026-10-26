"""SAMPLE-DATA UI regression of Sağlık Geçmişim (fixture values, not model output, not a camera test).

Reviewer counter-examples: a finding the scan could not confirm (inconclusive) must stay visible in history, without
requiring it to have been seen in an earlier scan.
  (a) acne measured absent + rosacea inconclusive -> the row never says "Bulgu görülmedi" and the detail never says
      "Bu taramada görülen bulgu yok"; rosacea is listed as "Kesinleştirilemedi".
  (b) acne seen, count 3 + rosacea inconclusive -> row shows "Sivilce 3" and rosacea not confirmed; the detail has a
      rosacea row in state inconclusive.
Requires the built app on 127.0.0.1:3000 and core-api on 127.0.0.1:8000. usage: SKIN_INC_UI_DIR=out python ... --chromium
"""
import copy, json, os, re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

SRC = Path(__file__).with_name('current_skin_findings_sample_ui.py').read_text('utf8')
ns = {'__file__': __file__}; exec(compile(SRC[:SRC.index('with sync_playwright() as pw:')], 'fixture', 'exec'), ns)
OUT = Path(os.environ.get('SKIN_INC_UI_DIR', 'audit-results/skin-history-inconclusive-ui')); OUT.mkdir(parents=True, exist_ok=True)
TURKISH = re.compile('[çğışİÇĞŞ]')


def record(rid, ts, findings):
    r = copy.deepcopy(ns['history'][0])
    r['id'] = r['general']['analysisId'] = rid; r['timestamp'] = ts
    r['general']['findings'].update(findings=findings, unavailable=[], status='measured')
    return r


INC = {'id': 'rosacea', 'region': 'nose', 'status': 'inconclusive', 'pose': 'FRONT', 'causes': ['ANGLE']}
a = record('inc-a', '2026-10-25T10:00:00+01:00', [{'id': 'acne', 'region': 'forehead', 'status': 'notSeen', 'pose': 'FRONT'}, INC])
b = record('inc-b', '2026-10-26T10:00:00+01:00', [{'id': 'acne', 'region': 'forehead', 'status': 'seen', 'pose': 'FRONT', 'count': 3}, INC])
history = [b, a]

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True, **ns['CHANNEL'])
    report = {}
    for lang in ('tr', 'en', 'de'):
        c = br.new_context(viewport={'width': 1600, 'height': 1000}); p = c.new_page(); errors = []; p.on('pageerror', lambda e: errors.append(str(e)))
        assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed', data={'speedKmH': 0}).ok
        p.goto('http://127.0.0.1:3000/skin')
        consent = p.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.')
        consent.wait_for(timeout=10000); consent.check(); p.get_by_role('button', name='İzin ver ve devam et').click()
        p.evaluate('([l,h,lang])=>{localStorage.setItem("togg_health_latest_skin",JSON.stringify(l));localStorage.setItem("togg_health_skin_history",JSON.stringify(h));localStorage.setItem("attune.language.v1",lang);}', [b, history, lang])
        p.goto('http://127.0.0.1:3000/profile')
        rows = p.locator('[data-record-table] [data-record-category="skin"]'); expect(rows).to_have_count(2, timeout=20000)
        sums = [rows.nth(i).locator('[data-skin-row-summary]') for i in range(2)]
        # (b) newest row: acne 3 + rosacea not confirmed; (a) older row: never "none-seen"
        assert sums[0].get_attribute('data-skin-row-summary') == 'measured'
        assert sums[1].get_attribute('data-skin-row-summary') != 'none-seen'
        for s in sums:
            assert s.locator('[data-skin-row-inconclusive="rosacea"]').count() == 1
        texts = [p.locator('main').inner_text()]
        if lang == 'tr':
            t0, t1 = rows.nth(0).inner_text(), rows.nth(1).inner_text()
            assert 'Sivilce 3' in t0 and 'Rozasea eğilimi · Kesinleştirilemedi' in t0, t0
            assert 'Rozasea eğilimi · Kesinleştirilemedi' in t1 and 'Bulgu görülmedi' not in t1, t1
        p.screenshot(path=str(OUT / f'{lang}-profile.png'), full_page=True)
        details = {}
        for i, key in ((0, 'b'), (1, 'a')):
            rows.nth(i).click()
            dlg = p.get_by_role('dialog'); expect(dlg.locator('[data-skin-record-comparison]')).to_have_count(1)
            now = {r.get_attribute('data-skin-compare-row'): r.get_attribute('data-skin-compare-now') for r in dlg.locator('[data-skin-compare-row]').all()}
            details[key] = now
            assert now.get('rosacea') == 'inconclusive', now
            assert dlg.locator('[data-skin-compare-empty]').count() == 0
            if lang == 'tr':
                t = dlg.inner_text(); assert 'Bu taramada görülen bulgu yok' not in t and 'Kesinleştirilemedi' in t, t
            texts.append(dlg.inner_text())
            p.screenshot(path=str(OUT / f'{lang}-detail-{key}.png'))
            p.keyboard.press('Escape'); expect(p.get_by_role('dialog')).to_have_count(0)
        assert details['b'].get('acne') == 'seen', details
        bad = sorted({ln.strip() for ln in '\n'.join(texts).splitlines() if TURKISH.search(ln)}) if lang != 'tr' else []
        report[lang] = {'detail': details, 'turkishLines': [ln for ln in bad if not ln.startswith('Siz')], 'pageErrors': errors}
        c.close()
    br.close()
(OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
print(json.dumps(report, ensure_ascii=False, indent=1))
assert all(not r['turkishLines'] and not r['pageErrors'] for r in report.values())
print('PASS: inconclusive findings stay visible in history (row + detail) TR/EN/DE')
