"""SAMPLE-DATA UI test of the approved skin result screen (not model output, not a camera test).

A hand-written record (scores, counts and history are illustrative fixtures) is placed in the app's own storage and
opened through the normal route /skin?view=latest. Checks: overview 2x2 cards with value-on-bar, per-page cards,
the history chart, the date-range picker (start can be changed and the end is still selectable), whole-day history
filtering (no evening of the day before), score bands and the 'no band without a measured value' rule.
Requires the built app on 127.0.0.1:3000 and core-api on 127.0.0.1:8000 (park state only). Flags: --chromium.
"""
import json, os, sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT = Path(os.environ.get('SKIN_SAMPLE_UI_DIR', 'audit-results/skin-sample-ui')); OUT.mkdir(parents=True, exist_ok=True)
CHANNEL = {} if '--chromium' in sys.argv else {'channel': 'chrome'}
now = datetime.now(); Y, M = now.year, now.month
if now.day < 8: raise SystemExit('run on day >= 8 of a month (the calendar checks stay inside the current month)')
D = now.day
def iso(day, hour): return datetime(Y, M, day, hour).astimezone().isoformat()
UNAV = [{'id': i, 'reason': 'MODEL_NOT_AVAILABLE'} for i in ('acne', 'acneMarks', 'redness', 'eyeBags', 'darkCircles', 'crowsFeet', 'foreheadLines')]
def record(rid, at, sev, extra=()):
    f = [{'id': 'rosacea', 'region': 'nose', 'status': 'seen', 'pose': 'FRONT', 'severity': sev}, *extra]
    return {'id': rid, 'timestamp': at, 'schemaVersion': 3, 'regions': {'forehead': {}}, 'comparisonScope': 'three-angle-v2', 'indicators': {},
            'general': {'schemaVersion': 1, 'analysisId': rid, 'pose': 'FRONT', 'indicators': [],
                        'skinType': {'value': 'combination', 'sensitive': False, 'quality': 'valid', 'confidence': None, 'methodVersion': 'sample', 'modelHash': None},
                        'findings': {'version': 'sample-fixture', 'status': 'measured', 'poses': ['FRONT', 'LEFT', 'RIGHT'], 'findings': f, 'unavailable': UNAV}}}
current = record('sample-now', iso(D, 10), 62, [
    {'id': 'mole', 'region': 'leftCheek', 'status': 'seen', 'pose': 'RIGHT', 'countRange': '1-3'},
    {'id': 'melasma', 'region': 'rightCheek', 'status': 'seen', 'pose': 'LEFT'},                 # seen, no area measured
    {'id': 'melasma', 'region': 'leftCheek', 'status': 'inconclusive', 'causes': ['ANGLE']}])
history = [current, record('sample-evening-before', iso(D - 3, 22), 55), record('sample-earlier', iso(D - 7, 10), 40)]

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, **CHANNEL); c = b.new_context(viewport={'width': 1600, 'height': 1000}); p = c.new_page()
    errors = []; p.on('pageerror', lambda e: errors.append(str(e)))
    assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed', data={'speedKmH': 0}).ok
    p.goto('http://127.0.0.1:3000/skin')
    consent = p.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.')
    consent.wait_for(timeout=10000); consent.check(); p.get_by_role('button', name='İzin ver ve devam et').click()
    p.evaluate('([l,h])=>{localStorage.setItem("togg_health_latest_skin",JSON.stringify(l));localStorage.setItem("togg_health_skin_history",JSON.stringify(h));}', [current, history])
    p.goto('http://127.0.0.1:3000/skin?view=latest'); expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
    # overview: one card per seen finding, value above the filled end of the bar; inconclusive and unmeasured pills
    cards = p.locator('[data-skin-overview-finding]').evaluate_all('e=>e.map(x=>x.dataset.skinOverviewFinding)')
    assert cards == ['rosacea', 'melasma', 'mole'], cards
    assert '%62' in p.locator('[data-skin-overview-finding="rosacea"]').inner_text()
    assert '1–3' in p.locator('[data-skin-overview-finding="mole"]').inner_text()
    assert '%' not in p.locator('[data-skin-overview-finding="melasma"]').inner_text()
    assert p.locator('[data-skin-findings-inconclusive]').get_attribute('data-skin-findings-inconclusive') == '1'
    assert p.locator('[data-skin-findings-unmeasured]').get_attribute('data-skin-findings-unmeasured') == str(len(UNAV))
    p.screenshot(path=str(OUT / 'sample-overview.png'), full_page=True)
    p.locator('[data-skin-overview-finding="rosacea"]').click(); p.screenshot(path=str(OUT / 'sample-overview-rosacea.png'), full_page=True)
    # T-zone page: rosacea card with score and the history chart (3 scans)
    p.locator('[data-skin-region-tab="forehead"]').click()
    assert p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') == 'rosacea'
    assert p.locator('[data-skin-finding-score]').get_attribute('data-skin-finding-score') == '62'
    assert p.locator('[data-skin-finding-history]').get_attribute('data-skin-finding-history') == '3'
    p.screenshot(path=str(OUT / 'sample-tzone.png'), full_page=True)
    p.get_by_role('button', name='Öneriler').click(); expect(p.locator('[data-band]')).to_have_attribute('data-band', '%61–80'); p.keyboard.press('Escape')
    # date range: change the start, then choose the end (Codex finding 1); whole local days (finding 2)
    def pick(start, end):
        p.locator('[data-skin-history-range]').click(); dlg = p.get_by_role('dialog')
        dlg.get_by_role('button', name=str(start), exact=True).click(); dlg.get_by_role('button', name=str(end), exact=True).click()
        label = dlg.locator('[data-skin-date-range] span').first.inner_text()
        dlg.get_by_role('button', name='Uygula').click(); return label
    label = pick(D - 2, D)
    assert str(D - 2) in label and str(D) in label and '…' not in label, label
    assert p.locator('[data-skin-finding-history]').get_attribute('data-skin-finding-history') == '1'   # the 22:00 scan of D-3 is outside
    p.screenshot(path=str(OUT / 'sample-tzone-range-excludes-evening-before.png'), full_page=True)
    pick(D - 3, D); assert p.locator('[data-skin-finding-history]').get_attribute('data-skin-finding-history') == '2'
    # a seen finding without a measured value: no score, no band
    p.locator('[data-skin-region-tab="rightCheek"]').click()
    assert p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') == 'melasma'
    assert p.locator('[data-skin-finding-unmeasured]').count() == 1 and p.locator('[data-skin-finding-score]').count() == 0
    p.get_by_role('button', name='Öneriler').click(); expect(p.locator('[data-skin-rec-unmeasured]')).to_have_count(1)
    p.screenshot(path=str(OUT / 'sample-rightcheek-no-band.png'), full_page=True); p.keyboard.press('Escape')
    p.locator('[data-skin-region-tab="leftCheek"]').click()
    assert p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') == 'mole'
    p.get_by_role('button', name='Öneriler').click(); expect(p.locator('[data-band]')).to_have_attribute('data-band', '1–3')
    p.keyboard.press('Escape'); p.screenshot(path=str(OUT / 'sample-leftcheek.png'), full_page=True)
    assert not errors, errors
    (OUT / 'proof.json').write_text(json.dumps({'status': 'PASS', 'kind': 'sample-data UI test (fixture values, not model output)', 'pageErrors': errors}, indent=2), 'utf8')
    c.close(); b.close()
print('PASS: sample-data UI (cards, bars, pages, history chart, date range, whole-day filter, bands)')
