"""Approved spoken UI replaces rotary/card/practice. Historical caller names retained.
Parser/scoring invariants use the production TS unit suite; no fake STT events.
"""
import json
from pathlib import Path
from playwright.sync_api import expect

def selector_contract(page,out=None,tag='spoken-letter'):
    page.goto('http://localhost:3000/vision')
    expect(page.get_by_role('heading',name='Sesli harf tanıma',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='Başlat',exact=True)).to_be_enabled()
    for removed in ('Kısa Alıştırma','Hazırlığı Başlat','Yanıtla','Ekran ölçeğini ayarla'):
        expect(page.get_by_role('button',name=removed,exact=True)).to_have_count(0)
    expect(page.get_by_role('slider')).to_have_count(0)
    assert page.locator('[data-continuous-selector]').count()==0
    assert page.evaluate('localStorage.getItem("togg_health_latest_vision")') is None
    if out:page.screenshot(path=str(Path(out)/(tag+'.png')),full_page=True)
    return {'spokenLetterUI':True,'manualCardRemoved':True,'practiceRemoved':True,'scoresCreated':0,'nativeSTTAcceptance':'not attempted by this UI check'}

def manual_calibration_contract(page):
    page.goto('http://localhost:3000/vision');page.evaluate('localStorage.setItem("attune_privacy_camera_allowed","false")')
    page.get_by_role('button',name='Başlat',exact=True).click()
    expect(page.locator('p[role=alert]')).to_contain_text('Kamera ve mikrofon izinlerini')
    expect(page.locator('[data-letter-optotype]')).to_have_count(0)
    assert page.get_by_role('slider').count()==0
    assert page.evaluate('localStorage.getItem("togg_health_latest_vision")') is None
    page.evaluate('localStorage.removeItem("attune_privacy_camera_allowed")')
    return {'privacyGate':True,'manualCalibrationRemoved':True,'exactDistanceInvented':False,'records':0}

if __name__=='__main__':
    from playwright.sync_api import sync_playwright
    out=Path('audit-results/continuous-vision');out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True);c=b.new_context();p=c.new_page();c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
        proof={'spokenUI':selector_contract(p,out),'privacy':manual_calibration_contract(p)}
        p.set_viewport_size({'width':633,'height':266});selector_contract(p,out,'short-viewport-spoken');p.get_by_role('button',name='Başlat',exact=True).scroll_into_view_if_needed()
        assert p.get_by_role('button',name='Başlat',exact=True).evaluate('e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2))}')
        assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        (out/'proof.json').write_text(json.dumps(proof,indent=2));c.close();b.close()
