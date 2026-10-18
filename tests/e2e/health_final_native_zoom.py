"""Owned persistent Chrome: actual native 200% zoom, never CSS/device emulation."""
import base64,json,math,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT.parent/'cdc-progress/health-final-technical-closeout-20261017'
profile=OUT/'native-200-final-profile'
assert not profile.exists(), 'Use a fresh task-owned zoom profile'
(profile/'Default').mkdir(parents=True)
level=math.log(2)/math.log(1.2)
(profile/'Default/Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':level}}}),'utf8')
proof={'nativeZoom':2,'preferenceLevel':level,'CSSZoom':False,'deviceEmulation':False,'physicalUserAcceptance':False,'screens':[]}
with sync_playwright() as pw:
 c=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,no_viewport=True,args=['--window-size=1440,1000'])
 try:
  c.add_init_script("navigator.mediaDevices.getUserMedia=()=>{throw Error('Physical camera forbidden')}")
  c.route('**/api/mental/speech',lambda r:r.fulfill(status=503,json={'detail':'CONTROLLED_UNAVAILABLE'}))
  p=c.new_page()
  for module in ['skin','vision','dental','hearing','mental']:
   p.goto('http://127.0.0.1:3311/'+module)
   d=p.get_by_role('dialog')
   if d.count():
    for box in d.get_by_role('checkbox').all():box.check()
    d.get_by_role('button',name='İzin ver ve devam et').click()
   p.locator('[data-health-start]').wait_for()
   p.locator('[data-health-portrait] img').evaluate('(e)=>e.decode()')
   dims=p.evaluate('({inner:innerWidth,outer:outerWidth,dpr:devicePixelRatio,scale:visualViewport.scale,doc:document.documentElement.scrollWidth,css:getComputedStyle(document.documentElement).zoom})')
   assert dims['inner']<dims['outer']*.65 and dims['dpr']>=2 and dims['scale']==1 and dims['css']=='1' and dims['doc']<=dims['inner'],dims
   p.get_by_role('button',name='Sağlık Merkezi',exact=True).focus();p.keyboard.press('ArrowDown')
   assert p.locator('#health-centre-links a').count()==5
   p.keyboard.press('Escape')
   session=c.new_cdp_session(p)
   try:
    captured=session.send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False})
    (OUT/(module+'-native200.png')).write_bytes(base64.b64decode(captured['data']))
   finally:session.detach()
   actions=p.locator('[data-health-start-actions]');actions.scroll_into_view_if_needed()
   bounds=actions.bounding_box();assert bounds and bounds['y']>=0 and bounds['y']+bounds['height']<=p.evaluate('innerHeight')
   session=c.new_cdp_session(p)
   try:
    captured=session.send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False})
    (OUT/(module+'-native200-actions.png')).write_bytes(base64.b64decode(captured['data']))
   finally:session.detach()
   proof['screens'].append({'module':module,'dimensions':dims,'actionsVisibleAfterScroll':bounds,'capture':'headed Chrome visible compositor, no CSS clip or full-page resize'})
 finally:c.close()
proof['BUILD_ID']=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
(OUT/'native200-proof.json').write_text(json.dumps(proof,indent=2),'utf8')
print('PASS five real native 200% preparation screens')
