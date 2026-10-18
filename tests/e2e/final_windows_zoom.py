"""Actual Windows Chrome 200% zoom, seven routes and all three deletion dialogs.
Disposable profile; no physical capture or provider dispatch. Generated records
are explicitly synthetic UI fixtures, not clinical measurement evidence.
"""
import base64, io, json, math, os, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright, expect
assert os.name == 'nt'
OUT=Path('audit-results/final-user-flow-20261003/windows-200');OUT.mkdir(parents=True,exist_ok=True)
DENIED="navigator.mediaDevices.getUserMedia=()=>{throw Error('Physical capture forbidden')};const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=()=>{throw Error('Physical capture forbidden')};"
with tempfile.TemporaryDirectory(prefix='attune-final-zoom-') as profile, sync_playwright() as pw:
 def launch():
  context=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,args=['--window-size=1280,900']);context.add_init_script(DENIED);return context
 c=launch();p=c.pages[0];p.goto('http://localhost:3000');original=p.evaluate('({width:innerWidth,dpr:devicePixelRatio})');c.close()
 preferences=Path(profile)/'Default/Preferences';settings=json.loads(preferences.read_text(encoding='utf-8'));settings.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};preferences.write_text(json.dumps(settings),encoding='utf-8')
 c=launch();p=c.pages[0];c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://localhost:3000');zoom=p.evaluate('({width:innerWidth,dpr:devicePixelRatio})');assert zoom['dpr']/original['dpr']>=1.99 and zoom['width']<original['width']*.55
 def snap(name):
  raw=base64.b64decode(c.new_cdp_session(p).send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False})['data']);assert sum(ImageStat.Stat(Image.open(io.BytesIO(raw))).var)>10;(OUT/(name+'.png')).write_bytes(raw)
 screens=[]
 try:
  for route in ['','vision','skin','mental','care','profile','privacy']:
   if route=='care':p.route('**/api/care/match',lambda r:r.abort())
   p.goto('http://localhost:3000/'+route);p.wait_for_timeout(350);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');snap((route or 'cockpit')+'-200-top');p.evaluate('scrollTo(0,document.documentElement.scrollHeight)');p.wait_for_timeout(150);snap((route or 'cockpit')+'-200-bottom')
   callers=p.get_by_role('button',name='hakkında bilgi').all()
   for i,caller in enumerate(callers):
    caller.click();d=p.get_by_role('dialog');expect(d).to_be_visible();assert d.bounding_box()['height']<=p.evaluate('innerHeight')-30;assert d.evaluate('(e)=>{const r=e.firstElementChild.getBoundingClientRect();return e.contains(document.elementFromPoint(r.left+10,r.top+10))}'),'Dialog title covered by page navigation';snap(f'{route or "cockpit"}-200-information-{i}');p.keyboard.press('Escape');assert caller.evaluate('e=>e===document.activeElement')
   screens.append(route or 'cockpit')
  p.goto('http://localhost:3000/profile')
  for category,history,latest in [('vision','togg_health_vision_history','togg_health_latest_vision'),('skin','togg_health_skin_history','togg_health_latest_skin'),('mental','togg_health_mental_history','togg_health_latest_mental')]:
   row={'id':'zoom-'+category,'date':'2026-10-03T10:00:00Z','timestamp':'2026-10-03T10:00:00Z','summaryText':'Sentetik zoom özeti','themes':['kitap'],'schemaVersion':2,'completed':True,'consented':True,'regions':{},'acuityRightSnellen':'20/20','acuityLeftSnellen':'20/30'}
   p.evaluate('([history,latest,row])=>{localStorage.setItem(history,JSON.stringify([row]));localStorage.setItem(latest,JSON.stringify(row));}',[history,latest,row]);p.reload();panel=p.locator(f'[data-record-history={category}]');panel.get_by_role('button',name='kaydını sil:').click();d=p.get_by_role('dialog',name='Bu kaydı silmek istiyor musunuz?',exact=True);expect(d).to_be_visible();snap(category+'-200-delete-dialog')
   for _ in range(12):p.keyboard.press('Tab');assert d.evaluate('e=>e.contains(document.activeElement)')
   p.keyboard.press('Escape');expect(panel.locator('[data-record-id]')).to_have_count(1)
   panel.get_by_role('button',name='kaydını sil:').click();p.get_by_role('button',name='Evet, sil',exact=True).click();expect(panel.locator('[data-record-id]')).to_have_count(0);p.reload();expect(panel.locator('[data-record-id]')).to_have_count(0)
  proof={'status':'PASS','routes':screens,'deletionCategories':['vision','skin','mental'],'chrome':c.browser.version,'original':original,'actualZoom':zoom,'ratio':zoom['dpr']/original['dpr'],'cssZoomUsed':False,'physicalCapture':False,'providerDispatch':False,'userProfileTouched':False,'sourceHead':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip()}
 finally:c.close()
proof['temporaryProfileRemoved']=not Path(profile).exists();(OUT/'result.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof))
