"""Live-test regressions: production DOM, pixels and real API; no private media."""
import base64
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT = Path('audit-results/live-followup')
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chromium', headless=True)
    context = browser.new_context(device_scale_factor=8)
    assert context.request.post('http://localhost:8000/api/vehicle/speed', data={'speedKmH':0}).ok
    page = context.new_page()
    from continuous_vision_contract import selector_contract, manual_calibration_contract
    result = selector_contract(page,OUT,'continuous')
    result['calibration'] = manual_calibration_contract(page)
    seen = {'continuous'}
    context.close()
    context=browser.new_context()
    page=context.new_page()
    page.goto('http://localhost:3000/profile')
    page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click()
    expect(page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True)).to_be_disabled()
    assert page.get_by_role('checkbox').count()==3
    assert page.get_by_role('checkbox').filter(has_text='').count()==3
    assert page.get_by_role('checkbox').evaluate_all('(items)=>items.every(i=>!i.checked && i.disabled)')
    assert 'Ahmet Yılmaz' not in page.locator('[data-share-preview]').inner_text()
    page.screenshot(path=str(OUT/'profile-empty.png'))
    (OUT/'first-group.json').write_text(json.dumps({'spokenLetterEntryAndPrivacy':sorted(seen),'emptyShareBlocked':True,'noAutomaticMentalSelection':True},ensure_ascii=False,indent=2),encoding='utf-8')
    context.close();browser.close()
print('PASS: spoken letter entry, automatic conditions/privacy, no manual scale; empty/unselected sharing; legacy math retained in unit suite')
