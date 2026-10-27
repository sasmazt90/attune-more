"""Shared checks of the approved product React Skin views. No model/pose/quality overrides."""
import json,os,time,math,subprocess
from pathlib import Path
from playwright.sync_api import expect
from owned_window_capture import capture_owned_window
OUT=Path('audit-results/skin-findings-browser')
VIEW_REGIONS={'forehead':['forehead','nose'],'periorbital':['periorbital'],'rightCheek':['rightCheek'],'leftCheek':['leftCheek'],'chin':['chin']}
REGIONS=['forehead','rightCheek','leftCheek','nose','chin','periorbital']
GPU=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']
BROWSER={'executable_path':os.environ['ATTUNE_BROWSER_EXECUTABLE']} if os.getenv('ATTUNE_BROWSER_EXECUTABLE') else {'channel':'chrome'}
def configure(out):
 global OUT
 OUT=Path(out);OUT.mkdir(parents=True,exist_ok=True)
def capture_native(page,profile,path):
 if os.name=='nt':return capture_owned_window(page,profile,path)
 page.screenshot(path=str(path),full_page=False)
 return dict(ownedWindow=False,nativeWindowCapture=False,browserCompositorCapture=True,platform=os.name,physicalCamera=False)
def admit_consent(page):
 consent=page.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.',exact=True)
 if consent.count():
  consent.check();page.get_by_role('button',name='İzin ver ve devam et',exact=True).click()
def scan(page,tag):
 page.goto('http://127.0.0.1:3000/skin');admit_consent(page)
 page.get_by_role('button',name='Analizi Başlat',exact=True).click()
 trace=[];deadline=time.monotonic()+420
 while not page.locator('[data-skin-result]').count() and time.monotonic()<deadline:
  page.wait_for_timeout(1500)
  trace.append(page.evaluate('({at:performance.now(),canvas:{...document.querySelector("canvas")?.dataset},guidance:document.querySelector("[data-camera-preparation]")?.innerText})'))
  (OUT/(tag+'-trace.json')).write_text(json.dumps(trace,ensure_ascii=False,indent=2))
  if page.get_by_role('heading',name='Cilt Sağlığı Başlatılamadı',exact=True).count():break
 if not page.locator('[data-skin-result]').count():
  page.screenshot(path=str(OUT/(tag+'-failure.png')),full_page=True)
 expect(page.locator('[data-skin-result]')).to_be_visible(timeout=1000)
 record=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
 assert record and record['general']['findings']['status']=='measured','BLOCKED: saved-model findings were not measured'
 assert 'data:image' not in page.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
 return record
def open_selected(page,record):
 page.goto('http://127.0.0.1:3000/profile')
 row=page.locator('[data-record-table] [data-record-id="'+record['id']+'"]');expect(row).to_have_count(1)
 row.get_by_role('button',name='Sonucu Aç',exact=True).click()
 dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True)
 expect(dialog.locator('[data-skin-record-comparison="'+record['id']+'"]')).to_have_count(1)
 dialog.locator('[data-skin-open-result]').click()
 expect(page.locator('[data-skin-result]')).to_be_visible(timeout=20000)
 from urllib.parse import urlsplit,parse_qs
 assert parse_qs(urlsplit(page.url).query).get('id')==[record['id']],page.url
 return page.locator('[data-skin-result]')
def seen_ids(findings, regions=None):
    return sorted({f['id'] for f in findings if f['status'] == 'seen' and (regions is None or f['region'] in regions)})


def expected_findings(result):
    """Project the actual numeric record through production UI utilities; never invent a measured value."""
    script=r"""require('./tests/unit/ts_loader');const fs=require('fs'),F=require('./apps/vehicle-app/src/utils/skinFindings'),R=require('./apps/vehicle-app/src/utils/skinRecommendations');const record=JSON.parse(fs.readFileSync(0,'utf8'));
    const item=f=>{const score=R.findingScore(f),count=F.countLabel(f),appearance=R.usesAppearance(f);return {id:f.id,score:score===undefined?null:Math.round(score),count,appearance,band:!!R.recommendationBand(f),text:score!==undefined?(appearance?String(Math.round(score)):'%'+Math.round(score)):appearance?'Görünüm skoru hesaplanamadı':count!==null?(count+' '+F.countUnit(count,F.FINDING_DEFS[f.id].unit,x=>x)).trim():(f.views||[]).map(v=>F.FINDING_VIEW_NAMES[v]).join(', ')};};
    console.log(JSON.stringify({overview:F.overviewFindings(record.findings).map(item),views:Object.fromEntries(F.FINDING_VIEWS.map(v=>[v,F.viewFindings(record.findings,v).map(item)])),unavailable:F.unmeasuredFindings(record)}));"""
    run=subprocess.run(['node','-e',script],input=json.dumps(result),text=True,capture_output=True,timeout=30)
    assert run.returncode==0,run.stderr
    return json.loads(run.stdout)


def check_result(p, rec, shots, tag, photo=True, frame=lambda: None):
    """The result screen shows exactly what the record carries (approved UI elements only)."""
    general = rec['general']; fr = general['findings']; findings = fr['findings']; expected = expected_findings(fr)
    expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
    ov = p.locator('[data-skin-overview-findings]')
    assert ov.get_attribute('data-skin-findings-state') == fr.get('status', 'measured') if fr.get('status') == 'unavailable' else ov.get_attribute('data-skin-findings-state') == 'measured'
    cards = sorted(p.locator('[data-skin-overview-finding]').evaluate_all('els=>els.map(e=>e.dataset.skinOverviewFinding)'))
    pages = max(1, math.ceil(len(seen_ids(findings)) / 4))
    for _ in range(pages - 1):   # the header arrows page the 2x2 grid
        p.get_by_role('button', name='Sonraki bulgular').click()
        cards += p.locator('[data-skin-overview-finding]').evaluate_all('els=>els.map(e=>e.dataset.skinOverviewFinding)')
    if pages > 1: p.get_by_role('button', name='Sonraki bulgular').click()
    assert sorted(set(cards)) == seen_ids(findings), (cards, seen_ids(findings))
    # A present classifier finding can have no appearance measurement. Require the
    # source-derived value OR its explicit unavailable state; never demand an invented number.
    for value in expected['overview']:
        card=p.locator('[data-skin-overview-finding="'+value['id']+'"]')
        if card.count():
            expect(card.get_by_text(value['text'],exact=True)).to_have_count(1)
            if value['score'] is None and value['count'] is None:
                assert not card.locator('span[style*="width:"]').count(),value
    if not any(value['score'] is not None and not value['appearance'] for value in expected['overview']):
        assert '%' not in p.locator('[data-skin-overview]').inner_text()
    if not cards:
        assert p.locator('[data-skin-findings-empty]').get_attribute('data-skin-findings-empty') == ('unavailable' if fr.get('status') == 'unavailable' else 'measured')
    pill = p.locator('[data-skin-findings-unmeasured]')
    unavailable=expected['unavailable']
    if unavailable:
        expect(pill).to_have_attribute('data-skin-findings-unmeasured',str(len(unavailable)))
        pill.click();expect(p.locator('[data-skin-unmeasured-item]')).to_have_count(len(unavailable))
        p.screenshot(path=str(OUT / f'{tag}-unmeasured.png'), full_page=True); shots.append(f'{tag}-unmeasured.png');p.keyboard.press('Escape')
    else:expect(pill).to_have_count(0)
    p.screenshot(path=str(OUT / f'{tag}-overview.png'), full_page=True); shots.append(f'{tag}-overview.png');frame();frame()
    for card in cards[:1]:
        p.locator(f'[data-skin-overview-finding="{card}"]').first.click()
        if photo: assert p.locator('[data-face-panel]').bounding_box()['width'] >= 300
        p.screenshot(path=str(OUT / f'{tag}-overview-{card}.png'), full_page=True); shots.append(f'{tag}-overview-{card}.png')
        p.locator(f'[data-skin-overview-finding="{card}"]').first.click()
    for view, regions in VIEW_REGIONS.items():
        tab = p.locator(f'[data-skin-region-tab="{view}"]'); tab.click()
        want = seen_ids(findings, regions)
        badge = tab.inner_text().strip().split('\n')[-1]
        assert (badge.isdigit() and int(badge) == len(want)) or (not want and not badge.isdigit()), (view, badge, want)
        if want:
            expect(p.locator('[data-skin-finding-card]')).to_have_count(1)
            assert p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') in want
            # mole markers are only drawn on the photo of their own pose
            if p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') == 'mole':
                photo_pose = p.locator('[data-face-panel]').evaluate("e=>e.closest('[data-skin-result]')&&document.querySelector('[data-skin-snapshot]')?.getAttribute('data-snapshot-pose')")
                (OUT / f'{tag}-{view}-marker-pose.json').write_text(json.dumps({'photoPose': photo_pose}), 'utf8')
            current=p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card')
            value=next(v for v in expected['views'][view] if v['id']==current)
            scores=p.locator('[data-skin-finding-card] [data-skin-finding-score]')
            if value['score'] is not None:expect(scores).to_have_attribute('data-skin-finding-score',str(value['score']))
            else:expect(scores).to_have_count(0)
            p.get_by_role('button', name='Öneriler').click();expect(p.locator('[data-skin-recommendations]')).to_have_count(1)
            expect(p.locator('[data-skin-rec-unmeasured]')).to_have_count(0 if value['band'] else 1)
            p.screenshot(path=str(OUT / f'{tag}-{view}-recommendations.png'), full_page=True); shots.append(f'{tag}-{view}-recommendations.png'); p.keyboard.press('Escape')
        else:
            expect(p.locator('[data-skin-findings-empty]')).to_have_count(1)
        if photo:   # the photo of the page stays readable next to the labels (no squeezed photo column)
            assert p.locator('[data-face-panel]').bounding_box()['width'] >= 300, (view, p.locator('[data-face-panel]').bounding_box())
        p.screenshot(path=str(OUT / f'{tag}-{view}.png'), full_page=True); shots.append(f'{tag}-{view}.png'); frame(); frame()
        if photo and 'acne' in want:
            check_acne_types(p, shots, f'{tag}-{view}', frame)
    p.locator('[data-skin-region-tab="overview"]').click()


def check_acne_types(p, shots, tag, frame):
    """Tapping an acne type draws only that type's circles on the photo; tapping it again draws all of them again."""
    for _ in range(6):
        if p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') == 'acne': break
        p.get_by_role('button', name='Sonraki bulgu').click()
    drawn = lambda: p.locator('[data-skin-finding-layer="acne"] [data-skin-finding-marker]').evaluate_all('e=>e.map(x=>x.dataset.skinMarkerType)')
    every = drawn()
    p.get_by_role('button', name='Akne türleri').click()
    for row in p.locator('[data-skin-acne-subtype]').all():
        t = row.get_attribute('data-skin-acne-subtype'); btn = row.locator('button')
        if btn.is_disabled(): continue
        btn.click(); frame()
        assert p.locator('[data-skin-acne-subtypes]').get_attribute('data-skin-acne-selected') == t
        assert drawn() == [x for x in every if x == t], (t, drawn(), every)
        p.screenshot(path=str(OUT / f'{tag}-acne-{t}.png'), full_page=True); shots.append(f'{tag}-acne-{t}.png'); frame()
        btn.click(); frame()   # the same type again: every circle
        assert drawn() == every and p.locator('[data-skin-acne-subtypes]').get_attribute('data-skin-acne-selected') == 'all'


