"""Read only the accepted isolated record; no recapture or repeated inference."""
import json,base64
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'audit-results/material-closeout-20261013';OUT=ROOT/'output/playwright/material-closeout-20261014'
prior=json.loads((DATA/'eyewear-product-browser.json').read_text('utf8'))
profile=(ROOT/prior['profile']).resolve();assert profile.is_relative_to(OUT.resolve())
expected=json.loads((DATA/'new-camera-normal-result.json').read_text('utf8'))['maps']['overview:tone']
with HeavyJobLease('CDC-current-record-geometry',peak_mib=550,minimum_available_mib=1000,include_children=True,memory_metric='private') as lease:
    from playwright.sync_api import sync_playwright,expect
    with sync_playwright() as pw:
        context=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,viewport=None,no_viewport=True,args=['--window-size=1600,1000','--disable-gpu'])
        try:
            page=context.pages[0] if context.pages else context.new_page();page.goto('http://127.0.0.1:3000/profile')
            before=page.evaluate('localStorage.getItem("togg_health_skin_history")')
            page.locator('[data-record-id="'+prior['newRecordId']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click()
            dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True)
            expect(dialog.locator('[data-skin-snapshot]')).to_be_visible()
            dialog.locator('[data-skin-record-indicator="tone"]').click();fill=dialog.locator('[data-skin-local-fill="tone"]');expect(fill).to_be_visible()
            actual=fill.locator('image').evaluate('(e)=>Object.fromEntries(["x","y","width","height"].map(k=>[k,Number(e.getAttribute(k))]))')
            wanted=dict(x=expected['x'],y=expected['y'],width=expected['width']*expected['step'],height=expected['height']*expected['step'])
            assert actual==wanted and fill.get_attribute('data-map-photo')==prior['actualPhotoId']
            geometry=dialog.evaluate('(e)=>{const r=e.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,innerWidth,innerHeight,outerWidth,dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth,panelScrollHeight:e.scrollHeight,panelClientHeight:e.clientHeight,bodyOverflow:getComputedStyle(document.body).overflow};}')
            assert 0<=geometry['left']<geometry['right']<=geometry['innerWidth'] and 0<=geometry['top']<geometry['bottom']<=geometry['innerHeight']
            assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65
            cdp=context.new_cdp_session(page);window=cdp.send('Browser.getWindowForTarget')
            cdp.send('Browser.setWindowBounds',dict(windowId=window['windowId'],bounds=dict(windowState='normal')))
            page.bring_to_front();fill.scroll_into_view_if_needed()
            page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT/'history-native200-viewport-with-map.png'),full_page=False,animations='disabled')
            captured=cdp.send('Page.captureScreenshot',dict(format='png',fromSurface=False))
            (OUT/'history-native200-browser-surface.png').write_bytes(base64.b64decode(captured['data']))
            assert before==page.evaluate('localStorage.getItem("togg_health_skin_history")')
            receipt=dict(geometry=geometry,browserWindow=window,actualMapSourceCoordinates=actual,expectedAPISourceCoordinates=wanted,mapStep=expected['step'],photoId=prior['actualPhotoId'],historyUnchanged=True,resource=lease.receipt())
            (DATA/'history-source-geometry.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(dict(geometry=geometry,mapSourceCoordinates=actual)),flush=True)
        finally:context.close()
