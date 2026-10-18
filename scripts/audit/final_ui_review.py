"""Current production UI, isolated declared history fixtures, native Chrome zoom.
No normal profile mutation, provider calls or physical acceptance claim.
"""
from pathlib import Path
import json, math, tempfile, time, sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/e2e'))
from owned_window_capture import capture_owned_window
OUT=ROOT/'audit-results/all-health-20261010/final-ui';OUT.mkdir(parents=True,exist_ok=True)
skin_out=ROOT/'audit-results/all-health-20261010/e2e/focused-final-skin'
assert json.loads((skin_out/'proof.json').read_text('utf8'))['buildId']==(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
skin=json.loads((skin_out/'completed-0.json').read_text('utf8'))['result']
skin={**skin,'id':'isolated-ui-history-fixture','timestamp':'2026-10-10T09:00:00Z','controlledHistoryFixture':True}
runs=[]
with sync_playwright() as pw:
 for width,zoom in [(1600,1),(780,1),(1600,2)]:
  with tempfile.TemporaryDirectory(prefix='attune-final-ui-') as profile:
   pref=Path(profile)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(zoom)/math.log(1.2)}}}),'utf8')
   c=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,args=[f'--window-size={width},1000'])
   c.add_init_script("window.guidanceEvents=[];window.addEventListener('attune-guidance-event',e=>guidanceEvents.push(e.detail));")
   p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   try:
    p.goto('http://127.0.0.1:3000/');expect(p.get_by_text('Park halinde göz, cilt, diş, işitme ve ruh sağlığı değerlendirmelerinizi başlatın.',exact=True)).to_be_visible()
    dims=p.evaluate('({inner:innerWidth,outer:outerWidth,dpr:devicePixelRatio,doc:document.documentElement.scrollWidth,css:document.body.style.zoom||"1"})')
    assert dims['doc']<=dims['inner'] and dims['css']=='1'
    if zoom==2:assert dims['dpr']>=2 and dims['inner']<dims['outer']*.65
    top=p.locator('main section').first
    for label in ['Göz Sağlığı','Cilt Sağlığı','Diş Sağlığı','İşitme Sağlığı','Ruh Sağlığı','Uzman & Randevu']:expect(top.get_by_text(label,exact=True)).to_be_visible()
    carousel=p.locator('[data-card-carousel]').first;track=carousel.get_by_role('list');before=track.evaluate('(e)=>e.scrollLeft')
    carousel.get_by_role('button',name='Sonraki kartlar',exact=True).click();p.wait_for_timeout(500);assert track.evaluate('(e)=>e.scrollLeft')>before
    assert carousel.get_by_role('listitem').evaluate_all('(a)=>Math.max(...a.map(e=>e.getBoundingClientRect().top))-Math.min(...a.map(e=>e.getBoundingClientRect().top))<2')
    carousel.get_by_role('button',name='Önceki kartlar',exact=True).click();p.wait_for_timeout(500)
    stem=f'{width}-{zoom}00';p.screenshot(path=str(OUT/f'cockpit-{stem}.png'),full_page=True);capture_owned_window(p,profile,OUT/f'cockpit-{stem}-owned.png',maximize=False)
    p.evaluate('(v)=>{localStorage.setItem("togg_health_skin_history",JSON.stringify([v]));localStorage.setItem("togg_health_latest_skin",JSON.stringify(v));window.dispatchEvent(new Event("attune-records"));}',skin)
    p.goto('http://127.0.0.1:3000/profile');p.locator('[data-health-module=skin]').click();dialog=p.get_by_role('dialog',name='Cilt Sağlığı geçmiş grafikleri',exact=True);expect(dialog).to_be_visible()
    dialog.get_by_label('Tarih aralığı').select_option('all')
    point=dialog.locator('svg circle[role=button]').first;expect(point).to_be_visible();point.focus();tooltip=dialog.get_by_role('tooltip');expect(tooltip).to_be_visible()
    text=tooltip.inner_text();assert '%' in text and not any(s in text for s in ['mean(', 'clamp(', 'appearance-cv','methodVersion','confidence','=>'])
    assert tooltip.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;}')
    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    p.screenshot(path=str(OUT/f'tooltip-{stem}.png'),full_page=True);capture_owned_window(p,profile,OUT/f'tooltip-{stem}-owned.png',maximize=False)
    p.keyboard.press('Escape');p.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click()
    share=p.get_by_role('dialog',name='Hekim Paylaşım Özeti',exact=True);expect(share.get_by_label('Cilt Sağlığı',exact=True)).to_be_enabled();share.get_by_label('Cilt Sağlığı',exact=True).check()
    expect(share.locator('[data-share-preview]')).to_contain_text('Cilt');share.get_by_label('Cilt Sağlığı',exact=True).uncheck();expect(share.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True)).to_be_disabled();p.keyboard.press('Escape')
    assert not p.evaluate('guidanceEvents.some(e=>e.event==="playing")')
    assert not errors,errors
    runs.append(dict(width=width,nativeZoom=zoom,dimensions=dims,tooltip=text,carouselMovesSingleRow=True,sharePreviewSelectionAndEmptyGuard=True,isolatedDeclaredHistoryFixture=True,generalPagesSilent=True,pageErrors=errors))
   finally:c.close();time.sleep(1)
(OUT/'proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),runs=runs,normalProfileTouched=False,physicalAcceptance=False),ensure_ascii=False,indent=2),'utf8')
print('PASS cockpit, history tooltip, narrow viewport and actual native 200 percent zoom')
