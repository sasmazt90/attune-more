"""Native Chrome zoom/preferences, no CSS zoom and no hardware claims."""
import json,math,tempfile,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from owned_window_capture import capture_owned_window
OUT=Path('audit-results/current-health-20261009/responsive');OUT.mkdir(parents=True,exist_ok=True)
LABELS=['Kokpit','Uzman & Randevu','Sağlık Geçmişim']
MODULES=['Göz Sağlığı','Cilt Sağlığı','Diş Sağlığı','İşitme Sağlığı','Ruh Sağlığı']
proof=[]
with sync_playwright() as pw:
 for zoom in (1,2):
  with tempfile.TemporaryDirectory(prefix='attune-combined-zoom-') as profile:
   pref=Path(profile)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(zoom)/math.log(1.2)}}}),'utf8')
   c=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,args=['--window-size=1600,1000']);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   try:
    capture_owned_window(p,profile,OUT/(str(zoom)+'00-owned-window.png'))
    for route in ('dental','hearing','privacy','profile','vision','skin','mental'):
     p.goto('http://127.0.0.1:3000/'+route);dims=p.evaluate('({inner:innerWidth,outer:outerWidth,dpr:devicePixelRatio,doc:document.documentElement.scrollWidth,css:document.body.style.zoom||"1"})')
     assert dims['doc']<=dims['inner'] and dims['css']=='1'
     if zoom==2:assert dims['dpr']>=2 and dims['inner']<dims['outer']*.65
     assert p.locator('nav a').all_text_contents()==LABELS
     centre=p.get_by_role('button',name='Sağlık Merkezi',exact=True);centre.focus();p.keyboard.press('ArrowDown');expect(centre).to_have_attribute('aria-expanded','true');assert p.locator('#health-centre-links a').all_text_contents()==MODULES
     assert p.locator('#health-centre-links a').first.evaluate('(e)=>e===document.activeElement');p.keyboard.press('End');assert p.locator('#health-centre-links a').last.evaluate('(e)=>e===document.activeElement');p.keyboard.press('Escape');expect(centre).to_have_attribute('aria-expanded','false');assert centre.evaluate('(e)=>e===document.activeElement')
     centre.click();assert p.locator('#health-centre-links').evaluate('(e)=>{const b=e.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth&&getComputedStyle(e).zIndex>=60;}');p.mouse.click(dims['inner']-12,8);expect(centre).to_have_attribute('aria-expanded','false')
     for label in LABELS:
      link=p.locator('nav').get_by_role('link',name=label,exact=True);link.focus();assert link.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}')
     footer=p.get_by_role('link',name='Gizlilik & İzinler',exact=True);assert footer.evaluate('(e)=>e.getBoundingClientRect().top>=e.closest("footer").firstElementChild.getBoundingClientRect().bottom');footer.focus()
     physicalFooter=capture_owned_window(p,profile,OUT/(route+'-'+str(zoom)+'00-footer.png'))
     active=p.locator('nav a[aria-current="page"]')
     if active.count():active.focus()
     else:p.locator('nav a').first.focus()
     p.evaluate('window.scrollTo(0,0)')
     physicalTop=capture_owned_window(p,profile,OUT/(route+'-'+str(zoom)+'00.png'))
     footer.focus()
     p.keyboard.press('Enter');expect(p).to_have_url('http://127.0.0.1:3000/privacy')
     if route!='privacy':p.go_back();expect(p).to_have_url('http://127.0.0.1:3000/'+route)
     proof.append({'route':route,'nativeZoom':zoom,'dimensions':dims,'keyboardNavAndPrivacy':True,'physicalTop':physicalTop,'physicalFooter':physicalFooter})
    assert not errors,errors
   finally:
    c.close()
    time.sleep(1) # allow Chrome crashpad handles to release before profile cleanup
 (OUT/'proof.json').write_text(json.dumps({'status':'PASS','buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'runs':proof,'CSSZoom':False,'physicalCamera':False},indent=2),'utf8')
print('PASS native 100/200 percent Chrome zoom, four top items and five disclosure links and footer privacy URL/back')
