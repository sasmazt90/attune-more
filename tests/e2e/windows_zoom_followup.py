"""Actual Chrome browser zoom via browser keyboard shortcuts in a disposable profile."""
import json,os,tempfile,math,subprocess,base64,io
from PIL import Image,ImageStat
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
assert os.name=='nt' and not os.getenv('OPENAI_API_KEY') and os.getenv('ATTUNE_LOAD_LOCAL_ENV')=='0'
OUT=Path(os.getenv('ATTUNE_WINDOWS_ZOOM_OUTPUT','audit-results/uat-20261003/windows-zoom'));OUT.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='attune-uat-zoom-') as profile,sync_playwright() as pw:
 c=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,args=['--window-size=1280,900']);c.add_init_script("window.captureAttempts=0;const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=()=>{window.captureAttempts++;throw new DOMException('Denied','NotAllowedError')};navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new DOMException('Denied','NotAllowedError'))}")
 page=c.pages[0];c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});page.goto('http://localhost:3000/mental');page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click();page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click();page.get_by_role('textbox',name='Görüşme mesajı').fill('Ailemle güzel bir kitap okudum.');page.get_by_role('button',name='Gönder',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
 original=page.evaluate('({width:innerWidth,dpr:devicePixelRatio,outer:outerWidth})')
 c.close()
 # Chrome 132 stores the default partition zoom in a dictionary; empty relative
 # profile path has key "x". See chrome_zoom_level_prefs.cc in Chromium 132.
 pref=Path(profile)/'Default'/'Preferences';settings=json.loads(pref.read_text(encoding='utf-8'));settings.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};pref.write_text(json.dumps(settings),encoding='utf-8')
 c=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,args=['--window-size=1280,900']);c.add_init_script("window.captureAttempts=0;const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=()=>{window.captureAttempts++;throw new DOMException('Denied','NotAllowedError')};navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new DOMException('Denied','NotAllowedError'))}");page=c.pages[0];page.goto('http://localhost:3000/mental')
 zoomed=page.evaluate('({width:innerWidth,dpr:devicePixelRatio,outer:outerWidth})');assert zoomed['dpr']/original['dpr']>=1.99 and zoomed['width']<original['width']*.55, {'original':original,'zoomed':zoomed}
 # Recreate the same non-personal completed UI record after the isolated restart.
 prior=page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]").length')
 page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click();page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click();page.get_by_role('textbox',name='Görüşme mesajı').fill('Ailemle güzel bir kitap okudum.');page.get_by_role('button',name='Gönder',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed');expect(page.get_by_text(f'{prior+1} kayıtlı görüşme',exact=True)).to_be_visible();assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]").length')==prior+1
 screens=[]
 def capture(name):
  # Browser zoom in Chrome 132 needs an un-clipped viewport capture. Automatic
  # Playwright full-page/clip geometry can crop or blank the scrolled viewport.
  raw=base64.b64decode(c.new_cdp_session(page).send('Page.captureScreenshot',{'format':'png','fromSurface':False})['data'])
  assert sum(ImageStat.Stat(Image.open(io.BytesIO(raw))).var)>10,'Blank capture is not visual evidence'
  (OUT/name).write_bytes(raw)
 for route in ['mental','profile','privacy','vision','skin','','care']:
  if route=='care': page.route('**/api/care/match',lambda route:route.abort())
  page.goto('http://localhost:3000/'+route);page.wait_for_timeout(500);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');capture(route+'-actual-browser-200.png');screens.append(route)
  page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.wait_for_timeout(500);capture(route+'-actual-browser-200-bottom.png')
  if route=='':
   page.get_by_role('button',name='Demo araç durumu hakkında bilgi',exact=True).click();capture('cockpit-demo-info-actual-browser-200.png');page.keyboard.press('Escape')
  if route=='care':
   page.locator('[data-care-limits]').scroll_into_view_if_needed();page.wait_for_timeout(500);capture('care-limits-actual-browser-200.png')
   page.get_by_text('Demo takvim:',exact=False).scroll_into_view_if_needed();page.wait_for_timeout(500);capture('care-example-fields-actual-browser-200.png')
 # All application data below belongs to this disposable synthetic test profile.
 page.goto('http://localhost:3000/profile');page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click();page.get_by_label('Ruhsal iyi oluş',exact=True).check();expect(page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True)).to_be_enabled();capture('profile-selected-actual-browser-200.png');page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True).scroll_into_view_if_needed();page.wait_for_timeout(500);capture('profile-selected-button-actual-browser-200.png');page.keyboard.press('Escape')
 page.evaluate('localStorage.removeItem("togg_health_mental_history");localStorage.removeItem("togg_health_latest_mental")');page.reload();page.wait_for_timeout(500);assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]").length')==0;capture('profile-empty-actual-browser-200.png');page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click();expect(page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True)).to_be_disabled();capture('profile-empty-disabled-actual-browser-200.png');page.keyboard.press('Escape')
 page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click();page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True).scroll_into_view_if_needed();page.wait_for_timeout(500);capture('profile-empty-disabled-button-actual-browser-200.png');page.keyboard.press('Escape')
 page.goto('http://localhost:3000/privacy');page.get_by_role('button',name='Erişimi Kapat',exact=True).first.click();page.get_by_role('button',name='Erişimi Kapat',exact=True).first.click();page.goto('http://localhost:3000/');page.wait_for_timeout(500);capture('cockpit-denied-actual-browser-200.png')
 assert page.locator('[data-sensor-status]').count()==0;capture('cockpit-denied-fields-actual-browser-200.png')
 assert page.evaluate('window.captureAttempts')==0
 proof={'status':'PASS','sourceHead':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'productionBuildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'browser':c.browser.version,'original':original,'actualBrowserZoom':zoomed,'zoomRatio':zoomed['dpr']/original['dpr'],'method':'Disposable profile partition.default_zoom_level, independently verified DPR and viewport reflow','screens':screens,'cssZoomUsed':False,'captureAttempts':0,'userProfileOrGlobalBrowserSettingsChanged':False}
 c.close()
proof['temporaryProfileRemoved']=not Path(profile).exists();(OUT/'result.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof))
