"""Native Chrome zoom/preferences, no CSS zoom and no hardware claims."""
import json,math,tempfile,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from owned_window_capture import capture_owned_window
OUT=Path('audit-results/combined-health-20261008/responsive');OUT.mkdir(parents=True,exist_ok=True)
LABELS=['Kokpit','Göz Sağlığı','Cilt Sağlığı','Diş Sağlığı','İşitme Sağlığı','Ruhsal Sağlık','Uzman & Randevu','Sağlık Geçmişim']
proof=[]
with sync_playwright() as pw:
 for zoom in (1,2):
  with tempfile.TemporaryDirectory(prefix='attune-combined-zoom-') as profile:
   pref=Path(profile)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(zoom)/math.log(1.2)}}}),'utf8')
   c=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,args=['--window-size=1600,1000']);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   try:
    capture_owned_window(p,profile,OUT/(str(zoom)+'00-owned-window.png'))
    for route in ('dental','hearing','privacy','profile'):
     p.goto('http://127.0.0.1:3000/'+route);dims=p.evaluate('({inner:innerWidth,outer:outerWidth,dpr:devicePixelRatio,doc:document.documentElement.scrollWidth,css:document.body.style.zoom||"1"})')
     assert dims['doc']<=dims['inner'] and dims['css']=='1'
     if zoom==2:assert dims['dpr']>=2 and dims['inner']<dims['outer']*.65
     assert p.locator('nav a').all_text_contents()==LABELS
     for label in LABELS:
      link=p.locator('nav').get_by_role('link',name=label,exact=True);link.focus();assert link.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}')
     footer=p.get_by_role('link',name='Gizlilik & İzinler',exact=True);footer.focus()
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
print('PASS native 100/200 percent Chrome zoom, all eight keyboard links and footer privacy URL/back')
