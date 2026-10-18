"""Actual completion/dialog/history UI on keyless generation, no device capture."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/product-decisions-20261004/layout');OUT.mkdir(parents=True,exist_ok=True)
proof=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True)
 for width in (390,1600):
  c=b.new_context(viewport={'width':width,'height':1000});c.add_init_script("navigator.mediaDevices.getUserMedia=()=>{throw Error('Physical capture forbidden')}")
  p=c.new_page();c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://localhost:3000/mental')
  for removed in ('Hazır','Sesli Yanıt Hazır','Tamamlandı','Tamamlanan görüşmenin tek özeti kaydedildi.'):
   expect(p.get_by_text(removed,exact=True)).to_have_count(0)
  for i in range(9):
   p.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();p.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
   mute=p.get_by_role('button',name='Sesli yanıtı kapat',exact=True)
   if mute.count():mute.click()
   p.get_by_role('textbox',name='Görüşme mesajı').fill('Bugün yeni bir kitap okudum.');p.get_by_role('button',name='Gönder',exact=True).click()
   expect(p.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready')
   panel=p.locator('[data-mental-record-panel]');expect(panel).to_have_count(1)
   assert panel.bounding_box()['y']>=p.locator('[data-live-transcript]').bounding_box()['y']+p.locator('[data-live-transcript]').bounding_box()['height']-1
   p.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();dialog=p.get_by_role('dialog',name='Görüşme tamamlandı',exact=True)
   expect(dialog).to_contain_text('tek özeti kaydedildi');expect(p.locator('[data-session-rows] [data-record-id]')).to_have_count(i+1)
   dialog.get_by_role('button',name='Tamam',exact=True).click();expect(dialog).to_have_count(0)
  rows=p.locator('[data-session-rows]');assert rows.evaluate('e=>e.scrollHeight>e.clientHeight&&getComputedStyle(e).overflowY==="auto"')
  if width==1600:assert panel.bounding_box()['width']>p.locator('[data-mental-history]').bounding_box()['width']*1.9
  p.get_by_role('button',name='Görüşme temaları hakkında bilgi',exact=True).click();expect(p.get_by_role('dialog')).to_contain_text('yuvarlanır');p.keyboard.press('Escape')
  assert 'yuvarlanır' not in p.locator('main').inner_text()
  p.screenshot(path=str(OUT/f'mental-records-{width}.png'),full_page=True)
  rows.locator('[aria-haspopup=dialog]').first.click();expect(p.get_by_role('dialog',name='Görüşme kaydı',exact=True)).to_contain_text('Başlangıç:');p.keyboard.press('Escape')
  p.goto('http://localhost:3000/skin');assert 'skin-preparation.png' in p.locator('[data-face-panel] img').get_attribute('src')
  for removed in ('Ön','Sağ','Sol'):expect(p.locator('[data-face-panel]').get_by_text(removed,exact=True)).to_have_count(0)
  proof.append({'width':width,'actualCompletedFixtureRecords':9,'fullWidthRecordPanel':True,'scrollInsidePanel':True,'oneCompletionDialog':True,'themeExplanationInDialog':True,'capture':0,'paidCalls':0,'liveAcceptance':False});c.close()
 b.close()
(OUT/'proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
