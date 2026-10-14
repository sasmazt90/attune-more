"""Read-only proof that the real browser paints nonzero API support on the photo."""
import json,base64,math,io
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'audit-results/dryness-integration-v2-20261014';OUT=ROOT/'output/playwright/dryness-integration-v2-20261014'
main=json.loads((DATA/'eyewear-product-browser.json').read_text('utf8'));positive=json.loads((DATA/'nonzero-camera-browser.json').read_text('utf8'));profile=ROOT/main['profile'];assert profile.resolve().is_relative_to(OUT.resolve())
with HeavyJobLease('CDC-dry-actual-browser-paint',peak_mib=600,minimum_available_mib=1200,include_children=True,memory_metric='private') as lease:
 from playwright.sync_api import sync_playwright,expect
 from PIL import Image,ImageChops
 pref=profile/'Default/Preferences';settings=json.loads(pref.read_text('utf8'));settings.setdefault('partition',{})['default_zoom_level']={'x':0};pref.write_text(json.dumps(settings),'utf8')
 with sync_playwright() as pw:
  context=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,viewport=None,no_viewport=True,args=['--window-size=1600,1000','--disable-gpu'])
  try:
   page=context.pages[0];page.goto('http://127.0.0.1:3000/profile');before=page.evaluate('localStorage.getItem("togg_health_skin_history")');page.locator('[data-record-id="'+positive['recordId']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);button=dialog.locator('[data-skin-record-indicator="dry"]');button.click();fill=dialog.locator('[data-skin-local-fill="dry"]');expect(fill).to_be_visible()
   svg=dialog.locator('[data-skin-snapshot]');source=svg.locator(':scope > image').get_attribute('href');cdp=context.new_cdp_session(page);window=cdp.send('Browser.getWindowForTarget');cdp.send('Browser.setWindowBounds',dict(windowId=window['windowId'],bounds=dict(windowState='normal')));page.bring_to_front()
   def capture(name):
    svg.scroll_into_view_if_needed();page.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');page.wait_for_timeout(250);lease.check();bounds=svg.bounding_box();viewport=page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})');raw=base64.b64decode(cdp.send('Page.captureScreenshot',dict(format='png',fromSurface=False))['data']);(OUT/(name+'.png')).write_bytes(raw);im=Image.open(io.BytesIO(raw)).convert('RGB');sx=im.width/viewport['width'];sy=im.height/viewport['height'];x0=max(0,int(bounds['x']*sx));y0=max(0,int(bounds['y']*sy));x1=min(im.width,int((bounds['x']+bounds['width'])*sx));y1=min(im.height,int((bounds['y']+bounds['height'])*sy));return im.crop((x0,y0,x1,y1)),bounds,viewport
   on,bounds,viewport=capture('nonzero-real-desktop-on');button.click();expect(dialog.locator('[data-skin-local-fill="dry"]')).to_have_count(0);off,other,other_view=capture('nonzero-real-desktop-off');assert bounds==other and viewport==other_view and source==svg.locator(':scope > image').get_attribute('href')
   diff=ImageChops.difference(on,off);hist=diff.convert('L').histogram();changed=sum(hist[1:]);maximum=max(v[1] for v in diff.getextrema());assert changed>0 and maximum>0
   on.save(OUT/'nonzero-photo-painted-crop.png');off.save(OUT/'nonzero-photo-unselected-crop.png');diff.save(OUT/'nonzero-photo-paint-difference.png')

   cdp.send('Browser.setWindowBounds',dict(windowId=window['windowId'],bounds=dict(width=720,height=900)));page.wait_for_timeout(400)
   narrow=dialog.evaluate('(e)=>{const b=e.getBoundingClientRect();return {innerWidth,outerWidth,scrollWidth:document.documentElement.scrollWidth,left:b.left,right:b.right,emulatedViewport:false};}')
   assert narrow['innerWidth']<=720 and narrow['scrollWidth']<=narrow['innerWidth'] and 0<=narrow['left']<narrow['right']<=narrow['innerWidth']
   captured=cdp.send('Page.captureScreenshot',dict(format='png',fromSurface=False));(OUT/'nonzero-real-narrow-window.png').write_bytes(base64.b64decode(captured['data']))
   assert before==page.evaluate('localStorage.getItem("togg_health_skin_history")')
   result=dict(actualViewportScreenshot=True,emulatedViewport=False,cssZoom=page.evaluate('getComputedStyle(document.documentElement).zoom'),photoSourceUnchanged=True,photoBounds=bounds,viewport=viewport,changedPhotoPixels=changed,maximumChannelDifference=maximum,nonzeroLocalSupportActuallyPainted=changed>0,historyUnchanged=True,actualNarrowWindow=narrow,recordId=positive['recordId'],photoId=positive['photoId'],resource=lease.receipt());(DATA/'actual-browser-paint.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(dict(changedPhotoPixels=changed,maximumChannelDifference=maximum,viewport=viewport)),flush=True)
  finally:context.close()
